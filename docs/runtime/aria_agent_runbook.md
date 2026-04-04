# ARIA Agent Runbook (Ops First)

This runbook standardizes how to invoke and validate multi-agent execution in ARIA.

## Enabled Cursor Rules

- `@agents-orchestrator`
- `@devops-automator`
- `@infrastructure-maintainer`
- `@incident-response-commander`
- `@testing-api-tester`
- `@testing-performance-benchmarker`
- `@reality-checker`

## Quick Start

1. Pick a template from `docs/runtime/nexus_micro_ops_templates.md`.
2. Fill scope/impact/target fields.
3. Run via `@agents-orchestrator`.
4. Require final gate from `@reality-checker`.

## Ops Scenarios

- **Incident handling**: commander -> infra -> reality gate
- **Release automation**: devops -> api tester -> reality gate
- **Performance stabilization**: benchmarker -> infra -> devops

## Escalation Policy

- Max 3 retries per failing step.
- If still failing, mark `blocked` and escalate with:
  - failing step
  - evidence
  - attempted mitigations
  - owner and ETA

## Acceptance Checklist

- At least one explicit PASS/FAIL gate result exists.
- Rollback path is defined for infra/release changes.
- Evidence includes deterministic checks (tests/status/metrics).
- Final output includes unresolved risks and next actions.

## Memory Usage Checklist

- At start: `recall` with `project + agent + task topic`.
- At key milestone: `remember` checkpoint with tags.
- Before handoff: `remember` pending work and constraints.
- On regression: `search` last known-good, then `rollback`.

