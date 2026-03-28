# ====================== 配置文件 config.py ======================
# 全链路使用单一模型；实际模型 ID 以环境变量 MODEL_NAME 为准（未设置时用下方默认值）。
DEFAULT_MODEL = "doubao-seed-2-0-lite-260215"

MODEL_POOL = {
    "llm": DEFAULT_MODEL,
}

# UI显示名称（用户看到的友好名称）
AGENT_UI_NAMES = {
    "TaskParser": "任务解析器",
    "MethodSearcher": "方案匹配器",
    "SolutionLearner": "学习生成器",
    "TaskSplitter": "任务拆分器",
    "QualityChecker": "质量校验员",
    "MethodSaver": "方法论沉淀器",
    "TextExecAgent": "文本执行专家",
    "VisionExecAgent": "视觉解析专家",
    "SpeechExecAgent": "语音交互专家",
}
