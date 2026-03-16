"""Project-wide state/config directory and filename constants."""

from __future__ import annotations

CONFIG_FILENAME = "pyclaw.json"
OPENCLAW_CONFIG_FILENAME = "openclaw.json"

STATE_DIRNAME = ".pyclaw"
OPENCLAW_STATE_DIRNAME = ".openclaw"
LEGACY_STATE_DIRNAMES = (OPENCLAW_STATE_DIRNAME, ".clawdbot", ".moldbot", ".moltbot")
LEGACY_CONFIG_FILENAMES = ("openclaw.json", "clawdbot.json", "moldbot.json", "moltbot.json")

AGENTS_DIRNAME = "agents"
SESSIONS_DIRNAME = "sessions"
CREDENTIALS_DIRNAME = "credentials"
MEMORY_DIRNAME = "memory"
WORKSPACE_DIRNAME = "workspace"
BROWSER_PROFILES_DIRNAME = "browser-profiles"
