"""应用注册表 — 管理所有已注册的应用插件。"""

from __future__ import annotations

import logging
from typing import Any

from .application import Application
from .capability import Capability
from .intent import AppIntent

logger = logging.getLogger(__name__)


class ApplicationRegistry:
    """应用注册表，管理所有已注册的应用。"""

    def __init__(self) -> None:
        self._apps: dict[str, Application] = {}
        self._action_type_index: dict[str, str] = {}  # action_type -> app_id

    def register(self, app: Application) -> None:
        """注册应用。

        Args:
            app: 实现 Application 接口的应用实例

        Raises:
            ValueError: 如果 app_id 已存在或 action_type 冲突
        """
        app_id = app.app_id
        if app_id in self._apps:
            raise ValueError(f"应用 {app_id} 已注册")

        # 检查 action_type 冲突
        for cap in app.capabilities:
            if cap.action_type in self._action_type_index:
                existing_app = self._action_type_index[cap.action_type]
                raise ValueError(
                    f"action_type '{cap.action_type}' 冲突：" f"已被应用 {existing_app} 注册，无法注册到 {app_id}"
                )

        # 注册应用和索引
        self._apps[app_id] = app
        for cap in app.capabilities:
            self._action_type_index[cap.action_type] = app_id

        logger.info(f"已注册应用：{app_id} ({app.app_name})，能力数：{len(app.capabilities)}")

    def unregister(self, app_id: str) -> None:
        """注销应用。

        Args:
            app_id: 应用 ID
        """
        if app_id not in self._apps:
            return

        app = self._apps[app_id]
        for cap in app.capabilities:
            self._action_type_index.pop(cap.action_type, None)

        del self._apps[app_id]
        logger.info(f"已注销应用：{app_id}")

    def get_app(self, app_id: str) -> Application | None:
        """获取应用实例。

        Args:
            app_id: 应用 ID

        Returns:
            Application 实例，如果不存在返回 None
        """
        return self._apps.get(app_id)

    def list_apps(self) -> list[Application]:
        """列出所有已注册应用。"""
        return list(self._apps.values())

    def detect_intent(self, text: str) -> tuple[Application, AppIntent] | None:
        """从用户输入中检测应用意图（遍历所有应用）。

        Args:
            text: 用户输入文本

        Returns:
            (Application, AppIntent) 如果检测到，否则 None
            如果多个应用都检测到意图，返回置信度最高的
        """
        best_app: Application | None = None
        best_intent: AppIntent | None = None
        best_confidence = 0.0

        for app in self._apps.values():
            intent = app.detect_intent(text)
            if intent and intent.confidence > best_confidence:
                best_app = app
                best_intent = intent
                best_confidence = intent.confidence

        if best_app and best_intent:
            return best_app, best_intent
        return None

    def get_capability(self, action_type: str) -> tuple[Application, Capability] | None:
        """根据 action_type 查找对应的应用和能力。

        Args:
            action_type: 动作类型，如 'messaging_send'

        Returns:
            (Application, Capability) 如果找到，否则 None
        """
        app_id = self._action_type_index.get(action_type)
        if not app_id:
            return None

        app = self._apps.get(app_id)
        if not app:
            return None

        for cap in app.capabilities:
            if cap.action_type == action_type:
                return app, cap

        return None

    def list_all_action_types(self) -> set[str]:
        """列出所有已注册的 action_type。

        用于动态生成 ALLOWED_ACTION_TYPES。
        """
        return set(self._action_type_index.keys())

    def list_all_capabilities(self) -> list[tuple[Application, Capability]]:
        """列出所有应用的所有能力。

        Returns:
            [(Application, Capability), ...] 列表
        """
        result: list[tuple[Application, Capability]] = []
        for app in self._apps.values():
            for cap in app.capabilities:
                result.append((app, cap))
        return result

    def get_planner_hints(self) -> str:
        """获取所有应用的规划器提示文本（用于 LLM prompt）。

        Returns:
            合并后的提示文本
        """
        hints: list[str] = []
        for app in self._apps.values():
            hint = app.get_planner_hint()
            if hint:
                hints.append(hint)
        return "\n\n".join(hints) if hints else ""
