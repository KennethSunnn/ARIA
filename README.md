# ARIA - Autonomous Recursive Intelligent Agent

ARIA is an LLM-powered Autonomous Recursive Intelligent Agent that understands natural language instructions and automatically executes various tasks, including desktop operations, browser automation, messaging-channel delivery, file processing, and more.

## Recent Updates (2026-04-03)

- Added **Xiaohongshu (RED) Automation** (`automation/xiaohongshu_driver.py`): Publish image-text posts via web creator center using Playwright; supports title, content, cover image, and topic tags.
- Added **DeepSeek OCR Adapter** (`automation/deepseek_ocr_adapter.py`): VLM-powered intelligent OCR with context understanding, better accuracy for mixed Chinese-English text, and automatic noise filtering.
- Added **Execution Retry Policy** (`automation/execution_retry.py`): Smart fallback mechanism for failed tool executions, including fuzzy file path matching and alternative suggestions.
- Added **Unified App Intent Recognition** (`automation/app_profiles/unified_app_intent.py`): Centralized intent parser for WeChat, WeCom, Xiaohongshu, and other apps; replaces scattered heuristics modules.

## Previous Updates (2026-04-01)

- Added **Computer Use** tools (`computer_*` in `automation/computer_use.py`): screen-coordinate GUI aligned with Claude Computer Use; optional ReAct vision via JSON `react_computer_use_vision` or env `ARIA_REACT_COMPUTER_USE_VISION` (requires a vision-capable `MODEL_NAME`). Audit export: `GET /api/audit_export?conversation_id=...`.

- Implemented **ReAct** execution mode (Thought → Action → Observation loop): enable in the web UI (Settings) or send `react_mode: true` with `/api/process_input`; max steps via `ARIA_REACT_MAX_STEPS` (default 20).
- Added a clear action risk policy (`safe` / `medium` / `high`) and confirmation behavior.
- Added methodology health API endpoint: `GET /api/methodology_health`.
- Added regression benchmark script: `scripts/run_regression_benchmark.py`.
- Added regression report output path: `data/benchmarks/latest_regression_report.json`.
- Upgraded Experience Center to **Skills Hub** with recommended skills, inline health signals, and one-click reuse.
- Added hub APIs for aggregation, draft generation from recent successes, import pre-check, and event metrics.
- Added benchmark strict gate fields (`strict_pass_rate`, `strict_ok`) and CLI threshold checks.
- Workspace mode is simplified to a single `aria` mode; legacy engineer/autocad values are normalized to `aria`.
- Performance: optional `ARIA_UI_ANIMATION_SLEEP_MS`, smarter LLM retries (`ARIA_LLM_*`), ReAct JPEG quality env, SSE-aware workflow polling; see **Performance tuning** and `scripts/measure_process_input_perf.py`.
- Added runtime orchestration modules (`runtime/orchestration.py`, `runtime/scheduler.py`) with dependency-aware parallel scheduling (`ARIA_AGENT_MAX_PARALLEL`).
- Added MCP memory server (`memory/mcp_memory_server.py`) exposing `remember/search/recall/rollback` for cross-session memory workflows.

## Core Features

- 🤖 **Intelligent Task Parsing**: Automatically analyzes user requirements and breaks them down into executable subtasks
- 🖥️ **Desktop Automation**: Operates Windows desktop applications (WeChat, WPS, browsers, etc.)
- 🌐 **Browser Automation**: Real browser operations powered by Playwright
- 💬 **Messaging Automation**: Channel-based messaging actions (`messaging_*`) with adapter-driven execution (currently WeChat/WeCom)
- 📱 **Social Media Automation**: Xiaohongshu (RED) post publishing with image upload, title, content, and topic tags
- 📁 **File Processing**: Automatic file read/write, organization, and Office document parsing
- 🧠 **Methodology Learning**: Learns from successful tasks and builds a solution repository
- 🕸️ **Runtime Orchestration**: Dependency-aware multi-agent execution graph with bounded parallel scheduling
- 🧷 **MCP Memory Service**: FastMCP memory tools (`remember`, `search`, `recall`, `rollback`) for external memory integration
- 🧩 **Skills Hub**: Turns methodologies into reusable skill cards with recommendation and risk hints
- 🧪 **Harness Feedback Loop**: Uses benchmark/health signals to drive recommendation confidence
- 🔍 **OCR Screen Recognition**: Automatically recognizes screen content; supports Tesseract and VLM-powered (DeepSeek/Doubao-vision) intelligent OCR
- 📊 **Multimodal Support**: Image upload and understanding (requires vision-capable models)
- 🧱 **CAD Attachment Intake (MVP)**: Supports uploading `dxf`/`dwg`; `dxf` provides lightweight layer/entity summary, `dwg` provides capability hint

## System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                      Web UI (Flask)                      │
│                   templates/ + static/                   │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│                   ARIAManager (Commander)                │
│  - Task Parser                                           │
│  - Solution Learner                                      │
│  - Agent Creation & Scheduling                           │
│  - Memory System (STM/MTM/LTM)                           │
└─────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
┌───────────────┐  ┌───────────────┐  ┌───────────────┐
│  LLM Layer    │  │  Automation   │  │  Memory       │
│  Volcengine   │  │  - browser_*  │  │  - STM        │
│  Bailian/Ark  │  │  - desktop_*  │  │  - MTM        │
│               │  │  - messaging_*│  │  - LTM        │
│               │  │  - file_*     │  │  (Methodology)│
└───────────────┘  └───────────────┘  └───────────────┘
```

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Copy `.env.example` to `.env` and configure necessary parameters:

```bash
# Volcengine Ark (Recommended)
ARK_API_KEY=your_api_key_here
OPENAI_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
MODEL_NAME=doubao-seed-2-0-lite-260215

# Or Alibaba Cloud Bailian
# OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
# DASHSCOPE_API_KEY=your_api_key_here
```

### 3. Start the Application

**Option 1: Using batch file (Windows)**
```bash
aria.bat
```

**Option 2: Run Python directly**
```bash
python web_app.py
```

After startup, visit http://localhost:5000 to use the application.

## Performance tuning

Tune behavior with environment variables (see `.env.example`). Typical combinations for lower latency:

| Goal | Suggested knobs |
|------|-----------------|
| Less LLM depth | `REASONING_EFFORT_DEFAULT=low` or `minimal`; on DashScope, `ENABLE_THINKING=false` if compatible |
| Fail faster | `LLM_TIMEOUT_SECONDS=30`–`45` (raise if you see timeouts) |
| Shorter ReAct loops | `ARIA_REACT_MAX_STEPS=8`–`12` |
| Smaller vision payloads | Only enable `ARIA_REACT_COMPUTER_USE_VISION` when needed; `ARIA_REACT_COMPUTER_USE_JPEG_MAX=960`–`1280`; `ARIA_REACT_COMPUTER_USE_JPEG_QUALITY=60`–`75` |
| Less disk / capture work | Turn off `ARIA_ACTION_SCREENSHOT` and the UI “action screenshots” option when not debugging |
| Skip UI-only delays | Keep `ARIA_UI_ANIMATION_SLEEP_MS=0` (default) |
| LLM retries | `ARIA_LLM_MAX_RETRIES=2`, `ARIA_LLM_RETRY_SLEEP_BASE_MS=500`, `ARIA_LLM_RETRY_SLEEP_MAX_MS=4000` (retries only on timeouts, connection errors, 429, and 5xx) |

**Baseline metrics:** With `web_app.py` running, record full request time and `token_usage` via:

```bash
python scripts/measure_process_input_perf.py
python scripts/measure_process_input_perf.py --react
python scripts/measure_process_input_perf.py --react --react-vision
```

Use browser DevTools **Network** timing for **TTFB** on `/api/process_input`. A sample local run is committed under `data/benchmarks/perf_baseline_local_2026-04-01.json` (replace by your own runs as needed).

The web UI stops workflow **polling** while the **SSE** stream is connected and receiving events, and falls back to polling only when the stream errors.

## Project Structure

```
Aria/
├── aria_manager.py          # Core manager: task parsing, agent scheduling, memory system
├── web_app.py               # Flask web application: API endpoints and frontend routes
├── config.py                # Configuration: model pool and default parameters
├── method_lib.py            # Methodology library: solution storage and retrieval
├── conversation_lib.py      # Conversation library: dialogue history management
├── chat_attachments.py      # Attachment handling: file upload, OCR, summary extraction
├── requirements.txt         # Python dependencies
├── .env.example             # Environment variable template
│
├── automation/              # Automation execution layer
│   ├── browser_driver.py    # Browser automation (Playwright)
│   ├── computer_use.py      # Coordinate-level GUI operations (click/drag/type/screenshot)
│   ├── desktop_uia.py       # Desktop application automation (pywinauto)
│   ├── wechat_driver.py     # WeChat/WeCom adapter backend for messaging capability
│   ├── xiaohongshu_driver.py # Xiaohongshu (RED) browser automation for post publishing
│   ├── messaging_capability.py # Channel-agnostic messaging capability contract + adapter
│   ├── deepseek_ocr_adapter.py # VLM-powered intelligent OCR (DeepSeek/vision model)
│   ├── execution_retry.py   # Smart execution retry policy with fuzzy file path fallback
│   └── screen_ocr.py        # Screen OCR recognition
│
├── llm/                     # LLM inference layer
│   └── volcengine_llm.py    # Volcengine/Bailian API wrapper
│
├── memory/                  # Memory system
│   ├── memory_system.py     # Short-term/Mid-term/Long-term memory management
│   └── mcp_memory_server.py # MCP memory server (remember/search/recall/rollback)
│
├── runtime/                 # Runtime orchestration layer
│   ├── orchestration.py     # End-to-end pipeline facade
│   ├── scheduler.py         # Dependency-aware parallel scheduler
│   └── execution_graph.py   # Agent execution DAG builder
│
├── templates/               # HTML templates
│   ├── landing.html         # Landing page
│   └── simple_index.html    # Main interaction interface
│
├── static/                  # Static assets
│   ├── img/                 # Image resources
│   └── locales/             # Internationalization files
│       ├── en.json
│       └── zh.json
│
├── docs/runtime/            # Runtime operation docs
│   ├── aria_agent_runbook.md
│   ├── mcp_memory_integration.md
│   └── multi_agent_runtime_contract.md
│
└── data/                    # Data directory (generated at runtime)
    ├── methodology/         # Methodology library storage
    │   ├── methodologies.json
    │   └── ab_stats.json
    ├── benchmarks/
    │   └── latest_regression_report.json
    └── experience_center_metrics.json
```

## Core Components

### ARIAManager (Commander)

Core workflow:
1. **Task Parsing**: Understand user input, identify intent and key information
2. **Methodology Matching**: Retrieve similar solutions from long-term memory (reuse directly if similarity ≥ 0.7)
3. **Solution Learning**: Learn new solutions from external sources when no match exists (supports skipping to save tokens)
4. **Task Decomposition**: Break complex tasks into executable subtasks
5. **Agent Creation**: Create specialized agents for each subtask
6. **Execution Scheduling**: Coordinate agent execution and monitor progress
7. **Result Validation**: Verify execution results meet expectations
8. **Methodology Consolidation**: Save successful experiences to long-term memory

### Memory System

- **Short-Term Memory (STM)**: Current task context, execution state, logs
- **Mid-Term Memory (MTM)**: Task templates, agent combination patterns, common prompts
- **Long-Term Memory (LTM)**: Methodology library, best practice cases, knowledge base

### Automation Capabilities

| Capability | Module | Dependencies | Description |
|------------|--------|--------------|-------------|
| Browser Operations | `browser_*` | Playwright | Open pages, click, type, screenshot, etc. |
| Desktop Applications | `desktop_*` | pywinauto | Launch apps, window operations, UIA element recognition |
| Messaging Channels | `messaging_*` | - | Send messages via channel adapters (current: WeChat/WeCom) |
| File Operations | `file_*` | - | Read/write files, organize directories, Office document parsing |
| Screen Recognition | `screen_ocr` | pytesseract | OCR text recognition, screen content understanding |

## Configuration

### Environment Variables Reference

#### Required
- `ARK_API_KEY`: Volcengine Ark API key
- `OPENAI_BASE_URL`: API base URL
- `MODEL_NAME`: Model ID to use

#### Optional
- `REASONING_EFFORT_DEFAULT`: Default reasoning effort level (minimal/low/medium/high)
- `ARIA_REASONING_ROUTER`: Lightweight model router switch
- `ARIA_TEMPORAL_METHOD_MATCH_FLOOR`: Temporal task methodology matching threshold (default 0.45)
- `ARIA_DEFAULT_WORKSPACE_MODE`: Server default workspace mode (`aria`)
- `ARIA_PLAYWRIGHT`: Enable real browser automation (set to 1)
- `ARIA_DESKTOP_UIA`: Enable desktop shortcuts/input (set to 1)
- `ARIA_WECHAT_PREFER_DESKTOP`: Prefer desktop adapter path for WeChat/WeCom (set to 1)
- `ARIA_ACTION_SCREENSHOT`: Auto full-screen screenshot after actions (set to 1)
- `ARIA_REACT_MAX_STEPS`: Max ReAct iterations per execution session (default 20)
- `ARIA_AGENT_MAX_PARALLEL`: Max parallel agents in runtime scheduler (default 2)
- `ARIA_COMPUTER_USE`: Enable/disable computer-use coordinate actions (`1`/`0`)
- `ARIA_COMPUTER_USE_ALLOW_REGIONS`: Optional click/drag allowlist regions as JSON `[[left,top,width,height], ...]`
- `ARIA_COMPUTER_USE_BLOCK_TITLE_KEYWORDS`: Block mutating actions when foreground window title matches keywords

### Action Risk Policy (safe / medium / high)

- `safe`: auto execute directly
- `medium`: require one confirmation
- `high`: require double confirmation

Risk level is inferred from action plan + action type and is returned in action-plan responses.

### Reasoning Effort Levels

| Level | Use Case | Token Consumption |
|-------|----------|-------------------|
| minimal | Simple Q&A, greetings | Lowest |
| low | Information retrieval, simple tasks | Low |
| medium | Complex task planning, code generation | Medium |
| high | Deep reasoning, complex problem solving | High |

The system automatically selects the effort level based on task type, or you can specify it manually.

## API Endpoints

### Core Endpoints

- `POST /api/process_input`: Process user input (supports multipart forms and file uploads). Optional JSON/form field `react_mode` enables ReAct-style step-by-step execution after confirmation (see `.env.example` for `ARIA_REACT_MAX_STEPS`).
- `POST /api/confirm_actions`: Confirm action plan execution
- `POST /api/execution/start`: Start execution directly
- `POST /api/execution/pause`: Pause execution
- `POST /api/execution/resume`: Resume execution
- `POST /api/execution/abort`: Abort execution
- `GET /api/execution/status`: Query execution status
- `GET /api/workflow_stream`: SSE real-time workflow event streaming

### Conversation Management

- `POST /api/conversations`: Create new conversation
- `GET /api/conversations`: List conversations
- `GET /api/conversations/<id>`: Get conversation details
- `DELETE /api/conversations/<id>`: Delete conversation

### Methodology Management

- `GET /api/get_methodologies`: Get all methodologies
- `POST /api/search_methodology`: Search methodologies
- `POST /api/create_methodology`: Create methodology
- `POST /api/import_methodologies`: Import methodologies with pre-check
- `POST /api/update_methodology_category`: Update category
- `POST /api/delete_methodology`: Delete single methodology
- `POST /api/delete_methodologies_batch`: Batch delete
- `GET /api/methodology_health`: Methodology health dashboard (quality/AB stats)
- `GET /api/experience_hub_data`: Skills Hub aggregate data (recommended skills / alerts / regression snapshot)
- `GET /api/experience_recent_successes`: Recent successful conversations for draft generation
- `POST /api/create_skill_draft_from_recent`: Generate skill draft from recent success
- `POST /api/experience_metrics/event`: Record hub behavior metrics

## Usage Examples

### Example 1: Send Message via Channel

User input:
> Send a message to Zhang San on WeChat: Meeting tomorrow at 10 AM to discuss project progress

ARIA workflow:
1. Identify intent: Send message via channel
2. Extract information: Recipient=Zhang San, Content=Meeting tomorrow at 10 AM to discuss project progress
3. Call `messaging_send(channel="wechat", recipient="Zhang San", content="Meeting tomorrow at 10 AM to discuss project progress")`
4. Screenshot verification after execution (if configured)
5. Return execution result

### Example 2: Browser Operations

User input:
> Open Baidu, search for "Python tutorial", open the first result

ARIA workflow:
1. `browser_open("https://www.baidu.com")`
2. `browser_type("#kw", "Python tutorial")`
3. `browser_click("#su")`
4. Wait for search results, click first link
5. Return page title and summary

### Example 3: File Organization

User input:
> Move all PDF files from Downloads folder to "Documents/PDFs" directory

ARIA workflow:
1. Scan Downloads folder, identify all .pdf files
2. Create target directory (if not exists)
3. Move files one by one
4. Return move statistics

## Development Guide

### Harness Baseline

- `AGENTS.md`: runtime guardrails index (keep concise, directory style)
- `pyproject.toml`: unified lint/type/test config (`ruff` / `mypy` / `pytest`)
- `.pre-commit-config.yaml`: local hard checks before commits
- `.github/workflows/ci.yml`: lint + type + test + regression benchmark gate
- `.github/workflows/housekeeping.yml`: weekly drift and quality housekeeping

### Runtime Operations Docs

- `docs/runtime/aria_agent_runbook.md`: operations-first runbook for incident/release/perf scenarios
- `docs/runtime/multi_agent_runtime_contract.md`: multi-agent runtime contract and boundaries
- `docs/runtime/mcp_memory_integration.md`: MCP memory server integration and usage patterns

### Adding New Automation Capabilities

1. Create a new driver module in `automation/` directory
2. Add tool definition in `ARIAManager._build_agent_tool_definitions()` in `aria_manager.py`
3. Implement execution logic in `ARIAManager._execute_tool()`
4. Update documentation and test cases

### Adjusting Task Parsing Logic

Modify in `aria_manager.py`:
- `plan_actions()`: Task planning logic
- `parse_task()`: Task parsing logic
- `classify_interaction_mode()`: Interaction mode classification

### Optimizing Methodology Matching

Adjust in `memory/memory_system.py`:
- `search_similar_methodologies()`: Similarity calculation algorithm
- `CATEGORY_RULES` in `method_lib.py`: Classification rules

### Regression Benchmark

Use built-in benchmark tasks to validate planner coverage and risk-layer behavior:

```bash
python scripts/run_regression_benchmark.py
```

Optional quality gate:

```bash
python scripts/run_regression_benchmark.py --min-match-rate 0.6 --min-strict-pass-rate 0.5
```

Report is written to `data/benchmarks/latest_regression_report.json`.

### Skills Hub (Experience Center v2)

- Experience Center is upgraded to **Skills Hub**:
  - top recommended skills
  - inline quality + regression signals
  - one-click reuse / plan bootstrap
- New authoring workflow:
  - `New Method` creates a draft editor
  - `从最近成功任务生成草稿` bootstraps a draft from recent conversation outcomes
  - import supports JSON array pre-check (missing fields / duplicate event key)
- Product metrics file:
  - `data/experience_center_metrics.json`
  - tracks events such as tab open, reuse click, draft save, import, rollback

### Quick Verification Checklist

```bash
# 0) Install quality tools
pip install ruff mypy pytest pre-commit

# 0.1) Optional: enable local commit hooks
pre-commit install

# 1) Start web app
python web_app.py

# 2) Check hub aggregate API
curl http://localhost:5000/api/experience_hub_data

# 3) Run benchmark and enforce gate
python scripts/run_regression_benchmark.py --min-match-rate 0.6 --min-strict-pass-rate 0.5

# 4) ReAct API sanity check (requires running web_app.py)
python scripts/react_api_sanity_check.py --base-url http://127.0.0.1:5000

# 5) Weekly housekeeping (docs/rules/quality drift)
python scripts/harness_housekeeping.py --min-strict-pass-rate 0.6
```

## Important Notes

1. **API Key Security**: Do not commit `.env` file to version control
2. **Windows Dependencies**: Desktop automation and desktop messaging adapters are only available on Windows
3. **Browser Driver**: Run `playwright install chromium` to use Playwright
4. **OCR Accuracy**: pytesseract requires Tesseract-OCR engine installation
5. **Memory Management**: Consider periodically clearing memory cache for long-running services

## Tech Stack

- **Backend**: Python 3.8+, Flask
- **LLM**: Volcengine Ark / Alibaba Cloud Bailian
- **Browser Automation**: Playwright
- **Desktop Automation**: pywinauto, pyautogui
- **OCR**: pytesseract, Pillow
- **Document Parsing**: python-docx, openpyxl, python-pptx, pypdf

## License

This project is licensed under the MIT License.

Third-party notices and attributions are documented in `THIRD_PARTY_NOTICES.md`.
This includes the upstream `agency-agents` assets used for personality catalog integration.

## Contributing

Issues and Pull Requests are welcome!

## Contact

For questions or suggestions, please contact via:
- Submit a GitHub Issue
- Email: hcsun0411@gmail.com

**Author**: Haochen Sun

---

**Last Updated**: 2026-04-03
