from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from automation import browser_driver, computer_use


@dataclass
class IntelligenceResult:
    success: bool
    message: str
    confidence: float = 0.0
    strategy_path: str = "rule_path"
    fallback_used: bool = False
    safe_block_reason: str = ""
    evidence: list[str] | None = None
    decision_trace: list[str] | None = None


class InteractionIntelligenceCore:
    """
    统一智能内核（轻量第一版）：
    - 规范不同执行器返回结构（strategy_path/confidence/safe_block_reason）
    - 在规则路径失败时，为 browser_* 动作提供文本语义回退
    """

    def _as_float(self, v: Any, default: float = 0.0) -> float:
        try:
            x = float(v)
            if x < 0:
                return 0.0
            if x > 1:
                return 1.0
            return x
        except Exception:
            return default

    def normalize_result(self, action_type: str, result: dict[str, Any]) -> dict[str, Any]:
        out = dict(result or {})
        success = bool(out.get("success"))
        out.setdefault("strategy_path", "rule_path")
        out.setdefault("fallback_used", False)
        out.setdefault("safe_block_reason", "")
        out.setdefault("decision_trace", [])
        if "confidence" not in out:
            out["confidence"] = 0.9 if success else 0.35
        else:
            out["confidence"] = self._as_float(out.get("confidence"), 0.9 if success else 0.35)
        if "evidence" not in out:
            out["evidence"] = []
        # 统一错误语义映射，便于上层 UI 与日志聚合
        err = str(out.get("stderr") or "").lower()
        msg = str(out.get("message") or "").lower()
        if not success and not out.get("safe_block_reason"):
            if "need_disambiguation" in err or "need_disambiguation" in msg:
                out["safe_block_reason"] = "need_disambiguation"
            elif "unresolved" in err or "not_found" in err or "missing_selector" in err:
                out["safe_block_reason"] = "unresolved_target"
            elif "unsafe" in err or "blocked" in err:
                out["safe_block_reason"] = "unsafe_to_continue"
        return out

    def should_try_browser_fallback(
        self,
        action_type: str,
        action: dict[str, Any],
        result: dict[str, Any],
    ) -> bool:
        if action_type not in ("browser_click", "browser_type", "browser_find", "browser_wait"):
            return False
        if bool(result.get("success")):
            return False
        if not (browser_driver.is_playwright_enabled() and browser_driver.playwright_package_installed()):
            return False
        p = action.get("params") if isinstance(action.get("params"), dict) else {}
        selector = str(p.get("selector") or "").strip()
        # 常见选择器失效再回退
        err = str(result.get("stderr") or "").lower()
        if "missing_selector" in err:
            return True
        if "timeout" in err or "failed" in err or "not found" in err:
            return True
        return bool(selector)

    def try_browser_fallback(
        self,
        action_type: str,
        action: dict[str, Any],
        previous_result: dict[str, Any],
    ) -> dict[str, Any] | None:
        p = action.get("params") if isinstance(action.get("params"), dict) else {}
        trace: list[str] = ["rule_path_failed"]
        evidence: list[str] = []

        if action_type == "browser_click":
            text_hint = str(
                p.get("text")
                or p.get("text_contains")
                or p.get("label")
                or p.get("selector")
                or action.get("target")
                or ""
            ).strip()
            if not text_hint:
                return None
            ok, err = browser_driver.click_by_text(text_hint)
            trace.append("fallback_click_by_text")
            if ok:
                evidence.append(f"text_hint:{text_hint[:80]}")
                return {
                    "success": True,
                    "message": f"browser_click_fallback:{text_hint}",
                    "strategy_path": "rule_path->perception_fallback",
                    "fallback_used": True,
                    "confidence": 0.72,
                    "safe_block_reason": "",
                    "decision_trace": trace,
                    "evidence": evidence,
                }
            return {
                **dict(previous_result or {}),
                "strategy_path": "rule_path->perception_fallback_failed",
                "fallback_used": True,
                "confidence": 0.25,
                "safe_block_reason": "unresolved_target",
                "decision_trace": trace + [f"fallback_error:{err}"],
            }

        if action_type == "browser_type":
            text = str(p.get("text") or "")
            label = str(
                p.get("label")
                or p.get("text_contains")
                or p.get("target_text")
                or p.get("selector")
                or action.get("target")
                or ""
            ).strip()
            if not text or not label:
                return None
            ok, err = browser_driver.fill_by_related_text(label, text)
            trace.append("fallback_fill_by_related_text")
            if ok:
                evidence.append(f"label:{label[:80]}")
                return {
                    "success": True,
                    "message": f"browser_type_fallback:{label}",
                    "stdout": text[:200],
                    "strategy_path": "rule_path->perception_fallback",
                    "fallback_used": True,
                    "confidence": 0.68,
                    "safe_block_reason": "",
                    "decision_trace": trace,
                    "evidence": evidence,
                }
            return {
                **dict(previous_result or {}),
                "strategy_path": "rule_path->perception_fallback_failed",
                "fallback_used": True,
                "confidence": 0.2,
                "safe_block_reason": "unresolved_target",
                "decision_trace": trace + [f"fallback_error:{err}"],
            }

        if action_type == "browser_find":
            text_hint = str(
                p.get("text_contains")
                or p.get("text")
                or p.get("selector")
                or action.get("target")
                or ""
            ).strip()
            if not text_hint:
                return None
            ok, rows, err = browser_driver.find_by_text(text_hint)
            trace.append("fallback_find_by_text")
            if ok:
                evidence.append(f"rows:{len(rows)}")
                return {
                    "success": True,
                    "message": f"browser_find_fallback:{text_hint}",
                    "stdout": f"Found {len(rows)} element(s): {rows[:5]}",
                    "strategy_path": "rule_path->perception_fallback",
                    "fallback_used": True,
                    "confidence": 0.66 if rows else 0.45,
                    "safe_block_reason": "" if rows else "unresolved_target",
                    "decision_trace": trace,
                    "evidence": evidence,
                }
            return {
                **dict(previous_result or {}),
                "strategy_path": "rule_path->perception_fallback_failed",
                "fallback_used": True,
                "confidence": 0.2,
                "safe_block_reason": "unresolved_target",
                "decision_trace": trace + [f"fallback_error:{err}"],
            }

        if action_type == "browser_wait":
            text_hint = str(
                p.get("text")
                or p.get("text_contains")
                or p.get("selector")
                or action.get("target")
                or ""
            ).strip()
            timeout_ms = int(p.get("timeout_ms") or 30_000)
            if not text_hint:
                return None
            ok, err = browser_driver.wait_for_text(text_hint, timeout_ms=timeout_ms)
            trace.append("fallback_wait_for_text")
            if ok:
                return {
                    "success": True,
                    "message": f"browser_wait_fallback:{text_hint}",
                    "strategy_path": "rule_path->perception_fallback",
                    "fallback_used": True,
                    "confidence": 0.7,
                    "safe_block_reason": "",
                    "decision_trace": trace,
                    "evidence": [f"text:{text_hint[:80]}"],
                }
            return {
                **dict(previous_result or {}),
                "strategy_path": "rule_path->perception_fallback_failed",
                "fallback_used": True,
                "confidence": 0.2,
                "safe_block_reason": "unresolved_target",
                "decision_trace": trace + [f"fallback_error:{err}"],
            }
        return None

    # ── Computer Use (pyautogui) fallback for desktop_* ──────────────────────

    def should_try_computer_fallback(
        self,
        action_type: str,
        action: dict[str, Any],
        result: dict[str, Any],
    ) -> bool:
        """desktop_hotkey / desktop_type / desktop_sequence 失败时，降级到 pyautogui。"""
        if action_type not in ("desktop_hotkey", "desktop_type", "desktop_sequence"):
            return False
        if bool(result.get("success")):
            return False
        return computer_use.is_computer_use_enabled()

    def try_computer_fallback(
        self,
        action_type: str,
        action: dict[str, Any],
        previous_result: dict[str, Any],
    ) -> dict[str, Any] | None:
        """用 pyautogui 重试失败的 desktop_* 动作。"""
        p = action.get("params") if isinstance(action.get("params"), dict) else {}
        trace: list[str] = ["uia_path_failed", "computer_use_fallback"]

        if action_type == "desktop_hotkey":
            hotkey = str(p.get("hotkey") or "").strip()
            if not hotkey:
                return None
            # pywinauto 格式 "ctrl+c" → pyautogui 格式 ["ctrl", "c"]
            keys = hotkey.lower().replace("{", "").replace("}", "")
            result = computer_use.run_key({"keys": keys})
            if result.get("success"):
                return {
                    **result,
                    "strategy_path": "uia_path->computer_use_fallback",
                    "fallback_used": True,
                    "confidence": 0.72,
                    "decision_trace": trace,
                }
            return {
                **dict(previous_result or {}),
                "strategy_path": "uia_path->computer_use_fallback_failed",
                "fallback_used": True,
                "confidence": 0.2,
                "decision_trace": trace + [f"fallback_error:{result.get('stderr', '')}"],
            }

        if action_type == "desktop_type":
            text = str(p.get("text") or p.get("content") or "")
            if not text:
                return None
            result = computer_use.run_type_text({"text": text})
            if result.get("success"):
                return {
                    **result,
                    "stdout": text[:400],
                    "strategy_path": "uia_path->computer_use_fallback",
                    "fallback_used": True,
                    "confidence": 0.70,
                    "decision_trace": trace,
                }
            return {
                **dict(previous_result or {}),
                "strategy_path": "uia_path->computer_use_fallback_failed",
                "fallback_used": True,
                "confidence": 0.2,
                "decision_trace": trace + [f"fallback_error:{result.get('stderr', '')}"],
            }

        if action_type == "desktop_sequence":
            # 逐步对每个子步骤尝试 pyautogui，部分成功也返回最终状态
            steps = p.get("steps") if isinstance(p.get("steps"), list) else []
            if not steps:
                return None
            success_count = 0
            for step in steps:
                stype = str(step.get("type") or "").strip()
                if stype == "hotkey":
                    keys = str(step.get("hotkey") or "").lower().replace("{", "").replace("}", "")
                    r = computer_use.run_key({"keys": keys})
                elif stype == "type":
                    r = computer_use.run_type_text({"text": str(step.get("text") or "")})
                elif stype == "sleep":
                    import time
                    try:
                        time.sleep(float(step.get("duration") or 0.5))
                    except Exception:
                        pass
                    r = {"success": True}
                else:
                    r = {"success": False, "stderr": f"unsupported_step_type:{stype}"}
                if r.get("success"):
                    success_count += 1
            ok = success_count == len(steps)
            return {
                "success": ok,
                "message": "desktop_sequence_computer_use_fallback",
                "stdout": f"steps={len(steps)} success={success_count}",
                "strategy_path": "uia_path->computer_use_fallback",
                "fallback_used": True,
                "confidence": 0.65 if ok else 0.3,
                "decision_trace": trace,
            }

        return None
