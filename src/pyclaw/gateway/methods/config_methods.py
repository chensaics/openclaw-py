"""config.* — configuration read/write handlers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from pyclaw.gateway.server import GatewayConnection, MethodHandler


def create_config_handlers(
    *, config_path: str | None = None
) -> dict[str, MethodHandler]:
    def _resolve_path() -> Path:
        if config_path:
            return Path(config_path)
        from pyclaw.config.paths import resolve_config_path
        return resolve_config_path()

    async def handle_config_get(
        params: dict[str, Any] | None, conn: GatewayConnection
    ) -> None:
        from pyclaw.config.io import load_config

        path = _resolve_path()
        if not path.exists():
            await conn.send_ok("config.get", {"config": {}})
            return

        try:
            cfg = load_config(path)
            await conn.send_ok("config.get", {
                "config": cfg.model_dump(by_alias=True, exclude_none=True),
            })
        except Exception as e:
            await conn.send_error("config.get", "config_error", str(e))

    async def handle_config_set(
        params: dict[str, Any] | None, conn: GatewayConnection
    ) -> None:
        from pyclaw.config.io import save_config
        from pyclaw.config.schema import PyClawConfig

        if not params or "config" not in params:
            await conn.send_error(
                "config.set", "invalid_params", "Missing 'config' in params."
            )
            return

        path = _resolve_path()
        try:
            cfg = PyClawConfig.model_validate(params["config"])
            save_config(path, cfg)
            await conn.send_ok("config.set", {"saved": True})
        except Exception as e:
            await conn.send_error("config.set", "config_error", str(e))

    async def handle_config_patch(
        params: dict[str, Any] | None, conn: GatewayConnection
    ) -> None:
        from pyclaw.config.io import patch_config

        if not params or "patch" not in params:
            await conn.send_error(
                "config.patch", "invalid_params", "Missing 'patch' in params."
            )
            return

        path = _resolve_path()
        try:
            cfg = patch_config(path, params["patch"])
            await conn.send_ok("config.patch", {
                "config": cfg.model_dump(by_alias=True, exclude_none=True),
            })
        except Exception as e:
            await conn.send_error("config.patch", "config_error", str(e))

    return {
        "config.get": handle_config_get,
        "config.set": handle_config_set,
        "config.patch": handle_config_patch,
    }
