"""Azure OpenAI Service provider adapter.

Supports:
- Deployment-based model routing (deployment_name → model)
- API version pinning (``api-version`` query parameter)
- Azure AD / Entra ID token authentication
- API key authentication
- Streaming via SSE

Configuration example::

    {
        "models": {
            "azure-openai": {
                "baseUrl": "https://my-resource.openai.azure.com",
                "apiKey": "${AZURE_OPENAI_API_KEY}",
                "api": "azure-openai",
                "models": [
                    {"id": "gpt-4o", "name": "gpt-4o", "deployment": "my-gpt4o-deployment"}
                ]
            }
        }
    }
"""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_API_VERSION = "2024-10-21"


@dataclass
class AzureDeployment:
    """Maps a model name to an Azure deployment."""

    model_id: str
    deployment_name: str
    context_window: int = 128_000
    max_output: int = 4096
    supports_tools: bool = True
    supports_vision: bool = False


@dataclass
class AzureOpenAIConfig:
    """Configuration for an Azure OpenAI resource."""

    resource_url: str = ""
    api_key: str = ""
    api_version: str = DEFAULT_API_VERSION
    deployments: list[AzureDeployment] = field(default_factory=list)
    use_aad: bool = False
    aad_tenant_id: str = ""
    aad_client_id: str = ""
    default_deployment: str = ""
    timeout_s: float = 120.0


class AzureOpenAIProvider:
    """Azure OpenAI Service adapter with deployment routing."""

    def __init__(self, config: AzureOpenAIConfig) -> None:
        self._config = config
        self._deployment_map: dict[str, AzureDeployment] = {
            d.model_id: d for d in config.deployments
        }
        self._aad_token: str = ""

    @property
    def provider_id(self) -> str:
        return "azure-openai"

    @property
    def display_name(self) -> str:
        return "Azure OpenAI"

    def resolve_deployment(self, model_id: str) -> AzureDeployment | None:
        dep = self._deployment_map.get(model_id)
        if dep:
            return dep
        for d in self._config.deployments:
            if d.deployment_name == model_id:
                return d
        return None

    def _endpoint(self, deployment_name: str) -> str:
        base = self._config.resource_url.rstrip("/")
        return (
            f"{base}/openai/deployments/{deployment_name}"
            f"/chat/completions?api-version={self._config.api_version}"
        )

    async def _get_auth_headers(self) -> dict[str, str]:
        if self._config.use_aad:
            token = await self._acquire_aad_token()
            return {"Authorization": f"Bearer {token}"}
        api_key = self._config.api_key or os.environ.get("AZURE_OPENAI_API_KEY", "")
        return {"api-key": api_key}

    async def _acquire_aad_token(self) -> str:
        """Acquire an Azure AD token via client credentials or cached value."""
        if self._aad_token:
            return self._aad_token

        try:
            import httpx

            tenant = self._config.aad_tenant_id or os.environ.get("AZURE_TENANT_ID", "")
            client_id = self._config.aad_client_id or os.environ.get("AZURE_CLIENT_ID", "")
            client_secret = os.environ.get("AZURE_CLIENT_SECRET", "")

            if not all([tenant, client_id, client_secret]):
                raise ValueError(
                    "Azure AD requires AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET"
                )

            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
                    data={
                        "grant_type": "client_credentials",
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "scope": "https://cognitiveservices.azure.com/.default",
                    },
                )
                resp.raise_for_status()
                self._aad_token = resp.json()["access_token"]
                return self._aad_token
        except Exception:
            logger.exception("Azure AD token acquisition failed")
            raise

    async def chat_completions(
        self,
        model_id: str,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        stream: bool = True,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Call Azure OpenAI chat completions with SSE streaming."""
        import httpx

        deployment = self.resolve_deployment(model_id)
        if not deployment:
            raise ValueError(
                f"No Azure deployment found for model '{model_id}'. "
                f"Available: {[d.model_id for d in self._config.deployments]}"
            )

        url = self._endpoint(deployment.deployment_name)
        headers = await self._get_auth_headers()
        headers["Content-Type"] = "application/json"

        body: dict[str, Any] = {
            "messages": messages,
            "stream": stream,
        }
        if tools:
            body["tools"] = tools
        if temperature is not None:
            body["temperature"] = temperature
        if max_tokens is not None:
            body["max_tokens"] = max_tokens

        async with httpx.AsyncClient(timeout=self._config.timeout_s) as client:
            if not stream:
                resp = await client.post(url, headers=headers, json=body)
                resp.raise_for_status()
                yield resp.json()
                return

            async with client.stream("POST", url, headers=headers, json=body) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:]
                    if data.strip() == "[DONE]":
                        return
                    try:
                        import json

                        yield json.loads(data)
                    except (ValueError, KeyError):
                        continue

    async def validate_key(self) -> bool:
        """Validate the API key / AAD credentials."""
        import httpx

        if not self._config.deployments:
            return False

        dep = self._config.deployments[0]
        url = self._endpoint(dep.deployment_name)
        headers = await self._get_auth_headers()
        headers["Content-Type"] = "application/json"

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    url,
                    headers=headers,
                    json={
                        "messages": [{"role": "user", "content": "hi"}],
                        "max_tokens": 1,
                        "stream": False,
                    },
                )
                return bool(resp.status_code == 200)
        except httpx.HTTPError:
            return False

    def status_info(self) -> dict[str, Any]:
        return {
            "provider": self.provider_id,
            "resourceUrl": self._config.resource_url,
            "apiVersion": self._config.api_version,
            "deployments": [
                {
                    "modelId": d.model_id,
                    "deploymentName": d.deployment_name,
                    "contextWindow": d.context_window,
                }
                for d in self._config.deployments
            ],
            "authMethod": "aad" if self._config.use_aad else "api-key",
        }
