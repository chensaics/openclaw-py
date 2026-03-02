"""Daemon/Service management — launchd, systemd, schtasks.

Ported from ``src/daemon/``.
"""

from pyclaw.daemon.service import resolve_gateway_service, GatewayService

__all__ = ["GatewayService", "resolve_gateway_service"]
