"""Tests for Phase 34: Browser automation (Playwright thin adapter layer)."""

from __future__ import annotations

import asyncio
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

# Phase 34a: Session Manager
from pyclaw.browser.session_manager import (
    BrowserConfig,
    BrowserSessionManager,
    BrowserType,
    LaunchOptions,
    ProfileConfig,
    SessionInfo,
    SessionState,
    list_profiles,
    profile_path,
)

# Phase 34b: Navigation Guard
from pyclaw.browser.navigation_guard import (
    NavigationGuard,
    NavigationPolicy,
)

# Phase 34c: Agent Tools
from pyclaw.browser.agent_tools import (
    BROWSER_TOOL_DEFINITIONS,
    BrowserAction,
    BrowserActionResult,
    BrowserActionType,
    BrowserToolExecutor,
    parse_browser_tool_call,
)

# Phase 34d: Bridge Server
from pyclaw.browser.bridge_server import (
    AuthTokenRegistry,
    BridgeConfig,
    BridgeServer,
    DOMSnapshot,
    TabInfo,
    generate_csrf_token,
    validate_csrf_token,
)

# Phase 34e: Screenshot
from pyclaw.browser.screenshot import (
    CDPScreenshotParams,
    ScreenshotFormat,
    ScreenshotOptions,
    ScreenshotResult,
    ScreenshotService,
    decode_cdp_screenshot,
)


# =====================================================================
# Phase 34a: Session Manager
# =====================================================================

class TestBrowserSessionManager:
    @pytest.mark.asyncio
    async def test_create_session(self) -> None:
        mgr = BrowserSessionManager(BrowserConfig(max_sessions=3))
        session = await mgr.create_session()
        assert session.state == SessionState.ACTIVE
        assert mgr.active_count == 1

    @pytest.mark.asyncio
    async def test_max_sessions(self) -> None:
        mgr = BrowserSessionManager(BrowserConfig(max_sessions=2))
        await mgr.create_session()
        await mgr.create_session()
        with pytest.raises(RuntimeError, match="Max browser sessions"):
            await mgr.create_session()

    @pytest.mark.asyncio
    async def test_close_session(self) -> None:
        mgr = BrowserSessionManager(BrowserConfig(max_sessions=5))
        session = await mgr.create_session()
        result = await mgr.close_session(session.session_id)
        assert result
        assert mgr.active_count == 0

    @pytest.mark.asyncio
    async def test_close_nonexistent(self) -> None:
        mgr = BrowserSessionManager()
        assert not await mgr.close_session("nonexistent")

    @pytest.mark.asyncio
    async def test_idle_cleanup(self) -> None:
        mgr = BrowserSessionManager(BrowserConfig(idle_timeout_s=0.01))
        session = await mgr.create_session()
        time.sleep(0.02)
        closed = await mgr.cleanup_idle()
        assert closed == 1
        assert mgr.active_count == 0

    @pytest.mark.asyncio
    async def test_touch_prevents_idle(self) -> None:
        mgr = BrowserSessionManager(BrowserConfig(idle_timeout_s=0.5))
        session = await mgr.create_session()
        mgr.touch(session.session_id)
        idle = mgr.find_idle_sessions()
        assert len(idle) == 0

    @pytest.mark.asyncio
    async def test_close_all(self) -> None:
        mgr = BrowserSessionManager(BrowserConfig(max_sessions=5))
        await mgr.create_session()
        await mgr.create_session()
        closed = await mgr.close_all()
        assert closed == 2

    def test_launch_options_to_playwright(self) -> None:
        opts = LaunchOptions(headless=False, args=["--no-sandbox"], proxy="http://proxy:8080")
        pw = opts.to_playwright_args()
        assert pw["headless"] is False
        assert "--no-sandbox" in pw["args"]
        assert pw["proxy"]["server"] == "http://proxy:8080"

    def test_launch_options_context(self) -> None:
        opts = LaunchOptions(viewport_width=1920, viewport_height=1080, storage_state="/tmp/state.json")
        ctx = opts.to_context_args()
        assert ctx["viewport"]["width"] == 1920
        assert ctx["storage_state"] == "/tmp/state.json"


class TestProfiles:
    def test_profile_path(self, tmp_path: Any) -> None:
        p = profile_path(str(tmp_path), "default")
        assert p.name == "default.json"

    def test_list_profiles(self, tmp_path: Any) -> None:
        (tmp_path / "profile1.json").write_text("{}")
        (tmp_path / "profile2.json").write_text("{}")
        (tmp_path / "not_a_profile.txt").write_text("")
        profiles = list_profiles(str(tmp_path))
        assert "profile1" in profiles
        assert "profile2" in profiles
        assert len(profiles) == 2

    def test_list_profiles_empty(self) -> None:
        assert list_profiles("/nonexistent") == []


# =====================================================================
# Phase 34b: Navigation Guard
# =====================================================================

class TestNavigationGuard:
    def test_allow_safe_url(self) -> None:
        guard = NavigationGuard()
        result = guard.check_url("https://example.com")
        assert result.allowed

    def test_block_localhost(self) -> None:
        guard = NavigationGuard()
        result = guard.check_url("http://localhost:8080/admin")
        assert not result.allowed
        assert "Blocked hostname" in result.reason

    def test_block_private_ip(self) -> None:
        guard = NavigationGuard()
        result = guard.check_url("http://192.168.1.1/admin")
        assert not result.allowed

    def test_block_data_url(self) -> None:
        guard = NavigationGuard()
        result = guard.check_url("data:text/html,<script>alert(1)</script>")
        assert not result.allowed
        assert "data:" in result.reason

    def test_allow_data_url_when_configured(self) -> None:
        policy = NavigationPolicy(allow_data_urls=True)
        guard = NavigationGuard(policy)
        result = guard.check_url("data:text/plain,hello")
        assert result.allowed

    def test_block_javascript_url(self) -> None:
        guard = NavigationGuard()
        result = guard.check_url("javascript:alert(1)")
        assert not result.allowed

    def test_allow_about_blank(self) -> None:
        guard = NavigationGuard()
        result = guard.check_url("about:blank")
        assert result.allowed

    def test_block_ftp(self) -> None:
        guard = NavigationGuard()
        result = guard.check_url("ftp://files.example.com/data")
        assert not result.allowed

    def test_redirect_chain(self) -> None:
        guard = NavigationGuard()
        result = guard.check_redirect_chain([
            "https://example.com",
            "https://www.example.com",
        ])
        assert result.allowed
        assert result.redirect_count == 2

    def test_redirect_chain_with_private(self) -> None:
        guard = NavigationGuard()
        result = guard.check_redirect_chain([
            "https://example.com",
            "http://192.168.1.1/internal",
        ])
        assert not result.allowed

    def test_too_many_redirects(self) -> None:
        guard = NavigationGuard(NavigationPolicy(max_redirects=2))
        result = guard.check_redirect_chain(["https://a.com", "https://b.com", "https://c.com"])
        assert not result.allowed
        assert "Too many redirects" in result.reason

    def test_disabled(self) -> None:
        guard = NavigationGuard(NavigationPolicy(enabled=False))
        result = guard.check_url("http://localhost:9999")
        assert result.allowed

    def test_blocked_count(self) -> None:
        guard = NavigationGuard()
        guard.check_url("http://localhost")
        guard.check_url("http://127.0.0.1")
        assert guard.blocked_count == 2

    def test_add_blocked_domain(self) -> None:
        guard = NavigationGuard()
        guard.add_blocked_domain("evil.com")
        result = guard.check_url("https://evil.com/phish")
        assert not result.allowed


# =====================================================================
# Phase 34c: Agent Tools
# =====================================================================

class MockPage:
    """Minimal mock Playwright page."""
    def __init__(self) -> None:
        self._url = "https://example.com"
        self._title = "Example"
        self._content = "<html><body>Hello</body></html>"

    @property
    def url(self) -> str:
        return self._url

    async def goto(self, url: str, **kwargs: Any) -> None:
        self._url = url

    async def click(self, selector: str, **kwargs: Any) -> None:
        pass

    async def fill(self, selector: str, value: str, **kwargs: Any) -> None:
        pass

    async def evaluate(self, expression: str) -> Any:
        return f"eval({expression})"

    async def screenshot(self, **kwargs: Any) -> bytes:
        return b"\x89PNG\r\n\x1a\n" + b"\x00" * 100

    async def title(self) -> str:
        return self._title

    async def content(self) -> str:
        return self._content

    async def go_back(self, **kwargs: Any) -> None:
        pass

    async def go_forward(self, **kwargs: Any) -> None:
        pass

    async def reload(self, **kwargs: Any) -> None:
        pass

    async def close(self) -> None:
        pass


class TestBrowserToolExecutor:
    @pytest.mark.asyncio
    async def test_navigate(self) -> None:
        executor = BrowserToolExecutor()
        page = MockPage()
        result = await executor.execute(page, BrowserAction(
            action_type=BrowserActionType.NAVIGATE, url="https://test.com",
        ))
        assert result.success
        assert page.url == "https://test.com"

    @pytest.mark.asyncio
    async def test_click(self) -> None:
        executor = BrowserToolExecutor()
        result = await executor.execute(MockPage(), BrowserAction(
            action_type=BrowserActionType.CLICK, selector="#btn",
        ))
        assert result.success

    @pytest.mark.asyncio
    async def test_type(self) -> None:
        executor = BrowserToolExecutor()
        result = await executor.execute(MockPage(), BrowserAction(
            action_type=BrowserActionType.TYPE, selector="#input", value="hello",
        ))
        assert result.success

    @pytest.mark.asyncio
    async def test_screenshot(self) -> None:
        executor = BrowserToolExecutor()
        result = await executor.execute(MockPage(), BrowserAction(
            action_type=BrowserActionType.SCREENSHOT,
        ))
        assert result.success
        assert result.screenshot_b64

    @pytest.mark.asyncio
    async def test_evaluate(self) -> None:
        executor = BrowserToolExecutor()
        result = await executor.execute(MockPage(), BrowserAction(
            action_type=BrowserActionType.EVALUATE, value="1+1",
        ))
        assert result.success
        assert "eval" in str(result.data)

    @pytest.mark.asyncio
    async def test_snapshot(self) -> None:
        executor = BrowserToolExecutor()
        result = await executor.execute(MockPage(), BrowserAction(
            action_type=BrowserActionType.SNAPSHOT,
        ))
        assert result.success
        assert "html_length" in result.data

    @pytest.mark.asyncio
    async def test_go_back(self) -> None:
        executor = BrowserToolExecutor()
        result = await executor.execute(MockPage(), BrowserAction(
            action_type=BrowserActionType.GO_BACK,
        ))
        assert result.success

    @pytest.mark.asyncio
    async def test_wait(self) -> None:
        executor = BrowserToolExecutor()
        result = await executor.execute(MockPage(), BrowserAction(
            action_type=BrowserActionType.WAIT, options={"ms": 10},
        ))
        assert result.success

    @pytest.mark.asyncio
    async def test_error_handling(self) -> None:
        executor = BrowserToolExecutor()
        page = MockPage()
        page.click = AsyncMock(side_effect=RuntimeError("element not found"))
        result = await executor.execute(page, BrowserAction(
            action_type=BrowserActionType.CLICK, selector="#missing",
        ))
        assert not result.success
        assert "element not found" in result.error


class TestToolResult:
    def test_format_success(self) -> None:
        r = BrowserActionResult(
            success=True, action_type=BrowserActionType.NAVIGATE,
            url="https://example.com", title="Example",
        )
        text = r.to_tool_result()
        assert "example.com" in text

    def test_format_error(self) -> None:
        r = BrowserActionResult(
            success=False, action_type=BrowserActionType.CLICK,
            error="timeout",
        )
        assert "Error" in r.to_tool_result()


class TestParseToolCall:
    def test_navigate(self) -> None:
        action = parse_browser_tool_call("browser_navigate", {"url": "https://example.com"})
        assert action is not None
        assert action.action_type == BrowserActionType.NAVIGATE
        assert action.url == "https://example.com"

    def test_click(self) -> None:
        action = parse_browser_tool_call("browser_click", {"selector": "#btn"})
        assert action is not None
        assert action.selector == "#btn"

    def test_unknown(self) -> None:
        assert parse_browser_tool_call("unknown_tool", {}) is None

    def test_definitions_exist(self) -> None:
        assert len(BROWSER_TOOL_DEFINITIONS) >= 7


# =====================================================================
# Phase 34d: Bridge Server
# =====================================================================

class TestAuthTokenRegistry:
    def test_generate_and_validate(self) -> None:
        registry = AuthTokenRegistry()
        token = registry.generate()
        assert registry.validate(token)
        assert not registry.validate("invalid")

    def test_revoke(self) -> None:
        registry = AuthTokenRegistry()
        token = registry.generate()
        assert registry.revoke(token)
        assert not registry.validate(token)

    def test_revoke_all(self) -> None:
        registry = AuthTokenRegistry()
        registry.generate()
        registry.generate()
        count = registry.revoke_all()
        assert count == 2
        assert registry.active_count == 0


class TestCSRF:
    def test_generate_validate(self) -> None:
        token = generate_csrf_token("session1", "secret123")
        assert validate_csrf_token(token, "session1", "secret123")

    def test_different_session_fails(self) -> None:
        token = generate_csrf_token("session1", "secret123")
        assert not validate_csrf_token(token, "session2", "secret123")


class TestBridgeServer:
    def test_create_bridge(self) -> None:
        bridge = BridgeServer()
        assert bridge.auth_token

    def test_update_tabs(self) -> None:
        bridge = BridgeServer()
        count = bridge.update_tabs([
            {"id": "1", "title": "Google", "url": "https://google.com", "active": True},
            {"id": "2", "title": "GitHub", "url": "https://github.com"},
        ])
        assert count == 2
        tabs = bridge.get_tabs()
        assert len(tabs) >= 2
        active = bridge.get_active_tab()
        assert active is not None
        assert active.title == "Google"

    def test_store_snapshot(self) -> None:
        bridge = BridgeServer()
        snapshot = DOMSnapshot(
            tab_id="1", html="<html>test</html>", text="test",
            url="https://example.com", title="Test",
        )
        assert bridge.store_snapshot(snapshot)
        retrieved = bridge.get_snapshot("1")
        assert retrieved is not None
        assert retrieved.html == "<html>test</html>"

    def test_snapshot_too_large(self) -> None:
        bridge = BridgeServer(BridgeConfig(max_snapshot_size=100))
        snapshot = DOMSnapshot(tab_id="1", html="x" * 200)
        assert not bridge.store_snapshot(snapshot)

    def test_csrf_integration(self) -> None:
        bridge = BridgeServer()
        token = bridge.get_csrf_token("sess1")
        assert bridge.validate_csrf(token, "sess1")
        assert not bridge.validate_csrf("bad", "sess1")

    @pytest.mark.asyncio
    async def test_handle_tabs_update(self) -> None:
        bridge = BridgeServer()
        from pyclaw.browser.relay import RelayMessage
        msg = RelayMessage(
            type="action",
            payload={"type": "tabs_update", "tabs": [{"id": "1", "title": "Tab"}]},
        )
        result = await bridge.handle_message(msg)
        assert result is not None
        assert result["type"] == "tabs_updated"

    @pytest.mark.asyncio
    async def test_handle_snapshot(self) -> None:
        bridge = BridgeServer()
        from pyclaw.browser.relay import RelayMessage
        msg = RelayMessage(
            type="action",
            payload={
                "type": "dom_snapshot",
                "tab_id": "1",
                "html": "<p>test</p>",
                "url": "https://test.com",
            },
        )
        result = await bridge.handle_message(msg)
        assert result is not None
        assert result["success"]


# =====================================================================
# Phase 34e: Screenshot
# =====================================================================

class TestScreenshotService:
    @pytest.mark.asyncio
    async def test_capture(self) -> None:
        service = ScreenshotService()
        page = MockPage()
        result = await service.capture(page)
        assert result.success
        assert result.size_bytes > 0
        assert service.capture_count == 1

    @pytest.mark.asyncio
    async def test_capture_jpeg(self) -> None:
        service = ScreenshotService()
        result = await service.capture(MockPage(), ScreenshotOptions(
            format=ScreenshotFormat.JPEG, quality=90,
        ))
        assert result.success

    @pytest.mark.asyncio
    async def test_capture_error(self) -> None:
        service = ScreenshotService()
        page = MockPage()
        page.screenshot = AsyncMock(side_effect=RuntimeError("no page"))
        result = await service.capture(page)
        assert not result.success
        assert "no page" in result.error


class TestScreenshotResult:
    def test_to_base64(self) -> None:
        result = ScreenshotResult(data=b"hello")
        b64 = result.to_base64()
        assert b64  # Non-empty
        import base64
        assert base64.b64decode(b64) == b"hello"

    def test_to_data_url(self) -> None:
        result = ScreenshotResult(data=b"test", format=ScreenshotFormat.PNG)
        url = result.to_data_url()
        assert url.startswith("data:image/png;base64,")

    def test_empty_result(self) -> None:
        result = ScreenshotResult()
        assert not result.success
        assert result.to_base64() == ""


class TestCDPScreenshot:
    def test_params(self) -> None:
        p = CDPScreenshotParams(format="jpeg", quality=85)
        params = p.to_cdp_params()
        assert params["format"] == "jpeg"
        assert params["quality"] == 85

    def test_decode(self) -> None:
        import base64
        b64 = base64.b64encode(b"png_data").decode()
        result = decode_cdp_screenshot(b64)
        assert result.success
        assert result.data == b"png_data"

    def test_decode_invalid(self) -> None:
        result = decode_cdp_screenshot("not_base64!!!")
        assert not result.success
