"""Gateway methods: models.* — enumerate models/providers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pyclaw.gateway.server import GatewayConnection


async def handle_models_list(
    params: dict[str, Any] | None, conn: GatewayConnection
) -> None:
    """Return the model catalog as a list."""
    from pyclaw.agents.model_catalog import ModelCatalog

    catalog = ModelCatalog()
    provider_filter = (params or {}).get("provider")
    models = catalog.list_models(provider=provider_filter)

    await conn.send_ok(
        "models.list",
        {
            "models": [
                {
                    "key": m.key,
                    "provider": m.provider,
                    "model_id": m.model_id,
                    "display_name": m.display_name,
                    "max_tokens": m.max_tokens,
                    "context_window": m.context_window,
                    "supports_tools": m.supports_tools,
                    "supports_vision": m.supports_vision,
                    "supports_thinking": m.supports_thinking,
                    "cost_per_1m_input": m.cost_per_1m_input,
                    "cost_per_1m_output": m.cost_per_1m_output,
                }
                for m in models
            ]
        },
    )


async def handle_models_providers(
    params: dict[str, Any] | None, conn: GatewayConnection
) -> None:
    """Return available providers."""
    _ = params
    from pyclaw.agents.model_catalog import ModelCatalog

    catalog = ModelCatalog()
    await conn.send_ok("models.providers", {"providers": catalog.list_providers()})


def create_models_handlers() -> dict[str, Any]:
    return {
        "models.list": handle_models_list,
        "models.providers": handle_models_providers,
    }
