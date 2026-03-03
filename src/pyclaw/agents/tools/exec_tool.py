"""Shell execution tool — run commands in a subprocess.

Enhanced with security policy (env sanitization), command approval,
and background process support.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

from pyclaw.agents.tools.base import BaseTool
from pyclaw.agents.types import ToolResult

_DEFAULT_TIMEOUT = 120  # seconds
_MAX_OUTPUT_BYTES = 256 * 1024  # 256 KiB


def _load_security_policy() -> dict[str, Any]:
    """Load the host environment security policy."""
    policy_path = Path(__file__).parent / "host-env-security-policy.json"
    if policy_path.exists():
        result: dict[str, Any] = json.loads(policy_path.read_text(encoding="utf-8"))
        return result
    return {"blockedKeys": [], "blockedPrefixes": [], "blockedOverrideKeys": []}


_SECURITY_POLICY = _load_security_policy()


def sanitize_env(env: dict[str, str] | None = None) -> dict[str, str]:
    """Remove blocked env vars per the security policy."""
    base = dict(env or os.environ)
    blocked_keys = set(_SECURITY_POLICY.get("blockedKeys", []))
    blocked_override = set(_SECURITY_POLICY.get("blockedOverrideKeys", []))
    blocked_prefixes = tuple(_SECURITY_POLICY.get("blockedPrefixes", []))

    sanitized: dict[str, str] = {}
    for key, value in base.items():
        if key in blocked_keys:
            continue
        if key in blocked_override:
            continue
        if blocked_prefixes and key.startswith(blocked_prefixes):
            continue
        sanitized[key] = value
    return sanitized


class ExecTool(BaseTool):
    """Execute a shell command and return stdout/stderr.

    Env vars are sanitized per the host-env-security-policy.json policy.
    """

    owner_only = True

    def __init__(
        self,
        *,
        workspace_root: str | None = None,
        timeout: int = _DEFAULT_TIMEOUT,
        allowed_commands: list[str] | None = None,
        require_approval: bool = False,
    ) -> None:
        self._workspace_root = workspace_root
        self._timeout = timeout
        self._allowed_commands = allowed_commands
        self._require_approval = require_approval
        self._pending_approvals: dict[str, str] = {}

    @property
    def name(self) -> str:
        return "exec"

    @property
    def description(self) -> str:
        return (
            "Execute a shell command. Returns stdout and stderr. "
            "The command runs in the workspace directory with a timeout. "
            "Supports background mode by setting background=true, "
            "which returns a PID that can be polled via the process tool."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to execute."},
                "timeout": {
                    "type": "integer",
                    "description": f"Timeout in seconds (default {_DEFAULT_TIMEOUT}).",
                },
                "working_directory": {
                    "type": "string",
                    "description": "Working directory for the command.",
                },
                "background": {
                    "type": "boolean",
                    "description": "Run in background, returning a PID (default false).",
                },
            },
            "required": ["command"],
        }

    async def execute(self, tool_call_id: str, arguments: dict[str, Any]) -> ToolResult:
        command = arguments.get("command", "")
        if not command:
            return ToolResult.text("Error: command is required.", is_error=True)

        if self._allowed_commands:
            first_word = command.strip().split()[0] if command.strip() else ""
            if first_word not in self._allowed_commands:
                return ToolResult.text(
                    f"Command '{first_word}' is not in the allowed list.",
                    is_error=True,
                )

        if self._require_approval:
            self._pending_approvals[tool_call_id] = command
            return ToolResult.text(
                f"Command requires approval: {command}\nApproval ID: " + tool_call_id,
                is_error=True,
            )

        background = arguments.get("background", False)
        timeout = arguments.get("timeout", self._timeout)
        cwd = arguments.get("working_directory", self._workspace_root)

        if cwd and not os.path.isdir(cwd):
            return ToolResult.text(f"Error: working directory does not exist: {cwd}", is_error=True)

        env = sanitize_env()

        from pyclaw.agents.progress import ProgressEvent, ProgressStatus, emit_progress

        task_id = f"exec-{tool_call_id[:8]}"
        emit_progress(
            ProgressEvent(
                task_id=task_id,
                status=ProgressStatus.STARTED,
                message=command[:80],
            )
        )

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=env,
            )

            if background:
                emit_progress(
                    ProgressEvent(
                        task_id=task_id,
                        status=ProgressStatus.PROGRESS,
                        progress=0.5,
                        message=f"Background PID {proc.pid}",
                    )
                )
                return ToolResult.text(
                    json.dumps(
                        {
                            "pid": proc.pid,
                            "status": "running",
                            "message": "Use the process tool to poll or kill this process.",
                        }
                    )
                )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout
                )
            except TimeoutError:
                proc.kill()
                await proc.wait()
                emit_progress(
                    ProgressEvent(
                        task_id=task_id,
                        status=ProgressStatus.FAILED,
                        message=f"Timed out after {timeout}s",
                    )
                )
                return ToolResult.text(
                    f"Command timed out after {timeout}s and was killed.",
                    is_error=True,
                )

        except Exception as e:
            emit_progress(
                ProgressEvent(
                    task_id=task_id,
                    status=ProgressStatus.FAILED,
                    message=str(e)[:80],
                )
            )
            return ToolResult.text(f"Error executing command: {e}", is_error=True)

        emit_progress(
            ProgressEvent(
                task_id=task_id,
                status=ProgressStatus.COMPLETED,
                progress=1.0,
                message=f"exit code {proc.returncode}",
            )
        )

        stdout = stdout_bytes.decode("utf-8", errors="replace")[:_MAX_OUTPUT_BYTES]
        stderr = stderr_bytes.decode("utf-8", errors="replace")[:_MAX_OUTPUT_BYTES]
        exit_code = proc.returncode

        parts: list[str] = []
        if stdout:
            parts.append(stdout)
        if stderr:
            parts.append(f"[stderr]\n{stderr}")
        parts.append(f"[exit code: {exit_code}]")

        return ToolResult.text("\n".join(parts), is_error=exit_code != 0)
