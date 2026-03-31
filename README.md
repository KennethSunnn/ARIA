# ARIA - Autonomous Recursive Intelligent Agent

ARIA is an LLM-powered Autonomous Recursive Intelligent Agent that understands natural language instructions and automatically executes various tasks, including desktop operations, browser automation, WeChat messaging, file processing, and more.

## Recent Updates (2026-03-31)

- Implemented **ReAct** execution mode (Thought → Action → Observation loop): enable in the web UI (Settings) or send `react_mode: true` with `/api/process_input`; max steps via `ARIA_REACT_MAX_STEPS` (default 20).
- Added a clear action risk policy (`safe` / `medium` / `high`) and confirmation behavior.
- Added methodology health API endpoint: `GET /api/methodology_health`.
- Added regression benchmark script: `scripts/run_regression_benchmark.py`.
- Added regression report output path: `data/benchmarks/latest_regression_report.json`.
- Upgraded Experience Center to **Skills Hub** with recommended skills, inline health signals, and one-click reuse.
- Added hub APIs for aggregation, draft generation from recent successes, import pre-check, and event metrics.
- Added benchmark strict gate fields (`strict_pass_rate`, `strict_ok`) and CLI threshold checks.
- Added workspace mode support for product/domain isolation: `aria` and `aria_engineer_autocad`.
- Added ARIA Engineer (AutoCAD-first) implementation docs under `docs/aria_engineer/`.

## Core Features

- 🤖 **Intelligent Task Parsing**: Automatically analyzes user requirements and breaks them down into executable subtasks
- 🖥️ **Desktop Automation**: Operates Windows desktop applications (WeChat, WPS, browsers, etc.)
- 🌐 **Browser Automation**: Real browser operations powered by Playwright
- 💬 **WeChat Automation**: Supports both desktop client and web version for sending messages
- 📁 **File Processing**: Automatic file read/write, organization, and Office document parsing
- 🧠 **Methodology Learning**: Learns from successful tasks and builds a solution repository
- 🧩 **Skills Hub**: Turns methodologies into reusable skill cards with recommendation and risk hints
- 🧪 **Harness Feedback Loop**: Uses benchmark/health signals to drive recommendation confidence
- 🔍 **OCR Screen Recognition**: Automatically recognizes screen content for intelligent operations
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
│               │  │  - wechat_*   │  │  - LTM        │
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
│   ├── desktop_uia.py       # Desktop application automation (pywinauto)
│   ├── wechat_driver.py     # WeChat automation
│   └── screen_ocr.py        # Screen OCR recognition
│
├── llm/                     # LLM inference layer
│   └── volcengine_llm.py    # Volcengine/Bailian API wrapper
│
├── memory/                  # Memory system
│   └── memory_system.py     # Short-term/Mid-term/Long-term memory management
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
| WeChat Messaging | `wechat_*` | - | Send messages to contacts/groups (desktop client preferred) |
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
- `ARIA_DEFAULT_WORKSPACE_MODE`: Server default workspace mode (`aria` / `aria_engineer_autocad`)
- `ARIA_PLAYWRIGHT`: Enable real browser automation (set to 1)
- `ARIA_DESKTOP_UIA`: Enable desktop shortcuts/input (set to 1)
- `ARIA_WECHAT_PREFER_DESKTOP`: Prefer desktop WeChat client (set to 1)
- `ARIA_ACTION_SCREENSHOT`: Auto full-screen screenshot after actions (set to 1)
- `ARIA_REACT_MAX_STEPS`: Max ReAct iterations per execution session (default 20)

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

### Example 1: Send WeChat Message

User input:
> Send WeChat message to Zhang San: Meeting tomorrow at 10 AM to discuss project progress

ARIA workflow:
1. Identify intent: Send WeChat message
2. Extract information: Recipient=Zhang San, Content=Meeting tomorrow at 10 AM to discuss project progress
3. Call `wechat_send_message("Zhang San", "Meeting tomorrow at 10 AM to discuss project progress")`
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

### ARIA Engineer (AutoCAD First)

- Boundaries and allowlist: `docs/aria_engineer/01-boundaries-and-allowlist.md`
- Monorepo migration map: `docs/aria_engineer/02-monorepo-migration-map.md`
- AutoCAD MVP contracts: `docs/aria_engineer/03-autocad-mvp-contracts.md`
- Workspace mode UX: `docs/aria_engineer/04-workspace-mode-ux.md`
- Release gates: `docs/aria_engineer/05-release-gates.md`

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
2. **Windows Dependencies**: Desktop automation and WeChat features are only available on Windows
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

## Contributing

Issues and Pull Requests are welcome!

## Contact

For questions or suggestions, please contact via:
- Submit a GitHub Issue
- Email: hcsun0411@gmail.com

**Author**: Haochen Sun

---

**Last Updated**: 2026-03-31
