"""Tests for ACP enhancements — control plane, session mapper, event mapper, acpx."""

from __future__ import annotations

import json

import pytest

from pyclaw.acp.acpx_runtime import (
    AcpxHandleState,
    decode_handle_state,
    encode_handle_state,
    resolve_acpx_config,
)
from pyclaw.acp.control_plane import (
    AcpRuntimeEvent,
    AcpRuntimeProtocol,
    AcpRunTurnInput,
    AcpSessionManager,
    AcpSessionResolution,
    AcpSessionStatus,
)
from pyclaw.acp.event_mapper import (
    extract_attachments_from_prompt,
    extract_text_from_prompt,
    format_tool_title,
    infer_tool_kind,
)
from pyclaw.acp.session_mapper import AcpSessionMetaHints, parse_session_meta, resolve_session_key
from pyclaw.acp.thread_ownership import ThreadOwnershipTracker

# ---------------------------------------------------------------------------
# Session mapper
# ---------------------------------------------------------------------------


class TestParseSessionMeta:
    def test_none_input(self) -> None:
        result = parse_session_meta(None)
        assert result.session_key is None
        assert result.reset_session is False

    def test_parse_session_key(self) -> None:
        meta = {"sessionKey": "my-session", "reset": True}
        result = parse_session_meta(meta)
        assert result.session_key == "my-session"
        assert result.reset_session is True

    def test_parse_label(self) -> None:
        meta = {"label": "My Label"}
        result = parse_session_meta(meta)
        assert result.session_label == "My Label"

    def test_alias_keys(self) -> None:
        meta = {"session": "alias-key", "requireExisting": True}
        result = parse_session_meta(meta)
        assert result.session_key == "alias-key"
        assert result.require_existing is True


class TestResolveSessionKey:
    @pytest.mark.asyncio
    async def test_returns_meta_key_directly(self) -> None:
        meta = AcpSessionMetaHints(session_key="direct-key")

        async def mock_gateway(method: str, params: dict) -> dict:
            return {}

        key = await resolve_session_key(meta=meta, fallback_key="fallback", gateway_request=mock_gateway)
        assert key == "direct-key"

    @pytest.mark.asyncio
    async def test_returns_fallback(self) -> None:
        meta = AcpSessionMetaHints()

        async def mock_gateway(method: str, params: dict) -> dict:
            return {}

        key = await resolve_session_key(meta=meta, fallback_key="my-fallback", gateway_request=mock_gateway)
        assert key == "my-fallback"

    @pytest.mark.asyncio
    async def test_resolves_label_via_gateway(self) -> None:
        meta = AcpSessionMetaHints(session_label="My Session")

        async def mock_gateway(method: str, params: dict) -> dict:
            if method == "sessions.resolve":
                return {"key": "resolved-key"}
            return {}

        key = await resolve_session_key(meta=meta, fallback_key="fallback", gateway_request=mock_gateway)
        assert key == "resolved-key"


# ---------------------------------------------------------------------------
# Event mapper
# ---------------------------------------------------------------------------


class TestExtractText:
    def test_string_input(self) -> None:
        assert extract_text_from_prompt("hello") == "hello"

    def test_content_parts(self) -> None:
        parts = [
            {"type": "text", "text": "hello"},
            {"type": "text", "text": "world"},
        ]
        assert extract_text_from_prompt(parts) == "hello\nworld"

    def test_empty(self) -> None:
        assert extract_text_from_prompt(None) == ""


class TestExtractAttachments:
    def test_image_attachment(self) -> None:
        parts = [{"type": "input_image", "source": {"url": "https://example.com/img.png"}}]
        result = extract_attachments_from_prompt(parts)
        assert len(result) == 1
        assert result[0]["type"] == "image"

    def test_no_attachments(self) -> None:
        assert extract_attachments_from_prompt("plain text") == []


class TestFormatToolTitle:
    def test_no_args(self) -> None:
        assert format_tool_title("read_file") == "read_file"

    def test_with_args(self) -> None:
        result = format_tool_title("read_file", {"path": "/tmp/test.txt"})
        assert "read_file" in result
        assert "path=" in result


class TestInferToolKind:
    def test_read_tools(self) -> None:
        assert infer_tool_kind("read_file") == "read"
        assert infer_tool_kind("list_dir") == "read"

    def test_write_tools(self) -> None:
        assert infer_tool_kind("write_file") == "write"

    def test_exec_tools(self) -> None:
        assert infer_tool_kind("exec_command") == "exec"

    def test_generic(self) -> None:
        assert infer_tool_kind("custom_tool") == "tool"


# ---------------------------------------------------------------------------
# Acpx handle encoding
# ---------------------------------------------------------------------------


class TestAcpxHandleEncoding:
    def test_roundtrip(self) -> None:
        state = AcpxHandleState(name="test", agent="codex", cwd="/tmp", mode="persistent")
        encoded = encode_handle_state(state)
        assert encoded.startswith("acpx:v1:")
        decoded = decode_handle_state(encoded)
        assert decoded is not None
        assert decoded.name == "test"
        assert decoded.agent == "codex"
        assert decoded.cwd == "/tmp"
        assert decoded.mode == "persistent"

    def test_with_optional_fields(self) -> None:
        state = AcpxHandleState(
            name="s1",
            agent="gpt",
            cwd="/home",
            mode="oneshot",
            acpx_record_id="rec-123",
        )
        encoded = encode_handle_state(state)
        decoded = decode_handle_state(encoded)
        assert decoded is not None
        assert decoded.acpx_record_id == "rec-123"

    def test_invalid_prefix(self) -> None:
        assert decode_handle_state("invalid:v1:abc") is None

    def test_invalid_mode(self) -> None:
        # Encode manually with bad mode
        import base64

        payload = json.dumps({"name": "x", "agent": "y", "cwd": "/", "mode": "bad"})
        encoded = base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")
        assert decode_handle_state(f"acpx:v1:{encoded}") is None


class TestResolveAcpxConfig:
    def test_defaults(self) -> None:
        cfg = resolve_acpx_config()
        assert cfg.permission_mode == "approve-reads"
        assert cfg.non_interactive_permissions == "fail"
        assert cfg.queue_owner_ttl_seconds == 0.1

    def test_custom_config(self) -> None:
        cfg = resolve_acpx_config({"permissionMode": "deny-all", "timeoutSeconds": 30})
        assert cfg.permission_mode == "deny-all"
        assert cfg.timeout_seconds == 30


# ---------------------------------------------------------------------------
# Control plane
# ---------------------------------------------------------------------------


class MockRuntime(AcpRuntimeProtocol):
    def __init__(self) -> None:
        self._sessions: dict[str, AcpSessionResolution] = {}

    def is_healthy(self) -> bool:
        return True

    async def ensure_session(
        self, session_key: str, agent: str, cwd: str, mode: str = "persistent"
    ) -> AcpSessionResolution:
        res = AcpSessionResolution(
            session_key=session_key,
            backend="mock",
            runtime_session_name=f"mock:{session_key}",
            cwd=cwd,
            agent_id=agent,
        )
        self._sessions[session_key] = res
        return res

    async def run_turn(self, input: AcpRunTurnInput):
        yield AcpRuntimeEvent(type="text", text="Hello from mock")
        yield AcpRuntimeEvent(type="done")

    async def get_status(self, handle: AcpSessionResolution) -> AcpSessionStatus:
        return AcpSessionStatus(session_key=handle.session_key, backend="mock", is_active=True)

    async def cancel(self, handle: AcpSessionResolution) -> None:
        pass

    async def close(self, handle: AcpSessionResolution) -> None:
        self._sessions.pop(handle.session_key, None)


class TestAcpSessionManager:
    @pytest.mark.asyncio
    async def test_register_and_initialize(self) -> None:
        mgr = AcpSessionManager()
        runtime = MockRuntime()
        mgr.register_runtime("mock", runtime)

        res = await mgr.initialize_session("s1", "gpt", "/tmp", backend="mock")
        assert res.session_key == "s1"
        assert res.backend == "mock"

    @pytest.mark.asyncio
    async def test_run_turn(self) -> None:
        mgr = AcpSessionManager()
        mgr.register_runtime("mock", MockRuntime())
        await mgr.initialize_session("s1", "gpt", "/tmp", backend="mock")

        events = []
        async for evt in mgr.run_turn("s1", "Hello"):
            events.append(evt)
        assert any(e.type == "text" for e in events)
        assert any(e.type == "done" for e in events)

    @pytest.mark.asyncio
    async def test_close_session(self) -> None:
        mgr = AcpSessionManager()
        mgr.register_runtime("mock", MockRuntime())
        await mgr.initialize_session("s1", "gpt", "/tmp", backend="mock")
        await mgr.close_session("s1")
        assert mgr.get_session("s1") is None

    def test_list_sessions(self) -> None:
        mgr = AcpSessionManager()
        assert mgr.list_sessions() == []

    def test_observability(self) -> None:
        mgr = AcpSessionManager()
        mgr.register_runtime("mock", MockRuntime())
        snap = mgr.observability_snapshot()
        assert "mock" in snap["runtimes"]


# ---------------------------------------------------------------------------
# Thread ownership
# ---------------------------------------------------------------------------


class TestThreadOwnership:
    def test_mention_tracking(self) -> None:
        tracker = ThreadOwnershipTracker(agent_name="Bot")
        tracker.on_message_received("Hey @Bot", "C01", "ts1", "slack")
        # After mention, the thread is tracked
        assert "C01:ts1" in tracker._mentioned_threads

    def test_non_slack_ignored(self) -> None:
        tracker = ThreadOwnershipTracker(agent_name="Bot")
        tracker.on_message_received("@Bot", "C01", "ts1", "telegram")
        assert len(tracker._mentioned_threads) == 0
