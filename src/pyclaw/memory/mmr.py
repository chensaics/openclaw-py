"""Maximal Marginal Relevance (MMR) re-ranking.

Balances relevance with diversity by iteratively selecting results that
maximize: lambda * relevance - (1 - lambda) * max_similarity_to_selected.

Ported from ``src/memory/mmr.ts`` (Carbonell & Goldstein, 1998).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

_TOKEN_RE = re.compile(r"[a-z0-9_]+")


@dataclass
class MMRConfig:
    enabled: bool = False
    lambda_: float = 0.7


DEFAULT_MMR = MMRConfig()


def tokenize(text: str) -> set[str]:
    """Extract lowercase alphanumeric tokens."""
    return set(_TOKEN_RE.findall(text.lower()))


def jaccard_similarity(set_a: set[str], set_b: set[str]) -> float:
    if not set_a and not set_b:
        return 1.0
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union else 0.0


def text_similarity(a: str, b: str) -> float:
    return jaccard_similarity(tokenize(a), tokenize(b))


def compute_mmr_score(relevance: float, max_similarity: float, lambda_: float) -> float:
    return lambda_ * relevance - (1.0 - lambda_) * max_similarity


def mmr_rerank(
    items: list[dict[str, Any]],
    *,
    config: MMRConfig | None = None,
) -> list[dict[str, Any]]:
    """Re-rank items using MMR.

    Each item must have ``score`` (float) and ``content`` (str) keys.
    Returns a new list in MMR order.
    """
    cfg = config or DEFAULT_MMR
    if not cfg.enabled or len(items) <= 1:
        return list(items)

    lambda_ = max(0.0, min(1.0, cfg.lambda_))
    if lambda_ == 1.0:
        return sorted(items, key=lambda x: x.get("score", 0), reverse=True)

    # Pre-tokenize
    token_cache: dict[int, set[str]] = {}
    for i, item in enumerate(items):
        token_cache[i] = tokenize(item.get("content", ""))

    # Normalize scores to [0, 1]
    scores = [it.get("score", 0.0) for it in items]
    max_s = max(scores)
    min_s = min(scores)
    rng = max_s - min_s

    def norm(s: float) -> float:
        return (s - min_s) / rng if rng else 1.0

    selected: list[dict[str, Any]] = []
    selected_idx: list[int] = []
    remaining = set(range(len(items)))

    while remaining:
        best_idx = -1
        best_mmr = float("-inf")

        for idx in remaining:
            rel = norm(items[idx].get("score", 0.0))
            max_sim = 0.0
            for si in selected_idx:
                sim = jaccard_similarity(token_cache[idx], token_cache[si])
                if sim > max_sim:
                    max_sim = sim
            mmr = compute_mmr_score(rel, max_sim, lambda_)
            if mmr > best_mmr or (mmr == best_mmr and items[idx].get("score", 0) > items[best_idx].get("score", 0) if best_idx >= 0 else True):
                best_mmr = mmr
                best_idx = idx

        if best_idx < 0:
            break
        selected.append(items[best_idx])
        selected_idx.append(best_idx)
        remaining.discard(best_idx)

    return selected


def apply_mmr_to_results(
    results: list[dict[str, Any]],
    *,
    config: MMRConfig | None = None,
) -> list[dict[str, Any]]:
    """Convenience wrapper for hybrid search results (with ``snippet`` key)."""
    if not results:
        return results

    items = []
    for i, r in enumerate(results):
        items.append({**r, "_idx": i, "content": r.get("snippet", r.get("content", ""))})

    reranked = mmr_rerank(items, config=config)

    return [{k: v for k, v in it.items() if k not in ("_idx", "content") or k == "content"} for it in reranked]
