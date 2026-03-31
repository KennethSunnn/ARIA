# ARIA Engineer Boundaries (AutoCAD First)

This document defines what is shared with ARIA and what is isolated for ARIA Engineer.

## Shared platform capabilities

- Account/conversation identity and session model
- LLM routing and reasoning effort controls
- Methodology memory, benchmark and quality metrics pipeline
- Execution timeline, logs, and risk confirmation flow

## Isolated product capabilities

- Product entry and workspace mode (`aria` vs `aria_engineer_autocad`)
- Domain prompts, terminology, and artifact templates
- Tool allowlist policies by workspace mode
- Domain-specific success metrics and release gates

## Workspace mode contract

- `aria`: full general-purpose ARIA behavior
- `aria_engineer_autocad`: engineering-first behavior for AutoCAD workflows

Current `aria_engineer_autocad` policy focuses on CAD-safe actions:

- allow: `desktop_open_app`, `file_write`, `file_move`, `screen_ocr`, `screen_find_text`, `screen_click_text`, `browser_open`, `browser_find`, `browser_wait`, `web_fetch`, `web_understand`, `media_summarize`
- block by default: social/messaging tools (`wechat_*`), high-risk local injection (`shell_run`, `desktop_hotkey`, `desktop_type`, `desktop_sequence`) and broad destructive actions (`file_delete`, `kb_delete_*`)

## Why this boundary design

- Keep UX unified: one ARIA platform and conversation model
- Keep domain behavior explicit: workspace mode is visible and enforceable
- Reduce accidental cross-domain actions while AutoCAD workflows are still maturing
