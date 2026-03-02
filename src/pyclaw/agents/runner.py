"""Agent runner — core agent loop with streaming LLM + tool execution.

Implements the fundamental loop:
  prompt -> stream LLM -> if tool_use: execute tools -> loop
  until the LLM stops requesting tools.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from pyclaw.agents.session import AgentMessage, SessionManager
from pyclaw.agents.stream import build_tool_definitions, stream_llm
from pyclaw.agents.types import AgentEvent, AgentTool, ModelConfig, ToolCall, ToolResult


async def run_agent(
    prompt: str,
    session: SessionManager,
    model: ModelConfig,
    tools: list[AgentTool] | None = None,
    system_prompt: str | None = None,
    max_turns: int = 50,
    abort_event: asyncio.Event | None = None,
) -> AsyncIterator[AgentEvent]:
    """Run the agent loop, yielding events as they occur.

    The loop continues until the LLM produces a response without tool calls,
    or max_turns is reached, or abort_event is set.
    """
    yield AgentEvent(type="agent_start")

    messages = session.get_messages_as_dicts()

    if system_prompt and not any(m["role"] == "system" for m in messages):
        messages.insert(0, {"role": "system", "content": system_prompt})

    messages.append({"role": "user", "content": prompt})
    session.append_message(AgentMessage(role="user", content=prompt))

    tool_defs = build_tool_definitions(tools) if tools else None
    tools_by_name = {t.name: t for t in tools} if tools else {}
    turn = 0

    while turn < max_turns:
        if abort_event and abort_event.is_set():
            yield AgentEvent(type="error", error="aborted")
            break

        turn += 1
        yield AgentEvent(type="message_start")

        completion_text = ""
        completion_tool_calls: list[ToolCall] = []
        usage: dict[str, int] | None = None

        async for event in stream_llm(model, messages, tool_defs):
            if event.type == "message_update":
                yield event
                if event.delta:
                    completion_text += event.delta

            elif event.type == "message_end":
                usage = event.usage

            elif event.type == "_completion":
                if event.result:
                    completion_text = event.result.get("text", "")
                    for tc_data in event.result.get("tool_calls", []):
                        completion_tool_calls.append(
                            ToolCall(
                                id=tc_data["id"],
                                name=tc_data["name"],
                                arguments=tc_data["arguments"],
                            )
                        )

        # Build and persist the assistant message
        assistant_msg = _build_assistant_message(completion_text, completion_tool_calls)
        messages.append(assistant_msg)
        session.append_message(AgentMessage.from_dict(assistant_msg))

        if usage:
            try:
                from pyclaw.infra.session_cost import record_usage

                persisted_session_id = session.path.stem if str(session.path) != "/dev/null" else session.session_id
                record_usage(
                    session_id=persisted_session_id,
                    provider=model.provider,
                    model=model.model_id,
                    input_tokens=int(usage.get("input_tokens", 0) or 0),
                    output_tokens=int(usage.get("output_tokens", 0) or 0),
                    has_api_key=bool(model.api_key),
                )
            except Exception:
                # Usage persistence should never break the response loop.
                pass
            yield AgentEvent(type="message_end", usage=usage)
        else:
            yield AgentEvent(type="message_end")

        if not completion_tool_calls:
            break

        # Execute tool calls
        for tc in completion_tool_calls:
            yield AgentEvent(type="tool_start", name=tc.name, tool_call_id=tc.id)

            tool = tools_by_name.get(tc.name)
            if tool:
                try:
                    result = await tool.execute(tc.id, tc.arguments)
                except Exception as e:
                    result = ToolResult.text(f"Error: {e}", is_error=True)
            else:
                result = ToolResult.text(f"Unknown tool: {tc.name}", is_error=True)

            yield AgentEvent(
                type="tool_end",
                name=tc.name,
                tool_call_id=tc.id,
                result={"content": result.content, "is_error": result.is_error},
            )

            tool_msg = _build_tool_result_message(tc.id, result)
            messages.append(tool_msg)
            session.append_message(AgentMessage.from_dict(tool_msg))

    yield AgentEvent(type="agent_end")


def _build_assistant_message(text: str, tool_calls: list[ToolCall]) -> dict[str, Any]:
    """Build an assistant message dict with optional tool calls."""
    msg: dict[str, Any] = {"role": "assistant"}

    if tool_calls:
        msg["content"] = text or None
        msg["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.name,
                    "arguments": json.dumps(tc.arguments),
                },
            }
            for tc in tool_calls
        ]
    else:
        msg["content"] = text

    return msg


def _build_tool_result_message(tool_call_id: str, result: ToolResult) -> dict[str, Any]:
    """Build a tool result message dict."""
    content_text = "\n".join(
        block.get("text", "") for block in result.content if block.get("type") == "text"
    )
    return {
        "role": "tool",
        "tool_call_id": tool_call_id,
        "content": content_text,
    }
