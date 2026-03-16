"""launchd backend — macOS LaunchAgent management."""

from __future__ import annotations

import asyncio
import logging
import os
import plistlib
import shutil
from pathlib import Path
from typing import Any

from pyclaw.constants.runtime import STATUS_RUNNING, STATUS_STOPPED
from pyclaw.daemon.service import GatewayServiceInstallArgs, GatewayServiceRuntime

logger = logging.getLogger(__name__)


def _launch_agents_dir() -> Path:
    return Path.home() / "Library" / "LaunchAgents"


def _plist_path(label: str) -> Path:
    return _launch_agents_dir() / f"{label}.plist"


def build_launch_agent_plist(args: GatewayServiceInstallArgs) -> dict[str, Any]:
    """Build a launchd plist dictionary."""
    program_args = [args.program, *args.arguments]
    plist: dict[str, Any] = {
        "Label": args.label,
        "ProgramArguments": program_args,
        "RunAtLoad": True,
        "KeepAlive": True,
        "ThrottleInterval": 10,
    }
    if args.working_directory:
        plist["WorkingDirectory"] = args.working_directory
    if args.environment:
        plist["EnvironmentVariables"] = args.environment

    log_dir = args.log_dir or str(Path.home() / ".pyclaw" / "logs")
    os.makedirs(log_dir, exist_ok=True)
    plist["StandardOutPath"] = os.path.join(log_dir, "gateway.stdout.log")
    plist["StandardErrorPath"] = os.path.join(log_dir, "gateway.stderr.log")

    return plist


class LaunchdService:
    """macOS launchd LaunchAgent."""

    async def install(self, args: GatewayServiceInstallArgs) -> None:
        plist = build_launch_agent_plist(args)
        path = _plist_path(args.label)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "wb") as f:
            plistlib.dump(plist, f)

        uid = os.getuid()
        await _run_cmd(f"launchctl bootstrap gui/{uid} {path}")
        logger.info("Installed LaunchAgent: %s", args.label)

    async def uninstall(self, label: str) -> None:
        uid = os.getuid()
        await _run_cmd(f"launchctl bootout gui/{uid}/{label}")

        path = _plist_path(label)
        if path.exists():
            trash = Path.home() / ".Trash" / path.name
            shutil.move(str(path), str(trash))
        logger.info("Uninstalled LaunchAgent: %s", label)

    async def stop(self, label: str) -> None:
        uid = os.getuid()
        await _run_cmd(f"launchctl kill SIGTERM gui/{uid}/{label}")

    async def restart(self, label: str) -> None:
        uid = os.getuid()
        await _run_cmd(f"launchctl kickstart -k gui/{uid}/{label}")

    async def is_loaded(self, label: str) -> bool:
        uid = os.getuid()
        proc = await asyncio.create_subprocess_shell(
            f"launchctl print gui/{uid}/{label}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
        return proc.returncode == 0

    async def read_runtime(self, label: str) -> GatewayServiceRuntime:
        uid = os.getuid()
        proc = await asyncio.create_subprocess_shell(
            f"launchctl print gui/{uid}/{label}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        output = stdout.decode("utf-8", errors="replace")

        runtime = GatewayServiceRuntime()
        if proc.returncode != 0:
            runtime.status = STATUS_STOPPED
            return runtime

        runtime.status = STATUS_RUNNING
        for line in output.splitlines():
            line = line.strip()
            if line.startswith("pid = "):
                try:
                    runtime.pid = int(line.split("=")[1].strip())
                except ValueError:
                    pass
            elif line.startswith("last exit code = "):
                try:
                    runtime.last_exit_code = int(line.split("=")[1].strip())
                except ValueError:
                    pass

        return runtime


async def _run_cmd(cmd: str) -> None:
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        logger.warning("launchctl command failed: %s — %s", cmd, stderr.decode())
