from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .compaction import ContextCompactor


class ExecutionContextStore:
    def __init__(self, manager: Any, compactor: "ContextCompactor | None" = None):
        self._manager = manager
        self._compactor = compactor  # 可选的上下文压缩器，传入时自动触发压缩
        self._lock = threading.Lock()
        self._results: list[dict[str, Any]] = []
        self._metadata: dict[str, Any] = {}

    def append_result(self, result: dict[str, Any]) -> None:
        with self._lock:
            self._results.append(dict(result))

    def snapshot_results(self) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(r) for r in self._results]

    def context_window(self) -> str:
        raw = self._manager._build_exec_context_window(self.snapshot_results())
        if self._compactor is not None:
            task_goal = str(getattr(self._manager.stm, "user_input", "") or "")
            return self._compactor.maybe_compact(raw, task_goal)
        return raw

    def set_metadata(self, key: str, value: Any) -> None:
        with self._lock:
            self._metadata[str(key)] = value

    def metadata_snapshot(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._metadata)
