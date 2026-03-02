"""Gateway methods: agents.list/add/remove — agent management."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pyclaw.gateway.server import GatewayConnection


async def handle_agents_list(conn: GatewayConnection, params: dict[str, Any]) -> dict[str, Any]:
    """List all configured agents."""
    from pyclaw.config.paths import resolve_agents_dir

    agents_dir = resolve_agents_dir()
    agents: list[dict[str, Any]] = []

    if agents_dir.is_dir():
        for d in sorted(agents_dir.iterdir()):
            if not d.is_dir():
                continue
            sessions_dir = d / "sessions"
            session_count = len(list(sessions_dir.glob("*.jsonl"))) if sessions_dir.is_dir() else 0
            config_file = d / "config.json"
            agent_config: dict[str, Any] = {}
            if config_file.is_file():
                try:
                    agent_config = json.loads(config_file.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    pass

            agents.append({
                "id": d.name,
                "session_count": session_count,
                "config": agent_config,
            })

    return {"agents": agents}


async def handle_agents_add(conn: GatewayConnection, params: dict[str, Any]) -> dict[str, Any]:
    """Add/create a new agent directory."""
    from pyclaw.config.paths import resolve_agents_dir

    agent_id = params.get("agent_id", "").strip()
    if not agent_id:
        return {"error": "agent_id is required"}

    agents_dir = resolve_agents_dir()
    agent_dir = agents_dir / agent_id
    if agent_dir.exists():
        return {"error": f"Agent '{agent_id}' already exists"}

    agent_dir.mkdir(parents=True, exist_ok=True)
    (agent_dir / "sessions").mkdir(exist_ok=True)

    config = params.get("config", {})
    if config:
        (agent_dir / "config.json").write_text(
            json.dumps(config, indent=2) + "\n", encoding="utf-8"
        )

    return {"agent_id": agent_id, "created": True}


async def handle_agents_remove(conn: GatewayConnection, params: dict[str, Any]) -> dict[str, Any]:
    """Remove an agent directory."""
    import shutil
    from pyclaw.config.paths import resolve_agents_dir

    agent_id = params.get("agent_id", "").strip()
    if not agent_id:
        return {"error": "agent_id is required"}

    agents_dir = resolve_agents_dir()
    agent_dir = agents_dir / agent_id
    if not agent_dir.is_dir():
        return {"error": f"Agent '{agent_id}' not found"}

    shutil.rmtree(agent_dir)
    return {"agent_id": agent_id, "removed": True}


def create_agents_handlers() -> dict[str, Any]:
    return {
        "agents.list": handle_agents_list,
        "agents.add": handle_agents_add,
        "agents.remove": handle_agents_remove,
    }
