"""应用接口协议定义。"""

from __future__ import annotations

from typing import Any, Protocol

from .capability import Capability
from .intent import AppIntent


class Application(Protocol):
    """应用插件接口协议。

    所有接入 ARIA 的应用必须实现此接口。
    """

    @property
    def app_id(self) -> str:
        """应用唯一标识，如 'wechat', 'xiaohongshu'。

        全局唯一，用于注册表查找和配置文件引用。
        """
        ...

    @property
    def app_name(self) -> str:
        """应用显示名称，如 '微信', '小红书'。

        用于日志、UI 展示等场景。
        """
        ...

    @property
    def capabilities(self) -> list[Capability]:
        """应用支持的能力列表。

        每个 Capability 定义一个可执行的 action_type。
        """
        ...

    def detect_intent(self, text: str) -> AppIntent | None:
        """从用户输入中检测应用相关意图。

        Args:
            text: 用户原始输入文本

        Returns:
            AppIntent 如果检测到意图，否则 None
        """
        ...

    def execute(self, action_type: str, params: dict[str, Any], *, cancel_checker: Any = None) -> dict[str, Any]:
        """执行应用能力。

        Args:
            action_type: 能力动作类型，必须在 capabilities 列表中
            params: 执行参数字典
            cancel_checker: 可选的取消检查器（manager.check_cancelled）

        Returns:
            执行结果字典，至少包含 'success': bool 字段
        """
        ...

    def get_planner_hint(self) -> str:
        """返回给 LLM 规划器的应用能力提示文本。

        用于在 plan_actions 时告知 LLM 该应用支持哪些操作。
        """
        ...
