# ARIA Multi-Agent Runtime Contract

This document freezes the orchestration baseline before and during the core rewrite.

## API Compatibility

- Input endpoint stays at `POST /api/process_input`.
- Execution control endpoints stay unchanged under `/api/execution/*`.
- Streaming endpoint stays at `GET /api/workflow_stream`.

## Runtime Pipeline Contract

The runtime facade executes this logical sequence:

1. `split_sub_tasks(task_info, method)`
2. `create_agents(sub_tasks)`
3. `build_execution_graph(agents)`
4. `AgentScheduler.run(...)`
5. `check_result(results)`
6. caller invokes `save_methodology(...)`
7. caller invokes `destroy_agents(...)`

For action execution sessions (`batch` and `react`), ARIA uses an autonomy loop per action:

1. execute one action attempt
2. verify result (deterministic checks when available)
3. classify state (`success`, `verify_failed`, `recoverable_error`, `hard_error`, `cancelled`)
4. apply bounded recovery policy (`retry_scheduled:*` or `manual_takeover_required:*`)
5. append loop trace row (`loop_step_id`, `attempt`, `outcome_state`, `recovery_decision`)

## Data Contract

- `sub_task` requires `sub_task_id`, `task_id`, `step`, `description`, `agent_type`.
- `sub_task.depends_on` is normalized to a list.
- `agent` payload remains dictionary-shaped for backward compatibility:
  - `agent_id`
  - `agent_type`
  - `task`
  - `persona_brief`
  - `agent_name`

- Action loop row keeps backward-compatible fields (`status`, `error_code`, `stdout`, etc.) and adds:
  - `loop_step_id`
  - `attempt`
  - `max_attempts`
  - `outcome_state`
  - `recovery_decision`

## Event Contract

`push_event(...)` remains the single event source for timeline and SSE sinks. The event payload must include:

- `conversation_id`
- `task_id`
- `stage`
- `status`
- `agent_code`
- `summary`

Scheduler implementations should emit `runtime_scheduler` start/finish events with node metadata
(`node_id`, `elapsed_ms`, queue/in-flight counters) without breaking existing consumers.

Any scheduler or agent implementation must emit state transitions through `push_event` to preserve UI behavior.
