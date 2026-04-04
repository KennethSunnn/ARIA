import time

import pytest

from runtime.context_store import ExecutionContextStore
from runtime.execution_graph import build_execution_graph
from runtime.scheduler import AgentScheduler


class _DummyManager:
    def __init__(self) -> None:
        self.cancelled = False
        self.events: list[dict] = []

    def check_cancelled(self, stage: str) -> None:
        if self.cancelled:
            raise RuntimeError(f"cancelled at {stage}")

    def push_event(self, stage: str, status: str, agent_code: str, summary: str, payload: dict) -> None:
        self.events.append(
            {
                "stage": stage,
                "status": status,
                "agent_code": agent_code,
                "summary": summary,
                "payload": payload,
            }
        )

    def _build_exec_context_window(self, results: list[dict]) -> str:
        return "\n".join([str(r.get("sub_task_id") or "") for r in results if isinstance(r, dict)])


class _SleepAgent:
    def __init__(self, manager: _DummyManager):
        self.manager = manager

    def execute(self, request):
        sleep_s = float(request.agent_payload.get("task", {}).get("sleep_s", 0.0) or 0.0)
        time.sleep(sleep_s)
        task = request.agent_payload.get("task", {})
        return {
            "agent_id": request.agent_id,
            "sub_task_id": task.get("sub_task_id"),
            "step": task.get("step", ""),
            "result": "ok",
        }


class _Registry:
    def create(self, agent_type: str, manager: _DummyManager):
        return _SleepAgent(manager)


def test_scheduler_runs_independent_nodes_in_parallel() -> None:
    manager = _DummyManager()
    agents = {
        "a1": {"agent_type": "TextExecAgent", "task": {"sub_task_id": "n1", "step": "one", "sleep_s": 0.2}},
        "a2": {"agent_type": "TextExecAgent", "task": {"sub_task_id": "n2", "step": "two", "sleep_s": 0.2}},
    }
    graph = build_execution_graph(agents)
    scheduler = AgentScheduler(max_parallel_agents=2)
    start = time.perf_counter()
    results = scheduler.run(
        graph=graph,
        manager=manager,
        registry=_Registry(),
        context_store=ExecutionContextStore(manager),
        method_ctx="",
        dialogue_context="",
    )
    elapsed = time.perf_counter() - start
    assert len(results) == 2
    assert elapsed < 0.35


def test_scheduler_respects_dependencies() -> None:
    manager = _DummyManager()
    agents = {
        "a1": {"agent_type": "TextExecAgent", "task": {"sub_task_id": "n1", "step": "one", "sleep_s": 0.01}},
        "a2": {
            "agent_type": "TextExecAgent",
            "task": {"sub_task_id": "n2", "step": "two", "depends_on": ["n1"], "sleep_s": 0.01},
        },
    }
    graph = build_execution_graph(agents)
    scheduler = AgentScheduler(max_parallel_agents=2)
    results = scheduler.run(
        graph=graph,
        manager=manager,
        registry=_Registry(),
        context_store=ExecutionContextStore(manager),
        method_ctx="",
        dialogue_context="",
    )
    assert [r.get("sub_task_id") for r in results] == ["n1", "n2"]
    assert all(isinstance(r.get("scheduler_meta"), dict) for r in results)
    assert any(evt.get("stage") == "runtime_scheduler" for evt in manager.events)
    assert any((evt.get("payload") or {}).get("topology") == "pipeline" for evt in manager.events)


def test_scheduler_propagates_cancellation() -> None:
    manager = _DummyManager()
    manager.cancelled = True
    agents = {
        "a1": {"agent_type": "TextExecAgent", "task": {"sub_task_id": "n1", "step": "one", "sleep_s": 0.0}},
    }
    graph = build_execution_graph(agents)
    scheduler = AgentScheduler(max_parallel_agents=1)
    with pytest.raises(RuntimeError):
        scheduler.run(
            graph=graph,
            manager=manager,
            registry=_Registry(),
            context_store=ExecutionContextStore(manager),
            method_ctx="",
            dialogue_context="",
        )
