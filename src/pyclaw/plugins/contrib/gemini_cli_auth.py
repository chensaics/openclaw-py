"""Gemini CLI OAuth extension — OAuth 2.0 + PKCE authentication for Google Gemini CLI.

Ported from ``extensions/google-gemini-cli-auth/`` in the TypeScript codebase.

Provides:
- PKCE (Proof Key for Code Exchange) challenge generation
- OAuth authorization URL construction for Google Gemini
- Token exchange handling
- Token refresh with expiry tracking
- Credential persistence helpers
"""

from __future__ import annotations

import base64
import hashlib
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlencode

logger = logging.getLogger(__name__)

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_GEMINI_SCOPES = [
    "https://www.googleapis.com/auth/generative-language",
    "https://www.googleapis.com/auth/cloud-platform",
]
DEFAULT_REDIRECT_URI = "http://localhost:8085/callback"


@dataclass
class PKCEChallenge:
    """PKCE challenge pair."""

    code_verifier: str
    code_challenge: str
    method: str = "S256"


@dataclass
class OAuthTokens:
    """OAuth token set."""

    access_token: str = ""
    refresh_token: str = ""
    token_type: str = "Bearer"
    expires_at: float = 0.0
    scope: str = ""
    id_token: str = ""

    @property
    def is_expired(self) -> bool:
        if self.expires_at == 0.0:
            return True
        return time.time() >= self.expires_at - 60  # 60s buffer

    @property
    def is_valid(self) -> bool:
        return bool(self.access_token) and not self.is_expired


@dataclass
class GeminiAuthConfig:
    """Configuration for Gemini CLI OAuth."""

    client_id: str = ""
    client_secret: str = ""
    redirect_uri: str = DEFAULT_REDIRECT_URI
    scopes: list[str] = field(default_factory=lambda: list(GOOGLE_GEMINI_SCOPES))
    port: int = 8085


def generate_pkce_challenge() -> PKCEChallenge:
    """Generate a PKCE code verifier and challenge pair."""
    verifier_bytes = os.urandom(32)
    code_verifier = base64.urlsafe_b64encode(verifier_bytes).rstrip(b"=").decode("ascii")

    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")

    return PKCEChallenge(
        code_verifier=code_verifier,
        code_challenge=code_challenge,
        method="S256",
    )


def build_auth_url(
    config: GeminiAuthConfig,
    pkce: PKCEChallenge,
    *,
    state: str = "",
) -> str:
    """Build the OAuth authorization URL for Google Gemini."""
    params: dict[str, str] = {
        "client_id": config.client_id,
        "redirect_uri": config.redirect_uri,
        "response_type": "code",
        "scope": " ".join(config.scopes),
        "code_challenge": pkce.code_challenge,
        "code_challenge_method": pkce.method,
        "access_type": "offline",
        "prompt": "consent",
    }
    if state:
        params["state"] = state

    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


def build_token_request(
    config: GeminiAuthConfig,
    code: str,
    pkce: PKCEChallenge,
) -> dict[str, str]:
    """Build the token exchange request body."""
    return {
        "client_id": config.client_id,
        "client_secret": config.client_secret,
        "code": code,
        "code_verifier": pkce.code_verifier,
        "grant_type": "authorization_code",
        "redirect_uri": config.redirect_uri,
    }


def build_refresh_request(
    config: GeminiAuthConfig,
    refresh_token: str,
) -> dict[str, str]:
    """Build a token refresh request body."""
    return {
        "client_id": config.client_id,
        "client_secret": config.client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }


def parse_token_response(data: dict[str, Any]) -> OAuthTokens:
    """Parse a token endpoint response into OAuthTokens."""
    expires_in = data.get("expires_in", 3600)

    return OAuthTokens(
        access_token=data.get("access_token", ""),
        refresh_token=data.get("refresh_token", ""),
        token_type=data.get("token_type", "Bearer"),
        expires_at=time.time() + int(expires_in),
        scope=data.get("scope", ""),
        id_token=data.get("id_token", ""),
    )


class GeminiCliAuthExtension:
    """Extension for managing Gemini CLI OAuth authentication."""

    name = "google-gemini-cli-auth"
    version = "1.0.0"

    def __init__(self, config: GeminiAuthConfig | None = None) -> None:
        self._config = config or GeminiAuthConfig()
        self._tokens: OAuthTokens | None = None
        self._pkce: PKCEChallenge | None = None

    def start_auth_flow(self) -> tuple[str, PKCEChallenge]:
        """Start a new OAuth flow. Returns (auth_url, pkce)."""
        self._pkce = generate_pkce_challenge()
        url = build_auth_url(self._config, self._pkce)
        return url, self._pkce

    def get_token_request(self, code: str) -> dict[str, str] | None:
        """Get the token exchange request after receiving the auth code."""
        if not self._pkce:
            return None
        return build_token_request(self._config, code, self._pkce)

    def set_tokens(self, tokens: OAuthTokens) -> None:
        self._tokens = tokens

    def get_refresh_request(self) -> dict[str, str] | None:
        """Get a token refresh request."""
        if not self._tokens or not self._tokens.refresh_token:
            return None
        return build_refresh_request(self._config, self._tokens.refresh_token)

    @property
    def is_authenticated(self) -> bool:
        return self._tokens is not None and self._tokens.is_valid

    @property
    def access_token(self) -> str:
        if self._tokens and self._tokens.is_valid:
            return self._tokens.access_token
        return ""

    @property
    def needs_refresh(self) -> bool:
        if not self._tokens:
            return False
        return self._tokens.is_expired and bool(self._tokens.refresh_token)
