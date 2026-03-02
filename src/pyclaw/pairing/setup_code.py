"""Pairing setup code — encode/decode gateway connection info for QR/deep-link."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass


@dataclass
class PairingSetup:
    url: str
    token: str | None = None
    password: str | None = None


def encode_pairing_setup_code(setup: PairingSetup) -> str:
    """Encode gateway connection info as a base64url string."""
    payload: dict[str, str] = {"url": setup.url}
    if setup.token:
        payload["token"] = setup.token
    if setup.password:
        payload["password"] = setup.password
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def decode_pairing_setup_code(code: str) -> PairingSetup:
    """Decode a base64url setup code back to connection info."""
    padded = code + "=" * (4 - len(code) % 4)
    raw = base64.urlsafe_b64decode(padded)
    data = json.loads(raw)
    return PairingSetup(
        url=data["url"],
        token=data.get("token"),
        password=data.get("password"),
    )
