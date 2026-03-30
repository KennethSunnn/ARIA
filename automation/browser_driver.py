"""
可选：Playwright 驱动的受控 Chromium，用于 browser_open / browser_click / browser_type。

启用：.env 中 ARIA_PLAYWRIGHT=1，并执行 pip install playwright && playwright install chromium
"""

from __future__ import annotations

import os
import threading
from typing import Any

_lock = threading.RLock()
_pw: Any = None
_browser: Any = None
_context: Any = None
_page: Any = None
_import_error: str | None = None


def is_playwright_enabled() -> bool:
    return os.getenv("ARIA_PLAYWRIGHT", "").strip().lower() in ("1", "true", "yes", "on")


def default_timeout_ms(fallback: int = 30_000) -> int:
    raw = (os.getenv("ARIA_PLAYWRIGHT_DEFAULT_TIMEOUT_MS") or "").strip()
    if raw.isdigit():
        return min(max(int(raw), 500), 300_000)
    return fallback


def _headless() -> bool:
    return os.getenv("ARIA_PLAYWRIGHT_HEADLESS", "").strip().lower() in ("1", "true", "yes", "on")


def ensure_session() -> tuple[bool, str]:
    """启动 Playwright Chromium（若尚未启动）。返回 (ok, error_message)。"""
    global _pw, _browser, _context, _page, _import_error
    with _lock:
        if _page is not None:
            return True, ""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as e:
            _import_error = str(e)
            return False, f"playwright_not_installed:{e}"
        try:
            # 正确初始化：sync_playwright() 返回上下文管理器，需要调用 start()
            _pw_instance = sync_playwright()
            _pw = _pw_instance.start()
            _browser = _pw.chromium.launch(headless=_headless())
            _context = _browser.new_context()
            _page = _context.new_page()
            _import_error = None
            return True, ""
        except Exception as e:
            # 清理失败的状态
            _pw = None
            _browser = None
            _context = None
            _page = None
            return False, f"playwright_init_failed:{str(e)}"


def navigate(url: str, timeout_ms: int | None = None) -> tuple[bool, str]:
    if timeout_ms is None:
        timeout_ms = default_timeout_ms(60_000)
    u = (url or "").strip()
    if not u.startswith(("http://", "https://")):
        u = "https://" + u.lstrip("/")
    ok, err = ensure_session()
    if not ok:
        return False, err
    with _lock:
        try:
            assert _page is not None
            _page.goto(u, wait_until="domcontentloaded", timeout=timeout_ms)
            return True, ""
        except Exception as e:
            return False, str(e)


def click(selector: str, timeout_ms: int | None = None, navigate_url: str | None = None) -> tuple[bool, str]:
    if timeout_ms is None:
        timeout_ms = default_timeout_ms(30_000)
    sel = (selector or "").strip()
    if not sel:
        return False, "missing_selector"
    ok, err = ensure_session()
    if not ok:
        return False, err
    with _lock:
        try:
            assert _page is not None
            if navigate_url:
                u = navigate_url.strip()
                if u and not u.startswith(("http://", "https://")):
                    u = "https://" + u.lstrip("/")
                if u:
                    _page.goto(u, wait_until="domcontentloaded", timeout=60_000)
            _page.click(sel, timeout=timeout_ms)
            return True, ""
        except Exception as e:
            return False, str(e)


def fill(selector: str, text: str, timeout_ms: int | None = None, navigate_url: str | None = None) -> tuple[bool, str]:
    if timeout_ms is None:
        timeout_ms = default_timeout_ms(30_000)
    sel = (selector or "").strip()
    if not sel:
        return False, "missing_selector"
    ok, err = ensure_session()
    if not ok:
        return False, err
    with _lock:
        try:
            assert _page is not None
            if navigate_url:
                u = navigate_url.strip()
                if u and not u.startswith(("http://", "https://")):
                    u = "https://" + u.lstrip("/")
                if u:
                    _page.goto(u, wait_until="domcontentloaded", timeout=60_000)
            _page.fill(sel, text, timeout=timeout_ms)
            return True, ""
        except Exception as e:
            return False, str(e)


def find_elements(selector: str, text_contains: str | None = None, timeout_ms: int = 10_000) -> tuple[bool, list[dict]]:
    """查找匹配的元素，返回位置、文本等信息"""
    sel = (selector or "").strip()
    if not sel:
        return False, [], "missing_selector"
    ok, err = ensure_session()
    if not ok:
        return False, [], err
    with _lock:
        try:
            assert _page is not None
            elements = _page.query_selector_all(sel)
            results = []
            for idx, el in enumerate(elements):
                try:
                    text = el.text_content(timeout=timeout_ms) or ""
                    if text_contains and text_contains not in text:
                        continue
                    box = el.bounding_box()
                    results.append({
                        "index": idx,
                        "text": text.strip(),
                        "x": box.get("x", 0) if box else 0,
                        "y": box.get("y", 0) if box else 0,
                        "width": box.get("width", 0) if box else 0,
                        "height": box.get("height", 0) if box else 0,
                    })
                except Exception:
                    continue
            return True, results, ""
        except Exception as e:
            return False, [], str(e)


def hover(selector: str, timeout_ms: int = 10_000) -> tuple[bool, str]:
    """鼠标悬停操作"""
    sel = (selector or "").strip()
    if not sel:
        return False, "missing_selector"
    ok, err = ensure_session()
    if not ok:
        return False, err
    with _lock:
        try:
            assert _page is not None
            _page.hover(sel, timeout=timeout_ms)
            return True, ""
        except Exception as e:
            return False, str(e)


def select_option(selector: str, value: str, timeout_ms: int = 10_000) -> tuple[bool, str]:
    """选择下拉框选项"""
    sel = (selector or "").strip()
    if not sel:
        return False, "missing_selector"
    ok, err = ensure_session()
    if not ok:
        return False, err
    with _lock:
        try:
            assert _page is not None
            _page.select_option(sel, value, timeout=timeout_ms)
            return True, ""
        except Exception as e:
            return False, str(e)


def upload_file(selector: str, file_path: str, timeout_ms: int = 30_000) -> tuple[bool, str]:
    """上传文件"""
    sel = (selector or "").strip()
    if not sel:
        return False, "missing_selector"
    if not file_path:
        return False, "missing_file_path"
    ok, err = ensure_session()
    if not ok:
        return False, err
    with _lock:
        try:
            assert _page is not None
            _page.set_input_files(sel, file_path, timeout=timeout_ms)
            return True, ""
        except Exception as e:
            return False, str(e)


def scroll_to(selector: str | None = None, timeout_ms: int = 10_000) -> tuple[bool, str]:
    """滚动到指定元素，selector 为空时滚动到底部"""
    ok, err = ensure_session()
    if not ok:
        return False, err
    with _lock:
        try:
            assert _page is not None
            if selector:
                sel = selector.strip()
                if sel:
                    _page.locator(sel).scroll_into_view_if_needed(timeout=timeout_ms)
                    return True, ""
            # 滚动到底部
            _page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            return True, ""
        except Exception as e:
            return False, str(e)


def wait_for_element(selector: str, timeout_ms: int | None = None) -> tuple[bool, str]:
    """等待元素出现"""
    if timeout_ms is None:
        timeout_ms = default_timeout_ms(30_000)
    sel = (selector or "").strip()
    if not sel:
        return False, "missing_selector"
    ok, err = ensure_session()
    if not ok:
        return False, err
    with _lock:
        try:
            assert _page is not None
            _page.wait_for_selector(sel, state="visible", timeout=timeout_ms)
            return True, ""
        except Exception as e:
            return False, str(e)


def execute_javascript(script: str) -> tuple[bool, Any]:
    """执行自定义 JavaScript"""
    if not script:
        return False, None, "missing_script"
    ok, err = ensure_session()
    if not ok:
        return False, None, err
    with _lock:
        try:
            assert _page is not None
            result = _page.evaluate(script)
            return True, result, ""
        except Exception as e:
            return False, None, str(e)


def get_page_content() -> tuple[bool, str]:
    """获取当前页面完整内容（HTML 或文本）"""
    ok, err = ensure_session()
    if not ok:
        return False, "", err
    with _lock:
        try:
            assert _page is not None
            content = _page.content()
            return True, content, ""
        except Exception as e:
            return False, "", str(e)


def press_key(key: str, selector: str | None = None, timeout_ms: int | None = None) -> tuple[bool, str]:
    """键盘按键，key 为 Playwright 接受的键名，如 Enter、Tab、Escape。"""
    k = (key or "").strip()
    if not k:
        return False, "missing_key"
    if timeout_ms is None:
        timeout_ms = default_timeout_ms(10_000)
    ok, err = ensure_session()
    if not ok:
        return False, err
    with _lock:
        try:
            assert _page is not None
            sel = (selector or "").strip()
            if sel:
                _page.locator(sel).press(k, timeout=timeout_ms)
            else:
                _page.keyboard.press(k)
            return True, ""
        except Exception as e:
            return False, str(e)


def playwright_package_installed() -> bool:
    try:
        import playwright  # noqa: F401
        return True
    except ImportError:
        return False


def capability_summary_for_planner() -> str:
    """规划阶段不启动浏览器，仅根据环境变量与是否已安装包描述能力边界。"""
    if not is_playwright_enabled():
        return (
            "【浏览器自动化】当前未启用 Playwright（未设置 ARIA_PLAYWRIGHT=1）。"
            "browser_open 仅用系统默认浏览器打开链接；browser_click/browser_type 为模拟占位，无法在页面内真实点击或输入。"
            "勿向用户承诺已完成淘宝/微信等客户端内操作。"
        )
    if not playwright_package_installed():
        return (
            "【浏览器自动化】已设置 ARIA_PLAYWRIGHT=1，但未安装 playwright 包。"
            "请执行: pip install playwright && playwright install chromium。"
            "在此之前仍勿承诺真实页面内点击/输入。"
        )
    return (
        "【浏览器自动化】Playwright 已配置：执行时 browser_open 将用受控 Chromium 导航；"
        "browser_click / browser_type 使用 CSS 选择器 params.selector，可选 params.url 在操作前先打开页面；"
        "browser_press 模拟键盘；环境变量 ARIA_PLAYWRIGHT_DEFAULT_TIMEOUT_MS 可调默认等待（毫秒）。"
        "新增功能：browser_find（查找元素），browser_hover（悬停），browser_select（选择下拉框），browser_upload（上传文件），"
        "browser_scroll（滚动页面），browser_wait（等待元素），browser_js（执行 JavaScript），get_page_content（获取页面内容）。"
        "多步网页操作须在同一 Playwright 会话内串联 browser_open → wait → type → click，勿穿插仅打开系统浏览器打断会话。"
        "强 JS/登录/验证码站点仍可能失败；勿承诺绕过风控或代用户完成微信私聊等。"
    )

