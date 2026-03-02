"""Register all core gateway method handlers."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pyclaw.gateway.server import GatewayServer


def register_core_handlers(
    server: GatewayServer, *, config_path: str | None = None
) -> None:
    """Register all built-in method handlers on the gateway server."""
    from pyclaw.gateway.methods.connect import create_connect_handler
    from pyclaw.gateway.methods.config_methods import create_config_handlers
    from pyclaw.gateway.methods.health import create_health_handlers
    from pyclaw.gateway.methods.sessions import create_session_handlers
    from pyclaw.gateway.methods.chat import create_chat_handlers
    from pyclaw.gateway.methods.models import create_models_handlers
    from pyclaw.gateway.methods.agents import create_agents_handlers
    from pyclaw.gateway.methods.channels import create_channels_handlers
    from pyclaw.gateway.methods.tools_catalog import create_tools_handlers
    from pyclaw.gateway.methods.cron_methods import create_cron_handlers
    from pyclaw.gateway.methods.device_pair import create_device_pair_handlers
    from pyclaw.gateway.methods.browser_methods import create_browser_handlers
    from pyclaw.gateway.methods.exec_approvals import create_exec_approval_handlers
    from pyclaw.gateway.methods.extended import create_extended_handlers
    from pyclaw.gateway.methods.logs_methods import create_logs_handlers

    server.register_handler("connect", create_connect_handler(server))
    server.register_handlers(create_health_handlers())
    server.register_handlers(create_config_handlers(config_path=config_path))
    server.register_handlers(create_session_handlers())
    server.register_handlers(create_chat_handlers())
    server.register_handlers(create_models_handlers())
    server.register_handlers(create_agents_handlers())
    server.register_handlers(create_channels_handlers())
    server.register_handlers(create_tools_handlers())
    server.register_handlers(create_cron_handlers())
    server.register_handlers(create_device_pair_handlers())
    # Extended first, then browser — browser_methods overrides any placeholder keys.
    server.register_handlers(create_extended_handlers())
    server.register_handlers(create_exec_approval_handlers())
    server.register_handlers(create_browser_handlers())
    server.register_handlers(create_logs_handlers())
