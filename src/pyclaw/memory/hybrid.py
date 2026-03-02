"""Hybrid search — merge vector + keyword results with decay and MMR.

Ported from ``src/memory/hybrid.ts``.
"""

from __future__ import annotations

from typing import Any

from pyclaw.memory.mmr import DEFAULT_MMR, MMRConfig, apply_mmr_to_results
from pyclaw.memory.temporal_decay import (
    DEFAULT_TEMPORAL_DECAY,
    TemporalDecayConfig,
    apply_temporal_decay,
)


def bm25_rank_to_score(rank: float) -> float:
    """Convert a BM25 rank value to a [0, 1] score."""
    import math
    normalized = max(0.0, rank) if math.isfinite(rank) else 999.0
    return 1.0 / (1.0 + normalized)


def merge_hybrid_results(
    *,
    vector: list[dict[str, Any]] | None = None,
    keyword: list[dict[str, Any]] | None = None,
    vector_weight: float = 0.7,
    text_weight: float = 0.3,
    workspace_dir: str | None = None,
    mmr: MMRConfig | None = None,
    temporal_decay: TemporalDecayConfig | None = None,
    now_ts: float | None = None,
) -> list[dict[str, Any]]:
    """Merge vector and keyword search results into a single scored list.

    Each vector result should have a ``vector_score`` key.
    Each keyword result should have a ``text_score`` key.
    Both need an ``id`` key for deduplication.
    """
    by_id: dict[str, dict[str, Any]] = {}

    for r in (vector or []):
        by_id[r["id"]] = {
            **r,
            "vector_score": r.get("vector_score", 0.0),
            "text_score": 0.0,
        }

    for r in (keyword or []):
        rid = r["id"]
        if rid in by_id:
            by_id[rid]["text_score"] = r.get("text_score", 0.0)
            if r.get("snippet"):
                by_id[rid]["snippet"] = r["snippet"]
        else:
            by_id[rid] = {
                **r,
                "vector_score": 0.0,
                "text_score": r.get("text_score", 0.0),
            }

    merged = []
    for entry in by_id.values():
        score = vector_weight * entry["vector_score"] + text_weight * entry["text_score"]
        merged.append({
            "id": entry["id"],
            "path": entry.get("path", ""),
            "start_line": entry.get("start_line", 0),
            "end_line": entry.get("end_line", 0),
            "score": score,
            "snippet": entry.get("snippet", ""),
            "source": entry.get("source", ""),
            "content": entry.get("content", entry.get("snippet", "")),
        })

    # Temporal decay
    decay_cfg = temporal_decay or DEFAULT_TEMPORAL_DECAY
    decayed = apply_temporal_decay(merged, config=decay_cfg, workspace_dir=workspace_dir, now_ts=now_ts)

    # Sort by score descending
    decayed.sort(key=lambda x: x.get("score", 0.0), reverse=True)

    # MMR re-ranking
    mmr_cfg = mmr or DEFAULT_MMR
    if mmr_cfg.enabled:
        return apply_mmr_to_results(decayed, config=mmr_cfg)

    return decayed
