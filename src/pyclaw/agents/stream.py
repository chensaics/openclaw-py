"""LLM streaming layer — unified interface over multiple providers.

Uses official Python SDKs (openai, anthropic, google-generativeai)
so no hand-written SSE parsing is needed.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from pyclaw.agents.types import AgentEvent, ModelConfig, ToolCall
from pyclaw.config.defaults import get_provider_defaults


def _apply_provider_defaults(model: ModelConfig) -> ModelConfig:
    """Fill in default base_url (and api_key placeholder) when not provided."""
    default_base, default_model = get_provider_defaults(model.provider)
    needs_update = False
    base_url = model.base_url
    api_key = model.api_key
    model_id = model.model_id

    if not base_url and default_base:
        base_url = default_base
        needs_update = True
    if not api_key and model.provider == "ollama":
        api_key = "ollama"
        needs_update = True
    if (not model_id or model_id == "default") and default_model and default_model != "default":
        model_id = default_model
        needs_update = True

    if not needs_update:
        return model
    return ModelConfig(
        provider=model.provider,
        model_id=model_id or model.model_id,
        api_key=api_key,
        base_url=base_url,
        max_tokens=model.max_tokens,
        temperature=model.temperature,
    )


async def stream_llm(
    model: ModelConfig,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
) -> AsyncIterator[AgentEvent]:
    """Stream an LLM response, yielding AgentEvents.

    Dispatches to the appropriate provider based on model.provider.
    """
    match model.provider:
        case "openai":
            async for event in _stream_openai(model, messages, tools):
                yield event
        case "anthropic":
            async for event in _stream_anthropic(model, messages, tools):
                yield event
        case "google" | "gemini":
            async for event in _stream_google(model, messages, tools):
                yield event
        case _:
            model = _apply_provider_defaults(model)
            async for event in _stream_openai(model, messages, tools):
                yield event


async def _stream_openai(
    model: ModelConfig,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
) -> AsyncIterator[AgentEvent]:
    """Stream from an OpenAI-compatible API."""
    from openai import AsyncOpenAI

    client = AsyncOpenAI(
        api_key=model.api_key or "not-set",
        base_url=model.base_url,
    )

    kwargs: dict[str, Any] = {
        "model": model.model_id,
        "messages": messages,
        "stream": True,
    }
    if model.max_tokens:
        kwargs["max_tokens"] = model.max_tokens
    if model.temperature is not None:
        kwargs["temperature"] = model.temperature
    if tools:
        kwargs["tools"] = tools

    tool_calls_acc: dict[int, dict[str, Any]] = {}
    current_text = ""

    stream = await client.chat.completions.create(**kwargs)
    async for chunk in stream:
        choice = chunk.choices[0] if chunk.choices else None
        if not choice:
            continue

        delta = choice.delta
        if delta and delta.content:
            current_text += delta.content
            yield AgentEvent(type="message_update", delta=delta.content)

        if delta and delta.tool_calls:
            for tc_delta in delta.tool_calls:
                idx = tc_delta.index
                if idx not in tool_calls_acc:
                    tool_calls_acc[idx] = {
                        "id": tc_delta.id or "",
                        "name": "",
                        "arguments": "",
                    }
                if tc_delta.id:
                    tool_calls_acc[idx]["id"] = tc_delta.id
                if tc_delta.function:
                    if tc_delta.function.name:
                        tool_calls_acc[idx]["name"] = tc_delta.function.name
                    if tc_delta.function.arguments:
                        tool_calls_acc[idx]["arguments"] += tc_delta.function.arguments

        if choice.finish_reason:
            break

    # Emit final usage if available
    if hasattr(stream, "usage") and stream.usage:
        yield AgentEvent(
            type="message_end",
            usage={
                "input_tokens": stream.usage.prompt_tokens or 0,
                "output_tokens": stream.usage.completion_tokens or 0,
            },
        )

    # Store accumulated state for the runner to extract
    if tool_calls_acc or current_text:
        yield _build_completion_event(current_text, tool_calls_acc)


async def _stream_anthropic(
    model: ModelConfig,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
) -> AsyncIterator[AgentEvent]:
    """Stream from the Anthropic API."""
    from anthropic import AsyncAnthropic

    client = AsyncAnthropic(api_key=model.api_key or "not-set")

    system_msgs = [m for m in messages if m["role"] == "system"]
    non_system = [m for m in messages if m["role"] != "system"]
    system_text = "\n\n".join(
        m["content"] if isinstance(m["content"], str) else str(m["content"]) for m in system_msgs
    )

    kwargs: dict[str, Any] = {
        "model": model.model_id,
        "messages": non_system,
        "max_tokens": model.max_tokens or 8192,
        "stream": True,
    }
    if system_text:
        kwargs["system"] = system_text
    if tools:
        kwargs["tools"] = _convert_tools_to_anthropic(tools)

    tool_calls_acc: dict[int, dict[str, Any]] = {}
    current_text = ""
    block_idx = 0

    async with client.messages.stream(**kwargs) as stream:
        async for event in stream:
            if event.type == "content_block_start":
                block = event.content_block
                if block.type == "tool_use":
                    tool_calls_acc[block_idx] = {
                        "id": block.id,
                        "name": block.name,
                        "arguments": "",
                    }
                block_idx += 1

            elif event.type == "content_block_delta":
                delta = event.delta
                if delta.type == "text_delta":
                    current_text += delta.text
                    yield AgentEvent(type="message_update", delta=delta.text)
                elif delta.type == "input_json_delta":
                    # Accumulate tool call arguments
                    last_tc_idx = block_idx - 1
                    if last_tc_idx in tool_calls_acc:
                        tool_calls_acc[last_tc_idx]["arguments"] += delta.partial_json

            elif event.type == "message_stop":
                break

        final_message = await stream.get_final_message()
        if final_message and final_message.usage:
            yield AgentEvent(
                type="message_end",
                usage={
                    "input_tokens": final_message.usage.input_tokens,
                    "output_tokens": final_message.usage.output_tokens,
                },
            )

    yield _build_completion_event(current_text, tool_calls_acc)


async def _stream_google(
    model: ModelConfig,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
) -> AsyncIterator[AgentEvent]:
    """Stream from the Google Gemini API."""
    import google.generativeai as genai

    genai.configure(api_key=model.api_key or "not-set")  # type: ignore[attr-defined]

    gemini_model = genai.GenerativeModel(model.model_id)  # type: ignore[attr-defined]

    # Convert messages to Gemini format
    system_text = ""
    history: list[dict[str, Any]] = []
    last_user_msg = ""

    for msg in messages:
        role = msg["role"]
        content = msg.get("content", "")
        if isinstance(content, list):
            content = " ".join(b.get("text", "") for b in content if isinstance(b, dict))

        if role == "system":
            system_text += content + "\n"
        elif role == "user":
            last_user_msg = content
            history.append({"role": "user", "parts": [content]})
        elif role == "assistant":
            history.append({"role": "model", "parts": [content]})

    # Gemini uses the chat interface with history
    chat = gemini_model.start_chat(history=history[:-1] if history else [])  # type: ignore[arg-type]

    prompt = last_user_msg
    if system_text and not history:
        prompt = system_text + "\n" + prompt

    kwargs: dict[str, Any] = {"stream": True}
    if model.temperature is not None:
        kwargs["generation_config"] = genai.types.GenerationConfig(
            temperature=model.temperature,
            max_output_tokens=model.max_tokens,
        )

    current_text = ""
    response = chat.send_message(prompt, **kwargs)

    for chunk in response:
        if chunk.text:
            current_text += chunk.text
            yield AgentEvent(type="message_update", delta=chunk.text)

    # Usage from Gemini response
    if hasattr(response, "usage_metadata") and response.usage_metadata:
        yield AgentEvent(
            type="message_end",
            usage={
                "input_tokens": getattr(response.usage_metadata, "prompt_token_count", 0),
                "output_tokens": getattr(response.usage_metadata, "candidates_token_count", 0),
            },
        )

    # Gemini tool calls are not yet handled via streaming — emit text only
    yield _build_completion_event(current_text, {})


def _build_completion_event(text: str, tool_calls_acc: dict[int, dict[str, Any]]) -> AgentEvent:
    """Build a final completion event with parsed tool calls."""
    parsed_tool_calls: list[ToolCall] = []
    for tc_data in tool_calls_acc.values():
        try:
            args = json.loads(tc_data["arguments"]) if tc_data["arguments"] else {}
        except json.JSONDecodeError:
            args = {}
        parsed_tool_calls.append(
            ToolCall(
                id=tc_data["id"],
                name=tc_data["name"],
                arguments=args,
            )
        )

    return AgentEvent(
        type="_completion",
        delta=text if text else None,
        result={
            "text": text,
            "tool_calls": [
                {"id": tc.id, "name": tc.name, "arguments": tc.arguments}
                for tc in parsed_tool_calls
            ],
        },
    )


def _convert_tools_to_anthropic(
    openai_tools: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Convert OpenAI-format tool definitions to Anthropic format."""
    result = []
    for tool in openai_tools:
        if tool.get("type") == "function":
            fn = tool["function"]
            result.append(
                {
                    "name": fn["name"],
                    "description": fn.get("description", ""),
                    "input_schema": fn.get("parameters", {"type": "object", "properties": {}}),
                }
            )
    return result


def build_tool_definitions(tools: list[Any]) -> list[dict[str, Any]]:
    """Convert AgentTool instances to OpenAI-format tool definitions."""
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            },
        }
        for tool in tools
    ]
