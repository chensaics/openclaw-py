"""llama.cpp backend — local inference via llama-cpp-python."""

from __future__ import annotations

import logging
from typing import Any, AsyncIterator

logger = logging.getLogger(__name__)


class LlamaCppBackend:
    """Wraps llama-cpp-python for local GGUF model inference."""

    def __init__(self, model_path: str, *, n_ctx: int = 4096, n_gpu_layers: int = -1) -> None:
        try:
            from llama_cpp import Llama
        except ImportError as exc:
            raise ImportError(
                "llama-cpp-python is required. Install with: pip install 'pyclaw[llamacpp]'"
            ) from exc

        self._model_path = model_path
        self._llm = Llama(
            model_path=model_path,
            n_ctx=n_ctx,
            n_gpu_layers=n_gpu_layers,
            verbose=False,
        )
        logger.info("Loaded llama.cpp model: %s (n_ctx=%d)", model_path, n_ctx)

    @property
    def backend_name(self) -> str:
        return "llamacpp"

    def generate(
        self,
        messages: list[dict[str, str]],
        *,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        stop: list[str] | None = None,
    ) -> dict[str, Any]:
        result = self._llm.create_chat_completion(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            stop=stop or [],
        )
        return {
            "content": result["choices"][0]["message"]["content"],
            "usage": {
                "prompt_tokens": result.get("usage", {}).get("prompt_tokens", 0),
                "completion_tokens": result.get("usage", {}).get("completion_tokens", 0),
            },
            "model": self._model_path,
            "finish_reason": result["choices"][0].get("finish_reason", "stop"),
        }

    async def stream(
        self,
        messages: list[dict[str, str]],
        *,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        stop: list[str] | None = None,
    ) -> AsyncIterator[str]:
        import asyncio

        stream = self._llm.create_chat_completion(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            stop=stop or [],
            stream=True,
        )
        for chunk in stream:
            delta = chunk["choices"][0].get("delta", {})
            content = delta.get("content", "")
            if content:
                yield content
            await asyncio.sleep(0)

    def close(self) -> None:
        del self._llm
