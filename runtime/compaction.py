"""
Context 自动压缩

Context 不是越大越好，而是越干净越好。
当累积 Token 超过模型上限的 50% 时，用 LLM 摘要替换原始历史，防止 Context Collapse。

配置项：
  ARIA_COMPACTION_ENABLED=1         在瀑布流模式下启用（TAOR 模式始终开启）
  ARIA_MODEL_CONTEXT_LIMIT=32000    模型 Context 上限（token 数）
  ARIA_COMPACTION_THRESHOLD=0.5     触发压缩的比例阈值（0.1~0.9）
"""
from __future__ import annotations

import os
import threading
from typing import Any


class ContextCompactor:
    """
    监控累积 Token 使用量，在超过阈值时将对话历史替换为 LLM 生成的摘要。

    用法
    ----
    在每次 _call_llm() 前后读取 get_token_usage_summary()["total_tokens"] 差值，
    调用 record_usage(delta) 累积；然后在构建 context_window 时调用 maybe_compact()。

    线程安全：内部使用 threading.Lock。
    """

    def __init__(self, manager: Any) -> None:
        self._manager = manager
        self._lock = threading.Lock()
        self._cumulative_tokens: int = 0
        self._compaction_count: int = 0

    # ------------------------------------------------------------------ #
    # 公开 API                                                              #
    # ------------------------------------------------------------------ #

    def record_usage(self, delta_tokens: int) -> None:
        """记录一次 LLM 调用的 token 增量。"""
        with self._lock:
            self._cumulative_tokens += max(0, int(delta_tokens or 0))

    def maybe_compact(
        self,
        context_text: str,
        task_goal: str = "",
    ) -> str:
        """
        如果累积 token 未超过阈值，直接返回 context_text；
        超过阈值时调用 LLM 生成摘要，替换原始历史并重置计数。
        """
        if not (context_text or "").strip():
            return context_text

        limit = self._context_limit()
        threshold = int(limit * self._threshold())

        with self._lock:
            current_usage = self._cumulative_tokens

        if current_usage < threshold:
            return context_text

        summary = self._compact(context_text, task_goal)
        with self._lock:
            self._compaction_count += 1
            count = self._compaction_count
            self._cumulative_tokens = self._estimate_tokens(summary)

        push = getattr(self._manager, "push_event", None)
        if callable(push):
            try:
                push(
                    "context_compact",
                    "success",
                    "ContextCompactor",
                    f"上下文压缩完成（第 {count} 次），原始 {current_usage} tokens",
                    {
                        "original_tokens": current_usage,
                        "compaction_count": count,
                        "limit": limit,
                        "threshold": threshold,
                    },
                )
            except Exception:
                pass

        return summary

    def cumulative_tokens(self) -> int:
        with self._lock:
            return self._cumulative_tokens

    def compaction_count(self) -> int:
        with self._lock:
            return self._compaction_count

    # ------------------------------------------------------------------ #
    # 私有辅助                                                               #
    # ------------------------------------------------------------------ #

    def _context_limit(self) -> int:
        try:
            return max(8000, int(os.getenv("ARIA_MODEL_CONTEXT_LIMIT", "32000") or "32000"))
        except (TypeError, ValueError):
            return 32000

    def _threshold(self) -> float:
        try:
            raw = float(os.getenv("ARIA_COMPACTION_THRESHOLD", "0.5") or "0.5")
            return max(0.1, min(0.9, raw))
        except (TypeError, ValueError):
            return 0.5

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """
        粗略 token 估算：中文字符约 1.5 chars/token，英文约 4 chars/token。
        仅用于压缩后重置计数，不参与阈值判断。
        """
        if not text:
            return 0
        cn = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
        other = len(text) - cn
        return int(cn / 1.5 + other / 4) + 1

    def _compact(self, context_text: str, task_goal: str) -> str:
        goal_line = f"【任务目标】\n{task_goal.strip()}\n\n" if task_goal.strip() else ""
        messages = [
            {
                "role": "system",
                "content": (
                    "你是 ARIA 的上下文压缩器。请将以下执行历史压缩为精简摘要。\n"
                    "必须保留：任务目标、每个工具调用的类型和成功/失败状态、关键决策和结论。\n"
                    "可删除：详细推理链、冗余重复、超长工具输出（只保留结论）。\n"
                    "输出：纯文本，不要 JSON，不超过 600 字。以「【压缩上下文】」开头。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"{goal_line}"
                    "【原始执行历史（需压缩）】\n"
                    f"{context_text[:8000]}"
                ),
            },
        ]
        call_llm = getattr(self._manager, "_call_llm", None)
        if not callable(call_llm):
            return context_text[:600]

        summary = call_llm(
            messages,
            fallback_text=f"【压缩上下文】（压缩失败）\n{context_text[:400]}",
            agent_code="ContextCompactor",
            reasoning_effort="low",
        )
        return summary or context_text[:600]
