"""应用意图识别结果数据类。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AppIntent:
    """应用意图识别结果。"""

    app_id: str
    """检测到的应用 ID，如 'wechat'。"""

    operation: str
    """操作类型，如 'send_message', 'post', 'check_login'。"""

    confidence: float
    """置信度 0.0–1.0。"""

    extracted_params: dict[str, Any] = field(default_factory=dict)
    """从用户输入中提取的参数，直接可用于构造 action params。"""

    raw_text: str = ""
    """原始用户输入文本。"""

    def to_action_type(self) -> str:
        """将意图转为 action_type 字符串。

        约定格式：{app_id}_{operation}，如 messaging_send_message → 但具体映射
        由各 Application 实现决定（operation 可能已经是完整的 action_type）。
        """
        return self.operation

    @property
    def is_confident(self) -> bool:
        """置信度是否足够高（≥ 0.7），足以跳过 LLM 二次规划。"""
        return self.confidence >= 0.7
