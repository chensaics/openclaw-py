"""Block streaming — per-provider coalescing, paragraph flushing, chunk sizing.

Ported from ``src/auto-reply/reply/block-streaming.ts``.

Provides:
- Per-provider min/max char configuration for streaming chunks
- Paragraph-boundary flushing
- Block coalescing (merge small chunks)
- Streaming directive filtering (strip @directives from stream)
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass

_DIRECTIVE_RE = re.compile(r"@(think|model|verbose|reasoning|elevated|exec)\b\s*\S*", re.IGNORECASE)


@dataclass
class StreamingConfig:
    """Per-provider streaming configuration."""

    min_chars: int = 20
    max_chars: int = 4000
    paragraph_flush: bool = True
    coalesce_ms: int = 100
    strip_directives: bool = True


DEFAULT_CONFIGS: dict[str, StreamingConfig] = {
    "openai": StreamingConfig(min_chars=15, max_chars=4000),
    "anthropic": StreamingConfig(min_chars=20, max_chars=4000),
    "google": StreamingConfig(min_chars=25, max_chars=4000),
    "ollama": StreamingConfig(min_chars=10, max_chars=4000, coalesce_ms=50),
}


def get_streaming_config(provider: str) -> StreamingConfig:
    return DEFAULT_CONFIGS.get(provider, StreamingConfig())


@dataclass
class StreamBlock:
    """A coalesced block of streamed text ready for delivery."""

    text: str
    index: int
    is_final: bool = False
    flushed_at: float = 0.0


class BlockCoalescer:
    """Coalesce streaming chunks into delivery-sized blocks."""

    def __init__(self, config: StreamingConfig | None = None) -> None:
        self._config = config or StreamingConfig()
        self._buffer = ""
        self._block_index = 0
        self._last_emit_time = 0.0
        self._total_chars = 0

    def feed(self, chunk: str) -> list[StreamBlock]:
        """Feed a streaming chunk. Returns blocks ready for delivery."""
        if self._config.strip_directives:
            chunk = _DIRECTIVE_RE.sub("", chunk)

        self._buffer += chunk
        self._total_chars += len(chunk)

        blocks: list[StreamBlock] = []
        now = time.time()

        while self._should_emit(now):
            block = self._emit_block(now)
            if block:
                blocks.append(block)

        return blocks

    def flush(self) -> StreamBlock | None:
        """Flush remaining buffer as a final block."""
        if not self._buffer:
            return None

        text = self._buffer.strip()
        self._buffer = ""
        if not text:
            return None

        block = StreamBlock(
            text=text,
            index=self._block_index,
            is_final=True,
            flushed_at=time.time(),
        )
        self._block_index += 1
        return block

    def _should_emit(self, now: float) -> bool:
        if len(self._buffer) < self._config.min_chars:
            return False

        if len(self._buffer) >= self._config.max_chars:
            return True

        # Paragraph boundary
        if self._config.paragraph_flush and "\n\n" in self._buffer:
            return True

        # Coalesce timeout
        elapsed_ms = (now - self._last_emit_time) * 1000 if self._last_emit_time else float("inf")
        return bool(elapsed_ms >= self._config.coalesce_ms and len(self._buffer) >= self._config.min_chars)

    def _emit_block(self, now: float) -> StreamBlock | None:
        if not self._buffer:
            return None

        # Try paragraph split
        if self._config.paragraph_flush:
            para_pos = self._buffer.find("\n\n")
            if para_pos > 0:
                text = self._buffer[:para_pos].strip()
                self._buffer = self._buffer[para_pos + 2 :]
                if text:
                    self._last_emit_time = now
                    block = StreamBlock(text=text, index=self._block_index, flushed_at=now)
                    self._block_index += 1
                    return block

        # Max-chars hard split
        if len(self._buffer) >= self._config.max_chars:
            text = self._buffer[: self._config.max_chars]
            self._buffer = self._buffer[self._config.max_chars :]

            # Try to split at last sentence/line
            for sep in ["\n", ". ", "! ", "? "]:
                pos = text.rfind(sep)
                if pos > len(text) // 4:
                    self._buffer = text[pos + len(sep) :] + self._buffer
                    text = text[: pos + len(sep)]
                    break

            text = text.strip()
            if text:
                self._last_emit_time = now
                block = StreamBlock(text=text, index=self._block_index, flushed_at=now)
                self._block_index += 1
                return block

        # Min-chars emit
        if len(self._buffer) >= self._config.min_chars:
            text = self._buffer.strip()
            self._buffer = ""
            if text:
                self._last_emit_time = now
                block = StreamBlock(text=text, index=self._block_index, flushed_at=now)
                self._block_index += 1
                return block

        return None

    @property
    def buffer_size(self) -> int:
        return len(self._buffer)

    @property
    def total_chars(self) -> int:
        return self._total_chars

    @property
    def block_count(self) -> int:
        return self._block_index

    def reset(self) -> None:
        self._buffer = ""
        self._block_index = 0
        self._last_emit_time = 0.0
        self._total_chars = 0
