"""Gateway methods: device.pair.* — device pairing flow."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from pyclaw.gateway.server import GatewayConnection

from pyclaw.pairing.store import approve_pairing_code, read_allow_from_store
from pyclaw.pairing.setup_code import encode_pairing_setup_code, PairingSetup


async def _handle_device_pair_code(
    params: dict[str, Any] | None,
    conn: GatewayConnection,
) -> dict[str, Any]:
    """Generate a pairing setup code for mobile/remote clients."""
    if not params:
        return {"error": "Missing params"}

    url = params.get("url", "")
    token = params.get("token")
    if not url:
        return {"error": "url is required"}

    setup = PairingSetup(url=url, token=token)
    code = encode_pairing_setup_code(setup)
    return {"code": code}


async def _handle_device_pair_approve(
    params: dict[str, Any] | None,
    conn: GatewayConnection,
) -> dict[str, Any]:
    """Approve a pairing code from a channel."""
    if not params:
        return {"error": "Missing params"}

    channel = params.get("channel", "")
    code = params.get("code", "")
    if not channel or not code:
        return {"error": "channel and code are required"}

    result = approve_pairing_code(channel, code)
    if result:
        return {"ok": True, "senderId": result.sender_id, "displayName": result.display_name}
    return {"ok": False, "error": "Invalid or expired code"}


async def _handle_device_pair_list(
    params: dict[str, Any] | None,
    conn: GatewayConnection,
) -> dict[str, Any]:
    """List paired devices for a channel."""
    channel = (params or {}).get("channel", "")
    if not channel:
        return {"error": "channel is required"}

    entries = read_allow_from_store(channel)
    return {
        "entries": [
            {
                "senderId": e.sender_id,
                "addedAt": e.added_at,
                "displayName": e.display_name,
                "pairedVia": e.paired_via,
            }
            for e in entries
        ],
    }


def create_device_pair_handlers() -> dict[str, Any]:
    return {
        "device.pair.code": _handle_device_pair_code,
        "device.pair.approve": _handle_device_pair_approve,
        "device.pair.list": _handle_device_pair_list,
    }
