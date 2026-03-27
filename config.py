# ====================== 配置文件 config.py ======================
# 火山引擎模型池（固定不可修改）
MODEL_POOL = {
    "router": "volcano-router",       # 路由决策：任务分类、选Agent、分配模型
    "llm": "volcano-chat",            # 语言模型：思考、生成、写作、推理
    "embedding": "volcano-embedding", # 向量模型：方法论匹配、相似度检索
    "vision": "volcano-vision",       # 视觉模型：看图、解析图表、识别
    "speech": "volcano-speech",       # 语音模型：语音转文字、播报
}

# 动态Agent模板 + 绑定使用的模型（唯一依据）
AGENT_TEMPLATES = {
    # 核心流程Agent
    "TaskParser":       ["router", "embedding"],   # 任务解析器
    "MethodSearcher":   ["embedding"],             # 方案匹配器
    "SolutionLearner":  ["llm"],                   # 学习生成器
    "TaskSplitter":     ["router", "llm"],         # 任务拆分器
    "QualityChecker":   ["llm", "embedding"],      # 质量校验员
    "MethodSaver":      ["embedding", "llm"],      # 方法论沉淀器

    # 执行类动态Agent
    "TextExecAgent":    ["llm"],                   # 文本执行专家
    "VisionExecAgent":  ["vision", "llm"],         # 视觉解析专家
    "SpeechExecAgent":  ["speech", "llm"],         # 语音交互专家
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
