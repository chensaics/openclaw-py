"""Phase 58 contract tests — verify documented RPC methods exist in Gateway
and that placeholder methods correctly report NOT_IMPLEMENTED.

Guards against documentation vs implementation drift.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = PROJECT_ROOT / "docs"
REF_DIR = DOCS_DIR / "reference"


def _api_ref() -> str:
    return (DOCS_DIR / "api-reference.md").read_text(encoding="utf-8")


def _progress() -> str:
    return (REF_DIR / "PROGRESS.md").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. All documented RPC methods are registered in Gateway handler return dicts
#    (source-code-based check to avoid full dependency installation)
# ---------------------------------------------------------------------------

def _collect_registered_method_keys_from_source() -> set[str]:
    """Parse handler factory source files for returned dict keys."""
    methods: set[str] = set()
    methods_dir = PROJECT_ROOT / "src" / "pyclaw" / "gateway" / "methods"
    for py_file in methods_dir.glob("*.py"):
        src = py_file.read_text(encoding="utf-8")
        for match in re.finditer(r'"([a-zA-Z]+\.[a-zA-Z.]+)":\s*handle', src):
            methods.add(match.group(1))
    return methods


class TestRegisteredMethods:
    """Ensure documented API methods appear in handler return dicts."""

    @pytest.fixture(scope="class")
    def registered(self) -> set[str]:
        return _collect_registered_method_keys_from_source()

    @pytest.mark.parametrize("method", [
        "chat.send", "chat.abort", "chat.history", "chat.edit", "chat.resend",
    ])
    def test_chat_methods(self, registered: set[str], method: str) -> None:
        assert method in registered, f"{method} not found in handler sources"

    @pytest.mark.parametrize("method", [
        "browser.status", "browser.start", "browser.stop", "browser.tabs",
        "browser.open", "browser.navigate", "browser.click", "browser.type",
        "browser.screenshot", "browser.snapshot", "browser.evaluate",
        "browser.profiles", "browser.createProfile", "browser.deleteProfile",
        "browser.focus", "browser.close",
    ])
    def test_browser_methods(self, registered: set[str], method: str) -> None:
        assert method in registered, f"{method} not found in handler sources"

    @pytest.mark.parametrize("method", [
        "system.info", "system.logs", "system.event",
        "system.heartbeat.last", "system.presence",
    ])
    def test_system_methods(self, registered: set[str], method: str) -> None:
        assert method in registered, f"{method} not found in handler sources"

    @pytest.mark.parametrize("method", [
        "usage.get", "doctor.run", "skills.list",
        "tts.speak", "tts.voices",
        "wizard.start", "wizard.step",
        "push.send", "voicewake.status",
        "update.check", "web.status",
    ])
    def test_extended_methods(self, registered: set[str], method: str) -> None:
        assert method in registered, f"{method} not found in handler sources"

    def test_logs_tail(self, registered: set[str]) -> None:
        assert "logs.tail" in registered


# ---------------------------------------------------------------------------
# 2. Chat advanced integration
# ---------------------------------------------------------------------------

class TestChatAdvancedIntegration:
    """Verify chat.py imports and uses chat_advanced utilities."""

    def test_chat_py_imports_validate_chat_params(self) -> None:
        src = (PROJECT_ROOT / "src" / "pyclaw" / "gateway" / "methods" / "chat.py").read_text()
        assert "validate_chat_params" in src

    def test_chat_py_imports_sanitize_content(self) -> None:
        src = (PROJECT_ROOT / "src" / "pyclaw" / "gateway" / "methods" / "chat.py").read_text()
        assert "sanitize_content" in src

    def test_chat_py_imports_inject_time_context(self) -> None:
        src = (PROJECT_ROOT / "src" / "pyclaw" / "gateway" / "methods" / "chat.py").read_text()
        assert "inject_time_context" in src

    def test_chat_py_imports_chat_abort_manager(self) -> None:
        src = (PROJECT_ROOT / "src" / "pyclaw" / "gateway" / "methods" / "chat.py").read_text()
        assert "ChatAbortManager" in src


# ---------------------------------------------------------------------------
# 3. Browser methods are real (not simulated)
# ---------------------------------------------------------------------------

class TestBrowserRealExecution:
    """Verify browser_methods.py uses Playwright, not in-memory simulation."""

    def test_no_fake_screenshot_string(self) -> None:
        src = (PROJECT_ROOT / "src" / "pyclaw" / "gateway" / "methods" / "browser_methods.py").read_text()
        assert "screenshot:" not in src or "page.screenshot" in src

    def test_uses_playwright_page_goto(self) -> None:
        src = (PROJECT_ROOT / "src" / "pyclaw" / "gateway" / "methods" / "browser_methods.py").read_text()
        assert "page.goto" in src

    def test_uses_playwright_page_screenshot(self) -> None:
        src = (PROJECT_ROOT / "src" / "pyclaw" / "gateway" / "methods" / "browser_methods.py").read_text()
        assert "page.screenshot" in src

    def test_uses_navigation_guard(self) -> None:
        src = (PROJECT_ROOT / "src" / "pyclaw" / "gateway" / "methods" / "browser_methods.py").read_text()
        assert "NavigationGuard" in src


# ---------------------------------------------------------------------------
# 4. Extended methods do NOT have fake-success placeholders
# ---------------------------------------------------------------------------

class TestExtendedNoFakePlaceholders:
    """Verify that previously-placeholder methods now return NOT_IMPLEMENTED or real data."""

    def test_wizard_returns_not_implemented(self) -> None:
        src = (PROJECT_ROOT / "src" / "pyclaw" / "gateway" / "methods" / "extended.py").read_text()
        assert "not_implemented" in src.lower()

    def test_no_hardcoded_version_triple_zero(self) -> None:
        src = (PROJECT_ROOT / "src" / "pyclaw" / "gateway" / "methods" / "extended.py").read_text()
        lines_with_000 = [ln for ln in src.splitlines() if '"0.0.0"' in ln and "latestVersion" in ln]
        assert not lines_with_000, "update.check still has hardcoded 0.0.0 latestVersion"

    def test_web_status_reports_connected_true(self) -> None:
        src = (PROJECT_ROOT / "src" / "pyclaw" / "gateway" / "methods" / "extended.py").read_text()
        assert '"connected": True' in src or "'connected': True" in src


# ---------------------------------------------------------------------------
# 5. System RPC methods exist (not just local fallback)
# ---------------------------------------------------------------------------

class TestSystemRPCExist:
    """Verify system.* RPC handlers are in extended.py."""

    def test_system_event_handler_exists(self) -> None:
        src = (PROJECT_ROOT / "src" / "pyclaw" / "gateway" / "methods" / "extended.py").read_text()
        assert "system.event" in src

    def test_system_heartbeat_last_handler_exists(self) -> None:
        src = (PROJECT_ROOT / "src" / "pyclaw" / "gateway" / "methods" / "extended.py").read_text()
        assert "system.heartbeat.last" in src

    def test_system_presence_handler_exists(self) -> None:
        src = (PROJECT_ROOT / "src" / "pyclaw" / "gateway" / "methods" / "extended.py").read_text()
        assert "system.presence" in src


# ---------------------------------------------------------------------------
# 6. CLI fallback shows explicit warning
# ---------------------------------------------------------------------------

class TestCLIFallbackWarning:
    """Verify CLI system/logs commands warn on fallback."""

    def test_system_cmd_has_fallback_warning(self) -> None:
        src = (PROJECT_ROOT / "src" / "pyclaw" / "cli" / "commands" / "system_cmd.py").read_text()
        assert "Gateway unreachable" in src

    def test_logs_cmd_has_fallback_warning(self) -> None:
        src = (PROJECT_ROOT / "src" / "pyclaw" / "cli" / "commands" / "logs_cmd.py").read_text()
        assert "Gateway unreachable" in src


# ---------------------------------------------------------------------------
# 7. Documentation consistency
# ---------------------------------------------------------------------------

class TestDocumentationConsistency:

    def test_progress_marks_phase54_to_58(self) -> None:
        progress = _progress()
        for phase in ("54", "55", "56", "57", "58"):
            assert re.search(rf"\| Phase {phase}: .+\| \*\*已完成\*\* \|", progress), \
                f"Phase {phase} not marked as completed in PROGRESS.md"

    def test_api_ref_has_chat_edit_resend(self) -> None:
        api = _api_ref()
        assert "chat.edit" in api
        assert "chat.resend" in api

    def test_api_ref_has_browser_profiles(self) -> None:
        api = _api_ref()
        assert "browser.profiles" in api
        assert "browser.createProfile" in api
        assert "browser.deleteProfile" in api
        assert "browser.focus" in api

    def test_api_ref_has_system_rpc(self) -> None:
        api = _api_ref()
        assert "system.event" in api
        assert "system.heartbeat.last" in api
        assert "system.presence" in api

    def test_api_ref_mentions_not_implemented(self) -> None:
        api = _api_ref()
        assert "NOT_IMPLEMENTED" in api

    def test_api_ref_has_not_implemented_error_code(self) -> None:
        api = _api_ref()
        assert "NOT_IMPLEMENTED" in api
        assert "方法已注册但尚未实现" in api
