"""应用能力描述数据类。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CapabilityParameter:
    """能力参数定义。"""

    name: str
    display_name: str
    param_type: str  # 'string' | 'int' | 'bool' | 'list' | 'dict'
    required: bool = True
    description: str = ""
    default: Any = None

    def validate(self, value: Any) -> tuple[bool, str]:
        """验证参数值是否合法。"""
        if self.required and value is None:
            return False, f"参数 {self.name} 是必需的"

        if value is None:
            return True, ""

        type_checks = {
            "string": (str, "字符串"),
            "int": (int, "整数"),
            "bool": (bool, "布尔值"),
            "list": (list, "列表"),
            "dict": (dict, "字典"),
        }
        if self.param_type in type_checks:
            expected_type, type_name = type_checks[self.param_type]
            if not isinstance(value, expected_type):
                return False, f"参数 {self.name} 必须是{type_name}"

        return True, ""


@dataclass(frozen=True)
class Capability:
    """应用能力描述。"""

    action_type: str
    """工具动作类型标识，如 'messaging_send'，全局唯一。"""

    display_name: str
    """用户可见的能力名称，如 '发送消息'。"""

    description: str = ""
    """能力功能描述，LLM 规划器可读。"""

    parameters: tuple[CapabilityParameter, ...] = ()
    """参数列表，使用 tuple 保持 frozen 兼容。"""

    risk_level: str = "medium"
    """执行风险级别：'safe' | 'medium' | 'high'"""

    requires_confirmation: bool = True
    """是否需要用户确认后执行。"""

    planner_hint: str = ""
    """向规划器暴露的额外提示，补充 description。"""

    def validate_params(self, params: dict[str, Any]) -> tuple[bool, str]:
        """验证 action params 字典是否满足参数要求。"""
        for param in self.parameters:
            ok, msg = param.validate(params.get(param.name))
            if not ok:
                return False, msg
        return True, ""

    def to_planner_description(self) -> str:
        """生成给 LLM 规划器读取的能力描述文本。"""
        parts = [f"- {self.action_type}：{self.display_name}"]
        if self.description:
            parts.append(f"  说明：{self.description}")
        if self.planner_hint:
            parts.append(f"  提示：{self.planner_hint}")
        required = [p.name for p in self.parameters if p.required]
        if required:
            parts.append(f"  必填参数：{', '.join(required)}")
        return "\n".join(parts)
