"""应用能力扩展框架 — 让任意应用以插件方式接入 ARIA。

核心组件：
- Application: 应用接口协议
- Capability: 能力描述数据类
- AppIntent: 意图识别结果
- ApplicationRegistry: 应用注册表
"""

from .application import Application
from .capability import Capability, CapabilityParameter
from .intent import AppIntent
from .registry import ApplicationRegistry

__all__ = [
    "Application",
    "Capability",
    "CapabilityParameter",
    "AppIntent",
    "ApplicationRegistry",
]
