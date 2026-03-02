"""Gateway service discovery — Bonjour mDNS + Tailscale DNS publishing.

Ported from ``src/gateway/server-discovery.ts``.

Provides:
- Service advertisement via mDNS/Bonjour (zeroconf)
- Tailscale DNS publishing via CLI
- Gateway URL resolution from multiple sources
- Discovery state management
"""

from __future__ import annotations

import logging
import socket
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class DiscoveryMethod(str, Enum):
    MDNS = "mdns"
    TAILSCALE = "tailscale"
    MANUAL = "manual"
    LOCAL = "local"


@dataclass
class DiscoveryConfig:
    """Configuration for service discovery."""
    mdns_enabled: bool = True
    tailscale_enabled: bool = False
    service_name: str = "pyclaw-gateway"
    service_type: str = "_pyclaw._tcp.local."
    port: int = 18789
    hostname: str = ""
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass
class DiscoveredService:
    """A discovered gateway service."""
    name: str
    host: str
    port: int
    method: DiscoveryMethod
    url: str = ""
    metadata: dict[str, str] = field(default_factory=dict)
    discovered_at: float = 0.0

    def __post_init__(self) -> None:
        if not self.url:
            self.url = f"http://{self.host}:{self.port}"
        if self.discovered_at == 0:
            self.discovered_at = time.time()


@dataclass
class AdvertisementState:
    """State of the service advertisement."""
    advertising: bool = False
    method: DiscoveryMethod = DiscoveryMethod.LOCAL
    service_name: str = ""
    started_at: float = 0.0


class MDNSAdvertiser:
    """Advertise the gateway via mDNS/Bonjour (zeroconf interface)."""

    def __init__(self, config: DiscoveryConfig) -> None:
        self._config = config
        self._state = AdvertisementState(method=DiscoveryMethod.MDNS)

    def build_service_info(self) -> dict[str, Any]:
        """Build service info dict for zeroconf registration."""
        hostname = self._config.hostname or socket.gethostname()
        return {
            "type": self._config.service_type,
            "name": f"{self._config.service_name}.{self._config.service_type}",
            "port": self._config.port,
            "server": f"{hostname}.local.",
            "properties": {
                "version": "1",
                **self._config.metadata,
            },
        }

    def start(self) -> AdvertisementState:
        """Start advertising (builds info; actual zeroconf registration done externally)."""
        self._state.advertising = True
        self._state.service_name = self._config.service_name
        self._state.started_at = time.time()
        return self._state

    def stop(self) -> None:
        self._state.advertising = False

    @property
    def state(self) -> AdvertisementState:
        return self._state


class TailscaleDiscovery:
    """Tailscale DNS-based service discovery."""

    def __init__(self, config: DiscoveryConfig) -> None:
        self._config = config
        self._state = AdvertisementState(method=DiscoveryMethod.TAILSCALE)

    def build_dns_record(self) -> dict[str, Any]:
        """Build the Tailscale DNS record for publishing."""
        return {
            "service": self._config.service_name,
            "port": self._config.port,
            "proto": "tcp",
            "hostname": self._config.hostname or socket.gethostname(),
        }

    def build_funnel_url(self, tailnet_name: str = "") -> str:
        """Build a Tailscale funnel URL."""
        host = self._config.hostname or socket.gethostname()
        if tailnet_name:
            return f"https://{host}.{tailnet_name}.ts.net:{self._config.port}"
        return f"https://{host}:{self._config.port}"

    def start(self) -> AdvertisementState:
        self._state.advertising = True
        self._state.service_name = self._config.service_name
        self._state.started_at = time.time()
        return self._state

    def stop(self) -> None:
        self._state.advertising = False

    @property
    def state(self) -> AdvertisementState:
        return self._state


def resolve_gateway_url(
    *,
    config_url: str = "",
    env_url: str = "",
    discovered: list[DiscoveredService] | None = None,
    default_port: int = 18789,
) -> str:
    """Resolve the best gateway URL from multiple sources.

    Priority: config > env > discovered > localhost fallback.
    """
    if config_url:
        return config_url
    if env_url:
        return env_url
    if discovered:
        # Prefer Tailscale over mDNS over manual
        priority = {DiscoveryMethod.TAILSCALE: 0, DiscoveryMethod.MDNS: 1, DiscoveryMethod.MANUAL: 2}
        sorted_services = sorted(discovered, key=lambda s: priority.get(s.method, 99))
        if sorted_services:
            return sorted_services[0].url
    return f"http://127.0.0.1:{default_port}"


class ServiceDiscoveryManager:
    """Manage all discovery methods."""

    def __init__(self, config: DiscoveryConfig) -> None:
        self._config = config
        self._mdns = MDNSAdvertiser(config) if config.mdns_enabled else None
        self._tailscale = TailscaleDiscovery(config) if config.tailscale_enabled else None
        self._discovered: list[DiscoveredService] = []

    def start(self) -> list[AdvertisementState]:
        states: list[AdvertisementState] = []
        if self._mdns:
            states.append(self._mdns.start())
        if self._tailscale:
            states.append(self._tailscale.start())
        return states

    def stop(self) -> None:
        if self._mdns:
            self._mdns.stop()
        if self._tailscale:
            self._tailscale.stop()

    def add_discovered(self, service: DiscoveredService) -> None:
        self._discovered.append(service)

    def resolve_url(self, *, config_url: str = "", env_url: str = "") -> str:
        return resolve_gateway_url(
            config_url=config_url,
            env_url=env_url,
            discovered=self._discovered,
            default_port=self._config.port,
        )

    @property
    def is_advertising(self) -> bool:
        if self._mdns and self._mdns.state.advertising:
            return True
        if self._tailscale and self._tailscale.state.advertising:
            return True
        return False
