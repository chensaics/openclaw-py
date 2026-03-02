"""CLI logs command — tail logs via Gateway RPC (preferred) or local file fallback."""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

import typer

from pyclaw.config.paths import resolve_state_dir


def logs_command(
    *,
    follow: bool = False,
    limit: int = 200,
    output_json: bool = False,
    plain: bool = False,
    no_color: bool = False,
    local_time: bool = False,
) -> None:
    """Tail gateway logs — tries RPC first, falls back to local file."""
    _ = (plain, no_color)

    if not follow:
        lines = _try_rpc_tail(limit=limit, output_json=output_json, local_time=local_time)
        if lines is not None:
            for line in lines:
                typer.echo(line)
            return

    # Fallback to local file
    log_path = resolve_state_dir() / "logs" / "pyclaw.log"
    _print_log_lines(log_path, limit=limit, output_json=output_json, local_time=local_time)
    if follow:
        _follow(log_path, output_json=output_json, local_time=local_time)


def _try_rpc_tail(*, limit: int, output_json: bool, local_time: bool) -> list[str] | None:
    """Attempt to fetch logs via Gateway RPC; returns None if unreachable."""
    try:
        from pyclaw.cli.commands.gateway_cmd import _default_gateway_url, _rpc_call
        import asyncio

        gw_url = _default_gateway_url()
        result = asyncio.run(
            _rpc_call(
                gw_url,
                method="logs.tail",
                params={"limit": limit, "json": output_json, "localTime": local_time},
                token=None,
                password=None,
                timeout_s=5.0,
            )
        )
        raw_lines = result.get("lines", [])
        if isinstance(raw_lines, list):
            out: list[str] = []
            for entry in raw_lines:
                if isinstance(entry, dict):
                    out.append(json.dumps(entry, ensure_ascii=False))
                else:
                    out.append(str(entry))
            return out
        return None
    except Exception:
        return None


def _print_log_lines(log_path: Path, *, limit: int, output_json: bool, local_time: bool) -> None:
    if not log_path.exists():
        typer.echo("No log file found.")
        return
    lines = log_path.read_text(encoding="utf-8").splitlines()[-limit:]
    for line in lines:
        _print_line(line, output_json=output_json, local_time=local_time)


def _follow(log_path: Path, *, output_json: bool, local_time: bool) -> None:
    if not log_path.exists():
        return
    with log_path.open("r", encoding="utf-8") as f:
        f.seek(0, 2)
        while True:
            line = f.readline()
            if not line:
                time.sleep(0.2)
                continue
            _print_line(line.rstrip("\n"), output_json=output_json, local_time=local_time)


def _print_line(line: str, *, output_json: bool, local_time: bool) -> None:
    if output_json:
        now = datetime.now().astimezone() if local_time else datetime.utcnow()
        typer.echo(json.dumps({"time": now.isoformat(), "line": line}, ensure_ascii=False))
    else:
        typer.echo(line)
