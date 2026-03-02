"""Config backup rotation — automatic pre-write backup with retention limits.

Ported from ``src/config/config-backup.ts``.

Provides:
- Pre-write automatic backup creation
- Maximum retention count (oldest pruned)
- Timestamp-based naming
- Atomic write support
"""

from __future__ import annotations

import logging
import os
import shutil
import time
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_MAX_BACKUPS = 5
BACKUP_SUFFIX = ".bak"
BACKUP_TIMESTAMP_FMT = "%Y%m%d-%H%M%S"


@dataclass
class BackupConfig:
    """Configuration for config file backup."""

    max_backups: int = DEFAULT_MAX_BACKUPS
    backup_dir: str = ""  # Empty = same dir as original
    enabled: bool = True


@dataclass
class BackupInfo:
    """Information about a backup file."""

    path: str
    original_path: str
    created_at: float
    size_bytes: int


def _backup_dir(original_path: str, config: BackupConfig) -> str:
    """Determine the backup directory."""
    if config.backup_dir:
        return config.backup_dir
    return str(Path(original_path).parent)


def _backup_filename(original_path: str) -> str:
    """Generate a timestamped backup filename."""
    name = Path(original_path).name
    ts = time.strftime(BACKUP_TIMESTAMP_FMT)
    return f"{name}.{ts}{BACKUP_SUFFIX}"


def list_backups(original_path: str, config: BackupConfig | None = None) -> list[BackupInfo]:
    """List existing backups for a config file, sorted oldest first."""
    cfg = config or BackupConfig()
    backup_dir = _backup_dir(original_path, cfg)
    base_name = Path(original_path).name

    if not os.path.isdir(backup_dir):
        return []

    backups: list[BackupInfo] = []
    for entry in os.scandir(backup_dir):
        if entry.name.startswith(base_name) and entry.name.endswith(BACKUP_SUFFIX):
            stat = entry.stat()
            backups.append(
                BackupInfo(
                    path=entry.path,
                    original_path=original_path,
                    created_at=stat.st_mtime,
                    size_bytes=stat.st_size,
                )
            )

    backups.sort(key=lambda b: b.created_at)
    return backups


def create_backup(original_path: str, config: BackupConfig | None = None) -> BackupInfo | None:
    """Create a backup of a config file before writing.

    Returns None if the original file doesn't exist or backups are disabled.
    """
    cfg = config or BackupConfig()
    if not cfg.enabled:
        return None

    if not os.path.exists(original_path):
        return None

    backup_dir = _backup_dir(original_path, cfg)
    os.makedirs(backup_dir, exist_ok=True)

    backup_name = _backup_filename(original_path)
    backup_path = os.path.join(backup_dir, backup_name)

    shutil.copy2(original_path, backup_path)

    stat = os.stat(backup_path)
    info = BackupInfo(
        path=backup_path,
        original_path=original_path,
        created_at=stat.st_mtime,
        size_bytes=stat.st_size,
    )

    # Prune old backups
    _prune_backups(original_path, cfg)

    return info


def _prune_backups(original_path: str, config: BackupConfig) -> int:
    """Remove old backups exceeding max_backups. Returns count removed."""
    backups = list_backups(original_path, config)
    if len(backups) <= config.max_backups:
        return 0

    to_remove = backups[: len(backups) - config.max_backups]
    removed = 0
    for b in to_remove:
        try:
            os.remove(b.path)
            removed += 1
        except OSError as e:
            logger.warning("Failed to remove old backup %s: %s", b.path, e)

    return removed


def atomic_write(path: str, content: str, *, backup_config: BackupConfig | None = None) -> None:
    """Write content to a file atomically with optional backup.

    Writes to a temporary file first, then renames to target.
    """
    cfg = backup_config or BackupConfig()
    create_backup(path, cfg)

    tmp_path = f"{path}.tmp.{os.getpid()}"
    try:
        with open(tmp_path, "w") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise
