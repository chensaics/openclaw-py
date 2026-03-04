"""Plugin HTTP routes — allow plugins to register custom FastAPI routes.

Plugins can register routes via the gateway's plugin route registry,
which are then mounted on the FastAPI application.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from fastapi import APIRouter, FastAPI

logger = logging.getLogger(__name__)


@dataclass
class PluginRoute:
    plugin_id: str
    prefix: str
    router: APIRouter


class PluginRouteRegistry:
    """Manages plugin HTTP route registrations."""

    def __init__(self) -> None:
        self._routes: list[PluginRoute] = []

    def register(self, plugin_id: str, prefix: str, router: APIRouter) -> None:
        """Register a plugin's API router under a prefix."""
        self._routes.append(
            PluginRoute(
                plugin_id=plugin_id,
                prefix=prefix,
                router=router,
            )
        )
        logger.info("Plugin route registered: %s → %s", plugin_id, prefix)

    def mount_all(self, app: FastAPI) -> None:
        """Mount all registered plugin routes on the FastAPI app."""
        for route in self._routes:
            full_prefix = f"/plugins/{route.plugin_id}{route.prefix}"
            app.include_router(route.router, prefix=full_prefix)
            logger.info("Mounted plugin route: %s", full_prefix)

    def list_routes(self) -> list[dict[str, str]]:
        return [{"pluginId": r.plugin_id, "prefix": f"/plugins/{r.plugin_id}{r.prefix}"} for r in self._routes]

    def __len__(self) -> int:
        return len(self._routes)
