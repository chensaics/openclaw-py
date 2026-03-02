"""Config file I/O — load and save pyclaw JSON5 configuration.

Compatible with the TypeScript version's config file format.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import json5

from pyclaw.config.paths import resolve_config_path
from pyclaw.config.schema import PyClawConfig


def load_config(path: Path | None = None) -> PyClawConfig:
    """Load and parse an pyclaw JSON5 config file.

    Returns a validated PyClawConfig. Unknown fields are preserved.
    """
    config_path = path or resolve_config_path()
    if not config_path.exists():
        return PyClawConfig()

    raw = config_path.read_text(encoding="utf-8")
    parsed = json5.loads(raw)
    return PyClawConfig.model_validate(parsed)


def save_config(config: PyClawConfig, path: Path | None = None) -> None:
    """Save config to disk as JSON (not JSON5 — JSON is a valid subset).

    Uses atomic write (write to temp, then rename) to prevent corruption.
    """
    config_path = path or resolve_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)

    data = config.model_dump(by_alias=True, exclude_none=True)
    content = json.dumps(data, indent=2, ensure_ascii=False) + "\n"

    tmp_path = config_path.with_suffix(".tmp")
    tmp_path.write_text(content, encoding="utf-8")
    tmp_path.rename(config_path)


def load_config_raw(path: Path | None = None) -> dict[str, Any]:
    """Load config as a raw dict (no validation)."""
    config_path = path or resolve_config_path()
    if not config_path.exists():
        return {}
    raw = config_path.read_text(encoding="utf-8")
    return json5.loads(raw)


def patch_config(updates: dict[str, Any], path: Path | None = None) -> PyClawConfig:
    """Load config, merge updates, save, and return the result."""
    config_path = path or resolve_config_path()
    raw = load_config_raw(config_path)
    _deep_merge(raw, updates)
    config = PyClawConfig.model_validate(raw)
    save_config(config, config_path)
    return config


def _deep_merge(base: dict[str, Any], updates: dict[str, Any]) -> None:
    """Recursively merge updates into base dict."""
    for key, value in updates.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
