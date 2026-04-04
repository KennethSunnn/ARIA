"""ActionExecAgent — 能够直接调用 ARIA 工具链的执行 agent。

与纯文本的 LLMExecAgent 不同，ActionExecAgent 会：
1. 解析子任务描述，通过 LLM 生成具体的 action 调用序列
2. 调用 manager._execute_tool() / manager.plan_actions() 实际执行工具
3. 将执行结果结构化返回，供后续 agent 或 check_result 使用

仅用于 execution_surface=local_desktop 类型的子任务。
"""
from __future__ import annotations

import json
import time
from typing import Any

from .agents import AgentExecutionInput


class ActionExecAgent:
    """调用真实工具的执行 agent。"""

    def __init__(self, manager: Any) -> None:
        self._manager = manager
        # 延迟导入，避免循环依赖
        self._retry_policy = None

    @property
    def _policy(self):
        if self._retry_policy is None:
            try:
                from automation.execution_retry import ExecutionRetryPolicy
                self._retry_policy = ExecutionRetryPolicy()
            except ImportError:
                self._retry_policy = None
        return self._retry_policy

    def execute(self, request: AgentExecutionInput) -> dict[str, Any]:
        agent = request.agent_payload
        task = agent.get("task", {})
        step = str(task.get("step") or "")
        description = str(task.get("description") or step)
        agent_id = request.agent_id

        self._manager.check_cancelled("action_exec_agent")
        self._manager.stm.agent_status[agent_id] = "running"
        self._manager.push_event(
            "agent_execute",
            "running",
            "ActionExecAgent",
            f"执行工具调用：{description}",
            {"sub_task_id": task.get("sub_task_id")},
        )
        self._manager.push_log("ActionExecAgent", f"开始工具执行：{description}", "running")

        # 如果子任务已经预嵌了 action_plan（来自 split_sub_tasks 的 local_desktop 路径），直接用
        action_plan = task.get("action_plan")
        if not action_plan or not isinstance(action_plan, dict):
            # 否则让 LLM 把文字描述转成 action plan
            action_plan = self._generate_action_plan(description, request.context_window)

        actions = action_plan.get("actions") if isinstance(action_plan, dict) else []
        if not isinstance(actions, list):
            actions = []

        execution_results: list[dict[str, Any]] = []
        all_success = True
        combined_output: list[str] = []

        for action in actions:
            if not isinstance(action, dict):
                continue
            self._manager.check_cancelled("action_exec_agent_loop")
            action_type = str(action.get("type") or "")
            if not action_type:
                continue

            try:
                result = self._manager._execute_tool(action_type, action)
            except Exception as exc:
                result = {"success": False, "stderr": str(exc), "stdout": ""}

            # 失败时尝试重试策略
            if not result.get("success") and self._policy:
                result = self._try_fallback(action_type, action, result, combined_output)

            execution_results.append({"action": action_type, "result": result})
            if not result.get("success"):
                all_success = False
                err = str(result.get("stderr") or result.get("message") or "未知错误")
                combined_output.append(f"[{action_type}] 失败: {err}")
            else:
                out = str(result.get("stdout") or result.get("message") or "成功")
                combined_output.append(f"[{action_type}] {out}")

        status = "completed" if all_success else "partial_failure"
        result_text = "\n".join(combined_output) if combined_output else (
            "无可执行动作" if not actions else "执行完成"
        )

        self._manager.stm.agent_status[agent_id] = status
        self._manager.push_log("ActionExecAgent", f"工具执行完成（{status}）", status)
        self._manager.push_event(
            "agent_execute",
            "success" if all_success else "warning",
            "ActionExecAgent",
            f"工具执行{'完成' if all_success else '部分失败'}：{step}",
            {
                "sub_task_id": task.get("sub_task_id"),
                "actions_count": len(actions),
                "all_success": all_success,
            },
        )

        return {
            "agent_id": agent_id,
            "agent_type": "ActionExecAgent",
            "agent_name": "ActionExecAgent",
            "step": step,
            "description": description,
            "task_id": task.get("task_id", ""),
            "sub_task_id": task.get("sub_task_id", ""),
            "selected_personality": task.get("selected_personality", {}),
            "routing_scores": task.get("routing_scores", []),
            "routing_confidence": task.get("routing_confidence", 0.0),
            "routing_reason": task.get("routing_reason", "action_exec"),
            "result": result_text,
            "execution_results": execution_results,
            "all_success": all_success,
            "status": status,
            "timestamp": time.time(),
        }

    def _try_fallback(
        self,
        action_type: str,
        action: dict[str, Any],
        result: dict[str, Any],
        log: list[str],
    ) -> dict[str, Any]:
        """失败时尝试 fallback 策略，返回修正后的结果。"""
        policy = self._policy
        if policy is None:
            return result

        params = action.get("params") if isinstance(action.get("params"), dict) else {}

        # 桌面应用找不到 → 提示网页版
        if policy.should_retry_desktop_app(action_type, result):
            app_name = str(params.get("app") or action.get("target") or "")
            web_alt = policy.suggest_web_alternative(app_name)
            if web_alt:
                log.append(f"[fallback] {app_name} 未找到，建议使用网页版：{web_alt}")
                return {"success": False, "stderr": f"应用未找到，网页版替代：{web_alt}", "fallback_url": web_alt}

        # 文件操作路径错误 → 模糊匹配
        if policy.should_retry_file_operation(action_type, result):
            original_path = str(params.get("path") or params.get("src") or action.get("target") or "")
            if original_path:
                alts = policy.suggest_file_path_alternatives(original_path)
                if alts:
                    log.append(f"[fallback] 路径 {original_path} 未找到，候选：{', '.join(alts[:2])}")
                    # 尝试第一个候选路径
                    alt_action = dict(action)
                    alt_params = dict(params)
                    alt_params["path"] = alts[0]
                    alt_action["params"] = alt_params
                    try:
                        return self._manager._execute_tool(action_type, alt_action)
                    except Exception:
                        pass

        return result

    def _generate_action_plan(self, description: str, context_window: str) -> dict[str, Any]:
        """将文字描述转换为 action plan（仅当没有预嵌 action_plan 时调用）。"""
        user_input = str(getattr(self._manager.stm, "user_input", "")) or description
        # 获取可用的动作类型列表
        allowed = sorted(getattr(self._manager, "ALLOWED_ACTION_TYPES", set()))
        messages = [
            {
                "role": "system",
                "content": (
                    "你是 ARIA 工具调用规划器。将给定的任务描述转为具体的工具调用序列。"
                    "只输出严格 JSON：{\"actions\":[{\"type\":\"...\",\"target\":\"...\",\"params\":{},\"risk\":\"low\"}]}\n"
                    f"可用工具类型：{', '.join(allowed[:30])}\n"
                    "规则：优先选择最直接的工具；无合适工具时返回 {\"actions\":[]}。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"原始用户输入：{user_input}\n"
                    f"当前子任务：{description}\n"
                    + (f"此前步骤输出：{context_window[:400]}" if context_window else "")
                ),
            },
        ]
        txt = self._manager._call_llm(
            messages, fallback_text="{}", agent_code="ActionExecAgent", reasoning_effort="low"
        )
        data = self._manager._extract_json_object(txt)
        return data if isinstance(data, dict) else {}
