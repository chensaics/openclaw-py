"""Tests for OpenResponses HTTP handler and Codex transport."""

from __future__ import annotations

import json

import pytest

from pyclaw.gateway.openresponses_http import (
    CreateResponseBody,
    apply_tool_choice,
    build_response_resource,
    extract_messages_from_input,
    format_sse_event,
    stream_response_created,
    stream_text_delta,
)
from pyclaw.agents.transports.codex import (
    inject_context_management,
    resolve_codex_transport,
    resolve_compact_threshold,
    should_enable_server_compaction,
    should_force_responses_store,
    wrap_codex_extra_params,
)


# ---------------------------------------------------------------------------
# Input extraction
# ---------------------------------------------------------------------------

class TestExtractMessages:
    def test_string_input(self) -> None:
        msgs = extract_messages_from_input("Hello world")
        assert len(msgs) == 1
        assert msgs[0]["role"] == "user"
        assert msgs[0]["content"] == "Hello world"

    def test_string_with_instructions(self) -> None:
        msgs = extract_messages_from_input("Hello", instructions="Be helpful")
        assert len(msgs) == 2
        assert msgs[0]["role"] == "system"
        assert msgs[1]["role"] == "user"

    def test_message_items(self) -> None:
        items = [
            {"type": "message", "role": "user", "content": "Hi"},
            {"type": "message", "role": "assistant", "content": "Hello!"},
            {"type": "message", "role": "user", "content": "How are you?"},
        ]
        msgs = extract_messages_from_input(items)
        assert len(msgs) == 3
        assert msgs[0]["role"] == "user"
        assert msgs[1]["role"] == "assistant"

    def test_function_call_items(self) -> None:
        items = [
            {"type": "message", "role": "user", "content": "Do something"},
            {
                "type": "function_call",
                "call_id": "call_1",
                "name": "do_stuff",
                "arguments": '{"key": "value"}',
            },
            {
                "type": "function_call_output",
                "call_id": "call_1",
                "output": "Done!",
            },
        ]
        msgs = extract_messages_from_input(items)
        assert len(msgs) == 3
        assert msgs[1]["role"] == "assistant"
        assert msgs[1]["tool_calls"][0]["function"]["name"] == "do_stuff"
        assert msgs[2]["role"] == "tool"

    def test_content_parts(self) -> None:
        items = [
            {
                "type": "message",
                "role": "user",
                "content": [
                    {"type": "input_text", "text": "Part 1"},
                    {"type": "input_text", "text": "Part 2"},
                ],
            }
        ]
        msgs = extract_messages_from_input(items)
        assert len(msgs) == 1
        assert "Part 1" in msgs[0]["content"]
        assert "Part 2" in msgs[0]["content"]


# ---------------------------------------------------------------------------
# Tool choice
# ---------------------------------------------------------------------------

class TestApplyToolChoice:
    def test_none(self) -> None:
        tools = [{"function": {"name": "test"}}]
        result_tools, extra = apply_tool_choice(tools, None)
        assert result_tools == tools
        assert extra is None

    def test_none_choice(self) -> None:
        tools, extra = apply_tool_choice([{"function": {"name": "test"}}], "none")
        assert tools == []
        assert extra is None

    def test_required(self) -> None:
        tools = [{"function": {"name": "test"}}]
        result_tools, extra = apply_tool_choice(tools, "required")
        assert result_tools == tools
        assert extra is not None
        assert "must call" in extra.lower()

    def test_required_no_tools(self) -> None:
        with pytest.raises(ValueError, match="required"):
            apply_tool_choice([], "required")

    def test_specific_function(self) -> None:
        tools = [
            {"function": {"name": "tool_a"}},
            {"function": {"name": "tool_b"}},
        ]
        result_tools, extra = apply_tool_choice(
            tools, {"type": "function", "function": {"name": "tool_b"}}
        )
        assert len(result_tools) == 1
        assert result_tools[0]["function"]["name"] == "tool_b"

    def test_unknown_function(self) -> None:
        tools = [{"function": {"name": "tool_a"}}]
        with pytest.raises(ValueError, match="unknown tool"):
            apply_tool_choice(tools, {"type": "function", "function": {"name": "nonexistent"}})


# ---------------------------------------------------------------------------
# Response building
# ---------------------------------------------------------------------------

class TestBuildResponse:
    def test_basic(self) -> None:
        resp = build_response_resource("resp_1", "gpt-4", "Hello world")
        assert resp["id"] == "resp_1"
        assert resp["model"] == "gpt-4"
        assert resp["status"] == "completed"
        assert len(resp["output"]) == 1
        assert resp["output"][0]["content"][0]["text"] == "Hello world"


# ---------------------------------------------------------------------------
# SSE events
# ---------------------------------------------------------------------------

class TestSseEvents:
    def test_format_sse(self) -> None:
        result = format_sse_event("test.event", {"key": "value"})
        assert "event: test.event\n" in result
        assert "data: " in result

    def test_stream_created(self) -> None:
        result = stream_response_created("r1", "gpt-4")
        assert "response.created" in result

    def test_stream_delta(self) -> None:
        result = stream_text_delta("r1", "Hello", "msg_1")
        assert "response.output_text.delta" in result
        assert "Hello" in result


# ---------------------------------------------------------------------------
# Codex transport
# ---------------------------------------------------------------------------

class TestCodexTransport:
    def test_default_transport(self) -> None:
        assert resolve_codex_transport("openai") == "sse"
        assert resolve_codex_transport("openai-codex") == "auto"

    def test_explicit_transport(self) -> None:
        assert resolve_codex_transport("openai", "websocket") == "websocket"


class TestContextManagement:
    def test_inject_for_openai(self) -> None:
        payload: dict = {}
        result = inject_context_management(
            payload, provider="openai", responses_server_compaction=True,
        )
        assert "context_management" in result
        assert result["context_management"][0]["type"] == "compaction"

    def test_skip_for_non_openai(self) -> None:
        payload: dict = {}
        result = inject_context_management(
            payload, provider="anthropic", responses_server_compaction=True,
        )
        assert "context_management" not in result

    def test_skip_if_already_present(self) -> None:
        payload = {"context_management": [{"type": "custom"}]}
        result = inject_context_management(
            payload, provider="openai", responses_server_compaction=True,
        )
        assert result["context_management"][0]["type"] == "custom"

    def test_threshold(self) -> None:
        assert resolve_compact_threshold(128_000) == 80_000
        assert resolve_compact_threshold(50_000) == 35_000
        assert resolve_compact_threshold(128_000, explicit_threshold=60_000) == 60_000


class TestServerCompaction:
    def test_enabled_for_openai(self) -> None:
        assert should_enable_server_compaction("openai") is True

    def test_disabled_for_codex(self) -> None:
        assert should_enable_server_compaction("openai-codex") is False

    def test_disabled_for_anthropic(self) -> None:
        assert should_enable_server_compaction("anthropic") is False

    def test_explicit_override(self) -> None:
        assert should_enable_server_compaction(
            "openai", model_config={"responsesServerCompaction": False}
        ) is False


class TestResponsesStore:
    def test_force_for_openai(self) -> None:
        assert should_force_responses_store("openai") is True

    def test_no_force_for_codex(self) -> None:
        assert should_force_responses_store("openai-codex") is False


class TestWrapCodexParams:
    def test_codex_provider(self) -> None:
        payload: dict = {}
        result = wrap_codex_extra_params(payload, provider="openai-codex")
        assert result.get("store") is False
        assert result.get("transport") == "auto"

    def test_openai_provider(self) -> None:
        payload: dict = {}
        result = wrap_codex_extra_params(payload, provider="openai")
        assert result.get("store") is True
        assert "context_management" in result
