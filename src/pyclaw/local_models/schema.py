"""Data models for local model management."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class BackendType(str, Enum):
    LLAMACPP = "llamacpp"
    MLX = "mlx"
    OLLAMA = "ollama"


class DownloadSource(str, Enum):
    HUGGINGFACE = "huggingface"
    MODELSCOPE = "modelscope"


class LocalModelInfo(BaseModel):
    id: str
    repo_id: str
    filename: str = ""
    backend: BackendType
    source: DownloadSource = DownloadSource.HUGGINGFACE
    file_size: int = 0
    local_path: str = ""
    display_name: str = ""
    context_length: int = 4096

    @property
    def size_mb(self) -> float:
        return self.file_size / (1024 * 1024)

    def summary(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "backend": self.backend.value,
            "display_name": self.display_name,
            "size_mb": round(self.size_mb, 1),
            "context_length": self.context_length,
            "local_path": self.local_path,
        }


class LocalModelsManifest(BaseModel):
    models: dict[str, LocalModelInfo] = Field(default_factory=dict)
    active_model_id: str = ""
