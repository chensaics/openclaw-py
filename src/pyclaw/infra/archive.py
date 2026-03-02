"""Archive management — session/config archival, compression, path management.

Ported from ``src/infra/archive.ts``, ``archive-path.ts``.

Provides:
- Session archival to compressed files
- Config snapshot archival
- Archive path management
- Archive listing and retrieval
"""

from __future__ import annotations

import gzip
import json
import logging
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ArchiveConfig:
    """Configuration for archive management."""
    base_dir: str = ""
    compress: bool = True
    max_archives: int = 50
    retention_days: int = 90


@dataclass
class ArchiveEntry:
    """Metadata for an archive entry."""
    archive_id: str
    archive_type: str  # "session" | "config" | "logs"
    source_path: str
    archive_path: str
    created_at: float = 0.0
    size_bytes: int = 0
    compressed: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.created_at == 0:
            self.created_at = time.time()


def archive_path(base_dir: str | Path, archive_type: str, archive_id: str, *, compressed: bool = True) -> Path:
    """Compute the archive path for a given type and ID."""
    base = Path(base_dir) / archive_type
    ext = ".json.gz" if compressed else ".json"
    return base / f"{archive_id}{ext}"


def archive_session(
    session_dir: str | Path,
    output_dir: str | Path,
    session_id: str,
    *,
    compress: bool = True,
) -> ArchiveEntry:
    """Archive a session directory to a single file."""
    src = Path(session_dir)
    out_dir = Path(output_dir) / "session"
    out_dir.mkdir(parents=True, exist_ok=True)

    data: dict[str, Any] = {
        "session_id": session_id,
        "archived_at": time.time(),
        "files": {},
    }

    if src.is_dir():
        for f in src.iterdir():
            if f.is_file():
                try:
                    data["files"][f.name] = f.read_text(encoding="utf-8")
                except Exception:
                    data["files"][f.name] = f"<binary: {f.stat().st_size} bytes>"

    ext = ".json.gz" if compress else ".json"
    archive_file = out_dir / f"{session_id}{ext}"
    content = json.dumps(data, indent=2).encode("utf-8")

    if compress:
        archive_file.write_bytes(gzip.compress(content))
    else:
        archive_file.write_bytes(content)

    return ArchiveEntry(
        archive_id=session_id,
        archive_type="session",
        source_path=str(src),
        archive_path=str(archive_file),
        size_bytes=archive_file.stat().st_size,
        compressed=compress,
    )


def archive_config(
    config_path: str | Path,
    output_dir: str | Path,
    *,
    compress: bool = True,
) -> ArchiveEntry:
    """Archive a config file with timestamp."""
    src = Path(config_path)
    if not src.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")

    out_dir = Path(output_dir) / "config"
    out_dir.mkdir(parents=True, exist_ok=True)

    timestamp = int(time.time())
    archive_id = f"config-{timestamp}"
    ext = ".json.gz" if compress else ".json"
    archive_file = out_dir / f"{archive_id}{ext}"

    content = src.read_bytes()
    if compress:
        archive_file.write_bytes(gzip.compress(content))
    else:
        archive_file.write_bytes(content)

    return ArchiveEntry(
        archive_id=archive_id,
        archive_type="config",
        source_path=str(src),
        archive_path=str(archive_file),
        size_bytes=archive_file.stat().st_size,
        compressed=compress,
    )


def list_archives(base_dir: str | Path, archive_type: str = "") -> list[ArchiveEntry]:
    """List all archives, optionally filtered by type."""
    base = Path(base_dir)
    entries: list[ArchiveEntry] = []

    if archive_type:
        dirs = [base / archive_type]
    else:
        dirs = [d for d in base.iterdir() if d.is_dir()] if base.exists() else []

    for d in dirs:
        if not d.exists():
            continue
        for f in sorted(d.iterdir()):
            if f.is_file() and (f.suffix in (".gz", ".json")):
                entries.append(ArchiveEntry(
                    archive_id=f.stem.replace(".json", ""),
                    archive_type=d.name,
                    source_path="",
                    archive_path=str(f),
                    size_bytes=f.stat().st_size,
                    compressed=f.suffix == ".gz",
                    created_at=f.stat().st_mtime,
                ))

    return entries


def prune_archives(base_dir: str | Path, config: ArchiveConfig) -> int:
    """Remove archives exceeding retention or count limits."""
    archives = list_archives(base_dir)
    archives.sort(key=lambda a: a.created_at)

    removed = 0
    cutoff = time.time() - (config.retention_days * 86400)

    while len(archives) > config.max_archives:
        oldest = archives.pop(0)
        Path(oldest.archive_path).unlink(missing_ok=True)
        removed += 1

    for a in list(archives):
        if a.created_at < cutoff:
            Path(a.archive_path).unlink(missing_ok=True)
            archives.remove(a)
            removed += 1

    return removed
