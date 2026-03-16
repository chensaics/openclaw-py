"""mDNS/Bonjour gateway advertisement via zeroconf.

Ported from ``src/infra/bonjour.ts``.
Publishes a ``_pyclaw-gw._tcp.local.`` service so LAN clients can
auto-discover the gateway.
"""

from __future__ import annotations

import asyncio
import logging
import os
import socket
from dataclasses import dataclass
from typing import Any

from pyclaw.constants.env import (
    ENV_CLAWDBOT_MDNS_HOSTNAME,
    ENV_PYCLAW_DISABLE_BONJOUR,
    ENV_PYCLAW_MDNS_HOSTNAME,
    ENV_PYCLAW_TEST,
)

logger = logging.getLogger(__name__)


@dataclass
class BonjourAdvertiseOpts:
    gateway_port: int
    instance_name: str = ""
    ssh_port: int = 22
    gateway_tls_enabled: bool = False
    gateway_tls_fingerprint_sha256: str = ""
    canvas_port: int = 0
    tailnet_dns: str = ""
    cli_path: str = ""
    minimal: bool = False


@dataclass
class BonjourAdvertiser:
    """Handle to a running Bonjour advertiser; call ``stop()`` to unregister."""

    _zeroconf: Any = None
    _info: Any = None
    _watchdog_task: asyncio.Task[None] | None = None

    async def stop(self) -> None:
        if self._watchdog_task and not self._watchdog_task.done():
            self._watchdog_task.cancel()
        if self._zeroconf:
            try:
                if self._info:
                    self._zeroconf.unregister_service(self._info)
                self._zeroconf.close()
            except Exception:
                logger.debug("Error stopping Bonjour advertiser", exc_info=True)
            self._zeroconf = None


def _build_txt_records(opts: BonjourAdvertiseOpts) -> dict[str, str]:
    hostname = socket.gethostname().split(".")[0]
    txt: dict[str, str] = {
        "role": "gateway",
        "gatewayPort": str(opts.gateway_port),
        "lanHost": hostname,
        "displayName": opts.instance_name or f"{hostname} (pyclaw)",
        "transport": "tls" if opts.gateway_tls_enabled else "ws",
    }
    if opts.gateway_tls_enabled and opts.gateway_tls_fingerprint_sha256:
        txt["gatewayTlsSha256"] = opts.gateway_tls_fingerprint_sha256
    if opts.canvas_port:
        txt["canvasPort"] = str(opts.canvas_port)
    if opts.tailnet_dns:
        txt["tailnetDns"] = opts.tailnet_dns
    if not opts.minimal:
        if opts.cli_path:
            txt["cliPath"] = opts.cli_path
        txt["sshPort"] = str(opts.ssh_port)
    return txt


async def start_gateway_bonjour_advertiser(
    opts: BonjourAdvertiseOpts,
) -> BonjourAdvertiser:
    """Start advertising the gateway via mDNS.

    Returns a :class:`BonjourAdvertiser` that can be stopped later.
    Falls back to a no-op advertiser if ``zeroconf`` is not installed or
    mDNS is disabled via environment variable.
    """
    if os.environ.get(ENV_PYCLAW_DISABLE_BONJOUR) or os.environ.get(ENV_PYCLAW_TEST):
        logger.debug("Bonjour disabled via environment")
        return BonjourAdvertiser()

    try:
        from zeroconf import ServiceInfo, Zeroconf
    except ImportError:
        logger.warning("zeroconf not installed; Bonjour advertising disabled")
        return BonjourAdvertiser()

    mdns_hostname = os.environ.get(ENV_PYCLAW_MDNS_HOSTNAME) or os.environ.get(ENV_CLAWDBOT_MDNS_HOSTNAME) or "pyclaw"
    mdns_hostname = mdns_hostname.replace(".local", "").split(".")[0]

    instance_name = opts.instance_name or f"{socket.gethostname().split('.')[0]} (pyclaw)"
    txt = _build_txt_records(opts)

    service_type = "_pyclaw-gw._tcp.local."
    info = ServiceInfo(
        type_=service_type,
        name=f"{instance_name}.{service_type}",
        port=opts.gateway_port,
        properties=txt,
        server=f"{mdns_hostname}.local.",
    )

    zc = Zeroconf()
    try:
        zc.register_service(info)
        logger.info("Bonjour: advertising %s on port %d", instance_name, opts.gateway_port)
    except Exception:
        logger.error("Failed to register Bonjour service", exc_info=True)
        zc.close()
        return BonjourAdvertiser()

    advertiser = BonjourAdvertiser(_zeroconf=zc, _info=info)

    async def _watchdog() -> None:
        while True:
            await asyncio.sleep(60)
            try:
                zc.unregister_service(info)
                zc.register_service(info)
            except Exception:
                logger.debug("Bonjour watchdog re-announce failed", exc_info=True)

    advertiser._watchdog_task = asyncio.create_task(_watchdog())
    return advertiser
