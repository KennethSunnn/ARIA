from __future__ import annotations

from typing import Any

from .agent_registry import AgentRegistry
from .context_store import ExecutionContextStore
from .execution_graph import build_execution_graph
from .scheduler import AgentScheduler


class OrchestrationFacade:
    def __init__(self, manager: Any):
        self._manager = manager
        self._registry = AgentRegistry()
        self._registry.register_defaults()
        personality_catalog = getattr(manager, "personality_catalog", None)
        if isinstance(personality_catalog, dict):
            self._registry.set_personality_catalog(personality_catalog)
        manager_scheduler = getattr(manager, "agent_scheduler", None)
        self._scheduler = manager_scheduler if isinstance(manager_scheduler, AgentScheduler) else AgentScheduler()

    def execute_pipeline(
        self,
        task_info: dict[str, Any],
        method: dict[str, Any],
        dialogue_context: str = "",
    ) -> dict[str, Any]:
        sub_tasks = self._manager.split_sub_tasks(task_info, method)
        agents = self._manager.create_agents(sub_tasks)
        topology = "adaptive_parallel_with_merge" if self._manager.choose_collaboration_topology(task_info, sub_tasks) == "parallel_with_merge" else "pipeline"
        graph = build_execution_graph(agents)
        context_store = ExecutionContextStore(self._manager)
        context_store.set_metadata("topology", topology)
        method_ctx = self._manager._methodology_summary_text(method) if method else ""
        results = self._scheduler.run(
            graph=graph,
            manager=self._manager,
            registry=self._registry,
            context_store=context_store,
            method_ctx=method_ctx,
            dialogue_context=dialogue_context,
            topology=topology,
        )
        self._manager.stm.results = results
        check_payload = self._manager.check_result(results)
        return {
            "sub_tasks": sub_tasks,
            "agents": agents,
            "results": results,
            "check_payload": check_payload,
            "topology": topology,
        }
