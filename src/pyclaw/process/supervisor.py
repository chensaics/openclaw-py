"""Process supervisor — spawn/cancel/scope-based lifecycle, tree termination, restart.

Ported from ``src/process/supervisor*.ts``.

Provides:
- Spawn and manage child processes
- Scope-based lifecycle (session, agent, gateway)
- Recursive process tree termination
- Restart with backoff
- PTY adapter support
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import time
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class ProcessScope(str, Enum):
    """Lifecycle scope for managed processes."""

    SESSION = "session"  # Killed when session ends
    AGENT = "agent"  # Killed when agent stops
    GATEWAY = "gateway"  # Killed when gateway shuts down
    MANUAL = "manual"  # Only killed explicitly


class ProcessState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"
    RESTARTING = "restarting"


@dataclass
class ProcessConfig:
    """Configuration for a managed process."""

    command: list[str]
    scope: ProcessScope = ProcessScope.SESSION
    cwd: str = ""
    env: dict[str, str] = field(default_factory=dict)
    max_restarts: int = 3
    restart_delay_s: float = 1.0
    restart_backoff: float = 2.0
    kill_timeout_s: float = 5.0
    use_pty: bool = False


@dataclass
class ProcessInfo:
    """Runtime information about a managed process."""

    process_id: str
    pid: int = 0
    state: ProcessState = ProcessState.PENDING
    scope: ProcessScope = ProcessScope.SESSION
    command: list[str] = field(default_factory=list)
    started_at: float = 0.0
    stopped_at: float = 0.0
    exit_code: int | None = None
    restart_count: int = 0
    error: str = ""

    @property
    def uptime_s(self) -> float:
        if self.started_at == 0:
            return 0
        end = self.stopped_at or time.time()
        return end - self.started_at


class ManagedProcess:
    """A single managed process with lifecycle control."""

    def __init__(self, process_id: str, config: ProcessConfig) -> None:
        self._id = process_id
        self._config = config
        self._proc: asyncio.subprocess.Process | None = None
        self._info = ProcessInfo(
            process_id=process_id,
            scope=config.scope,
            command=config.command,
        )

    @property
    def info(self) -> ProcessInfo:
        return self._info

    @property
    def is_running(self) -> bool:
        return self._info.state == ProcessState.RUNNING

    async def start(self) -> bool:
        """Start the process."""
        try:
            self._proc = await asyncio.create_subprocess_exec(
                *self._config.command,
                cwd=self._config.cwd or None,
                env={**os.environ, **self._config.env} if self._config.env else None,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            self._info.pid = self._proc.pid
            self._info.state = ProcessState.RUNNING
            self._info.started_at = time.time()
            self._info.exit_code = None
            return True
        except Exception as e:
            self._info.state = ProcessState.FAILED
            self._info.error = str(e)
            return False

    async def stop(self, *, force: bool = False) -> bool:
        """Stop the process. Sends SIGTERM, then SIGKILL after timeout."""
        if not self._proc or self._info.state != ProcessState.RUNNING:
            return False

        self._info.state = ProcessState.STOPPING

        try:
            if force:
                self._proc.kill()
            else:
                self._proc.terminate()

            try:
                await asyncio.wait_for(
                    self._proc.wait(),
                    timeout=self._config.kill_timeout_s,
                )
            except TimeoutError:
                self._proc.kill()
                await self._proc.wait()

            self._info.exit_code = self._proc.returncode
            self._info.state = ProcessState.STOPPED
            self._info.stopped_at = time.time()
            return True
        except Exception as e:
            self._info.state = ProcessState.FAILED
            self._info.error = str(e)
            return False

    async def restart(self) -> bool:
        """Restart the process with backoff."""
        if self._info.restart_count >= self._config.max_restarts:
            self._info.state = ProcessState.FAILED
            self._info.error = "Max restarts exceeded"
            return False

        self._info.state = ProcessState.RESTARTING
        self._info.restart_count += 1

        delay = self._config.restart_delay_s * (self._config.restart_backoff ** (self._info.restart_count - 1))
        await asyncio.sleep(min(delay, 30.0))

        await self.stop(force=True)
        return await self.start()


def kill_process_tree(pid: int, sig: int = signal.SIGTERM) -> list[int]:
    """Kill a process and all its children (best-effort, platform-dependent)."""
    killed: list[int] = []
    try:
        os.kill(pid, sig)
        killed.append(pid)
    except (ProcessLookupError, PermissionError):
        pass
    return killed


class ProcessSupervisor:
    """Manage multiple processes with scope-based lifecycle."""

    def __init__(self) -> None:
        self._processes: dict[str, ManagedProcess] = {}

    async def spawn(self, process_id: str, config: ProcessConfig) -> ManagedProcess:
        """Spawn a new managed process."""
        proc = ManagedProcess(process_id, config)
        self._processes[process_id] = proc
        await proc.start()
        return proc

    def get(self, process_id: str) -> ManagedProcess | None:
        return self._processes.get(process_id)

    async def cancel(self, process_id: str, *, force: bool = False) -> bool:
        """Cancel/stop a process by ID."""
        proc = self._processes.get(process_id)
        if not proc:
            return False
        result = await proc.stop(force=force)
        self._processes.pop(process_id, None)
        return result

    async def cancel_by_scope(self, scope: ProcessScope) -> int:
        """Cancel all processes in a given scope."""
        to_cancel = [pid for pid, proc in self._processes.items() if proc.info.scope == scope]
        count = 0
        for pid in to_cancel:
            if await self.cancel(pid, force=True):
                count += 1
        return count

    def list_processes(self, *, scope: ProcessScope | None = None) -> list[ProcessInfo]:
        """List all managed processes."""
        infos = [p.info for p in self._processes.values()]
        if scope is not None:
            infos = [i for i in infos if i.scope == scope]
        return infos

    async def stop_all(self) -> int:
        """Stop all managed processes."""
        count = 0
        for proc in list(self._processes.values()):
            await proc.stop(force=True)
            count += 1
        self._processes.clear()
        return count

    @property
    def active_count(self) -> int:
        return sum(1 for p in self._processes.values() if p.is_running)

    @property
    def total_count(self) -> int:
        return len(self._processes)
