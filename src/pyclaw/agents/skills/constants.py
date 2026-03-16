"""Shared constants for skills runtime and diagnostics."""

from __future__ import annotations

# Generic status values
STATUS_OK = "ok"
STATUS_NEEDS_ATTENTION = "needs_attention"
STATUS_INVALID = "invalid"

# Skill keys
SKILL_OFFICE_READER = "office-reader"
SKILL_REPO_REVIEW = "repo-review"
SKILL_DOCS_SYNC = "docs-sync"
SKILL_INCIDENT_TRIAGE = "incident-triage"
SKILL_CHANNEL_OPS = "channel-ops"
SKILL_RELEASE_HELPER = "release-helper"
SKILL_NODE_TOOLCHAIN = "node-toolchain"
SKILL_MCP_ADMIN = "mcp-admin"
SKILL_CLAW_REDBOOK_AUTO = "claw-redbook-auto"

# Alias mapping
# `office-reader` is a logical alias and currently routes to the `pdf` skill entry.
SKILL_ALIAS_OFFICE_READER = "office-reader"
SKILL_ALIAS_OFFICE_FORMAT = "pdf"

# Multi-format office reader support
OFFICE_SKILLS = frozenset({"pdf", "docx", "xlsx", "pptx"})

# Docs-sync defaults
DEFAULT_DOCS_SCOPE = "docs/configuration.md"
DOCS_ENV_TABLE_MARKER = "### 核心变量"
DOCS_TOP_LEVEL_MARKER = "## 顶层配置节一览"
DOCS_CHECKS = (
    "config_keys_alignment",
    "env_vars_alignment",
    "cli_examples_alignment",
    "broken_or_stale_paths",
)
DOCS_CATEGORY_PRESENCE = "docs_presence"
DOCS_LOCATION_CONFIG = "docs/configuration.md"
DOCS_LOCATION_TOP_LEVEL = "docs/configuration.md#顶层配置节一览"
DOCS_LOCATION_ENV = "docs/configuration.md#核心变量"

# Release helper gate checks
RELEASE_CHECK_WORKTREE_CLEAN = "working_tree_clean"
RELEASE_CHECK_CRITICAL_TEST_PLAN = "critical_changes_test_plan"
RELEASE_CHECK_NOTES_PRESENT = "release_notes_present"
RELEASE_CHECK_BREAKING_NOTES = "breaking_change_notes"
RELEASE_CHECK_ROLLBACK_NOTES = "rollback_notes_present"

CRITICAL_PATH_PREFIXES = (
    "src/pyclaw/gateway/",
    "src/pyclaw/agents/",
    "src/pyclaw/cli/",
    "src/pyclaw/config/",
)

# Node toolchain
NODE_LOCKFILES = ("package-lock.json", "pnpm-lock.yaml", "yarn.lock")
NODE_PM_NPM = "npm"
NODE_PM_PNPM = "pnpm"
NODE_PM_YARN = "yarn"
NODE_BLOCKER_MISSING_NODE = "node_missing"
NODE_BLOCKER_MISSING_NPM = "npm_missing"

# MCP admin
MCP_TRANSPORT_STDIO = "stdio"
MCP_TRANSPORT_HTTP = "http"
MCP_TRANSPORT_UNKNOWN = "unknown"
MCP_ISSUE_SERVER_CONFIG_NOT_OBJECT = "server_config_not_object"
MCP_ISSUE_MISSING_COMMAND = "missing_command"
MCP_ISSUE_COMMAND_NOT_FOUND = "command_not_found"
MCP_ISSUE_ARGS_NOT_LIST = "args_must_be_list"
MCP_ISSUE_INVALID_URL = "invalid_url"
MCP_ISSUE_MISSING_TRANSPORT = "missing_transport"
