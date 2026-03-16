"""systemd backend — Linux systemd user service management."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from pyclaw.constants.runtime import STATUS_ACTIVE, STATUS_RUNNING, STATUS_STOPPED
from pyclaw.daemon.service import GatewayServiceInstallArgs, GatewayServiceRuntime

logger = logging.getLogger(__name__)


def _systemd_user_dir() -> Path:
    return Path.home() / ".config" / "systemd" / "user"


def _unit_name(label: str) -> str:
    return label.replace(".", "-") + ".service"


def _build_unit(args: GatewayServiceInstallArgs) -> str:
    """Build a systemd unit file."""
    program = args.program
    full_cmd = f"{program} {' '.join(args.arguments)}" if args.arguments else program
    env_lines = "\n".join(f"Environment={k}={v}" for k, v in args.environment.items())

    return f"""[Unit]
Description=pyclaw Gateway
After=network.target

[Service]
Type=simple
ExecStart={full_cmd}
WorkingDirectory={args.working_directory or str(Path.home())}
Restart=on-failure
RestartSec=10
{env_lines}

[Install]
WantedBy=default.target
"""


class SystemdService:
    """Linux systemd user service."""

    async def install(self, args: GatewayServiceInstallArgs) -> None:
        unit_dir = _systemd_user_dir()
        unit_dir.mkdir(parents=True, exist_ok=True)
        unit_path = unit_dir / _unit_name(args.label)

        unit_content = _build_unit(args)
        unit_path.write_text(unit_content)

        await _run("systemctl --user daemon-reload")
        await _run(f"systemctl --user enable {_unit_name(args.label)}")
        await _run(f"systemctl --user start {_unit_name(args.label)}")
        logger.info("Installed systemd service: %s", args.label)

    async def uninstall(self, label: str) -> None:
        name = _unit_name(label)
        await _run(f"systemctl --user stop {name}")
        await _run(f"systemctl --user disable {name}")
        path = _systemd_user_dir() / name
        if path.exists():
            path.unlink()
        await _run("systemctl --user daemon-reload")
        logger.info("Uninstalled systemd service: %s", label)

    async def stop(self, label: str) -> None:
        await _run(f"systemctl --user stop {_unit_name(label)}")

    async def restart(self, label: str) -> None:
        await _run(f"systemctl --user restart {_unit_name(label)}")

    async def is_loaded(self, label: str) -> bool:
        proc = await asyncio.create_subprocess_shell(
            f"systemctl --user is-active {_unit_name(label)}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        return stdout.decode().strip() == STATUS_ACTIVE

    async def read_runtime(self, label: str) -> GatewayServiceRuntime:
        proc = await asyncio.create_subprocess_shell(
            f"systemctl --user show {_unit_name(label)} --property=ActiveState,MainPID,ExecMainStatus",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        output = stdout.decode()

        runtime = GatewayServiceRuntime()
        for line in output.splitlines():
            if line.startswith("ActiveState="):
                state = line.split("=")[1]
                runtime.status = STATUS_RUNNING if state == STATUS_ACTIVE else STATUS_STOPPED
            elif line.startswith("MainPID="):
                try:
                    runtime.pid = int(line.split("=")[1])
                except ValueError:
                    pass
            elif line.startswith("ExecMainStatus="):
                try:
                    runtime.last_exit_code = int(line.split("=")[1])
                except ValueError:
                    pass
        return runtime


async def _run(cmd: str) -> None:
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await proc.communicate()
