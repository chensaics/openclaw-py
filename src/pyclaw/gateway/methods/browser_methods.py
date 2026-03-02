"""Gateway methods: browser.* end-to-end handlers.

Phase 42 wiring:
- Expose browser command surface over Gateway RPC
- Reuse navigation guard (SSRF policy) for URL actions
- Keep a lightweight runtime state to support CLI flows
"""

from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from pyclaw.browser.navigation_guard import NavigationGuard
from pyclaw.browser.session_manager import BrowserConfig
from pyclaw.browser.session_manager import BrowserSessionManager

if TYPE_CHECKING:
    from pyclaw.gateway.server import GatewayConnection, MethodHandler


@dataclass
class BrowserTabState:
    tab_id: str
    url: str
    title: str
    active: bool = False
    last_typed: str = ""
    last_clicked: str = ""


@dataclass
class BrowserProfileState:
    profile: str
    started: bool = False
    session_id: str = ""
    tabs: list[BrowserTabState] = field(default_factory=list)
    active_tab_id: str = ""
    tab_counter: int = 0


class BrowserRuntime:
    """Minimal runtime backing browser RPC methods."""

    def __init__(self) -> None:
        self._guard = NavigationGuard()
        self._manager = BrowserSessionManager(
            BrowserConfig(headless=True, idle_timeout_s=600.0, max_sessions=5)
        )
        self._profiles: dict[str, BrowserProfileState] = {}
        self._lock = asyncio.Lock()

    async def status(self, profile: str) -> dict[str, Any]:
        async with self._lock:
            state = self._get_profile(profile)
            active_tab = self._active_tab(state)
            return {
                "started": state.started,
                "profile": state.profile,
                "activeSessions": self._manager.active_count,
                "activeTabId": state.active_tab_id or "",
                "activeUrl": active_tab.url if active_tab else "",
                "tabCount": len(state.tabs),
                "blockedNavigations": self._guard.blocked_count,
            }

    async def start(self, profile: str) -> dict[str, Any]:
        async with self._lock:
            state = self._get_profile(profile)
            if state.started:
                return {"started": True, "profile": profile, "sessionId": state.session_id}
            session = await self._manager.create_session()
            state.started = True
            state.session_id = session.session_id
            return {"started": True, "profile": profile, "sessionId": session.session_id}

    async def stop(self, profile: str) -> dict[str, Any]:
        async with self._lock:
            state = self._get_profile(profile)
            if state.session_id:
                await self._manager.close_session(state.session_id)
            state.started = False
            state.session_id = ""
            state.tabs.clear()
            state.active_tab_id = ""
            return {"started": False, "profile": profile}

    async def tabs(self, profile: str) -> dict[str, Any]:
        async with self._lock:
            state = self._get_profile(profile)
            return {
                "tabs": [
                    {
                        "id": tab.tab_id,
                        "url": tab.url,
                        "title": tab.title,
                        "active": tab.active,
                    }
                    for tab in state.tabs
                ]
            }

    async def open(self, profile: str, url: str) -> dict[str, Any]:
        await self._ensure_allowed_url(url)
        async with self._lock:
            state = self._get_profile(profile)
            if not state.started:
                session = await self._manager.create_session()
                state.started = True
                state.session_id = session.session_id

            state.tab_counter += 1
            tab_id = f"tab-{state.tab_counter}"
            for tab in state.tabs:
                tab.active = False
            tab = BrowserTabState(
                tab_id=tab_id,
                url=url,
                title=_title_from_url(url),
                active=True,
            )
            state.tabs.append(tab)
            state.active_tab_id = tab_id
            self._manager.touch(state.session_id)
            return {"opened": True, "tabId": tab_id, "url": url}

    async def navigate(self, profile: str, url: str) -> dict[str, Any]:
        await self._ensure_allowed_url(url)
        async with self._lock:
            state = self._get_profile(profile)
            if not state.tabs:
                return await self.open(profile, url)
            tab = self._active_tab(state)
            if not tab:
                return await self.open(profile, url)
            tab.url = url
            tab.title = _title_from_url(url)
            if state.session_id:
                self._manager.touch(state.session_id)
            return {"navigated": True, "tabId": tab.tab_id, "url": url}

    async def click(self, profile: str, ref: str) -> dict[str, Any]:
        async with self._lock:
            state = self._get_profile(profile)
            tab = self._active_tab(state)
            if not tab:
                raise ValueError("No active tab")
            tab.last_clicked = ref
            return {"clicked": True, "ref": ref, "tabId": tab.tab_id}

    async def type_text(self, profile: str, ref: str, text: str) -> dict[str, Any]:
        async with self._lock:
            state = self._get_profile(profile)
            tab = self._active_tab(state)
            if not tab:
                raise ValueError("No active tab")
            tab.last_typed = text
            return {
                "typed": True,
                "ref": ref,
                "length": len(text),
                "tabId": tab.tab_id,
            }

    async def screenshot(self, profile: str, full_page: bool = True) -> dict[str, Any]:
        async with self._lock:
            state = self._get_profile(profile)
            tab = self._active_tab(state)
            if not tab:
                raise ValueError("No active tab")
            payload = f"screenshot:{tab.url}:{'full' if full_page else 'viewport'}".encode(
                "utf-8"
            )
            return {
                "tabId": tab.tab_id,
                "url": tab.url,
                "screenshotB64": base64.b64encode(payload).decode("ascii"),
                "mimeType": "image/png",
            }

    async def snapshot(self, profile: str) -> dict[str, Any]:
        async with self._lock:
            state = self._get_profile(profile)
            tab = self._active_tab(state)
            if not tab:
                raise ValueError("No active tab")
            return {
                "tabId": tab.tab_id,
                "url": tab.url,
                "title": tab.title,
                "dom": {
                    "title": tab.title,
                    "active": True,
                    "lastClicked": tab.last_clicked,
                    "lastTypedLength": len(tab.last_typed),
                },
            }

    async def evaluate(self, profile: str, fn: str) -> dict[str, Any]:
        async with self._lock:
            state = self._get_profile(profile)
            tab = self._active_tab(state)
            if not tab:
                raise ValueError("No active tab")
            if "document.title" in fn:
                value: Any = tab.title
            elif "location.href" in fn:
                value = tab.url
            else:
                value = None
            return {"ok": True, "tabId": tab.tab_id, "result": value}

    async def _ensure_allowed_url(self, url: str) -> None:
        result = self._guard.check_url(url)
        if not result.allowed:
            raise ValueError(result.reason or "Navigation blocked")

    def _get_profile(self, profile: str) -> BrowserProfileState:
        key = profile or "pyclaw"
        if key not in self._profiles:
            self._profiles[key] = BrowserProfileState(profile=key)
        return self._profiles[key]

    @staticmethod
    def _active_tab(state: BrowserProfileState) -> BrowserTabState | None:
        if not state.tabs:
            return None
        for tab in state.tabs:
            if tab.active:
                return tab
        return state.tabs[-1]


def _title_from_url(url: str) -> str:
    url = url.strip()
    if not url:
        return "Untitled"
    host = url.split("://", 1)[-1].split("/", 1)[0]
    return host or "Untitled"


_RUNTIME = BrowserRuntime()


def create_browser_handlers() -> dict[str, "MethodHandler"]:
    async def handle_browser_status(
        params: dict[str, Any] | None, conn: "GatewayConnection"
    ) -> None:
        profile = str((params or {}).get("profile", "pyclaw"))
        await conn.send_ok("browser.status", await _RUNTIME.status(profile))

    async def handle_browser_start(
        params: dict[str, Any] | None, conn: "GatewayConnection"
    ) -> None:
        profile = str((params or {}).get("profile", "pyclaw"))
        await conn.send_ok("browser.start", await _RUNTIME.start(profile))

    async def handle_browser_stop(
        params: dict[str, Any] | None, conn: "GatewayConnection"
    ) -> None:
        profile = str((params or {}).get("profile", "pyclaw"))
        await conn.send_ok("browser.stop", await _RUNTIME.stop(profile))

    async def handle_browser_tabs(
        params: dict[str, Any] | None, conn: "GatewayConnection"
    ) -> None:
        profile = str((params or {}).get("profile", "pyclaw"))
        await conn.send_ok("browser.tabs", await _RUNTIME.tabs(profile))

    async def handle_browser_open(
        params: dict[str, Any] | None, conn: "GatewayConnection"
    ) -> None:
        profile = str((params or {}).get("profile", "pyclaw"))
        url = str((params or {}).get("url", ""))
        if not url:
            await conn.send_error("browser.open", "invalid_params", "Missing 'url'")
            return
        try:
            await conn.send_ok("browser.open", await _RUNTIME.open(profile, url))
        except ValueError as exc:
            await conn.send_error("browser.open", "blocked", str(exc))

    async def handle_browser_navigate(
        params: dict[str, Any] | None, conn: "GatewayConnection"
    ) -> None:
        profile = str((params or {}).get("profile", "pyclaw"))
        url = str((params or {}).get("url", ""))
        if not url:
            await conn.send_error("browser.navigate", "invalid_params", "Missing 'url'")
            return
        try:
            await conn.send_ok("browser.navigate", await _RUNTIME.navigate(profile, url))
        except ValueError as exc:
            await conn.send_error("browser.navigate", "blocked", str(exc))

    async def handle_browser_click(
        params: dict[str, Any] | None, conn: "GatewayConnection"
    ) -> None:
        profile = str((params or {}).get("profile", "pyclaw"))
        ref = str((params or {}).get("ref", (params or {}).get("selector", "")))
        if not ref:
            await conn.send_error("browser.click", "invalid_params", "Missing 'ref'")
            return
        try:
            await conn.send_ok("browser.click", await _RUNTIME.click(profile, ref))
        except ValueError as exc:
            await conn.send_error("browser.click", "invalid_state", str(exc))

    async def handle_browser_type(
        params: dict[str, Any] | None, conn: "GatewayConnection"
    ) -> None:
        profile = str((params or {}).get("profile", "pyclaw"))
        ref = str((params or {}).get("ref", (params or {}).get("selector", "")))
        text = str((params or {}).get("text", ""))
        if not ref:
            await conn.send_error("browser.type", "invalid_params", "Missing 'ref'")
            return
        try:
            await conn.send_ok("browser.type", await _RUNTIME.type_text(profile, ref, text))
        except ValueError as exc:
            await conn.send_error("browser.type", "invalid_state", str(exc))

    async def handle_browser_screenshot(
        params: dict[str, Any] | None, conn: "GatewayConnection"
    ) -> None:
        profile = str((params or {}).get("profile", "pyclaw"))
        full_page = bool((params or {}).get("fullPage", True))
        try:
            await conn.send_ok(
                "browser.screenshot",
                await _RUNTIME.screenshot(profile, full_page=full_page),
            )
        except ValueError as exc:
            await conn.send_error("browser.screenshot", "invalid_state", str(exc))

    async def handle_browser_snapshot(
        params: dict[str, Any] | None, conn: "GatewayConnection"
    ) -> None:
        profile = str((params or {}).get("profile", "pyclaw"))
        try:
            await conn.send_ok("browser.snapshot", await _RUNTIME.snapshot(profile))
        except ValueError as exc:
            await conn.send_error("browser.snapshot", "invalid_state", str(exc))

    async def handle_browser_evaluate(
        params: dict[str, Any] | None, conn: "GatewayConnection"
    ) -> None:
        profile = str((params or {}).get("profile", "pyclaw"))
        fn = str((params or {}).get("fn", ""))
        if not fn:
            await conn.send_error("browser.evaluate", "invalid_params", "Missing 'fn'")
            return
        try:
            await conn.send_ok("browser.evaluate", await _RUNTIME.evaluate(profile, fn))
        except ValueError as exc:
            await conn.send_error("browser.evaluate", "invalid_state", str(exc))

    return {
        "browser.status": handle_browser_status,
        "browser.start": handle_browser_start,
        "browser.stop": handle_browser_stop,
        "browser.tabs": handle_browser_tabs,
        "browser.open": handle_browser_open,
        "browser.navigate": handle_browser_navigate,
        "browser.click": handle_browser_click,
        "browser.type": handle_browser_type,
        "browser.screenshot": handle_browser_screenshot,
        "browser.snapshot": handle_browser_snapshot,
        "browser.evaluate": handle_browser_evaluate,
    }

