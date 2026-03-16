---
skill_key: repo-review
description: Code review checklist for regressions, risks, and tests.
version: 1.0.0
runtime: python-native
launcher: python-native
security-level: standard
deps: py:json
capability: review, regression-detection, risk-ranking
healthcheck: python -c "import json; print('ok')"
rollback: Disable skill in skill filter and fall back to manual review checklist.
---

# Repo Review

Use this skill when the user asks for a review or when a risky change needs a focused quality pass.

## Review focus order

1. Behavioral regressions
2. Security and data-safety risks
3. Concurrency/performance side effects
4. Error handling and fallback paths
5. Missing tests and observability gaps

## Output format

- Findings first, ordered by severity.
- Keep each finding actionable (what breaks, why, and where).
- Mention residual risks when no critical issues are found.
