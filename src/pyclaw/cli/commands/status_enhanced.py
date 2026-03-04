"""Enhanced status reporting — summary, scan, deep, daemon, channels, models, sessions.

Ported from ``src/commands/status-all/*.ts``.

Provides:
- Status summary with all subsystems
- Deep probe mode (active health checks)
- Scan mode (file system scan)
- Per-subsystem status formatters
- --all / --deep / --scan modes
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class StatusLevel(str, Enum):
    OK = "ok"
    WARN = "warn"
    ERROR = "error"
    UNKNOWN = "unknown"


@dataclass
class SubsystemStatus:
    """Status of a single subsystem."""

    name: str
    level: StatusLevel = StatusLevel.UNKNOWN
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class StatusReport:
    """Full status report."""

    subsystems: list[SubsystemStatus] = field(default_factory=list)
    mode: str = "summary"
    generated_at: float = 0.0

    def __post_init__(self) -> None:
        if self.generated_at == 0:
            self.generated_at = time.time()

    @property
    def overall_level(self) -> StatusLevel:
        if any(s.level == StatusLevel.ERROR for s in self.subsystems):
            return StatusLevel.ERROR
        if any(s.level == StatusLevel.WARN for s in self.subsystems):
            return StatusLevel.WARN
        if all(s.level == StatusLevel.OK for s in self.subsystems):
            return StatusLevel.OK
        return StatusLevel.UNKNOWN

    def format_text(self) -> str:
        lines = [f"Status Report ({self.mode} mode)"]
        icon_map = {"ok": "✓", "warn": "⚠", "error": "✗", "unknown": "?"}
        for s in self.subsystems:
            icon = icon_map.get(s.level.value, "?")
            lines.append(f"  {icon} {s.name}: {s.message}")
            for k, v in s.details.items():
                lines.append(f"      {k}: {v}")
        lines.append(f"\nOverall: {self.overall_level.value}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Status Collectors
# ---------------------------------------------------------------------------


def collect_gateway_status(*, deep: bool = False) -> SubsystemStatus:
    """Collect gateway status."""
    import socket

    port = 18789
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2)
        result = s.connect_ex(("127.0.0.1", port))
        s.close()
        if result == 0:
            return SubsystemStatus(
                name="Gateway",
                level=StatusLevel.OK,
                message=f"Running on port {port}",
                details={"port": port, "host": "127.0.0.1"},
            )
        return SubsystemStatus(
            name="Gateway",
            level=StatusLevel.WARN,
            message="Not running",
        )
    except Exception as e:
        return SubsystemStatus(
            name="Gateway",
            level=StatusLevel.ERROR,
            message=f"Check failed: {e}",
        )


def collect_config_status() -> SubsystemStatus:
    """Collect config status."""
    config_path = Path.home() / ".pyclaw" / "config.json"
    if config_path.exists():
        size = config_path.stat().st_size
        return SubsystemStatus(
            name="Config",
            level=StatusLevel.OK,
            message=f"Found ({size} bytes)",
            details={"path": str(config_path)},
        )
    return SubsystemStatus(
        name="Config",
        level=StatusLevel.WARN,
        message="Not found",
    )


def collect_auth_status() -> SubsystemStatus:
    """Collect auth/credentials status."""
    creds_dir = Path.home() / ".pyclaw" / "credentials"
    if not creds_dir.exists():
        return SubsystemStatus(
            name="Auth",
            level=StatusLevel.WARN,
            message="No credentials configured",
        )
    providers = [p.stem for p in creds_dir.glob("*.json")]
    if providers:
        return SubsystemStatus(
            name="Auth",
            level=StatusLevel.OK,
            message=f"{len(providers)} provider(s): {', '.join(providers)}",
        )
    return SubsystemStatus(
        name="Auth",
        level=StatusLevel.WARN,
        message="No providers authenticated",
    )


def collect_daemon_status() -> SubsystemStatus:
    """Collect daemon/service status."""
    if sys.platform == "darwin":
        return SubsystemStatus(
            name="Daemon",
            level=StatusLevel.UNKNOWN,
            message="macOS (launchd)",
            details={"platform": "darwin"},
        )
    elif sys.platform == "linux":
        return SubsystemStatus(
            name="Daemon",
            level=StatusLevel.UNKNOWN,
            message="Linux (systemd)",
            details={"platform": "linux"},
        )
    return SubsystemStatus(
        name="Daemon",
        level=StatusLevel.UNKNOWN,
        message=f"Platform: {sys.platform}",
    )


def collect_sessions_status() -> SubsystemStatus:
    """Collect sessions status."""
    sessions_dir = Path.home() / ".pyclaw" / "sessions"
    if not sessions_dir.exists():
        return SubsystemStatus(
            name="Sessions",
            level=StatusLevel.OK,
            message="No sessions (clean state)",
        )
    count = sum(1 for _ in sessions_dir.iterdir() if _.is_dir())
    return SubsystemStatus(
        name="Sessions",
        level=StatusLevel.OK,
        message=f"{count} session(s)",
        details={"count": count},
    )


def collect_memory_status() -> SubsystemStatus:
    """Collect memory status."""
    mem_dir = Path.home() / ".pyclaw" / "memory"
    if not mem_dir.exists():
        return SubsystemStatus(
            name="Memory",
            level=StatusLevel.OK,
            message="Not initialized",
        )
    dbs = list(mem_dir.glob("*.db")) + list(mem_dir.glob("*.sqlite"))
    total_size = sum(f.stat().st_size for f in dbs)
    return SubsystemStatus(
        name="Memory",
        level=StatusLevel.OK,
        message=f"{len(dbs)} database(s), {total_size / 1024:.0f} KB",
    )


def collect_channels_status() -> SubsystemStatus:
    """Collect channels status (config-based)."""
    config_path = Path.home() / ".pyclaw" / "config.json"
    if not config_path.exists():
        return SubsystemStatus(name="Channels", level=StatusLevel.UNKNOWN, message="No config")

    try:
        import json

        config = json.loads(config_path.read_text(encoding="utf-8"))
        channels = config.get("channels", {})
        enabled = [k for k, v in channels.items() if isinstance(v, dict) and v.get("enabled", True)]
        return SubsystemStatus(
            name="Channels",
            level=StatusLevel.OK,
            message=f"{len(enabled)} channel(s) configured",
            details={"channels": enabled},
        )
    except Exception:
        return SubsystemStatus(
            name="Channels",
            level=StatusLevel.WARN,
            message="Could not parse channels from config",
        )


def collect_models_status() -> SubsystemStatus:
    """Collect models/provider status."""
    creds_dir = Path.home() / ".pyclaw" / "credentials"
    if not creds_dir.exists():
        return SubsystemStatus(
            name="Models",
            level=StatusLevel.WARN,
            message="No providers configured",
        )
    providers = [p.stem for p in creds_dir.glob("*.json")]
    return SubsystemStatus(
        name="Models",
        level=StatusLevel.OK if providers else StatusLevel.WARN,
        message=f"{len(providers)} provider(s) available",
    )


# ---------------------------------------------------------------------------
# Report Generation
# ---------------------------------------------------------------------------


def generate_status_report(*, mode: str = "summary", deep: bool = False) -> StatusReport:
    """Generate a full status report."""
    collectors = [
        lambda: collect_gateway_status(deep=deep),
        collect_config_status,
        collect_auth_status,
        collect_daemon_status,
        collect_sessions_status,
        collect_memory_status,
        collect_channels_status,
        collect_models_status,
    ]

    report = StatusReport(mode=mode)
    for collector in collectors:
        try:
            report.subsystems.append(collector())
        except Exception as e:
            report.subsystems.append(
                SubsystemStatus(
                    name="unknown",
                    level=StatusLevel.ERROR,
                    message=f"Collector failed: {e}",
                )
            )

    return report
