from config import MODEL_POOL, AGENT_TEMPLATES
import json
import random
import re
import time
import uuid
from typing import Any, Optional

from llm.volcengine_llm import VolcengineLLM
from memory.memory_system import ShortTermMemory, MidTermMemory, LongTermMemory


class TaskCancelledError(Exception):
    """当前任务被用户中止。"""


class ARIAManager:
    ALLOWED_ACTION_TYPES = {
        "kb_delete_all",
        "kb_delete_by_keyword",
        "kb_delete_low_quality",
        "conversation_archive",
        "conversation_new",
    }
    HIGH_RISK_ACTION_TYPES = {"kb_delete_all"}

    def __init__(self, api_key: Optional[str] = None):
        self.model_pool = MODEL_POOL
        self.agent_templates = AGENT_TEMPLATES
        self.execution_log = []  # 全流程日志（给UI展示）
        self.workflow_events = []  # 结构化工作流事件（给实时时间线）
        self.model_thoughts = {}  # 模型思考过程
        self.current_conversation_id = ""
        self.current_task_id = ""
        self.current_request_id = ""
        self.cancelled_requests: set[str] = set()
        self.event_sink = None
        self.api_key = api_key or ""
        self.llm = VolcengineLLM(self.api_key) if self.api_key else VolcengineLLM(None)
        
        # 初始化三级记忆
        self.stm = ShortTermMemory()  # 短期记忆
        self.mtm = MidTermMemory()  # 中期记忆
        self.ltm = LongTermMemory()  # 长期记忆
        
        # 加载记忆
        self.mtm.load()
        self.ltm.load()
        self.exec_agent_name_pool: dict[str, list[str]] = {
            "TextExecAgent": [
                "李楠", "张弛", "王越", "赵晨", "陈屿", "周航", "吴泽", "郑川", "冯煦", "孙启",
                "马岩", "朱睿", "胡峻", "郭湛", "何川", "高远", "林朔", "罗尧", "梁恺", "谢恒",
                "宋川", "唐逸", "许诺", "韩骁", "曹峥", "彭锐", "袁景", "邓一鸣", "蒋澈", "沈奕",
            ],
            "VisionExecAgent": [
                "周岚", "顾宁", "程澄", "苏芮", "夏沫", "叶青", "白露", "安禾", "姜苒", "陆悠",
                "沈禾", "温雅", "林汐", "贺晴", "乔然", "宋颜", "唐婧", "许薇", "袁念", "邱彤",
                "施瑶", "徐静", "韩悦", "罗妍", "蔡宁", "孔乔", "杜曼", "陶冉", "毛伊", "尹澜",
            ],
            "SpeechExecAgent": [
                "赵尧", "林嘉", "方恺", "魏哲", "潘越", "吕衡", "严朗", "任川", "施博", "钟宁",
                "董恺", "孟川", "祁峰", "易然", "池恒", "裴青", "邢岳", "鲍骁", "洪毅", "汪言",
                "贾睿", "范哲", "樊涛", "邹赫", "石航", "雷靖", "龙湛", "万川", "段驰", "侯野",
            ],
        }
        self.action_registry = {
            "kb_delete_all": self._exec_kb_delete_all,
            "kb_delete_by_keyword": self._exec_kb_delete_by_keyword,
            "kb_delete_low_quality": self._exec_kb_delete_low_quality,
            "conversation_new": self._exec_conversation_new,
            "conversation_archive": self._exec_conversation_archive,
        }

    def set_api_key(self, api_key: Optional[str]) -> None:
        api_key = (api_key or "").strip()
        if api_key == self.api_key:
            return
        self.api_key = api_key
        self.llm = VolcengineLLM(api_key if api_key else None)

    def set_conversation_context(self, conversation_id: str) -> None:
        self.current_conversation_id = conversation_id or ""

    def set_event_sink(self, sink) -> None:
        """注册事件回调，供 SSE 推送。"""
        self.event_sink = sink

    # 记录模型思考过程
    def record_model_thought(self, agent_name, thought):
        if agent_name not in self.model_thoughts:
            self.model_thoughts[agent_name] = []
        self.model_thoughts[agent_name].append({
            "thought": thought,
            "timestamp": time.time()
        })

    # 获取模型思考过程
    def get_model_thoughts(self, agent_name):
        return self.model_thoughts.get(agent_name, [])

    # 清空模型思考过程
    def clear_model_thoughts(self):
        self.model_thoughts = {}

    def _agent_profile(self, agent_code: str) -> dict[str, str]:
        mapping = {
            "TaskParser": {"role": "项目经理PM", "name": "王琳"},
            "MethodSearcher": {"role": "知识专家KS", "name": "陈舟"},
            "SolutionLearner": {"role": "执行专家EXE", "name": "李楠"},
            "TaskSplitter": {"role": "项目经理PM", "name": "王琳"},
            "TextExecAgent": {"role": "执行专家EXE", "name": "李楠"},
            "VisionExecAgent": {"role": "视觉专家VE", "name": "周岚"},
            "SpeechExecAgent": {"role": "语音专家SE", "name": "赵尧"},
            "QualityChecker": {"role": "质检QA", "name": "周启"},
            "MethodSaver": {"role": "知识专家KS", "name": "陈舟"},
        }
        return mapping.get(agent_code, {"role": "执行专家EXE", "name": "李楠"})

    def _pick_exec_agent_name(self, agent_type: str, used_names: dict[str, set[str]]) -> str:
        pool = self.exec_agent_name_pool.get(agent_type, [])
        fallback = self._agent_profile(agent_type)["name"]
        if not pool:
            return fallback
        used = used_names.setdefault(agent_type, set())
        candidates = [n for n in pool if n not in used]
        picked = random.choice(candidates or pool)
        used.add(picked)
        return picked

    def push_event(
        self,
        stage: str,
        status: str,
        agent_code: str,
        summary: str,
        detail: dict[str, Any] | None = None,
        agent_name_override: str | None = None,
    ) -> None:
        profile = self._agent_profile(agent_code)
        event = {
            "event_id": str(uuid.uuid4()),
            "conversation_id": self.current_conversation_id,
            "task_id": self.current_task_id,
            "request_id": self.current_request_id,
            "stage": stage,
            "status": status,  # pending/running/success/error
            "agent_code": agent_code,
            "agent_name": agent_name_override or profile["name"],
            "agent_role": profile["role"],
            "summary": summary,
            "detail": detail or {},
            "timestamp": time.time(),
        }
        self.workflow_events.append(event)
        if self.event_sink:
            try:
                self.event_sink(event)
            except Exception:
                pass

    def get_workflow_events(self) -> list[dict[str, Any]]:
        return self.workflow_events

    def clear_workflow_events(self) -> None:
        self.workflow_events = []

    def request_cancel(self, request_id: str) -> bool:
        rid = (request_id or "").strip()
        if not rid:
            return False
        self.cancelled_requests.add(rid)
        return True

    def clear_cancel(self, request_id: str) -> None:
        rid = (request_id or "").strip()
        if rid and rid in self.cancelled_requests:
            self.cancelled_requests.remove(rid)

    def is_cancelled(self, request_id: str | None = None) -> bool:
        rid = (request_id or self.current_request_id or "").strip()
        return bool(rid) and rid in self.cancelled_requests

    def check_cancelled(self, stage: str) -> None:
        if self.is_cancelled():
            self.push_event(
                "task_cancelled",
                "success",
                "TaskParser",
                "任务已中止",
                {"stage": stage, "request_id": self.current_request_id},
            )
            self.push_log("系统", f"任务已中止（阶段：{stage}）", "warning")
            raise TaskCancelledError(f"任务已中止（{stage}）")

    def _normalize_query_text(self, text: str) -> str:
        s = (text or "").strip().lower()
        s = re.sub(r"\s+", "", s)
        s = re.sub(r"[，。！？,.!?:;；、\"'“”‘’`~@#$%^&*()（）\[\]{}<>《》\-_=+\\/|]+", "", s)
        return s

    def find_exact_methodology(self, user_input: str) -> dict[str, Any] | None:
        normalized_query = self._normalize_query_text(user_input)
        if not normalized_query:
            return None
        methodologies = getattr(self.ltm, "methodologies", []) or []
        for method in methodologies:
            scene = str(method.get("scene") or method.get("scenario") or "")
            if self._normalize_query_text(scene) == normalized_query:
                return method
        return None

    def _call_llm(self, messages: list[dict[str, str]], fallback_text: str = "") -> str:
        """调用 LLM；失败时返回 fallback_text。"""
        if self.is_cancelled():
            return fallback_text
        try:
            if not getattr(self, "llm", None) or getattr(self.llm, "ark", None) is None:
                return fallback_text
            return self.llm.generate(messages)
        except Exception as e:
            self.push_log("LLM", f"LLM调用失败: {str(e)}", "warning")
            return fallback_text

    def _extract_json_object(self, text: str) -> dict[str, Any]:
        if not text:
            return {}
        cleaned = text.strip()
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"```$", "", cleaned).strip()
        m = re.search(r"\{[\s\S]*\}", cleaned)
        if not m:
            return {}
        try:
            return json.loads(m.group(0))
        except Exception:
            return {}

    def _normalize_keywords(self, keywords: Any) -> list[str]:
        if keywords is None:
            return []
        if isinstance(keywords, list):
            return [str(k).strip() for k in keywords if str(k).strip()]
        if isinstance(keywords, str):
            # 按中文/英文常见分隔符拆分
            parts = re.split(r"[\s,，;；/|]+", keywords.strip())
            return [p.strip() for p in parts if p.strip()]
        return [str(keywords).strip()] if str(keywords).strip() else []

    def _normalize_methodology(self, method: dict[str, Any], task_info: dict[str, Any]) -> dict[str, Any]:
        scene = method.get("scene") or method.get("scenario") or task_info.get("user_input", "")[:50]
        keywords = method.get("keywords")
        if keywords is None:
            keywords = method.get("core_keywords")
        keywords = self._normalize_keywords(keywords) or task_info.get("user_input", "").split()[:5]

        solve_steps = method.get("solve_steps") or method.get("steps") or []
        if isinstance(solve_steps, str):
            solve_steps = [s.strip() for s in re.split(r"[\n;；]+", solve_steps) if s.strip()]

        applicable_range = method.get("applicable_range", "") or method.get("applicability", "")
        text = " ".join([scene, " ".join(keywords), task_info.get("user_input", "")]).lower()
        category = "通用/其他"
        greeting_keywords = ["你好", "您好", "hello", "hi", "在吗", "谢谢", "早上好", "晚上好"]
        if any(g in text for g in greeting_keywords):
            category = "通用/其他"
        elif sum(1 for k in ["分析", "报表", "指标", "趋势", "data", "sql"] if k in text) >= 2:
            category = "数据分析/报表"
        elif sum(1 for k in ["代码", "开发", "接口", "python", "bug", "java", "前端", "后端"] if k in text) >= 2:
            category = "开发工程/代码实现"
        elif sum(1 for k in ["需求", "产品", "交互", "原型", "prd"] if k in text) >= 2:
            category = "产品设计/需求"
        elif sum(1 for k in ["运营", "增长", "市场", "投放", "活动"] if k in text) >= 2:
            category = "运营增长/市场"
        title = method.get("title") or method.get("name") or (scene[:24] if scene else "新方法论")
        event_key = f"{str(scene).strip().lower()}|{'/'.join(sorted({k.lower() for k in keywords})[:4])}"

        return {
            "method_id": str(uuid.uuid4()),
            "title": title,
            "category": category,
            "scene": scene,
            "scenario": scene,  # 兼容 LongTermMemory 相似度逻辑
            "keywords": keywords,
            "core_keywords": keywords,  # 兼容 LongTermMemory 相似度逻辑
            "solve_steps": solve_steps,
            "applicable_range": applicable_range,
            "event_key": event_key,
            "success_count": int(bool(method.get("is_success", False))),
            "usage_count": 0,
            "create_time": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

    def _should_save_methodology(
        self,
        task_info: dict[str, Any],
        method: dict[str, Any],
        result_payload: Any,
    ) -> tuple[bool, str, str]:
        """
        判定是否应沉淀方法论。
        返回 (should_save, reason, source)。
        source: llm / heuristic
        """
        user_input = str(task_info.get("user_input", "") or "").strip()
        if not user_input:
            return False, "empty_input", "heuristic"

        # 1) 优先走 LLM 判定（更灵活，避免硬编码）
        method_scene = str((method or {}).get("scene") or (method or {}).get("scenario") or "").strip()
        method_keywords = self._normalize_keywords((method or {}).get("keywords") or (method or {}).get("core_keywords"))
        step_count = len((method or {}).get("solve_steps") or (method or {}).get("steps") or [])
        is_success = bool(result_payload.get("is_success")) if isinstance(result_payload, dict) else False

        messages = [
            {
                "role": "system",
                "content": (
                    "你是ARIA知识沉淀判定器。目标：判断这次对话是否值得沉淀为可复用方法论。"
                    "请只输出JSON：{\"should_save\":true/false,\"reason\":\"...\"}。"
                    "规则：寒暄/问候/纯礼貌/无明确任务目标 -> false；"
                    "有清晰任务目标、可复用步骤或可迁移经验 -> true。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"user_input: {user_input}\n"
                    f"task_type: {task_info.get('task_type', '')}\n"
                    f"intent: {task_info.get('intent', '')}\n"
                    f"method_scene: {method_scene}\n"
                    f"method_keywords: {method_keywords}\n"
                    f"method_step_count: {step_count}\n"
                    f"is_success: {is_success}"
                ),
            },
        ]
        llm_text = self._call_llm(messages, fallback_text="")
        llm_data = self._extract_json_object(llm_text)
        if llm_data:
            should_save = bool(llm_data.get("should_save", False))
            reason = str(llm_data.get("reason") or ("valuable_task" if should_save else "small_talk"))
            return should_save, reason[:80], "llm"

        # 2) 回退轻量启发式（仅在 LLM 不可用/失败时）
        compact_input = re.sub(r"[\s\W_]+", "", user_input.lower())
        greeting_keywords = ["你好", "您好", "hello", "hi", "hey", "在吗", "谢谢", "thank", "早上好", "晚上好"]
        has_greeting = any(k in user_input.lower() for k in greeting_keywords)
        if has_greeting and len(compact_input) <= 12:
            return False, "small_talk_fallback", "heuristic"
        return True, "valuable_task_fallback", "heuristic"

    def classify_interaction_mode(self, user_input: str) -> dict[str, Any]:
        text = (user_input or "").strip()
        if not text:
            return {"mode": "small_talk", "reason": "empty_input", "source": "heuristic", "confidence": 1.0}

        messages = [
            {
                "role": "system",
                "content": (
                    "你是ARIA输入路由器。判断用户输入应该走哪条链路："
                    "small_talk(寒暄/问候/感谢/闲聊) 或 task(有明确目标的任务请求)。"
                    "仅输出JSON：{\"mode\":\"small_talk|task\",\"reason\":\"...\",\"confidence\":0-1}。"
                ),
            },
            {"role": "user", "content": f"用户输入：{text}"},
        ]
        llm_text = self._call_llm(messages, fallback_text="")
        data = self._extract_json_object(llm_text)
        if data:
            mode = str(data.get("mode", "")).strip().lower()
            if mode in ("small_talk", "task"):
                try:
                    confidence = float(data.get("confidence", 0.8))
                except Exception:
                    confidence = 0.8
                return {
                    "mode": mode,
                    "reason": str(data.get("reason") or ""),
                    "source": "llm",
                    "confidence": max(0.0, min(1.0, confidence)),
                }

        lowered = text.lower()
        compact = re.sub(r"[\s\W_]+", "", lowered)
        greeting_keywords = ["你好", "您好", "hello", "hi", "hey", "在吗", "谢谢", "thank", "早上好", "晚上好"]
        if any(k in lowered for k in greeting_keywords) and len(compact) <= 16:
            return {"mode": "small_talk", "reason": "greeting_fallback", "source": "heuristic", "confidence": 0.9}
        return {"mode": "task", "reason": "task_fallback", "source": "heuristic", "confidence": 0.7}

    def derive_action_risk(self, action_type: str, risk: str) -> str:
        normalized = (risk or "").strip().lower()
        if normalized not in ("low", "medium", "high"):
            normalized = "medium"
        if action_type in self.HIGH_RISK_ACTION_TYPES:
            return "high"
        return normalized

    def normalize_action_plan(self, plan: dict[str, Any]) -> dict[str, Any]:
        mode = str(plan.get("mode") or "").strip().lower()
        if mode not in ("action", "qa", "small_talk"):
            mode = "qa"
        actions = plan.get("actions")
        if not isinstance(actions, list):
            actions = []
        normalized_actions = []
        for action in actions:
            if not isinstance(action, dict):
                continue
            action_type = str(action.get("type") or "").strip()
            if not action_type or action_type not in self.ALLOWED_ACTION_TYPES:
                continue
            normalized_actions.append(
                {
                    "type": action_type,
                    "target": str(action.get("target") or "").strip(),
                    "filters": action.get("filters") if isinstance(action.get("filters"), dict) else {},
                    "params": action.get("params") if isinstance(action.get("params"), dict) else {},
                    "risk": self.derive_action_risk(action_type, str(action.get("risk") or "medium")),
                    "reason": str(action.get("reason") or "").strip(),
                }
            )
        return {
            "mode": mode,
            "summary": str(plan.get("summary") or "").strip(),
            "requires_confirmation": True,
            "actions": normalized_actions,
            "requires_double_confirmation": self.requires_double_confirmation(normalized_actions),
        }

    def plan_actions(self, user_input: str) -> dict[str, Any]:
        text = (user_input or "").strip()
        if not text:
            return {"mode": "small_talk", "summary": "empty_input", "requires_confirmation": True, "actions": []}

        messages = [
            {
                "role": "system",
                "content": (
                    "你是ARIA动作规划器。请把用户输入解析为：small_talk / qa / action。"
                    "如果是action，输出可执行动作列表。禁止编造执行结果。"
                    "仅输出JSON："
                    "{\"mode\":\"small_talk|qa|action\","
                    "\"summary\":\"...\","
                    "\"actions\":[{\"type\":\"...\",\"target\":\"...\",\"filters\":{},\"params\":{},\"risk\":\"low|medium|high\",\"reason\":\"...\"}]}"
                    "可用动作类型示例：kb_delete_all,kb_delete_by_keyword,kb_delete_low_quality,conversation_archive,conversation_new。"
                ),
            },
            {"role": "user", "content": text},
        ]
        llm_text = self._call_llm(messages, fallback_text="")
        llm_plan = self._extract_json_object(llm_text)
        plan = self.normalize_action_plan(llm_plan) if llm_plan else {}
        if plan and (plan.get("mode") != "qa" or plan.get("actions")):
            return plan

        lowered = text.lower()
        if any(k in lowered for k in ["清理", "清空", "删除", "移除"]) and any(k in text for k in ["知识库", "方法论", "经验"]):
            action_type = "kb_delete_low_quality"
            if "清空" in text:
                action_type = "kb_delete_all"
            actions = [{
                "type": action_type,
                "target": "knowledge_base",
                "filters": {},
                "params": {},
                "risk": self.derive_action_risk(action_type, "medium"),
                "reason": "用户请求清理知识库",
            }]
            return {
                "mode": "action",
                "summary": "识别为知识库清理操作",
                "requires_confirmation": True,
                "actions": actions,
                "requires_double_confirmation": self.requires_double_confirmation(actions),
            }
        return {"mode": "qa", "summary": "未识别为可执行动作", "requires_confirmation": True, "actions": []}

    def format_action_plan_for_user(self, plan: dict[str, Any]) -> str:
        actions = plan.get("actions") or []
        if not actions:
            return "我理解了你的请求，但当前未识别出可执行动作。请再具体一点，比如“删除关键词为xx的方法论”。"
        lines = ["我已理解为可执行操作，执行前请确认："]
        for idx, action in enumerate(actions, start=1):
            lines.append(
                f"{idx}. type={action.get('type')} target={action.get('target')} risk={action.get('risk')} reason={action.get('reason')}"
            )
        if self.requires_double_confirmation(actions):
            lines.append("检测到高风险动作：需要二次确认。先回复“确认执行”，再回复“二次确认”后才会实际执行。")
        else:
            lines.append("请回复“确认执行”后我再实际执行。")
        return "\n".join(lines)

    def requires_double_confirmation(self, actions: list[dict[str, Any]]) -> bool:
        return any((a.get("risk") or "medium") == "high" for a in (actions or []))

    def execute_actions(
        self,
        actions: list[dict[str, Any]],
        conversation_id: str,
        request_id: str,
        methodology_manager: Any,
        conversation_manager: Any,
    ) -> dict[str, Any]:
        report = []
        for action in actions or []:
            action_type = action.get("type", "")
            handler = self.action_registry.get(action_type)
            if not handler:
                report.append({"action": action_type, "result": {"success": False, "message": "unsupported_action"}})
                continue
            try:
                result = handler(action, conversation_id, methodology_manager, conversation_manager)
                report.append({"action": action_type, "result": result})
            except Exception as e:
                report.append({"action": action_type, "result": {"success": False, "message": str(e)}})
        success_count = sum(1 for r in report if r.get("result", {}).get("success") is not False)
        return {"success_count": success_count, "total": len(report), "report": report}

    def _exec_kb_delete_all(self, action: dict[str, Any], conversation_id: str, methodology_manager: Any, conversation_manager: Any) -> dict[str, Any]:
        all_methods = methodology_manager.get_all_methodologies() or []
        ids = [m.get("method_id") for m in all_methods if m.get("method_id")]
        return methodology_manager.delete_methodologies_batch(ids)

    def _exec_kb_delete_by_keyword(self, action: dict[str, Any], conversation_id: str, methodology_manager: Any, conversation_manager: Any) -> dict[str, Any]:
        kw = str((action.get("filters") or {}).get("keyword") or "").strip()
        candidates = methodology_manager.search_methodologies(kw) if kw else []
        ids = [m.get("method_id") for m in candidates if m.get("method_id")]
        result = methodology_manager.delete_methodologies_batch(ids)
        result["keyword"] = kw
        return result

    def _exec_kb_delete_low_quality(self, action: dict[str, Any], conversation_id: str, methodology_manager: Any, conversation_manager: Any) -> dict[str, Any]:
        all_methods = methodology_manager.get_all_methodologies() or []
        ids = [
            m.get("method_id")
            for m in all_methods
            if m.get("method_id") and int(m.get("success_count", 0)) <= 0 and int(m.get("usage_count", 0)) <= 0
        ]
        return methodology_manager.delete_methodologies_batch(ids)

    def _exec_conversation_new(self, action: dict[str, Any], conversation_id: str, methodology_manager: Any, conversation_manager: Any) -> dict[str, Any]:
        title = str((action.get("params") or {}).get("title") or "新会话")
        conv = conversation_manager.create_conversation(title)
        return {"success": True, "conversation_id": conv.get("conversation_id")}

    def _exec_conversation_archive(self, action: dict[str, Any], conversation_id: str, methodology_manager: Any, conversation_manager: Any) -> dict[str, Any]:
        conv_id = str((action.get("params") or {}).get("conversation_id") or conversation_id or "").strip()
        ok = conversation_manager.set_archived(conv_id, True) if conv_id else False
        return {"success": bool(ok), "conversation_id": conv_id}

    def generate_small_talk_reply(self, user_input: str) -> str:
        text = (user_input or "").strip()
        messages = [
            {
                "role": "system",
                "content": (
                    "你是ARIA助手。请对用户寒暄做简短友好回复。"
                    "要求：1-2句话、总长度不超过50字、不输出JSON、不输出步骤。"
                ),
            },
            {"role": "user", "content": text or "你好"},
        ]
        llm_text = self._call_llm(messages, fallback_text="")
        cleaned = (llm_text or "").strip()
        if cleaned:
            cleaned = cleaned.replace("```", "").strip()
            if len(cleaned) <= 120 and "{" not in cleaned:
                return cleaned
        if any(k in text.lower() for k in ["谢谢", "thank"]):
            return "不客气，我在这儿，随时可以继续帮你。"
        return "你好，我在。告诉我你想解决什么问题，我马上开始。"

    # 1. 解析用户问题
    def parse_task(self, user_input: str) -> dict:
        self.check_cancelled("task_parse_start")
        # 每次请求生成一个任务ID，供前端只展示当前任务协作日志
        self.current_task_id = str(uuid.uuid4())
        self.push_event("task_parse", "running", "TaskParser", "PM 正在解析用户需求")
        self.push_log("TaskParser", "正在分析你的问题", "running")
        # 记录模型思考过程
        self.record_model_thought("TaskParser", f"收到用户输入: {user_input}")
        self.record_model_thought("TaskParser", "分析用户意图和任务类型")

        # LLM 任务解析（失败则回退到简单规则解析）
        fallback_task_info = {
            "task_id": self.current_task_id,
            "user_input": user_input,
            "task_type": "text",
            "intent": "general",
            "keywords": user_input.split()[:5],
            "timestamp": time.time(),
        }
        messages = [
            {
                "role": "system",
                "content": "你是ARIA任务解析器。请根据用户输入提取任务类型(task_type)、意图(intent)以及关键词(keywords)。只输出严格JSON，不要多余文本。keywords为数组，元素为短关键词（3-8个字/词）。",
            },
            {"role": "user", "content": f"用户输入：{user_input}"},
        ]
        llm_text = self._call_llm(messages, fallback_text="")
        data = self._extract_json_object(llm_text)

        task_info = fallback_task_info
        if data:
            task_info.update(
                {
                    "task_id": fallback_task_info["task_id"],
                    "user_input": user_input,
                    "task_type": str(data.get("task_type") or "text"),
                    "intent": str(data.get("intent") or "general"),
                    "keywords": self._normalize_keywords(data.get("keywords"))[:10],
                    "timestamp": time.time(),
                }
            )

        # 写入短期记忆
        self.stm.task_id = task_info["task_id"]
        self.stm.user_input = user_input
        
        self.record_model_thought("TaskParser", f"任务解析完成，任务类型: {task_info['task_type']}")
        self.push_event(
            "task_parse",
            "success",
            "TaskParser",
            "PM 已完成需求解析",
            {"task_type": task_info.get("task_type"), "intent": task_info.get("intent")},
        )
        self.push_log("TaskParser", "问题分析完成", "completed")
        self.check_cancelled("task_parse_end")
        return task_info

    # 2. 匹配本地方法论
    def match_methodology(self, task_info: dict) -> tuple[float, dict]:
        self.check_cancelled("method_match_start")
        self.push_event("method_match", "running", "MethodSearcher", "知识专家正在检索历史方法论")
        self.push_log("MethodSearcher", "正在查找历史解决方案", "running")
        # 记录模型思考过程
        self.record_model_thought("MethodSearcher", f"基于用户输入: {task_info['user_input']} 查找匹配的方法论")
        self.record_model_thought("MethodSearcher", "从长期记忆中查找方法论")
        exact = self.find_exact_methodology(task_info.get("user_input", ""))
        if exact:
            self.record_model_thought("MethodSearcher", "命中同问句精确复用")
            self.push_event(
                "method_match",
                "success",
                "MethodSearcher",
                "命中同问句复用，跳过外网学习",
                {"score": 1.0, "exact_hit": True},
            )
            self.push_log("MethodSearcher", "命中同问句复用", "completed")
            self.check_cancelled("method_match_exact_hit")
            return 1.0, exact

        # 从长期记忆中搜索方法论：传入用户原始输入，尽量包含“场景”语义
        query = (task_info.get("user_input") or "").strip()
        results = self.ltm.search_methodology(query)
        
        best_match = None
        best_score = 0
        if results:
            best_score, best_match = results[0]
            self.record_model_thought("MethodSearcher", f"成功找到匹配方法论，相似度：{best_score:.2f}")
        else:
            self.record_model_thought("MethodSearcher", "未找到匹配的方法论")

        self.record_model_thought("MethodSearcher", f"匹配完成，最佳匹配相似度：{best_score:.2f}")
        self.push_event(
            "method_match",
            "success",
            "MethodSearcher",
            f"方法论匹配完成，相似度 {best_score:.2f}",
            {"score": best_score},
        )
        self.push_log("MethodSearcher", f"找到匹配方案，相似度：{best_score:.2f}", "completed")
        self.check_cancelled("method_match_end")
        return best_score, best_match

    # 3. 无方案 → 调用外网大模型学习
    def learn_from_external(self, task_info: dict) -> dict:
        self.check_cancelled("method_learn_start")
        self.push_event("method_learn", "running", "SolutionLearner", "执行专家正在学习新的解决方案")
        self.push_log("SolutionLearner", "正在外网获取解决方案", "running")
        # 记录模型思考过程
        self.record_model_thought("SolutionLearner", f"调用大模型学习解决方案，用户输入: {task_info['user_input']}")
        self.record_model_thought("SolutionLearner", "正在分析问题并生成解决方案")
        fallback_solution = {
            "scene": task_info["user_input"][:50],
            "keywords": self._normalize_keywords(task_info.get("keywords") or task_info["user_input"].split()[:5]),
            "solve_steps": ["分析问题", "查找资料", "生成解决方案", "验证结果"],
            "applicable_range": "通用",
        }
        messages = [
            {
                "role": "system",
                "content": "你是ARIA方案学习器。请把用户需求抽象成一个可复用的方法论(methodology)。只输出严格JSON，不要多余文本。JSON字段: scene(字符串), keywords(字符串数组), solve_steps(字符串数组), applicable_range(字符串，可选)。",
            },
            {
                "role": "user",
                "content": f"用户需求：{task_info.get('user_input','')}\n\n请给出：1) 场景(scene)，2) 关键词(keywords)，3) 解决步骤(solve_steps，4-8条)，4) 适用范围(applicable_range)。",
            },
        ]
        llm_text = self._call_llm(messages, fallback_text="")
        data = self._extract_json_object(llm_text)
        solution = data if data else fallback_solution
        solution["is_success"] = False
        self.push_event(
            "method_learn",
            "success",
            "SolutionLearner",
            "执行专家已输出候选方法论",
            {"steps_count": len(solution.get("solve_steps", []))},
        )
        self.record_model_thought("SolutionLearner", f"学习完成，生成解决方案: {solution['solve_steps']}")
        self.push_log("SolutionLearner", "学习完成，生成解决方案", "completed")
        self.check_cancelled("method_learn_end")
        return solution

    # 4. 拆分子任务
    def split_sub_tasks(self, task_info: dict, method: dict) -> list:
        self.check_cancelled("task_split_start")
        self.push_event("task_split", "running", "TaskSplitter", "PM 正在拆分子任务")
        self.push_log("TaskSplitter", "正在拆分任务", "running")
        # 记录模型思考过程
        self.record_model_thought("TaskSplitter", f"基于方法论拆分子任务，用户输入: {task_info['user_input']}")
        self.record_model_thought("TaskSplitter", f"方法论步骤: {method.get('solve_steps', [])}")
        steps = method.get("solve_steps", []) or []
        fallback_sub_tasks: list[dict[str, Any]] = []
        for step in steps:
            fallback_sub_tasks.append(
                {
                    "sub_task_id": str(uuid.uuid4()),
                    "task_id": task_info["task_id"],
                    "step": str(step),
                    "description": f"执行{step}",
                    "agent_type": "TextExecAgent",
                }
            )

        messages = [
            {
                "role": "system",
                "content": "你是ARIA任务拆分器。请把solve_steps拆成可执行子任务。只输出严格JSON，不要多余文本。字段：sub_tasks(数组)，数组元素包含 step(字符串), description(字符串), agent_type(只能是 TextExecAgent / VisionExecAgent / SpeechExecAgent)。",
            },
            {
                "role": "user",
                "content": f"任务原始输入：{task_info.get('user_input','')}\n\n方法论场景(scene)：{method.get('scene','') or method.get('scenario','')}\n\nsolve_steps：{steps}",
            },
        ]
        llm_text = self._call_llm(messages, fallback_text="")
        data = self._extract_json_object(llm_text)
        sub_tasks_data = data.get("sub_tasks") if isinstance(data.get("sub_tasks"), list) else None

        if not sub_tasks_data:
            sub_tasks = fallback_sub_tasks
        else:
            sub_tasks = []
            for item in sub_tasks_data:
                step = str(item.get("step") or "")
                sub_tasks.append(
                    {
                        "sub_task_id": str(uuid.uuid4()),
                        "task_id": task_info["task_id"],
                        "step": step,
                        "description": str(item.get("description") or f"执行{step}"),
                        "agent_type": str(item.get("agent_type") or "TextExecAgent"),
                    }
                )
        
        # 写入短期记忆
        self.stm.sub_tasks = sub_tasks
        
        self.record_model_thought("TaskSplitter", f"任务拆分完成，共{len(sub_tasks)}个子任务")
        self.push_event(
            "task_split",
            "success",
            "TaskSplitter",
            f"任务拆分完成，共 {len(sub_tasks)} 个子任务",
            {"sub_tasks": sub_tasks},
        )
        self.push_log("TaskSplitter", f"拆分完成，共{len(sub_tasks)}个子任务", "completed")
        self.check_cancelled("task_split_end")
        return sub_tasks

    # 5. 动态生成Agent
    def create_agents(self, sub_tasks: list) -> dict:
        self.check_cancelled("agent_create_start")
        self.push_event("agent_create", "running", "TaskSplitter", "PM 正在组建执行小队")
        self.push_log("TaskSplitter", "正在生成执行Agent", "running")
        # 记录模型思考过程
        self.record_model_thought("TaskSplitter", f"开始生成Agent，共{len(sub_tasks)}个子任务")
        time.sleep(0.5)  # 添加延迟，使日志显示更加流畅
        agents = {}
        agent_status = {}
        used_names_by_type: dict[str, set[str]] = {}
        for sub_task in sub_tasks:
            agent_id = str(uuid.uuid4())
            agent_type = sub_task["agent_type"]
            models = self.agent_templates.get(agent_type, ["llm"])
            assigned_name = self._pick_exec_agent_name(agent_type, used_names_by_type)
            # 这里应该实例化具体的Agent类，现在只是模拟
            agents[agent_id] = {
                "agent_id": agent_id,
                "agent_type": agent_type,
                "task": sub_task,
                "models": models,
                "agent_name": assigned_name,
            }
            agent_status[agent_id] = "created"
            self.record_model_thought("TaskSplitter", f"生成Agent: {agent_type}({assigned_name})，使用模型: {models}")
        
        # 写入短期记忆
        self.stm.agent_status = agent_status
        
        self.record_model_thought("TaskSplitter", f"Agent生成完成，共{len(agents)}个Agent")
        self.push_event(
            "agent_create",
            "success",
            "TaskSplitter",
            f"执行小队组建完成，共 {len(agents)} 名成员",
        )
        self.push_log("TaskSplitter", f"生成完成，共{len(agents)}个Agent", "completed")
        self.check_cancelled("agent_create_end")
        return agents

    # 6. 执行Agent
    def run_agents(self, agents: dict) -> list:
        self.check_cancelled("agent_execute_start")
        results: list[dict[str, Any]] = []
        previous_results_text = ""
        for agent_id, agent in agents.items():
            self.check_cancelled("agent_execute_loop")
            agent_type = agent["agent_type"]
            task = agent["task"]
            agent_name = agent.get("agent_name") or self._agent_profile(agent_type)["name"]
            role = self._agent_profile(agent_type)["role"]
            self.push_event(
                "agent_execute",
                "running",
                agent_type,
                f"{role} 正在执行：{task['description']}",
                {"sub_task_id": task.get("sub_task_id")},
                agent_name_override=agent_name,
            )
            self.push_log(agent_type, f"正在执行子任务：{task['description']}", "running")
            # 记录模型思考过程
            self.record_model_thought(agent_type, f"开始执行任务：{task['description']}")
            self.record_model_thought(agent_type, f"使用模型：{agent['models']}")

            messages = [
                {
                    "role": "system",
                    "content": f"你是ARIA执行专家[{agent_type}]。你将基于给定步骤产出可直接使用的结果。只输出纯文本，不要JSON。",
                },
                {
                    "role": "user",
                    "content": (
                        f"原始任务输入：{self.stm.user_input}\n"
                        f"当前子任务步骤(step)：{task.get('step','')}\n"
                        f"子任务描述(description)：{task.get('description','')}\n"
                        f"已有步骤产出(previous_results)：{previous_results_text or '无'}\n\n"
                        "请输出该步骤的结果。"
                    ),
                },
            ]
            llm_text = self._call_llm(messages, fallback_text=f"执行完成：{task['description']}")

            result = {
                "agent_id": agent_id,
                "agent_type": agent_type,
                "task_id": task["task_id"],
                "sub_task_id": task["sub_task_id"],
                "result": llm_text.strip(),
                "status": "completed",
                "timestamp": time.time(),
            }
            # 更新短期记忆中的Agent状态
            self.stm.agent_status[agent_id] = "completed"
            self.record_model_thought(agent_type, f"任务执行完成：{result['result']}")
            results.append(result)
            self.push_log(agent_type, "执行完成", "completed")
            self.push_event(
                "agent_execute",
                "success",
                agent_type,
                f"{role} 已完成：{task['step']}",
                {
                    "sub_task_id": task.get("sub_task_id"),
                    "result_preview": (result["result"] or "")[:120],
                },
                agent_name_override=agent_name,
            )

            previous_results_text = "\n".join([r["result"] for r in results])
        
        # 写入短期记忆
        self.stm.results = results
        
        self.check_cancelled("agent_execute_end")
        return results

    # 7. 校验结果
    def check_result(self, results: list) -> dict:
        self.check_cancelled("quality_check_start")
        self.push_event("quality_check", "running", "QualityChecker", "QA 正在校验并汇总结果")
        self.push_log("QualityChecker", "正在校验结果", "running")
        # 记录模型思考过程
        self.record_model_thought("QualityChecker", f"开始校验结果，共{len(results)}个结果")
        for i, result in enumerate(results):
            self.record_model_thought("QualityChecker", f"校验第{i+1}个结果：{result['result']}")

        fallback_final = "\n".join([result["result"] for result in results])
        messages = [
            {
                "role": "system",
                "content": "你是ARIA质量校验员。请基于各子步骤产出生成最终结果，并判断整体是否符合要求。只输出严格JSON，不要多余文本。JSON字段：final_result(字符串), is_success(布尔)。",
            },
            {
                "role": "user",
                "content": f"原始任务输入：{self.stm.user_input}\n\n子步骤产出：{json.dumps(results, ensure_ascii=False)}",
            },
        ]
        llm_text = self._call_llm(messages, fallback_text="")
        data = self._extract_json_object(llm_text)
        if not data:
            final_result = fallback_final
            is_success = False
        else:
            final_result = str(data.get("final_result") or fallback_final)
            is_success = bool(data.get("is_success", False))

        self.record_model_thought("QualityChecker", "结果校验完成，生成最终结果")
        self.push_event(
            "quality_check",
            "success",
            "QualityChecker",
            "QA 已完成校验与汇总",
            {"is_success": is_success},
        )
        self.push_log("QualityChecker", "结果校验完成", "completed")
        self.check_cancelled("quality_check_end")
        return {"final_result": final_result, "is_success": is_success}

    # 8. 保存方法论
    def save_methodology(self, task_info: dict, method: dict, result_payload: Any):
        self.check_cancelled("method_save_start")
        should_save, skip_reason, judge_source = self._should_save_methodology(task_info, method or {}, result_payload)
        if not should_save:
            self.record_model_thought(
                "MethodSaver",
                f"知识沉淀判定为跳过，reason={skip_reason}, source={judge_source}"
            )
            self.push_event(
                "method_save",
                "success",
                "MethodSaver",
                "本轮对话暂不满足沉淀条件，已跳过方法论入库",
                {"skipped": True, "reason": skip_reason, "judge_source": judge_source},
            )
            self.push_log("MethodSaver", f"已跳过方法论保存（{skip_reason}）", "completed")
            self.check_cancelled("method_save_skipped")
            return

        self.push_event("method_save", "running", "MethodSaver", "知识专家正在沉淀方法论")
        self.push_log("MethodSaver", "正在保存方案", "running")
        # 记录模型思考过程
        self.record_model_thought("MethodSaver", f"开始保存方法论，用户输入: {task_info['user_input']}")
        self.record_model_thought("MethodSaver", "将方法论保存到长期记忆")

        is_success = False
        final_result_text = ""
        if isinstance(result_payload, dict):
            is_success = bool(result_payload.get("is_success", False))
            final_result_text = str(result_payload.get("final_result", ""))
        else:
            final_result_text = str(result_payload)

        normalized_method = self._normalize_methodology(method or {}, task_info)
        normalized_method["success_count"] = 1 if is_success else 0
        normalized_method["is_success"] = is_success

        self.ltm.add_methodology(normalized_method)
        
        # 保存到中期记忆作为模板
        task_template = {
            "template_id": str(uuid.uuid4()),
            "task_type": task_info["task_type"],
            "solve_steps": normalized_method["solve_steps"],
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        self.mtm.task_templates.append(task_template)
        self.mtm.save()

        self.record_model_thought("MethodSaver", "方法论保存完成")
        self.push_event("method_save", "success", "MethodSaver", "方法论沉淀完成")
        self.push_log("MethodSaver", "方案保存完成", "completed")
        self.check_cancelled("method_save_end")

    # 9. 销毁所有Agent
    def destroy_agents(self, agents: dict):
        self.push_log("TaskSplitter", "正在销毁Agent", "running")
        # 记录模型思考过程
        self.record_model_thought("TaskSplitter", f"开始销毁Agent，共{len(agents)}个Agent")
        time.sleep(0.3)  # 添加延迟，使日志显示更加流畅
        # 实际应该调用Agent的销毁方法，释放资源
        agents.clear()
        # 任务结束，清空短期记忆
        self.stm.clear()
        self.record_model_thought("TaskSplitter", "Agent销毁完成，短期记忆已清空")
        self.push_event("agent_destroy", "success", "TaskSplitter", "小队任务结束，已释放资源")
        self.push_log("TaskSplitter", "Agent销毁完成", "completed")

    # 10. 推送日志到UI
    def push_log(self, agent_name: str, content: str, status="running"):
        log_entry = {
            "agent": agent_name,
            "content": content,
            "status": status,
            "timestamp": time.time()
        }
        self.execution_log.append(log_entry)
        # 同时写入短期记忆
        self.stm.logs.append(log_entry)

    # 获取执行日志
    def get_execution_log(self):
        return self.execution_log

    # 清空执行日志
    def clear_execution_log(self):
        self.execution_log = []
