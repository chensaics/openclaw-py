"""Gateway CLI commands — status, probe, call, discover, run."""

from __future__ import annotations

import asyncio
import json
import socket
import time
from typing import Any, cast

import typer

from pyclaw.config.paths import resolve_config_path


def gateway_run_command(
    *,
    port: int = 18789,
    bind: str = "127.0.0.1",
    auth_token: str | None = None,
) -> None:
    """Start the pyclaw gateway server."""
    import uvicorn

    from pyclaw.gateway.server import create_gateway_app

    server = create_gateway_app(auth_token=auth_token)
    typer.echo(f"Starting pyclaw gateway on {bind}:{port}")
    uvicorn.run(server.app, host=bind, port=port, log_level="info")


def gateway_status_command(
    *,
    url: str = "",
    token: str | None = None,
    password: str | None = None,
    timeout_ms: int = 10000,
    no_probe: bool = False,
    deep: bool = False,
    output_json: bool = False,
) -> None:
    """Show gateway service + optional RPC probe status."""
    result: dict[str, Any] = {"service": _service_status(deep=deep)}

    if not no_probe:
        gw_url = url or _default_gateway_url()
        probe = _probe_gateway(gw_url, token=token, password=password, timeout_s=timeout_ms / 1000)
        result["probe"] = probe

    if output_json:
        typer.echo(json.dumps(result, ensure_ascii=False))
        return

    svc = result["service"]
    typer.echo(f"Service: {svc.get('status', 'unknown')}")
    if svc.get("port"):
        typer.echo(f"Port: {svc['port']}")
    if "probe" in result:
        p = result["probe"]
        typer.echo(f"Probe: {'reachable' if p.get('reachable') else 'unreachable'}")
        if p.get("error"):
            typer.echo(f"  Error: {p['error']}")
        if p.get("latencyMs") is not None:
            typer.echo(f"  Latency: {p['latencyMs']}ms")


def gateway_probe_command(
    *,
    url: str = "",
    token: str | None = None,
    password: str | None = None,
    timeout_ms: int = 10000,
    output_json: bool = False,
) -> None:
    """Probe gateway connectivity (configured remote + localhost)."""
    gw_url = url or _default_gateway_url()
    results: list[dict[str, Any]] = []

    results.append(
        {"target": gw_url, **_probe_gateway(gw_url, token=token, password=password, timeout_s=timeout_ms / 1000)}
    )

    loopback = "ws://127.0.0.1:18789"
    if gw_url != loopback and loopback not in gw_url:
        results.append(
            {
                "target": loopback,
                **_probe_gateway(loopback, token=token, password=password, timeout_s=timeout_ms / 1000),
            }
        )

    if output_json:
        typer.echo(json.dumps({"probes": results}, ensure_ascii=False))
        return

    for probe in results:
        status = "reachable" if probe.get("reachable") else "unreachable"
        typer.echo(f"{probe['target']}: {status}")
        if probe.get("latencyMs") is not None:
            typer.echo(f"  Latency: {probe['latencyMs']}ms")
        if probe.get("error"):
            typer.echo(f"  Error: {probe['error']}")


def gateway_call_command(
    *,
    method: str,
    params_json: str = "{}",
    url: str = "",
    token: str | None = None,
    password: str | None = None,
    timeout_ms: int = 30000,
    output_json: bool = False,
) -> None:
    """Low-level RPC call to a running gateway."""
    try:
        params = json.loads(params_json)
    except json.JSONDecodeError as exc:
        typer.echo(f"Invalid JSON params: {exc}", err=True)
        raise typer.Exit(1)

    gw_url = url or _default_gateway_url()
    result = asyncio.run(
        _rpc_call(
            gw_url,
            method=method,
            params=params,
            token=token,
            password=password,
            timeout_s=timeout_ms / 1000,
        )
    )

    if output_json or isinstance(result, dict):
        typer.echo(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        typer.echo(str(result))


def gateway_discover_command(
    *,
    timeout_ms: int = 2000,
    output_json: bool = False,
) -> None:
    """Discover gateways via mDNS/Bonjour."""
    from pyclaw.gateway.discovery import (
        DiscoveredService,
        DiscoveryConfig,
        DiscoveryMethod,
        ServiceDiscoveryManager,
    )

    config = DiscoveryConfig(mdns_enabled=True, tailscale_enabled=True)
    manager = ServiceDiscoveryManager(config)

    # Attempt to discover via a quick socket scan on common local ports.
    beacons: list[dict[str, Any]] = []
    for port in (18789, 18790):
        if _port_open("127.0.0.1", port, timeout_s=timeout_ms / 1000):
            svc = DiscoveredService(
                name="local-gateway",
                host="127.0.0.1",
                port=port,
                method=DiscoveryMethod.LOCAL,
            )
            manager.add_discovered(svc)
            beacons.append(
                {
                    "name": svc.name,
                    "host": svc.host,
                    "port": svc.port,
                    "method": svc.method.value,
                    "wsUrl": f"ws://{svc.host}:{svc.port}",
                }
            )

    if output_json:
        typer.echo(json.dumps({"beacons": beacons}, ensure_ascii=False))
        return

    if not beacons:
        typer.echo("No gateways discovered.")
        return

    for b in beacons:
        typer.echo(f"  {b['name']}: {b['wsUrl']} ({b['method']})")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _default_gateway_url() -> str:
    """Resolve gateway URL from config or environment."""
    import os

    env_url = os.environ.get("PYCLAW_GATEWAY_URL", "")
    if env_url:
        return env_url

    config_path = resolve_config_path()
    if config_path.exists():
        try:
            raw = json.loads(config_path.read_text(encoding="utf-8"))
            gw = raw.get("gateway", {})
            port = gw.get("port", 18789)
            return f"ws://127.0.0.1:{port}"
        except Exception:
            pass

    return "ws://127.0.0.1:18789"


def _service_status(*, deep: bool = False) -> dict[str, Any]:
    """Check local gateway service status."""
    port = 18789
    listening = _port_open("127.0.0.1", port, timeout_s=2.0)
    result: dict[str, Any] = {
        "status": "running" if listening else "stopped",
        "port": port,
    }
    if deep:
        import sys

        result["platform"] = sys.platform
        result["python"] = sys.version.split()[0]
    return result


def _port_open(host: str, port: int, *, timeout_s: float = 2.0) -> bool:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout_s)
        result = s.connect_ex((host, port))
        s.close()
        return result == 0
    except Exception:
        return False


def _probe_gateway(
    url: str,
    *,
    token: str | None = None,
    password: str | None = None,
    timeout_s: float = 10.0,
) -> dict[str, Any]:
    """Probe a gateway via RPC health.check."""
    try:
        start = time.monotonic()
        result = asyncio.run(
            _rpc_call(url, method="health.check", params={}, token=token, password=password, timeout_s=timeout_s)
        )
        elapsed = int((time.monotonic() - start) * 1000)
        return {"reachable": True, "latencyMs": elapsed, "payload": result}
    except Exception as exc:
        return {"reachable": False, "error": str(exc)}


async def _rpc_call(
    gateway_url: str,
    *,
    method: str,
    params: dict[str, Any],
    token: str | None = None,
    password: str | None = None,
    timeout_s: float = 30.0,
) -> dict[str, Any]:
    """Make one RPC call to the gateway and return the result payload."""
    try:
        import websockets
    except ImportError as exc:
        raise RuntimeError("websockets package required: pip install websockets") from exc

    candidates = _ws_candidates(gateway_url)
    last_error: Exception | None = None

    for ws_url in candidates:
        try:
            async with websockets.connect(ws_url) as ws:
                # Handshake
                connect_msg = {
                    "type": "req",
                    "id": "gw-cli-connect",
                    "method": "connect",
                    "params": {
                        "minProtocol": 1,
                        "maxProtocol": 3,
                        "protocolVersion": 3,
                        "clientName": "pyclaw-gateway-cli",
                        "auth": {"token": token or "", "password": password or ""},
                    },
                }
                await ws.send(json.dumps(connect_msg))
                while True:
                    raw = await asyncio.wait_for(ws.recv(), timeout=timeout_s)
                    data = json.loads(raw)
                    if data.get("type") != "res":
                        continue
                    rid = str(data.get("id", ""))
                    if rid not in {"gw-cli-connect", "connect"}:
                        continue
                    if not data.get("ok", False):
                        err = data.get("error", {})
                        raise RuntimeError(err.get("message", "Gateway auth failed"))
                    break

                # RPC call
                req_id = f"gw-call-{method}"
                await ws.send(
                    json.dumps(
                        {
                            "type": "req",
                            "id": req_id,
                            "method": method,
                            "params": params,
                        }
                    )
                )
                while True:
                    raw = await asyncio.wait_for(ws.recv(), timeout=timeout_s)
                    data = json.loads(raw)
                    if data.get("type") != "res":
                        continue
                    rid = str(data.get("id", ""))
                    if rid != req_id:
                        continue
                    if not data.get("ok", False):
                        err = data.get("error", {})
                        raise RuntimeError(err.get("message", f"RPC {method} failed"))
                    return cast(dict[str, Any], data.get("payload", {}))
        except Exception as exc:
            last_error = exc
            continue

    raise last_error or RuntimeError("Unable to connect to gateway")


def _ws_candidates(url: str) -> list[str]:
    base = (url or "ws://127.0.0.1:18789").strip()
    if base.startswith("http://"):
        base = "ws://" + base[len("http://") :]
    elif base.startswith("https://"):
        base = "wss://" + base[len("https://") :]
    if not base.startswith("ws://") and not base.startswith("wss://"):
        base = f"ws://{base}"

    candidates = [base]
    if base.endswith("/ws"):
        candidates.append(base[: -len("/ws")] or "ws://127.0.0.1:18789")
    else:
        candidates.append(f"{base}/ws")
    return candidates
