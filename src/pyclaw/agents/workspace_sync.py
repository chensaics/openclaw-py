"""Workspace template sync — create/update workspace files from bundled templates."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

SYNC_TEMPLATES = [
    "AGENTS.md",
    "AGENTS.default.md",
    "SOUL.md",
    "HEARTBEAT.md",
    "TOOLS.md",
    "USER.md",
    "IDENTITY.md",
    "BOOT.md",
    "BOOTSTRAP.md",
]

_TEMPLATES_DIR = Path(__file__).parent / "templates"


def _workspace_dir() -> Path:
    return Path.home() / ".pyclaw" / "workspace"


def sync_templates(
    *,
    force: bool = False,
    workspace: Path | None = None,
) -> dict[str, list[str]]:
    """Sync templates to workspace. Returns created/updated/skipped file lists."""
    ws = workspace or _workspace_dir()
    ws.mkdir(parents=True, exist_ok=True)

    result: dict[str, list[str]] = {"created": [], "updated": [], "skipped": []}

    for name in SYNC_TEMPLATES:
        tpl_path = _TEMPLATES_DIR / name
        ws_path = ws / name

        if not tpl_path.exists():
            continue

        tpl_content = tpl_path.read_text(encoding="utf-8")

        if not ws_path.exists():
            ws_path.write_text(tpl_content, encoding="utf-8")
            result["created"].append(name)
        elif force:
            ws_path.write_text(tpl_content, encoding="utf-8")
            result["updated"].append(name)
        else:
            current = ws_path.read_text(encoding="utf-8")
            if current != tpl_content:
                result["skipped"].append(name)

    return result


def diff_templates(*, workspace: Path | None = None) -> list[dict[str, str]]:
    """Compare workspace files against templates."""
    ws = workspace or _workspace_dir()
    diffs: list[dict[str, str]] = []

    for name in SYNC_TEMPLATES:
        tpl_path = _TEMPLATES_DIR / name
        ws_path = ws / name

        if not tpl_path.exists():
            continue

        if not ws_path.exists():
            diffs.append({"name": name, "status": "missing"})
            continue

        tpl_content = tpl_path.read_text(encoding="utf-8")
        ws_content = ws_path.read_text(encoding="utf-8")

        if tpl_content != ws_content:
            diffs.append({"name": name, "status": "modified"})

    return diffs
