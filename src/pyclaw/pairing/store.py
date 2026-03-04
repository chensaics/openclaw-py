"""Pairing store — manages pairing requests and allowFrom lists.

Paths: ``~/.pyclaw/credentials/<channel>-pairing.json``,
       ``~/.pyclaw/credentials/<channel>-allowFrom.json``.
"""

from __future__ import annotations

import json
import logging
import secrets
import time
from dataclasses import dataclass
from pathlib import Path

from pyclaw.config.paths import resolve_credentials_dir

logger = logging.getLogger(__name__)

# Code alphabet without ambiguous chars (O/0, I/1)
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 8
MAX_PENDING = 3
TTL_SECONDS = 3600  # 1 hour


@dataclass
class PairingRequest:
    sender_id: str
    channel: str
    code: str
    created_at: float
    display_name: str = ""


@dataclass
class AllowFromEntry:
    sender_id: str
    added_at: float
    display_name: str = ""
    paired_via: str = ""  # "code" | "manual"


def _pairing_path(channel: str, creds_dir: Path | None = None) -> Path:
    d = creds_dir or resolve_credentials_dir()
    return d / f"{channel}-pairing.json"


def _allow_from_path(channel: str, creds_dir: Path | None = None) -> Path:
    d = creds_dir or resolve_credentials_dir()
    return d / f"{channel}-allowFrom.json"


def _generate_code() -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))


def _load_requests(channel: str, creds_dir: Path | None = None) -> list[PairingRequest]:
    path = _pairing_path(channel, creds_dir)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return [
            PairingRequest(
                sender_id=r["senderId"],
                channel=r.get("channel", channel),
                code=r["code"],
                created_at=r.get("createdAt", 0),
                display_name=r.get("displayName", ""),
            )
            for r in data
            if isinstance(r, dict)
        ]
    except Exception:
        return []


def _save_requests(
    channel: str,
    requests: list[PairingRequest],
    creds_dir: Path | None = None,
) -> None:
    path = _pairing_path(channel, creds_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = [
        {
            "senderId": r.sender_id,
            "channel": r.channel,
            "code": r.code,
            "createdAt": r.created_at,
            "displayName": r.display_name,
        }
        for r in requests
    ]
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def upsert_pairing_request(
    channel: str,
    sender_id: str,
    display_name: str = "",
    creds_dir: Path | None = None,
) -> PairingRequest:
    """Create or update a pairing request, returning the code."""
    requests = _load_requests(channel, creds_dir)

    # Remove expired
    now = time.time()
    requests = [r for r in requests if (now - r.created_at) < TTL_SECONDS]

    # Check for existing request from this sender
    for r in requests:
        if r.sender_id == sender_id:
            return r

    # Enforce max pending
    if len(requests) >= MAX_PENDING:
        requests = requests[-(MAX_PENDING - 1) :]

    req = PairingRequest(
        sender_id=sender_id,
        channel=channel,
        code=_generate_code(),
        created_at=now,
        display_name=display_name,
    )
    requests.append(req)
    _save_requests(channel, requests, creds_dir)
    return req


def approve_pairing_code(
    channel: str,
    code: str,
    creds_dir: Path | None = None,
) -> PairingRequest | None:
    """Match a code, remove the request, and add sender to allowFrom.

    Returns the matched request or None.
    """
    requests = _load_requests(channel, creds_dir)
    now = time.time()

    matched: PairingRequest | None = None
    remaining: list[PairingRequest] = []
    for r in requests:
        if r.code.upper() == code.upper() and (now - r.created_at) < TTL_SECONDS:
            matched = r
        else:
            remaining.append(r)

    if matched:
        _save_requests(channel, remaining, creds_dir)
        add_allow_from_entry(
            channel,
            matched.sender_id,
            display_name=matched.display_name,
            paired_via="code",
            creds_dir=creds_dir,
        )

    return matched


def read_allow_from_store(
    channel: str,
    creds_dir: Path | None = None,
) -> list[AllowFromEntry]:
    path = _allow_from_path(channel, creds_dir)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return [
            AllowFromEntry(
                sender_id=e["senderId"],
                added_at=e.get("addedAt", 0),
                display_name=e.get("displayName", ""),
                paired_via=e.get("pairedVia", ""),
            )
            for e in data
            if isinstance(e, dict)
        ]
    except Exception:
        return []


def add_allow_from_entry(
    channel: str,
    sender_id: str,
    display_name: str = "",
    paired_via: str = "manual",
    creds_dir: Path | None = None,
) -> None:
    entries = read_allow_from_store(channel, creds_dir)

    if any(e.sender_id == sender_id for e in entries):
        return

    entries.append(
        AllowFromEntry(
            sender_id=sender_id,
            added_at=time.time(),
            display_name=display_name,
            paired_via=paired_via,
        )
    )

    path = _allow_from_path(channel, creds_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = [
        {
            "senderId": e.sender_id,
            "addedAt": e.added_at,
            "displayName": e.display_name,
            "pairedVia": e.paired_via,
        }
        for e in entries
    ]
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
