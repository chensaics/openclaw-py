"""Daemon/Service management — launchd, systemd, schtasks.

Ported from ``src/daemon/``.
"""

from pyclaw.daemon.service import GatewayService, resolve_gateway_service

__all__ = ["GatewayService", "resolve_gateway_service"]
