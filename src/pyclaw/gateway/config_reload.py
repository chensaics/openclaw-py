"""Gateway config hot-reload — file watching, diff, hot/restart strategies.

Ported from ``src/gateway/config-reload.ts``.

Provides:
- File watcher for config changes (watchdog-compatible interface)
- Config diff detection (added/removed/changed keys)
- Hot-reload vs restart strategy selection
- Channel/plugin reload prefix matching
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ReloadStrategy(str, Enum):
    HOT = "hot"  # Apply changes without restart
    RESTART = "restart"  # Full gateway restart required
    IGNORE = "ignore"  # No action needed


class ChangeType(str, Enum):
    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"


@dataclass
class ConfigChange:
    """A single config key change."""

    key: str
    change_type: ChangeType
    old_value: Any = None
    new_value: Any = None


@dataclass
class ConfigDiff:
    """Diff between two config snapshots."""

    changes: list[ConfigChange] = field(default_factory=list)
    strategy: ReloadStrategy = ReloadStrategy.IGNORE
    timestamp: float = 0.0

    @property
    def has_changes(self) -> bool:
        return len(self.changes) > 0

    @property
    def change_count(self) -> int:
        return len(self.changes)


# Keys that require full restart
RESTART_KEYS = frozenset(
    {
        "gateway.port",
        "gateway.bind",
        "gateway.tls",
        "gateway.mode",
        "daemon",
    }
)

# Keys safe for hot reload
HOT_RELOAD_PREFIXES = (
    "channels.",
    "plugins.",
    "hooks.",
    "agents.model",
    "agents.tools",
    "agents.skills",
    "session.",
    "cron.",
)


def flatten_dict(d: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    """Flatten a nested dict into dot-separated keys."""
    result: dict[str, Any] = {}
    for k, v in d.items():
        full_key = f"{prefix}{k}" if prefix else k
        if isinstance(v, dict):
            result.update(flatten_dict(v, f"{full_key}."))
        else:
            result[full_key] = v
    return result


def compute_config_diff(old: dict[str, Any], new: dict[str, Any]) -> ConfigDiff:
    """Compute diff between two config snapshots."""
    old_flat = flatten_dict(old)
    new_flat = flatten_dict(new)
    changes: list[ConfigChange] = []

    all_keys = set(old_flat.keys()) | set(new_flat.keys())
    for key in sorted(all_keys):
        if key not in old_flat:
            changes.append(ConfigChange(key=key, change_type=ChangeType.ADDED, new_value=new_flat[key]))
        elif key not in new_flat:
            changes.append(ConfigChange(key=key, change_type=ChangeType.REMOVED, old_value=old_flat[key]))
        elif old_flat[key] != new_flat[key]:
            changes.append(
                ConfigChange(
                    key=key,
                    change_type=ChangeType.MODIFIED,
                    old_value=old_flat[key],
                    new_value=new_flat[key],
                )
            )

    strategy = determine_strategy(changes)
    return ConfigDiff(changes=changes, strategy=strategy, timestamp=time.time())


def determine_strategy(changes: list[ConfigChange]) -> ReloadStrategy:
    """Determine reload strategy from a set of changes."""
    if not changes:
        return ReloadStrategy.IGNORE

    for change in changes:
        if change.key in RESTART_KEYS:
            return ReloadStrategy.RESTART
        if any(change.key.startswith(p) for p in ("gateway.",)):
            if change.key not in RESTART_KEYS:
                continue
            return ReloadStrategy.RESTART

    for change in changes:
        if any(change.key.startswith(p) for p in HOT_RELOAD_PREFIXES):
            return ReloadStrategy.HOT

    return ReloadStrategy.HOT


def file_hash(path: str | Path) -> str:
    """Compute SHA-256 hash of a file."""
    try:
        data = Path(path).read_bytes()
        return hashlib.sha256(data).hexdigest()
    except OSError:
        return ""


@dataclass
class WatcherConfig:
    """Configuration for the config file watcher."""

    config_path: str = ""
    poll_interval_s: float = 2.0
    debounce_s: float = 0.5
    enabled: bool = True


ReloadCallback = Callable[[ConfigDiff], None]


class ConfigFileWatcher:
    """Watch a config file for changes and trigger reload."""

    def __init__(self, config: WatcherConfig) -> None:
        self._config = config
        self._last_hash = ""
        self._last_snapshot: dict[str, Any] = {}
        self._callbacks: list[ReloadCallback] = []
        self._running = False
        self._last_change_time = 0.0
        self._reload_count = 0

    def on_change(self, callback: ReloadCallback) -> None:
        self._callbacks.append(callback)

    def start(self) -> None:
        """Start watching (sets initial snapshot)."""
        if not self._config.enabled or not self._config.config_path:
            return
        self._last_hash = file_hash(self._config.config_path)
        self._last_snapshot = self._load_config()
        self._running = True

    def stop(self) -> None:
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def reload_count(self) -> int:
        return self._reload_count

    def check(self) -> ConfigDiff | None:
        """Poll for changes. Returns diff if changed, None otherwise."""
        if not self._running:
            return None

        current_hash = file_hash(self._config.config_path)
        if current_hash == self._last_hash:
            return None

        now = time.time()
        if now - self._last_change_time < self._config.debounce_s:
            return None

        new_snapshot = self._load_config()
        diff = compute_config_diff(self._last_snapshot, new_snapshot)

        if diff.has_changes:
            self._last_hash = current_hash
            self._last_snapshot = new_snapshot
            self._last_change_time = now
            self._reload_count += 1

            for cb in self._callbacks:
                try:
                    cb(diff)
                except Exception as e:
                    logger.error("Reload callback error: %s", e)

            return diff

        self._last_hash = current_hash
        return None

    def _load_config(self) -> dict[str, Any]:
        try:
            text = Path(self._config.config_path).read_text(encoding="utf-8")
            result: dict[str, Any] = json.loads(text)
            return result
        except Exception:
            return {}
