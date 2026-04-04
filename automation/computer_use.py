"""
Computer Use 层：截屏与屏幕坐标级 GUI 操作（对标 Claude Computer Use 的客户端执行面）。

环境变量：
- ARIA_COMPUTER_USE：设为 0/false/off 可整体关闭（默认开启）。
- ARIA_COMPUTER_USE_ALLOW_REGIONS：JSON 数组，元素为 [left, top, width, height]；非空时点击/拖拽端点必须落在并集内。
- ARIA_COMPUTER_USE_BLOCK_TITLE_KEYWORDS：逗号分隔；若当前前台窗口标题包含任一子串（忽略大小写），则拒绝执行 computer_click 等变异动作。
"""

from __future__ import annotations

import base64
import io
import json
import logging
import os
import sys
import time
from typing import Any

logger = logging.getLogger(__name__)


def is_computer_use_enabled() -> bool:
    v = (os.getenv("ARIA_COMPUTER_USE") or "1").strip().lower()
    return v not in ("0", "false", "no", "off", "disabled")


def load_allow_regions() -> list[tuple[int, int, int, int]]:
    raw = (os.getenv("ARIA_COMPUTER_USE_ALLOW_REGIONS") or "").strip()
    if not raw:
        return []
    try:
        data = json.loads(raw)
        if not isinstance(data, list):
            return []
        out: list[tuple[int, int, int, int]] = []
        for item in data:
            if isinstance(item, (list, tuple)) and len(item) == 4:
                out.append(tuple(int(x) for x in item))
        return out
    except Exception:
        logger.warning("computer_use_invalid_allow_regions_json")
        return []


def virtual_screen_metrics() -> dict[str, int]:
    if sys.platform == "win32":
        try:
            import ctypes
            u = ctypes.windll.user32
            left = int(u.GetSystemMetrics(76))
            top = int(u.GetSystemMetrics(77))
            vw = int(u.GetSystemMetrics(78))
            vh = int(u.GetSystemMetrics(79))
            return {"left": left, "top": top, "width": vw, "height": vh}
        except Exception:
            pass
    try:
        from PIL import ImageGrab
        img = ImageGrab.grab(all_screens=True)
        w, h = img.size
        return {"left": 0, "top": 0, "width": int(w), "height": int(h)}
    except Exception:
        return {"left": 0, "top": 0, "width": 1920, "height": 1080}


def point_in_allow_regions(x: int, y: int, regions: list[tuple[int, int, int, int]]) -> bool:
    if not regions:
        return True
    for left, top, w, h in regions:
        if left <= x < left + w and top <= y < top + h:
            return True
    return False


def resolve_screen_point(params: dict[str, Any], *, metrics: dict[str, int] | None = None) -> tuple[int, int] | None:
    m = metrics or virtual_screen_metrics()
    left, top, vw, vh = m["left"], m["top"], m["width"], m["height"]
    space = str(params.get("coord_space") or "absolute").strip().lower()
    try:
        if space in ("normalized_1000", "norm_1000", "1000"):
            nx = float(params.get("x"))
            ny = float(params.get("y"))
            px = left + int(round(nx / 1000.0 * vw))
            py = top + int(round(ny / 1000.0 * vh))
            return px, py
        px = int(params.get("x"))
        py = int(params.get("y"))
        return px, py
    except (TypeError, ValueError):
        return None


def foreground_window_title() -> str:
    if sys.platform != "win32":
        return ""
    try:
        import ctypes
        u32 = ctypes.windll.user32
        hwnd = u32.GetForegroundWindow()
        if not hwnd:
            return ""
        buf = ctypes.create_unicode_buffer(1024)
        u32.GetWindowTextW(hwnd, buf, 1024)
        return buf.value or ""
    except Exception:
        return ""


def blocked_by_sensitive_title() -> tuple[bool, str]:
    raw = (os.getenv("ARIA_COMPUTER_USE_BLOCK_TITLE_KEYWORDS") or "").strip()
    if not raw:
        return False, ""
    kws = [k.strip().lower() for k in raw.split(",") if k.strip()]
    if not kws:
        return False, ""
    title = foreground_window_title().lower()
    for k in kws:
        if k in title:
            return True, k
    return False, ""


def ensure_mutation_allowed(x: int, y: int, x2: int | None = None, y2: int | None = None) -> tuple[bool, str]:
    if not is_computer_use_enabled():
        return False, "computer_use_disabled"
    blocked, kw = blocked_by_sensitive_title()
    if blocked:
        return False, f"sensitive_foreground_title:{kw}"
    regions = load_allow_regions()
    if not point_in_allow_regions(x, y, regions):
        return False, "click_outside_allow_regions"
    if x2 is not None and y2 is not None and not point_in_allow_regions(x2, y2, regions):
        return False, "drag_end_outside_allow_regions"
    return True, ""


def _import_pyautogui():
    import pyautogui
    pyautogui.FAILSAFE = True
    return pyautogui


def capture_screen_pil(region: tuple[int, int, int, int] | None = None):
    from automation.screen_ocr import capture_screen
    return capture_screen(region)


def capture_jpeg_data_url(*, max_side: int = 1280, quality: int = 75, region: tuple[int, int, int, int] | None = None) -> str:
    img = capture_screen_pil(region)
    from PIL import Image
    if max_side > 0:
        w, h = img.size
        m = max(w, h)
        if m > max_side:
            scale = max_side / float(m)
            nw = max(1, int(w * scale))
            nh = max(1, int(h * scale))
            try:
                resample = Image.Resampling.LANCZOS
            except AttributeError:
                resample = Image.LANCZOS
            img = img.resize((nw, nh), resample)
    buf = io.BytesIO()
    rgb = img.convert("RGB")
    rgb.save(buf, format="JPEG", quality=max(30, min(95, int(quality))))
    b64 = base64.standard_b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{b64}"


def capability_summary_for_planner() -> str:
    if not is_computer_use_enabled():
        return "【Computer Use】已关闭（ARIA_COMPUTER_USE=0）。\n"
    m = virtual_screen_metrics()
    regs = load_allow_regions()
    reg_hint = "未配置区域白名单（全虚拟屏可点）。" if not regs else f"已配置点击白名单 {len(regs)} 个矩形，坐标须在白名单内。"
    return (
        f"【Computer Use】已启用：虚拟屏原点=({m['left']},{m['top']}) 尺寸={m['width']}x{m['height']}。{reg_hint}\n"
        "工具：computer_screenshot；computer_click / computer_double_click（params.x,params.y，可选 coord_space=normalized_1000）；"
        "computer_move；computer_drag（x,y,x2,y2）；computer_scroll（x,y,clicks）；computer_key（params.keys 如 ctrl+c）；"
        "computer_type（params.text）；computer_wait（params.seconds）。浏览器内优先 browser_*。\n"
    )


def run_click(params: dict[str, Any], *, button: str = "left", clicks: int = 1) -> dict[str, Any]:
    pt = resolve_screen_point(params)
    if not pt:
        return {"success": False, "message": "bad_coordinates", "stderr": "missing_or_invalid_x_y"}
    x, y = pt
    ok, reason = ensure_mutation_allowed(x, y)
    if not ok:
        return {"success": False, "message": reason, "stderr": reason}
    try:
        pg = _import_pyautogui()
        pg.moveTo(x, y, duration=0.15)
        if clicks >= 2:
            pg.click(x, y, button=button, clicks=2, interval=0.08)
        else:
            pg.click(x, y, button=button)
        return {"success": True, "message": "computer_click_ok", "stdout": f"clicked_at=({x},{y}) button={button} clicks={clicks}"}
    except Exception as e:
        return {"success": False, "message": "click_failed", "stderr": str(e)}


def run_move(params: dict[str, Any]) -> dict[str, Any]:
    pt = resolve_screen_point(params)
    if not pt:
        return {"success": False, "message": "bad_coordinates", "stderr": "missing_or_invalid_x_y"}
    x, y = pt
    ok, reason = ensure_mutation_allowed(x, y)
    if not ok:
        return {"success": False, "message": reason, "stderr": reason}
    try:
        pg = _import_pyautogui()
        dur = float(params.get("duration") or 0.2)
        pg.moveTo(x, y, duration=max(0.05, min(3.0, dur)))
        return {"success": True, "message": "computer_move_ok", "stdout": f"moved_to=({x},{y})"}
    except Exception as e:
        return {"success": False, "message": "move_failed", "stderr": str(e)}


def run_drag(params: dict[str, Any]) -> dict[str, Any]:
    m = virtual_screen_metrics()
    p1 = resolve_screen_point(params, metrics=m)
    p2 = resolve_screen_point({"x": params.get("x2"), "y": params.get("y2"), "coord_space": params.get("coord_space") or "absolute"}, metrics=m)
    if not p1 or not p2:
        return {"success": False, "message": "bad_coordinates", "stderr": "need x,y,x2,y2"}
    x, y = p1
    x2, y2 = p2
    ok, reason = ensure_mutation_allowed(x, y, x2, y2)
    if not ok:
        return {"success": False, "message": reason, "stderr": reason}
    try:
        pg = _import_pyautogui()
        pg.moveTo(x, y, duration=0.12)
        pg.drag(x2 - x, y2 - y, duration=float(params.get("duration") or 0.3), button=str(params.get("button") or "left"))
        return {"success": True, "message": "computer_drag_ok", "stdout": f"drag ({x},{y})->({x2},{y2})"}
    except Exception as e:
        return {"success": False, "message": "drag_failed", "stderr": str(e)}


def run_scroll(params: dict[str, Any]) -> dict[str, Any]:
    pt = resolve_screen_point(params)
    if not pt:
        return {"success": False, "message": "bad_coordinates", "stderr": "missing_or_invalid_x_y"}
    x, y = pt
    ok, reason = ensure_mutation_allowed(x, y)
    if not ok:
        return {"success": False, "message": reason, "stderr": reason}
    try:
        clicks = int(params.get("clicks") or 0)
    except (TypeError, ValueError):
        return {"success": False, "message": "bad_clicks", "stderr": "clicks_must_be_int"}
    try:
        pg = _import_pyautogui()
        pg.moveTo(x, y, duration=0.12)
        pg.scroll(clicks)
        return {"success": True, "message": "computer_scroll_ok", "stdout": f"scroll_at=({x},{y}) clicks={clicks}"}
    except Exception as e:
        return {"success": False, "message": "scroll_failed", "stderr": str(e)}


def run_key(params: dict[str, Any]) -> dict[str, Any]:
    raw = str(params.get("keys") or "").strip()
    if not raw:
        return {"success": False, "message": "missing_keys", "stderr": "params.keys required"}
    blocked, kw = blocked_by_sensitive_title()
    if blocked:
        return {"success": False, "message": f"sensitive_foreground_title:{kw}", "stderr": "blocked"}
    parts = [p.strip().lower() for p in raw.replace(" ", "").split("+") if p.strip()]
    if not parts:
        return {"success": False, "message": "empty_keys", "stderr": raw}
    try:
        pg = _import_pyautogui()
        if len(parts) == 1:
            pg.press(parts[0])
        else:
            pg.hotkey(*parts)
        return {"success": True, "message": "computer_key_ok", "stdout": f"key={raw}"}
    except Exception as e:
        return {"success": False, "message": "key_failed", "stderr": str(e)}


def run_type_text(params: dict[str, Any]) -> dict[str, Any]:
    text = str(params.get("text") or "")
    blocked, kw = blocked_by_sensitive_title()
    if blocked:
        return {"success": False, "message": f"sensitive_foreground_title:{kw}", "stderr": "blocked"}
    try:
        interval = float(params.get("interval") or 0.03)
    except (TypeError, ValueError):
        interval = 0.03
    try:
        pg = _import_pyautogui()
        pg.write(text, interval=max(0.0, min(0.5, interval)))
        return {"success": True, "message": "computer_type_ok", "stdout": f"typed_len={len(text)}"}
    except Exception as e:
        return {"success": False, "message": "type_failed", "stderr": str(e)}


def run_wait(params: dict[str, Any]) -> dict[str, Any]:
    try:
        sec = float(params.get("seconds") or params.get("duration") or 1.0)
    except (TypeError, ValueError):
        sec = 1.0
    sec = max(0.0, min(120.0, sec))
    time.sleep(sec)
    return {"success": True, "message": "computer_wait_ok", "stdout": f"waited_s={sec}"}


def run_screenshot_info(params: dict[str, Any]) -> dict[str, Any]:
    if not is_computer_use_enabled():
        return {"success": False, "message": "computer_use_disabled", "stderr": "ARIA_COMPUTER_USE 已关闭"}
    region = params.get("region")
    reg_tuple = None
    if isinstance(region, (list, tuple)) and len(region) == 4:
        reg_tuple = tuple(int(x) for x in region)
    try:
        img = capture_screen_pil(reg_tuple)
        w, h = img.size
        m = virtual_screen_metrics()
        return {"success": True, "message": "computer_screenshot_ok", "stdout": f"image_size={w}x{h} virtual_screen={m['width']}x{m['height']} origin=({m['left']},{m['top']})"}
    except Exception as e:
        return {"success": False, "message": "screenshot_failed", "stderr": str(e)}
