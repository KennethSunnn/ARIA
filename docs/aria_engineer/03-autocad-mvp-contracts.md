# AutoCAD MVP Contracts

Phase-1 scope is limited to three high-frequency flows.

## Flow A: Drawing parse and indexing

- Goal: parse a drawing package and produce structured metadata.
- Input contract:
  - `workspace_mode=aria_engineer_autocad`
  - file path(s) under workspace scope
  - optional project metadata (discipline/version)
- Output contract:
  - normalized document summary
  - layer/block index
  - parse warnings/errors

## Flow B: Annotation and layer suggestions

- Goal: suggest annotation consistency fixes and layer naming improvements.
- Input contract:
  - drawing summary/index from Flow A
  - project convention profile (if provided)
- Output contract:
  - suggestion list with severity (`info`, `warn`, `critical`)
  - optional patch plan draft (not auto-applied)
  - confidence and rationale per suggestion

## Flow C: Batch check report

- Goal: run batch quality checks and produce auditable reports.
- Input contract:
  - folder scope
  - selected checks (default: naming/layer/annotation consistency)
- Output contract:
  - JSON report for machine processing
  - human-readable summary for UI
  - per-file pass/fail and reason

## API-level payload additions

Request payload (`/api/process_input`) includes:

- `workspace_mode`: `aria` or `aria_engineer_autocad`

Response includes normalized:

- `workspace_mode`

## Safety policy for MVP

- No destructive write-back to CAD source files in phase-1.
- High-risk local actions are filtered by workspace mode allowlist.
- Every plan remains confirmation-gated before execution.
