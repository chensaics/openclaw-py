"""Process tool — manage background exec sessions."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from pyclaw.agents.tools.base import BaseTool
from pyclaw.agents.types import ToolResult

_MAX_OUTPUT = 128 * 1024


class _BackgroundProcess:
    __slots__ = ("pid", "proc", "label", "stdout_buf", "stderr_buf", "done")

    def __init__(self, proc: asyncio.subprocess.Process, label: str) -> None:
        self.pid = proc.pid
        self.proc = proc
        self.label = label
        self.stdout_buf = bytearray()
        self.stderr_buf = bytearray()
        self.done = False


class ProcessTool(BaseTool):
    """Manage background exec sessions — start, poll, kill."""

    owner_only = True

    def __init__(self, *, workspace_root: str | None = None) -> None:
        self._workspace_root = workspace_root
        self._processes: dict[int, _BackgroundProcess] = {}

    @property
    def name(self) -> str:
        return "process"

    @property
    def description(self) -> str:
        return (
            "Manage background exec sessions. Start long-running commands, "
            "poll for output, or kill running processes. "
            "For long waits, use poll with a timeout instead of rapid loops."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Action: 'start', 'poll', 'kill', 'list'.",
                },
                "command": {
                    "type": "string",
                    "description": "Shell command to run (for 'start').",
                },
                "pid": {
                    "type": "integer",
                    "description": "Process ID (for 'poll' or 'kill').",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Poll timeout in milliseconds (for 'poll', default 5000).",
                },
            },
            "required": ["action"],
        }

    async def execute(self, tool_call_id: str, arguments: dict[str, Any]) -> ToolResult:
        action = arguments.get("action", "")

        if action == "list":
            items = []
            for proc_item in self._processes.values():
                items.append(
                    {
                        "pid": proc_item.pid,
                        "label": proc_item.label,
                        "done": proc_item.done,
                        "returncode": proc_item.proc.returncode,
                    }
                )
            return ToolResult.text(json.dumps(items, indent=2))

        if action == "start":
            command = arguments.get("command", "")
            if not command:
                return ToolResult.text("Error: command is required for start.", is_error=True)

            cwd = self._workspace_root
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )
            bp = _BackgroundProcess(proc, command[:80])
            self._processes[proc.pid or 0] = bp
            return ToolResult.text(json.dumps({"pid": proc.pid, "status": "started"}))

        if action == "poll":
            pid = arguments.get("pid")
            if pid is None:
                return ToolResult.text("Error: pid is required for poll.", is_error=True)
            bg_proc = self._processes.get(pid)
            if not bg_proc:
                return ToolResult.text(f"No tracked process with pid={pid}.", is_error=True)

            timeout_ms = arguments.get("timeout", 5000)
            try:
                await asyncio.wait_for(bg_proc.proc.wait(), timeout=timeout_ms / 1000.0)
                bg_proc.done = True
            except TimeoutError:
                pass

            stdout = b""
            stderr = b""
            if bg_proc.proc.stdout:
                try:
                    stdout = await asyncio.wait_for(bg_proc.proc.stdout.read(_MAX_OUTPUT), timeout=0.1)
                except TimeoutError:
                    pass
            if bg_proc.proc.stderr:
                try:
                    stderr = await asyncio.wait_for(bg_proc.proc.stderr.read(_MAX_OUTPUT), timeout=0.1)
                except TimeoutError:
                    pass

            return ToolResult.text(
                json.dumps(
                    {
                        "pid": pid,
                        "done": bg_proc.done,
                        "returncode": bg_proc.proc.returncode,
                        "stdout": stdout.decode("utf-8", errors="replace")[-_MAX_OUTPUT:]
                        if stdout
                        else "",
                        "stderr": stderr.decode("utf-8", errors="replace")[-_MAX_OUTPUT:]
                        if stderr
                        else "",
                    }
                )
            )

        if action == "kill":
            pid = arguments.get("pid")
            if pid is None:
                return ToolResult.text("Error: pid is required for kill.", is_error=True)
            bg_proc = self._processes.get(pid)
            if not bg_proc:
                return ToolResult.text(f"No tracked process with pid={pid}.", is_error=True)
            try:
                bg_proc.proc.kill()
                await bg_proc.proc.wait()
                bg_proc.done = True
            except ProcessLookupError:
                bg_proc.done = True
            return ToolResult.text(f"Process {pid} killed.")

        return ToolResult.text(f"Unknown action: {action}", is_error=True)
