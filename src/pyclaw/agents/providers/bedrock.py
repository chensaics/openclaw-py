"""Amazon Bedrock Converse Stream adapter.

Ported from ``src/agents/providers/bedrock*.ts``.

Provides:
- Bedrock Converse API request/response formatting
- AWS Signature v4 auth header building (deferred to boto3 at runtime)
- Streaming chunk parsing
- Model mapping for Bedrock model IDs
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class BedrockModelMapping:
    """Map a friendly name to a Bedrock model ARN/ID."""

    alias: str
    model_id: str
    provider: str  # "anthropic" | "amazon" | "meta" | "mistral" | "cohere"
    context_window: int = 0
    max_output: int = 4096
    supports_tools: bool = True
    supports_vision: bool = False
    supports_streaming: bool = True


BEDROCK_MODELS: list[BedrockModelMapping] = [
    BedrockModelMapping(
        "claude-3.5-sonnet", "anthropic.claude-3-5-sonnet-20241022-v2:0", "anthropic", 200000, 8192, True, True
    ),
    BedrockModelMapping("claude-3.5-haiku", "anthropic.claude-3-5-haiku-20241022-v1:0", "anthropic", 200000, 8192),
    BedrockModelMapping(
        "claude-3-opus", "anthropic.claude-3-opus-20240229-v1:0", "anthropic", 200000, 4096, True, True
    ),
    BedrockModelMapping("llama-3.1-70b", "meta.llama3-1-70b-instruct-v1:0", "meta", 131072, 2048),
    BedrockModelMapping("llama-3.1-8b", "meta.llama3-1-8b-instruct-v1:0", "meta", 131072, 2048),
    BedrockModelMapping("mistral-large", "mistral.mistral-large-2407-v1:0", "mistral", 131072, 8192),
    BedrockModelMapping("command-r-plus", "cohere.command-r-plus-v1:0", "cohere", 131072, 4096),
    BedrockModelMapping("titan-premier", "amazon.titan-text-premier-v1:0", "amazon", 32000, 3072, False),
]


@dataclass
class BedrockConfig:
    """Configuration for the Bedrock provider."""

    region: str = "us-east-1"
    profile: str = ""  # AWS profile name
    access_key_id: str = ""
    secret_access_key: str = ""
    session_token: str = ""
    endpoint_url: str = ""  # Custom endpoint
    default_model: str = "claude-3.5-sonnet"


@dataclass
class ConverseMessage:
    """A message in Bedrock Converse format."""

    role: str  # "user" | "assistant"
    content: list[dict[str, Any]]


@dataclass
class ConverseStreamChunk:
    """A parsed Bedrock Converse stream event."""

    type: str = ""  # "contentBlockDelta" | "contentBlockStart" | "contentBlockStop" | "messageStop" | "metadata"
    delta_text: str = ""
    stop_reason: str = ""
    usage: dict[str, int] | None = None
    tool_use: dict[str, Any] | None = None


class BedrockProvider:
    """Amazon Bedrock Converse API adapter."""

    def __init__(self, config: BedrockConfig | None = None) -> None:
        self._config = config or BedrockConfig()
        self._model_map: dict[str, BedrockModelMapping] = {}
        for m in BEDROCK_MODELS:
            self._model_map[m.alias] = m

    @property
    def name(self) -> str:
        return "bedrock"

    @property
    def region(self) -> str:
        return self._config.region

    def resolve_model(self, model: str) -> str:
        mapping = self._model_map.get(model)
        return mapping.model_id if mapping else model

    def get_model_info(self, model: str) -> BedrockModelMapping | None:
        return self._model_map.get(model)

    def build_converse_request(
        self,
        messages: list[ConverseMessage],
        model: str,
        *,
        system_prompt: str = "",
        max_tokens: int = 4096,
        temperature: float | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Build a Bedrock Converse API request body."""
        model_id = self.resolve_model(model)

        body: dict[str, Any] = {
            "modelId": model_id,
            "messages": [self._format_message(m) for m in messages],
            "inferenceConfig": {
                "maxTokens": max_tokens,
            },
        }

        if system_prompt:
            body["system"] = [{"text": system_prompt}]

        if temperature is not None:
            body["inferenceConfig"]["temperature"] = temperature

        if tools:
            body["toolConfig"] = {
                "tools": [self._format_tool(t) for t in tools],
            }

        return body

    def _format_message(self, msg: ConverseMessage) -> dict[str, Any]:
        return {"role": msg.role, "content": msg.content}

    def _format_tool(self, tool: dict[str, Any]) -> dict[str, Any]:
        """Convert OpenAI-style tool to Bedrock format."""
        if "function" in tool:
            fn = tool["function"]
            return {
                "toolSpec": {
                    "name": fn["name"],
                    "description": fn.get("description", ""),
                    "inputSchema": {
                        "json": fn.get("parameters", {"type": "object", "properties": {}}),
                    },
                },
            }
        return tool

    def parse_stream_event(self, event: dict[str, Any]) -> ConverseStreamChunk:
        """Parse a Bedrock Converse stream event."""
        if "contentBlockDelta" in event:
            delta = event["contentBlockDelta"].get("delta", {})
            return ConverseStreamChunk(
                type="contentBlockDelta",
                delta_text=delta.get("text", ""),
            )

        if "contentBlockStart" in event:
            start = event["contentBlockStart"].get("start", {})
            if "toolUse" in start:
                return ConverseStreamChunk(
                    type="contentBlockStart",
                    tool_use=start["toolUse"],
                )
            return ConverseStreamChunk(type="contentBlockStart")

        if "contentBlockStop" in event:
            return ConverseStreamChunk(type="contentBlockStop")

        if "messageStop" in event:
            return ConverseStreamChunk(
                type="messageStop",
                stop_reason=event["messageStop"].get("stopReason", "end_turn"),
            )

        if "metadata" in event:
            usage = event["metadata"].get("usage", {})
            return ConverseStreamChunk(
                type="metadata",
                usage={
                    "input_tokens": usage.get("inputTokens", 0),
                    "output_tokens": usage.get("outputTokens", 0),
                },
            )

        return ConverseStreamChunk()

    def get_endpoint_url(self) -> str:
        if self._config.endpoint_url:
            return self._config.endpoint_url
        return f"https://bedrock-runtime.{self._config.region}.amazonaws.com"

    def list_models(self) -> list[str]:
        return [m.alias for m in BEDROCK_MODELS]

    def list_models_by_provider(self, provider: str) -> list[str]:
        return [m.alias for m in BEDROCK_MODELS if m.provider == provider]

    def get_boto3_config(self) -> dict[str, Any]:
        """Get configuration dict suitable for creating boto3 client."""
        config: dict[str, Any] = {"region_name": self._config.region}
        if self._config.profile:
            config["profile_name"] = self._config.profile
        if self._config.access_key_id:
            config["aws_access_key_id"] = self._config.access_key_id
            config["aws_secret_access_key"] = self._config.secret_access_key
        if self._config.session_token:
            config["aws_session_token"] = self._config.session_token
        if self._config.endpoint_url:
            config["endpoint_url"] = self._config.endpoint_url
        return config
