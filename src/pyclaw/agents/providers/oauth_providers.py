"""OAuth provider flows — MiniMax Portal, Qwen Portal, GitHub Copilot Device OAuth.

Ported from ``src/agents/providers/oauth*.ts`` and
``src/agents/providers/github-copilot*.ts``.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
import time
import urllib.parse
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# PKCE helpers (shared)
# ---------------------------------------------------------------------------

def generate_code_verifier(length: int = 64) -> str:
    """Generate a PKCE code verifier."""
    return secrets.token_urlsafe(length)[:length]


def generate_code_challenge(verifier: str) -> str:
    """Generate a PKCE S256 code challenge from a verifier."""
    import base64
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


# ---------------------------------------------------------------------------
# OAuth flow states
# ---------------------------------------------------------------------------

@dataclass
class OAuthFlowState:
    """State for an in-progress OAuth flow."""
    provider: str
    state: str
    code_verifier: str = ""
    redirect_uri: str = ""
    started_at: float = 0.0

    def __post_init__(self) -> None:
        if self.started_at == 0.0:
            self.started_at = time.time()


@dataclass
class OAuthTokens:
    """OAuth token response."""
    access_token: str
    refresh_token: str = ""
    token_type: str = "Bearer"
    expires_in: int = 0
    scope: str = ""
    obtained_at: float = 0.0

    def __post_init__(self) -> None:
        if self.obtained_at == 0.0:
            self.obtained_at = time.time()

    @property
    def is_expired(self) -> bool:
        if self.expires_in <= 0:
            return False
        return time.time() > self.obtained_at + self.expires_in


@dataclass
class DeviceCodeResponse:
    """GitHub/OAuth device code flow response."""
    device_code: str
    user_code: str
    verification_uri: str
    expires_in: int = 900
    interval: int = 5


# ---------------------------------------------------------------------------
# MiniMax Portal OAuth
# ---------------------------------------------------------------------------

@dataclass
class MiniMaxOAuthConfig:
    client_id: str
    redirect_uri: str = "http://localhost:19876/callback"
    auth_url: str = "https://portal.minimaxi.com/oauth/authorize"
    token_url: str = "https://portal.minimaxi.com/oauth/token"
    scope: str = "api"


class MiniMaxOAuthFlow:
    """MiniMax Portal OAuth flow with PKCE."""

    def __init__(self, config: MiniMaxOAuthConfig) -> None:
        self._config = config
        self._state: OAuthFlowState | None = None

    def start(self) -> str:
        """Start the OAuth flow. Returns the authorization URL."""
        state = secrets.token_urlsafe(32)
        verifier = generate_code_verifier()
        challenge = generate_code_challenge(verifier)

        self._state = OAuthFlowState(
            provider="minimax",
            state=state,
            code_verifier=verifier,
            redirect_uri=self._config.redirect_uri,
        )

        params = {
            "client_id": self._config.client_id,
            "redirect_uri": self._config.redirect_uri,
            "response_type": "code",
            "scope": self._config.scope,
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
        return f"{self._config.auth_url}?{urllib.parse.urlencode(params)}"

    def build_token_request(self, code: str) -> dict[str, Any]:
        """Build the token exchange request body."""
        if not self._state:
            raise RuntimeError("OAuth flow not started")
        return {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self._config.redirect_uri,
            "client_id": self._config.client_id,
            "code_verifier": self._state.code_verifier,
        }

    def parse_token_response(self, data: dict[str, Any]) -> OAuthTokens:
        return OAuthTokens(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token", ""),
            token_type=data.get("token_type", "Bearer"),
            expires_in=data.get("expires_in", 0),
        )

    @property
    def token_url(self) -> str:
        return self._config.token_url


# ---------------------------------------------------------------------------
# Qwen Portal OAuth
# ---------------------------------------------------------------------------

@dataclass
class QwenOAuthConfig:
    client_id: str
    redirect_uri: str = "http://localhost:19876/callback"
    auth_url: str = "https://auth.aliyun.com/oauth/authorize"
    token_url: str = "https://auth.aliyun.com/oauth/token"
    scope: str = "openid"


class QwenOAuthFlow:
    """Qwen/Tongyi Portal OAuth flow with PKCE."""

    def __init__(self, config: QwenOAuthConfig) -> None:
        self._config = config
        self._state: OAuthFlowState | None = None

    def start(self) -> str:
        """Start the OAuth flow. Returns the authorization URL."""
        state = secrets.token_urlsafe(32)
        verifier = generate_code_verifier()
        challenge = generate_code_challenge(verifier)

        self._state = OAuthFlowState(
            provider="qwen",
            state=state,
            code_verifier=verifier,
            redirect_uri=self._config.redirect_uri,
        )

        params = {
            "client_id": self._config.client_id,
            "redirect_uri": self._config.redirect_uri,
            "response_type": "code",
            "scope": self._config.scope,
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
        return f"{self._config.auth_url}?{urllib.parse.urlencode(params)}"

    def build_token_request(self, code: str) -> dict[str, Any]:
        if not self._state:
            raise RuntimeError("OAuth flow not started")
        return {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self._config.redirect_uri,
            "client_id": self._config.client_id,
            "code_verifier": self._state.code_verifier,
        }

    def parse_token_response(self, data: dict[str, Any]) -> OAuthTokens:
        return OAuthTokens(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token", ""),
            token_type=data.get("token_type", "Bearer"),
            expires_in=data.get("expires_in", 0),
        )

    @property
    def token_url(self) -> str:
        return self._config.token_url


# ---------------------------------------------------------------------------
# GitHub Copilot Device OAuth
# ---------------------------------------------------------------------------

@dataclass
class CopilotDeviceConfig:
    client_id: str = "Iv1.b507a08c87ecfe98"  # VS Code Copilot client
    device_code_url: str = "https://github.com/login/device/code"
    token_url: str = "https://github.com/login/oauth/access_token"
    scope: str = ""


class CopilotDeviceFlow:
    """GitHub Copilot device code OAuth flow."""

    def __init__(self, config: CopilotDeviceConfig | None = None) -> None:
        self._config = config or CopilotDeviceConfig()
        self._device_code: str = ""

    def build_device_code_request(self) -> dict[str, Any]:
        """Build the device code request body."""
        body: dict[str, str] = {"client_id": self._config.client_id}
        if self._config.scope:
            body["scope"] = self._config.scope
        return body

    def parse_device_code_response(self, data: dict[str, Any]) -> DeviceCodeResponse:
        self._device_code = data["device_code"]
        return DeviceCodeResponse(
            device_code=data["device_code"],
            user_code=data["user_code"],
            verification_uri=data.get("verification_uri", "https://github.com/login/device"),
            expires_in=data.get("expires_in", 900),
            interval=data.get("interval", 5),
        )

    def build_token_poll_request(self) -> dict[str, Any]:
        """Build the token polling request body."""
        return {
            "client_id": self._config.client_id,
            "device_code": self._device_code,
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
        }

    def parse_token_response(self, data: dict[str, Any]) -> OAuthTokens | None:
        """Parse token response. Returns None if still pending."""
        error = data.get("error")
        if error == "authorization_pending":
            return None
        if error == "slow_down":
            return None
        if error:
            raise RuntimeError(f"Copilot OAuth error: {error} — {data.get('error_description', '')}")

        return OAuthTokens(
            access_token=data["access_token"],
            token_type=data.get("token_type", "Bearer"),
            scope=data.get("scope", ""),
        )

    @property
    def device_code_url(self) -> str:
        return self._config.device_code_url

    @property
    def token_url(self) -> str:
        return self._config.token_url

    def build_copilot_chat_headers(self, token: str) -> dict[str, str]:
        """Build headers for GitHub Copilot Chat API."""
        return {
            "Authorization": f"Bearer {token}",
            "Editor-Version": "vscode/1.96.0",
            "Editor-Plugin-Version": "copilot-chat/0.24.0",
            "Openai-Organization": "github-copilot",
            "Copilot-Integration-Id": "vscode-chat",
            "Content-Type": "application/json",
        }
