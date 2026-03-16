---
skill_key: channel-ops
description: Channel policy checks, routing validation, and delivery diagnostics.
version: 1.0.0
runtime: python-native
launcher: python-native
security-level: standard
deps: py:json
capability: channel-audit, routing-diagnostics, delivery-analysis
healthcheck: python -c "import json; print('ok')"
rollback: Disable channel-ops execution and use static troubleshooting docs.
---

# Channel Ops

Use this skill when channel behavior is inconsistent across platforms.

## Validation checklist

1. DM/group policy alignment (`dmPolicy`, `groupPolicy`, `allowFrom`).
2. Routing correctness (binding and session scope).
3. Message formatting fallback behavior by channel capability.
4. Delivery queue retry/dead-letter symptoms.
5. Typing/reaction/action support mismatch.

## Deliverable

- A per-channel issue table:
  - symptom
  - likely config/code cause
  - fix proposal
