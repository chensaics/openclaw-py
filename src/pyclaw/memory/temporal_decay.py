"""Temporal decay scoring for memory search results.

Applies exponential time-based decay so that recent memories
score higher than old ones, unless marked as evergreen.

Ported from ``src/memory/temporal-decay.ts``.
"""

from __future__ import annotations

import math
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DAY_SECONDS = 86400
_DATED_PATH_RE = re.compile(r"(?:^|/)memory/(\d{4})-(\d{2})-(\d{2})\.md$")


@dataclass
class TemporalDecayConfig:
    enabled: bool = False
    half_life_days: float = 30.0


DEFAULT_TEMPORAL_DECAY = TemporalDecayConfig()


def to_decay_lambda(half_life_days: float) -> float:
    if half_life_days <= 0 or not math.isfinite(half_life_days):
        return 0.0
    return math.log(2) / half_life_days


def calculate_decay_multiplier(age_days: float, half_life_days: float) -> float:
    lam = to_decay_lambda(half_life_days)
    clamped = max(0.0, age_days)
    if lam <= 0 or not math.isfinite(clamped):
        return 1.0
    return math.exp(-lam * clamped)


def apply_decay_to_score(score: float, age_days: float, half_life_days: float) -> float:
    return score * calculate_decay_multiplier(age_days, half_life_days)


def _parse_date_from_path(file_path: str) -> float | None:
    """Try to extract a date from a memory file path like ``memory/2025-01-15.md``."""
    normalized = file_path.replace("\\", "/").lstrip("./")
    m = _DATED_PATH_RE.search(normalized)
    if not m:
        return None
    import datetime

    try:
        dt = datetime.datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=datetime.timezone.utc)
        return dt.timestamp()
    except ValueError:
        return None


def _is_evergreen(file_path: str) -> bool:
    """Evergreen files (MEMORY.md, memory/<topic>.md without date) don't decay."""
    normalized = file_path.replace("\\", "/").lstrip("./")
    if normalized.lower() in ("memory.md",):
        return True
    if not normalized.startswith("memory/"):
        return False
    return not _DATED_PATH_RE.search(normalized)


def _extract_timestamp(file_path: str, workspace_dir: str | None = None) -> float | None:
    """Get a timestamp for a memory file."""
    from_path = _parse_date_from_path(file_path)
    if from_path is not None:
        return from_path

    if _is_evergreen(file_path):
        return None

    if workspace_dir:
        p = Path(workspace_dir) / file_path if not Path(file_path).is_absolute() else Path(file_path)
        try:
            return p.stat().st_mtime
        except OSError:
            pass
    return None


def apply_temporal_decay(
    results: list[dict[str, Any]],
    *,
    config: TemporalDecayConfig | None = None,
    workspace_dir: str | None = None,
    now_ts: float | None = None,
) -> list[dict[str, Any]]:
    """Apply temporal decay to a list of result dicts with ``score`` and ``path`` keys."""
    cfg = config or DEFAULT_TEMPORAL_DECAY
    if not cfg.enabled:
        return list(results)

    now = now_ts if now_ts is not None else time.time()
    out: list[dict[str, Any]] = []

    for entry in results:
        ts = _extract_timestamp(entry.get("path", ""), workspace_dir)
        if ts is None:
            out.append(entry)
            continue
        age_days = max(0.0, (now - ts) / DAY_SECONDS)
        new_score = apply_decay_to_score(entry.get("score", 0.0), age_days, cfg.half_life_days)
        out.append({**entry, "score": new_score})

    return out
