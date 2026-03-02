"""CLI: ``pyclaw secrets`` — audit, configure, apply, reload.

Ported from ``src/cli/secrets-cli.ts``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import typer

secrets_app = typer.Typer(name="secrets", help="Manage external secret references.")


@secrets_app.command()
def audit(
    check: bool = typer.Option(False, help="Exit with non-zero if findings exist."),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """Scan config and auth files for plaintext secrets and stale refs."""
    from pyclaw.secrets.audit import run_secrets_audit

    report = run_secrets_audit()

    if json_output:
        out = {
            "version": report.version,
            "status": report.status,
            "filesScanned": report.files_scanned,
            "summary": report.summary,
            "findings": [
                {
                    "code": f.code,
                    "severity": f.severity,
                    "file": f.file,
                    "jsonPath": f.json_path,
                    "message": f.message,
                }
                for f in report.findings
            ],
        }
        typer.echo(json.dumps(out, indent=2))
    else:
        typer.echo(f"Status: {report.status}")
        typer.echo(f"Files scanned: {len(report.files_scanned)}")
        if report.findings:
            typer.echo(f"\nFindings ({len(report.findings)}):")
            for f in report.findings:
                icon = {"error": "!!", "warn": "!", "info": "i"}[f.severity]
                typer.echo(f"  [{icon}] {f.code}: {f.message}")
                typer.echo(f"      File: {f.file}")
                typer.echo(f"      Path: {f.json_path}")
        else:
            typer.echo("\nNo findings — secrets configuration looks clean.")

    if check and report.status != "clean":
        raise typer.Exit(1)


@secrets_app.command()
def apply(
    plan_file: Path = typer.Argument(..., help="Path to the secrets plan JSON file."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview changes without writing."),
) -> None:
    """Apply a secrets plan to update config with SecretRefs."""
    from pyclaw.secrets.plan import SecretsApplyPlan
    from pyclaw.secrets.apply import run_secrets_apply

    if not plan_file.exists():
        typer.echo(f"Plan file not found: {plan_file}", err=True)
        raise typer.Exit(1)

    plan_data = json.loads(plan_file.read_text(encoding="utf-8"))
    plan = SecretsApplyPlan.from_dict(plan_data)

    result = run_secrets_apply(plan, dry_run=dry_run)

    if dry_run:
        typer.echo("Dry run — no changes written.")
    typer.echo(f"Applied: {len(result['applied'])}")
    for p in result["applied"]:
        typer.echo(f"  - {p}")
    if result["errors"]:
        typer.echo(f"Errors: {len(result['errors'])}")
        for e in result["errors"]:
            typer.echo(f"  - {e}", err=True)


@secrets_app.command()
def reload(
    gateway_url: str = typer.Option("ws://127.0.0.1:18789/ws", help="Gateway WebSocket URL."),
) -> None:
    """Reload secrets on the running gateway (re-resolve all SecretRefs)."""
    import asyncio

    async def _reload() -> None:
        try:
            import websockets
        except ImportError:
            typer.echo("websockets package required for gateway communication.", err=True)
            raise typer.Exit(1)

        try:
            ws = await websockets.connect(gateway_url)
            # Connect
            connect_msg = json.dumps({
                "id": 1,
                "method": "connect",
                "params": {"protocolVersion": 3, "clientName": "secrets-cli"},
            })
            await ws.send(connect_msg)
            await ws.recv()

            # Request secrets reload
            reload_msg = json.dumps({
                "id": 2,
                "method": "secrets.reload",
                "params": {},
            })
            await ws.send(reload_msg)
            response = json.loads(await ws.recv())

            await ws.close()

            if response.get("error"):
                typer.echo(f"Reload failed: {response['error']}", err=True)
                raise typer.Exit(1)
            typer.echo("Secrets reloaded on gateway.")
        except Exception as exc:
            typer.echo(f"Failed to connect to gateway: {exc}", err=True)
            raise typer.Exit(1)

    asyncio.run(_reload())
