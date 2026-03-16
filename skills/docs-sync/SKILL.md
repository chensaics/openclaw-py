---
skill_key: docs-sync
description: Keep documentation and implementation contracts aligned.
version: 1.0.0
runtime: python-native
launcher: python-native
security-level: standard
deps: py:json, py:re
capability: docs-audit, contract-drift-detection
healthcheck: python -c "import json,re; print('ok')"
rollback: Revert to manual docs parity checklist.
---

# Docs Sync

Use this skill to detect and reduce drift between docs and implementation.

## Checklist

1. Confirm config keys in docs exist in schema/code.
2. Confirm RPC method names and params are consistent.
3. Confirm CLI examples map to actual command flags.
4. Flag stale paths, renamed files, or broken references.

## Deliverable

- A concise delta list with:
  - doc location
  - implementation location
  - proposed correction
