"""Path resolution for pyclaw state, config, and session files.

Compatible with the TypeScript version's path conventions.
"""

import os
from collections.abc import Mapping
from pathlib import Path

CONFIG_FILENAME = "pyclaw.json"
NEW_STATE_DIRNAME = ".pyclaw"
LEGACY_STATE_DIRNAMES = [".openclaw", ".clawdbot", ".moldbot", ".moltbot"]
LEGACY_CONFIG_FILENAMES = ["openclaw.json", "clawdbot.json", "moldbot.json", "moltbot.json"]
DEFAULT_GATEWAY_PORT = 18789


def _homedir() -> Path:
    return Path.home()


def resolve_state_dir(env: Mapping[str, str] | None = None) -> Path:
    """Resolve the pyclaw state directory.

    Checks PYCLAW_STATE_DIR env var, then falls back to ~/.pyclaw.
    Recognizes legacy directory names for migration.
    """
    e = env or os.environ
    if override := e.get("PYCLAW_STATE_DIR"):
        return Path(override)

    home = _homedir()

    new_dir = home / NEW_STATE_DIRNAME
    if new_dir.exists():
        return new_dir

    for legacy in LEGACY_STATE_DIRNAMES:
        legacy_dir = home / legacy
        if legacy_dir.exists():
            return legacy_dir

    return new_dir


def resolve_config_path(env: Mapping[str, str] | None = None) -> Path:
    """Resolve the config file path.

    Checks PYCLAW_CONFIG_PATH env var, then looks in state dir.
    """
    e = env or os.environ
    if override := e.get("PYCLAW_CONFIG_PATH"):
        return Path(override)

    state_dir = resolve_state_dir(e)

    config_path = state_dir / CONFIG_FILENAME
    if config_path.exists():
        return config_path

    for legacy_name in LEGACY_CONFIG_FILENAMES:
        legacy_path = state_dir / legacy_name
        if legacy_path.exists():
            return legacy_path

    return config_path


def resolve_agents_dir(state_dir: Path | None = None) -> Path:
    sd = state_dir or resolve_state_dir()
    return sd / "agents"


def resolve_agent_dir(agent_id: str, state_dir: Path | None = None) -> Path:
    return resolve_agents_dir(state_dir) / agent_id


def resolve_sessions_dir(agent_id: str, state_dir: Path | None = None) -> Path:
    return resolve_agent_dir(agent_id, state_dir) / "sessions"


def resolve_credentials_dir(state_dir: Path | None = None) -> Path:
    sd = state_dir or resolve_state_dir()
    return sd / "credentials"


def resolve_memory_dir(state_dir: Path | None = None) -> Path:
    sd = state_dir or resolve_state_dir()
    return sd / "memory"


def resolve_workspace_dir(state_dir: Path | None = None) -> Path:
    sd = state_dir or resolve_state_dir()
    return sd / "workspace"


def resolve_gateway_port(env: Mapping[str, str] | None = None) -> int:
    e = env or os.environ
    if port_str := e.get("PYCLAW_GATEWAY_PORT"):
        return int(port_str)
    return DEFAULT_GATEWAY_PORT
