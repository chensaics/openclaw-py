"""Browser relay — Chrome Extension relay with CORS, auth, and reconnect.

Ported from ``src/browser/`` relay logic in the TypeScript codebase.

Provides:
- Chrome Extension WebSocket relay server
- CORS origin validation for extension connections
- Token-based authentication for relay sessions
- Auto-reconnect state tracking
- Message routing between extension and gateway
"""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, cast

logger = logging.getLogger(__name__)

DEFAULT_HEARTBEAT_INTERVAL_S = 30.0
DEFAULT_RECONNECT_DELAY_S = 5.0
DEFAULT_MAX_RECONNECT_DELAY_S = 60.0
DEFAULT_MAX_RECONNECT_ATTEMPTS = 10


class RelayState(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    AUTHENTICATING = "authenticating"
    ERROR = "error"


@dataclass
class RelaySession:
    """A single browser relay session."""

    session_id: str
    origin: str = ""
    state: RelayState = RelayState.DISCONNECTED
    authenticated: bool = False
    connected_at: float = 0.0
    last_heartbeat: float = 0.0
    reconnect_attempts: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.session_id:
            self.session_id = str(uuid.uuid4())[:12]


@dataclass
class RelayConfig:
    """Configuration for the browser relay."""

    allowed_origins: list[str] = field(
        default_factory=lambda: [
            "chrome-extension://",
        ]
    )
    auth_token: str = ""
    heartbeat_interval_s: float = DEFAULT_HEARTBEAT_INTERVAL_S
    max_reconnect_attempts: int = DEFAULT_MAX_RECONNECT_ATTEMPTS
    reconnect_delay_s: float = DEFAULT_RECONNECT_DELAY_S
    max_reconnect_delay_s: float = DEFAULT_MAX_RECONNECT_DELAY_S
    max_sessions: int = 10


@dataclass
class RelayMessage:
    """A message passed through the relay."""

    type: str  # "action" | "result" | "event" | "heartbeat"
    payload: dict[str, Any] = field(default_factory=dict)
    session_id: str = ""
    timestamp: float = 0.0

    def __post_init__(self) -> None:
        if self.timestamp == 0.0:
            self.timestamp = time.time()


MessageHandler = Callable[[RelayMessage], Coroutine[Any, Any, None]]


def validate_cors_origin(origin: str, allowed_origins: list[str]) -> bool:
    """Validate a WebSocket connection origin against allowed patterns.

    Supports prefix matching for chrome-extension:// and exact matches.
    """
    if not origin:
        return False

    for allowed in allowed_origins:
        if allowed.endswith("://"):
            # Prefix match (e.g. "chrome-extension://")
            if origin.startswith(allowed) or origin.startswith(allowed.rstrip("/")):
                return True
        elif origin == allowed:
            return True

    return False


def validate_relay_auth(token: str, expected_token: str) -> bool:
    """Validate relay authentication token.

    Uses constant-time comparison to prevent timing attacks.
    """
    import hmac

    if not expected_token:
        return True  # No auth configured
    return hmac.compare_digest(token, expected_token)


class BrowserRelayManager:
    """Manages browser relay sessions and message routing."""

    def __init__(self, config: RelayConfig | None = None) -> None:
        self._config = config or RelayConfig()
        self._sessions: dict[str, RelaySession] = {}
        self._handlers: list[MessageHandler] = []

    def create_session(self, *, origin: str = "") -> RelaySession | None:
        """Create a new relay session after CORS validation.

        Returns None if the origin is not allowed or max sessions reached.
        """
        if origin and not validate_cors_origin(origin, self._config.allowed_origins):
            logger.warning("Relay CORS rejected: origin=%s", origin)
            return None

        if len(self._sessions) >= self._config.max_sessions:
            logger.warning("Relay max sessions reached (%d)", self._config.max_sessions)
            return None

        session = RelaySession(
            session_id="",
            origin=origin,
            state=RelayState.CONNECTING,
        )
        self._sessions[session.session_id] = session
        return session

    def authenticate_session(self, session_id: str, token: str) -> bool:
        """Authenticate a relay session."""
        session = self._sessions.get(session_id)
        if not session:
            return False

        if validate_relay_auth(token, self._config.auth_token):
            session.authenticated = True
            session.state = RelayState.CONNECTED
            session.connected_at = time.time()
            session.last_heartbeat = time.time()
            return True

        session.state = RelayState.ERROR
        return False

    def disconnect_session(self, session_id: str) -> None:
        """Disconnect and remove a relay session."""
        session = self._sessions.pop(session_id, None)
        if session:
            session.state = RelayState.DISCONNECTED

    def handle_heartbeat(self, session_id: str) -> bool:
        """Process a heartbeat from a session. Returns False if session invalid."""
        session = self._sessions.get(session_id)
        if not session or not session.authenticated:
            return False
        session.last_heartbeat = time.time()
        return True

    def get_session(self, session_id: str) -> RelaySession | None:
        return self._sessions.get(session_id)

    def get_active_sessions(self) -> list[RelaySession]:
        return [s for s in self._sessions.values() if s.state == RelayState.CONNECTED]

    def register_handler(self, handler: MessageHandler) -> None:
        self._handlers.append(handler)

    async def route_message(self, message: RelayMessage) -> None:
        """Route a message to all registered handlers."""
        session = self._sessions.get(message.session_id)
        if session and not session.authenticated and message.type != "auth":
            logger.warning("Message from unauthenticated session: %s", message.session_id)
            return

        for handler in self._handlers:
            try:
                await handler(message)
            except Exception:
                logger.debug("Relay handler error", exc_info=True)

    def compute_reconnect_delay(self, session_id: str) -> float:
        """Compute reconnect delay with exponential backoff."""
        session = self._sessions.get(session_id)
        if not session:
            return self._config.reconnect_delay_s

        attempt = session.reconnect_attempts
        delay = min(
            self._config.reconnect_delay_s * (2**attempt),
            self._config.max_reconnect_delay_s,
        )
        return cast(float, delay)

    def should_reconnect(self, session_id: str) -> bool:
        """Check if a session should attempt reconnection."""
        session = self._sessions.get(session_id)
        if not session:
            return False
        return session.reconnect_attempts < self._config.max_reconnect_attempts

    def cleanup_stale(self, *, timeout_s: float = 120.0) -> int:
        """Remove sessions that haven't sent a heartbeat within timeout."""
        now = time.time()
        stale = [
            sid
            for sid, s in self._sessions.items()
            if s.state == RelayState.CONNECTED and (now - s.last_heartbeat) > timeout_s
        ]
        for sid in stale:
            self.disconnect_session(sid)
        return len(stale)

    @property
    def session_count(self) -> int:
        return len(self._sessions)
