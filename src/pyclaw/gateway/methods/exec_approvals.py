"""Exec approvals RPC — request, resolve, CRUD for exec approval requests.

Ported from ``src/gateway/method-handlers/exec-approvals.ts``.

Provides:
- exec.approve / exec.deny — resolve pending approval requests
- exec.list / exec.get — list and inspect pending requests
- exec.create — programmatic approval request creation
- exec.update — modify pending request (timeout, metadata)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pyclaw.gateway.server import GatewayConnection, MethodHandler

logger = logging.getLogger(__name__)


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


@dataclass
class ApprovalRequest:
    """An exec approval request."""

    request_id: str
    command: str
    args: list[str] = field(default_factory=list)
    working_dir: str = ""
    session_id: str = ""
    agent_id: str = ""
    status: ApprovalStatus = ApprovalStatus.PENDING
    created_at: float = 0.0
    resolved_at: float = 0.0
    timeout_s: float = 300.0
    risk_level: str = "medium"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.created_at == 0:
            self.created_at = time.time()

    @property
    def is_expired(self) -> bool:
        if self.status != ApprovalStatus.PENDING:
            return False
        return (time.time() - self.created_at) > self.timeout_s

    @property
    def is_pending(self) -> bool:
        return self.status == ApprovalStatus.PENDING and not self.is_expired

    def to_dict(self) -> dict[str, Any]:
        return {
            "requestId": self.request_id,
            "command": self.command,
            "args": self.args,
            "workingDir": self.working_dir,
            "sessionId": self.session_id,
            "agentId": self.agent_id,
            "status": self.status.value,
            "createdAt": self.created_at,
            "resolvedAt": self.resolved_at,
            "timeoutS": self.timeout_s,
            "riskLevel": self.risk_level,
        }


class ApprovalStore:
    """In-memory store for exec approval requests."""

    def __init__(self) -> None:
        self._requests: dict[str, ApprovalRequest] = {}
        self._counter = 0

    def create(
        self,
        command: str,
        *,
        args: list[str] | None = None,
        session_id: str = "",
        agent_id: str = "",
        working_dir: str = "",
        timeout_s: float = 300.0,
        risk_level: str = "medium",
    ) -> ApprovalRequest:
        self._counter += 1
        req = ApprovalRequest(
            request_id=f"exec-{self._counter}",
            command=command,
            args=args or [],
            session_id=session_id,
            agent_id=agent_id,
            working_dir=working_dir,
            timeout_s=timeout_s,
            risk_level=risk_level,
        )
        self._requests[req.request_id] = req
        return req

    def get(self, request_id: str) -> ApprovalRequest | None:
        req = self._requests.get(request_id)
        if req and req.is_expired:
            req.status = ApprovalStatus.EXPIRED
        return req

    def resolve(self, request_id: str, approved: bool) -> ApprovalRequest | None:
        req = self._requests.get(request_id)
        if not req:
            return None
        if req.is_expired:
            req.status = ApprovalStatus.EXPIRED
            return req
        if req.status != ApprovalStatus.PENDING:
            return req

        req.status = ApprovalStatus.APPROVED if approved else ApprovalStatus.DENIED
        req.resolved_at = time.time()
        return req

    def list_pending(self) -> list[ApprovalRequest]:
        result: list[ApprovalRequest] = []
        for req in self._requests.values():
            if req.is_expired and req.status == ApprovalStatus.PENDING:
                req.status = ApprovalStatus.EXPIRED
            if req.status == ApprovalStatus.PENDING:
                result.append(req)
        return result

    def list_all(self) -> list[ApprovalRequest]:
        for req in self._requests.values():
            if req.is_expired and req.status == ApprovalStatus.PENDING:
                req.status = ApprovalStatus.EXPIRED
        return list(self._requests.values())

    def cancel(self, request_id: str) -> bool:
        req = self._requests.get(request_id)
        if req and req.status == ApprovalStatus.PENDING:
            req.status = ApprovalStatus.CANCELLED
            req.resolved_at = time.time()
            return True
        return False

    def cleanup_expired(self) -> int:
        expired = [
            rid
            for rid, req in self._requests.items()
            if req.is_expired or req.status in (ApprovalStatus.EXPIRED, ApprovalStatus.CANCELLED)
        ]
        for rid in expired:
            self._requests.pop(rid, None)
        return len(expired)

    @property
    def pending_count(self) -> int:
        return len(self.list_pending())


# Singleton store
_store = ApprovalStore()


def create_exec_approval_handlers() -> dict[str, MethodHandler]:
    async def handle_exec_list(params: dict[str, Any] | None, conn: GatewayConnection) -> None:
        show_all = (params or {}).get("all", False)
        requests = _store.list_all() if show_all else _store.list_pending()
        await conn.send_ok(
            "exec.list",
            {
                "requests": [r.to_dict() for r in requests],
                "count": len(requests),
            },
        )

    async def handle_exec_get(params: dict[str, Any] | None, conn: GatewayConnection) -> None:
        request_id = (params or {}).get("requestId", "")
        if not request_id:
            await conn.send_error("exec.get", "invalid_params", "Missing requestId")
            return
        req = _store.get(request_id)
        if not req:
            await conn.send_error("exec.get", "not_found", f"Request {request_id} not found")
            return
        await conn.send_ok("exec.get", {"request": req.to_dict()})

    async def handle_exec_approve(params: dict[str, Any] | None, conn: GatewayConnection) -> None:
        request_id = (params or {}).get("requestId", "")
        if not request_id:
            await conn.send_error("exec.approve", "invalid_params", "Missing requestId")
            return
        req = _store.resolve(request_id, True)
        if not req:
            await conn.send_error("exec.approve", "not_found", "Request not found")
            return
        await conn.send_ok("exec.approve", {"request": req.to_dict()})

    async def handle_exec_deny(params: dict[str, Any] | None, conn: GatewayConnection) -> None:
        request_id = (params or {}).get("requestId", "")
        if not request_id:
            await conn.send_error("exec.deny", "invalid_params", "Missing requestId")
            return
        req = _store.resolve(request_id, False)
        if not req:
            await conn.send_error("exec.deny", "not_found", "Request not found")
            return
        await conn.send_ok("exec.deny", {"request": req.to_dict()})

    async def handle_exec_create(params: dict[str, Any] | None, conn: GatewayConnection) -> None:
        command = (params or {}).get("command", "")
        if not command:
            await conn.send_error("exec.create", "invalid_params", "Missing command")
            return
        req = _store.create(
            command,
            args=(params or {}).get("args", []),
            session_id=(params or {}).get("sessionId", ""),
            agent_id=(params or {}).get("agentId", ""),
            working_dir=(params or {}).get("workingDir", ""),
        )
        await conn.send_ok("exec.create", {"request": req.to_dict()})

    return {
        "exec.list": handle_exec_list,
        "exec.get": handle_exec_get,
        "exec.approve": handle_exec_approve,
        "exec.deny": handle_exec_deny,
        "exec.create": handle_exec_create,
    }
