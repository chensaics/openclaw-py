"""CLI: nodes/devices — manage paired devices."""

from __future__ import annotations

import typer

from pyclaw.config.paths import resolve_credentials_dir


def devices_list() -> None:
    """List paired devices across all channels."""
    from pyclaw.pairing.store import read_allow_from_store

    creds_dir = resolve_credentials_dir()
    if not creds_dir.exists():
        typer.echo("No credentials directory found.")
        return

    found_any = False
    for path in sorted(creds_dir.glob("*-allowFrom.json")):
        channel = path.stem.replace("-allowFrom", "")
        entries = read_allow_from_store(channel, creds_dir)
        if entries:
            found_any = True
            typer.echo(f"\n{channel}:")
            for e in entries:
                import datetime
                added = datetime.datetime.fromtimestamp(e.added_at).strftime("%Y-%m-%d %H:%M") if e.added_at else "unknown"
                name = e.display_name or e.sender_id
                typer.echo(f"  {name} (via {e.paired_via}, added {added})")

    if not found_any:
        typer.echo("No paired devices found.")


def devices_approve(channel: str, code: str) -> None:
    """Approve a pairing code for a channel."""
    from pyclaw.pairing.store import approve_pairing_code

    result = approve_pairing_code(channel, code)
    if result:
        typer.echo(f"Approved: {result.display_name or result.sender_id} on {channel}")
    else:
        typer.echo("Invalid or expired pairing code.", err=True)
        raise typer.Exit(1)


def devices_remove(channel: str, sender_id: str) -> None:
    """Remove a paired device from a channel's allowFrom store."""
    import json
    from pyclaw.pairing.store import _allow_from_path, read_allow_from_store

    entries = read_allow_from_store(channel)
    remaining = [e for e in entries if e.sender_id != sender_id]

    if len(remaining) == len(entries):
        typer.echo(f"No device with sender ID '{sender_id}' found for {channel}.", err=True)
        raise typer.Exit(1)

    path = _allow_from_path(channel)
    data = [
        {
            "senderId": e.sender_id,
            "addedAt": e.added_at,
            "displayName": e.display_name,
            "pairedVia": e.paired_via,
        }
        for e in remaining
    ]
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    typer.echo(f"Removed {sender_id} from {channel}.")
