"""SSRF protection — private IP/localhost interception, domain allowlist.

Ported from ``src/infra/net/ssrf.ts``.

Provides:
- Private/reserved IP detection (RFC 1918, loopback, link-local, etc.)
- Hostname resolution and validation
- Domain allowlist management
- URL validation for outbound requests
"""

from __future__ import annotations

import ipaddress
import logging
import re
import socket
from dataclasses import dataclass, field
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


PRIVATE_RANGES = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]

BLOCKED_HOSTNAMES = frozenset({
    "localhost",
    "localhost.localdomain",
    "0.0.0.0",
    "[::1]",
    "metadata.google.internal",         # GCP metadata
    "169.254.169.254",                   # Cloud metadata (AWS/GCP/Azure)
})


@dataclass
class SSRFConfig:
    """Configuration for SSRF protection."""
    enabled: bool = True
    allow_private: bool = False
    allowed_domains: list[str] = field(default_factory=list)
    blocked_domains: list[str] = field(default_factory=list)
    allowed_ports: list[int] = field(default_factory=lambda: [80, 443, 8080, 8443])
    resolve_dns: bool = True


@dataclass
class SSRFCheckResult:
    """Result of an SSRF check."""
    allowed: bool
    reason: str = ""
    resolved_ip: str = ""
    hostname: str = ""


def is_private_ip(ip_str: str) -> bool:
    """Check if an IP address is in a private/reserved range."""
    try:
        addr = ipaddress.ip_address(ip_str)
        return any(addr in network for network in PRIVATE_RANGES)
    except ValueError:
        return False


def is_blocked_hostname(hostname: str) -> bool:
    """Check if a hostname is in the blocked list."""
    return hostname.lower() in BLOCKED_HOSTNAMES


def resolve_hostname(hostname: str) -> list[str]:
    """Resolve a hostname to IP addresses."""
    try:
        results = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        return list({str(r[4][0]) for r in results})
    except socket.gaierror:
        return []


def check_url(url: str, config: SSRFConfig | None = None) -> SSRFCheckResult:
    """Check if a URL is safe from SSRF perspective."""
    config = config or SSRFConfig()

    if not config.enabled:
        return SSRFCheckResult(allowed=True)

    try:
        parsed = urlparse(url)
    except Exception:
        return SSRFCheckResult(allowed=False, reason="Invalid URL")

    scheme = parsed.scheme.lower()
    if scheme not in ("http", "https"):
        return SSRFCheckResult(allowed=False, reason=f"Blocked scheme: {scheme}")

    hostname = parsed.hostname or ""
    if not hostname:
        return SSRFCheckResult(allowed=False, reason="No hostname in URL")

    # Check blocked hostnames
    if is_blocked_hostname(hostname):
        return SSRFCheckResult(allowed=False, reason=f"Blocked hostname: {hostname}", hostname=hostname)

    # Check blocked domains
    for domain in config.blocked_domains:
        if hostname == domain or hostname.endswith(f".{domain}"):
            return SSRFCheckResult(allowed=False, reason=f"Blocked domain: {domain}", hostname=hostname)

    # Check allowed domains (if configured, acts as allowlist)
    if config.allowed_domains:
        matched = any(
            hostname == d or hostname.endswith(f".{d}")
            for d in config.allowed_domains
        )
        if not matched:
            return SSRFCheckResult(allowed=False, reason="Not in allowed domains", hostname=hostname)

    # Check port
    port = parsed.port
    if port and config.allowed_ports and port not in config.allowed_ports:
        return SSRFCheckResult(allowed=False, reason=f"Blocked port: {port}", hostname=hostname)

    # Direct IP check
    if is_private_ip(hostname) and not config.allow_private:
        return SSRFCheckResult(allowed=False, reason="Private IP address", hostname=hostname, resolved_ip=hostname)

    # DNS resolution check
    if config.resolve_dns and not is_private_ip(hostname):
        ips = resolve_hostname(hostname)
        for ip in ips:
            if is_private_ip(ip) and not config.allow_private:
                return SSRFCheckResult(
                    allowed=False,
                    reason=f"Hostname resolves to private IP: {ip}",
                    hostname=hostname,
                    resolved_ip=ip,
                )
        resolved_ip = ips[0] if ips else ""
        return SSRFCheckResult(allowed=True, hostname=hostname, resolved_ip=resolved_ip)

    return SSRFCheckResult(allowed=True, hostname=hostname)


class SSRFGuard:
    """Stateful SSRF guard with configuration."""

    def __init__(self, config: SSRFConfig | None = None) -> None:
        self._config = config or SSRFConfig()
        self._blocked_count = 0

    def check(self, url: str) -> SSRFCheckResult:
        result = check_url(url, self._config)
        if not result.allowed:
            self._blocked_count += 1
        return result

    def add_allowed_domain(self, domain: str) -> None:
        if domain not in self._config.allowed_domains:
            self._config.allowed_domains.append(domain)

    def add_blocked_domain(self, domain: str) -> None:
        if domain not in self._config.blocked_domains:
            self._config.blocked_domains.append(domain)

    @property
    def blocked_count(self) -> int:
        return self._blocked_count

    @property
    def config(self) -> SSRFConfig:
        return self._config
