"""Path resolution for pyclaw state, config, and session files.

Compatible with the TypeScript version's path conventions.
"""

import os
from collections.abc import Mapping
from pathlib import Path

from pyclaw.constants.env import (
    ENV_OPENCLAW_CONFIG_PATH,
    ENV_OPENCLAW_GATEWAY_PORT,
    ENV_OPENCLAW_STATE_DIR,
    ENV_PYCLAW_CONFIG_PATH,
    ENV_PYCLAW_GATEWAY_PORT,
    ENV_PYCLAW_STATE_DIR,
)
from pyclaw.constants.runtime import DEFAULT_GATEWAY_PORT
from pyclaw.constants.storage import (
    AGENTS_DIRNAME,
    CONFIG_FILENAME,
    CREDENTIALS_DIRNAME,
    LEGACY_CONFIG_FILENAMES,
    LEGACY_STATE_DIRNAMES,
    MEMORY_DIRNAME,
    OPENCLAW_CONFIG_FILENAME,
    OPENCLAW_STATE_DIRNAME,
    SESSIONS_DIRNAME,
    STATE_DIRNAME,
    WORKSPACE_DIRNAME,
)


def _homedir() -> Path:
    return Path.home()


def resolve_state_dir(env: Mapping[str, str] | None = None) -> Path:
    """Resolve the pyclaw state directory.

    Checks PYCLAW_STATE_DIR / OPENCLAW_STATE_DIR env vars, then falls back to ~/.pyclaw.
    Recognizes legacy directory names for migration.
    """
    e = env or os.environ
    if override := e.get(ENV_PYCLAW_STATE_DIR):
        return Path(override)
    if override := e.get(ENV_OPENCLAW_STATE_DIR):
        return Path(override)

    home = _homedir()

    new_dir = home / STATE_DIRNAME
    if new_dir.exists():
        return new_dir

    for legacy in LEGACY_STATE_DIRNAMES:
        legacy_dir = home / legacy
        if legacy_dir.exists():
            return legacy_dir

    return new_dir


def resolve_config_path(env: Mapping[str, str] | None = None) -> Path:
    """Resolve the config file path.

    Checks PYCLAW_CONFIG_PATH / OPENCLAW_CONFIG_PATH env vars, then looks in state dir.
    """
    e = env or os.environ
    if override := e.get(ENV_PYCLAW_CONFIG_PATH):
        return Path(override)
    if override := e.get(ENV_OPENCLAW_CONFIG_PATH):
        return Path(override)

    state_dir = resolve_state_dir(e)

    # If we are explicitly using the openclaw state dir, prefer openclaw.json.
    default_filename = OPENCLAW_CONFIG_FILENAME if state_dir.name == OPENCLAW_STATE_DIRNAME else CONFIG_FILENAME
    config_path = state_dir / default_filename
    if config_path.exists():
        return config_path

    # Always check pyclaw.json explicitly to preserve existing behavior.
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
    return sd / AGENTS_DIRNAME


def resolve_agent_dir(agent_id: str, state_dir: Path | None = None) -> Path:
    return resolve_agents_dir(state_dir) / agent_id


def resolve_sessions_dir(agent_id: str, state_dir: Path | None = None) -> Path:
    return resolve_agent_dir(agent_id, state_dir) / SESSIONS_DIRNAME


def get_sessions_dir(state_dir: Path | None = None) -> Path:
    """Legacy flat sessions directory path for backward compatibility."""
    sd = state_dir or resolve_state_dir()
    return sd / SESSIONS_DIRNAME


def resolve_credentials_dir(state_dir: Path | None = None) -> Path:
    sd = state_dir or resolve_state_dir()
    return sd / CREDENTIALS_DIRNAME


def resolve_memory_dir(state_dir: Path | None = None) -> Path:
    sd = state_dir or resolve_state_dir()
    return sd / MEMORY_DIRNAME


def resolve_workspace_dir(state_dir: Path | None = None) -> Path:
    sd = state_dir or resolve_state_dir()
    return sd / WORKSPACE_DIRNAME


def resolve_gateway_port(env: Mapping[str, str] | None = None) -> int:
    e = env or os.environ
    if port_str := e.get(ENV_PYCLAW_GATEWAY_PORT):
        return int(port_str)
    if port_str := e.get(ENV_OPENCLAW_GATEWAY_PORT):
        return int(port_str)
    return DEFAULT_GATEWAY_PORT
