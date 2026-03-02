"""Node Host invoke handler — dispatch remote commands.

Routes incoming ``node.invoke.request`` events to the appropriate handler
(exec approvals, system.run, system.which, browser proxy).
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class InvokeRequest:
    id: str = ""
    node_id: str = ""
    command: str = ""
    params: dict[str, Any] | None = None
    timeout_ms: int = 30_000


@dataclass
class InvokeResult:
    id: str = ""
    success: bool = True
    result: Any = None
    error: str = ""


def sanitize_env(overrides: dict[str, str] | None = None) -> dict[str, str]:
    """Build a sanitized environment for subprocess execution."""
    env = dict(os.environ)
    # Remove potentially dangerous vars
    for key in ("LD_PRELOAD", "DYLD_INSERT_LIBRARIES", "PYTHONSTARTUP"):
        env.pop(key, None)
    if overrides:
        env.update(overrides)
    return env


async def handle_invoke(request: InvokeRequest) -> InvokeResult:
    """Central dispatcher for node invoke commands."""
    command = request.command
    params = request.params or {}

    try:
        if command == "system.which":
            return _handle_which(request, params)
        elif command == "system.run":
            return await _handle_system_run(request, params)
        elif command == "system.execApprovals.get":
            return _handle_exec_approvals_get(request)
        elif command == "system.execApprovals.set":
            return _handle_exec_approvals_set(request, params)
        else:
            return InvokeResult(id=request.id, success=False, error=f"Unknown command: {command}")
    except Exception as exc:
        return InvokeResult(id=request.id, success=False, error=str(exc))


def _handle_which(request: InvokeRequest, params: dict[str, Any]) -> InvokeResult:
    """Resolve binary paths."""
    bins = params.get("bins", [])
    results: dict[str, str | None] = {}
    for b in bins:
        results[b] = shutil.which(b)
    return InvokeResult(id=request.id, result=results)


async def _handle_system_run(request: InvokeRequest, params: dict[str, Any]) -> InvokeResult:
    """Execute a command with sandboxed environment."""
    cmd = params.get("command", "")
    if not cmd:
        return InvokeResult(id=request.id, success=False, error="No command")

    cwd = params.get("cwd")
    timeout = request.timeout_ms / 1000.0

    env = sanitize_env(params.get("env"))

    try:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
            env=env,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return InvokeResult(
            id=request.id,
            success=proc.returncode == 0,
            result={
                "exitCode": proc.returncode,
                "stdout": stdout.decode("utf-8", errors="replace")[:50_000],
                "stderr": stderr.decode("utf-8", errors="replace")[:10_000],
            },
        )
    except asyncio.TimeoutError:
        return InvokeResult(id=request.id, success=False, error="Timeout")


def _handle_exec_approvals_get(request: InvokeRequest) -> InvokeResult:
    from pyclaw.infra.exec_approvals import load_exec_approvals, _serialize_agent_config
    approvals = load_exec_approvals()
    data: dict[str, Any] = {"version": approvals.version}
    if approvals.defaults:
        data["defaults"] = _serialize_agent_config(approvals.defaults)
    data["agents"] = {k: _serialize_agent_config(v) for k, v in approvals.agents.items()}
    return InvokeResult(id=request.id, result=data)


def _handle_exec_approvals_set(request: InvokeRequest, params: dict[str, Any]) -> InvokeResult:
    from pyclaw.infra.exec_approvals import load_exec_approvals, save_exec_approvals, _parse_approvals
    approvals = _parse_approvals(params)
    save_exec_approvals(approvals)
    return InvokeResult(id=request.id, result={"ok": True})
