"""chat.* — real-time chat handlers (send, history, abort)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from pyclaw.gateway.server import GatewayConnection, MethodHandler

logger = logging.getLogger(__name__)

_active_runs: dict[str, asyncio.Event] = {}


def _use_embedded_runner() -> bool:
    """Check config to decide runner: 'embedded' (default) or 'legacy'."""
    try:
        from pyclaw.config.io import load_config_raw
        raw = load_config_raw()
        runner_cfg = raw.get("runner", {})
        if isinstance(runner_cfg, dict):
            return runner_cfg.get("mode", "embedded") != "legacy"
        return True
    except Exception:
        return True


def create_chat_handlers() -> dict[str, "MethodHandler"]:
    async def handle_chat_send(
        params: dict[str, Any] | None, conn: "GatewayConnection"
    ) -> None:
        """Send a message and stream the agent response back as events."""
        if not params or "message" not in params:
            await conn.send_error(
                "chat.send", "invalid_params", "Missing 'message'."
            )
            return

        from pyclaw.agents.session import SessionManager
        from pyclaw.agents.types import ModelConfig
        from pyclaw.agents.tools.registry import create_default_tools
        from pyclaw.config.paths import resolve_sessions_dir

        message = params["message"]
        agent_id = params.get("agentId", "main")
        provider = params.get("provider", "openai")
        model_id = params.get("model", "gpt-4o")
        api_key = params.get("apiKey")
        system_prompt = params.get("systemPrompt")

        sessions_dir = resolve_sessions_dir(agent_id)
        sessions_dir.mkdir(parents=True, exist_ok=True)
        session_file = sessions_dir / f"{params.get('sessionId', 'default')}.jsonl"
        session_key = str(session_file)

        session = SessionManager.open(session_file)
        if not session.messages:
            session.write_header()

        model = ModelConfig(
            provider=provider,
            model_id=model_id,
            api_key=api_key,
        )

        abort_event = asyncio.Event()
        _active_runs[session_key] = abort_event

        registry = create_default_tools(enable_exec=True, enable_web=True)
        tools = registry.all()

        use_embedded = _use_embedded_runner()

        try:
            if use_embedded:
                await _run_embedded(
                    message=message,
                    session=session,
                    model=model,
                    tools=tools,
                    system_prompt=system_prompt,
                    abort_event=abort_event,
                    conn=conn,
                    session_key=session_key,
                )
            else:
                await _run_legacy(
                    message=message,
                    session=session,
                    model=model,
                    tools=tools,
                    system_prompt=system_prompt,
                    abort_event=abort_event,
                    conn=conn,
                )

            await conn.send_ok("chat.send", {"completed": True})
        except Exception as e:
            await conn.send_error("chat.send", "agent_error", str(e))
        finally:
            _active_runs.pop(session_key, None)

    async def handle_chat_abort(
        params: dict[str, Any] | None, conn: "GatewayConnection"
    ) -> None:
        if not params or "sessionId" not in params:
            await conn.send_error(
                "chat.abort", "invalid_params", "Missing 'sessionId'."
            )
            return

        agent_id = params.get("agentId", "main")
        from pyclaw.config.paths import resolve_sessions_dir

        sessions_dir = resolve_sessions_dir(agent_id)
        session_file = sessions_dir / f"{params['sessionId']}.jsonl"
        session_key = str(session_file)

        abort = _active_runs.get(session_key)
        if abort:
            abort.set()
            await conn.send_ok("chat.abort", {"aborted": True})
        else:
            await conn.send_ok("chat.abort", {"aborted": False})

    async def handle_chat_history(
        params: dict[str, Any] | None, conn: "GatewayConnection"
    ) -> None:
        """Return the message history for a session."""
        if not params:
            await conn.send_error(
                "chat.history", "invalid_params", "Missing params."
            )
            return

        agent_id = params.get("agentId", "main")
        session_id = params.get("sessionId", "default")

        from pyclaw.agents.session import SessionManager
        from pyclaw.config.paths import resolve_sessions_dir

        sessions_dir = resolve_sessions_dir(agent_id)
        session_file = sessions_dir / f"{session_id}.jsonl"

        if not session_file.exists():
            await conn.send_ok("chat.history", {"messages": []})
            return

        session = SessionManager.open(session_file)
        messages = session.get_messages_as_dicts()
        await conn.send_ok("chat.history", {"messages": messages})

    return {
        "chat.send": handle_chat_send,
        "chat.abort": handle_chat_abort,
        "chat.history": handle_chat_history,
    }


# ---------------------------------------------------------------------------
# Runner implementations
# ---------------------------------------------------------------------------

async def _run_embedded(
    *,
    message: str,
    session: Any,
    model: Any,
    tools: list[Any],
    system_prompt: str | None,
    abort_event: asyncio.Event,
    conn: Any,
    session_key: str,
) -> None:
    """Run using the embedded runner (default path)."""
    from pyclaw.agents.embedded_runner.run import (
        Message,
        RunConfig,
        RunTracker,
        build_request_payload,
    )

    tracker = RunTracker()
    record = tracker.start_run(model=model.model_id)

    config = RunConfig(
        model=model.model_id,
        provider=model.provider,
        max_turns=50,
        stream=True,
    )

    messages = [Message(role="user", content=message)]
    payload = build_request_payload(
        messages, config,
        tools=[t.schema() if hasattr(t, "schema") else t for t in tools] if tools else None,
        system_prompt=system_prompt or "",
    )

    # Delegate to legacy stream for actual LLM call (embedded runner provides
    # the execution loop structure but the LLM streaming is shared infra).
    from pyclaw.agents.runner import run_agent

    async for event in run_agent(
        prompt=message,
        session=session,
        model=model,
        tools=tools,
        system_prompt=system_prompt,
        abort_event=abort_event,
    ):
        if abort_event.is_set():
            from pyclaw.agents.embedded_runner.run import RunState
            tracker.finish_run(record.run_id, state=RunState.ABORTED)
            break

        record.turns += 1
        if event.usage:
            record.total_input_tokens += event.usage.get("input_tokens", 0)
            record.total_output_tokens += event.usage.get("output_tokens", 0)

        await conn.send_event(f"chat.{event.type}", {
            k: v for k, v in {
                "delta": event.delta,
                "name": event.name,
                "result": event.result,
                "error": event.error,
                "toolCallId": event.tool_call_id,
                "usage": event.usage,
                "runner": "embedded",
            }.items() if v is not None
        })

    # Record usage for cost tracking
    try:
        from pyclaw.infra.session_cost import record_usage
        record_usage(
            session_key=session_key,
            provider=model.provider,
            model=model.model_id,
            input_tokens=record.total_input_tokens,
            output_tokens=record.total_output_tokens,
        )
    except Exception:
        pass

    from pyclaw.agents.embedded_runner.run import RunState
    if not abort_event.is_set():
        tracker.finish_run(record.run_id, state=RunState.COMPLETED)


async def _run_legacy(
    *,
    message: str,
    session: Any,
    model: Any,
    tools: list[Any],
    system_prompt: str | None,
    abort_event: asyncio.Event,
    conn: Any,
) -> None:
    """Run using the legacy runner (fallback path)."""
    from pyclaw.agents.runner import run_agent

    async for event in run_agent(
        prompt=message,
        session=session,
        model=model,
        tools=tools,
        system_prompt=system_prompt,
        abort_event=abort_event,
    ):
        await conn.send_event(f"chat.{event.type}", {
            k: v for k, v in {
                "delta": event.delta,
                "name": event.name,
                "result": event.result,
                "error": event.error,
                "toolCallId": event.tool_call_id,
                "usage": event.usage,
            }.items() if v is not None
        })
