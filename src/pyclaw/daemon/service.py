"""Platform-aware gateway service abstraction.

Selects launchd (macOS), systemd (Linux), or schtasks (Windows).
"""

from __future__ import annotations

import platform
from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class GatewayServiceInstallArgs:
    label: str = "ai.pyclaw.gateway"
    program: str = ""
    arguments: list[str] = field(default_factory=list)
    working_directory: str = ""
    environment: dict[str, str] = field(default_factory=dict)
    log_dir: str = ""


@dataclass
class GatewayServiceRuntime:
    status: str = "unknown"  # "running" | "stopped" | "unknown"
    pid: int | None = None
    last_exit_code: int | None = None


class GatewayService(Protocol):
    async def install(self, args: GatewayServiceInstallArgs) -> None: ...
    async def uninstall(self, label: str) -> None: ...
    async def stop(self, label: str) -> None: ...
    async def restart(self, label: str) -> None: ...
    async def is_loaded(self, label: str) -> bool: ...
    async def read_runtime(self, label: str) -> GatewayServiceRuntime: ...


def resolve_gateway_service() -> GatewayService:
    """Pick the right service backend for the current platform."""
    system = platform.system()
    if system == "Darwin":
        from pyclaw.daemon.launchd import LaunchdService

        return LaunchdService()
    elif system == "Linux":
        from pyclaw.daemon.systemd import SystemdService

        return SystemdService()
    elif system == "Windows":
        from pyclaw.daemon.schtasks import SchtasksService

        return SchtasksService()
    else:
        raise RuntimeError(f"Unsupported platform: {system}")
