from __future__ import annotations

from typing import Any, Callable

from .action_agent import ActionExecAgent
from .agents import LLMExecAgent

AgentFactory = Callable[[Any], Any]


class AgentRegistry:
    def __init__(self) -> None:
        self._factories: dict[str, AgentFactory] = {}
        self._personality_catalog: dict[str, list[dict[str, Any]]] = {}

    def register(self, agent_type: str, factory: AgentFactory) -> None:
        self._factories[str(agent_type)] = factory

    def register_defaults(self) -> None:
        for agent_type in ("TextExecAgent", "VisionExecAgent", "SpeechExecAgent"):
            self.register(agent_type, lambda manager, _agent_type=agent_type: LLMExecAgent(manager))
        self.register("ActionExecAgent", lambda manager: ActionExecAgent(manager))

    def create(self, agent_type: str, manager: Any) -> Any:
        factory = self._factories.get(str(agent_type))
        if factory is None:
            factory = lambda m: LLMExecAgent(m)
        return factory(manager)

    def set_personality_catalog(self, catalog: dict[str, list[dict[str, Any]]]) -> None:
        self._personality_catalog = {
            str(k): [dict(x) for x in (v or []) if isinstance(x, dict)]
            for k, v in (catalog or {}).items()
        }

    def candidates_for(self, agent_type: str) -> list[dict[str, Any]]:
        return [dict(x) for x in self._personality_catalog.get(str(agent_type), [])]
