"""Bridge server — Chrome Extension WebSocket relay with token auth and tab discovery.

Enhances the existing ``browser/relay.py`` with:
- Token-based authentication registry
- Tab discovery and listing from extension
- DOM snapshot forwarding from extension to agent
- CSRF protection for mutation requests
- Integration with BrowserRelayManager
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
import time
from dataclasses import dataclass
from typing import Any

from pyclaw.browser.relay import (
    BrowserRelayManager,
    RelayConfig,
    RelayMessage,
)
from pyclaw.constants.runtime import DEFAULT_GATEWAY_BIND

logger = logging.getLogger(__name__)


@dataclass
class BridgeConfig:
    """Configuration for the bridge server."""

    host: str = DEFAULT_GATEWAY_BIND
    port: int = 9222
    auth_token: str = ""
    auto_generate_token: bool = True
    csrf_enabled: bool = True
    max_snapshot_size: int = 5 * 1024 * 1024  # 5 MB
    tab_cache_ttl_s: float = 30.0


@dataclass
class TabInfo:
    """Information about a browser tab from the extension."""

    tab_id: str
    title: str = ""
    url: str = ""
    active: bool = False
    pinned: bool = False
    favicon_url: str = ""
    last_updated: float = 0.0

    def __post_init__(self) -> None:
        if self.last_updated == 0:
            self.last_updated = time.time()


@dataclass
class DOMSnapshot:
    """A DOM snapshot received from the extension."""

    tab_id: str
    html: str = ""
    text: str = ""
    accessibility_tree: str = ""
    url: str = ""
    title: str = ""
    timestamp: float = 0.0
    size_bytes: int = 0

    def __post_init__(self) -> None:
        if self.timestamp == 0:
            self.timestamp = time.time()
        if not self.size_bytes:
            self.size_bytes = len(self.html) + len(self.text) + len(self.accessibility_tree)


class AuthTokenRegistry:
    """Manage authentication tokens for bridge connections."""

    def __init__(self) -> None:
        self._tokens: dict[str, float] = {}  # token -> issued_at

    def generate(self) -> str:
        token = secrets.token_urlsafe(32)
        self._tokens[token] = time.time()
        return token

    def validate(self, token: str) -> bool:
        return token in self._tokens

    def revoke(self, token: str) -> bool:
        return self._tokens.pop(token, None) is not None

    def revoke_all(self) -> int:
        count = len(self._tokens)
        self._tokens.clear()
        return count

    @property
    def active_count(self) -> int:
        return len(self._tokens)


def generate_csrf_token(session_id: str, secret: str) -> str:
    """Generate a CSRF token tied to a session."""
    payload = f"{session_id}:{secret}".encode()
    return hashlib.sha256(payload).hexdigest()[:32]


def validate_csrf_token(token: str, session_id: str, secret: str) -> bool:
    """Validate a CSRF token."""
    expected = generate_csrf_token(session_id, secret)
    return hmac.compare_digest(token, expected)


class BridgeServer:
    """Chrome Extension bridge server with auth, tabs, and snapshot forwarding."""

    def __init__(self, config: BridgeConfig | None = None) -> None:
        self._config = config or BridgeConfig()
        self._auth_registry = AuthTokenRegistry()
        self._tabs: dict[str, TabInfo] = {}
        self._snapshots: dict[str, DOMSnapshot] = {}
        self._csrf_secret = secrets.token_hex(16)

        relay_config = RelayConfig(auth_token=self._config.auth_token)
        self._relay = BrowserRelayManager(relay_config)

        if self._config.auto_generate_token and not self._config.auth_token:
            self._config.auth_token = self._auth_registry.generate()

    @property
    def auth_token(self) -> str:
        return self._config.auth_token

    @property
    def relay(self) -> BrowserRelayManager:
        return self._relay

    @property
    def auth_registry(self) -> AuthTokenRegistry:
        return self._auth_registry

    def update_tabs(self, tabs: list[dict[str, Any]]) -> int:
        """Update tab cache from extension message."""
        self._tabs.clear()
        for t in tabs:
            tab = TabInfo(
                tab_id=str(t.get("id", t.get("tab_id", ""))),
                title=t.get("title", ""),
                url=t.get("url", ""),
                active=t.get("active", False),
                pinned=t.get("pinned", False),
                favicon_url=t.get("favIconUrl", t.get("favicon_url", "")),
            )
            self._tabs[tab.tab_id] = tab
        return len(self._tabs)

    def get_tabs(self) -> list[TabInfo]:
        """Get cached tabs, filtering stale entries."""
        cutoff = time.time() - self._config.tab_cache_ttl_s
        return [t for t in self._tabs.values() if t.last_updated > cutoff]

    def get_active_tab(self) -> TabInfo | None:
        for t in self._tabs.values():
            if t.active:
                return t
        return None

    def store_snapshot(self, snapshot: DOMSnapshot) -> bool:
        """Store a DOM snapshot from the extension."""
        if snapshot.size_bytes > self._config.max_snapshot_size:
            logger.warning(
                "Snapshot too large: %d bytes (max %d)",
                snapshot.size_bytes,
                self._config.max_snapshot_size,
            )
            return False
        self._snapshots[snapshot.tab_id] = snapshot
        return True

    def get_snapshot(self, tab_id: str) -> DOMSnapshot | None:
        return self._snapshots.get(tab_id)

    def get_csrf_token(self, session_id: str) -> str:
        return generate_csrf_token(session_id, self._csrf_secret)

    def validate_csrf(self, token: str, session_id: str) -> bool:
        if not self._config.csrf_enabled:
            return True
        return validate_csrf_token(token, session_id, self._csrf_secret)

    async def handle_message(self, message: RelayMessage) -> dict[str, Any] | None:
        """Handle an incoming bridge message."""
        msg_type = message.payload.get("type", message.type)

        if msg_type == "tabs_update":
            count = self.update_tabs(message.payload.get("tabs", []))
            return {"type": "tabs_updated", "count": count}

        if msg_type == "dom_snapshot":
            snapshot = DOMSnapshot(
                tab_id=message.payload.get("tab_id", ""),
                html=message.payload.get("html", ""),
                text=message.payload.get("text", ""),
                accessibility_tree=message.payload.get("accessibility_tree", ""),
                url=message.payload.get("url", ""),
                title=message.payload.get("title", ""),
            )
            stored = self.store_snapshot(snapshot)
            return {"type": "snapshot_stored", "success": stored}

        return None

    @property
    def tab_count(self) -> int:
        return len(self._tabs)
