"""Browser session manager — Playwright browser/context lifecycle on top of Playwright Python SDK.

Provides:
- Browser instance management (launch/connect/close)
- Context creation with profile persistence (cookies, storage state)
- Concurrent session limiting
- Idle timeout auto-cleanup
- Profile directory management
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class BrowserType(str, Enum):
    CHROMIUM = "chromium"
    FIREFOX = "firefox"
    WEBKIT = "webkit"


class SessionState(str, Enum):
    IDLE = "idle"
    ACTIVE = "active"
    CLOSED = "closed"


@dataclass
class BrowserConfig:
    """Configuration for browser session management."""

    browser_type: BrowserType = BrowserType.CHROMIUM
    headless: bool = True
    max_sessions: int = 5
    idle_timeout_s: float = 300.0
    default_viewport_width: int = 1280
    default_viewport_height: int = 720
    user_data_dir: str = ""
    proxy: str = ""
    extra_args: list[str] = field(default_factory=list)
    slow_mo_ms: float = 0.0


@dataclass
class SessionInfo:
    """Metadata for a browser session."""

    session_id: str
    state: SessionState = SessionState.IDLE
    created_at: float = 0.0
    last_active_at: float = 0.0
    page_count: int = 0
    url: str = ""

    def __post_init__(self) -> None:
        now = time.time()
        if self.created_at == 0:
            self.created_at = now
        if self.last_active_at == 0:
            self.last_active_at = now


@dataclass
class LaunchOptions:
    """Options for launching a browser."""

    headless: bool = True
    args: list[str] = field(default_factory=list)
    proxy: str = ""
    slow_mo: float = 0.0
    viewport_width: int = 1280
    viewport_height: int = 720
    storage_state: str = ""
    user_data_dir: str = ""

    def to_playwright_args(self) -> dict[str, Any]:
        opts: dict[str, Any] = {
            "headless": self.headless,
        }
        args = list(self.args)
        if args:
            opts["args"] = args
        if self.proxy:
            opts["proxy"] = {"server": self.proxy}
        if self.slow_mo:
            opts["slow_mo"] = self.slow_mo
        return opts

    def to_context_args(self) -> dict[str, Any]:
        opts: dict[str, Any] = {
            "viewport": {"width": self.viewport_width, "height": self.viewport_height},
        }
        if self.storage_state:
            opts["storage_state"] = self.storage_state
        return opts


class PlaywrightBridge(Protocol):
    """Protocol abstracting Playwright for testability."""

    async def launch(self, browser_type: str, **kwargs: Any) -> Any: ...
    async def close_browser(self, browser: Any) -> None: ...
    async def new_context(self, browser: Any, **kwargs: Any) -> Any: ...
    async def new_page(self, context: Any) -> Any: ...
    async def close_context(self, context: Any) -> None: ...


class BrowserSessionManager:
    """Manage Playwright browser sessions with lifecycle control."""

    def __init__(
        self,
        config: BrowserConfig | None = None,
        *,
        bridge: PlaywrightBridge | None = None,
    ) -> None:
        self._config = config or BrowserConfig()
        self._bridge = bridge
        self._sessions: dict[str, SessionInfo] = {}
        self._browsers: dict[str, Any] = {}
        self._contexts: dict[str, Any] = {}
        self._counter = 0

    def _next_id(self) -> str:
        self._counter += 1
        return f"browser-{self._counter}"

    async def create_session(
        self,
        *,
        options: LaunchOptions | None = None,
    ) -> SessionInfo:
        """Create a new browser session.

        Raises RuntimeError if max sessions reached.
        """
        if len(self._sessions) >= self._config.max_sessions:
            raise RuntimeError(f"Max browser sessions reached ({self._config.max_sessions})")

        opts = options or LaunchOptions(
            headless=self._config.headless,
            viewport_width=self._config.default_viewport_width,
            viewport_height=self._config.default_viewport_height,
            proxy=self._config.proxy,
            slow_mo=self._config.slow_mo_ms,
        )

        session_id = self._next_id()

        if self._bridge:
            browser = await self._bridge.launch(
                self._config.browser_type.value,
                **opts.to_playwright_args(),
            )
            self._browsers[session_id] = browser

            context = await self._bridge.new_context(browser, **opts.to_context_args())
            self._contexts[session_id] = context

        info = SessionInfo(session_id=session_id, state=SessionState.ACTIVE)
        self._sessions[session_id] = info
        return info

    async def close_session(self, session_id: str) -> bool:
        info = self._sessions.get(session_id)
        if not info:
            return False

        context = self._contexts.pop(session_id, None)
        if context and self._bridge:
            await self._bridge.close_context(context)

        browser = self._browsers.pop(session_id, None)
        if browser and self._bridge:
            await self._bridge.close_browser(browser)

        info.state = SessionState.CLOSED
        self._sessions.pop(session_id, None)
        return True

    def touch(self, session_id: str) -> None:
        """Mark a session as recently active."""
        info = self._sessions.get(session_id)
        if info:
            info.last_active_at = time.time()
            info.state = SessionState.ACTIVE

    def get_session(self, session_id: str) -> SessionInfo | None:
        return self._sessions.get(session_id)

    def list_sessions(self) -> list[SessionInfo]:
        return list(self._sessions.values())

    def find_idle_sessions(self) -> list[str]:
        """Find sessions that have been idle longer than the timeout."""
        now = time.time()
        return [
            sid
            for sid, info in self._sessions.items()
            if (now - info.last_active_at) > self._config.idle_timeout_s
        ]

    async def cleanup_idle(self) -> int:
        """Close idle sessions. Returns count of sessions closed."""
        idle = self.find_idle_sessions()
        for sid in idle:
            await self.close_session(sid)
        return len(idle)

    async def close_all(self) -> int:
        """Close all sessions."""
        sids = list(self._sessions.keys())
        for sid in sids:
            await self.close_session(sid)
        return len(sids)

    def get_context(self, session_id: str) -> Any | None:
        return self._contexts.get(session_id)

    def get_browser(self, session_id: str) -> Any | None:
        return self._browsers.get(session_id)

    @property
    def active_count(self) -> int:
        return len(self._sessions)

    @property
    def config(self) -> BrowserConfig:
        return self._config


# ---------------------------------------------------------------------------
# Profile Persistence
# ---------------------------------------------------------------------------


@dataclass
class ProfileConfig:
    """Configuration for browser profile persistence."""

    profiles_dir: str = ""
    auto_save: bool = True
    save_on_close: bool = True


def profile_path(profiles_dir: str, profile_name: str) -> Path:
    """Get the storage state path for a named profile."""
    return Path(profiles_dir) / f"{profile_name}.json"


def list_profiles(profiles_dir: str) -> list[str]:
    """List available browser profiles."""
    p = Path(profiles_dir)
    if not p.exists():
        return []
    return [f.stem for f in p.glob("*.json")]
