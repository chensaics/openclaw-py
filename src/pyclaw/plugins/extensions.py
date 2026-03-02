"""Non-channel extension framework — plugins that aren't messaging channels.

Ported from ``src/extensions/`` patterns in the TypeScript codebase.

Extensions can provide:
- Custom tools for the agent
- Gateway method handlers
- Background tasks (cron, watchers)
- Memory backends
- Custom middleware

Unlike channel plugins, extensions don't process messages from a messaging
platform. They augment the agent/gateway with additional capabilities.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ExtensionManifest:
    """Metadata manifest for an extension."""

    name: str
    version: str = "0.0.0"
    description: str = ""
    author: str = ""
    homepage: str = ""
    requires: list[str] = field(default_factory=list)
    provides: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "homepage": self.homepage,
            "requires": self.requires,
            "provides": self.provides,
        }


class Extension(ABC):
    """Abstract base class for non-channel extensions."""

    @property
    @abstractmethod
    def manifest(self) -> ExtensionManifest:
        """Return the extension manifest."""
        ...

    async def on_load(self, context: ExtensionContext) -> None:
        """Called when the extension is loaded. Register tools, methods, etc."""

    async def on_unload(self) -> None:
        """Called when the extension is unloaded."""

    async def on_gateway_start(self) -> None:
        """Called when the gateway starts."""

    async def on_gateway_stop(self) -> None:
        """Called when the gateway stops."""


@dataclass
class ExtensionContext:
    """Context passed to extensions on load."""

    config: dict[str, Any] = field(default_factory=dict)
    register_tool: Any = None
    register_method: Any = None
    register_task: Any = None
    data_dir: str = ""


class ExtensionRegistry:
    """Registry for non-channel extensions."""

    def __init__(self) -> None:
        self._extensions: dict[str, Extension] = {}
        self._load_order: list[str] = []

    def register(self, extension: Extension) -> None:
        name = extension.manifest.name
        if name in self._extensions:
            logger.warning("Extension %s already registered, replacing", name)
        self._extensions[name] = extension
        if name not in self._load_order:
            self._load_order.append(name)
        logger.debug("Registered extension: %s v%s", name, extension.manifest.version)

    def get(self, name: str) -> Extension | None:
        return self._extensions.get(name)

    def list_all(self) -> list[Extension]:
        return [self._extensions[n] for n in self._load_order if n in self._extensions]

    def list_manifests(self) -> list[ExtensionManifest]:
        return [ext.manifest for ext in self.list_all()]

    async def load_all(self, context: ExtensionContext) -> list[str]:
        """Load all registered extensions, respecting dependency order."""
        loaded: list[str] = []
        provided: set[str] = set()

        # Topological sort by requires/provides
        ordered = self._resolve_load_order()

        for name in ordered:
            ext = self._extensions.get(name)
            if not ext:
                continue

            # Check deps
            missing = [r for r in ext.manifest.requires if r not in provided]
            if missing:
                logger.error(
                    "Extension %s requires %s but they are not provided",
                    name,
                    missing,
                )
                continue

            try:
                await ext.on_load(context)
                loaded.append(name)
                provided.update(ext.manifest.provides)
                logger.info("Loaded extension: %s", name)
            except Exception:
                logger.exception("Failed to load extension: %s", name)

        return loaded

    async def unload_all(self) -> None:
        """Unload all extensions in reverse order."""
        for name in reversed(self._load_order):
            ext = self._extensions.get(name)
            if ext:
                try:
                    await ext.on_unload()
                except Exception:
                    logger.exception("Failed to unload extension: %s", name)

        self._extensions.clear()
        self._load_order.clear()

    async def notify_gateway_start(self) -> None:
        for ext in self.list_all():
            try:
                await ext.on_gateway_start()
            except Exception:
                logger.exception(
                    "Extension %s failed on gateway start",
                    ext.manifest.name,
                )

    async def notify_gateway_stop(self) -> None:
        for ext in self.list_all():
            try:
                await ext.on_gateway_stop()
            except Exception:
                logger.exception(
                    "Extension %s failed on gateway stop",
                    ext.manifest.name,
                )

    def _resolve_load_order(self) -> list[str]:
        """Simple topological sort by requires/provides."""
        provided_by: dict[str, str] = {}
        for name, ext in self._extensions.items():
            for cap in ext.manifest.provides:
                provided_by[cap] = name

        visited: set[str] = set()
        order: list[str] = []

        def visit(name: str) -> None:
            if name in visited:
                return
            visited.add(name)
            ext = self._extensions.get(name)
            if ext:
                for req in ext.manifest.requires:
                    provider = provided_by.get(req)
                    if provider:
                        visit(provider)
            order.append(name)

        for name in self._load_order:
            visit(name)

        return order
