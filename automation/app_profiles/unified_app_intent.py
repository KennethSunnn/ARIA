"""
统一的应用操作意图识别器。
"""

from __future__ import annotations

import re
from typing import Any


# 应用定义：每个应用的关键词、支持的操作类型
APP_REGISTRY = {
    "wechat": {
        "markers": ["微信", "wechat", "weixin"],
        "operations": {
            "send_message": {
                "keywords": ["发消息", "发信息", "发给", "私信", "告诉", "通知"],
                "patterns": [r"给\s*.{1,48}?\s*发"],
            },
            "open_chat": {
                "keywords": ["打开聊天", "打开对话", "打开会话"],
            },
            "check_login": {
                "keywords": ["是否登录", "登录了没", "登录状态"],
            },
        },
    },
    "wecom": {
        "markers": ["企业微信", "企微", "wecom"],
        "operations": {
            "send_message": {
                "keywords": ["发消息", "发信息", "发给"],
            },
        },
    },
    "xiaohongshu": {
        "markers": ["小红书", "xiaohongshu", "xhs"],
        "operations": {
            "post": {
                "keywords": ["发笔记", "发帖", "发布笔记", "发布帖子"],
            },
            "open": {
                "keywords": ["打开", "启动"],
            },
            "check_login": {
                "keywords": ["是否登录", "登录了没"],
            },
        },
    },
}


def detect_app_intent(text: str) -> dict[str, Any] | None:
    """
    统一检测应用操作意图。
    返回：{"app": "wechat", "operation": "send_message", "confidence": 0.9}
    或 None（无法识别）
    """
    t = (text or "").strip()
    if not t:
        return None

    tl = t.lower()

    # 第一步：识别目标应用
    detected_app = None
    for app_id, app_config in APP_REGISTRY.items():
        markers = app_config.get("markers", [])
        if any(m in t or m in tl for m in markers):
            detected_app = app_id
            break

    if not detected_app:
        return None

    # 第二步：识别操作类型
    app_config = APP_REGISTRY[detected_app]
    operations = app_config.get("operations", {})

    detected_operation = None
    max_confidence = 0.0

    for op_name, op_config in operations.items():
        confidence = 0.0
        keywords = op_config.get("keywords", [])
        patterns = op_config.get("patterns", [])

        # 关键词匹配
        for kw in keywords:
            if kw in t:
                confidence = max(confidence, 0.8)

        # 正则匹配
        for pattern in patterns:
            if re.search(pattern, t):
                confidence = max(confidence, 0.9)

        if confidence > max_confidence:
            max_confidence = confidence
            detected_operation = op_name

    # 如果只提到应用名，没有明确操作，默认为"打开"
    if not detected_operation:
        if "打开" in t or "启动" in t or "运行" in t:
            detected_operation = "open"
            max_confidence = 0.7

    if not detected_operation:
        return None

    return {
        "app": detected_app,
        "operation": detected_operation,
        "confidence": max_confidence,
        "raw_text": t,
    }
