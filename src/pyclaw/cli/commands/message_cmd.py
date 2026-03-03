"""CLI: message send — send messages via the gateway or channels."""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

import typer


def message_send(
    text: str,
    channel: str = "default",
    recipient: str = "",
    gateway_url: str = "ws://127.0.0.1:18789",
    auth_token: str | None = None,
) -> None:
    """Send a message through the gateway or directly to a channel."""
    asyncio.run(_send_via_gateway(text, channel, recipient, gateway_url, auth_token))


async def _send_via_gateway(
    text: str,
    channel: str,
    recipient: str,
    gateway_url: str,
    auth_token: str | None,
) -> None:
    """Send a message via WebSocket gateway."""
    try:
        import websockets
    except ImportError:
        typer.echo("websockets package required: pip install websockets", err=True)
        raise typer.Exit(1)

    url = f"{gateway_url}/ws"
    try:
        async with websockets.connect(url) as ws:
            # Authenticate
            connect_msg: dict[str, Any] = {
                "id": 1,
                "method": "connect",
                "params": {
                    "protocolVersion": 3,
                    "clientName": "pyclaw-cli",
                },
            }
            if auth_token:
                connect_msg["params"]["token"] = auth_token

            await ws.send(json.dumps(connect_msg))
            response: dict[str, Any] = json.loads(await ws.recv())

            if response.get("error"):
                typer.echo(f"Connection error: {response['error']}", err=True)
                raise typer.Exit(1)

            # Send chat message
            chat_msg: dict[str, Any] = {
                "id": 2,
                "method": "chat.send",
                "params": {
                    "message": text,
                    "channel": channel,
                },
            }
            if recipient:
                chat_msg["params"]["recipient"] = recipient

            await ws.send(json.dumps(chat_msg))

            # Read response and any streaming events
            while True:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=60)
                    data = json.loads(raw)

                    if data.get("id") == 2:
                        if data.get("error"):
                            typer.echo(f"Error: {data['error']}", err=True)
                        else:
                            typer.echo("Message sent.")
                        break

                    # Print streamed events
                    if "event" in data:
                        event = data["event"]
                        payload = data.get("payload", {})
                        if event == "chat.delta":
                            text_delta = payload.get("text", "")
                            sys.stdout.write(text_delta)
                            sys.stdout.flush()
                        elif event == "chat.done":
                            sys.stdout.write("\n")
                            break
                except asyncio.TimeoutError:
                    typer.echo("\nTimeout waiting for response.", err=True)
                    break

    except ConnectionRefusedError:
        typer.echo(f"Could not connect to gateway at {gateway_url}", err=True)
        raise typer.Exit(1)
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
