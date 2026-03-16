"""Tests for the agent runner core loop."""

import asyncio
from typing import Any
from unittest.mock import patch

import pytest

from pyclaw.agents.runner import run_agent
from pyclaw.agents.session import SessionManager
from pyclaw.agents.types import AgentEvent, ModelConfig, ToolResult


class MockTool:
    """A simple mock tool for testing."""

    def __init__(self, name: str = "get_weather", response: str = "Sunny, 72F"):
        self._name = name
        self._response = response

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return f"Mock tool: {self._name}"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"location": {"type": "string"}},
            "required": ["location"],
        }

    async def execute(self, tool_call_id: str, arguments: dict[str, Any]) -> ToolResult:
        return ToolResult.text(self._response)


def _make_model() -> ModelConfig:
    return ModelConfig(provider="openai", model_id="gpt-4o", api_key="test-key")


async def _collect_events(agent_iter) -> list[AgentEvent]:
    events = []
    async for event in agent_iter:
        events.append(event)
    return events


@pytest.mark.asyncio
async def test_agent_simple_response():
    """Agent should handle a simple text response (no tools)."""
    session = SessionManager.in_memory()
    model = _make_model()

    # Mock stream_llm to return a simple text response
    async def mock_stream(*args, **kwargs):
        yield AgentEvent(type="message_update", delta="Hello ")
        yield AgentEvent(type="message_update", delta="world!")
        yield AgentEvent(
            type="_completion",
            result={"text": "Hello world!", "tool_calls": []},
        )

    with patch("pyclaw.agents.runner.stream_llm", side_effect=mock_stream):
        events = await _collect_events(run_agent("Hi", session=session, model=model))

    types = [e.type for e in events]
    assert types[0] == "agent_start"
    assert "message_start" in types
    assert "message_update" in types
    assert "message_end" in types
    assert types[-1] == "agent_end"

    # Session should have user + assistant messages
    assert len(session.messages) == 2
    assert session.messages[0].role == "user"
    assert session.messages[1].role == "assistant"


@pytest.mark.asyncio
async def test_agent_with_tool_call():
    """Agent should execute tools and loop back to LLM."""
    session = SessionManager.in_memory()
    model = _make_model()
    tool = MockTool()

    call_count = 0

    async def mock_stream(m, messages, tools):
        nonlocal call_count
        call_count += 1

        if call_count == 1:
            # First call: LLM requests a tool
            yield AgentEvent(type="message_update", delta="")
            yield AgentEvent(
                type="_completion",
                result={
                    "text": "",
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "name": "get_weather",
                            "arguments": {"location": "NYC"},
                        }
                    ],
                },
            )
        else:
            # Second call: LLM gives final answer
            yield AgentEvent(type="message_update", delta="It's sunny in NYC!")
            yield AgentEvent(
                type="_completion",
                result={"text": "It's sunny in NYC!", "tool_calls": []},
            )

    with patch("pyclaw.agents.runner.stream_llm", side_effect=mock_stream):
        events = await _collect_events(
            run_agent("What's the weather in NYC?", session=session, model=model, tools=[tool])
        )

    types = [e.type for e in events]
    assert "tool_start" in types
    assert "tool_end" in types
    assert call_count == 2

    # Session: user, assistant (tool_call), tool (result), assistant (final)
    assert len(session.messages) == 4
    assert session.messages[0].role == "user"
    assert session.messages[1].role == "assistant"
    assert session.messages[2].role == "tool"
    assert session.messages[3].role == "assistant"


@pytest.mark.asyncio
async def test_agent_unknown_tool():
    """Agent should handle unknown tool names gracefully."""
    session = SessionManager.in_memory()
    model = _make_model()

    call_count = 0

    async def mock_stream(m, messages, tools):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            yield AgentEvent(
                type="_completion",
                result={
                    "text": "",
                    "tool_calls": [
                        {"id": "call_x", "name": "nonexistent_tool", "arguments": {}},
                    ],
                },
            )
        else:
            yield AgentEvent(
                type="_completion",
                result={"text": "Sorry, I couldn't do that.", "tool_calls": []},
            )

    with patch("pyclaw.agents.runner.stream_llm", side_effect=mock_stream):
        events = await _collect_events(run_agent("Do something", session=session, model=model))

    tool_end_events = [e for e in events if e.type == "tool_end"]
    assert len(tool_end_events) == 1
    assert tool_end_events[0].result["is_error"] is True


@pytest.mark.asyncio
async def test_agent_abort():
    """Agent should stop when abort event is set."""
    session = SessionManager.in_memory()
    model = _make_model()
    abort = asyncio.Event()
    abort.set()  # Already aborted

    async def mock_stream(*args, **kwargs):
        yield AgentEvent(type="_completion", result={"text": "hi", "tool_calls": []})

    with patch("pyclaw.agents.runner.stream_llm", side_effect=mock_stream):
        events = await _collect_events(run_agent("Hi", session=session, model=model, abort_event=abort))

    types = [e.type for e in events]
    assert "error" in types
