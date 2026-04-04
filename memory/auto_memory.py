"""
Auto-Memory System — 跨 Session 用户模式学习

每次成功任务结束后，从对话中提取值得长期记住的用户偏好与行为模式，
写入 memory/entries/{slug}.md（带 frontmatter），并重建 memory/MEMORY.md 索引。

下次 Session 启动时，aria_manager 从 MEMORY.md 加载并注入系统提示。
"""
from __future__ import annotations

import json
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any, Literal

MemoryType = Literal["user_preference", "task_pattern", "feedback"]

_MEMORY_DIR = Path("memory")
_ENTRIES_DIR = _MEMORY_DIR / "entries"
_MEMORY_INDEX_PATH = _MEMORY_DIR / "MEMORY.md"
_MAX_INDEX_LINES = 200
_ENABLED_ENV = "ARIA_AUTO_MEMORY_ENABLED"


class MemoryEntry:
    """一条记忆条目，对应 memory/entries/{slug}.md。"""

    def __init__(
        self,
        name: str,
        type_: MemoryType,
        description: str,
        body: str,
        task_id: str = "",
        created_at: str = "",
        updated_at: str = "",
    ) -> None:
        self.name = name
        self.type_ = type_
        self.description = description
        self.body = body
        self.task_id = task_id
        self.created_at = created_at or time.strftime("%Y-%m-%d %H:%M:%S")
        self.updated_at = updated_at or self.created_at

    def to_markdown(self) -> str:
        fm = (
            f"---\n"
            f'name: "{self.name}"\n'
            f"type: {self.type_}\n"
            f'description: "{self.description}"\n'
            f'created_at: "{self.created_at}"\n'
            f'updated_at: "{self.updated_at}"\n'
            f'task_id: "{self.task_id}"\n'
            f"---\n\n"
        )
        return fm + self.body.strip()

    @classmethod
    def from_file(cls, path: Path) -> "MemoryEntry | None":
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            return None
        m = re.match(r"^---\n(.*?)\n---\n?(.*)", text, re.DOTALL)
        if not m:
            return None
        fm_text, body = m.group(1), m.group(2)
        fm: dict[str, str] = {}
        for line in fm_text.splitlines():
            kv = line.split(":", 1)
            if len(kv) == 2:
                fm[kv[0].strip()] = kv[1].strip().strip('"')
        return cls(
            name=fm.get("name", path.stem),
            type_=fm.get("type", "user_preference"),  # type: ignore[arg-type]
            description=fm.get("description", ""),
            body=body.strip(),
            task_id=fm.get("task_id", ""),
            created_at=fm.get("created_at", ""),
            updated_at=fm.get("updated_at", ""),
        )


class AutoMemoryManager:
    """
    负责提取、持久化和加载跨 Session 用户记忆。

    设计原则：记忆是索引，不是存储。
    只记录无法从代码推导的信息：用户偏好、工作流规律、明确的纠正反馈。
    """

    def __init__(self, manager: Any) -> None:
        self._manager = manager
        _ENTRIES_DIR.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ #
    # Session 启动：加载 MEMORY.md                                         #
    # ------------------------------------------------------------------ #

    def load_into_stm(self) -> str:
        """
        读取 memory/MEMORY.md，返回内容字符串，供注入系统提示。
        文件不存在时返回空字符串。
        """
        if not _MEMORY_INDEX_PATH.exists():
            return ""
        try:
            return _MEMORY_INDEX_PATH.read_text(encoding="utf-8").strip()
        except OSError:
            return ""

    # ------------------------------------------------------------------ #
    # 任务结束：提取并持久化模式                                             #
    # ------------------------------------------------------------------ #

    def analyze_and_persist(
        self,
        task_info: dict[str, Any],
        result_payload: dict[str, Any],
        tool_trace: list[dict[str, Any]] | None = None,
    ) -> list[str]:
        """
        成功任务结束后，让 LLM 提取值得记住的用户模式，并持久化。

        参数
        ----
        task_info      : 包含 user_input、task_id 等字段的任务信息字典
        result_payload : 包含 is_success、final_result 等字段的结果字典
        tool_trace     : TAOR 模式的工具调用链（可为 None）

        返回
        ----
        已创建或更新的条目 slug 列表
        """
        if not self._is_enabled():
            return []
        if not isinstance(result_payload, dict) or not result_payload.get("is_success"):
            return []

        user_input = str(task_info.get("user_input") or "")
        final_result = str(result_payload.get("final_result") or "")
        task_id = str(task_info.get("task_id") or "")

        trace_text = self._format_tool_trace(tool_trace or [])
        conversation_snapshot = (
            f"用户输入：{user_input}\n\n"
            f"最终结果摘要：{final_result[:600]}\n\n"
            + (f"工具调用记录：\n{trace_text}\n\n" if trace_text else "")
        )

        extracted = self._extract_patterns(conversation_snapshot, task_id)
        if not extracted:
            return []

        saved_names: list[str] = []
        for pattern in extracted:
            name = self._persist_entry(pattern, task_id)
            if name:
                saved_names.append(name)

        if saved_names:
            self._rebuild_index()
            self._manager.push_event(
                "auto_memory",
                "success",
                "AutoMemoryManager",
                f"已记录 {len(saved_names)} 条用户模式",
                {"entry_names": saved_names},
            )

        return saved_names

    # ------------------------------------------------------------------ #
    # 私有：LLM 提取                                                        #
    # ------------------------------------------------------------------ #

    def _extract_patterns(
        self,
        conversation_snapshot: str,
        task_id: str,
    ) -> list[dict[str, Any]]:
        existing_names = self._existing_entry_names()
        existing_hint = (
            f"\n已记录的模式（避免重复）：{', '.join(existing_names[:30])}\n"
            if existing_names
            else ""
        )
        messages = [
            {
                "role": "system",
                "content": (
                    "你是 ARIA 的学习分析器。分析以下任务对话，提取值得长期记住的用户偏好或行为模式。\n"
                    "只提取无法从代码推导的信息：用户偏好、工作流规律、明确的纠正反馈。\n"
                    "忽略：任务内容本身（不要记任务结论）、单次随机需求、可从代码推导的行为。\n"
                    + existing_hint
                    + "\n输出严格 JSON 数组（可为空 []），每个元素字段：\n"
                    '  "name": 唯一英文 slug（如 "output-format-markdown"）\n'
                    '  "type": "user_preference" | "task_pattern" | "feedback"\n'
                    '  "description": 一句话中文描述（≤30字）\n'
                    '  "body": 完整中文记录（≤150字）\n'
                    "最多提取 3 条，若无值得记录的内容输出 []。"
                ),
            },
            {
                "role": "user",
                "content": conversation_snapshot[:3000],
            },
        ]
        raw = self._manager._call_llm(
            messages,
            fallback_text="[]",
            agent_code="AutoMemoryManager",
            reasoning_effort="low",
        )
        cleaned = re.sub(r"^```(?:json)?\s*", "", (raw or "").strip(), flags=re.IGNORECASE)
        cleaned = re.sub(r"```$", "", cleaned).strip()
        m = re.search(r"\[[\s\S]*\]", cleaned)
        if not m:
            return []
        try:
            data = json.loads(m.group(0))
            if isinstance(data, list):
                return [d for d in data if isinstance(d, dict)]
        except (json.JSONDecodeError, ValueError):
            pass
        return []

    # ------------------------------------------------------------------ #
    # 私有：持久化                                                           #
    # ------------------------------------------------------------------ #

    def _persist_entry(self, pattern: dict[str, Any], task_id: str) -> str:
        raw_name = str(pattern.get("name") or "").strip()
        if not raw_name:
            raw_name = str(uuid.uuid4())[:8]
        slug = re.sub(r"[^a-zA-Z0-9\-_]", "-", raw_name)[:64].strip("-")
        if not slug:
            slug = str(uuid.uuid4())[:8]

        entry_path = _ENTRIES_DIR / f"{slug}.md"
        now = time.strftime("%Y-%m-%d %H:%M:%S")

        if entry_path.exists():
            existing = MemoryEntry.from_file(entry_path)
            if existing:
                existing.updated_at = now
                existing.body = str(pattern.get("body") or existing.body)
                existing.description = str(pattern.get("description") or existing.description)[:80]
                try:
                    entry_path.write_text(existing.to_markdown(), encoding="utf-8")
                except OSError:
                    pass
                return slug

        entry = MemoryEntry(
            name=slug,
            type_=pattern.get("type", "user_preference"),  # type: ignore[arg-type]
            description=str(pattern.get("description") or "")[:80],
            body=str(pattern.get("body") or ""),
            task_id=task_id,
            created_at=now,
            updated_at=now,
        )
        try:
            entry_path.write_text(entry.to_markdown(), encoding="utf-8")
        except OSError:
            return ""
        return slug

    def _rebuild_index(self) -> None:
        entries: list[MemoryEntry] = []
        for path in sorted(_ENTRIES_DIR.glob("*.md")):
            e = MemoryEntry.from_file(path)
            if e:
                entries.append(e)

        lines: list[str] = [
            "# ARIA Memory Index",
            f"Last updated: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
        ]
        by_type: dict[str, list[MemoryEntry]] = {}
        for e in entries:
            by_type.setdefault(e.type_, []).append(e)

        for type_name in ("user_preference", "task_pattern", "feedback"):
            group = by_type.get(type_name, [])
            if not group:
                continue
            lines.append(f"## {type_name}")
            for e in group:
                rel_path = f"entries/{e.name}.md"
                lines.append(f"- [{e.name}]({rel_path}): {e.description}")
            lines.append("")

        if len(lines) > _MAX_INDEX_LINES:
            lines = lines[:_MAX_INDEX_LINES]
            lines.append("... (truncated)")

        try:
            _MEMORY_INDEX_PATH.write_text("\n".join(lines), encoding="utf-8")
        except OSError:
            pass

    def _existing_entry_names(self) -> list[str]:
        if not _ENTRIES_DIR.exists():
            return []
        return [p.stem for p in sorted(_ENTRIES_DIR.glob("*.md"))]

    @staticmethod
    def _format_tool_trace(tool_trace: list[dict[str, Any]]) -> str:
        if not tool_trace:
            return ""
        lines: list[str] = []
        for row in tool_trace[:10]:
            act = row.get("action") or {}
            obs = row.get("observation") or {}
            success = obs.get("success", "?")
            lines.append(f"- [{act.get('type', '?')}] success={success}")
        return "\n".join(lines)

    @staticmethod
    def _is_enabled() -> bool:
        return os.getenv(_ENABLED_ENV, "0").strip().lower() in ("1", "true", "yes")
