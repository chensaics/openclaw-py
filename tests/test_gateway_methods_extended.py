"""Tests for Phase 37: Gateway Methods + Sessions."""

from __future__ import annotations

import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

# Phase 37a: Extended RPC
from pyclaw.gateway.methods.extended import create_extended_handlers

# Phase 37b: Chat Advanced
from pyclaw.gateway.methods.chat_advanced import (
    ChatAbortManager,
    ChatAttachment,
    ChatParams,
    inject_time_context,
    sanitize_content,
    validate_chat_params,
)

# Phase 37c: Sessions Advanced
from pyclaw.sessions.advanced import (
    AdvancedSessionManager,
    BatchConfig,
    InputSource,
    SendStrategy,
    SessionMetadata,
    SessionOverrides,
    ThinkingLevel,
    TranscriptEvent,
    resolve_send_strategy,
)

# Phase 37d: Exec Approvals
from pyclaw.gateway.methods.exec_approvals import (
    ApprovalRequest,
    ApprovalStatus,
    ApprovalStore,
)


# =====================================================================
# Phase 37a: Extended RPC Methods
# =====================================================================

class TestExtendedHandlers:
    def test_handlers_registered(self) -> None:
        handlers = create_extended_handlers()
        # browser.status/navigate moved to browser_methods; extended has 13 handlers
        assert len(handlers) >= 13
        assert "tts.speak" in handlers
        assert "system.info" in handlers
        assert "doctor.run" in handlers
        assert "wizard.start" in handlers
        assert "push.send" in handlers
        assert "update.check" in handlers
        # browser keys intentionally removed from extended (now in browser_methods)
        assert "browser.status" not in handlers
        assert "browser.navigate" not in handlers

    @pytest.mark.asyncio
    async def test_tts_speak_missing_text(self) -> None:
        handlers = create_extended_handlers()
        conn = MagicMock()
        conn.send_error = AsyncMock()
        await handlers["tts.speak"]({}, conn)
        conn.send_error.assert_called_once()

    @pytest.mark.asyncio
    async def test_tts_speak_valid(self) -> None:
        handlers = create_extended_handlers()
        conn = MagicMock()
        conn.send_ok = AsyncMock()
        await handlers["tts.speak"]({"text": "Hello"}, conn)
        conn.send_ok.assert_called_once()

    @pytest.mark.asyncio
    async def test_system_info(self) -> None:
        handlers = create_extended_handlers()
        conn = MagicMock()
        conn.send_ok = AsyncMock()
        await handlers["system.info"](None, conn)
        conn.send_ok.assert_called_once()

    @pytest.mark.asyncio
    async def test_usage_get(self) -> None:
        handlers = create_extended_handlers()
        conn = MagicMock()
        conn.send_ok = AsyncMock()
        await handlers["usage.get"](None, conn)
        conn.send_ok.assert_called_once()


# =====================================================================
# Phase 37b: Chat Advanced
# =====================================================================

class TestChatParams:
    def test_validate_valid(self) -> None:
        params, err = validate_chat_params({"message": "Hello"})
        assert params is not None
        assert params.message == "Hello"
        assert err == ""

    def test_validate_missing_message(self) -> None:
        params, err = validate_chat_params({})
        assert params is None
        assert "Missing" in err

    def test_validate_empty_message(self) -> None:
        params, err = validate_chat_params({"message": "  "})
        assert params is None
        assert "non-empty" in err

    def test_validate_too_long(self) -> None:
        params, err = validate_chat_params({"message": "x" * 600000})
        assert params is None
        assert "too long" in err

    def test_validate_with_attachments(self) -> None:
        params, err = validate_chat_params({
            "message": "Check this",
            "attachments": [
                {"filename": "test.png", "mimeType": "image/png", "size": 1024},
            ],
        })
        assert params is not None
        assert params.has_attachments
        assert params.attachments[0].is_image

    def test_validate_temperature(self) -> None:
        params, _ = validate_chat_params({"message": "Hi", "temperature": "0.5"})
        assert params is not None
        assert params.temperature == 0.5

    def test_validate_temperature_invalid(self) -> None:
        params, _ = validate_chat_params({"message": "Hi", "temperature": "abc"})
        assert params is not None
        assert params.temperature is None


class TestSanitization:
    def test_remove_script(self) -> None:
        result = sanitize_content("Hello <script>alert(1)</script> World")
        assert "<script>" not in result
        assert "Hello" in result

    def test_remove_null_bytes(self) -> None:
        result = sanitize_content("Hello\x00World")
        assert "\x00" not in result

    def test_remove_comments(self) -> None:
        result = sanitize_content("Hello <!-- hidden --> World")
        assert "hidden" not in result


class TestTimeInjection:
    def test_inject(self) -> None:
        result = inject_time_context("You are helpful")
        assert "Current date" in result

    def test_no_duplicate(self) -> None:
        result = inject_time_context("Current date: 2026-01-01")
        assert result.count("Current date") == 1


class TestChatAbortManager:
    def test_register_and_abort(self) -> None:
        mgr = ChatAbortManager()
        mgr.register("s1")
        assert mgr.is_active("s1")
        assert mgr.active_count == 1

        assert mgr.abort("s1")
        assert not mgr.is_active("s1")

    def test_abort_nonexistent(self) -> None:
        mgr = ChatAbortManager()
        assert not mgr.abort("nonexistent")

    def test_abort_all(self) -> None:
        mgr = ChatAbortManager()
        mgr.register("s1")
        mgr.register("s2")
        count = mgr.abort_all()
        assert count == 2
        assert mgr.active_count == 0

    def test_list_active(self) -> None:
        mgr = ChatAbortManager()
        mgr.register("s1")
        active = mgr.list_active()
        assert len(active) == 1
        assert active[0]["sessionId"] == "s1"


# =====================================================================
# Phase 37c: Sessions Advanced
# =====================================================================

class TestAdvancedSessionManager:
    def test_get_or_create(self) -> None:
        mgr = AdvancedSessionManager()
        meta = mgr.get_or_create("s1", agent_id="a1")
        assert meta.session_id == "s1"
        assert meta.agent_id == "a1"
        assert mgr.count == 1

        # Same session
        meta2 = mgr.get_or_create("s1")
        assert meta2 is meta

    def test_set_overrides(self) -> None:
        mgr = AdvancedSessionManager()
        mgr.get_or_create("s1")
        overrides = SessionOverrides(model="gpt-4o", thinking_level=ThinkingLevel.HIGH)
        assert mgr.set_overrides("s1", overrides)
        meta = mgr.get("s1")
        assert meta is not None
        assert meta.overrides.model == "gpt-4o"
        assert meta.overrides.has_model_override

    def test_tags(self) -> None:
        meta = SessionMetadata(session_id="s1")
        meta.add_tag("env", "production")
        assert meta.get_tag("env") == "production"
        meta.add_tag("env", "staging")
        assert meta.get_tag("env") == "staging"
        assert meta.remove_tag("env")
        assert meta.get_tag("env") is None

    def test_transcript(self) -> None:
        meta = SessionMetadata(session_id="s1")
        meta.record_event(TranscriptEvent(event_type="message", role="user", content="Hello"))
        meta.record_event(TranscriptEvent(event_type="message", role="assistant", content="Hi"))
        assert meta.transcript_count == 2

    def test_list_with_filter(self) -> None:
        mgr = AdvancedSessionManager()
        s1 = mgr.get_or_create("s1", input_source=InputSource.CLI)
        s2 = mgr.get_or_create("s2", input_source=InputSource.WEB)
        s1.add_tag("test")

        assert len(mgr.list_sessions(source_filter=InputSource.CLI)) == 1
        assert len(mgr.list_sessions(tag_filter="test")) == 1


class TestSendStrategy:
    def test_immediate(self) -> None:
        overrides = SessionOverrides()
        assert resolve_send_strategy(overrides) == SendStrategy.IMMEDIATE

    def test_batched(self) -> None:
        overrides = SessionOverrides(send_strategy=SendStrategy.BATCHED)
        assert resolve_send_strategy(overrides) == SendStrategy.BATCHED


# =====================================================================
# Phase 37d: Exec Approvals
# =====================================================================

class TestApprovalStore:
    def test_create_and_get(self) -> None:
        store = ApprovalStore()
        req = store.create("rm -rf /tmp/test", args=["-rf", "/tmp/test"])
        assert req.status == ApprovalStatus.PENDING
        assert req.is_pending

        fetched = store.get(req.request_id)
        assert fetched is not None
        assert fetched.command == "rm -rf /tmp/test"

    def test_approve(self) -> None:
        store = ApprovalStore()
        req = store.create("npm install")
        resolved = store.resolve(req.request_id, True)
        assert resolved is not None
        assert resolved.status == ApprovalStatus.APPROVED
        assert resolved.resolved_at > 0

    def test_deny(self) -> None:
        store = ApprovalStore()
        req = store.create("dangerous_command")
        resolved = store.resolve(req.request_id, False)
        assert resolved is not None
        assert resolved.status == ApprovalStatus.DENIED

    def test_expiry(self) -> None:
        store = ApprovalStore()
        req = store.create("cmd", timeout_s=0.01)
        time.sleep(0.02)
        assert req.is_expired
        assert not req.is_pending

    def test_list_pending(self) -> None:
        store = ApprovalStore()
        store.create("cmd1")
        store.create("cmd2")
        req3 = store.create("cmd3")
        store.resolve(req3.request_id, True)

        pending = store.list_pending()
        assert len(pending) == 2

    def test_cancel(self) -> None:
        store = ApprovalStore()
        req = store.create("cmd")
        assert store.cancel(req.request_id)
        assert store.get(req.request_id).status == ApprovalStatus.CANCELLED

    def test_to_dict(self) -> None:
        req = ApprovalRequest(
            request_id="exec-1",
            command="ls",
            args=["-la"],
            risk_level="low",
        )
        d = req.to_dict()
        assert d["requestId"] == "exec-1"
        assert d["riskLevel"] == "low"

    def test_resolve_nonexistent(self) -> None:
        store = ApprovalStore()
        assert store.resolve("nonexistent", True) is None

    def test_cleanup(self) -> None:
        store = ApprovalStore()
        store.create("cmd", timeout_s=0.01)
        time.sleep(0.02)
        cleaned = store.cleanup_expired()
        assert cleaned >= 1
