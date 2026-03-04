"""Embedding providers — OpenAI, Gemini, Voyage, Mistral, Ollama, and local."""

from __future__ import annotations

import logging
import math
import os
from dataclasses import dataclass
from typing import Any, Literal

logger = logging.getLogger(__name__)

EmbeddingProviderId = Literal["openai", "gemini", "voyage", "mistral", "local", "ollama", "auto"]


@dataclass
class EmbeddingProvider:
    """An embedding provider that can generate vector embeddings."""

    id: str = ""
    model: str = ""
    max_input_tokens: int = 8192

    async def embed_query(self, text: str) -> list[float]:
        raise NotImplementedError

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [await self.embed_query(t) for t in texts]


@dataclass
class EmbeddingProviderResult:
    provider: EmbeddingProvider | None = None
    requested_provider: str = ""
    fallback_from: str = ""
    fallback_reason: str = ""
    provider_unavailable_reason: str = ""


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """Embeddings via OpenAI API."""

    def __init__(self, *, api_key: str, model: str = "text-embedding-3-small", base_url: str | None = None) -> None:
        super().__init__(id="openai", model=model)
        self._api_key = api_key
        self._base_url = base_url

    async def embed_query(self, text: str) -> list[float]:
        return (await self.embed_batch([text]))[0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        import aiohttp

        url = (self._base_url or "https://api.openai.com") + "/v1/embeddings"
        headers = {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}
        payload = {"input": texts, "model": self.model}

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                data = await resp.json()
                if "error" in data:
                    raise ValueError(f"OpenAI embedding error: {data['error']}")

                # Sort by index to ensure order
                embeddings = sorted(data["data"], key=lambda x: x["index"])
                return [sanitize_and_normalize(e["embedding"]) for e in embeddings]


class GeminiEmbeddingProvider(EmbeddingProvider):
    """Embeddings via Google Gemini API."""

    def __init__(self, *, api_key: str, model: str = "text-embedding-004") -> None:
        super().__init__(id="gemini", model=model)
        self._api_key = api_key

    async def embed_query(self, text: str) -> list[float]:
        import aiohttp

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:embedContent"
        params = {"key": self._api_key}
        payload = {"model": f"models/{self.model}", "content": {"parts": [{"text": text}]}}

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, params=params) as resp:
                data = await resp.json()
                if "error" in data:
                    raise ValueError(f"Gemini embedding error: {data['error']}")
                return sanitize_and_normalize(data["embedding"]["values"])


class VoyageEmbeddingProvider(EmbeddingProvider):
    """Embeddings via Voyage AI API."""

    def __init__(self, *, api_key: str, model: str = "voyage-3") -> None:
        super().__init__(id="voyage", model=model)
        self._api_key = api_key

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        import aiohttp

        url = "https://api.voyageai.com/v1/embeddings"
        headers = {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}
        payload = {"input": texts, "model": self.model}

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                data = await resp.json()
                if "error" in data:
                    raise ValueError(f"Voyage embedding error: {data['error']}")
                embeddings = sorted(data["data"], key=lambda x: x["index"])
                return [sanitize_and_normalize(e["embedding"]) for e in embeddings]


class MistralEmbeddingProvider(EmbeddingProvider):
    """Embeddings via Mistral API."""

    def __init__(self, *, api_key: str, model: str = "mistral-embed") -> None:
        super().__init__(id="mistral", model=model)
        self._api_key = api_key

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        import aiohttp

        url = "https://api.mistral.ai/v1/embeddings"
        headers = {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}
        payload = {"input": texts, "model": self.model}

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                data = await resp.json()
                if "error" in data:
                    raise ValueError(f"Mistral embedding error: {data['error']}")
                embeddings = sorted(data["data"], key=lambda x: x["index"])
                return [sanitize_and_normalize(e["embedding"]) for e in embeddings]


class OllamaEmbeddingProvider(EmbeddingProvider):
    """Embeddings via local Ollama API."""

    def __init__(self, *, base_url: str = "http://localhost:11434", model: str = "nomic-embed-text") -> None:
        super().__init__(id="ollama", model=model)
        self._base_url = base_url.rstrip("/")

    async def embed_query(self, text: str) -> list[float]:
        import aiohttp

        url = f"{self._base_url}/api/embed"
        payload = {"model": self.model, "input": text}

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as resp:
                data = await resp.json()
                if "error" in data:
                    raise ValueError(f"Ollama embedding error: {data['error']}")
                return sanitize_and_normalize(data["embeddings"][0])


# ─── Factory ─────────────────────────────────────────────────────────────


async def create_embedding_provider(
    *,
    provider: EmbeddingProviderId = "auto",
    config: dict[str, Any] | None = None,
    model: str = "",
    fallback: bool = True,
) -> EmbeddingProviderResult:
    """Create an embedding provider from config and preferences."""
    from pyclaw.config.secrets import resolve_api_key_for_provider

    config = config or {}

    def _try_create(pid: str) -> EmbeddingProvider | None:
        if pid == "openai":
            key = resolve_api_key_for_provider("openai", config=config)
            if key:
                return OpenAIEmbeddingProvider(api_key=key, model=model or "text-embedding-3-small")
        elif pid == "gemini":
            key = resolve_api_key_for_provider("google", config=config)
            if key:
                return GeminiEmbeddingProvider(api_key=key, model=model or "text-embedding-004")
        elif pid == "voyage":
            key = resolve_api_key_for_provider("voyage", config=config)
            if key:
                return VoyageEmbeddingProvider(api_key=key, model=model or "voyage-3")
        elif pid == "mistral":
            key = resolve_api_key_for_provider("mistral", config=config)
            if key:
                return MistralEmbeddingProvider(api_key=key, model=model or "mistral-embed")
        elif pid == "ollama":
            base_url = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
            try:
                import urllib.request

                req = urllib.request.Request(base_url)
                with urllib.request.urlopen(req, timeout=2) as resp:
                    if resp.status < 500:
                        return OllamaEmbeddingProvider(base_url=base_url, model=model or "nomic-embed-text")
            except Exception:
                pass
        return None

    if provider != "auto":
        p = _try_create(provider)
        if p:
            return EmbeddingProviderResult(provider=p, requested_provider=provider)
        if fallback:
            return await create_embedding_provider(provider="auto", config=config, model=model, fallback=False)
        return EmbeddingProviderResult(
            requested_provider=provider,
            provider_unavailable_reason=f"No API key for {provider}",
        )

    # Auto: try providers in preference order (ollama last as local fallback)
    for pid in ("openai", "gemini", "voyage", "mistral", "ollama"):
        p = _try_create(pid)
        if p:
            return EmbeddingProviderResult(provider=p, requested_provider="auto")

    return EmbeddingProviderResult(
        requested_provider="auto",
        provider_unavailable_reason="No embedding provider available (no API keys)",
    )


# ─── Utilities ───────────────────────────────────────────────────────────


def sanitize_and_normalize(vec: list[float]) -> list[float]:
    """Sanitize (replace non-finite) and L2-normalize an embedding vector."""
    clean = [v if math.isfinite(v) else 0.0 for v in vec]
    norm = math.sqrt(sum(v * v for v in clean))
    if norm > 0:
        return [v / norm for v in clean]
    return clean


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
