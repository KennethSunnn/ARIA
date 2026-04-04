from __future__ import annotations

from threading import Lock
from typing import Any

from mcp.server.fastmcp import FastMCP

from memory.memory_system import LongTermMemory


class MemoryOps:
    """Small adapter exposing remember/recall/search/rollback semantics."""

    def __init__(self) -> None:
        self._ltm = LongTermMemory()
        self._ltm.load()
        self._lock = Lock()

    def remember(
        self,
        project: str,
        agent: str,
        topic: str,
        content: str,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        clean_tags = [str(t).strip() for t in (tags or []) if str(t).strip()]
        keywords = list(dict.fromkeys([project, agent, topic, *clean_tags]))
        payload = {
            "scene": f"{project}:{topic}",
            "title": f"{agent}::{topic}",
            "keywords": keywords,
            "solve_steps": [content],
            "applicable_range": project,
            "category": "mcp-memory",
            "quality_metrics": {"source": "mcp"},
        }
        with self._lock:
            self._ltm.load()
            existing = None
            for raw in self._ltm.methodologies:
                if not isinstance(raw, dict):
                    continue
                scene = str(raw.get("scene") or raw.get("scenario") or "")
                keywords = raw.get("keywords") or raw.get("core_keywords") or []
                if scene == f"{project}:{topic}" and agent in keywords:
                    existing = raw
                    break
            if existing:
                self._ltm.update_methodology(existing, payload)
            else:
                self._ltm.add_methodology(payload)
            self._ltm.load()
            candidates = [
                m
                for m in self._ltm.get_all_methodologies()
                if str(m.get("scene", "")) == f"{project}:{topic}" and agent in (m.get("keywords") or [])
            ]
            candidates.sort(key=lambda x: int(x.get("version", 1) or 1), reverse=True)
            saved = candidates[0] if candidates else {}
        return {
            "ok": True,
            "method_id": saved.get("method_id"),
            "version": saved.get("version", 1),
            "keywords": saved.get("keywords", []),
            "scene": saved.get("scene", ""),
        }

    def search(self, query: str, limit: int = 5) -> dict[str, Any]:
        with self._lock:
            rows = self._ltm.search_methodology(query)
        top = []
        for score, row in rows[: max(1, int(limit or 5))]:
            top.append(
                {
                    "method_id": row.get("method_id"),
                    "title": row.get("title") or row.get("scene"),
                    "scene": row.get("scene"),
                    "keywords": row.get("keywords", []),
                    "content": (row.get("solve_steps") or [""])[0],
                    "score": round(float(score), 4),
                    "version": row.get("version", 1),
                }
            )
        return {"ok": True, "count": len(top), "results": top}

    def recall(self, query: str, tags: list[str] | None = None, limit: int = 5) -> dict[str, Any]:
        tag_text = " ".join([str(t).strip() for t in (tags or []) if str(t).strip()])
        merged = f"{query} {tag_text}".strip()
        return self.search(merged, limit=limit)

    def rollback(self, method_id: str, to_version: int) -> dict[str, Any]:
        with self._lock:
            restored = self._ltm.rollback_methodology(method_id, int(to_version))
        if not restored:
            return {"ok": False, "error": "rollback_target_not_found"}
        return {
            "ok": True,
            "method_id": restored.get("method_id"),
            "version": restored.get("version", 1),
            "rollback_to": restored.get("rollback_to"),
        }


ops = MemoryOps()
mcp = FastMCP("aria-memory")


@mcp.tool()
def remember(project: str, agent: str, topic: str, content: str, tags: list[str] | None = None) -> dict[str, Any]:
    """Persist a decision/deliverable checkpoint into ARIA long-term memory."""
    return ops.remember(project=project, agent=agent, topic=topic, content=content, tags=tags)


@mcp.tool()
def search(query: str, limit: int = 5) -> dict[str, Any]:
    """Find memory records by semantic query."""
    return ops.search(query=query, limit=limit)


@mcp.tool()
def recall(query: str, tags: list[str] | None = None, limit: int = 5) -> dict[str, Any]:
    """Recall memory by query plus optional tags."""
    return ops.recall(query=query, tags=tags, limit=limit)


@mcp.tool()
def rollback(method_id: str, to_version: int) -> dict[str, Any]:
    """Rollback one memory record to a historical version."""
    return ops.rollback(method_id=method_id, to_version=to_version)


if __name__ == "__main__":
    mcp.run(transport="stdio")

