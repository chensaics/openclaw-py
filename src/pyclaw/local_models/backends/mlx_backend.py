"""MLX backend — local inference on Apple Silicon via mlx-lm."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any, cast

logger = logging.getLogger(__name__)


class MLXBackend:
    """Wraps mlx-lm for local model inference on Apple Silicon."""

    def __init__(self, model_path: str, *, max_tokens: int = 4096) -> None:
        try:
            from mlx_lm import load
        except ImportError as exc:
            raise ImportError("mlx-lm is required for MLX backend. Install with: pip install 'pyclaw[mlx]'") from exc

        self._model_path = model_path
        self._max_tokens = max_tokens
        self._model, self._tokenizer = load(model_path)
        logger.info("Loaded MLX model: %s", model_path)

    @property
    def backend_name(self) -> str:
        return "mlx"

    def _format_messages(self, messages: list[dict[str, str]]) -> str:
        if hasattr(self._tokenizer, "apply_chat_template"):
            return cast(
                str,
                self._tokenizer.apply_chat_template(
                    messages,
                    tokenize=False,
                    add_generation_prompt=True,
                ),
            )
        parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            parts.append(f"<|{role}|>\n{content}")
        parts.append("<|assistant|>\n")
        return "\n".join(parts)

    def generate(
        self,
        messages: list[dict[str, str]],
        *,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        **_kwargs: Any,
    ) -> dict[str, Any]:
        from mlx_lm import generate as mlx_generate

        prompt = self._format_messages(messages)
        result = mlx_generate(
            self._model,
            self._tokenizer,
            prompt=prompt,
            max_tokens=max_tokens,
            temp=temperature,
        )
        return {
            "content": result,
            "usage": {"prompt_tokens": 0, "completion_tokens": 0},
            "model": self._model_path,
            "finish_reason": "stop",
        }

    async def stream(
        self,
        messages: list[dict[str, str]],
        *,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        **_kwargs: Any,
    ) -> AsyncIterator[str]:
        import asyncio

        from mlx_lm import stream_generate

        prompt = self._format_messages(messages)
        for token_text in stream_generate(
            self._model,
            self._tokenizer,
            prompt=prompt,
            max_tokens=max_tokens,
            temp=temperature,
        ):
            if token_text:
                yield token_text
            await asyncio.sleep(0)

    def close(self) -> None:
        del self._model
        del self._tokenizer
