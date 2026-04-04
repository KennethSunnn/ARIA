from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class AgentExecutionInput:
    agent_id: str
    agent_payload: dict[str, Any]
    context_window: str
    method_ctx: str
    dialogue_context: str
    max_turns: int = 1          # Sub-Agent 最大执行轮数（默认 1，即单轮推理）
    summary_only: bool = False  # True 时只向主 Agent 返回 result 字段，丢弃中间推理


class LLMExecAgent:
    def __init__(self, manager: Any):
        self._manager = manager

    def execute(self, request: AgentExecutionInput) -> dict[str, Any]:
        agent = request.agent_payload
        task = agent.get("task", {})
        agent_type = str(agent.get("agent_type") or "TextExecAgent")
        agent_name = str(agent.get("agent_name") or self._manager._agent_profile(agent_type)["name"])
        role = self._manager._agent_profile(agent_type)["role"]
        persona = str(agent.get("persona_brief") or "").strip() or self._manager._default_persona_brief(
            agent_type,
            str(task.get("step") or ""),
            str(task.get("description") or ""),
        )

        self._manager.check_cancelled("agent_execute_loop")
        self._manager.stm.agent_status[request.agent_id] = "running"
        self._manager.push_event(
            "agent_execute",
            "running",
            agent_type,
            f"{role} 正在执行：{task.get('description', '')}",
            {"sub_task_id": task.get("sub_task_id")},
            agent_name_override=agent_name,
        )
        self._manager.push_log(agent_type, f"正在执行子任务：{task.get('description', '')}", "running")
        self._manager.record_model_thought(agent_type, f"开始执行任务：{task.get('description', '')}")
        self._manager.record_model_thought(agent_type, f"统一模型：{self._manager.unified_model}")

        sys_parts = [
            f"你是ARIA执行专家[{agent_type}]。你将基于给定步骤产出可直接使用的结果。只输出纯文本，不要JSON。",
            self._manager._math_notation_hint(),
        ]
        if str(getattr(self._manager.stm, "temporal_risk", "low")).lower() == "high":
            sys_parts.append(
                "【时效】本任务结论依赖当下数据：须说明信息时间点或获取渠道，禁止把方法论纲要中的示例数值当作当前事实；"
                "无法取得实时数据时要明确说明并给出用户可自行核实的方式。"
            )
        sys_parts.extend(
            [
                "本链路仅为文本推理：你没有调用 file_write、没有访问用户磁盘。严禁声称「已成功创建/保存 .docx」「已写入 我的文档/此电脑>文档」等；若用户要可下载文件，应明确说明须由用户在动作计划中「确认执行」file_write 到工作区，或自行在本机用 Word 另存。",
                "用户可通过网页回形针上传文件；若子任务涉及已上传文件，正文可能在「原始任务输入」的附件摘要中。不要编造用户未提供的文件内容。",
                "涉及「创建文档/保存文件」时：不要因未安装 Word 就拒绝；应给出可落地方案——例如建议相对路径如 data/artifacts/xxx.md、记事本或 WPS/LibreOffice/VS Code 等替代、以及可复制粘贴的正文草稿。",
                "若仍缺关键信息（路径、格式、是否覆盖），在答复末尾用简短编号列出 1～3 个需用户确认的问题。",
                "【总指挥设定的人设与要求】",
                persona,
            ]
        )
        user_parts: list[str] = []
        if (request.dialogue_context or "").strip():
            user_parts.append(f"【本会话近期对话（与当前任务同一线程）】\n{request.dialogue_context.strip()}")
        if request.method_ctx:
            user_parts.append(request.method_ctx)
        user_parts.extend(
            [
                f"原始任务输入：{self._manager.stm.user_input}",
                f"当前子任务步骤(step)：{task.get('step', '')}",
                f"子任务描述(description)：{task.get('description', '')}",
                "【此前各执行者的完整产出（请完整理解，勿遗漏细节；执行链为纯文本传递，无二次解析）】",
                request.context_window if request.context_window else "（尚无）",
                "",
                "请仅输出本步骤的最终结果正文。",
            ]
        )
        user_body = "\n".join(user_parts)
        user_content = self._manager._user_content_with_optional_vision(user_body)
        messages = [
            {"role": "system", "content": "\n".join(sys_parts)},
            {"role": "user", "content": user_content},
        ]
        llm_text = self._manager._call_llm(
            messages, fallback_text=f"执行完成：{task.get('description', '')}", agent_code=agent_type
        )
        result = {
            "agent_id": request.agent_id,
            "agent_type": agent_type,
            "agent_name": agent_name,
            "step": task.get("step", ""),
            "description": task.get("description", ""),
            "task_id": task.get("task_id", ""),
            "sub_task_id": task.get("sub_task_id", ""),
            "selected_personality": task.get("selected_personality", {}),
            "routing_scores": task.get("routing_scores", []),
            "routing_confidence": task.get("routing_confidence", 0.0),
            "routing_reason": task.get("routing_reason", ""),
            "result": str(llm_text or "").strip(),
            "status": "completed",
            "timestamp": time.time(),
        }
        self._manager.stm.agent_status[request.agent_id] = "completed"
        self._manager.record_model_thought(agent_type, f"任务执行完成：{result['result']}")
        self._manager.push_log(agent_type, "执行完成", "completed")
        self._manager.push_event(
            "agent_execute",
            "success",
            agent_type,
            f"{role} 已完成：{task.get('step', '')}",
            {
                "sub_task_id": task.get("sub_task_id"),
                "selected_personality": result.get("selected_personality", {}),
                "routing_reason": result.get("routing_reason", ""),
                "routing_confidence": result.get("routing_confidence", 0.0),
                "result_preview": (result["result"] or "")[:120],
            },
            agent_name_override=agent_name,
        )
        return result
