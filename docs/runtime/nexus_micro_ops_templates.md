# ARIA NEXUS-Micro Ops Templates

This file defines reusable, ops-first NEXUS-Micro prompts for ARIA.

## 1) Incident Triage and Recovery

```text
Activate @agents-orchestrator in NEXUS-Micro mode for production incident handling.

Incident: <brief title>
Scope: <system/service/env>
Impact: <users/region/functions>

Team:
- @incident-response-commander (lead, severity + timeline)
- @infrastructure-maintainer (diagnosis + mitigation)
- @reality-checker (evidence-based gate)

Execution rules:
- Classify SEV level first, then start mitigation.
- Use 15-minute decision checkpoints.
- Max 3 retries per failing step, then escalate.
- Final output must include: timeline, root cause hypothesis, mitigation, rollback status, next actions.
```

## 2) Deployment Automation and Verification

```text
Activate @agents-orchestrator in NEXUS-Micro mode for release automation.

Release target: <service/version/branch>
Environment: <staging|prod>

Team:
- @devops-automator (pipeline + rollout)
- @testing-api-tester (endpoint checks)
- @reality-checker (release gate)

Execution rules:
- Define pre-flight checks before deployment.
- Deploy with rollback strategy and health probes.
- Require PASS from API checks and runtime health checks before completion.
- If FAIL, rollback immediately and report failed gate.
```

## 3) Performance Stabilization

```text
Activate @agents-orchestrator in NEXUS-Micro mode for performance remediation.

Problem statement: <latency/error/throughput signal>
Scope: <api/ui/database/infra>

Team:
- @testing-performance-benchmarker (baseline + bottlenecks)
- @infrastructure-maintainer (infra tuning)
- @devops-automator (safe rollout of fixes)

Execution rules:
- Capture baseline metrics first.
- Apply one optimization batch at a time.
- Verify metric delta after each batch.
- Stop when SLO target is met or 3 batches are exhausted.
```

## Minimal Completion Checklist

- A clear owner exists for each step.
- Every flow has explicit PASS/FAIL gates.
- Retry/rollback is defined before execution.
- Final report includes evidence and unresolved risks.

