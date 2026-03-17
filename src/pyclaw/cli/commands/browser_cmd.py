"""CLI browser command surface — Gateway RPC backed implementation."""

from __future__ import annotations

import asyncio
import base64
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import typer

from pyclaw.constants.runtime import DEFAULT_GATEWAY_WS_URL, STATUS_RUNNING, STATUS_STOPPED
from pyclaw.constants.storage import BROWSER_PROFILES_DIRNAME


def browser_status_command(
    *,
    profile: str,
    output_json: bool,
    gateway_url: str,
    token: str | None,
    password: str | None,
    timeout_ms: int,
) -> None:
    payload = _browser_rpc_sync(
        "browser.status",
        {"profile": profile},
        gateway_url=gateway_url,
        token=token,
        password=password,
        timeout_ms=timeout_ms,
    )
    _emit(payload, output_json=output_json, text=_format_status(payload))


def browser_start_command(
    *,
    profile: str,
    output_json: bool,
    gateway_url: str,
    token: str | None,
    password: str | None,
    timeout_ms: int,
) -> None:
    payload = _browser_rpc_sync(
        "browser.start",
        {"profile": profile},
        gateway_url=gateway_url,
        token=token,
        password=password,
        timeout_ms=timeout_ms,
    )
    _emit(payload, output_json=output_json, text=f"Started profile {profile}")


def browser_stop_command(
    *,
    profile: str,
    output_json: bool,
    gateway_url: str,
    token: str | None,
    password: str | None,
    timeout_ms: int,
) -> None:
    payload = _browser_rpc_sync(
        "browser.stop",
        {"profile": profile},
        gateway_url=gateway_url,
        token=token,
        password=password,
        timeout_ms=timeout_ms,
    )
    _emit(payload, output_json=output_json, text=f"Stopped profile {profile}")


def browser_tabs_command(
    *,
    profile: str,
    output_json: bool,
    gateway_url: str,
    token: str | None,
    password: str | None,
    timeout_ms: int,
) -> None:
    payload = _browser_rpc_sync(
        "browser.tabs",
        {"profile": profile},
        gateway_url=gateway_url,
        token=token,
        password=password,
        timeout_ms=timeout_ms,
    )
    if output_json:
        typer.echo(json.dumps(payload, ensure_ascii=False))
        return
    tabs = payload.get("tabs", [])
    if not tabs:
        typer.echo("No tabs.")
        return
    for tab in tabs:
        mark = "*" if tab.get("active") else " "
        typer.echo(f"{mark} [{tab.get('id', '')}] {tab.get('url', '')}")


def browser_open_command(
    *,
    url: str,
    profile: str,
    output_json: bool,
    gateway_url: str,
    token: str | None,
    password: str | None,
    timeout_ms: int,
) -> None:
    payload = _browser_rpc_sync(
        "browser.open",
        {"profile": profile, "url": url},
        gateway_url=gateway_url,
        token=token,
        password=password,
        timeout_ms=timeout_ms,
    )
    _emit(payload, output_json=output_json, text=f"Opened {url}")


def browser_navigate_command(
    *,
    url: str,
    profile: str,
    output_json: bool,
    gateway_url: str,
    token: str | None,
    password: str | None,
    timeout_ms: int,
) -> None:
    payload = _browser_rpc_sync(
        "browser.navigate",
        {"profile": profile, "url": url},
        gateway_url=gateway_url,
        token=token,
        password=password,
        timeout_ms=timeout_ms,
    )
    _emit(payload, output_json=output_json, text=f"Navigated to {url}")


def browser_click_command(
    *,
    ref: str,
    profile: str,
    output_json: bool,
    gateway_url: str,
    token: str | None,
    password: str | None,
    timeout_ms: int,
) -> None:
    payload = _browser_rpc_sync(
        "browser.click",
        {"profile": profile, "ref": ref},
        gateway_url=gateway_url,
        token=token,
        password=password,
        timeout_ms=timeout_ms,
    )
    _emit(payload, output_json=output_json, text=f"Clicked {ref}")


def browser_type_command(
    *,
    ref: str,
    text: str,
    profile: str,
    output_json: bool,
    gateway_url: str,
    token: str | None,
    password: str | None,
    timeout_ms: int,
) -> None:
    payload = _browser_rpc_sync(
        "browser.type",
        {"profile": profile, "ref": ref, "text": text},
        gateway_url=gateway_url,
        token=token,
        password=password,
        timeout_ms=timeout_ms,
    )
    _emit(payload, output_json=output_json, text=f"Typed into {ref}")


def browser_screenshot_command(
    *,
    profile: str,
    output_json: bool,
    out: str,
    gateway_url: str,
    token: str | None,
    password: str | None,
    timeout_ms: int,
) -> None:
    payload = _browser_rpc_sync(
        "browser.screenshot",
        {"profile": profile, "fullPage": True},
        gateway_url=gateway_url,
        token=token,
        password=password,
        timeout_ms=timeout_ms,
    )
    screenshot_b64 = payload.get("screenshotB64", "")
    target = Path(out).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(screenshot_b64, str) and screenshot_b64:
        target.write_bytes(base64.b64decode(screenshot_b64))
    else:
        target.write_bytes(b"")
    payload["path"] = str(target)
    _emit(payload, output_json=output_json, text=str(target))


def browser_snapshot_command(
    *,
    profile: str,
    output_json: bool,
    gateway_url: str,
    token: str | None,
    password: str | None,
    timeout_ms: int,
) -> None:
    payload = _browser_rpc_sync(
        "browser.snapshot",
        {"profile": profile},
        gateway_url=gateway_url,
        token=token,
        password=password,
        timeout_ms=timeout_ms,
    )
    _emit(payload, output_json=output_json, text="Snapshot captured.")


def browser_evaluate_command(
    *,
    fn: str,
    profile: str,
    output_json: bool,
    gateway_url: str,
    token: str | None,
    password: str | None,
    timeout_ms: int,
) -> None:
    payload = _browser_rpc_sync(
        "browser.evaluate",
        {"profile": profile, "fn": fn},
        gateway_url=gateway_url,
        token=token,
        password=password,
        timeout_ms=timeout_ms,
    )
    _emit(payload, output_json=output_json, text=f"Evaluate result: {payload.get('result')}")


def browser_profiles_command(
    *,
    output_json: bool,
    gateway_url: str,
    token: str | None,
    password: str | None,
    timeout_ms: int,
) -> None:
    payload = _browser_rpc_sync(
        "browser.profiles",
        {},
        gateway_url=gateway_url,
        token=token,
        password=password,
        timeout_ms=timeout_ms,
    )
    profiles = payload.get("profiles", [])
    if output_json:
        _emit(payload, output_json=True, text="")
        return
    if not profiles:
        typer.echo("No browser profiles found.")
        return
    for p in profiles:
        name = p if isinstance(p, str) else p.get("name", "?")
        typer.echo(f"  {name}")


def browser_create_profile_command(
    *,
    name: str,
    output_json: bool,
    gateway_url: str,
    token: str | None,
    password: str | None,
    timeout_ms: int,
) -> None:
    payload = _browser_rpc_sync(
        "browser.createProfile",
        {"name": name},
        gateway_url=gateway_url,
        token=token,
        password=password,
        timeout_ms=timeout_ms,
    )
    _emit(payload, output_json=output_json, text=f"Profile '{name}' created.")


def browser_delete_profile_command(
    *,
    name: str,
    output_json: bool,
    gateway_url: str,
    token: str | None,
    password: str | None,
    timeout_ms: int,
) -> None:
    payload = _browser_rpc_sync(
        "browser.deleteProfile",
        {"name": name},
        gateway_url=gateway_url,
        token=token,
        password=password,
        timeout_ms=timeout_ms,
    )
    _emit(payload, output_json=output_json, text=f"Profile '{name}' deleted.")


def browser_lifecycle_audit_command(*, output_json: bool) -> None:
    """Audit browser profile lifecycle metadata from local persisted profiles."""
    from pyclaw.config.paths import resolve_state_dir

    profiles_dir = resolve_state_dir() / BROWSER_PROFILES_DIRNAME
    rows: list[dict[str, Any]] = []
    for item in sorted(profiles_dir.glob("*.json")):
        stat = item.stat()
        rows.append(
            {
                "profile": item.stem,
                "path": str(item),
                "size": stat.st_size,
                "modifiedAt": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
            }
        )

    payload = {
        "profilesDir": str(profiles_dir),
        "count": len(rows),
        "profiles": rows,
    }
    if output_json:
        _emit(payload, output_json=True, text="")
        return
    if not rows:
        typer.echo(f"No browser profile snapshots found in {profiles_dir}")
        return
    typer.echo(f"Browser profile lifecycle audit ({len(rows)}):")
    for row in rows:
        typer.echo(f"- {row['profile']} size={row['size']} modified={row['modifiedAt']}")


def browser_focus_command(
    *,
    tab_id: str,
    profile: str,
    output_json: bool,
    gateway_url: str,
    token: str | None,
    password: str | None,
    timeout_ms: int,
) -> None:
    payload = _browser_rpc_sync(
        "browser.focus",
        {"profile": profile, "tabId": tab_id},
        gateway_url=gateway_url,
        token=token,
        password=password,
        timeout_ms=timeout_ms,
    )
    _emit(payload, output_json=output_json, text=f"Focused tab {tab_id}")


def browser_close_command(
    *,
    tab_id: str,
    profile: str,
    output_json: bool,
    gateway_url: str,
    token: str | None,
    password: str | None,
    timeout_ms: int,
) -> None:
    payload = _browser_rpc_sync(
        "browser.close",
        {"profile": profile, "tabId": tab_id},
        gateway_url=gateway_url,
        token=token,
        password=password,
        timeout_ms=timeout_ms,
    )
    _emit(payload, output_json=output_json, text=f"Closed tab {tab_id}")


def _format_status(payload: dict[str, Any]) -> str:
    started = STATUS_RUNNING if payload.get("started") else STATUS_STOPPED
    profile = payload.get("profile", "pyclaw")
    tab_count = payload.get("tabCount", 0)
    active_url = payload.get("activeUrl", "")
    return f"Browser {started} [{profile}] tabs={tab_count} active={active_url}"


def _emit(payload: dict[str, Any], *, output_json: bool, text: str) -> None:
    if output_json:
        typer.echo(json.dumps(payload, ensure_ascii=False))
    else:
        typer.echo(text)


def _browser_rpc_sync(
    method: str,
    params: dict[str, Any],
    *,
    gateway_url: str,
    token: str | None,
    password: str | None,
    timeout_ms: int,
) -> dict[str, Any]:
    return asyncio.run(
        _browser_rpc(
            method,
            params,
            gateway_url=gateway_url,
            token=token,
            password=password,
            timeout_ms=timeout_ms,
        )
    )


async def _browser_rpc(
    method: str,
    params: dict[str, Any],
    *,
    gateway_url: str,
    token: str | None,
    password: str | None,
    timeout_ms: int,
) -> dict[str, Any]:
    try:
        import websockets
    except ImportError as exc:
        raise RuntimeError("websockets package required") from exc

    timeout_s = max(timeout_ms, 100) / 1000.0
    errors: list[Exception] = []

    for url in _ws_candidates(gateway_url):
        try:
            async with websockets.connect(url, open_timeout=timeout_s) as ws:
                await _connect(ws, token=token, password=password, timeout_s=timeout_s)
                req_id = "browser-cli-request"
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
                    response_id = str(data.get("id", ""))
                    if response_id not in {req_id, method}:
                        continue
                    if not data.get("ok", False):
                        error = data.get("error", {})
                        message = error.get("message", "Gateway error")
                        raise RuntimeError(str(message))
                    payload = data.get("payload", {})
                    return payload if isinstance(payload, dict) else {"payload": payload}
        except Exception as exc:  # pragma: no cover - multi-url fallback
            errors.append(exc)
            continue

    if errors:
        raise RuntimeError(str(errors[-1]))
    raise RuntimeError("Unable to connect to gateway")


async def _connect(
    ws: Any,
    *,
    token: str | None,
    password: str | None,
    timeout_s: float,
) -> None:
    await ws.send(
        json.dumps(
            {
                "type": "req",
                "id": "browser-cli-connect",
                "method": "connect",
                "params": {
                    "minProtocol": 1,
                    "maxProtocol": 3,
                    "protocolVersion": 3,
                    "clientName": "pyclaw-browser-cli",
                    "auth": {"token": token or "", "password": password or ""},
                },
            }
        )
    )
    # Server may return id "connect" instead of request id.
    while True:
        raw = await asyncio.wait_for(ws.recv(), timeout=timeout_s)
        data = json.loads(raw)
        if data.get("type") != "res":
            continue
        response_id = str(data.get("id", ""))
        if response_id not in {"browser-cli-connect", "connect"}:
            continue
        if not data.get("ok", False):
            error = data.get("error", {})
            raise RuntimeError(error.get("message", "Gateway connect/auth failed"))
        return


def _ws_candidates(url: str) -> list[str]:
    base = (url or DEFAULT_GATEWAY_WS_URL).strip()
    if base.startswith("http://"):
        base = "ws://" + base[len("http://") :]
    elif base.startswith("https://"):
        base = "wss://" + base[len("https://") :]
    if not base.startswith("ws://") and not base.startswith("wss://"):
        base = f"ws://{base}"

    candidates = [base]
    if base.endswith("/ws"):
        candidates.append(base[: -len("/ws")] or DEFAULT_GATEWAY_WS_URL)
    else:
        candidates.append(base.rstrip("/") + "/ws")
    # de-duplicate while preserving order
    seen: set[str] = set()
    result: list[str] = []
    for item in candidates:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result
