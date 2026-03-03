"""acpx runtime — ACP runtime backend via external ``acpx`` CLI.

Ported from ``extensions/acpx/src/runtime.ts``.
Spawns ``acpx`` as a subprocess and communicates via JSON-lines stdout.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import shutil
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from pyclaw.acp.control_plane import (
    AcpRuntimeEvent,
    AcpRuntimeProtocol,
    AcpRunTurnInput,
    AcpSessionResolution,
    AcpSessionStatus,
)

logger = logging.getLogger(__name__)

ACPX_BACKEND_ID = "acpx"
ACPX_HANDLE_PREFIX = "acpx:v1:"
ACPX_PINNED_VERSION = "0.1.13"
DEFAULT_AGENT_FALLBACK = "codex"

PERMISSION_MODES = ("approve-all", "approve-reads", "deny-all")
NON_INTERACTIVE_POLICIES = ("deny", "fail")


@dataclass
class AcpxConfig:
    """Resolved configuration for the acpx runtime."""

    command: str = "acpx"
    cwd: str = "."
    permission_mode: str = "approve-reads"
    non_interactive_permissions: str = "fail"
    timeout_seconds: float | None = None
    queue_owner_ttl_seconds: float = 0.1


@dataclass
class AcpxHandleState:
    """Encoded state for an acpx session handle."""

    name: str
    agent: str
    cwd: str
    mode: str = "persistent"
    acpx_record_id: str | None = None
    backend_session_id: str | None = None
    agent_session_id: str | None = None


def encode_handle_state(state: AcpxHandleState) -> str:
    payload = json.dumps(
        {
            "name": state.name,
            "agent": state.agent,
            "cwd": state.cwd,
            "mode": state.mode,
            **({"acpxRecordId": state.acpx_record_id} if state.acpx_record_id else {}),
            **({"backendSessionId": state.backend_session_id} if state.backend_session_id else {}),
            **({"agentSessionId": state.agent_session_id} if state.agent_session_id else {}),
        }
    )
    encoded = base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")
    return f"{ACPX_HANDLE_PREFIX}{encoded}"


def decode_handle_state(runtime_session_name: str) -> AcpxHandleState | None:
    trimmed = runtime_session_name.strip()
    if not trimmed.startswith(ACPX_HANDLE_PREFIX):
        return None
    encoded = trimmed[len(ACPX_HANDLE_PREFIX) :]
    if not encoded:
        return None
    # Restore padding
    padding = 4 - len(encoded) % 4
    if padding != 4:
        encoded += "=" * padding
    try:
        raw = base64.urlsafe_b64decode(encoded).decode()
        data = json.loads(raw)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    name = (data.get("name") or "").strip()
    agent = (data.get("agent") or "").strip()
    cwd = (data.get("cwd") or "").strip()
    mode = (data.get("mode") or "").strip()
    if not name or not agent or not cwd or mode not in ("persistent", "oneshot"):
        return None
    return AcpxHandleState(
        name=name,
        agent=agent,
        cwd=cwd,
        mode=mode,
        acpx_record_id=data.get("acpxRecordId"),
        backend_session_id=data.get("backendSessionId"),
        agent_session_id=data.get("agentSessionId"),
    )


def resolve_acpx_config(
    raw_config: dict[str, Any] | None = None, workspace_dir: str = ""
) -> AcpxConfig:
    """Resolve acpx plugin config, finding the acpx binary."""
    cfg = raw_config or {}
    command = shutil.which("acpx") or "acpx"
    import os

    cwd = os.path.abspath(cfg.get("cwd", workspace_dir or os.getcwd()))
    return AcpxConfig(
        command=command,
        cwd=cwd,
        permission_mode=cfg.get("permissionMode", "approve-reads"),
        non_interactive_permissions=cfg.get("nonInteractivePermissions", "fail"),
        timeout_seconds=cfg.get("timeoutSeconds"),
        queue_owner_ttl_seconds=cfg.get("queueOwnerTtlSeconds", 0.1),
    )


async def _spawn_and_collect(command: str, args: list[str], cwd: str) -> tuple[int, str, str]:
    proc = await asyncio.create_subprocess_exec(
        command,
        *args,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    return proc.returncode or 0, stdout.decode(), stderr.decode()


async def check_acpx_version(command: str, cwd: str) -> bool:
    """Check that the acpx CLI is available and matches expected version."""
    try:
        code, stdout, _ = await _spawn_and_collect(command, ["--version"], cwd)
        if code != 0:
            return False
        version = stdout.strip()
        return ACPX_PINNED_VERSION in version
    except Exception:
        return False


class AcpxRuntime(AcpRuntimeProtocol):
    """ACP runtime backend that delegates to the ``acpx`` CLI."""

    def __init__(self, config: AcpxConfig) -> None:
        self._config = config
        self._healthy = False

    def is_healthy(self) -> bool:
        return self._healthy

    async def probe_availability(self) -> None:
        self._healthy = await check_acpx_version(self._config.command, self._config.cwd)
        if not self._healthy:
            logger.warning("acpx CLI not available or version mismatch")

    async def ensure_session(
        self,
        session_key: str,
        agent: str,
        cwd: str,
        mode: str = "persistent",
        sandbox_config: dict[str, Any] | None = None,
    ) -> AcpSessionResolution:
        if not agent:
            raise ValueError("ACP agent id is required")
        effective_cwd = cwd or self._config.cwd

        args = self._build_control_args(
            effective_cwd,
            [agent, "sessions", "ensure", "--name", session_key],
        )
        events = await self._run_control_command(args, effective_cwd)

        acpx_record_id: str | None = None
        backend_session_id: str | None = None
        agent_session_id: str | None = None
        for evt in events:
            acpx_record_id = acpx_record_id or evt.get("acpxRecordId")
            backend_session_id = backend_session_id or evt.get("acpxSessionId")
            agent_session_id = agent_session_id or evt.get("agentSessionId")

        state = AcpxHandleState(
            name=session_key,
            agent=agent,
            cwd=effective_cwd,
            mode=mode,
            acpx_record_id=acpx_record_id,
            backend_session_id=backend_session_id,
            agent_session_id=agent_session_id,
        )
        return AcpSessionResolution(
            session_key=session_key,
            backend=ACPX_BACKEND_ID,
            runtime_session_name=encode_handle_state(state),
            cwd=effective_cwd,
            acpx_record_id=acpx_record_id,
            backend_session_id=backend_session_id,
            agent_session_id=agent_session_id,
        )

    async def run_turn(self, input: AcpRunTurnInput) -> AsyncIterator[AcpRuntimeEvent]:
        state = decode_handle_state(input.handle.runtime_session_name)
        if not state:
            yield AcpRuntimeEvent(type="error", text="Invalid acpx handle state")
            return

        args = self._build_prompt_args(state.agent, state.cwd, input.prompt)
        proc = await asyncio.create_subprocess_exec(
            self._config.command,
            *args,
            cwd=state.cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        if proc.stdout:
            async for line_bytes in proc.stdout:
                line = line_bytes.decode().strip()
                if not line:
                    continue
                event = self._parse_json_line(line)
                if event:
                    yield event
                    if event.type in ("done", "error"):
                        break

                if input.abort_event and input.abort_event.is_set():
                    proc.terminate()
                    yield AcpRuntimeEvent(type="done", text="Cancelled")
                    break

        await proc.wait()

    async def get_status(self, handle: AcpSessionResolution) -> AcpSessionStatus:
        state = decode_handle_state(handle.runtime_session_name)
        if not state:
            return AcpSessionStatus(session_key=handle.session_key, backend=ACPX_BACKEND_ID)

        args = self._build_control_args(state.cwd, [state.agent, "status"])
        try:
            events = await self._run_control_command(args, state.cwd)
            is_active = any(e.get("status") == "active" for e in events)
        except Exception:
            is_active = False

        return AcpSessionStatus(
            session_key=handle.session_key,
            backend=ACPX_BACKEND_ID,
            mode=state.mode,
            is_active=is_active,
        )

    async def cancel(self, handle: AcpSessionResolution) -> None:
        state = decode_handle_state(handle.runtime_session_name)
        if not state:
            return
        args = self._build_control_args(state.cwd, [state.agent, "cancel"])
        try:
            await self._run_control_command(args, state.cwd)
        except Exception:
            logger.warning("Failed to cancel acpx session %s", handle.session_key)

    async def close(self, handle: AcpSessionResolution) -> None:
        pass  # acpx sessions are managed by the CLI

    def _build_control_args(self, cwd: str, command: list[str]) -> list[str]:
        args = ["--format", "json", "--json-strict"]
        if self._config.permission_mode:
            args.extend(["--permission-mode", self._config.permission_mode])
        args.extend(command)
        return args

    def _build_prompt_args(self, agent: str, cwd: str, prompt: str) -> list[str]:
        args = self._build_control_args(cwd, [agent, "prompt"])
        args.extend(["--message", prompt])
        if self._config.timeout_seconds:
            args.extend(["--timeout", str(int(self._config.timeout_seconds))])
        return args

    async def _run_control_command(self, args: list[str], cwd: str) -> list[dict[str, Any]]:
        code, stdout, stderr = await _spawn_and_collect(self._config.command, args, cwd)
        if code != 0:
            raise RuntimeError(f"acpx command failed (exit {code}): {stderr.strip()}")
        events: list[dict[str, Any]] = []
        for line in stdout.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                pass
        return events

    @staticmethod
    def _parse_json_line(line: str) -> AcpRuntimeEvent | None:
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            return None
        if not isinstance(data, dict):
            return None

        evt_type = data.get("type", "")
        if evt_type == "message":
            return AcpRuntimeEvent(type="text", text=data.get("content", ""))
        if evt_type == "tool_use":
            return AcpRuntimeEvent(type="tool_start", name=data.get("name", ""), data=data)
        if evt_type == "tool_result":
            return AcpRuntimeEvent(type="tool_end", name=data.get("name", ""), data=data)
        if evt_type == "done":
            return AcpRuntimeEvent(type="done")
        if evt_type == "error":
            return AcpRuntimeEvent(type="error", text=data.get("message", "unknown error"))
        # Pass through unrecognized events
        if evt_type:
            return AcpRuntimeEvent(type=evt_type, data=data)
        return None
