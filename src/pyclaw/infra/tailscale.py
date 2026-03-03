"""Tailscale VPN integration -- discovery, funnel, serve, whois.

Ported from ``src/infra/tailscale.ts``.
Uses the ``tailscale`` CLI subprocess for all operations.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shutil
import time
from dataclasses import dataclass
from typing import Any, cast

logger = logging.getLogger(__name__)

_cached_binary: str | None = None
_whois_cache: dict[str, tuple[float, dict[str, str] | None]] = {}

WHOIS_CACHE_TTL_S = 60.0
WHOIS_ERROR_TTL_S = 5.0


@dataclass
class TailscaleWhoisIdentity:
    login: str
    name: str = ""


async def _run_exec(
    command: str,
    args: list[str],
    *,
    timeout_s: float = 5.0,
) -> tuple[str, str]:
    """Run a CLI command and return (stdout, stderr). Raises on non-zero exit."""
    proc = await asyncio.create_subprocess_exec(
        command,
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        raise TimeoutError(f"{command} timed out after {timeout_s}s")

    stdout = stdout_b.decode("utf-8", errors="replace") if stdout_b else ""
    stderr = stderr_b.decode("utf-8", errors="replace") if stderr_b else ""

    if proc.returncode and proc.returncode != 0:
        raise RuntimeError(f"{command} exited with {proc.returncode}: {stderr.strip()}")
    return stdout, stderr


def _parse_noisy_json(raw: str) -> dict[str, Any]:
    """Extract a JSON object from potentially noisy stdout."""
    start = raw.find("{")
    end = raw.rfind("}")
    if start < 0 or end < start:
        return {}
    try:
        result: dict[str, Any] = json.loads(raw[start : end + 1])
        return result
    except json.JSONDecodeError:
        return {}


async def find_tailscale_binary() -> str | None:
    """Find the tailscale CLI binary. Returns path or None."""
    env_override = os.environ.get("PYCLAW_TEST_TAILSCALE_BINARY")
    if env_override:
        return env_override

    ts = shutil.which("tailscale")
    if ts:
        return ts

    mac_path = "/Applications/Tailscale.app/Contents/MacOS/Tailscale"
    if os.path.isfile(mac_path):
        try:
            await _run_exec(mac_path, ["--version"], timeout_s=3)
            return mac_path
        except Exception:
            pass

    return None


async def get_tailscale_binary() -> str:
    """Return the cached Tailscale binary path (or ``"tailscale"`` as fallback)."""
    global _cached_binary
    if _cached_binary:
        return _cached_binary
    found = await find_tailscale_binary()
    _cached_binary = found or "tailscale"
    return _cached_binary


async def read_tailscale_status_json(*, timeout_s: float = 5.0) -> dict[str, Any]:
    """Run ``tailscale status --json`` and return parsed JSON."""
    binary = await get_tailscale_binary()
    try:
        stdout, _ = await _run_exec(binary, ["status", "--json"], timeout_s=timeout_s)
    except Exception as exc:
        logger.debug("tailscale status failed: %s", exc)
        return {}
    return _parse_noisy_json(stdout)


async def get_tailnet_hostname() -> str:
    """Return this machine's Tailscale DNS name or first IP."""
    status = await read_tailscale_status_json()
    self_info = status.get("Self", {})
    dns_name = self_info.get("DNSName", "")
    if dns_name:
        return cast(str, dns_name.rstrip("."))
    ips = self_info.get("TailscaleIPs", [])
    if ips:
        return cast(str, ips[0])
    raise RuntimeError("Cannot determine Tailscale hostname: no DNS name or IPs found")


async def ensure_funnel(port: int) -> None:
    """Enable Tailscale Funnel for *port*.

    Runs ``tailscale funnel --yes --bg <port>``. Falls back to ``sudo``
    on permission errors.
    """
    binary = await get_tailscale_binary()
    try:
        await _run_exec(binary, ["funnel", "--yes", "--bg", str(port)])
        logger.info("Tailscale Funnel enabled on port %d", port)
    except RuntimeError as exc:
        if _is_permission_error(str(exc)):
            logger.info("Retrying with sudo...")
            sudo = shutil.which("sudo")
            if sudo:
                await _run_exec(sudo, ["-n", binary, "funnel", "--yes", "--bg", str(port)])
                logger.info("Tailscale Funnel enabled (via sudo) on port %d", port)
                return
        raise


async def enable_tailscale_serve(port: int) -> None:
    """Run ``tailscale serve --bg --yes <port>``."""
    binary = await get_tailscale_binary()
    try:
        await _run_exec(binary, ["serve", "--bg", "--yes", str(port)])
    except RuntimeError as exc:
        if _is_permission_error(str(exc)):
            sudo = shutil.which("sudo")
            if sudo:
                await _run_exec(sudo, ["-n", binary, "serve", "--bg", "--yes", str(port)])
                return
        raise


async def disable_tailscale_serve() -> None:
    """Run ``tailscale serve reset``."""
    binary = await get_tailscale_binary()
    await _run_exec(binary, ["serve", "reset"])


async def enable_tailscale_funnel(port: int) -> None:
    """Run ``tailscale funnel --bg --yes <port>``."""
    binary = await get_tailscale_binary()
    await _run_exec(binary, ["funnel", "--bg", "--yes", str(port)])


async def disable_tailscale_funnel() -> None:
    """Run ``tailscale funnel reset``."""
    binary = await get_tailscale_binary()
    await _run_exec(binary, ["funnel", "reset"])


async def read_tailscale_whois_identity(
    ip: str,
    *,
    timeout_s: float = 5.0,
    cache_ttl_s: float = WHOIS_CACHE_TTL_S,
    error_ttl_s: float = WHOIS_ERROR_TTL_S,
) -> TailscaleWhoisIdentity | None:
    """Return the Tailscale identity for *ip*, with caching."""
    now = time.monotonic()
    if ip in _whois_cache:
        ts, val = _whois_cache[ip]
        ttl = cache_ttl_s if val is not None else error_ttl_s
        if now - ts < ttl:
            if val is None:
                return None
            return TailscaleWhoisIdentity(login=val["login"], name=val.get("name", ""))

    binary = await get_tailscale_binary()
    try:
        stdout, _ = await _run_exec(binary, ["whois", "--json", ip], timeout_s=timeout_s)
    except Exception as exc:
        logger.debug("tailscale whois %s failed: %s", ip, exc)
        _whois_cache[ip] = (now, None)
        return None

    data = _parse_noisy_json(stdout)
    login = (
        data.get("UserProfile", {}).get("LoginName")
        or data.get("User", {}).get("LoginName")
        or data.get("LoginName")
        or ""
    )
    name = (
        data.get("UserProfile", {}).get("DisplayName")
        or data.get("User", {}).get("DisplayName")
        or data.get("DisplayName")
        or ""
    )

    if not login:
        _whois_cache[ip] = (now, None)
        return None

    entry = {"login": login, "name": name}
    _whois_cache[ip] = (now, entry)
    return TailscaleWhoisIdentity(login=login, name=name)


_PERM_PATTERNS = re.compile(
    r"permission denied|access denied|operation not permitted|"
    r"requires root|must be run as root|requires sudo|EACCES",
    re.IGNORECASE,
)


def _is_permission_error(msg: str) -> bool:
    return bool(_PERM_PATTERNS.search(msg))
