"""Exec approval system — allowlist, interactive ask, and node forwarding.

Ported from ``src/infra/exec-approvals.ts``.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from pyclaw.config.paths import resolve_state_dir

logger = logging.getLogger(__name__)

ExecHost = Literal["sandbox", "gateway", "node"]
ExecSecurity = Literal["deny", "allowlist", "full"]
ExecAsk = Literal["off", "on-miss", "always"]
ExecApprovalDecision = Literal["allow-once", "allow-always", "deny"]

APPROVALS_FILENAME = "exec-approvals.json"
APPROVALS_SOCKET = "exec-approvals.sock"


@dataclass
class ExecAllowlistEntry:
    pattern: str
    last_used_at: str | None = None
    last_used_command: str | None = None
    last_resolved_path: str | None = None


@dataclass
class AgentExecConfig:
    security: ExecSecurity = "allowlist"
    ask: ExecAsk = "on-miss"
    allowlist: list[ExecAllowlistEntry] = field(default_factory=list)


@dataclass
class ExecApprovalsFile:
    version: int = 1
    defaults: AgentExecConfig | None = None
    agents: dict[str, AgentExecConfig] = field(default_factory=dict)


def _approvals_path(state_dir: Path | None = None) -> Path:
    sd = state_dir or resolve_state_dir()
    return sd / APPROVALS_FILENAME


def load_exec_approvals(state_dir: Path | None = None) -> ExecApprovalsFile:
    path = _approvals_path(state_dir)
    if not path.exists():
        return ExecApprovalsFile()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return _parse_approvals(data)
    except Exception:
        logger.warning("Failed to load exec approvals from %s", path)
        return ExecApprovalsFile()


def _parse_approvals(data: dict[str, Any]) -> ExecApprovalsFile:
    result = ExecApprovalsFile(version=data.get("version", 1))
    if defaults := data.get("defaults"):
        result.defaults = _parse_agent_config(defaults)
    for agent_id, cfg in data.get("agents", {}).items():
        result.agents[agent_id] = _parse_agent_config(cfg)
    return result


def _parse_agent_config(data: dict[str, Any]) -> AgentExecConfig:
    cfg = AgentExecConfig(
        security=data.get("security", "allowlist"),
        ask=data.get("ask", "on-miss"),
    )
    for entry in data.get("allowlist", []):
        if isinstance(entry, dict):
            cfg.allowlist.append(ExecAllowlistEntry(
                pattern=entry.get("pattern", ""),
                last_used_at=entry.get("lastUsedAt"),
                last_used_command=entry.get("lastUsedCommand"),
                last_resolved_path=entry.get("lastResolvedPath"),
            ))
        elif isinstance(entry, str):
            cfg.allowlist.append(ExecAllowlistEntry(pattern=entry))
    return cfg


def save_exec_approvals(approvals: ExecApprovalsFile, state_dir: Path | None = None) -> None:
    path = _approvals_path(state_dir)
    path.parent.mkdir(parents=True, exist_ok=True)

    data: dict[str, Any] = {"version": approvals.version}
    if approvals.defaults:
        data["defaults"] = _serialize_agent_config(approvals.defaults)
    if approvals.agents:
        data["agents"] = {k: _serialize_agent_config(v) for k, v in approvals.agents.items()}
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _serialize_agent_config(cfg: AgentExecConfig) -> dict[str, Any]:
    return {
        "security": cfg.security,
        "ask": cfg.ask,
        "allowlist": [
            {
                "pattern": e.pattern,
                **({"lastUsedAt": e.last_used_at} if e.last_used_at else {}),
                **({"lastUsedCommand": e.last_used_command} if e.last_used_command else {}),
                **({"lastResolvedPath": e.last_resolved_path} if e.last_resolved_path else {}),
            }
            for e in cfg.allowlist
        ],
    }


def resolve_exec_config(
    agent_id: str | None,
    approvals: ExecApprovalsFile | None = None,
    state_dir: Path | None = None,
) -> AgentExecConfig:
    """Resolve the exec config for a given agent, falling back to defaults."""
    if approvals is None:
        approvals = load_exec_approvals(state_dir)
    if agent_id and agent_id in approvals.agents:
        return approvals.agents[agent_id]
    return approvals.defaults or AgentExecConfig()


def check_allowlist(command: str, allowlist: list[ExecAllowlistEntry]) -> ExecAllowlistEntry | None:
    """Check if *command* matches any allowlist entry pattern."""
    for entry in allowlist:
        pattern = entry.pattern
        try:
            if re.match(pattern, command):
                return entry
        except re.error:
            if pattern in command or command.startswith(pattern):
                return entry
    return None


def requires_exec_approval(
    command: str,
    config: AgentExecConfig,
) -> bool:
    """Return True if *command* requires interactive approval."""
    if config.security == "deny":
        return True
    if config.security == "full":
        return config.ask == "always"
    # allowlist mode
    matched = check_allowlist(command, config.allowlist)
    if matched:
        return config.ask == "always"
    return config.ask != "off"


def add_allowlist_entry(
    agent_id: str,
    pattern: str,
    command: str | None = None,
    state_dir: Path | None = None,
) -> None:
    """Add a new allowlist entry for an agent."""
    approvals = load_exec_approvals(state_dir)
    cfg = approvals.agents.get(agent_id)
    if cfg is None:
        cfg = AgentExecConfig()
        approvals.agents[agent_id] = cfg
    cfg.allowlist.append(ExecAllowlistEntry(
        pattern=pattern,
        last_used_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        last_used_command=command,
    ))
    save_exec_approvals(approvals, state_dir)


def record_allowlist_use(
    agent_id: str,
    entry: ExecAllowlistEntry,
    command: str,
    state_dir: Path | None = None,
) -> None:
    """Update last-used metadata for an allowlist entry."""
    entry.last_used_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    entry.last_used_command = command
    approvals = load_exec_approvals(state_dir)
    if agent_id in approvals.agents:
        save_exec_approvals(approvals, state_dir)
