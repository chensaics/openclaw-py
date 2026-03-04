"""CLI command: run a single agent turn.

Phase 39 notes:
- Keep parameter semantics aligned with documented CLI surface.
- Command name is provided by the top-level app (`pyclaw`), while this module
  only handles execution behavior.
"""

from __future__ import annotations

from pyclaw.config.defaults import DEFAULT_MODEL, DEFAULT_PROVIDER

import asyncio
import json
import sys

import typer

from pyclaw.agents.runner import run_agent
from pyclaw.agents.session import SessionManager
from pyclaw.agents.types import ModelConfig
from pyclaw.config.paths import resolve_sessions_dir


async def _run_agent_turn(
    message: str,
    provider: str,
    model_id: str,
    api_key: str | None,
    base_url: str | None,
    agent_id: str,
    session_id: str,
    output_json: bool,
) -> None:
    sessions_dir = resolve_sessions_dir(agent_id)
    sessions_dir.mkdir(parents=True, exist_ok=True)
    key = session_id or "cli-session"
    session_file = sessions_dir / f"{key}.jsonl"

    session = SessionManager.open(session_file)
    if not session.messages:
        session.write_header()

    model = ModelConfig(
        provider=provider,
        model_id=model_id,
        api_key=api_key,
        base_url=base_url,
    )

    response_text = ""
    usage_summary: dict[str, int] = {}

    async for event in run_agent(prompt=message, session=session, model=model):
        match event.type:
            case "message_update":
                if event.delta:
                    response_text += event.delta
                    if not output_json:
                        sys.stdout.write(event.delta)
                        sys.stdout.flush()
            case "message_end":
                if event.usage:
                    usage_summary = {
                        "input_tokens": event.usage.get("input_tokens", 0),
                        "output_tokens": event.usage.get("output_tokens", 0),
                    }
                if output_json:
                    typer.echo(
                        json.dumps(
                            {
                                "ok": True,
                                "agent_id": agent_id,
                                "session_id": key,
                                "provider": provider,
                                "model": model_id,
                                "message": response_text,
                                "usage": usage_summary,
                            },
                            ensure_ascii=False,
                        )
                    )
                else:
                    sys.stdout.write("\n")
                    tokens_in = usage_summary.get("input_tokens", 0)
                    tokens_out = usage_summary.get("output_tokens", 0)
                    typer.echo(
                        f"[tokens: {tokens_in} in / {tokens_out} out]",
                        err=True,
                    )
            case "error":
                if output_json:
                    typer.echo(json.dumps({"ok": False, "error": event.error}, ensure_ascii=False))
                else:
                    typer.echo(f"Error: {event.error}", err=True)


def _resolve_from_config() -> tuple[str, str, str | None, str | None]:
    """Read provider, model, api_key, base_url from ~/.pyclaw/pyclaw.json when set.
    Returns (provider, model, api_key, base_url). api_key/base_url may be None.
    """
    from pyclaw.config.defaults import get_provider_defaults
    from pyclaw.config.io import load_config_raw
    from pyclaw.config.paths import resolve_config_path

    path = resolve_config_path()
    if not path.exists():
        return (DEFAULT_PROVIDER, DEFAULT_MODEL, None, None)
    raw = load_config_raw(path)
    models = raw.get("models") or {}
    providers = models.get("providers") or {}
    if not providers:
        return (DEFAULT_PROVIDER, DEFAULT_MODEL, None, None)

    agents_cfg = raw.get("agents") or {}
    defaults = agents_cfg.get("defaults") or {}
    default_provider = defaults.get("provider")
    default_model = defaults.get("model")

    provider_id = default_provider or next(iter(providers))
    prov = providers.get(provider_id)
    if not prov or not isinstance(prov, dict):
        return (DEFAULT_PROVIDER, DEFAULT_MODEL, None, None)

    key = prov.get("apiKey")
    if key is not None and not isinstance(key, str):
        key = None
    base = prov.get("baseUrl") or None
    if base is not None and not isinstance(base, str):
        base = None

    default_base, default_model_id = get_provider_defaults(provider_id)

    if not base and default_base:
        base = default_base

    model_id = default_model
    if not model_id:
        models_list = prov.get("models") or []
        if models_list and isinstance(models_list[0], dict):
            model_id = models_list[0].get("id")
        if not model_id:
            model_id = default_model_id or DEFAULT_MODEL
    return (provider_id, model_id, key, base)


def agent_command(
    *,
    message: str,
    provider: str = DEFAULT_PROVIDER,
    model: str = DEFAULT_MODEL,
    api_key: str | None = None,
    base_url: str | None = None,
    agent_id: str = "main",
    session_id: str = "",
    to: str = "",
    thinking: str = "",
    verbose: str = "off",
    channel: str = "",
    local: bool = False,
    deliver: bool = False,
    output_json: bool = False,
    timeout: int = 120,
    resume: bool = False,
) -> None:
    """Run a single agent turn with the given message."""
    import os

    _ = (to, thinking, verbose, channel, local, deliver, timeout)

    if not api_key:
        api_key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        cfg_provider, cfg_model, cfg_key, cfg_base = _resolve_from_config()
        if cfg_key or cfg_provider in ("ollama",):
            api_key = cfg_key or "not-set"
            if provider == "openai" and cfg_provider != "openai":
                provider = cfg_provider
                model = cfg_model
            if base_url is None and cfg_base:
                base_url = cfg_base

    if not api_key:
        if output_json:
            typer.echo(
                json.dumps(
                    {
                        "ok": False,
                        "error": "No API key provided. Set --api-key or OPENAI_API_KEY env var, or run 'pyclaw setup --wizard'.",
                    },
                    ensure_ascii=False,
                )
            )
        else:
            typer.echo(
                "Error: No API key provided. Set --api-key or OPENAI_API_KEY env var, or run 'pyclaw setup --wizard'.",
                err=True,
            )
        raise typer.Exit(1)

    effective_session = session_id
    if resume and not effective_session:
        effective_session = _find_latest_session(agent_id)
        if not output_json and effective_session:
            typer.echo(f"Resuming session: {effective_session}", err=True)

    asyncio.run(
        _run_agent_turn(
            message,
            provider,
            model,
            api_key,
            base_url,
            agent_id,
            effective_session,
            output_json,
        )
    )


def _find_latest_session(agent_id: str) -> str:
    """Find the most recently modified session file for an agent."""
    sessions_dir = resolve_sessions_dir(agent_id)
    if not sessions_dir.is_dir():
        return ""

    sessions = sorted(
        sessions_dir.glob("*.jsonl"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return sessions[0].stem if sessions else ""
