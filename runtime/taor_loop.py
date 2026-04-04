"""
TAOR 自主执行循环 (Think-Act-Observe-Repeat)

核心思想：Orchestrator 只负责驱动循环、执行工具、传递结果；
让模型决定下一步，约 50 行核心循环逻辑，给模型无限操作空间。

对比现有 7 步瀑布流：
  瀑布流  = 框架决定 agent 类型、任务拆分、方法论应用
  TAOR   = 模型看到工具清单后自主决定每一步

模型输出格式（JSON-in-response，复用 react_infer_next_step 约定）：
  {
    "thought": "本轮推理",
    "finish": false,
    "final_result": "",        // finish=true 时填写
    "is_success": true,        // finish=true 时填写
    "action": {                // 需要调用工具时填写（字段名复用 react_infer_next_step）
      "type": "browser_open",
      "target": "...",
      "params": {},
      "risk": "low",
      "reason": "..."
    }
  }

配置项：
  ARIA_TAOR_MODE=1          在 web_app.py 调用入口启用
  ARIA_TAOR_MAX_TURNS=20    最大循环轮数（默认 20，上限 60）
"""
from __future__ import annotations

import json
import os
import time
from typing import Any

from .compaction import ContextCompactor


class TAORLoop:
    """
    Think-Act-Observe-Repeat 自主执行循环。

    当 ARIA_TAOR_MODE=1 时，由 aria_manager.run_taor_pipeline() 调用，
    替代现有 7 步瀑布流。瀑布流原始代码保持不变，通过特性标志切换。
    """

    def __init__(self, manager: Any) -> None:
        self._manager = manager

    # ------------------------------------------------------------------ #
    # 公开入口                                                               #
    # ------------------------------------------------------------------ #

    def run(
        self,
        user_input: str,
        dialogue_context: str = "",
        method: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        执行 TAOR 循环直到任务完成或达到最大轮数。

        返回与瀑布流结果兼容的字典：
          {
            "final_result": str,
            "is_success": bool,
            "tool_trace": list[dict],   # 每轮的 thought/action/observation
          }
        """
        max_turns = self._max_turns()
        compactor = ContextCompactor(self._manager)
        messages = self._build_initial_messages(user_input, dialogue_context, method)
        tool_trace: list[dict[str, Any]] = []

        for turn in range(1, max_turns + 1):
            self._manager.check_cancelled("taor_turn_start")
            self._manager.push_event(
                "taor_loop",
                "running",
                "TAORLoop",
                f"TAOR 第 {turn} 轮推理",
                {"turn": turn, "max_turns": max_turns},
            )

            # ---- Think ----
            token_before = self._manager.get_token_usage_summary().get("total_tokens", 0)
            llm_text = self._manager._call_llm(
                messages,
                fallback_text="",
                agent_code="TAORLoop",
            )
            token_after = self._manager.get_token_usage_summary().get("total_tokens", 0)
            compactor.record_usage(token_after - token_before)

            step = self._parse_model_response(llm_text)
            messages.append({"role": "assistant", "content": llm_text or ""})

            if step["finish"]:
                final_result = step["final_result"] or step["thought"] or ""
                is_success = step["is_success"]
                self._manager.push_event(
                    "taor_loop",
                    "success",
                    "TAORLoop",
                    f"TAOR 完成（{turn} 轮）",
                    {"turn": turn, "is_success": is_success},
                )
                return {
                    "final_result": final_result,
                    "is_success": is_success,
                    "tool_trace": tool_trace,
                }

            raw_action = step["action"]
            if not isinstance(raw_action, dict) or not raw_action.get("type"):
                # 模型给出文字回复但未指定动作且未 finish → 隐式完成
                return {
                    "final_result": step["thought"] or llm_text or "",
                    "is_success": True,
                    "tool_trace": tool_trace,
                }

            # ---- Act ----
            action_type = str(raw_action.get("type") or "")
            self._manager.push_event(
                "taor_loop",
                "running",
                "TAORLoop",
                f"TAOR Act: {action_type}（第 {turn} 轮）",
                {"action_type": action_type, "turn": turn},
            )

            # ---- Observe ----
            observation = self._dispatch_action(raw_action)
            tool_trace.append(
                {
                    "turn": turn,
                    "thought": step["thought"],
                    "action": raw_action,
                    "observation": observation,
                }
            )

            obs_text = json.dumps(observation, ensure_ascii=False, default=str)
            messages.append({"role": "user", "content": f"TOOL_RESULT:\n{obs_text}"})

            # 对 context_window 文本做压缩（用已完成的 tool_trace 作为历史）
            if len(tool_trace) >= 3:
                history_text = self._format_trace_for_compact(tool_trace[:-1])
                compacted = compactor.maybe_compact(history_text, task_goal=user_input)
                if compacted != history_text:
                    # 重建 messages：保留 system + 首轮 user，替换中间历史
                    messages = self._rebuild_messages_with_compact(
                        messages, compacted, user_input
                    )

        # 达到最大轮数
        self._manager.push_event(
            "taor_loop",
            "warning",
            "TAORLoop",
            f"TAOR 已达最大轮数 {max_turns}，强制结束",
            {"max_turns": max_turns},
        )
        return {
            "final_result": f"任务已执行 {max_turns} 轮，请查看工具执行记录获取中间结果。",
            "is_success": False,
            "tool_trace": tool_trace,
        }

    # ------------------------------------------------------------------ #
    # 私有：消息构建                                                          #
    # ------------------------------------------------------------------ #

    def _build_initial_messages(
        self,
        user_input: str,
        dialogue_context: str,
        method: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        method_ctx = self._manager._methodology_summary_text(method) if method else ""
        allowed_types = ", ".join(sorted(self._manager.ALLOWED_ACTION_TYPES))
        capability_fragment = self._manager._react_capability_prompt_fragment()
        current_time_str = time.strftime("%Y年%m月%d日 %H:%M，%A")
        memory_fragment = self._manager._memory_system_prompt_fragment()

        sys_content = (
            f"【当前时间】{current_time_str}\n\n"
            "你是 ARIA 的 TAOR 自主执行引擎。每轮先推理（Think），再决定是否调用一个工具（Act），"
            "观察结果（Observe）后进入下一轮（Repeat），直到任务完成。\n\n"
            "输出格式：严格 JSON 对象，禁止 markdown 围栏，禁止前后缀文字。字段：\n"
            '  "thought"      : 本步推理\n'
            '  "finish"       : bool，任务完成时为 true\n'
            '  "final_result" : 当 finish=true 时给用户的最终回复\n'
            '  "is_success"   : 当 finish=true 时填写，bool\n'
            '  "action"       : 需要调用工具时填写，字段：type, target, params, risk, reason\n\n'
            "规则：\n"
            "- 若上一步工具调用失败，在 thought 中分析原因并调整策略。\n"
            "- 不要编造未执行的结果；不要声称已保存文件但未执行 file_write。\n"
            "- 每轮只输出一个 action。\n\n"
            f"可用工具类型：{allowed_types}\n\n"
            f"{capability_fragment}\n\n"
            + (f"{method_ctx}\n\n" if method_ctx else "")
            + memory_fragment
        )

        user_parts: list[str] = []
        if (dialogue_context or "").strip():
            user_parts.append(f"【本会话近期对话】\n{dialogue_context.strip()}")
        user_parts.append(f"【当前任务】\n{user_input}")

        return [
            {"role": "system", "content": sys_content},
            {"role": "user", "content": "\n\n".join(user_parts)},
        ]

    def _rebuild_messages_with_compact(
        self,
        messages: list[dict[str, Any]],
        compact_text: str,
        user_input: str,
    ) -> list[dict[str, Any]]:
        """
        压缩触发后，重建 messages 列表：
        保留 system 提示和任务说明，中间历史替换为压缩摘要。
        """
        if not messages:
            return messages
        system_msg = messages[0]
        # 第一条 user 消息（任务目标）
        first_user = next((m for m in messages[1:] if m.get("role") == "user"), None)
        rebuilt = [system_msg]
        if first_user:
            rebuilt.append(first_user)
        rebuilt.append(
            {"role": "user", "content": f"【执行历史摘要（已压缩）】\n{compact_text}"}
        )
        # 最后两条消息（最新 assistant + tool_result）保留
        if len(messages) >= 2:
            rebuilt.extend(messages[-2:])
        return rebuilt

    # ------------------------------------------------------------------ #
    # 私有：模型输出解析                                                       #
    # ------------------------------------------------------------------ #

    def _parse_model_response(self, llm_text: str) -> dict[str, Any]:
        data = self._manager._extract_json_object(llm_text or "")
        if not isinstance(data, dict):
            # 非 JSON 回复 → 隐式完成
            return {
                "thought": llm_text or "",
                "finish": True,
                "final_result": llm_text or "",
                "is_success": True,
                "action": None,
            }
        finish_raw = data.get("finish")
        finish = finish_raw is True or str(finish_raw).lower() in ("1", "true", "yes")
        return {
            "thought": str(data.get("thought") or "").strip(),
            "finish": finish,
            "final_result": str(data.get("final_result") or "").strip(),
            "is_success": bool(data.get("is_success", True)),
            "action": data.get("action") or data.get("tool_call"),  # 兼容两种字段名
        }

    # ------------------------------------------------------------------ #
    # 私有：工具分发                                                          #
    # ------------------------------------------------------------------ #

    def _dispatch_action(self, action: dict[str, Any]) -> dict[str, Any]:
        """
        通过现有的 app_registry → action_registry 链路分发单个工具调用。
        优先级与 execute_actions() 一致。
        """
        raw_type = str(action.get("type") or "")
        action_type = self._manager._normalize_action_type_alias(raw_type)

        if not action_type or action_type not in self._manager.ALLOWED_ACTION_TYPES:
            return {
                "success": False,
                "error_code": "unsupported_action",
                "error": f"不支持的工具类型：{raw_type!r}",
            }

        # 权限检查（复用 permission_model）
        permission_model = getattr(self._manager, "permission_model", None)
        if permission_model is not None:
            risk = str(action.get("risk") or "low")
            if permission_model.is_readonly_only() and action_type not in self._manager.SAFE_ACTION_TYPES:
                return {
                    "success": False,
                    "error_code": "permission_denied",
                    "error": f"当前权限级别（plan）不允许执行 {action_type}",
                }

        # 优先通过 app_registry 处理
        app_registry = getattr(self._manager, "app_registry", None)
        if app_registry is not None:
            cap_result = app_registry.get_capability(action_type)
            if cap_result:
                app, _ = cap_result
                try:
                    execute_fn = getattr(app, "execute", None)
                    if callable(execute_fn):
                        result = execute_fn(
                            action_type,
                            action,
                            cancel_checker=getattr(self._manager, "check_cancelled", None),
                        )
                        return result if isinstance(result, dict) else {"success": True, "output": str(result)}
                except Exception as exc:
                    return {"success": False, "error": str(exc)}

        # 回退到 action_registry
        handler = self._manager.action_registry.get(action_type)
        if not handler:
            return {"success": False, "error_code": "unsupported_action", "error": action_type}

        action_ctx = dict(action)
        action_ctx["_request_id"] = getattr(self._manager, "current_request_id", "")
        try:
            result = handler(
                action_ctx,
                getattr(self._manager, "current_conversation_id", ""),
                None,  # methodology_manager
                None,  # conversation_manager
            )
            return result if isinstance(result, dict) else {"success": True, "output": str(result)}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    # ------------------------------------------------------------------ #
    # 私有：辅助                                                             #
    # ------------------------------------------------------------------ #

    def _max_turns(self) -> int:
        try:
            return max(1, min(60, int(os.getenv("ARIA_TAOR_MAX_TURNS", "20") or "20")))
        except (TypeError, ValueError):
            return 20

    @staticmethod
    def _format_trace_for_compact(tool_trace: list[dict[str, Any]]) -> str:
        """将 tool_trace 转为适合压缩器处理的文本。"""
        if not tool_trace:
            return ""
        lines: list[str] = []
        for row in tool_trace:
            turn = row.get("turn", "?")
            thought = str(row.get("thought") or "").strip()[:200]
            act = row.get("action") or {}
            obs = row.get("observation") or {}
            success = obs.get("success", "?")
            atype = act.get("type", "?")
            lines.append(
                f"[Turn {turn}] thought: {thought}\n"
                f"  action: {atype}  success: {success}"
            )
        return "\n".join(lines)
