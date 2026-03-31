# Monorepo Migration Map (ARIA + ARIA Engineer)

Target architecture keeps one repository with explicit product/domain boundaries.

## Target folder layout

```text
apps/
  aria-main/                  # existing ARIA product entry
  aria-engineer/              # engineering product entry
packages/
  core-runtime/               # planner, execution, risk, memory glue
  shared-ui/                  # reusable UI components and i18n shell
  domain-engineering/         # engineering prompts, policies, templates
  integrations-autocad/       # AutoCAD adapters, parsers, validators
services/
  api-gateway/                # optional split for API assembly
```

## Mapping from current codebase

- `aria_manager.py` -> phase-wise extract into `packages/core-runtime/`
- `web_app.py` + `templates/` + `static/` -> first become `apps/aria-main/` source of truth
- AutoCAD-specific logic (new) -> `packages/integrations-autocad/` and `packages/domain-engineering/`
- existing regression + housekeeping scripts remain shared and run against both product profiles

## Step-by-step migration strategy

1. Keep current runtime intact, add workspace mode and domain allowlist first (done in this phase).
2. Introduce `docs/` and stable contracts before moving Python modules.
3. Split UI entry later into `aria-main` and `aria-engineer` routes with shared components.
4. Extract runtime internals into package folders when team and release cadence require it.

## Exit criteria for physical split

Move from monorepo to hybrid (`core` + separate app repos) only when:

- Engineer product has independent release train for at least 2 consecutive iterations.
- Core dependency changes become a frequent cross-team bottleneck.
- CI and ownership model justify separate branch protection and deployment gates.
