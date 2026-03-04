"""Secrets apply — execute a secrets plan to update config and auth files.

Ported from ``src/secrets/apply.ts``.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from pyclaw.config.io import load_config_raw, save_config
from pyclaw.config.paths import resolve_config_path
from pyclaw.config.schema import PyClawConfig
from pyclaw.secrets.plan import SecretsApplyPlan

logger = logging.getLogger(__name__)


def run_secrets_apply(
    plan: SecretsApplyPlan,
    *,
    config_path: Path | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Apply a secrets plan to the configuration.

    Returns a summary of changes made.
    """
    cfg_path = config_path or resolve_config_path()
    raw = load_config_raw(cfg_path)

    applied: list[str] = []
    skipped: list[str] = []
    errors: list[str] = []

    for target in plan.targets:
        try:
            ref_dict = {
                "source": target.ref.source,
                "provider": target.ref.provider,
                "id": target.ref.id,
            }
            _set_nested(raw, target.path, ref_dict)
            applied.append(target.path)
        except Exception as exc:
            errors.append(f"{target.path}: {exc}")

    if plan.scrub_legacy:
        _scrub_legacy_auth(cfg_path.parent)

    if not dry_run and applied:
        config = PyClawConfig.model_validate(raw)
        save_config(config, cfg_path)
        logger.info("Applied %d secret refs to config", len(applied))

    return {
        "applied": applied,
        "skipped": skipped,
        "errors": errors,
        "dry_run": dry_run,
    }


def _set_nested(data: dict[str, Any], path: str, value: Any) -> None:
    """Set a nested value in a dict using dot-separated path."""
    parts = path.split(".")
    current = data
    for part in parts[:-1]:
        if part not in current or not isinstance(current[part], dict):
            current[part] = {}
        current = current[part]
    current[parts[-1]] = value


def _scrub_legacy_auth(state_dir: Path) -> None:
    """Remove legacy auth.json files from agent directories."""
    agents_dir = state_dir / "agents"
    if not agents_dir.exists():
        return
    for agent_dir in agents_dir.iterdir():
        if not agent_dir.is_dir():
            continue
        legacy = agent_dir / "auth.json"
        if legacy.exists():
            legacy.unlink()
            logger.info("Removed legacy auth file: %s", legacy)
