"""OpenAI Chat Completions API compatible HTTP endpoint.

Provides ``POST /v1/chat/completions`` for tools that expect an OpenAI-compatible
API (e.g. Cursor, Continue, aider).
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse


def register_openai_routes(
    app: FastAPI,
    *,
    auth_token: str | None = None,
    run_agent_fn: Any = None,
) -> None:
    """Register ``/v1/chat/completions`` and ``/v1/models`` on the FastAPI app."""

    @app.post("/v1/chat/completions")
    async def chat_completions(request: Request) -> Any:
        # Auth
        if auth_token:
            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                raise HTTPException(status_code=401, detail="Missing Bearer token")
            token = auth_header[7:]
            if token != auth_token:
                raise HTTPException(status_code=401, detail="Invalid token")

        try:
            body = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON body")

        messages = body.get("messages", [])
        model = body.get("model", "")
        stream = body.get("stream", False)
        user = body.get("user", "")

        if not messages:
            raise HTTPException(status_code=400, detail="messages is required")

        # Build prompt from messages
        prompt = _build_prompt(messages)
        completion_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
        created = int(time.time())

        if stream:
            return StreamingResponse(
                _stream_response(
                    completion_id=completion_id,
                    created=created,
                    model=model,
                    prompt=prompt,
                    run_agent_fn=run_agent_fn,
                ),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )
        else:
            return await _non_stream_response(
                completion_id=completion_id,
                created=created,
                model=model,
                prompt=prompt,
                run_agent_fn=run_agent_fn,
            )

    @app.get("/v1/models")
    async def list_models() -> JSONResponse:
        from pyclaw.agents.model_catalog import ModelCatalog

        catalog = ModelCatalog()
        models = catalog.list_models()
        data = [
            {
                "id": m.key,
                "object": "model",
                "created": int(time.time()),
                "owned_by": m.provider,
            }
            for m in models
        ]
        return JSONResponse({"object": "list", "data": data})


def _build_prompt(messages: list[dict[str, Any]]) -> str:
    """Extract text from OpenAI-format messages."""
    parts: list[str] = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")

        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            text_parts = []
            for item in content:
                if isinstance(item, dict):
                    t = item.get("text") or item.get("input_text", "")
                    if t:
                        text_parts.append(t)
            text = "\n".join(text_parts)
        else:
            text = str(content)

        if text:
            parts.append(text)

    return parts[-1] if parts else ""


async def _non_stream_response(
    *,
    completion_id: str,
    created: int,
    model: str,
    prompt: str,
    run_agent_fn: Any,
) -> JSONResponse:
    """Collect full response and return as JSON."""
    output_parts: list[str] = []

    if run_agent_fn:
        async for event in run_agent_fn(prompt=prompt, model_id=model):
            if hasattr(event, "delta") and event.delta:
                output_parts.append(event.delta)
    else:
        output_parts.append("(Agent not configured)")

    content = "".join(output_parts)

    return JSONResponse({
        "id": completion_id,
        "object": "chat.completion",
        "created": created,
        "model": model or "pyclaw",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": len(prompt) // 4,
            "completion_tokens": len(content) // 4,
            "total_tokens": (len(prompt) + len(content)) // 4,
        },
    })


async def _stream_response(
    *,
    completion_id: str,
    created: int,
    model: str,
    prompt: str,
    run_agent_fn: Any,
) -> Any:
    """Generate SSE stream chunks."""
    # Initial role chunk
    chunk = {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model or "pyclaw",
        "choices": [
            {
                "index": 0,
                "delta": {"role": "assistant"},
                "finish_reason": None,
            }
        ],
    }
    yield f"data: {json.dumps(chunk)}\n\n"

    if run_agent_fn:
        async for event in run_agent_fn(prompt=prompt, model_id=model):
            if hasattr(event, "delta") and event.delta:
                chunk = {
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": model or "pyclaw",
                    "choices": [
                        {
                            "index": 0,
                            "delta": {"content": event.delta},
                            "finish_reason": None,
                        }
                    ],
                }
                yield f"data: {json.dumps(chunk)}\n\n"

    # Final chunk
    final = {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model or "pyclaw",
        "choices": [
            {
                "index": 0,
                "delta": {},
                "finish_reason": "stop",
            }
        ],
    }
    yield f"data: {json.dumps(final)}\n\n"
    yield "data: [DONE]\n\n"
