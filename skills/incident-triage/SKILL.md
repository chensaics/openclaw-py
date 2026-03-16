---
skill_key: incident-triage
description: Incident triage workflow for production failures and degraded service.
version: 1.0.0
runtime: python-native
launcher: python-native
security-level: elevated
deps: py:json, py:datetime
capability: incident-triage, severity-assessment, mitigation-planning
healthcheck: python -c "import json,datetime; print('ok')"
rollback: Fall back to standard on-call runbook and manual triage.
---

# Incident Triage

Use this skill for outages, error spikes, or partial degradation.

## Triage flow

1. Classify severity (critical/high/medium/low).
2. Capture blast radius (users, channels, platforms).
3. Build a hypothesis tree from logs, metrics, and recent changes.
4. Propose immediate mitigations and safe rollback options.
5. Define verification signals and closure criteria.

## Response format

- Severity
- Impact summary
- Suspected causes
- Immediate actions
- Next diagnostics
