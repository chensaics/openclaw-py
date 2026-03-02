"""chat.* — real-time chat handlers (send, abort, history, edit, resend).

Phase 55: Integrates chat_advanced validation/sanitization/time-injection,
adds chat.edit + chat.resend, and unifies usage/abort across both runner paths.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, TYPE_CHECKING

from pyclaw.gateway.methods.chat_advanced import (
    ChatAbortManager,
    validate_chat_params,
    sanitize_content,
    inject_time_context,
)

if TYPE_CHECKING:
    from pyclaw.gateway.server import GatewayConnection, MethodHandler

logger = logging.getLogger(__name__)

_abort_mgr = ChatAbortManager()
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


def _make_session_key(agent_id: str, session_id: str) -> str:
    from pyclaw.config.paths import resolve_sessions_dir
    return str(resolve_sessions_dir(agent_id) / f"{session_id}.jsonl")


def create_chat_handlers() -> dict[str, "MethodHandler"]:

    async def handle_chat_send(
        params: dict[str, Any] | None, conn: "GatewayConnection"
    ) -> None:
        """Send a message and stream the agent response back as events."""
        chat_params, err = validate_chat_params(params or {})
        if err or not chat_params:
            await conn.send_error("chat.send", "invalid_params", err or "Invalid parameters")
            return

        message = sanitize_content(chat_params.message)
        agent_id = chat_params.agent_id
        session_id = chat_params.session_id or "default"
        system_prompt = chat_params.system_prompt or ""

        system_prompt = inject_time_context(system_prompt)

        if chat_params.abort_previous:
            session_key = _make_session_key(agent_id, session_id)
            existing = _active_runs.get(session_key)
            if existing:
                existing.set()
                _abort_mgr.abort(session_key)
                await asyncio.sleep(0.05)

        await _do_chat_run(
            message=message,
            agent_id=agent_id,
            session_id=session_id,
            provider=chat_params.provider,
            model_id=chat_params.model,
            api_key=chat_params.api_key,
            system_prompt=system_prompt,
            temperature=chat_params.temperature,
            conn=conn,
            method="chat.send",
        )

    async def handle_chat_abort(
        params: dict[str, Any] | None, conn: "GatewayConnection"
    ) -> None:
        if not params or "sessionId" not in params:
            await conn.send_error("chat.abort", "invalid_params", "Missing 'sessionId'.")
            return

        agent_id = params.get("agentId", "main")
        session_id = params["sessionId"]
        session_key = _make_session_key(agent_id, session_id)

        abort = _active_runs.get(session_key)
        mgr_aborted = _abort_mgr.abort(session_key)
        if abort:
            abort.set()
            await conn.send_ok("chat.abort", {"aborted": True})
        elif mgr_aborted:
            await conn.send_ok("chat.abort", {"aborted": True})
        else:
            await conn.send_ok("chat.abort", {"aborted": False})

    async def handle_chat_history(
        params: dict[str, Any] | None, conn: "GatewayConnection"
    ) -> None:
        if not params:
            await conn.send_error("chat.history", "invalid_params", "Missing params.")
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

    async def handle_chat_edit(
        params: dict[str, Any] | None, conn: "GatewayConnection"
    ) -> None:
        """Edit the last user message and re-run the agent."""
        if not params or "message" not in params:
            await conn.send_error("chat.edit", "invalid_params", "Missing 'message'.")
            return

        message = sanitize_content(str(params["message"]))
        agent_id = params.get("agentId", "main")
        session_id = params.get("sessionId", "default")

        from pyclaw.agents.session import SessionManager
        from pyclaw.config.paths import resolve_sessions_dir

        sessions_dir = resolve_sessions_dir(agent_id)
        session_file = sessions_dir / f"{session_id}.jsonl"
        if session_file.exists():
            session = SessionManager.open(session_file)
            _remove_last_exchange(session)

        system_prompt = inject_time_context(params.get("systemPrompt", ""))

        await _do_chat_run(
            message=message,
            agent_id=agent_id,
            session_id=session_id,
            provider=params.get("provider", "openai"),
            model_id=params.get("model", "gpt-4o"),
            api_key=params.get("apiKey", ""),
            system_prompt=system_prompt,
            temperature=None,
            conn=conn,
            method="chat.edit",
        )

    async def handle_chat_resend(
        params: dict[str, Any] | None, conn: "GatewayConnection"
    ) -> None:
        """Re-send the last user message (regenerate assistant response)."""
        agent_id = (params or {}).get("agentId", "main")
        session_id = (params or {}).get("sessionId", "default")

        from pyclaw.agents.session import SessionManager
        from pyclaw.config.paths import resolve_sessions_dir

        sessions_dir = resolve_sessions_dir(agent_id)
        session_file = sessions_dir / f"{session_id}.jsonl"

        if not session_file.exists():
            await conn.send_error("chat.resend", "invalid_state", "No session found")
            return

        session = SessionManager.open(session_file)
        last_user_msg = _find_last_user_message(session)
        if not last_user_msg:
            await conn.send_error("chat.resend", "invalid_state", "No user message to resend")
            return

        _remove_last_assistant_response(session)

        system_prompt = inject_time_context((params or {}).get("systemPrompt", ""))

        await _do_chat_run(
            message=last_user_msg,
            agent_id=agent_id,
            session_id=session_id,
            provider=(params or {}).get("provider", "openai"),
            model_id=(params or {}).get("model", "gpt-4o"),
            api_key=(params or {}).get("apiKey", ""),
            system_prompt=system_prompt,
            temperature=None,
            conn=conn,
            method="chat.resend",
        )

    return {
        "chat.send": handle_chat_send,
        "chat.abort": handle_chat_abort,
        "chat.history": handle_chat_history,
        "chat.edit": handle_chat_edit,
        "chat.resend": handle_chat_resend,
    }


# ---------------------------------------------------------------------------
# Model resolution — merge gateway params with config defaults
# ---------------------------------------------------------------------------

def _resolve_gateway_model(
    provider: str, model_id: str, api_key: str
) -> tuple[str, str, str, str | None]:
    """Return (provider, model, api_key, base_url) with config & provider defaults applied."""
    from pyclaw.config.defaults import get_provider_defaults
    from pyclaw.config.io import load_config_raw

    effective_provider = provider
    effective_model = model_id
    effective_key = api_key
    effective_base: str | None = None

    try:
        raw = load_config_raw()
        providers_cfg = (raw.get("models") or {}).get("providers") or {}

        agents_defaults = (raw.get("agents") or {}).get("defaults") or {}
        cfg_provider = agents_defaults.get("provider")
        cfg_model = agents_defaults.get("model")

        if not effective_key and providers_cfg:
            resolved_pid = cfg_provider or next(iter(providers_cfg), None)
            prov = providers_cfg.get(resolved_pid or "") or {}
            if isinstance(prov, dict):
                cfg_key = prov.get("apiKey")
                if isinstance(cfg_key, str) and cfg_key:
                    effective_key = cfg_key
                    if effective_provider == "openai" and resolved_pid and resolved_pid != "openai":
                        effective_provider = resolved_pid
                        effective_model = cfg_model or model_id
                    effective_base = prov.get("baseUrl") or None
    except Exception:
        pass

    if not effective_base:
        default_base, default_model = get_provider_defaults(effective_provider)
        if default_base:
            effective_base = default_base
        if (not effective_model or effective_model == "gpt-4o") and default_model:
            effective_model = default_model

    return effective_provider, effective_model, effective_key, effective_base


# ---------------------------------------------------------------------------
# Shared run logic
# ---------------------------------------------------------------------------

async def _do_chat_run(
    *,
    message: str,
    agent_id: str,
    session_id: str,
    provider: str,
    model_id: str,
    api_key: str,
    system_prompt: str,
    temperature: float | None,
    conn: Any,
    method: str,
) -> None:
    from pyclaw.agents.session import SessionManager
    from pyclaw.agents.types import ModelConfig
    from pyclaw.agents.tools.registry import create_default_tools
    from pyclaw.config.defaults import get_provider_defaults
    from pyclaw.config.paths import resolve_sessions_dir

    sessions_dir = resolve_sessions_dir(agent_id)
    sessions_dir.mkdir(parents=True, exist_ok=True)
    session_file = sessions_dir / f"{session_id}.jsonl"
    session_key = str(session_file)

    session = SessionManager.open(session_file)
    if not session.messages:
        session.write_header()

    effective_provider, effective_model, effective_key, effective_base = (
        _resolve_gateway_model(provider, model_id, api_key)
    )
    model = ModelConfig(
        provider=effective_provider,
        model_id=effective_model,
        api_key=effective_key,
        base_url=effective_base,
    )

    abort_event = asyncio.Event()
    _active_runs[session_key] = abort_event
    _abort_mgr.register(session_key)

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
                method=method,
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
                method=method,
            )

        await conn.send_ok(method, {"completed": True})
    except Exception as e:
        await conn.send_error(method, "agent_error", str(e))
    finally:
        _active_runs.pop(session_key, None)
        _abort_mgr.unregister(session_key)


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
    method: str,
) -> None:
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
    build_request_payload(
        messages, config,
        tools=[t.schema() if hasattr(t, "schema") else t for t in tools] if tools else None,
        system_prompt=system_prompt or "",
    )

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
    method: str,
) -> None:
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


# ---------------------------------------------------------------------------
# Session manipulation helpers
# ---------------------------------------------------------------------------

def _remove_last_exchange(session: Any) -> None:
    """Remove the last user+assistant pair from the session's in-memory messages."""
    msgs = session.messages
    last_assistant = None
    for i in range(len(msgs) - 1, -1, -1):
        if msgs[i].role == "assistant":
            last_assistant = i
            break
    if last_assistant is not None:
        msgs.pop(last_assistant)

    last_user = None
    for i in range(len(msgs) - 1, -1, -1):
        if msgs[i].role == "user":
            last_user = i
            break
    if last_user is not None:
        msgs.pop(last_user)


def _remove_last_assistant_response(session: Any) -> None:
    msgs = session.messages
    for i in range(len(msgs) - 1, -1, -1):
        if msgs[i].role == "assistant":
            msgs.pop(i)
            return


def _find_last_user_message(session: Any) -> str:
    for msg in reversed(session.messages):
        if msg.role == "user":
            return msg.content
    return ""
