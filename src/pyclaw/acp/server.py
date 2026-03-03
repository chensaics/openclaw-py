"""ACP server — NDJSON stdio bridge to gateway WebSocket."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import re
import sys
import uuid
from pathlib import Path
from typing import Any

from pyclaw.acp.event_mapper import extract_text_from_prompt
from pyclaw.acp.session import create_in_memory_session_store
from pyclaw.acp.session_mapper import parse_session_meta
from pyclaw.acp.session_mapper import resolve_session_key
from pyclaw.acp.session_mapper import SessionLabelMap
from pyclaw.acp.types import AcpAgentInfo
from pyclaw.acp.types import AcpSessionMeta
from pyclaw.config.paths import resolve_state_dir

logger = logging.getLogger(__name__)


class AcpGatewayAgent:
    """Translates ACP protocol to gateway WebSocket calls."""

    def __init__(
        self,
        *,
        gateway_url: str = "ws://127.0.0.1:18789/ws",
        auth_token: str | None = None,
        auth_password: str | None = None,
        default_session_key: str = "",
        default_session_label: str = "",
        require_existing_session: bool = False,
        reset_session_default: bool = False,
        prefix_cwd: bool = True,
        verbose: bool = False,
        dispatch_enabled: bool = True,
    ) -> None:
        self._gateway_url = gateway_url
        self._auth_token = auth_token
        self._auth_password = auth_password
        self._default_session_key = default_session_key
        self._default_session_label = default_session_label
        self._require_existing_session = require_existing_session
        self._reset_session_default = reset_session_default
        self._prefix_cwd = prefix_cwd
        self._verbose = verbose
        self._dispatch_enabled = dispatch_enabled

        self._store = create_in_memory_session_store()
        self._ws: Any = None
        self._agent_info = AcpAgentInfo()
        self._request_id = 10
        self._label_map = SessionLabelMap(resolve_state_dir() / "acp" / "session-map.json")

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    def _debug(self, message: str) -> None:
        if self._verbose:
            logger.info("[acp] %s", message)

    async def initialize(self) -> dict[str, Any]:
        return {
            "name": self._agent_info.name,
            "version": self._agent_info.version,
            "capabilities": self._agent_info.capabilities,
        }

    async def new_session(self, params: dict[str, Any]) -> dict[str, Any]:
        agent_id = params.get("agentId", "main")
        if not re.match(r"^[a-zA-Z0-9_-]+$", agent_id):
            raise ValueError(
                f"Invalid agentId format: {agent_id!r}. "
                "Must match ^[a-zA-Z0-9_-]+$ (alphanumeric, dash, underscore)."
            )

        session_id = params.get("sessionId", str(uuid.uuid4()))
        hints = parse_session_meta(params.get("_meta"))

        fallback_key = self._label_map.resolve_session(session_id) or f"acp:{session_id}"
        try:
            resolved_key = await resolve_session_key(
                meta=hints,
                fallback_key=fallback_key,
                gateway_request=self._gateway_request,
                default_session_key=self._default_session_key or None,
                default_session_label=self._default_session_label or None,
                require_existing_session=self._require_existing_session,
            )
        except ValueError:
            if hints.require_existing or self._require_existing_session:
                raise
            resolved_key = hints.session_key or self._default_session_key or fallback_key

        should_reset = hints.reset_session or self._reset_session_default
        if should_reset:
            await self._reset_session_by_key(resolved_key)
            self._label_map.reset_session(session_id)

        label = hints.session_label or self._default_session_label
        meta = AcpSessionMeta(
            session_id=session_id,
            session_key=resolved_key,
            session_label=label,
            cwd=hints.cwd or "",
            agent_id=agent_id,
            mode=params.get("mode", "agent"),
        )
        self._store.create_session(session_id, meta)
        self._label_map.bind(session_id=session_id, session_key=resolved_key, session_label=label or None)

        return {"sessionId": session_id, "sessionKey": resolved_key, "sessionLabel": label or None}

    async def load_session(self, params: dict[str, Any]) -> dict[str, Any]:
        session_id = params.get("sessionId", "")
        session = self._store.get_session(session_id)
        if not session:
            return {"error": "Session not found"}
        return {
            "sessionId": session_id,
            "sessionKey": session.meta.session_key,
            "sessionLabel": session.meta.session_label or None,
            "messages": session.messages,
        }

    async def list_sessions(self) -> list[dict[str, Any]]:
        return [
            {
                "sessionId": s.meta.session_id,
                "sessionKey": s.meta.session_key,
                "sessionLabel": s.meta.session_label or None,
                "agentId": s.meta.agent_id,
            }
            for s in self._store.list_sessions()
        ]

    async def prompt(self, params: dict[str, Any]) -> None:
        """Forward a prompt to the gateway."""
        session_id = params.get("sessionId", "")
        if not session_id:
            return
        session = self._store.get_session(session_id)
        if not session:
            return

        text = extract_text_from_prompt(params.get("text") or params.get("prompt") or "")
        if not text:
            return

        # Gateway currently keys chat sessions by `sessionId`; ACP maps labels/keys to it.
        chat_session_id = session.meta.session_key or session_id
        _meta = params.get("_meta")
        meta: dict[str, Any] = _meta if isinstance(_meta, dict) else {}
        prefix_override = meta.get("prefixCwd")
        prefix_enabled = (
            bool(prefix_override) if isinstance(prefix_override, bool) else self._prefix_cwd
        )
        cwd = str(meta.get("cwd") or session.meta.cwd or "").strip()
        if prefix_enabled and cwd:
            text = f"[cwd:{cwd}] {text}"

        if self._ws:
            msg = {
                "id": self._next_id(),
                "method": "chat.send",
                "params": {"message": text, "sessionId": chat_session_id},
            }
            await self._ws.send(json.dumps(msg))

    async def cancel(self, params: dict[str, Any]) -> None:
        session_id = params.get("sessionId", "")
        session = self._store.get_session(session_id)
        if not session or not self._ws:
            return
        run_id = self._store.cancel_active_run(session_id)
        if run_id is not None:
            msg = {
                "id": self._next_id(),
                "method": "chat.abort",
                "params": {"sessionId": session.meta.session_key or session_id},
            }
            await self._ws.send(json.dumps(msg))

    async def connect_gateway(self) -> None:
        """Connect to the gateway WebSocket."""
        try:
            import websockets
        except ImportError:
            logger.error("websockets required for ACP server")
            return

        self._ws = await websockets.connect(self._gateway_url)

        connect_msg: dict[str, Any] = {
            "id": self._next_id(),
            "method": "connect",
            "params": {"protocolVersion": 3, "clientName": "acp-bridge"},
        }
        if self._auth_token:
            connect_msg["params"]["token"] = self._auth_token
        if self._auth_password:
            connect_msg["params"]["password"] = self._auth_password
        await self._ws.send(json.dumps(connect_msg))
        response = json.loads(await self._ws.recv())
        if response.get("error"):
            raise RuntimeError(f"Gateway auth failed: {response.get('error')}")

    async def disconnect_gateway(self) -> None:
        if self._ws:
            await self._ws.close()
            self._ws = None

    async def _gateway_request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        if method == "sessions.resolve":
            label = params.get("label")
            if isinstance(label, str) and label:
                key = self._label_map.resolve_label(label)
                return {"key": key} if key else {}

            key = params.get("key")
            if isinstance(key, str) and key:
                if self._label_map.is_known_key(key):
                    return {"key": key}
                if await self._gateway_has_session_key(key):
                    return {"key": key}
            return {}

        if method == "sessions.reset":
            key = params.get("key")
            if isinstance(key, str) and key:
                await self._reset_session_by_key(key)
                return {"ok": True}
            return {}

        result = await self._request_gateway(method, params)
        return result if isinstance(result, dict) else {}

    async def _gateway_has_session_key(self, key: str) -> bool:
        try:
            result = await self._request_gateway("sessions.list", {})
        except Exception:
            return False
        sessions = result.get("sessions", []) if isinstance(result, dict) else []
        for entry in sessions:
            if not isinstance(entry, dict):
                continue
            if entry.get("file") == f"{key}.jsonl":
                return True
            path = str(entry.get("path", ""))
            if path.endswith(f"/{key}.jsonl"):
                return True
        return False

    async def _reset_session_by_key(self, key: str) -> None:
        try:
            result = await self._request_gateway("sessions.list", {})
        except Exception:
            return
        sessions = result.get("sessions", []) if isinstance(result, dict) else []
        for entry in sessions:
            if not isinstance(entry, dict):
                continue
            if entry.get("file") == f"{key}.jsonl":
                path = entry.get("path")
                if isinstance(path, str) and path:
                    await self._request_gateway("sessions.reset", {"path": path})
                return

    async def _request_gateway(self, method: str, params: dict[str, Any]) -> Any:
        if not self._ws:
            raise RuntimeError("Gateway not connected")

        req_id = self._next_id()
        msg = {"id": req_id, "method": method, "params": params}
        await self._ws.send(json.dumps(msg))

        # Note: we do not run a dedicated event reader yet; this waits for matching id.
        while True:
            raw = await self._ws.recv()
            payload = json.loads(raw)
            if payload.get("id") != req_id:
                continue
            if payload.get("error"):
                raise RuntimeError(str(payload["error"]))
            return payload.get("result")


async def serve_acp_gateway(
    *,
    gateway_url: str = "ws://127.0.0.1:18789/ws",
    auth_token: str | None = None,
    auth_password: str | None = None,
    default_session_key: str = "",
    default_session_label: str = "",
    require_existing_session: bool = False,
    reset_session_default: bool = False,
    prefix_cwd: bool = True,
    verbose: bool = False,
    dispatch_enabled: bool = True,
) -> None:
    """Main entry — read NDJSON from stdin, bridge to gateway."""
    agent = AcpGatewayAgent(
        gateway_url=gateway_url,
        auth_token=auth_token,
        auth_password=auth_password,
        default_session_key=default_session_key,
        default_session_label=default_session_label,
        require_existing_session=require_existing_session,
        reset_session_default=reset_session_default,
        prefix_cwd=prefix_cwd,
        verbose=verbose,
        dispatch_enabled=dispatch_enabled,
    )

    try:
        await agent.connect_gateway()
    except Exception:
        logger.error("Failed to connect to gateway at %s", gateway_url)
        return

    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await asyncio.get_event_loop().connect_read_pipe(lambda: protocol, sys.stdin)

    try:
        while True:
            line = await reader.readline()
            if not line:
                break
            line_str = line.decode("utf-8").strip()
            if not line_str:
                continue

            try:
                data = json.loads(line_str)
            except json.JSONDecodeError:
                continue

            method = data.get("method", "")
            req_id = data.get("id", 0)
            params = data.get("params", {})

            result: Any = None
            error: dict[str, Any] | None = None

            try:
                if method == "initialize":
                    result = await agent.initialize()
                elif method == "newSession":
                    result = await agent.new_session(params)
                elif method == "loadSession":
                    result = await agent.load_session(params)
                elif method == "unstable_listSessions":
                    result = await agent.list_sessions()
                elif method == "prompt":
                    await agent.prompt(params)
                    result = {"ok": True}
                elif method == "cancel":
                    await agent.cancel(params)
                    result = {"ok": True}
                else:
                    error = {"code": -32601, "message": f"Unknown method: {method}"}
            except Exception as exc:
                error = {"code": -32000, "message": str(exc)}

            response = {"jsonrpc": "2.0", "id": req_id}
            if error:
                response["error"] = error
            else:
                response["result"] = result

            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()

    except asyncio.CancelledError:
        pass
    finally:
        await agent.disconnect_gateway()


def _read_file_secret(path: str) -> str:
    """Read a secret value from a file, stripping trailing whitespace."""
    return Path(path).read_text().rstrip()


def _parse_cli_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m pyclaw.acp.server")
    parser.add_argument("--gateway-url", default="ws://127.0.0.1:18789/ws")
    parser.add_argument("--auth-token", default="")
    parser.add_argument("--auth-password", default="")
    parser.add_argument("--token-file", default="", help="Read auth token from file (overrides --auth-token)")
    parser.add_argument("--password-file", default="", help="Read auth password from file (overrides --auth-password)")
    parser.add_argument("--session", default="")
    parser.add_argument("--session-label", default="")
    parser.add_argument("--require-existing-session", action="store_true")
    parser.add_argument("--reset-session", action="store_true")
    parser.add_argument("--no-prefix-cwd", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_cli_args(argv or sys.argv[1:])
    if args.verbose:
        logging.basicConfig(level=logging.INFO)

    token = args.auth_token
    password = args.auth_password
    if args.token_file:
        token = _read_file_secret(args.token_file)
    if args.password_file:
        password = _read_file_secret(args.password_file)

    asyncio.run(
        serve_acp_gateway(
            gateway_url=args.gateway_url,
            auth_token=token or None,
            auth_password=password or None,
            default_session_key=args.session,
            default_session_label=args.session_label,
            require_existing_session=args.require_existing_session,
            reset_session_default=args.reset_session,
            prefix_cwd=not args.no_prefix_cwd,
            verbose=args.verbose,
        )
    )


if __name__ == "__main__":
    main()
