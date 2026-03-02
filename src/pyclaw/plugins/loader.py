"""Plugin loader — discovers and loads extension packages.

Plugins are Python packages that expose a ``pyclaw_plugin`` entry point
or live under the ``extensions/`` directory. Each plugin can provide:
  - Channel implementations
  - Agent tools
  - Gateway method handlers
"""

from __future__ import annotations

import importlib
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("pyclaw.plugins")


@dataclass
class PluginInfo:
    """Metadata for a loaded plugin."""

    name: str
    version: str
    module: Any
    channels: list[Any] = field(default_factory=list)
    tools: list[Any] = field(default_factory=list)
    gateway_methods: dict[str, Any] = field(default_factory=dict)


class PluginLoader:
    """Discovers and loads pyclaw plugins."""

    def __init__(self) -> None:
        self._plugins: dict[str, PluginInfo] = {}

    def load_from_entry_points(self) -> list[PluginInfo]:
        """Load plugins registered via Python entry points."""
        loaded: list[PluginInfo] = []
        try:
            from importlib.metadata import entry_points
            eps = entry_points(group="pyclaw.plugins")
        except Exception:
            return loaded

        for ep in eps:
            try:
                module = ep.load()
                info = self._register_module(ep.name, module)
                if info:
                    loaded.append(info)
                    logger.info("Loaded plugin: %s", ep.name)
            except Exception:
                logger.exception("Failed to load plugin: %s", ep.name)

        return loaded

    def load_from_directory(self, extensions_dir: Path) -> list[PluginInfo]:
        """Load plugins from an extensions directory."""
        loaded: list[PluginInfo] = []

        if not extensions_dir.exists():
            return loaded

        for plugin_dir in sorted(extensions_dir.iterdir()):
            if not plugin_dir.is_dir():
                continue
            # Look for a Python package with __init__.py
            init_file = plugin_dir / "__init__.py"
            if not init_file.exists():
                # Also check for src layout
                src_init = plugin_dir / "src" / plugin_dir.name / "__init__.py"
                if not src_init.exists():
                    continue

            try:
                module = importlib.import_module(plugin_dir.name)
                info = self._register_module(plugin_dir.name, module)
                if info:
                    loaded.append(info)
                    logger.info("Loaded extension: %s", plugin_dir.name)
            except Exception:
                logger.exception("Failed to load extension: %s", plugin_dir.name)

        return loaded

    def load_module(self, name: str, module_path: str) -> PluginInfo | None:
        """Load a single plugin by importable module path."""
        try:
            module = importlib.import_module(module_path)
            return self._register_module(name, module)
        except Exception:
            logger.exception("Failed to load module: %s", module_path)
            return None

    def _register_module(self, name: str, module: Any) -> PluginInfo | None:
        version = getattr(module, "__version__", "0.0.0")
        info = PluginInfo(name=name, version=version, module=module)

        # Look for register() function
        register_fn = getattr(module, "register", None)
        if register_fn and callable(register_fn):
            try:
                result = register_fn()
                if isinstance(result, dict):
                    info.channels = result.get("channels", [])
                    info.tools = result.get("tools", [])
                    info.gateway_methods = result.get("gateway_methods", {})
            except Exception:
                logger.exception("Plugin register() failed: %s", name)

        self._plugins[name] = info
        return info

    def get(self, name: str) -> PluginInfo | None:
        return self._plugins.get(name)

    def all(self) -> list[PluginInfo]:
        return list(self._plugins.values())

    def names(self) -> list[str]:
        return list(self._plugins.keys())
