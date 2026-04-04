# ARIA 应用开发指南

本指南介绍如何为 ARIA 开发自定义应用插件，让任意桌面/Web 应用以统一方式接入。

## 快速开始

### 1. 创建应用类

在 `automation/apps/` 或自定义目录下创建应用类，实现 `Application` 接口：

```python
from automation.app_framework import Application, Capability, CapabilityParameter, AppIntent

class MyCustomApplication:
    """我的自定义应用插件。"""

    @property
    def app_id(self) -> str:
        return "my_app"  # 全局唯一标识

    @property
    def app_name(self) -> str:
        return "我的应用"

    @property
    def capabilities(self) -> list[Capability]:
        return [
            Capability(
                action_type="my_app_action",
                display_name="执行操作",
                description="在我的应用中执行某个操作",
                parameters=(
                    CapabilityParameter("target", "目标", "string", description="操作目标"),
                    CapabilityParameter("value", "值", "string", required=False),
                ),
                risk_level="medium",
                requires_confirmation=True,
            ),
        ]

    def detect_intent(self, text: str) -> AppIntent | None:
        """从用户输入中检测意图。"""
        if "我的应用" not in text:
            return None
        # 简单关键词匹配示例
        if "执行" in text:
            return AppIntent(
                app_id=self.app_id,
                operation="my_app_action",
                confidence=0.8,
                extracted_params={"target": "默认目标"},
                raw_text=text,
            )
        return None

    def execute(self, action_type: str, params: dict, *, cancel_checker=None) -> dict:
        """执行应用能力。"""
        if action_type == "my_app_action":
            target = params.get("target", "")
            # 在这里实现实际的应用操作逻辑
            return {"success": True, "stdout": f"已在我的应用中操作：{target}"}
        return {"success": False, "error": f"不支持的动作：{action_type}"}

    def get_planner_hint(self) -> str:
        """返回给 LLM 规划器的提示文本。"""
        return f"【{self.app_name}】支持 my_app_action 操作"
```

### 2. 注册应用

#### 方式 A：代码注册（推荐用于内置应用）

在 `aria_manager.py` 的 `__init__` 方法中：

```python
from automation.apps.my_app import MyCustomApplication
self.app_registry.register(MyCustomApplication())
```

#### 方式 B：配置文件注册（推荐用于第三方应用）

在 `config/applications.yaml` 中添加：

```yaml
applications:
  - module: automation.apps.my_app
    class: MyCustomApplication
    enabled: true
```

### 3. 测试应用

```python
from automation.app_framework import ApplicationRegistry
from automation.apps.my_app import MyCustomApplication

reg = ApplicationRegistry()
reg.register(MyCustomApplication())

# 测试意图识别
result = reg.detect_intent("在我的应用中执行操作")
if result:
    app, intent = result
    print(f"识别到：{app.app_id}.{intent.operation}")

# 测试执行
app = reg.get_app("my_app")
result = app.execute("my_app_action", {"target": "测试目标"})
print(result)
```

## 核心接口说明

### Application 接口

所有应用必须实现以下属性和方法：

- `app_id`: 应用唯一标识（字符串）
- `app_name`: 应用显示名称
- `capabilities`: 能力列表（`list[Capability]`）
- `detect_intent(text)`: 意图识别，返回 `AppIntent | None`
- `execute(action_type, params, cancel_checker)`: 执行能力，返回结果字典
- `get_planner_hint()`: 返回给 LLM 的提示文本

### Capability 数据类

描述应用的一个可执行能力：

- `action_type`: 动作类型标识（全局唯一）
- `display_name`: 用户可见名称
- `description`: 功能描述
- `parameters`: 参数列表（`tuple[CapabilityParameter, ...]`）
- `risk_level`: 风险级别（`'safe'` | `'medium'` | `'high'`）
- `requires_confirmation`: 是否需要用户确认

### AppIntent 数据类

意图识别结果：

- `app_id`: 应用 ID
- `operation`: 操作类型（通常对应 action_type）
- `confidence`: 置信度（0.0–1.0，≥0.7 为高置信度）
- `extracted_params`: 从用户输入中提取的参数
- `raw_text`: 原始用户输入

## 最佳实践

### 1. 意图识别

- 使用关键词匹配 + 正则表达式提取参数
- 置信度 ≥ 0.7 时会跳过 LLM 二次规划，直接执行
- 置信度 < 0.7 时会交给 LLM 补全参数

### 2. 参数验证

使用 `Capability.validate_params()` 验证参数：

```python
cap = Capability(...)
ok, msg = cap.validate_params(params)
if not ok:
    return {"success": False, "error": msg}
```

### 3. 错误处理

执行结果必须包含 `success` 字段：

```python
# 成功
return {"success": True, "stdout": "操作完成"}

# 失败
return {"success": False, "error": "错误原因", "stderr": "详细错误"}
```

### 4. 取消检查

长时间运行的操作应定期检查取消：

```python
def execute(self, action_type, params, *, cancel_checker=None):
    for i in range(100):
        if cancel_checker:
            cancel_checker("my_app_action")  # 如果用户取消会抛出异常
        # 执行操作...
```

## 示例：浏览器应用

参考 `automation/apps/wechat.py` 和 `automation/apps/xiaohongshu.py` 的完整实现。

## API 端点

- `GET /api/applications` - 列出所有已注册应用
- `GET /api/applications/<app_id>/capabilities` - 查看应用能力

## 常见问题

### Q: action_type 冲突怎么办？

A: 每个 action_type 必须全局唯一。建议使用 `{app_id}_{operation}` 格式，如 `my_app_send`。

### Q: 如何调试意图识别？

A: 使用 `ApplicationRegistry.detect_intent()` 单独测试：

```python
result = registry.detect_intent("用户输入")
if result:
    app, intent = result
    print(f"置信度：{intent.confidence}")
    print(f"提取参数：{intent.extracted_params}")
```

### Q: 如何与现有驱动集成？

A: 在 `execute()` 方法中调用现有驱动代码：

```python
def execute(self, action_type, params, *, cancel_checker=None):
    from automation import my_existing_driver
    return my_existing_driver.do_something(params)
```

## 下一步

- 查看 `automation/app_framework/` 了解框架实现
- 参考 `automation/apps/wechat.py` 学习完整示例
- 运行 `python scripts/run_regression_benchmark.py` 验证兼容性
