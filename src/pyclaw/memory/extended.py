"""Extended memory — Voyage/Mistral embedding providers, batch upload, remote HTTP client.

Ported from ``src/memory/embedding-providers*.ts`` and ``src/memory/batch*.ts``.

Provides:
- Voyage embedding provider
- Mistral embedding provider
- Batch upload pipeline (batch runner)
- Remote embedding HTTP client interface
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Embedding Provider Protocol
# ---------------------------------------------------------------------------

class EmbeddingProvider(Protocol):
    """Protocol for embedding providers."""
    @property
    def name(self) -> str: ...
    @property
    def dimension(self) -> int: ...
    def build_request(self, texts: list[str]) -> dict[str, Any]: ...
    def parse_response(self, response: dict[str, Any]) -> list[list[float]]: ...


# ---------------------------------------------------------------------------
# Voyage Embeddings
# ---------------------------------------------------------------------------

@dataclass
class VoyageConfig:
    api_key: str = ""
    base_url: str = "https://api.voyageai.com/v1"
    model: str = "voyage-3"
    dimension: int = 1024


class VoyageEmbeddingProvider:
    """Voyage AI embedding provider."""

    def __init__(self, config: VoyageConfig) -> None:
        self._config = config

    @property
    def name(self) -> str:
        return "voyage"

    @property
    def dimension(self) -> int:
        return self._config.dimension

    def build_request(self, texts: list[str]) -> dict[str, Any]:
        return {
            "url": f"{self._config.base_url}/embeddings",
            "headers": {
                "Authorization": f"Bearer {self._config.api_key}",
                "Content-Type": "application/json",
            },
            "body": {
                "model": self._config.model,
                "input": texts,
                "input_type": "document",
            },
        }

    def parse_response(self, response: dict[str, Any]) -> list[list[float]]:
        data = response.get("data", [])
        return [item.get("embedding", []) for item in data]


# ---------------------------------------------------------------------------
# Mistral Embeddings
# ---------------------------------------------------------------------------

@dataclass
class MistralEmbeddingConfig:
    api_key: str = ""
    base_url: str = "https://api.mistral.ai/v1"
    model: str = "mistral-embed"
    dimension: int = 1024


class MistralEmbeddingProvider:
    """Mistral embedding provider."""

    def __init__(self, config: MistralEmbeddingConfig) -> None:
        self._config = config

    @property
    def name(self) -> str:
        return "mistral"

    @property
    def dimension(self) -> int:
        return self._config.dimension

    def build_request(self, texts: list[str]) -> dict[str, Any]:
        return {
            "url": f"{self._config.base_url}/embeddings",
            "headers": {
                "Authorization": f"Bearer {self._config.api_key}",
                "Content-Type": "application/json",
            },
            "body": {
                "model": self._config.model,
                "input": texts,
            },
        }

    def parse_response(self, response: dict[str, Any]) -> list[list[float]]:
        data = response.get("data", [])
        return [item.get("embedding", []) for item in data]


# ---------------------------------------------------------------------------
# Batch Upload Pipeline
# ---------------------------------------------------------------------------

@dataclass
class BatchItem:
    """A single item in a batch upload."""
    item_id: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class BatchResult:
    """Result from a batch upload."""
    total: int
    succeeded: int = 0
    failed: int = 0
    duration_ms: float = 0.0
    errors: list[str] = field(default_factory=list)


@dataclass
class BatchConfig:
    """Configuration for batch processing."""
    batch_size: int = 50
    max_concurrent_batches: int = 3
    retry_count: int = 2
    delay_between_batches_ms: int = 100


class BatchRunner:
    """Process items in batches with concurrency control."""

    def __init__(self, config: BatchConfig | None = None) -> None:
        self._config = config or BatchConfig()
        self._total_processed = 0

    def create_batches(self, items: list[BatchItem]) -> list[list[BatchItem]]:
        """Split items into sized batches."""
        batches: list[list[BatchItem]] = []
        for i in range(0, len(items), self._config.batch_size):
            batches.append(items[i:i + self._config.batch_size])
        return batches

    def process_batch_sync(
        self,
        batch: list[BatchItem],
        *,
        embed_fn: Any = None,
    ) -> BatchResult:
        """Process a single batch synchronously (for testing/simple use)."""
        start = time.time()
        succeeded = 0
        failed = 0
        errors: list[str] = []

        texts = [item.text for item in batch]
        try:
            if embed_fn:
                embed_fn(texts)
            succeeded = len(batch)
        except Exception as e:
            failed = len(batch)
            errors.append(str(e))

        duration = (time.time() - start) * 1000
        self._total_processed += succeeded

        return BatchResult(
            total=len(batch),
            succeeded=succeeded,
            failed=failed,
            duration_ms=duration,
            errors=errors,
        )

    @property
    def total_processed(self) -> int:
        return self._total_processed

    def reset(self) -> None:
        self._total_processed = 0


# ---------------------------------------------------------------------------
# Remote Embedding HTTP Client
# ---------------------------------------------------------------------------

@dataclass
class RemoteEmbeddingConfig:
    """Configuration for a remote embedding HTTP client."""
    url: str
    api_key: str = ""
    model: str = ""
    timeout_s: float = 30.0
    max_batch_size: int = 100


class RemoteEmbeddingClient:
    """HTTP client interface for remote embedding services."""

    def __init__(self, config: RemoteEmbeddingConfig) -> None:
        self._config = config

    @property
    def url(self) -> str:
        return self._config.url

    def build_request(self, texts: list[str]) -> dict[str, Any]:
        """Build an embedding request."""
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._config.api_key:
            headers["Authorization"] = f"Bearer {self._config.api_key}"

        body: dict[str, Any] = {"input": texts}
        if self._config.model:
            body["model"] = self._config.model

        return {
            "url": self._config.url,
            "headers": headers,
            "body": body,
            "timeout": self._config.timeout_s,
        }

    def validate_batch_size(self, texts: list[str]) -> bool:
        return len(texts) <= self._config.max_batch_size

    def split_batches(self, texts: list[str]) -> list[list[str]]:
        """Split texts into batches respecting max_batch_size."""
        batches: list[list[str]] = []
        for i in range(0, len(texts), self._config.max_batch_size):
            batches.append(texts[i:i + self._config.max_batch_size])
        return batches
