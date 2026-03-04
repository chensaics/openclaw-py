"""Node Host runner — connects to gateway and handles invoke events."""

from __future__ import annotations

import json
import logging
from typing import Any

from pyclaw.node_host.invoke import InvokeRequest, handle_invoke

logger = logging.getLogger(__name__)


async def run_node_host(
    gateway_url: str = "ws://127.0.0.1:18789/ws",
    auth_token: str | None = None,
    node_id: str = "",
) -> None:
    """Connect to gateway as a node and handle invoke requests."""
    try:
        import websockets
    except ImportError:
        logger.error("websockets required: pip install websockets")
        return

    if not node_id:
        import platform

        node_id = platform.node() or "node-1"

    logger.info("Node host starting: %s → %s", node_id, gateway_url)

    async with websockets.connect(gateway_url) as ws:
        # Authenticate
        connect_msg: dict[str, Any] = {
            "id": 1,
            "method": "connect",
            "params": {
                "protocolVersion": 3,
                "clientName": f"node:{node_id}",
                "role": "node",
                "nodeId": node_id,
            },
        }
        if auth_token:
            connect_msg["params"]["token"] = auth_token

        await ws.send(json.dumps(connect_msg))
        resp = json.loads(await ws.recv())

        if resp.get("error"):
            logger.error("Gateway connection failed: %s", resp["error"])
            return

        logger.info("Node host connected: %s", node_id)

        # Event loop
        async for raw in ws:
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue

            event = data.get("event", "")
            if event != "node.invoke.request":
                continue

            payload = data.get("payload", {})
            request = InvokeRequest(
                id=payload.get("id", ""),
                node_id=payload.get("nodeId", node_id),
                command=payload.get("command", ""),
                params=json.loads(payload.get("paramsJSON", "{}")),
                timeout_ms=payload.get("timeoutMs", 30_000),
            )

            # Handle async
            result = await handle_invoke(request)

            # Send result back
            result_msg = {
                "id": 0,
                "method": "node.invoke.result",
                "params": {
                    "id": result.id,
                    "success": result.success,
                    "result": result.result,
                    "error": result.error,
                },
            }
            await ws.send(json.dumps(result_msg))
