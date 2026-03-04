"""CLI sessions command (root surface + JSON/text output)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

import typer

from pyclaw.config.paths import resolve_agents_dir


@dataclass
class SessionEntry:
    agent_id: str
    key: str
    path: str
    updated_at: float


def sessions_command(
    *,
    output_json: bool = False,
    active_minutes: int | None = None,
    store: str = "",
    agent: str = "",
    all_agents: bool = False,
    verbose: bool = False,
) -> None:
    """List stored sessions with optional filters."""
    _ = verbose
    entries = _collect_sessions(store=store, agent=agent, all_agents=all_agents)

    if active_minutes is not None:
        cutoff = datetime.now().timestamp() - (active_minutes * 60)
        entries = [e for e in entries if e.updated_at >= cutoff]

    if output_json:
        payload = {
            "count": len(entries),
            "activeMinutes": active_minutes,
            "allAgents": all_agents,
            "sessions": [asdict(e) for e in entries],
        }
        typer.echo(json.dumps(payload, ensure_ascii=False))
        return

    if not entries:
        typer.echo("No sessions found.")
        return
    for entry in entries:
        typer.echo(f"{entry.agent_id}/{entry.key}")


def _collect_sessions(*, store: str, agent: str, all_agents: bool) -> list[SessionEntry]:
    if store:
        return _collect_from_store_path(Path(store).expanduser())

    agents_dir = resolve_agents_dir()
    if not agents_dir.exists():
        return []

    if agent:
        return _collect_from_agent_dir(agents_dir / agent, agent_id=agent)

    if all_agents:
        entries: list[SessionEntry] = []
        for agent_dir in sorted(d for d in agents_dir.iterdir() if d.is_dir()):
            entries.extend(_collect_from_agent_dir(agent_dir, agent_id=agent_dir.name))
        return entries

    # Default scope: main agent
    default_agent = agents_dir / "main"
    if default_agent.exists():
        return _collect_from_agent_dir(default_agent, agent_id="main")

    # Fallback to all available if main doesn't exist.
    fallback_entries: list[SessionEntry] = []
    for agent_dir in sorted(d for d in agents_dir.iterdir() if d.is_dir()):
        fallback_entries.extend(_collect_from_agent_dir(agent_dir, agent_id=agent_dir.name))
    return fallback_entries


def _collect_from_store_path(store_path: Path) -> list[SessionEntry]:
    if store_path.is_dir():
        files = sorted(store_path.glob("*.jsonl"))
        return [
            SessionEntry(
                agent_id="custom",
                key=f.stem,
                path=str(f),
                updated_at=f.stat().st_mtime,
            )
            for f in files
        ]
    if store_path.is_file():
        return [
            SessionEntry(
                agent_id="custom",
                key=store_path.stem,
                path=str(store_path),
                updated_at=store_path.stat().st_mtime,
            )
        ]
    return []


def _collect_from_agent_dir(agent_dir: Path, *, agent_id: str) -> list[SessionEntry]:
    sessions_dir = agent_dir / "sessions"
    if not sessions_dir.exists():
        return []
    entries: list[SessionEntry] = []
    for session_file in sorted(sessions_dir.glob("*.jsonl")):
        stat = session_file.stat()
        entries.append(
            SessionEntry(
                agent_id=agent_id,
                key=session_file.stem,
                path=str(session_file),
                updated_at=stat.st_mtime,
            )
        )
    return entries


# ---------------------------------------------------------------------------
# sessions cleanup
# ---------------------------------------------------------------------------


def sessions_cleanup_command(
    *,
    dry_run: bool = False,
    enforce: bool = False,
    active_key: str = "",
    store: str = "",
    agent: str = "",
    all_agents: bool = True,
    output_json: bool = False,
) -> None:
    """Clean up stale sessions (locks, zero-byte files, very old sessions)."""
    import time

    agents_dir = resolve_agents_dir()
    if store:
        targets = [Path(store).expanduser()]
    elif agent:
        targets = [agents_dir / agent / "sessions"]
    elif all_agents and agents_dir.exists():
        targets = [d / "sessions" for d in agents_dir.iterdir() if d.is_dir()]
    else:
        targets = [agents_dir / "main" / "sessions"]

    stale_locks: list[Path] = []
    empty_files: list[Path] = []
    old_sessions: list[Path] = []
    now = time.time()
    max_age_s = 30 * 86400  # 30 days

    for sessions_dir in targets:
        if not sessions_dir.exists():
            continue
        for f in sessions_dir.iterdir():
            if f.name.endswith(".lock"):
                stale_locks.append(f)
            elif f.suffix == ".jsonl" and f.stat().st_size == 0:
                empty_files.append(f)
            elif f.suffix == ".jsonl" and (now - f.stat().st_mtime) > max_age_s:
                if active_key and f.stem == active_key:
                    continue
                old_sessions.append(f)

    candidates = stale_locks + empty_files
    if enforce:
        candidates += old_sessions

    if output_json:
        result = {
            "dryRun": dry_run,
            "staleLocks": len(stale_locks),
            "emptyFiles": len(empty_files),
            "oldSessions": len(old_sessions),
            "toRemove": len(candidates),
            "paths": [str(p) for p in candidates],
        }
        if not dry_run:
            removed = _remove_files(candidates)
            result["removed"] = removed
        typer.echo(json.dumps(result, ensure_ascii=False))
        return

    if not candidates:
        typer.echo("No stale sessions to clean up.")
        return

    typer.echo(
        f"Found: {len(stale_locks)} lock(s), {len(empty_files)} empty file(s), {len(old_sessions)} old session(s)."
    )

    if dry_run:
        for p in candidates:
            typer.echo(f"  [dry-run] would remove {p}")
        return

    removed = _remove_files(candidates)
    typer.echo(f"Removed {removed} file(s).")


def _remove_files(files: list[Path]) -> int:
    count = 0
    for f in files:
        try:
            f.unlink()
            count += 1
        except Exception:
            pass
    return count
