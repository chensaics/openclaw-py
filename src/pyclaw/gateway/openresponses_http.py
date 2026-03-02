"""OpenResponses HTTP handler — ``/v1/responses`` endpoint.

Ported from ``src/gateway/openresponses-http.ts``.
Implements the OpenResponses API for pyclaw Gateway.

See: https://www.open-responses.com/
"""

from __future__ import annotations

import logging
import uuid
import time
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Request/Response schemas (ported from open-responses.schema.ts)
# ---------------------------------------------------------------------------


class ContentPart(BaseModel):
    type: str
    text: str | None = None
    source: dict[str, Any] | None = None


class MessageItem(BaseModel):
    type: str = "message"
    role: str = "user"
    content: str | list[ContentPart] = ""


class FunctionCallItem(BaseModel):
    type: str = "function_call"
    id: str | None = None
    call_id: str | None = None
    name: str = ""
    arguments: str = ""


class FunctionCallOutputItem(BaseModel):
    type: str = "function_call_output"
    call_id: str = ""
    output: str = ""


class ToolDefinition(BaseModel):
    type: str = "function"
    function: dict[str, Any] | None = None
    name: str | None = None


class CreateResponseBody(BaseModel):
    model: str = ""
    input: str | list[dict[str, Any]] = ""
    instructions: str | None = None
    tools: list[dict[str, Any]] = Field(default_factory=list)
    tool_choice: str | dict[str, Any] | None = None
    stream: bool = False
    temperature: float | None = None
    max_output_tokens: int | None = None
    store: bool | None = None
    metadata: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Response types
# ---------------------------------------------------------------------------

@dataclass
class OutputItem:
    type: str = "message"
    role: str = "assistant"
    content: list[dict[str, Any]] = field(default_factory=list)
    id: str = ""
    status: str = "completed"


@dataclass
class ResponseResource:
    id: str = ""
    object: str = "response"
    created_at: int = 0
    model: str = ""
    output: list[OutputItem] = field(default_factory=list)
    status: str = "completed"
    usage: dict[str, int] | None = None


# ---------------------------------------------------------------------------
# Input extraction
# ---------------------------------------------------------------------------

def extract_messages_from_input(
    input_data: str | list[dict[str, Any]],
    instructions: str | None = None,
) -> list[dict[str, Any]]:
    """Convert OpenResponses input format to standard messages."""
    messages: list[dict[str, Any]] = []

    if instructions:
        messages.append({"role": "system", "content": instructions})

    if isinstance(input_data, str):
        messages.append({"role": "user", "content": input_data})
        return messages

    if isinstance(input_data, list):
        for item in input_data:
            if not isinstance(item, dict):
                continue
            item_type = item.get("type", "message")

            if item_type == "message":
                role = item.get("role", "user")
                content = item.get("content", "")
                if isinstance(content, str):
                    messages.append({"role": role, "content": content})
                elif isinstance(content, list):
                    text_parts = []
                    for part in content:
                        if isinstance(part, dict):
                            if part.get("type") in ("input_text", "text"):
                                text_parts.append(part.get("text", ""))
                            elif part.get("type") == "output_text":
                                text_parts.append(part.get("text", ""))
                    messages.append({"role": role, "content": "\n".join(text_parts)})

            elif item_type == "function_call":
                messages.append({
                    "role": "assistant",
                    "tool_calls": [{
                        "id": item.get("call_id", item.get("id", "")),
                        "type": "function",
                        "function": {
                            "name": item.get("name", ""),
                            "arguments": item.get("arguments", "{}"),
                        },
                    }],
                })

            elif item_type == "function_call_output":
                messages.append({
                    "role": "tool",
                    "tool_call_id": item.get("call_id", ""),
                    "content": item.get("output", ""),
                })

    return messages


def extract_client_tools(body: CreateResponseBody) -> list[dict[str, Any]]:
    """Extract tool definitions from request body."""
    return list(body.tools) if body.tools else []


# ---------------------------------------------------------------------------
# Tool choice
# ---------------------------------------------------------------------------

def apply_tool_choice(
    tools: list[dict[str, Any]],
    tool_choice: str | dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], str | None]:
    """Apply tool_choice constraint. Returns (tools, extra_system_prompt)."""
    if not tool_choice:
        return tools, None

    if tool_choice == "none":
        return [], None

    if tool_choice == "required":
        if not tools:
            raise ValueError("tool_choice=required but no tools were provided")
        return tools, "You must call one of the available tools before responding."

    if isinstance(tool_choice, dict) and tool_choice.get("type") == "function":
        fn = tool_choice.get("function", {})
        target_name = (fn.get("name") or "").strip()
        if not target_name:
            raise ValueError("tool_choice.function.name is required")
        matched = [t for t in tools if t.get("function", {}).get("name") == target_name]
        if not matched:
            raise ValueError(f"tool_choice requested unknown tool: {target_name}")
        return matched, f"You must call the {target_name} tool before responding."

    return tools, None


# ---------------------------------------------------------------------------
# Response builder
# ---------------------------------------------------------------------------

def build_response_resource(
    response_id: str,
    model: str,
    output_text: str,
    *,
    usage: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Build a complete response resource."""
    return {
        "id": response_id,
        "object": "response",
        "created_at": int(time.time()),
        "model": model,
        "output": [
            {
                "type": "message",
                "role": "assistant",
                "id": f"msg_{uuid.uuid4().hex[:12]}",
                "status": "completed",
                "content": [{"type": "output_text", "text": output_text}],
            }
        ],
        "status": "completed",
        **({"usage": usage} if usage else {}),
    }


# ---------------------------------------------------------------------------
# SSE streaming events
# ---------------------------------------------------------------------------

def format_sse_event(event_type: str, data: dict[str, Any]) -> str:
    """Format an SSE event string."""
    import json
    payload = {"type": event_type, **data}
    return f"event: {event_type}\ndata: {json.dumps(payload)}\n\n"


def stream_response_created(response_id: str, model: str) -> str:
    return format_sse_event("response.created", {
        "response": {
            "id": response_id,
            "object": "response",
            "created_at": int(time.time()),
            "model": model,
            "output": [],
            "status": "in_progress",
        },
    })


def stream_text_delta(response_id: str, delta: str, item_id: str) -> str:
    return format_sse_event("response.output_text.delta", {
        "response_id": response_id,
        "item_id": item_id,
        "output_index": 0,
        "content_index": 0,
        "delta": delta,
    })


def stream_response_completed(response_id: str, model: str, text: str) -> str:
    return format_sse_event("response.completed", {
        "response": build_response_resource(response_id, model, text),
    })
