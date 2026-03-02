"""OpenAI-compatible API adapter — generic adapter for any provider exposing the
OpenAI Chat Completions API (base_url + api_key + model mapping).

Supports: Together, OpenRouter, vLLM, HuggingFace TGI, Nvidia NIM, Fireworks,
Groq, Perplexity, Cerebras, SambaNova, and any custom endpoint.

Ported from ``src/agents/providers/openai-compat*.ts``.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator

logger = logging.getLogger(__name__)


class StreamFormat(str, Enum):
    """Streaming response format."""
    SSE = "sse"           # Standard SSE (data: {...})
    NDJSON = "ndjson"     # Newline-delimited JSON


@dataclass
class ModelMapping:
    """Map a local alias to the provider's actual model ID."""
    alias: str
    model_id: str
    context_window: int = 0
    max_output: int = 0
    supports_tools: bool = True
    supports_vision: bool = False
    supports_streaming: bool = True


@dataclass
class OpenAICompatConfig:
    """Configuration for an OpenAI-compatible provider."""
    name: str
    base_url: str
    api_key: str = ""
    default_model: str = ""
    models: list[ModelMapping] = field(default_factory=list)
    stream_format: StreamFormat = StreamFormat.SSE
    extra_headers: dict[str, str] = field(default_factory=dict)
    # Provider quirks
    supports_system_role: bool = True
    supports_tool_choice: bool = True
    max_retries: int = 2
    timeout_s: float = 120.0


@dataclass
class ChatMessage:
    role: str
    content: str
    name: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    tool_call_id: str = ""


@dataclass
class CompletionChunk:
    """A single streamed chunk."""
    delta_content: str = ""
    finish_reason: str = ""
    model: str = ""
    usage: dict[str, int] | None = None


@dataclass
class CompletionResult:
    """Full (non-streaming) completion result."""
    content: str
    model: str = ""
    finish_reason: str = ""
    usage: dict[str, int] = field(default_factory=dict)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)


class OpenAICompatProvider:
    """Generic OpenAI-compatible LLM provider."""

    def __init__(self, config: OpenAICompatConfig) -> None:
        self._config = config
        self._model_map: dict[str, ModelMapping] = {}
        for m in config.models:
            self._model_map[m.alias] = m

    @property
    def name(self) -> str:
        return self._config.name

    @property
    def base_url(self) -> str:
        return self._config.base_url.rstrip("/")

    def resolve_model(self, model: str) -> str:
        """Resolve a model alias to the provider's model ID."""
        if model in self._model_map:
            return self._model_map[model].model_id
        return model

    def get_model_info(self, model: str) -> ModelMapping | None:
        return self._model_map.get(model)

    def build_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {
            "Content-Type": "application/json",
        }
        if self._config.api_key:
            headers["Authorization"] = f"Bearer {self._config.api_key}"
        headers.update(self._config.extra_headers)
        return headers

    def build_request_body(
        self,
        messages: list[ChatMessage],
        model: str,
        *,
        stream: bool = False,
        temperature: float | None = None,
        max_tokens: int | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | None = None,
    ) -> dict[str, Any]:
        """Build a Chat Completions API request body."""
        resolved_model = self.resolve_model(model)

        body: dict[str, Any] = {
            "model": resolved_model,
            "messages": [self._format_message(m) for m in messages],
            "stream": stream,
        }

        if temperature is not None:
            body["temperature"] = temperature
        if max_tokens is not None:
            body["max_tokens"] = max_tokens

        if tools and self._config.supports_tool_choice:
            body["tools"] = tools
            if tool_choice:
                body["tool_choice"] = tool_choice

        return body

    def _format_message(self, msg: ChatMessage) -> dict[str, Any]:
        result: dict[str, Any] = {"role": msg.role, "content": msg.content}
        if msg.name:
            result["name"] = msg.name
        if msg.tool_calls:
            result["tool_calls"] = msg.tool_calls
        if msg.tool_call_id:
            result["tool_call_id"] = msg.tool_call_id
        if msg.role == "system" and not self._config.supports_system_role:
            result["role"] = "user"
        return result

    def parse_sse_chunk(self, line: str) -> CompletionChunk | None:
        """Parse a single SSE data line into a CompletionChunk."""
        if not line.startswith("data: "):
            return None
        data = line[6:].strip()
        if data == "[DONE]":
            return CompletionChunk(finish_reason="stop")

        try:
            obj = json.loads(data)
        except json.JSONDecodeError:
            return None

        choices = obj.get("choices", [])
        if not choices:
            return CompletionChunk(usage=obj.get("usage"))

        choice = choices[0]
        delta = choice.get("delta", {})
        return CompletionChunk(
            delta_content=delta.get("content", ""),
            finish_reason=choice.get("finish_reason", ""),
            model=obj.get("model", ""),
            usage=obj.get("usage"),
        )

    def parse_completion(self, response: dict[str, Any]) -> CompletionResult:
        """Parse a non-streaming completion response."""
        choices = response.get("choices", [])
        if not choices:
            return CompletionResult(content="")

        choice = choices[0]
        message = choice.get("message", {})
        return CompletionResult(
            content=message.get("content", ""),
            model=response.get("model", ""),
            finish_reason=choice.get("finish_reason", ""),
            usage=response.get("usage", {}),
            tool_calls=message.get("tool_calls", []),
        )

    def get_endpoint(self, path: str = "/chat/completions") -> str:
        return f"{self.base_url}/v1{path}"

    def list_models(self) -> list[str]:
        return [m.alias for m in self._config.models]


# ---------------------------------------------------------------------------
# Pre-built provider configurations
# ---------------------------------------------------------------------------

def together_config(api_key: str) -> OpenAICompatConfig:
    return OpenAICompatConfig(
        name="together",
        base_url="https://api.together.xyz",
        api_key=api_key,
        default_model="meta-llama/Llama-3.3-70B-Instruct-Turbo",
        models=[
            ModelMapping("llama-3.3-70b", "meta-llama/Llama-3.3-70B-Instruct-Turbo", context_window=131072),
            ModelMapping("llama-3.1-8b", "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo", context_window=131072),
            ModelMapping("qwen-2.5-72b", "Qwen/Qwen2.5-72B-Instruct-Turbo", context_window=131072),
            ModelMapping("deepseek-r1", "deepseek-ai/DeepSeek-R1", context_window=131072),
        ],
    )


def openrouter_config(api_key: str) -> OpenAICompatConfig:
    return OpenAICompatConfig(
        name="openrouter",
        base_url="https://openrouter.ai/api",
        api_key=api_key,
        default_model="anthropic/claude-sonnet-4",
        extra_headers={"HTTP-Referer": "https://openclaw.ai"},
        models=[
            ModelMapping("claude-sonnet", "anthropic/claude-sonnet-4", context_window=200000),
            ModelMapping("gpt-4o", "openai/gpt-4o", context_window=128000),
            ModelMapping("gemini-pro", "google/gemini-2.5-pro-preview", context_window=1000000),
        ],
    )


def fireworks_config(api_key: str) -> OpenAICompatConfig:
    return OpenAICompatConfig(
        name="fireworks",
        base_url="https://api.fireworks.ai/inference",
        api_key=api_key,
        default_model="accounts/fireworks/models/llama-v3p3-70b-instruct",
        models=[
            ModelMapping("llama-3.3-70b", "accounts/fireworks/models/llama-v3p3-70b-instruct", context_window=131072),
            ModelMapping("qwen-2.5-72b", "accounts/fireworks/models/qwen2p5-72b-instruct", context_window=131072),
        ],
    )


def groq_config(api_key: str) -> OpenAICompatConfig:
    return OpenAICompatConfig(
        name="groq",
        base_url="https://api.groq.com/openai",
        api_key=api_key,
        default_model="llama-3.3-70b-versatile",
        models=[
            ModelMapping("llama-3.3-70b", "llama-3.3-70b-versatile", context_window=131072),
            ModelMapping("llama-3.1-8b", "llama-3.1-8b-instant", context_window=131072),
            ModelMapping("gemma-2-9b", "gemma2-9b-it", context_window=8192),
        ],
    )


def perplexity_config(api_key: str) -> OpenAICompatConfig:
    return OpenAICompatConfig(
        name="perplexity",
        base_url="https://api.perplexity.ai",
        api_key=api_key,
        default_model="sonar-pro",
        supports_tool_choice=False,
        models=[
            ModelMapping("sonar-pro", "sonar-pro", context_window=200000),
            ModelMapping("sonar", "sonar", context_window=127072),
        ],
    )


PRECONFIGURED_PROVIDERS = {
    "together": together_config,
    "openrouter": openrouter_config,
    "fireworks": fireworks_config,
    "groq": groq_config,
    "perplexity": perplexity_config,
}
