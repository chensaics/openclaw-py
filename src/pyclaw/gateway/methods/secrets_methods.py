"""Gateway method: secrets.reload — re-resolve all SecretRefs at runtime.

Ported from gateway secrets reload handler.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pyclaw.gateway.server import GatewayConnection, MethodHandler

logger = logging.getLogger(__name__)


async def handle_secrets_reload(params: dict[str, Any] | None, conn: GatewayConnection) -> None:
    """Re-resolve all cached SecretRefs and update the runtime snapshot."""
    from pyclaw.secrets.runtime import SecretsRuntime

    # The runtime singleton is typically held by the gateway server
    runtime = getattr(conn, "secrets_runtime", None)
    if runtime and isinstance(runtime, SecretsRuntime):
        count = runtime.reload()
        await conn.send_ok({"reloaded": True, "count": count})
        logger.info("Secrets reloaded via gateway RPC")
    else:
        await conn.send_ok({"reloaded": True, "count": 0})


def create_secrets_handlers() -> dict[str, MethodHandler]:
    """Create handlers for secrets.* RPC methods."""
    return {
        "secrets.reload": handle_secrets_reload,
    }
