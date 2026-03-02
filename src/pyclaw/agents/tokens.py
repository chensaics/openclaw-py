"""Token estimation utilities for session compaction.

Uses a simple character-ratio heuristic by default.
Can be swapped for a proper tokenizer (tiktoken) when available.
"""

from __future__ import annotations

from typing import Any

# Average chars per token across common models (GPT/Claude)
_CHARS_PER_TOKEN = 3.5


def estimate_tokens(text: str) -> int:
    """Estimate the number of tokens in a text string."""
    if not text:
        return 0
    return max(1, int(len(text) / _CHARS_PER_TOKEN))


def estimate_message_tokens(message: dict[str, Any]) -> int:
    """Estimate tokens for a single LLM message dict."""
    # Base overhead per message (role tag, formatting)
    tokens = 4

    content = message.get("content", "")
    if isinstance(content, str):
        tokens += estimate_tokens(content)
    elif isinstance(content, list):
        for block in content:
            if isinstance(block, dict):
                text = block.get("text", "")
                if text:
                    tokens += estimate_tokens(text)
                # Image blocks count as ~85 tokens (low-res estimate)
                if block.get("type") == "image":
                    tokens += 85
            elif isinstance(block, str):
                tokens += estimate_tokens(block)

    # Tool calls
    if tool_calls := message.get("tool_calls"):
        for tc in tool_calls:
            tokens += 10  # function overhead
            fn = tc.get("function", {})
            tokens += estimate_tokens(fn.get("name", ""))
            tokens += estimate_tokens(fn.get("arguments", ""))

    return tokens


def estimate_messages_tokens(messages: list[dict[str, Any]]) -> int:
    """Estimate total tokens for a list of messages."""
    return sum(estimate_message_tokens(m) for m in messages)
