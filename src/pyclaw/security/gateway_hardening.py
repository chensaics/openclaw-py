"""Gateway security hardening — env hashing, HTTP auth canonicalization, pairing metadata.

Ported from various security-related modules in the TypeScript codebase:
- Environment variable hashing for safe logging
- HTTP auth header canonicalization for plugin auth
- Pairing metadata pinning to prevent replay/impersonation
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Environment variable hashing
# ---------------------------------------------------------------------------

SENSITIVE_ENV_PATTERNS = re.compile(
    r"(KEY|TOKEN|SECRET|PASSWORD|CREDENTIALS|AUTH|API_KEY|PRIVATE|SIGNING)",
    re.IGNORECASE,
)


def hash_env_value(value: str, *, prefix_len: int = 4) -> str:
    """Hash an environment variable value for safe logging.

    Returns ``prefix...sha256[:8]`` so values are identifiable but not exposed.
    """
    if len(value) <= prefix_len:
        return "***"
    digest = hashlib.sha256(value.encode()).hexdigest()[:8]
    return f"{value[:prefix_len]}...{digest}"


def sanitize_env_for_logging(env: dict[str, str]) -> dict[str, str]:
    """Sanitize environment variables for safe logging output."""
    result: dict[str, str] = {}
    for key, value in env.items():
        if SENSITIVE_ENV_PATTERNS.search(key):
            result[key] = hash_env_value(value)
        else:
            result[key] = value
    return result


def compute_env_fingerprint(env: dict[str, str], keys: list[str] | None = None) -> str:
    """Compute a stable fingerprint of selected env vars for drift detection."""
    target_keys = sorted(keys) if keys else sorted(env.keys())
    parts = [f"{k}={env.get(k, '')}" for k in target_keys if k in env]
    combined = "\n".join(parts)
    return hashlib.sha256(combined.encode()).hexdigest()


# ---------------------------------------------------------------------------
# HTTP auth canonicalization
# ---------------------------------------------------------------------------


@dataclass
class CanonicalAuthHeader:
    """Parsed and canonicalized auth header."""

    scheme: str  # "bearer", "basic", "api-key"
    credential: str
    raw: str = ""

    @property
    def is_bearer(self) -> bool:
        return self.scheme == "bearer"

    @property
    def is_basic(self) -> bool:
        return self.scheme == "basic"

    def to_header(self) -> str:
        """Re-encode as a standard Authorization header value."""
        if self.scheme == "bearer":
            return f"Bearer {self.credential}"
        if self.scheme == "basic":
            return f"Basic {self.credential}"
        return f"{self.scheme} {self.credential}"


def canonicalize_auth_header(value: str) -> CanonicalAuthHeader | None:
    """Parse an Authorization header into canonical form.

    Handles common plugin auth patterns:
    - ``Bearer <token>``
    - ``Basic <base64>``
    - ``Api-Key <key>``
    - Raw token (assumed Bearer)
    """
    value = value.strip()
    if not value:
        return None

    lower = value.lower()

    if lower.startswith("bearer "):
        token = value[7:].strip()
        return CanonicalAuthHeader(scheme="bearer", credential=token, raw=value)

    if lower.startswith("basic "):
        cred = value[6:].strip()
        return CanonicalAuthHeader(scheme="basic", credential=cred, raw=value)

    if lower.startswith("api-key ") or lower.startswith("apikey "):
        sep = value.index(" ")
        key = value[sep + 1 :].strip()
        return CanonicalAuthHeader(scheme="api-key", credential=key, raw=value)

    # Raw token — treat as Bearer
    if _looks_like_token(value):
        return CanonicalAuthHeader(scheme="bearer", credential=value, raw=value)

    return None


def _looks_like_token(value: str) -> bool:
    """Heuristic: tokens are at least 20 chars and alphanumeric/base64-ish."""
    if len(value) < 20:
        return False
    return bool(re.match(r"^[A-Za-z0-9_\-./+=]+$", value))


# ---------------------------------------------------------------------------
# Pairing metadata pinning
# ---------------------------------------------------------------------------


@dataclass
class PairingMetadata:
    """Metadata attached to a pairing for anti-replay/impersonation."""

    channel_id: str
    account_id: str
    peer_id: str
    paired_at: float = 0.0
    ip_address: str = ""
    user_agent: str = ""
    fingerprint: str = ""
    nonce: str = ""

    def __post_init__(self) -> None:
        if self.paired_at == 0.0:
            self.paired_at = time.time()

    def compute_fingerprint(self) -> str:
        """Compute a binding fingerprint from pinned fields."""
        parts = [
            self.channel_id,
            self.account_id,
            self.peer_id,
            self.ip_address,
            self.user_agent,
        ]
        combined = "|".join(parts)
        return hashlib.sha256(combined.encode()).hexdigest()

    def verify_fingerprint(self) -> bool:
        """Verify that the stored fingerprint matches the current metadata."""
        if not self.fingerprint:
            return True
        return self.fingerprint == self.compute_fingerprint()

    def to_dict(self) -> dict[str, Any]:
        return {
            "channelId": self.channel_id,
            "accountId": self.account_id,
            "peerId": self.peer_id,
            "pairedAt": self.paired_at,
            "ipAddress": self.ip_address,
            "userAgent": self.user_agent,
            "fingerprint": self.fingerprint,
            "nonce": self.nonce,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PairingMetadata:
        return cls(
            channel_id=data.get("channelId", ""),
            account_id=data.get("accountId", ""),
            peer_id=data.get("peerId", ""),
            paired_at=data.get("pairedAt", 0.0),
            ip_address=data.get("ipAddress", ""),
            user_agent=data.get("userAgent", ""),
            fingerprint=data.get("fingerprint", ""),
            nonce=data.get("nonce", ""),
        )


# ---------------------------------------------------------------------------
# Webhook replay protection
# ---------------------------------------------------------------------------


class WebhookReplayGuard:
    """Protects webhook endpoints from replay attacks using nonces and timestamps."""

    def __init__(self, *, max_age_s: float = 300.0, max_nonces: int = 10_000) -> None:
        self._max_age_s = max_age_s
        self._seen_nonces: dict[str, float] = {}
        self._max_nonces = max_nonces

    def check(self, nonce: str, timestamp: float) -> bool:
        """Check if a webhook request is valid (not replayed).

        Returns True if the request is fresh and the nonce is unseen.
        """
        now = time.time()

        if abs(now - timestamp) > self._max_age_s:
            return False

        if nonce in self._seen_nonces:
            return False

        self._seen_nonces[nonce] = now
        self._cleanup()
        return True

    def _cleanup(self) -> None:
        """Remove expired nonces."""
        if len(self._seen_nonces) <= self._max_nonces:
            return
        now = time.time()
        expired = [k for k, v in self._seen_nonces.items() if now - v > self._max_age_s]
        for k in expired:
            del self._seen_nonces[k]
