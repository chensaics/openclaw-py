"""schtasks backend — Windows scheduled task management."""

from __future__ import annotations

import asyncio
import logging

from pyclaw.daemon.service import GatewayServiceInstallArgs, GatewayServiceRuntime

logger = logging.getLogger(__name__)


class SchtasksService:
    """Windows schtasks-based service."""

    async def install(self, args: GatewayServiceInstallArgs) -> None:
        program = args.program
        full_args = " ".join(args.arguments)
        task_name = f"\\PyClaw\\{args.label}"
        cmd = f'schtasks /Create /TN "{task_name}" /TR "{program} {full_args}" /SC ONLOGON /RL HIGHEST /F'
        await _run(cmd)
        # Start immediately
        await _run(f'schtasks /Run /TN "{task_name}"')
        logger.info("Installed Windows scheduled task: %s", args.label)

    async def uninstall(self, label: str) -> None:
        task_name = f"\\PyClaw\\{label}"
        await _run(f'schtasks /Delete /TN "{task_name}" /F')
        logger.info("Uninstalled Windows scheduled task: %s", label)

    async def stop(self, label: str) -> None:
        task_name = f"\\PyClaw\\{label}"
        await _run(f'schtasks /End /TN "{task_name}"')

    async def restart(self, label: str) -> None:
        await self.stop(label)
        task_name = f"\\PyClaw\\{label}"
        await _run(f'schtasks /Run /TN "{task_name}"')

    async def is_loaded(self, label: str) -> bool:
        task_name = f"\\PyClaw\\{label}"
        proc = await asyncio.create_subprocess_shell(
            f'schtasks /Query /TN "{task_name}"',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
        return proc.returncode == 0

    async def read_runtime(self, label: str) -> GatewayServiceRuntime:
        task_name = f"\\PyClaw\\{label}"
        proc = await asyncio.create_subprocess_shell(
            f'schtasks /Query /TN "{task_name}" /FO LIST /V',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        output = stdout.decode("utf-8", errors="replace")

        runtime = GatewayServiceRuntime()
        for line in output.splitlines():
            line = line.strip()
            if "Status:" in line:
                status_val = line.split(":", 1)[1].strip()
                runtime.status = "running" if status_val == "Running" else "stopped"
            elif "Last Result:" in line:
                try:
                    runtime.last_exit_code = int(line.split(":", 1)[1].strip())
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
