"""Backup CLI commands — export and import pyclaw configuration and sessions.

Usage:
    pyclaw backup export [--output backup.zip]
    pyclaw backup import backup.zip
"""

from __future__ import annotations

import json
import logging
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import typer
from rich.console import Console

logger = logging.getLogger(__name__)
console = Console()

backup_app = typer.Typer(name="backup", help="Export and import pyclaw data.")


@backup_app.command("export")
def backup_export(
    output: str = typer.Option(
        "",
        "--output", "-o",
        help="Output zip file path. Defaults to pyclaw-backup-<date>.zip",
    ),
) -> None:
    """Export configuration, sessions, and summaries to a zip archive."""
    from pyclaw.config.paths import resolve_state_dir

    state_dir = resolve_state_dir()
    if not state_dir.exists():
        console.print("[red]No pyclaw data directory found.[/red]")
        raise typer.Exit(1)

    if not output:
        datestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        output = f"pyclaw-backup-{datestamp}.zip"

    output_path = Path(output)
    included_count = 0

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for pattern in ("*.json", "*.json5"):
            for p in state_dir.glob(pattern):
                if _is_safe_to_backup(p):
                    arcname = f"config/{p.name}"
                    zf.write(p, arcname)
                    included_count += 1

        sessions_dir = state_dir / "sessions"
        if sessions_dir.exists():
            for p in sessions_dir.rglob("*.jsonl"):
                arcname = f"sessions/{p.relative_to(sessions_dir)}"
                zf.write(p, arcname)
                included_count += 1

        summaries_dir = state_dir / "summaries"
        if summaries_dir.exists():
            for p in summaries_dir.rglob("*.md"):
                arcname = f"summaries/{p.relative_to(summaries_dir)}"
                zf.write(p, arcname)
                included_count += 1

        memory_db = state_dir / "memory.db"
        if memory_db.exists():
            zf.write(memory_db, "memory.db")
            included_count += 1

        manifest: dict[str, Any] = {
            "version": 1,
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "files": included_count,
        }
        zf.writestr("manifest.json", json.dumps(manifest, indent=2))

    console.print(f"[green]Exported {included_count} files to {output_path}[/green]")


@backup_app.command("import")
def backup_import(
    archive: str = typer.Argument(..., help="Path to backup zip file"),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing files"),
) -> None:
    """Import configuration and sessions from a backup archive."""
    from pyclaw.config.paths import resolve_state_dir

    archive_path = Path(archive)
    if not archive_path.exists():
        console.print(f"[red]Archive not found: {archive}[/red]")
        raise typer.Exit(1)

    state_dir = resolve_state_dir()
    state_dir.mkdir(parents=True, exist_ok=True)

    restored = 0
    skipped = 0

    with zipfile.ZipFile(archive_path, "r") as zf:
        manifest_data = None
        if "manifest.json" in zf.namelist():
            manifest_data = json.loads(zf.read("manifest.json"))
            console.print(f"Backup created: {manifest_data.get('createdAt', 'unknown')}")

        for info in zf.infolist():
            if info.is_dir() or info.filename == "manifest.json":
                continue

            if info.filename.startswith("config/"):
                target = state_dir / info.filename[len("config/"):]
            elif info.filename.startswith("sessions/"):
                target = state_dir / "sessions" / info.filename[len("sessions/"):]
            elif info.filename.startswith("summaries/"):
                target = state_dir / "summaries" / info.filename[len("summaries/"):]
            elif info.filename == "memory.db":
                target = state_dir / "memory.db"
            else:
                continue

            if target.exists() and not force:
                skipped += 1
                continue

            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(zf.read(info.filename))
            restored += 1

    console.print(f"[green]Restored {restored} files[/green]")
    if skipped:
        console.print(f"[yellow]Skipped {skipped} existing files (use --force to overwrite)[/yellow]")


def _is_safe_to_backup(path: Path) -> bool:
    """Exclude files that might contain raw secrets."""
    name = path.name.lower()
    if "credential" in name or "secret" in name:
        return False
    return True
