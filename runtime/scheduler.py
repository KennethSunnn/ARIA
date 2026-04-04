from __future__ import annotations

import os
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
import time
from typing import Any

from .agents import AgentExecutionInput
from .context_store import ExecutionContextStore
from .execution_graph import ExecutionGraph


class AgentScheduler:
    def __init__(self, max_parallel_agents: int | None = None) -> None:
        env_value = os.getenv("ARIA_AGENT_MAX_PARALLEL", "2")
        try:
            env_parallel = max(1, int(env_value or "2"))
        except (TypeError, ValueError):
            env_parallel = 2
        if max_parallel_agents is None:
            max_parallel_agents = env_parallel
        self.max_parallel_agents = max(1, int(max_parallel_agents))

    def run(
        self,
        graph: ExecutionGraph,
        manager: Any,
        registry: Any,
        context_store: ExecutionContextStore,
        method_ctx: str,
        dialogue_context: str,
        topology: str = "pipeline",
    ) -> list[dict[str, Any]]:
        index_by_node_id = {node.node_id: idx for idx, node in enumerate(graph.nodes)}
        unresolved = graph.unresolved_dependencies()
        if unresolved:
            raise ValueError(f"execution graph has unresolved dependencies: {unresolved}")

        node_by_id = {node.node_id: node for node in graph.nodes}
        pending: set[str] = set(node_by_id)
        completed: set[str] = set()
        started: set[str] = set()
        future_to_node: dict[Future, str] = {}
        results: dict[str, dict[str, Any]] = {}
        started_at: dict[str, float] = {}

        with ThreadPoolExecutor(max_workers=self.max_parallel_agents) as pool:
            while pending or future_to_node:
                manager.check_cancelled("agent_schedule_loop")
                ready_nodes = [
                    node_by_id[node_id]
                    for node_id in sorted(
                        pending,
                        key=lambda nid: index_by_node_id.get(nid, 0),
                    )
                    if node_id not in started and set(node_by_id[node_id].depends_on).issubset(completed)
                ]

                for node in ready_nodes:
                    if len(future_to_node) >= self.max_parallel_agents:
                        break
                    started.add(node.node_id)
                    pending.discard(node.node_id)
                    started_at[node.node_id] = time.perf_counter()
                    self._emit_scheduler_event(
                        manager=manager,
                        status="running",
                        summary=f"scheduler start: {node.node_id}",
                        payload={
                            "node_id": node.node_id,
                            "depends_on": list(node.depends_on),
                            "in_flight": len(future_to_node) + 1,
                            "pending": len(pending),
                            "topology": topology,
                        },
                    )
                    future = pool.submit(
                        self._execute_node,
                        manager=manager,
                        registry=registry,
                        context_store=context_store,
                        node=node,
                        method_ctx=method_ctx,
                        dialogue_context=dialogue_context,
                    )
                    future_to_node[future] = node.node_id

                if not future_to_node:
                    unresolved_nodes = sorted(pending)
                    raise RuntimeError(f"scheduler deadlock: unresolved nodes={unresolved_nodes}")

                done, _ = wait(list(future_to_node.keys()), timeout=0.2, return_when=FIRST_COMPLETED)
                if not done:
                    continue
                for future in done:
                    node_id = future_to_node.pop(future)
                    result = future.result()
                    context_store.append_result(result)
                    results[node_id] = result
                    completed.add(node_id)
                    elapsed_ms = int((time.perf_counter() - started_at.pop(node_id, time.perf_counter())) * 1000)
                    if isinstance(result, dict):
                        result.setdefault(
                            "scheduler_meta",
                            {
                                "node_id": node_id,
                                "elapsed_ms": elapsed_ms,
                                "max_parallel_agents": self.max_parallel_agents,
                            },
                        )
                    self._emit_scheduler_event(
                        manager=manager,
                        status="success",
                        summary=f"scheduler done: {node_id}",
                        payload={
                            "node_id": node_id,
                            "elapsed_ms": elapsed_ms,
                            "completed": len(completed),
                            "remaining": len(pending) + len(future_to_node),
                        },
                    )

        ordered = sorted(results.items(), key=lambda kv: index_by_node_id.get(kv[0], 0))
        return [item[1] for item in ordered]

    @staticmethod
    def _emit_scheduler_event(manager: Any, status: str, summary: str, payload: dict[str, Any]) -> None:
        push_event = getattr(manager, "push_event", None)
        if callable(push_event):
            try:
                push_event("runtime_scheduler", status, "AgentScheduler", summary, payload)
            except Exception:
                return

    def _execute_node(
        self,
        manager: Any,
        registry: Any,
        context_store: ExecutionContextStore,
        node: Any,
        method_ctx: str,
        dialogue_context: str,
    ) -> dict[str, Any]:
        payload = node.agent_payload
        agent_type = str(payload.get("agent_type") or "TextExecAgent")
        agent = registry.create(agent_type, manager)
        exec_input = AgentExecutionInput(
            agent_id=node.agent_id,
            agent_payload=payload,
            context_window=context_store.context_window(),
            method_ctx=method_ctx,
            dialogue_context=dialogue_context,
            max_turns=node.max_turns,
            summary_only=node.summary_only,
        )
        return agent.execute(exec_input)
