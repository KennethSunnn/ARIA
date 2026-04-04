from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ExecutionNode:
    node_id: str
    agent_id: str
    agent_payload: dict[str, Any]
    depends_on: list[str] = field(default_factory=list)
    max_turns: int = 1          # Sub-Agent 最大执行轮数
    summary_only: bool = False  # 向主 Agent 只返回摘要


@dataclass(slots=True)
class ExecutionGraph:
    nodes: list[ExecutionNode]

    def node_ids(self) -> list[str]:
        return [node.node_id for node in self.nodes]

    def unresolved_dependencies(self) -> dict[str, list[str]]:
        known = set(self.node_ids())
        missing: dict[str, list[str]] = {}
        for node in self.nodes:
            unknown = [dep for dep in node.depends_on if dep not in known]
            if unknown:
                missing[node.node_id] = unknown
        return missing


def build_execution_graph(agents: dict[str, dict[str, Any]]) -> ExecutionGraph:
    nodes: list[ExecutionNode] = []
    for agent_id, payload in agents.items():
        task = payload.get("task") if isinstance(payload, dict) else {}
        depends_on_raw = task.get("depends_on", []) if isinstance(task, dict) else []
        depends_on = [str(dep) for dep in (depends_on_raw or []) if str(dep).strip()]
        node_id = str(task.get("sub_task_id") or agent_id)
        try:
            max_turns = int(payload.get("max_turns") or (task or {}).get("max_turns") or 1)
            max_turns = max(1, min(60, max_turns))
        except (TypeError, ValueError):
            max_turns = 1
        summary_only = bool(payload.get("summary_only") or (task or {}).get("summary_only", False))
        nodes.append(
            ExecutionNode(
                node_id=node_id,
                agent_id=str(agent_id),
                agent_payload=payload,
                depends_on=depends_on,
                max_turns=max_turns,
                summary_only=summary_only,
            )
        )
    return ExecutionGraph(nodes=nodes)
