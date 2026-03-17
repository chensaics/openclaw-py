"""Ops automation commands for M2/M3/M4 execution checklists."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import typer

from pyclaw.agents.skills.runner import run_skill
from pyclaw.cli.commands.status import scan_status
from pyclaw.terminal.palette import PALETTE

_ARTIFACT_NAME_RE = re.compile(r"^(android|ios|macos|windows|linux|web)-([0-9]+\.[0-9]+\.[0-9]+)-([A-Za-z0-9._-]+)$")
_DEFAULT_M4_TRACKER = "reference/ops/M4_UPSTREAM_RELEASE_DOCS_TRACKER.md"


@dataclass
class OpsCheck:
    name: str
    passed: bool
    detail: str
    required: bool = True


def ops_release_gate_command(
    *,
    artifacts_dir: str,
    release_notes: str,
    rollback_notes: str,
    expected_version: str | None,
    output_json: bool,
    write_report: str | None,
) -> None:
    """Run M3 release gate checks and optionally write a report."""
    workspace = Path.cwd()
    artifact_root = (workspace / artifacts_dir).resolve()
    checks: list[OpsCheck] = []

    pyproject_version = _read_project_version(workspace / "pyproject.toml")
    version_target = expected_version or pyproject_version

    checks.append(
        OpsCheck(
            name="project_version_available",
            passed=bool(pyproject_version),
            detail=f"pyproject version={pyproject_version or 'missing'}",
        )
    )
    checks.append(
        OpsCheck(
            name="version_consistency",
            passed=bool(version_target and pyproject_version and version_target == pyproject_version),
            detail=f"expected={version_target or 'unset'} pyproject={pyproject_version or 'missing'}",
        )
    )

    notes_ok = bool(release_notes.strip())
    rollback_ok = bool(rollback_notes.strip())
    checks.append(OpsCheck(name="release_notes_present", passed=notes_ok, detail="release_notes non-empty"))
    checks.append(OpsCheck(name="rollback_notes_present", passed=rollback_ok, detail="rollback_notes non-empty"))

    artifact_files = _list_artifacts(artifact_root)
    checks.append(
        OpsCheck(
            name="artifacts_present",
            passed=bool(artifact_files),
            detail=f"artifacts={len(artifact_files)} in {artifact_root}",
        )
    )

    naming_failures = _artifact_naming_failures(artifact_files, version_target or "")
    checks.append(
        OpsCheck(
            name="artifact_naming_rule",
            passed=not naming_failures,
            detail="all artifacts match platform-version-build naming"
            if not naming_failures
            else f"invalid: {', '.join(naming_failures)}",
        )
    )

    sha_file = ""
    if artifact_files:
        sha_file = str(_write_sha256_sums(artifact_files, artifact_root / "SHA256SUMS.txt"))
        checks.append(OpsCheck(name="sha256_archive_generated", passed=True, detail=sha_file))
    else:
        checks.append(OpsCheck(name="sha256_archive_generated", passed=False, detail="no artifacts to hash"))

    clean_ok, clean_detail = _is_worktree_clean(workspace)
    checks.append(OpsCheck(name="working_tree_clean", passed=clean_ok, detail=clean_detail))

    report = {
        "milestone": "M3",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "version": version_target,
        "checks": [asdict(c) for c in checks],
        "failed_required": [c.name for c in checks if c.required and not c.passed],
        "manual_checks_pending": [
            "android_signing_and_manifest_review",
            "apple_provisioning_entitlements_signing",
            "desktop_cold_start_validation",
            "web_route_and_static_asset_validation",
            "gate_record_traceability_to_tag",
        ],
        "release_notes": release_notes.strip(),
        "rollback_notes": rollback_notes.strip(),
        "artifacts_dir": str(artifact_root),
        "sha256_file": sha_file,
        "decision": "go" if all(c.passed for c in checks if c.required) else "hold",
    }
    if write_report:
        target = (workspace / write_report).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    _emit_ops(report, output_json=output_json, title="M3 release gate")


def ops_client_baseline_check_command(*, output_json: bool) -> None:
    """Run automated subset of M2 baseline checks."""
    checks: list[OpsCheck] = []

    status = scan_status(output_json=False, deep=True)
    checks.append(
        OpsCheck(
            name="gateway_health_visible",
            passed=bool(status.gateway_running),
            detail=f"gateway_running={status.gateway_running}",
        )
    )

    try:
        skill_ok = run_skill("repo-review", payload={"findings": []})
        checks.append(
            OpsCheck(
                name="skills_run_structured_result",
                passed=skill_ok.get("status") == "ok" and isinstance(skill_ok.get("findings"), list),
                detail=f"skill={skill_ok.get('skill')} status={skill_ok.get('status')}",
            )
        )
    except Exception as exc:
        checks.append(
            OpsCheck(
                name="skills_run_structured_result",
                passed=False,
                detail=f"repo-review failed: {exc}",
            )
        )

    try:
        skill_fail = run_skill(
            "docs-sync",
            payload={"scope": "docs/__intentionally_missing__.md"},
        )
        checks.append(
            OpsCheck(
                name="skills_failure_exposes_blocking_items",
                passed=skill_fail.get("status") == "needs_attention"
                and isinstance(skill_fail.get("blocking_items"), list)
                and len(skill_fail.get("blocking_items", [])) > 0,
                detail=f"status={skill_fail.get('status')} blockers={len(skill_fail.get('blocking_items', []))}",
            )
        )
    except Exception as exc:
        checks.append(
            OpsCheck(
                name="skills_failure_exposes_blocking_items",
                passed=False,
                detail=f"docs-sync failed: {exc}",
            )
        )

    report = {
        "milestone": "M2",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "checks": [asdict(c) for c in checks],
        "failed_required": [c.name for c in checks if c.required and not c.passed],
        "manual_checks_pending": [
            "flet_flutter_reconnect_behavior_consistency",
            "session_crud_consistency_across_clients",
            "chat_stream_interrupt_and_resend_consistency",
            "logs_and_cron_behavior_consistency_across_clients",
        ],
        "decision": "pass" if all(c.passed for c in checks if c.required) else "fail",
    }
    _emit_ops(report, output_json=output_json, title="M2 baseline check")


def ops_upstream_snapshot_command(
    *,
    window_start: str,
    window_end: str,
    summary: str,
    output_json: bool,
    tracker_path: str,
) -> None:
    """Append an M4 upstream tracking snapshot entry."""
    start = _parse_iso_date(window_start, field="window_start")
    end = _parse_iso_date(window_end, field="window_end")
    if start > end:
        raise typer.BadParameter("window_start must be <= window_end")

    target = (Path.cwd() / tracker_path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    block = (
        "\n\n---\n\n"
        f"### Snapshot {now}\n\n"
        f"- 巡检窗口：`{start.isoformat()} ~ {end.isoformat()}`\n"
        f"- 结论：{summary.strip() or '待补充'}\n"
        "- 状态：已记录\n"
    )
    with target.open("a", encoding="utf-8") as f:
        f.write(block)

    payload = {
        "milestone": "M4",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tracker_path": str(target),
        "window_start": start.isoformat(),
        "window_end": end.isoformat(),
        "summary": summary.strip(),
        "status": "recorded",
    }
    _emit_ops(payload, output_json=output_json, title="M4 upstream snapshot")


def _read_project_version(pyproject_path: Path) -> str:
    if not pyproject_path.is_file():
        return ""
    try:
        import tomllib

        parsed = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
        project = parsed.get("project")
        if isinstance(project, dict):
            val = project.get("version")
            if isinstance(val, str):
                return val.strip()
        tool = parsed.get("tool")
        if isinstance(tool, dict):
            poetry = tool.get("poetry")
            if isinstance(poetry, dict):
                val = poetry.get("version")
                if isinstance(val, str):
                    return val.strip()
    except Exception:
        return ""
    return ""


def _list_artifacts(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(
        [p for p in root.iterdir() if p.is_file() and p.name != "SHA256SUMS.txt"],
        key=lambda p: p.name,
    )


def _artifact_naming_failures(files: list[Path], version: str) -> list[str]:
    failed: list[str] = []
    for item in files:
        m = _ARTIFACT_NAME_RE.fullmatch(item.name)
        if not m:
            failed.append(item.name)
            continue
        if version and m.group(2) != version:
            failed.append(item.name)
    return failed


def _write_sha256_sums(files: list[Path], target: Path) -> Path:
    lines = []
    for path in files:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {path.name}")
    target.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return target


def _is_worktree_clean(workspace: Path) -> tuple[bool, str]:
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(workspace),
            capture_output=True,
            text=True,
            check=False,
            timeout=8,
        )
    except Exception as exc:
        return False, str(exc)
    if proc.returncode != 0:
        return False, (proc.stderr or "git status failed").strip()
    clean = (proc.stdout or "").strip() == ""
    return clean, "clean" if clean else "dirty"


def _parse_iso_date(raw: str, *, field: str) -> date:
    text = raw.strip()
    try:
        return date.fromisoformat(text)
    except Exception as exc:
        raise typer.BadParameter(f"{field} must be in YYYY-MM-DD format") from exc


def _emit_ops(payload: dict[str, Any], *, output_json: bool, title: str) -> None:
    p = PALETTE
    if output_json:
        typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    typer.echo(f"{p.info}{title}{p.reset}")
    decision = payload.get("decision", payload.get("status", "unknown"))
    typer.echo(f"Decision: {decision}")
    failed = payload.get("failed_required", [])
    if isinstance(failed, list) and failed:
        typer.echo(f"{p.warn}Failed checks:{p.reset} {', '.join(str(v) for v in failed)}")
    else:
        typer.echo(f"{p.success}All required automated checks passed.{p.reset}")
