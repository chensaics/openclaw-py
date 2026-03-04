"""Unified local model chat interface — bridges local backends to Agent provider protocol."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any, cast

from .manager import get_active_model, get_local_model
from .schema import BackendType

logger = logging.getLogger(__name__)

_active_backend: Any = None
_active_model_id: str = ""


def _load_backend(model_id: str | None = None) -> Any:
    global _active_backend, _active_model_id

    info = get_local_model(model_id) if model_id else get_active_model()
    if info is None:
        raise RuntimeError("No local model available. Download one first: pyclaw models download <repo>")

    if _active_model_id == info.id and _active_backend is not None:
        return _active_backend

    if _active_backend is not None:
        try:
            _active_backend.close()
        except Exception:
            pass

    if info.backend == BackendType.LLAMACPP:
        from .backends.llamacpp import LlamaCppBackend

        _active_backend = LlamaCppBackend(
            info.local_path,
            n_ctx=info.context_length,
        )
    elif info.backend == BackendType.MLX:
        from .backends.mlx_backend import MLXBackend

        _active_backend = MLXBackend(info.local_path)
    else:
        raise ValueError(f"Backend '{info.backend}' does not support direct local inference")

    _active_model_id = info.id
    return _active_backend


def local_chat(
    messages: list[dict[str, str]],
    *,
    model_id: str | None = None,
    max_tokens: int = 2048,
    temperature: float = 0.7,
) -> dict[str, Any]:
    backend = _load_backend(model_id)
    return cast(dict[str, Any], backend.generate(messages, max_tokens=max_tokens, temperature=temperature))


async def local_chat_stream(
    messages: list[dict[str, str]],
    *,
    model_id: str | None = None,
    max_tokens: int = 2048,
    temperature: float = 0.7,
) -> AsyncIterator[str]:
    backend = _load_backend(model_id)
    async for token in backend.stream(
        messages,
        max_tokens=max_tokens,
        temperature=temperature,
    ):
        yield token
