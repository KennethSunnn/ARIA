# ARIA 智能助手

Adaptive Resilient Intelligence Architecture (ARIA) - 一个具备三级记忆系统、知识库管理、多智能体协作和Web界面的智能助手系统。

## 核心特性

- **三级记忆系统**：短期记忆（STM）、中期记忆（MTM）、长期记忆（LTM）
- **知识库管理**：支持点击查看知识库完整内容，包含相似度检测和去重机制
- **多智能体协作**：支持多种类型智能体的协作，包括数据分析专家、文案策划师、开发工程师等
- **Web界面**：直观的用户界面，支持任务执行、记忆管理和方法论库管理
- **API集成**：使用火山引擎官方SDK调用Doubao模型
- **记忆调用流程**：任务解析→方案匹配→任务拆分→执行→结果沉淀
- **方法论管理**：包括添加、更新、查询、删除、导入/导出等功能
- **标准化知识库结构**：场景、关键词、解决步骤、适用范围、使用次数、时间

## 安装步骤

1. **克隆项目**
   ```bash
   git clone <repository-url>
   cd Aria
   ```

2. **创建虚拟环境**
   ```bash
   python -m venv .venv
   # Windows
   .venv\Scripts\activate
   # Linux/Mac
   source .venv/bin/activate
   ```

3. **安装依赖**
   ```bash
   pip install -r requirements.txt
   # 安装火山引擎官方SDK
   pip install 'volcengine-python-sdk[ark]'
   ```

4. **配置环境变量**
   - 复制仓库中的 `.env.example` 为 `.env`（**不要将 `.env` 提交到 Git**）
   - 在 `.env` 中填写你在火山引擎控制台申请的密钥，例如：
     ```
     VOLCANO_API_KEY=your-api-key-here
     ```
   - 也可仅通过系统环境变量设置 `VOLCANO_API_KEY`（与 `.env` 二选一或同时存在均可，以你运行进程时的环境为准）。

**安全提示**：若你曾在仓库里提交过真实密钥，请在服务商控制台**轮换/作废**旧密钥，再使用新密钥。

## 运行方式

### 方法1：使用HTML启动器
- 双击 `启动Aria.html` 文件
- 点击"启动Aria"按钮
- 浏览器会自动打开Web界面

### 方法2：直接运行 Python
```bash
python web_app.py
```

## 核心模块

- `web_app.py`：Flask Web应用，提供API接口和前端服务
- `aria_manager.py`：ARIA管理器，整合所有功能
- `method_lib.py`：方法论库管理，实现方法论的添加、更新、查询等功能
- `memory/memory_system.py`：三级记忆系统，实现短期、中期、长期记忆的管理
- `templates/simple_index.html`：Web界面模板
- `.env.example`：环境变量模板；本地复制为 `.env` 并填写密钥（`.env` 已在 `.gitignore` 中忽略）

## 技术栈

- **模型层**：火山引擎Doubao模型
- **API客户端**：volcenginesdkarkruntime
- **Web框架**：Flask
- **前端**：HTML、CSS、JavaScript、Bootstrap
- **记忆系统**：本地文件存储

## 三级记忆系统

- **短期记忆（STM）**：任务执行过程中的临时记忆，包括用户输入、子任务、执行状态等
- **中期记忆（MTM）**：任务模板和执行流程，用于快速匹配相似任务
- **长期记忆（LTM）**：方法论和知识库，包含场景、步骤、关键词等结构化信息

## 知识库改进

- **相似度检测**：基于关键词匹配和向量检索实现重复内容识别，相似度≥70%禁止创建新条目
- **标准化结构**：包含场景、关键词、解决步骤、适用范围、使用次数、时间等字段
- **方法论覆盖/更新机制**：当创建相似方法论时，自动更新已有条目
- **UI界面优化**：支持知识库列表+详情展示，点击查看完整内容

## 注意事项

1. 确保已在火山引擎控制台激活相应模型
2. 确保已通过 `.env` 或系统环境变量正确配置 `VOLCANO_API_KEY`
3. 首次运行时可能需要安装依赖包，耐心等待安装完成
4. Web界面默认运行在 `http://127.0.0.1:5000`

## 故障排除

- **API 调用失败**：检查 `VOLCANO_API_KEY` / 网络 / 控制台模型权限
- **模型访问权限**：确保已在火山引擎控制台激活相应模型
- **依赖安装问题**：使用 `pip install` 命令安装缺失的依赖包
- **端口冲突**：如果5000端口被占用，修改 `web_app.py` 中的端口配置
- **UI界面混乱**：确保浏览器缓存已清除，或者尝试使用隐私模式打开