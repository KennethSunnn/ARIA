"""执行重试策略 — 为工具执行失败提供智能 fallback。

扩展 interaction_intelligence.py 的 fallback 机制，为更多工具类型提供重试策略。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any


class ExecutionRetryPolicy:
    """工具执行失败时的重试策略。"""

    @staticmethod
    def should_retry_file_operation(action_type: str, result: dict[str, Any]) -> bool:
        """文件操作失败时是否应该重试。"""
        if action_type not in ("file_move", "file_write", "file_delete"):
            return False
        if result.get("success"):
            return False
        stderr = str(result.get("stderr") or "").lower()
        # 文件不存在、路径错误等可以尝试模糊匹配
        return any(k in stderr for k in ("not found", "no such file", "不存在", "找不到"))

    @staticmethod
    def suggest_file_path_alternatives(original_path: str, base_dir: str = ".") -> list[str]:
        """为失败的文件路径提供替代方案（模糊匹配）。"""
        try:
            p = Path(original_path)
            stem = p.stem.lower()
            suffix = p.suffix.lower()
            base = Path(base_dir)
            if not base.is_dir():
                return []

            candidates: list[tuple[int, str]] = []
            for item in base.rglob(f"*{suffix}"):
                if not item.is_file():
                    continue
                score = 0
                if stem in item.stem.lower():
                    score += 100
                if item.name.lower() == p.name.lower():
                    score += 200
                if score > 0:
                    candidates.append((score, str(item)))

            candidates.sort(key=lambda x: -x[0])
            return [path for _, path in candidates[:5]]
        except Exception:
            return []

    @staticmethod
    def should_retry_desktop_app(action_type: str, result: dict[str, Any]) -> bool:
        """桌面应用启动失败时是否应该重试。"""
        if action_type != "desktop_open_app":
            return False
        if result.get("success"):
            return False
        stderr = str(result.get("stderr") or "").lower()
        return any(k in stderr for k in ("not found", "未找到", "找不到", "不存在"))

    @staticmethod
    def suggest_web_alternative(app_name: str) -> str | None:
        """为未找到的桌面应用提供网页版替代。"""
        app_lower = app_name.lower()
        web_alternatives = {
            "wechat": "https://web.wechat.com",
            "微信": "https://web.wechat.com",
            "weixin": "https://web.wechat.com",
            "qq": "https://im.qq.com",
            "钉钉": "https://www.dingtalk.com",
            "dingtalk": "https://www.dingtalk.com",
            "企业微信": "https://work.weixin.qq.com",
            "wps": "https://www.kdocs.cn",
            "word": "https://www.office.com",
            "excel": "https://www.office.com",
            "powerpoint": "https://www.office.com",
            "ppt": "https://www.office.com",
            "photoshop": "https://www.adobe.com",
            "ps": "https://www.adobe.com",
        }
        for key, url in web_alternatives.items():
            if key in app_lower or app_lower in key:
                return url
        return None

    @staticmethod
    def format_retry_suggestion(action_type: str, result: dict[str, Any], alternatives: list[str] | None = None) -> str:
        """格式化重试建议消息。"""
        stderr = str(result.get("stderr") or result.get("message") or "未知错误")
        parts = [f"执行 {action_type} 失败：{stderr}"]

        if alternatives:
            parts.append("建议尝试以下替代方案：")
            for idx, alt in enumerate(alternatives[:3], 1):
                parts.append(f"  {idx}. {alt}")

        return "\n".join(parts)
