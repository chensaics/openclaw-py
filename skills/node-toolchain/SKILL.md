---
skill_key: node-toolchain
description: Bridge Node/TypeScript skill workflows with controlled execution.
version: 1.0.0
runtime: node-wrapper
launcher: node-wrapper
security-level: elevated
deps: cmd:node, cmd:npm
install: npm install
capability: node-bridge, ts-tooling, dependency-audit
healthcheck: node --version
rollback: Disable node-wrapper skills and route to python-native alternatives.
---

# Node Toolchain

Use this skill for Node/TypeScript ecosystem tasks that are not yet native in Python.

## Safety guardrails

1. Prefer read-only checks before write operations.
2. Keep command scope within workspace.
3. Require explicit approval for high-risk commands.
4. Record command intent and outcome in logs.

## Typical tasks

- TypeScript build/lint/test orchestration
- JS package audit and dependency drift checks
- Compatibility probes for TS-based tooling
