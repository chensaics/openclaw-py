"""Gateway methods: browser.* end-to-end handlers.

Phase 54: Real Playwright execution instead of in-memory simulation.
- Reuses BrowserSessionManager + BrowserToolExecutor + ScreenshotService
- Supports profiles via session_manager.list_profiles / profile_path
- Navigation guard (SSRF) applied to all URL actions
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pyclaw.browser.navigation_guard import NavigationGuard
from pyclaw.browser.session_manager import (
    BrowserConfig,
    BrowserSessionManager,
    LaunchOptions,
    ProfileConfig,
    list_profiles,
    profile_path,
)

if TYPE_CHECKING:
    from pyclaw.gateway.server import GatewayConnection, MethodHandler

logger = logging.getLogger(__name__)


def _profiles_dir() -> Path:
    from pyclaw.config.paths import resolve_state_dir
    d = resolve_state_dir() / "browser-profiles"
    d.mkdir(parents=True, exist_ok=True)
    return d


@dataclass
class _TabState:
    tab_id: str
    page: Any = None
    url: str = ""
    title: str = ""
    active: bool = False


@dataclass
class _ProfileRuntime:
    profile: str
    session_id: str = ""
    tabs: list[_TabState] = field(default_factory=list)
    tab_counter: int = 0


class BrowserRuntime:
    """Runtime backing browser RPC methods with real Playwright execution."""

    def __init__(self) -> None:
        self._guard = NavigationGuard()
        self._manager = BrowserSessionManager(
            BrowserConfig(headless=True, idle_timeout_s=600.0, max_sessions=5)
        )
        self._profiles: dict[str, _ProfileRuntime] = {}
        self._lock = asyncio.Lock()
        self._pw_available: bool | None = None

    def _check_playwright(self) -> bool:
        if self._pw_available is None:
            try:
                import playwright  # noqa: F401
                self._pw_available = True
            except ImportError:
                self._pw_available = False
        return self._pw_available

    def _get_rt(self, profile: str) -> _ProfileRuntime:
        key = profile or "pyclaw"
        if key not in self._profiles:
            self._profiles[key] = _ProfileRuntime(profile=key)
        return self._profiles[key]

    def _active_tab(self, rt: _ProfileRuntime) -> _TabState | None:
        for t in rt.tabs:
            if t.active:
                return t
        return rt.tabs[-1] if rt.tabs else None

    async def _ensure_started(self, rt: _ProfileRuntime) -> None:
        if rt.session_id:
            return
        storage = str(profile_path(str(_profiles_dir()), rt.profile))
        opts = LaunchOptions(
            headless=True,
            storage_state=storage if Path(storage).exists() else "",
        )
        session = await self._manager.create_session(options=opts)
        rt.session_id = session.session_id

    async def _new_page(self, rt: _ProfileRuntime) -> Any:
        ctx = self._manager.get_context(rt.session_id)
        if ctx is not None:
            return await ctx.new_page()
        return None

    async def _get_page_url(self, page: Any) -> str:
        try:
            return page.url if page else ""
        except Exception:
            return ""

    async def _get_page_title(self, page: Any) -> str:
        try:
            return await page.title() if page else ""
        except Exception:
            return ""

    async def status(self, profile: str) -> dict[str, Any]:
        async with self._lock:
            rt = self._get_rt(profile)
            active = self._active_tab(rt)
            return {
                "started": bool(rt.session_id),
                "profile": rt.profile,
                "activeSessions": self._manager.active_count,
                "activeTabId": active.tab_id if active else "",
                "activeUrl": active.url if active else "",
                "tabCount": len(rt.tabs),
                "blockedNavigations": self._guard.blocked_count,
                "playwrightAvailable": self._check_playwright(),
            }

    async def start(self, profile: str) -> dict[str, Any]:
        async with self._lock:
            rt = self._get_rt(profile)
            if rt.session_id:
                return {"started": True, "profile": profile, "sessionId": rt.session_id}
            await self._ensure_started(rt)
            return {"started": True, "profile": profile, "sessionId": rt.session_id}

    async def stop(self, profile: str) -> dict[str, Any]:
        async with self._lock:
            rt = self._get_rt(profile)
            for tab in rt.tabs:
                if tab.page:
                    try:
                        await tab.page.close()
                    except Exception:
                        pass
            if rt.session_id:
                await self._manager.close_session(rt.session_id)
            rt.session_id = ""
            rt.tabs.clear()
            return {"started": False, "profile": profile}

    async def tabs(self, profile: str) -> dict[str, Any]:
        async with self._lock:
            rt = self._get_rt(profile)
            result = []
            for tab in rt.tabs:
                tab.url = await self._get_page_url(tab.page)
                tab.title = await self._get_page_title(tab.page)
                result.append({
                    "id": tab.tab_id,
                    "url": tab.url,
                    "title": tab.title,
                    "active": tab.active,
                })
            return {"tabs": result}

    async def open(self, profile: str, url: str) -> dict[str, Any]:
        await self._ensure_allowed_url(url)
        async with self._lock:
            rt = self._get_rt(profile)
            await self._ensure_started(rt)
            page = await self._new_page(rt)
            rt.tab_counter += 1
            tab_id = f"tab-{rt.tab_counter}"
            for t in rt.tabs:
                t.active = False
            if page:
                try:
                    await page.goto(url, timeout=30000)
                except Exception as exc:
                    logger.warning("browser.open goto failed: %s", exc)
            tab = _TabState(tab_id=tab_id, page=page, url=url, active=True)
            tab.url = await self._get_page_url(page)
            tab.title = await self._get_page_title(page)
            rt.tabs.append(tab)
            self._manager.touch(rt.session_id)
            return {"opened": True, "tabId": tab_id, "url": tab.url, "title": tab.title}

    async def navigate(self, profile: str, url: str) -> dict[str, Any]:
        await self._ensure_allowed_url(url)
        async with self._lock:
            rt = self._get_rt(profile)
            tab = self._active_tab(rt)
            if not tab or not tab.page:
                pass  # will fall through to open
            else:
                try:
                    await tab.page.goto(url, timeout=30000)
                except Exception as exc:
                    logger.warning("browser.navigate goto failed: %s", exc)
                tab.url = await self._get_page_url(tab.page)
                tab.title = await self._get_page_title(tab.page)
                if rt.session_id:
                    self._manager.touch(rt.session_id)
                return {"navigated": True, "tabId": tab.tab_id, "url": tab.url, "title": tab.title}
        return await self.open(profile, url)

    async def click(self, profile: str, ref: str) -> dict[str, Any]:
        async with self._lock:
            rt = self._get_rt(profile)
            tab = self._active_tab(rt)
            if not tab:
                raise ValueError("No active tab")
            if tab.page:
                try:
                    await tab.page.click(ref, timeout=10000)
                except Exception as exc:
                    raise ValueError(f"Click failed: {exc}") from exc
                tab.url = await self._get_page_url(tab.page)
                tab.title = await self._get_page_title(tab.page)
            return {"clicked": True, "ref": ref, "tabId": tab.tab_id, "url": tab.url}

    async def type_text(self, profile: str, ref: str, text: str) -> dict[str, Any]:
        async with self._lock:
            rt = self._get_rt(profile)
            tab = self._active_tab(rt)
            if not tab:
                raise ValueError("No active tab")
            if tab.page:
                try:
                    await tab.page.fill(ref, text, timeout=10000)
                except Exception as exc:
                    raise ValueError(f"Type failed: {exc}") from exc
            return {"typed": True, "ref": ref, "length": len(text), "tabId": tab.tab_id}

    async def screenshot(self, profile: str, full_page: bool = True) -> dict[str, Any]:
        import base64 as b64mod
        async with self._lock:
            rt = self._get_rt(profile)
            tab = self._active_tab(rt)
            if not tab:
                raise ValueError("No active tab")
            if tab.page:
                try:
                    raw = await tab.page.screenshot(full_page=full_page, type="png")
                    encoded = b64mod.b64encode(raw).decode("ascii")
                    tab.url = await self._get_page_url(tab.page)
                    tab.title = await self._get_page_title(tab.page)
                    return {
                        "tabId": tab.tab_id,
                        "url": tab.url,
                        "title": tab.title,
                        "screenshotB64": encoded,
                        "mimeType": "image/png",
                        "sizeBytes": len(raw),
                    }
                except Exception as exc:
                    raise ValueError(f"Screenshot failed: {exc}") from exc
            raise ValueError("No Playwright page available for screenshot")

    async def snapshot(self, profile: str) -> dict[str, Any]:
        async with self._lock:
            rt = self._get_rt(profile)
            tab = self._active_tab(rt)
            if not tab:
                raise ValueError("No active tab")
            if tab.page:
                try:
                    html = await tab.page.content()
                    tab.url = await self._get_page_url(tab.page)
                    tab.title = await self._get_page_title(tab.page)
                    return {
                        "tabId": tab.tab_id,
                        "url": tab.url,
                        "title": tab.title,
                        "htmlLength": len(html),
                        "htmlPreview": html[:2000] if html else "",
                    }
                except Exception as exc:
                    raise ValueError(f"Snapshot failed: {exc}") from exc
            raise ValueError("No Playwright page available for snapshot")

    async def evaluate(self, profile: str, fn: str) -> dict[str, Any]:
        async with self._lock:
            rt = self._get_rt(profile)
            tab = self._active_tab(rt)
            if not tab:
                raise ValueError("No active tab")
            if tab.page:
                try:
                    result = await tab.page.evaluate(fn)
                    return {"ok": True, "tabId": tab.tab_id, "result": result}
                except Exception as exc:
                    raise ValueError(f"Evaluate failed: {exc}") from exc
            raise ValueError("No Playwright page available for evaluate")

    async def focus_tab(self, profile: str, tab_id: str) -> dict[str, Any]:
        async with self._lock:
            rt = self._get_rt(profile)
            found = False
            for t in rt.tabs:
                if t.tab_id == tab_id:
                    t.active = True
                    found = True
                    if t.page:
                        try:
                            await t.page.bring_to_front()
                        except Exception:
                            pass
                else:
                    t.active = False
            if not found:
                raise ValueError(f"Tab '{tab_id}' not found")
            return {"focused": True, "tabId": tab_id}

    async def close_tab(self, profile: str, tab_id: str) -> dict[str, Any]:
        async with self._lock:
            rt = self._get_rt(profile)
            target = None
            for i, t in enumerate(rt.tabs):
                if t.tab_id == tab_id:
                    target = rt.tabs.pop(i)
                    break
            if not target:
                raise ValueError(f"Tab '{tab_id}' not found")
            if target.page:
                try:
                    await target.page.close()
                except Exception:
                    pass
            if rt.tabs and not any(t.active for t in rt.tabs):
                rt.tabs[-1].active = True
            return {"closed": True, "tabId": tab_id, "remainingTabs": len(rt.tabs)}

    async def list_profiles(self) -> dict[str, Any]:
        profiles = list_profiles(str(_profiles_dir()))
        return {"profiles": profiles}

    async def create_profile(self, name: str) -> dict[str, Any]:
        import json
        p = profile_path(str(_profiles_dir()), name)
        if p.exists():
            return {"created": False, "profile": name, "reason": "already exists"}
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"cookies": [], "origins": []}))
        return {"created": True, "profile": name, "path": str(p)}

    async def delete_profile(self, name: str) -> dict[str, Any]:
        p = profile_path(str(_profiles_dir()), name)
        if not p.exists():
            return {"deleted": False, "profile": name, "reason": "not found"}
        p.unlink()
        return {"deleted": True, "profile": name}

    async def _ensure_allowed_url(self, url: str) -> None:
        result = self._guard.check_url(url)
        if not result.allowed:
            raise ValueError(result.reason or "Navigation blocked by SSRF guard")


_RUNTIME = BrowserRuntime()


def create_browser_handlers() -> dict[str, "MethodHandler"]:
    """Create browser.* RPC handlers backed by real Playwright execution."""

    async def _safe(method: str, coro: Any, conn: "GatewayConnection") -> None:
        try:
            result = await coro
            await conn.send_ok(method, result)
        except ValueError as exc:
            await conn.send_error(method, "invalid_state", str(exc))
        except RuntimeError as exc:
            await conn.send_error(method, "runtime_error", str(exc))
        except Exception as exc:
            logger.warning("%s unexpected error: %s", method, exc)
            await conn.send_error(method, "internal", str(exc))

    async def handle_browser_status(p: dict[str, Any] | None, conn: "GatewayConnection") -> None:
        profile = str((p or {}).get("profile", "pyclaw"))
        await _safe("browser.status", _RUNTIME.status(profile), conn)

    async def handle_browser_start(p: dict[str, Any] | None, conn: "GatewayConnection") -> None:
        profile = str((p or {}).get("profile", "pyclaw"))
        await _safe("browser.start", _RUNTIME.start(profile), conn)

    async def handle_browser_stop(p: dict[str, Any] | None, conn: "GatewayConnection") -> None:
        profile = str((p or {}).get("profile", "pyclaw"))
        await _safe("browser.stop", _RUNTIME.stop(profile), conn)

    async def handle_browser_tabs(p: dict[str, Any] | None, conn: "GatewayConnection") -> None:
        profile = str((p or {}).get("profile", "pyclaw"))
        await _safe("browser.tabs", _RUNTIME.tabs(profile), conn)

    async def handle_browser_open(p: dict[str, Any] | None, conn: "GatewayConnection") -> None:
        profile = str((p or {}).get("profile", "pyclaw"))
        url = str((p or {}).get("url", ""))
        if not url:
            await conn.send_error("browser.open", "invalid_params", "Missing 'url'")
            return
        await _safe("browser.open", _RUNTIME.open(profile, url), conn)

    async def handle_browser_navigate(p: dict[str, Any] | None, conn: "GatewayConnection") -> None:
        profile = str((p or {}).get("profile", "pyclaw"))
        url = str((p or {}).get("url", ""))
        if not url:
            await conn.send_error("browser.navigate", "invalid_params", "Missing 'url'")
            return
        await _safe("browser.navigate", _RUNTIME.navigate(profile, url), conn)

    async def handle_browser_click(p: dict[str, Any] | None, conn: "GatewayConnection") -> None:
        profile = str((p or {}).get("profile", "pyclaw"))
        ref = str((p or {}).get("ref", (p or {}).get("selector", "")))
        if not ref:
            await conn.send_error("browser.click", "invalid_params", "Missing 'ref'")
            return
        await _safe("browser.click", _RUNTIME.click(profile, ref), conn)

    async def handle_browser_type(p: dict[str, Any] | None, conn: "GatewayConnection") -> None:
        profile = str((p or {}).get("profile", "pyclaw"))
        ref = str((p or {}).get("ref", (p or {}).get("selector", "")))
        text = str((p or {}).get("text", ""))
        if not ref:
            await conn.send_error("browser.type", "invalid_params", "Missing 'ref'")
            return
        await _safe("browser.type", _RUNTIME.type_text(profile, ref, text), conn)

    async def handle_browser_screenshot(p: dict[str, Any] | None, conn: "GatewayConnection") -> None:
        profile = str((p or {}).get("profile", "pyclaw"))
        full_page = bool((p or {}).get("fullPage", True))
        await _safe("browser.screenshot", _RUNTIME.screenshot(profile, full_page=full_page), conn)

    async def handle_browser_snapshot(p: dict[str, Any] | None, conn: "GatewayConnection") -> None:
        profile = str((p or {}).get("profile", "pyclaw"))
        await _safe("browser.snapshot", _RUNTIME.snapshot(profile), conn)

    async def handle_browser_evaluate(p: dict[str, Any] | None, conn: "GatewayConnection") -> None:
        profile = str((p or {}).get("profile", "pyclaw"))
        fn = str((p or {}).get("fn", ""))
        if not fn:
            await conn.send_error("browser.evaluate", "invalid_params", "Missing 'fn'")
            return
        await _safe("browser.evaluate", _RUNTIME.evaluate(profile, fn), conn)

    async def handle_browser_profiles(p: dict[str, Any] | None, conn: "GatewayConnection") -> None:
        await _safe("browser.profiles", _RUNTIME.list_profiles(), conn)

    async def handle_browser_create_profile(p: dict[str, Any] | None, conn: "GatewayConnection") -> None:
        name = str((p or {}).get("name", ""))
        if not name:
            await conn.send_error("browser.createProfile", "invalid_params", "Missing 'name'")
            return
        await _safe("browser.createProfile", _RUNTIME.create_profile(name), conn)

    async def handle_browser_delete_profile(p: dict[str, Any] | None, conn: "GatewayConnection") -> None:
        name = str((p or {}).get("name", ""))
        if not name:
            await conn.send_error("browser.deleteProfile", "invalid_params", "Missing 'name'")
            return
        await _safe("browser.deleteProfile", _RUNTIME.delete_profile(name), conn)

    async def handle_browser_focus(p: dict[str, Any] | None, conn: "GatewayConnection") -> None:
        profile = str((p or {}).get("profile", "pyclaw"))
        tab_id = str((p or {}).get("tabId", ""))
        if not tab_id:
            await conn.send_error("browser.focus", "invalid_params", "Missing 'tabId'")
            return
        await _safe("browser.focus", _RUNTIME.focus_tab(profile, tab_id), conn)

    async def handle_browser_close(p: dict[str, Any] | None, conn: "GatewayConnection") -> None:
        profile = str((p or {}).get("profile", "pyclaw"))
        tab_id = str((p or {}).get("tabId", ""))
        if not tab_id:
            await conn.send_error("browser.close", "invalid_params", "Missing 'tabId'")
            return
        await _safe("browser.close", _RUNTIME.close_tab(profile, tab_id), conn)

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
        "browser.profiles": handle_browser_profiles,
        "browser.createProfile": handle_browser_create_profile,
        "browser.deleteProfile": handle_browser_delete_profile,
        "browser.focus": handle_browser_focus,
        "browser.close": handle_browser_close,
    }
