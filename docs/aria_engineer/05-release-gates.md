# Release Gates for ARIA + ARIA Engineer

## Shared mandatory gates

- `ruff`, `mypy`, `pytest` pass
- regression benchmark runs and publishes report
- housekeeping checks pass for docs/rules drift

## ARIA Engineer additional gates

- workspace mode allowlist test coverage (must verify blocked actions are filtered)
- mode roundtrip check (`workspace_mode` request -> normalized response)
- manual smoke on three AutoCAD MVP flows:
  - parse/index
  - suggestion generation
  - batch report output

## Promotion criteria

- No high-severity safety regressions in action filtering
- No cross-mode ambiguity in UI badge/selector
- Benchmark strict pass rate not below team threshold

## Rollback trigger examples

- blocked actions unexpectedly executable in engineer mode
- mode label inconsistent with backend policy
- repeated benchmark failures or quality drift alerts
