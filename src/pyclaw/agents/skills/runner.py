"""Skill runtime entrypoints for bundled skills."""

from __future__ import annotations

import importlib.util
import inspect
import json
import re
import shlex
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pyclaw.agents.skills.constants import (
    CRITICAL_PATH_PREFIXES,
    DEFAULT_DOCS_SCOPE,
    DOCS_CATEGORY_PRESENCE,
    DOCS_CHECKS,
    DOCS_ENV_TABLE_MARKER,
    DOCS_LOCATION_CONFIG,
    DOCS_LOCATION_ENV,
    DOCS_LOCATION_TOP_LEVEL,
    DOCS_TOP_LEVEL_MARKER,
    MCP_ISSUE_ARGS_NOT_LIST,
    MCP_ISSUE_COMMAND_NOT_FOUND,
    MCP_ISSUE_INVALID_URL,
    MCP_ISSUE_MISSING_COMMAND,
    MCP_ISSUE_MISSING_TRANSPORT,
    MCP_ISSUE_SERVER_CONFIG_NOT_OBJECT,
    MCP_TRANSPORT_HTTP,
    MCP_TRANSPORT_STDIO,
    MCP_TRANSPORT_UNKNOWN,
    NODE_BLOCKER_MISSING_NODE,
    NODE_BLOCKER_MISSING_NPM,
    NODE_LOCKFILES,
    NODE_PM_NPM,
    NODE_PM_PNPM,
    NODE_PM_YARN,
    OFFICE_SKILLS,
    RELEASE_CHECK_BREAKING_NOTES,
    RELEASE_CHECK_CRITICAL_TEST_PLAN,
    RELEASE_CHECK_NOTES_PRESENT,
    RELEASE_CHECK_ROLLBACK_NOTES,
    RELEASE_CHECK_WORKTREE_CLEAN,
    SKILL_ALIAS_OFFICE_FORMAT,
    SKILL_ALIAS_OFFICE_READER,
    SKILL_CHANNEL_OPS,
    SKILL_CLAW_REDBOOK_AUTO,
    SKILL_DOCS_SYNC,
    SKILL_INCIDENT_TRIAGE,
    SKILL_MCP_ADMIN,
    SKILL_NODE_TOOLCHAIN,
    SKILL_OFFICE_READER,
    SKILL_RELEASE_HELPER,
    SKILL_REPO_REVIEW,
    STATUS_INVALID,
    STATUS_NEEDS_ATTENTION,
    STATUS_OK,
)
from pyclaw.agents.skills.loader import load_workspace_skill_entries
from pyclaw.cli.app import app as cli_app
from pyclaw.config.io import load_config_raw

_ENV_VAR_RE = re.compile(r"\b(?:PYCLAW|OPENCLAW)_[A-Z0-9_]+\b")
_PATH_RE = re.compile(r"`([A-Za-z0-9_./-]+\.[A-Za-z0-9]+)`")
_TOP_LEVEL_KEY_RE = re.compile(r"^\|\s*`([^`]+)`\s*\|", re.MULTILINE)


def run_skill(
    skill_key: str,
    *,
    workspace_dir: str | Path | None = None,
    payload: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run a bundled skill by key and return structured output."""
    workspace = Path(workspace_dir or Path.cwd())
    payload = payload or {}
    payload = dict(payload)
    payload.setdefault("workspace_dir", str(workspace))
    resolved_config = config if isinstance(config, dict) else load_config_raw()
    entry = _resolve_skill_entry(skill_key, workspace, config=resolved_config)
    preflight = _preflight_skill_invocation(entry, payload)
    if preflight is not None:
        return preflight
    prefer_script = bool(payload.get("prefer_script_runtime", False))
    if prefer_script:
        script_result = _run_skill_script(entry, payload=payload, workspace=workspace, config=resolved_config)
        if script_result is not None:
            return script_result
    key = entry.name
    if key in OFFICE_SKILLS:
        return _run_office_reader(key, payload)
    if key == SKILL_REPO_REVIEW:
        return _run_repo_review(payload)
    if key == SKILL_DOCS_SYNC:
        return _run_docs_sync(payload)
    if key == SKILL_INCIDENT_TRIAGE:
        return _run_incident_triage(payload)
    if key == SKILL_CHANNEL_OPS:
        return _run_channel_ops(payload)
    if key == SKILL_RELEASE_HELPER:
        return _run_release_helper(workspace, payload)
    if key == SKILL_NODE_TOOLCHAIN:
        return _run_node_toolchain(payload)
    if key == SKILL_MCP_ADMIN:
        return _run_mcp_admin(resolved_config, payload)
    if key == SKILL_CLAW_REDBOOK_AUTO:
        return _run_xiaohongshu_core(payload)
    script_result = _run_skill_script(entry, payload=payload, workspace=workspace, config=resolved_config)
    if script_result is not None:
        return script_result
    raise KeyError(f"Unsupported skill: {skill_key}")


def _preflight_skill_invocation(entry: Any, payload: dict[str, Any]) -> dict[str, Any] | None:
    """Validate invocation policy and runtime contract before execution."""
    allow_unsafe = _payload_bool(payload, "ignore_runtime_contract", default=False)
    invocation = getattr(entry, "invocation", None)
    if invocation is not None and not invocation.user_invocable:
        return {
            "skill": entry.name,
            "status": STATUS_INVALID,
            "summary": "Skill is not user invocable.",
            "blocking_items": ["skill_not_user_invocable"],
        }
    # Runtime probe skills must run even when dependencies are currently missing.
    if entry.name in {SKILL_MCP_ADMIN, SKILL_NODE_TOOLCHAIN}:
        return None
    contract = getattr(entry, "runtime_contract", None)
    if allow_unsafe or contract is None or contract.is_compatible:
        return None
    missing_deps = list(contract.missing_deps or [])
    return {
        "skill": entry.name,
        "status": STATUS_NEEDS_ATTENTION,
        "summary": "Skill runtime contract check failed.",
        "runtime_contract": {
            "runtime": contract.runtime,
            "launcher": contract.launcher,
            "security_level": contract.security_level,
            "deps": list(contract.deps or []),
            "missing_deps": missing_deps,
            "is_compatible": bool(contract.is_compatible),
        },
        "blocking_items": [f"missing_dep:{dep}" for dep in missing_deps],
        "next_steps": [
            "Install missing runtime dependencies declared by the skill.",
            "Re-run with payload flag `ignore_runtime_contract=true` only for diagnostics.",
        ],
    }


def _payload_bool(payload: dict[str, Any], key: str, *, default: bool = False) -> bool:
    """Parse a payload boolean field strictly and safely."""
    value = payload.get(key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off", ""}:
            return False
    if isinstance(value, int):
        return value != 0
    return default


def _run_skill_script(
    entry: Any,
    *,
    payload: dict[str, Any],
    workspace: Path,
    config: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Run skill-local script runtime if present.

    Expected location:
    - <skill-dir>/scripts/runtime.py
    Expected callable:
    - run(...)
    """
    skill_file = Path(str(entry.path))
    runtime_file = skill_file.parent / "scripts" / "runtime.py"
    if not runtime_file.is_file():
        return None
    runtime_file_str = str(runtime_file)
    try:
        module_name = f"pyclaw_skill_runtime_{entry.name.replace('-', '_')}"
        spec = importlib.util.spec_from_file_location(module_name, runtime_file)
        if spec is None or spec.loader is None:
            return {
                "skill": entry.name,
                "status": STATUS_INVALID,
                "summary": "Skill runtime script could not be loaded.",
                "blocking_items": ["runtime_module_load_failed"],
                "runtime_file": runtime_file_str,
            }
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        runner = getattr(module, "run", None)
        if not callable(runner):
            return {
                "skill": entry.name,
                "status": STATUS_INVALID,
                "summary": "Skill runtime script missing callable run().",
                "blocking_items": ["runtime_run_missing"],
                "runtime_file": runtime_file_str,
            }
        kwargs = {
            "payload": payload,
            "workspace_dir": str(workspace),
            "skill_key": entry.name,
            "config": config or {},
        }
        sig = inspect.signature(runner)
        accepted = {k: v for k, v in kwargs.items() if k in sig.parameters}
        result = runner(**accepted)
        if not isinstance(result, dict):
            return {
                "skill": entry.name,
                "status": STATUS_INVALID,
                "summary": "Skill runtime returned non-dict result.",
                "blocking_items": ["runtime_invalid_return_type"],
                "runtime_file": runtime_file_str,
            }
        result.setdefault("skill", entry.name)
        result.setdefault("runtime", "skill-script")
        return result
    except Exception as exc:
        return {
            "skill": entry.name,
            "status": STATUS_INVALID,
            "summary": f"Skill runtime execution failed: {exc}",
            "blocking_items": ["runtime_execution_failed"],
            "runtime_file": runtime_file_str,
        }


def _resolve_skill_entry(skill_key: str, workspace: Path, config: dict[str, Any] | None) -> Any:
    entries = load_workspace_skill_entries(workspace, config=config)
    by_name = {entry.name: entry for entry in entries}
    key = skill_key.strip().lower()
    normalized = SKILL_ALIAS_OFFICE_FORMAT if key == SKILL_ALIAS_OFFICE_READER else key
    if normalized not in by_name:
        raise KeyError(f"Skill not found: {skill_key}")
    return by_name[normalized]


def _run_repo_review(payload: dict[str, Any]) -> dict[str, Any]:
    findings = payload.get("findings")
    if not isinstance(findings, list):
        findings = []
    return {
        "skill": SKILL_REPO_REVIEW,
        "status": STATUS_OK,
        "summary": "Repository review checklist prepared.",
        "focus_order": [
            "behavioral_regressions",
            "security_data_safety",
            "concurrency_performance",
            "error_handling_fallbacks",
            "missing_tests_observability",
        ],
        "findings": findings,
    }


def _run_docs_sync(payload: dict[str, Any]) -> dict[str, Any]:
    workspace = Path(payload.get("workspace_dir") or Path.cwd())
    docs_path = _resolve_docs_path(workspace, payload.get("scope"))
    checks = list(DOCS_CHECKS)
    if not docs_path.exists():
        return {
            "skill": SKILL_DOCS_SYNC,
            "status": STATUS_NEEDS_ATTENTION,
            "requested_scope": payload.get("scope", DEFAULT_DOCS_SCOPE),
            "checks": checks,
            "blocking_items": [f"docs_not_found:{docs_path}"],
            "drift_summary": {"total": 1, "by_category": {DOCS_CATEGORY_PRESENCE: 1}},
            "drifts": [
                {
                    "category": DOCS_CATEGORY_PRESENCE,
                    "doc_location": str(docs_path),
                    "implementation_location": DOCS_LOCATION_CONFIG,
                    "proposed_correction": "Restore or regenerate configuration documentation.",
                }
            ],
        }

    doc_text = docs_path.read_text(encoding="utf-8")
    drifts: list[dict[str, str]] = []
    drifts.extend(_detect_top_level_key_drifts(doc_text))
    drifts.extend(_detect_env_var_drifts(workspace, doc_text))
    drifts.extend(_detect_stale_paths(workspace, doc_text))
    drifts.extend(_detect_cli_example_drifts(doc_text))

    by_category: dict[str, int] = {}
    for drift in drifts:
        category = drift.get("category", "other")
        by_category[category] = by_category.get(category, 0) + 1

    status = STATUS_OK if not drifts else STATUS_NEEDS_ATTENTION
    blocking_items = sorted(by_category.keys()) if drifts else []
    return {
        "skill": SKILL_DOCS_SYNC,
        "status": status,
        "checks": checks,
        "requested_scope": payload.get("scope", DEFAULT_DOCS_SCOPE),
        "drift_summary": {"total": len(drifts), "by_category": by_category},
        "drifts": drifts,
        "blocking_items": blocking_items,
    }


def _run_incident_triage(payload: dict[str, Any]) -> dict[str, Any]:
    severity = str(payload.get("severity", "medium")).lower()
    return {
        "skill": SKILL_INCIDENT_TRIAGE,
        "status": STATUS_OK,
        "severity": severity,
        "impact_summary": payload.get("impact_summary", ""),
        "next_actions": payload.get(
            "next_actions",
            [
                "classify_blast_radius",
                "collect_logs_metrics",
                "prepare_safe_mitigation",
                "define_verification_signals",
            ],
        ),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def _run_channel_ops(payload: dict[str, Any]) -> dict[str, Any]:
    channels = payload.get("channels")
    if not isinstance(channels, list):
        channels = []
    return {
        "skill": SKILL_CHANNEL_OPS,
        "status": STATUS_OK,
        "channels": channels,
        "checks": [
            "policy_alignment",
            "routing_validation",
            "formatting_fallback",
            "retry_deadletter",
            "capability_mismatch",
        ],
    }


def _run_release_helper(workspace: Path, payload: dict[str, Any]) -> dict[str, Any]:
    branch = _run_git(workspace, ["rev-parse", "--abbrev-ref", "HEAD"])
    porcelain = _run_git(workspace, ["status", "--porcelain"])
    clean = porcelain == ""
    tag = str(payload.get("tag", "")).strip()
    changed_files = _collect_changed_files(workspace)
    critical_changed = _collect_critical_changed(changed_files)
    notes = str(payload.get("release_notes", "")).strip()
    rollback_notes = str(payload.get("rollback_notes", "")).strip()
    breaking_change = bool(payload.get("breaking_change", False))
    breaking_notes = str(payload.get("breaking_notes", "")).strip()

    check_items = [
        {
            "name": RELEASE_CHECK_WORKTREE_CLEAN,
            "required": True,
            "passed": clean,
            "detail": "No local changes pending." if clean else "Working tree has pending changes.",
        },
        {
            "name": RELEASE_CHECK_CRITICAL_TEST_PLAN,
            "required": True,
            "passed": (not critical_changed) or bool(payload.get("test_plan")),
            "detail": (
                "Critical modules changed; attach `test_plan` before release."
                if critical_changed and not payload.get("test_plan")
                else "No critical-module blocker."
            ),
        },
        {
            "name": RELEASE_CHECK_NOTES_PRESENT,
            "required": True,
            "passed": bool(notes),
            "detail": "release_notes provided." if notes else "Missing `release_notes`.",
        },
        {
            "name": RELEASE_CHECK_BREAKING_NOTES,
            "required": breaking_change,
            "passed": (not breaking_change) or bool(breaking_notes),
            "detail": (
                "Breaking change declared without `breaking_notes`."
                if breaking_change and not breaking_notes
                else "No breaking-note blocker."
            ),
        },
        {
            "name": RELEASE_CHECK_ROLLBACK_NOTES,
            "required": True,
            "passed": bool(rollback_notes),
            "detail": "rollback_notes provided." if rollback_notes else "Missing `rollback_notes`.",
        },
    ]
    blocking_items = [item["name"] for item in check_items if item["required"] and not item["passed"]]
    return {
        "skill": SKILL_RELEASE_HELPER,
        "status": STATUS_OK if not blocking_items else STATUS_NEEDS_ATTENTION,
        "branch": branch or "unknown",
        "clean_worktree": clean,
        "git_status_porcelain": porcelain.splitlines(),
        "changed_files": changed_files,
        "critical_changed_files": critical_changed,
        "requested_tag": tag,
        "checks": check_items,
        "blocking_items": blocking_items,
    }


def _run_node_toolchain(payload: dict[str, Any]) -> dict[str, Any]:
    workspace = Path(payload.get("workspace_dir") or Path.cwd())
    node_ok, node_version = _run_command(["node", "--version"], workspace)
    npm_ok, npm_version = _run_command(["npm", "--version"], workspace)
    package_json = workspace / "package.json"
    scripts: list[str] = []
    if package_json.exists():
        try:
            parsed = json.loads(package_json.read_text(encoding="utf-8"))
            script_obj = parsed.get("scripts")
            if isinstance(script_obj, dict):
                scripts = sorted(k for k in script_obj if isinstance(k, str))
        except Exception:
            scripts = []

    lockfiles = [f for f in NODE_LOCKFILES if (workspace / f).exists()]
    preferred_pm = NODE_PM_NPM
    if "pnpm-lock.yaml" in lockfiles:
        preferred_pm = NODE_PM_PNPM
    elif "yarn.lock" in lockfiles:
        preferred_pm = NODE_PM_YARN

    blockers: list[str] = []
    if not node_ok:
        blockers.append(NODE_BLOCKER_MISSING_NODE)
    if not npm_ok and preferred_pm == NODE_PM_NPM:
        blockers.append(NODE_BLOCKER_MISSING_NPM)
    return {
        "skill": SKILL_NODE_TOOLCHAIN,
        "status": STATUS_OK if not blockers else STATUS_NEEDS_ATTENTION,
        "intent": payload.get("intent", "read_only_probe"),
        "workspace": str(workspace),
        "node": {"available": node_ok, "version": node_version},
        "npm": {"available": npm_ok, "version": npm_version},
        "package_manager": {"lockfiles": lockfiles, "preferred": preferred_pm},
        "scripts": scripts,
        "blocking_items": blockers,
        "next_steps": (
            ["Install Node.js runtime."]
            if blockers
            else ["Run lint/test through project package scripts before release."]
        ),
    }


def _run_mcp_admin(config: dict[str, Any] | None, payload: dict[str, Any]) -> dict[str, Any]:
    cfg = config if isinstance(config, dict) else load_config_raw()
    tools = cfg.get("tools") if isinstance(cfg, dict) else None
    mcp_servers = tools.get("mcpServers") if isinstance(tools, dict) else None
    servers = mcp_servers if isinstance(mcp_servers, dict) else {}
    target = str(payload.get("target", "")).strip()
    server_names = sorted(servers.keys())
    if target:
        server_names = [name for name in server_names if name == target]

    diagnostics: list[dict[str, Any]] = []
    failed: list[str] = []
    for name in server_names:
        raw = servers.get(name)
        if not isinstance(raw, dict):
            diagnostics.append(
                {
                    "server": name,
                    "status": STATUS_INVALID,
                    "transport": MCP_TRANSPORT_UNKNOWN,
                    "issues": [MCP_ISSUE_SERVER_CONFIG_NOT_OBJECT],
                }
            )
            failed.append(name)
            continue
        transport, issues = _validate_mcp_server(raw)
        if issues:
            failed.append(name)
        diagnostics.append(
            {
                "server": name,
                "status": STATUS_OK if not issues else STATUS_NEEDS_ATTENTION,
                "transport": transport,
                "issues": issues,
            }
        )

    return {
        "skill": SKILL_MCP_ADMIN,
        "status": STATUS_OK if not failed else STATUS_NEEDS_ATTENTION,
        "configured_servers": server_names,
        "target": target,
        "blocking_items": failed,
        "failed_servers": failed,
        "diagnostics": diagnostics,
    }


def _run_office_reader(skill_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    path = str(payload.get("path", "")).strip()
    return {
        "skill": SKILL_OFFICE_READER,
        "status": STATUS_OK,
        "format": skill_key,
        "path": path,
        "note": "Reader extraction should be performed via corresponding read_* tool.",
    }


def _run_xiaohongshu_core(payload: dict[str, Any]) -> dict[str, Any]:
    workspace = Path(payload.get("workspace_dir") or Path.cwd())
    intent = str(payload.get("intent", "full-stack-ops")).strip() or "full-stack-ops"
    account = str(payload.get("account", "default")).strip() or "default"
    target_mode = str(payload.get("mode", "headless")).strip() or "headless"
    compliance = payload.get("compliance", True)
    if not isinstance(compliance, bool):
        compliance = True
    python_bin = shutil.which("python") or shutil.which("python3")
    browser_candidates = [
        "google-chrome",
        "google-chrome-stable",
        "chromium",
        "chromium-browser",
        "chrome",
    ]
    browser_bin = next((name for name in browser_candidates if shutil.which(name)), "")
    blockers: list[str] = []
    if not python_bin:
        blockers.append("python_runtime_missing")
    if not browser_bin:
        blockers.append("chrome_or_chromium_missing")

    capabilities = [
        "auth_and_qrcode_login",
        "multi_account_profile_isolation",
        "publish_graphic_video_longform",
        "publish_preview_and_confirm",
        "scheduled_publish",
        "auto_hashtag_inference",
        "home_feed_and_keyword_search",
        "note_detail_and_comment_thread_extraction",
        "comment_reply_like_favorite_actions",
        "profile_snapshot_and_notes_listing",
        "notification_mentions_pull",
        "creator_center_content_data_export_csv",
        "cdn_media_download_with_cache",
        "remote_cdp_and_headless_execution",
        "selector_drift_repair_and_fallback_waits",
    ]
    execution_steps = [
        "verify_login_state",
        "load_or_switch_account",
        "resolve_operation_intent",
        "prepare_media_and_payload",
        "run_publish_or_explore_or_interact",
        "capture_structured_result",
        "apply_compliance_and_risk_checks",
        "emit_summary_and_next_actions",
    ]
    safety_checks = [
        "platform_policy_compliance",
        "content_legality_and_sensitive_terms",
        "idempotent_interaction_guard",
        "rate_limit_backoff",
        "selector_change_detection",
        "credential_scope_isolation",
    ]
    return {
        "skill": SKILL_CLAW_REDBOOK_AUTO,
        "status": STATUS_OK if not blockers else STATUS_NEEDS_ATTENTION,
        "summary": "Xiaohongshu core operations profile loaded.",
        "workspace": str(workspace),
        "intent": intent,
        "account": account,
        "mode": target_mode,
        "compliance_enabled": compliance,
        "runtime_probe": {
            "python": {"available": bool(python_bin), "binary": python_bin or ""},
            "browser": {
                "available": bool(browser_bin),
                "binary": browser_bin,
                "candidates": browser_candidates,
            },
        },
        "capabilities": capabilities,
        "execution_steps": execution_steps,
        "safety_checks": safety_checks,
        "blocking_items": blockers,
    }


def _run_git(workspace: Path, args: list[str]) -> str:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(workspace),
            capture_output=True,
            text=True,
            check=False,
            timeout=8,
        )
        if proc.returncode != 0:
            return ""
        return proc.stdout.strip()
    except Exception:
        return ""


def parse_payload(input_json: str) -> dict[str, Any]:
    text = input_json.strip()
    if not text:
        return {}
    loaded = json.loads(text)
    if not isinstance(loaded, dict):
        raise ValueError("Payload must be a JSON object")
    return loaded


def _resolve_docs_path(workspace: Path, scope: Any) -> Path:
    if isinstance(scope, str) and scope.strip():
        p = Path(scope.strip())
        return p if p.is_absolute() else workspace / p
    return workspace / DEFAULT_DOCS_SCOPE


def _detect_top_level_key_drifts(doc_text: str) -> list[dict[str, str]]:
    section = _slice_section(doc_text, DOCS_TOP_LEVEL_MARKER)
    if not section:
        return []
    documented = {_normalize_key(v) for v in _TOP_LEVEL_KEY_RE.findall(section) if v and v not in {"配置节", "------"}}
    from pyclaw.config.schema import PyClawConfig

    model_fields = PyClawConfig.model_fields
    code_keys = {_normalize_key(name) for name in model_fields}
    code_keys.update(_normalize_key(field.alias) for field in model_fields.values() if isinstance(field.alias, str))
    missing = sorted(k for k in documented if k and k not in code_keys)
    return [
        {
            "category": "config_keys_alignment",
            "doc_location": DOCS_LOCATION_TOP_LEVEL,
            "implementation_location": "src/pyclaw/config/schema.py",
            "proposed_correction": f"Remove or rename unknown config key `{k}` in docs.",
        }
        for k in missing
    ]


def _detect_env_var_drifts(workspace: Path, doc_text: str) -> list[dict[str, str]]:
    section = _slice_section(doc_text, DOCS_ENV_TABLE_MARKER)
    if not section:
        return []
    documented = {v for v in _TOP_LEVEL_KEY_RE.findall(section) if v.startswith("PYCLAW_") or v.startswith("OPENCLAW_")}
    code_vars: set[str] = set()
    for file in workspace.joinpath("src").rglob("*.py"):
        try:
            text = file.read_text(encoding="utf-8")
        except Exception:
            continue
        code_vars.update(_ENV_VAR_RE.findall(text))
    stale = sorted(v for v in documented if v not in code_vars)
    return [
        {
            "category": "env_vars_alignment",
            "doc_location": DOCS_LOCATION_ENV,
            "implementation_location": "src/**/*.py",
            "proposed_correction": f"Remove stale env var `{v}` or add code support.",
        }
        for v in stale
    ]


def _detect_stale_paths(workspace: Path, doc_text: str) -> list[dict[str, str]]:
    drifts: list[dict[str, str]] = []
    for path_str in sorted(set(_PATH_RE.findall(doc_text))):
        if path_str.startswith("~") or path_str.startswith("http"):
            continue
        candidate = workspace / path_str
        if not candidate.exists():
            drifts.append(
                {
                    "category": "broken_or_stale_paths",
                    "doc_location": DOCS_LOCATION_CONFIG,
                    "implementation_location": path_str,
                    "proposed_correction": f"Fix broken path reference `{path_str}`.",
                }
            )
    return drifts


def _detect_cli_example_drifts(doc_text: str) -> list[dict[str, str]]:
    commands = _extract_pyclaw_commands(doc_text)
    if not commands:
        return []
    import click
    from typer.main import get_command

    click_app = get_command(cli_app)
    # 检查是否有 commands 属性（对于 Group 类型）或者作为其他类型的处理
    if hasattr(click_app, "commands"):
        available = set(click_app.commands.keys())
    elif isinstance(click_app, click.Command):
        # 如果是单一命令而不是命令组，则可用命令集为空
        available = set()
    else:
        available = set()

    drifts: list[dict[str, str]] = []
    for cmd in commands:
        parts = shlex.split(cmd)
        if len(parts) < 2:
            continue
        root = parts[1]
        if root not in available:
            drifts.append(
                {
                    "category": "cli_examples_alignment",
                    "doc_location": DOCS_LOCATION_CONFIG,
                    "implementation_location": "src/pyclaw/cli/app.py",
                    "proposed_correction": f"Update example `{cmd}`; unknown command `{root}`.",
                }
            )
    return drifts


def _extract_pyclaw_commands(doc_text: str) -> list[str]:
    lines = doc_text.splitlines()
    commands: list[str] = []
    in_bash = False
    for line in lines:
        if line.strip().startswith("```"):
            in_bash = line.strip() == "```bash" if not in_bash else False
            continue
        if in_bash and line.strip().startswith("pyclaw "):
            commands.append(line.strip())
    return commands


def _slice_section(text: str, marker: str) -> str:
    idx = text.find(marker)
    if idx < 0:
        return ""
    remain = text[idx:]
    next_idx = remain.find("\n## ", 1)
    return remain if next_idx < 0 else remain[:next_idx]


def _normalize_key(key: str) -> str:
    cleaned = key.replace("`", "").strip()
    return cleaned.replace("_", "").replace("-", "").lower()


def _collect_changed_files(workspace: Path) -> list[str]:
    files = _run_git(workspace, ["status", "--porcelain"])
    out: list[str] = []
    for line in files.splitlines():
        if not line.strip():
            continue
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1].strip()
        if path:
            out.append(path)
    return out


def _collect_critical_changed(paths: list[str]) -> list[str]:
    return sorted(p for p in paths if p.startswith(CRITICAL_PATH_PREFIXES))


def _run_command(args: list[str], cwd: Path) -> tuple[bool, str]:
    try:
        proc = subprocess.run(
            args,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except Exception as exc:
        return False, str(exc)
    if proc.returncode != 0:
        return False, (proc.stderr or "").strip()
    return True, (proc.stdout or "").strip()


def _validate_mcp_server(server_cfg: dict[str, Any]) -> tuple[str, list[str]]:
    issues: list[str] = []
    if "command" in server_cfg:
        transport = MCP_TRANSPORT_STDIO
        command = str(server_cfg.get("command", "")).strip()
        if not command:
            issues.append(MCP_ISSUE_MISSING_COMMAND)
        elif shutil.which(command) is None:
            issues.append(MCP_ISSUE_COMMAND_NOT_FOUND)
        args = server_cfg.get("args")
        if args is not None and not isinstance(args, list):
            issues.append(MCP_ISSUE_ARGS_NOT_LIST)
    elif "url" in server_cfg:
        transport = MCP_TRANSPORT_HTTP
        url = str(server_cfg.get("url", "")).strip()
        if not (url.startswith("http://") or url.startswith("https://")):
            issues.append(MCP_ISSUE_INVALID_URL)
    else:
        transport = MCP_TRANSPORT_UNKNOWN
        issues.append(MCP_ISSUE_MISSING_TRANSPORT)
    return transport, issues
