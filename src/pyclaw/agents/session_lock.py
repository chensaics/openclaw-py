"""Session file lock — exclusive file-based locking with stale detection."""

from __future__ import annotations

import json
import os
import time
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

_STALE_MS = 30 * 60 * 1000  # 30 minutes
_MAX_HOLD_MS = 5 * 60 * 1000  # 5 minutes


def _is_process_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


class SessionLockError(Exception):
    pass


@contextmanager
def acquire_session_lock(
    session_path: Path,
    *,
    stale_ms: int = _STALE_MS,
) -> Generator[None, None, None]:
    """Acquire an exclusive lock on a session file.

    Uses a .lock sidecar file with O_CREAT|O_EXCL for atomicity.
    Automatically cleans up stale locks from dead processes.
    """
    lock_path = session_path.with_suffix(session_path.suffix + ".lock")

    # Check and clean stale locks
    if lock_path.exists():
        try:
            lock_data = json.loads(lock_path.read_text(encoding="utf-8"))
            lock_pid = lock_data.get("pid", -1)
            created_at = lock_data.get("createdAt", 0)

            is_stale = (time.time() * 1000 - created_at) > stale_ms
            is_dead = not _is_process_alive(lock_pid)

            if is_stale or is_dead:
                lock_path.unlink(missing_ok=True)
        except (json.JSONDecodeError, OSError):
            lock_path.unlink(missing_ok=True)

    # Acquire
    try:
        fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        payload = json.dumps({"pid": os.getpid(), "createdAt": time.time() * 1000})
        os.write(fd, payload.encode("utf-8"))
        os.close(fd)
    except FileExistsError:
        raise SessionLockError(f"Session is locked by another process: {lock_path}") from None

    try:
        yield
    finally:
        lock_path.unlink(missing_ok=True)
