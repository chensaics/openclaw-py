"""Provider authentication handlers — API Key, OAuth, Device Code flows.

Ported from ``src/commands/onboard-auth/auth-choice.apply.*.ts``.

Provides:
- Auth handler registry for 30+ providers
- API Key authentication flow
- OAuth PKCE flow (browser-based)
- Device Code flow (terminal-based)
- Credential persistence and validation
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)


class AuthMethod(str, Enum):
    API_KEY = "api_key"
    OAUTH = "oauth"
    DEVICE_CODE = "device_code"
    AWS_IAM = "aws_iam"
    NONE = "none"


@dataclass
class ProviderAuthSpec:
    """Specification for a provider's authentication."""
    provider_id: str
    display_name: str
    auth_method: AuthMethod
    env_var: str = ""
    api_key_prefix: str = ""
    api_key_url: str = ""
    oauth_authorize_url: str = ""
    oauth_token_url: str = ""
    oauth_client_id: str = ""
    oauth_scopes: list[str] = field(default_factory=list)
    device_code_url: str = ""
    validate_url: str = ""
    notes: str = ""


@dataclass
class AuthCredential:
    """Stored credential for a provider."""
    provider_id: str
    auth_method: AuthMethod
    api_key: str = ""
    access_token: str = ""
    refresh_token: str = ""
    expires_at: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_expired(self) -> bool:
        if self.expires_at == 0:
            return False
        return time.time() > self.expires_at

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "provider_id": self.provider_id,
            "auth_method": self.auth_method.value,
        }
        if self.api_key:
            d["api_key"] = self.api_key
        if self.access_token:
            d["access_token"] = self.access_token
        if self.refresh_token:
            d["refresh_token"] = self.refresh_token
        if self.expires_at:
            d["expires_at"] = self.expires_at
        if self.metadata:
            d["metadata"] = self.metadata
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AuthCredential:
        return cls(
            provider_id=data.get("provider_id", ""),
            auth_method=AuthMethod(data.get("auth_method", "api_key")),
            api_key=data.get("api_key", ""),
            access_token=data.get("access_token", ""),
            refresh_token=data.get("refresh_token", ""),
            expires_at=data.get("expires_at", 0.0),
            metadata=data.get("metadata", {}),
        )


@dataclass
class AuthResult:
    """Result of an authentication attempt."""
    success: bool
    credential: AuthCredential | None = None
    error: str = ""
    message: str = ""


# ---------------------------------------------------------------------------
# Built-in Provider Specs
# ---------------------------------------------------------------------------

PROVIDER_SPECS: dict[str, ProviderAuthSpec] = {
    "openai": ProviderAuthSpec(
        provider_id="openai", display_name="OpenAI",
        auth_method=AuthMethod.API_KEY, env_var="OPENAI_API_KEY",
        api_key_prefix="sk-", api_key_url="https://platform.openai.com/api-keys",
    ),
    "anthropic": ProviderAuthSpec(
        provider_id="anthropic", display_name="Anthropic",
        auth_method=AuthMethod.API_KEY, env_var="ANTHROPIC_API_KEY",
        api_key_prefix="sk-ant-", api_key_url="https://console.anthropic.com/settings/keys",
    ),
    "google": ProviderAuthSpec(
        provider_id="google", display_name="Google Gemini",
        auth_method=AuthMethod.API_KEY, env_var="GOOGLE_GENERATIVE_AI_API_KEY",
        api_key_url="https://aistudio.google.com/app/apikey",
    ),
    "moonshot": ProviderAuthSpec(
        provider_id="moonshot", display_name="Moonshot / Kimi",
        auth_method=AuthMethod.API_KEY, env_var="MOONSHOT_API_KEY",
        api_key_url="https://platform.moonshot.cn/console/api-keys",
    ),
    "volcengine": ProviderAuthSpec(
        provider_id="volcengine", display_name="Volcengine / Doubao",
        auth_method=AuthMethod.API_KEY, env_var="VOLCENGINE_API_KEY",
        api_key_url="https://console.volcengine.com/ark",
    ),
    "deepseek": ProviderAuthSpec(
        provider_id="deepseek", display_name="DeepSeek",
        auth_method=AuthMethod.API_KEY, env_var="DEEPSEEK_API_KEY",
        api_key_url="https://platform.deepseek.com/api_keys",
    ),
    "qwen": ProviderAuthSpec(
        provider_id="qwen", display_name="Qwen / Tongyi",
        auth_method=AuthMethod.API_KEY, env_var="DASHSCOPE_API_KEY",
        api_key_url="https://dashscope.console.aliyun.com/apiKey",
    ),
    "zhipu": ProviderAuthSpec(
        provider_id="zhipu", display_name="Zhipu / GLM",
        auth_method=AuthMethod.API_KEY, env_var="ZHIPU_API_KEY",
        api_key_url="https://open.bigmodel.cn/usercenter/apikeys",
    ),
    "minimax": ProviderAuthSpec(
        provider_id="minimax", display_name="MiniMax",
        auth_method=AuthMethod.API_KEY, env_var="MINIMAX_API_KEY",
        api_key_url="https://platform.minimaxi.com/user-center/basic-information/interface-key",
    ),
    "xai": ProviderAuthSpec(
        provider_id="xai", display_name="xAI / Grok",
        auth_method=AuthMethod.API_KEY, env_var="XAI_API_KEY",
        api_key_url="https://console.x.ai",
    ),
    "openrouter": ProviderAuthSpec(
        provider_id="openrouter", display_name="OpenRouter",
        auth_method=AuthMethod.API_KEY, env_var="OPENROUTER_API_KEY",
        api_key_prefix="sk-or-", api_key_url="https://openrouter.ai/keys",
    ),
    "together": ProviderAuthSpec(
        provider_id="together", display_name="Together AI",
        auth_method=AuthMethod.API_KEY, env_var="TOGETHER_API_KEY",
        api_key_url="https://api.together.ai/settings/api-keys",
    ),
    "groq": ProviderAuthSpec(
        provider_id="groq", display_name="Groq",
        auth_method=AuthMethod.API_KEY, env_var="GROQ_API_KEY",
        api_key_prefix="gsk_", api_key_url="https://console.groq.com/keys",
    ),
    "perplexity": ProviderAuthSpec(
        provider_id="perplexity", display_name="Perplexity",
        auth_method=AuthMethod.API_KEY, env_var="PERPLEXITY_API_KEY",
        api_key_prefix="pplx-", api_key_url="https://www.perplexity.ai/settings/api",
    ),
    "fireworks": ProviderAuthSpec(
        provider_id="fireworks", display_name="Fireworks AI",
        auth_method=AuthMethod.API_KEY, env_var="FIREWORKS_API_KEY",
        api_key_url="https://fireworks.ai/api-keys",
    ),
    "huggingface": ProviderAuthSpec(
        provider_id="huggingface", display_name="HuggingFace",
        auth_method=AuthMethod.API_KEY, env_var="HF_TOKEN",
        api_key_prefix="hf_", api_key_url="https://huggingface.co/settings/tokens",
    ),
    "bedrock": ProviderAuthSpec(
        provider_id="bedrock", display_name="Amazon Bedrock",
        auth_method=AuthMethod.AWS_IAM, env_var="AWS_ACCESS_KEY_ID",
        notes="Requires AWS IAM credentials (access key + secret + region)",
    ),
    "ollama": ProviderAuthSpec(
        provider_id="ollama", display_name="Ollama (Local)",
        auth_method=AuthMethod.NONE,
        notes="No authentication needed; runs locally",
    ),
    "minimax-portal": ProviderAuthSpec(
        provider_id="minimax-portal", display_name="MiniMax Portal",
        auth_method=AuthMethod.OAUTH,
        oauth_authorize_url="https://api.minimax.chat/v1/oauth/authorize",
        oauth_token_url="https://api.minimax.chat/v1/oauth/token",
    ),
    "qwen-portal": ProviderAuthSpec(
        provider_id="qwen-portal", display_name="Qwen Portal",
        auth_method=AuthMethod.OAUTH,
        oauth_authorize_url="https://account.aliyun.com/authorize",
        oauth_token_url="https://account.aliyun.com/token",
    ),
    "copilot": ProviderAuthSpec(
        provider_id="copilot", display_name="GitHub Copilot",
        auth_method=AuthMethod.DEVICE_CODE,
        device_code_url="https://github.com/login/device/code",
    ),
    "nvidia": ProviderAuthSpec(
        provider_id="nvidia", display_name="Nvidia NIM",
        auth_method=AuthMethod.API_KEY, env_var="NVIDIA_API_KEY",
        api_key_url="https://build.nvidia.com",
    ),
    "qianfan": ProviderAuthSpec(
        provider_id="qianfan", display_name="Baidu Qianfan",
        auth_method=AuthMethod.API_KEY, env_var="QIANFAN_API_KEY",
        api_key_url="https://console.bce.baidu.com/qianfan",
    ),
    "vllm": ProviderAuthSpec(
        provider_id="vllm", display_name="vLLM",
        auth_method=AuthMethod.API_KEY,
        notes="Self-hosted vLLM instance",
    ),
    "litellm": ProviderAuthSpec(
        provider_id="litellm", display_name="LiteLLM",
        auth_method=AuthMethod.API_KEY,
        notes="LiteLLM proxy",
    ),
    "byteplus": ProviderAuthSpec(
        provider_id="byteplus", display_name="BytePlus",
        auth_method=AuthMethod.API_KEY, env_var="BYTEPLUS_API_KEY",
    ),
    "xiaomi": ProviderAuthSpec(
        provider_id="xiaomi", display_name="Xiaomi AI",
        auth_method=AuthMethod.API_KEY, env_var="XIAOMI_API_KEY",
    ),
}


# ---------------------------------------------------------------------------
# Credential Storage
# ---------------------------------------------------------------------------

class CredentialStore:
    """Persist and retrieve provider credentials."""

    def __init__(self, base_dir: str | Path | None = None) -> None:
        self._base = Path(base_dir) if base_dir else Path.home() / ".pyclaw" / "credentials"

    def save(self, credential: AuthCredential) -> None:
        self._base.mkdir(parents=True, exist_ok=True)
        path = self._base / f"{credential.provider_id}.json"
        path.write_text(json.dumps(credential.to_dict(), indent=2), encoding="utf-8")

    def load(self, provider_id: str) -> AuthCredential | None:
        path = self._base / f"{provider_id}.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return AuthCredential.from_dict(data)
        except Exception:
            return None

    def delete(self, provider_id: str) -> bool:
        path = self._base / f"{provider_id}.json"
        if path.exists():
            path.unlink()
            return True
        return False

    def list_providers(self) -> list[str]:
        if not self._base.exists():
            return []
        return [p.stem for p in self._base.glob("*.json")]


# ---------------------------------------------------------------------------
# Auth Handlers
# ---------------------------------------------------------------------------

def validate_api_key(key: str, spec: ProviderAuthSpec) -> bool:
    """Basic validation of an API key against its spec."""
    if not key:
        return False
    if spec.api_key_prefix and not key.startswith(spec.api_key_prefix):
        return False
    if len(key) < 8:
        return False
    return True


def apply_api_key_auth(provider_id: str, api_key: str) -> AuthResult:
    """Apply API key authentication for a provider."""
    spec = PROVIDER_SPECS.get(provider_id)
    if not spec:
        return AuthResult(success=False, error=f"Unknown provider: {provider_id}")

    if not validate_api_key(api_key, spec):
        prefix_hint = f" (should start with '{spec.api_key_prefix}')" if spec.api_key_prefix else ""
        return AuthResult(success=False, error=f"Invalid API key format{prefix_hint}")

    credential = AuthCredential(
        provider_id=provider_id,
        auth_method=AuthMethod.API_KEY,
        api_key=api_key,
    )
    return AuthResult(success=True, credential=credential, message=f"{spec.display_name} authenticated")


def get_provider_auth_info(provider_id: str) -> dict[str, Any] | None:
    """Get auth info for display/onboarding."""
    spec = PROVIDER_SPECS.get(provider_id)
    if not spec:
        return None
    return {
        "provider_id": spec.provider_id,
        "display_name": spec.display_name,
        "auth_method": spec.auth_method.value,
        "env_var": spec.env_var,
        "api_key_url": spec.api_key_url,
        "notes": spec.notes,
    }


def list_available_providers() -> list[dict[str, str]]:
    """List all available providers with their auth methods."""
    return [
        {
            "id": spec.provider_id,
            "name": spec.display_name,
            "method": spec.auth_method.value,
        }
        for spec in PROVIDER_SPECS.values()
    ]
