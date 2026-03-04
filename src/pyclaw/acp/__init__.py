"""ACP — Agent Control Protocol bridge.

Ported from ``src/acp/``.
Provides NDJSON stdio bridge between IDE clients (VS Code, etc.) and the
pyclaw gateway WebSocket, plus acpx runtime backend and thread ownership.
"""

from pyclaw.acp.acpx_runtime import ACPX_BACKEND_ID, AcpxConfig, AcpxRuntime
from pyclaw.acp.client import create_acp_client
from pyclaw.acp.control_plane import (
    AcpRuntimeEvent,
    AcpRuntimeProtocol,
    AcpSessionManager,
    AcpSessionResolution,
    get_acp_session_manager,
)
from pyclaw.acp.server import serve_acp_gateway
from pyclaw.acp.session import AcpSessionStore, create_in_memory_session_store
from pyclaw.acp.session_mapper import (
    AcpSessionMetaHints,
    parse_session_meta,
    resolve_session_key,
)
from pyclaw.acp.thread_ownership import ThreadOwnershipTracker
from pyclaw.acp.types import AcpAgentInfo, AcpSessionMeta

__all__ = [
    "ACPX_BACKEND_ID",
    "AcpAgentInfo",
    "AcpRuntimeEvent",
    "AcpRuntimeProtocol",
    "AcpSessionManager",
    "AcpSessionMeta",
    "AcpSessionMetaHints",
    "AcpSessionResolution",
    "AcpSessionStore",
    "AcpxConfig",
    "AcpxRuntime",
    "ThreadOwnershipTracker",
    "create_acp_client",
    "create_in_memory_session_store",
    "get_acp_session_manager",
    "parse_session_meta",
    "resolve_session_key",
    "serve_acp_gateway",
]
