"""Extra LLM providers — Venice, HuggingFace, NvidiaNIM, vLLM, LiteLLM, KimiCoding.

All based on OpenAI-compatible API endpoints.

Provides:
- Provider configurations for 6 additional LLM services
- Model mappings and default models
- API endpoint and auth configuration
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ExtraProviderConfig:
    """Configuration for an OpenAI-compatible extra provider."""
    name: str
    display_name: str
    base_url: str
    api_key_env: str = ""
    default_model: str = ""
    models: list[str] = field(default_factory=list)
    supports_streaming: bool = True
    supports_tools: bool = True
    supports_vision: bool = False
    max_context: int = 0
    headers: dict[str, str] = field(default_factory=dict)
    notes: str = ""

    def to_openai_config(self, api_key: str = "") -> dict[str, Any]:
        """Generate OpenAI-compatible client config."""
        return {
            "base_url": self.base_url,
            "api_key": api_key,
            "model": self.default_model,
            "stream": self.supports_streaming,
        }


EXTRA_PROVIDERS: dict[str, ExtraProviderConfig] = {
    "venice": ExtraProviderConfig(
        name="venice",
        display_name="Venice AI",
        base_url="https://api.venice.ai/api/v1",
        api_key_env="VENICE_API_KEY",
        default_model="llama-3.3-70b",
        models=[
            "llama-3.3-70b",
            "llama-3.1-405b",
            "deepseek-r1-671b",
            "qwen-2.5-coder-32b",
        ],
        supports_tools=True,
        notes="Privacy-focused AI platform",
    ),

    "huggingface": ExtraProviderConfig(
        name="huggingface",
        display_name="Hugging Face Inference",
        base_url="https://api-inference.huggingface.co/v1",
        api_key_env="HF_TOKEN",
        default_model="meta-llama/Llama-3.3-70B-Instruct",
        models=[
            "meta-llama/Llama-3.3-70B-Instruct",
            "mistralai/Mixtral-8x7B-Instruct-v0.1",
            "Qwen/Qwen2.5-72B-Instruct",
            "microsoft/Phi-3-medium-128k-instruct",
        ],
        supports_tools=False,
        notes="Hugging Face Inference API (Pro subscription may be required)",
    ),

    "nvidia-nim": ExtraProviderConfig(
        name="nvidia-nim",
        display_name="NVIDIA NIM",
        base_url="https://integrate.api.nvidia.com/v1",
        api_key_env="NVIDIA_API_KEY",
        default_model="meta/llama-3.1-405b-instruct",
        models=[
            "meta/llama-3.1-405b-instruct",
            "meta/llama-3.1-70b-instruct",
            "mistralai/mixtral-8x22b-instruct-v0.1",
            "google/gemma-2-27b-it",
        ],
        supports_tools=True,
        notes="NVIDIA AI Foundation Models",
    ),

    "vllm": ExtraProviderConfig(
        name="vllm",
        display_name="vLLM",
        base_url="http://localhost:8000/v1",
        api_key_env="VLLM_API_KEY",
        default_model="default",
        models=[],
        supports_tools=True,
        notes="Self-hosted vLLM instance (OpenAI-compatible)",
    ),

    "litellm": ExtraProviderConfig(
        name="litellm",
        display_name="LiteLLM Proxy",
        base_url="http://localhost:4000/v1",
        api_key_env="LITELLM_API_KEY",
        default_model="gpt-4o",
        models=[],
        supports_tools=True,
        notes="LiteLLM proxy for unified LLM access",
    ),

    "kimi-coding": ExtraProviderConfig(
        name="kimi-coding",
        display_name="Kimi (Moonshot)",
        base_url="https://api.moonshot.cn/v1",
        api_key_env="MOONSHOT_API_KEY",
        default_model="moonshot-v1-128k",
        models=[
            "moonshot-v1-8k",
            "moonshot-v1-32k",
            "moonshot-v1-128k",
        ],
        supports_tools=True,
        max_context=128000,
        notes="Moonshot AI / Kimi coding assistant",
    ),
}


def get_extra_provider(name: str) -> ExtraProviderConfig | None:
    return EXTRA_PROVIDERS.get(name)


def list_extra_providers() -> list[ExtraProviderConfig]:
    return list(EXTRA_PROVIDERS.values())


def get_all_extra_models() -> dict[str, list[str]]:
    """Get all models grouped by provider."""
    return {
        name: config.models
        for name, config in EXTRA_PROVIDERS.items()
        if config.models
    }


def resolve_extra_provider_env(name: str) -> str:
    """Resolve the API key for an extra provider from environment."""
    import os
    config = EXTRA_PROVIDERS.get(name)
    if not config:
        return ""
    return os.environ.get(config.api_key_env, "")


def create_openai_config(
    provider_name: str,
    *,
    api_key: str = "",
    model: str = "",
) -> dict[str, Any] | None:
    """Create an OpenAI-compatible config for an extra provider."""
    config = EXTRA_PROVIDERS.get(provider_name)
    if not config:
        return None

    key = api_key or resolve_extra_provider_env(provider_name)
    return {
        "base_url": config.base_url,
        "api_key": key,
        "model": model or config.default_model,
        "stream": config.supports_streaming,
    }
