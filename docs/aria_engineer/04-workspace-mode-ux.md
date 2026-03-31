# Workspace/Mode UX Specification

## Objective

Keep ARIA and ARIA Engineer connected by identity and core capabilities, while making domain context explicit at all times.

## UI behavior

- Settings panel includes `Workspace Mode` selector:
  - `ARIA (General Assistant)`
  - `ARIA Engineer (AutoCAD)`
- Top navigation displays current mode badge.
- Selected mode is persisted in local storage and sent on each request.

## Request/response behavior

- Frontend sends `workspace_mode` in both JSON and multipart requests.
- Backend normalizes aliases (`engineer`, `autocad`) to `aria_engineer_autocad`.
- Backend returns normalized `workspace_mode`; frontend syncs selector + badge.

## UX guardrails

- Mode switch is explicit and reversible in one click.
- Planning behavior changes without requiring a separate login/app.
- Users always see the current mode to reduce cross-domain mistakes.
