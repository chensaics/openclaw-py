"""Gateway WebSocket protocol — frame types and constants."""

from pyclaw.gateway.protocol.frames import (
    PROTOCOL_VERSION,
    ErrorShape,
    EventFrame,
    RequestFrame,
    ResponseFrame,
)

__all__ = [
    "PROTOCOL_VERSION",
    "ErrorShape",
    "EventFrame",
    "RequestFrame",
    "ResponseFrame",
]
