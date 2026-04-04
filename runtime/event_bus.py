from __future__ import annotations

from typing import Any


class WorkflowEventBus:
    def __init__(self, manager: Any):
        self._manager = manager

    def emit(
        self,
        stage: str,
        status: str,
        agent_code: str,
        message: str,
        payload: dict[str, Any] | None = None,
        agent_name_override: str | None = None,
    ) -> None:
        self._manager.push_event(
            stage,
            status,
            agent_code,
            message,
            payload or {},
            agent_name_override=agent_name_override,
        )

    def log(self, agent_name: str, content: str, status: str) -> None:
        self._manager.push_log(agent_name, content, status)

    def thought(self, agent_code: str, content: str) -> None:
        self._manager.record_model_thought(agent_code, content)
