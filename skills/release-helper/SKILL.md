---
skill_key: release-helper
description: Release readiness checklist, changelog quality, and rollback notes.
version: 1.0.0
runtime: python-native
launcher: python-native
security-level: elevated
deps: cmd:git
install: pip install -e ".[dev]"
capability: release-gate, changelog-check, rollback-prep
healthcheck: git --version
rollback: Skip release-helper automation and use manual release checklist.
---

# Release Helper

Use this skill before tagging or publishing a release.

## Release gate

1. Verify working tree cleanliness expectations.
2. Validate tests for touched critical modules.
3. Check changelog completeness and user-facing impact notes.
4. Ensure migration/breaking-change notes exist when needed.
5. Prepare rollback instructions and known-risk notes.

## Output

- Release checklist status (pass/fail).
- Blocking items with owners and quick remediation path.
