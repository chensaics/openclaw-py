"""Session cost tracking — token billing, usage aggregation, formatted output.

Ported from ``src/infra/session-cost-usage.ts``.

Provides:
- Per-session cost tracking
- Token-based billing with per-model pricing
- Usage aggregation across sessions
- Cost formatting for display
"""

from __future__ import annotations

import json
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ModelPricing:
    """Pricing for a specific model (per 1M tokens)."""

    model_id: str
    provider: str = ""
    input_per_1m: float = 0.0
    output_per_1m: float = 0.0
    cached_input_per_1m: float = 0.0


# Approximate pricing as of early 2026
DEFAULT_PRICING: dict[str, ModelPricing] = {
    "gpt-4o": ModelPricing("gpt-4o", "openai", 2.50, 10.00),
    "gpt-4o-mini": ModelPricing("gpt-4o-mini", "openai", 0.15, 0.60),
    "o3-mini": ModelPricing("o3-mini", "openai", 1.10, 4.40),
    "claude-sonnet-4-20250514": ModelPricing("claude-sonnet-4-20250514", "anthropic", 3.00, 15.00),
    "claude-3-5-haiku-20241022": ModelPricing("claude-3-5-haiku-20241022", "anthropic", 0.80, 4.00),
    "gemini-2.0-flash": ModelPricing("gemini-2.0-flash", "google", 0.10, 0.40),
    "deepseek-chat": ModelPricing("deepseek-chat", "deepseek", 0.14, 0.28),
}


@dataclass
class TokenUsage:
    """Token usage for a single API call."""

    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    model: str = ""
    timestamp: float = 0.0

    def __post_init__(self) -> None:
        if self.timestamp == 0:
            self.timestamp = time.time()


@dataclass
class SessionCost:
    """Accumulated cost for a session."""

    session_id: str
    entries: list[TokenUsage] = field(default_factory=list)
    custom_pricing: dict[str, ModelPricing] | None = None

    @property
    def total_input_tokens(self) -> int:
        return sum(e.input_tokens for e in self.entries)

    @property
    def total_output_tokens(self) -> int:
        return sum(e.output_tokens for e in self.entries)

    @property
    def total_tokens(self) -> int:
        return self.total_input_tokens + self.total_output_tokens

    def compute_cost(self) -> float:
        """Compute total cost based on model pricing."""
        pricing_db = self.custom_pricing or DEFAULT_PRICING
        total = 0.0
        for entry in self.entries:
            pricing = pricing_db.get(entry.model)
            if not pricing:
                continue
            input_cost = (entry.input_tokens / 1_000_000) * pricing.input_per_1m
            output_cost = (entry.output_tokens / 1_000_000) * pricing.output_per_1m
            cached_cost = (entry.cached_tokens / 1_000_000) * pricing.cached_input_per_1m
            total += input_cost + output_cost + cached_cost
        return total

    def add_usage(self, usage: TokenUsage) -> None:
        self.entries.append(usage)

    @property
    def call_count(self) -> int:
        return len(self.entries)

    def by_model(self) -> dict[str, dict[str, int]]:
        """Aggregate usage by model."""
        result: dict[str, dict[str, int]] = {}
        for entry in self.entries:
            if entry.model not in result:
                result[entry.model] = {"input": 0, "output": 0, "calls": 0}
            result[entry.model]["input"] += entry.input_tokens
            result[entry.model]["output"] += entry.output_tokens
            result[entry.model]["calls"] += 1
        return result


def format_cost(cost: float) -> str:
    """Format a cost value for display."""
    if cost < 0.01:
        return f"${cost:.4f}"
    if cost < 1.0:
        return f"${cost:.3f}"
    return f"${cost:.2f}"


def format_tokens(count: int) -> str:
    """Format a token count for display."""
    if count < 1000:
        return str(count)
    if count < 1_000_000:
        return f"{count / 1000:.1f}K"
    return f"{count / 1_000_000:.2f}M"


def format_session_cost_summary(session_cost: SessionCost) -> str:
    """Format a session cost summary for display."""
    cost = session_cost.compute_cost()
    lines = [
        f"Session: {session_cost.session_id}",
        f"  Calls: {session_cost.call_count}",
        f"  Tokens: {format_tokens(session_cost.total_input_tokens)} in / {format_tokens(session_cost.total_output_tokens)} out",
        f"  Cost: {format_cost(cost)}",
    ]

    by_model = session_cost.by_model()
    if by_model:
        lines.append("  By model:")
        for model, stats in by_model.items():
            lines.append(
                f"    {model}: {format_tokens(stats['input'])} in / {format_tokens(stats['output'])} out ({stats['calls']} calls)"
            )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Usage Aggregation
# ---------------------------------------------------------------------------


class UsageAggregator:
    """Aggregate usage across multiple sessions."""

    def __init__(self) -> None:
        self._sessions: dict[str, SessionCost] = {}

    def get_or_create(self, session_id: str) -> SessionCost:
        if session_id not in self._sessions:
            self._sessions[session_id] = SessionCost(session_id=session_id)
        return self._sessions[session_id]

    def record(self, session_id: str, usage: TokenUsage) -> None:
        session = self.get_or_create(session_id)
        session.add_usage(usage)

    def total_cost(self) -> float:
        return sum(s.compute_cost() for s in self._sessions.values())

    def total_tokens(self) -> int:
        return sum(s.total_tokens for s in self._sessions.values())

    @property
    def session_count(self) -> int:
        return len(self._sessions)

    def summary(self) -> dict[str, Any]:
        return {
            "sessions": self.session_count,
            "total_tokens": self.total_tokens(),
            "total_cost": format_cost(self.total_cost()),
        }


def _usage_log_path(path: Path | None = None) -> Path:
    if path is not None:
        return path
    from pyclaw.config.paths import resolve_state_dir

    return resolve_state_dir() / "usage" / "usage.jsonl"


def record_usage(
    *,
    session_id: str,
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cached_tokens: int = 0,
    has_api_key: bool = True,
    timestamp: float | None = None,
    path: Path | None = None,
) -> None:
    """Append one usage event to the persistent usage ledger."""
    usage = TokenUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cached_tokens=cached_tokens,
        model=model,
        timestamp=timestamp or time.time(),
    )
    session_cost = SessionCost(session_id=session_id, entries=[usage])
    estimated_cost_value = session_cost.compute_cost() if has_api_key else 0.0

    entry = {
        "timestamp": usage.timestamp,
        "session_id": session_id,
        "provider": provider,
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cached_tokens": cached_tokens,
        "total_tokens": input_tokens + output_tokens,
        "has_api_key": has_api_key,
        "estimated_cost_value": estimated_cost_value,
    }
    usage_path = _usage_log_path(path)
    usage_path.parent.mkdir(parents=True, exist_ok=True)
    with usage_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def aggregate_usage(*, days: int = 7, path: Path | None = None) -> dict[str, Any]:
    """Aggregate persisted usage entries by provider/model/session."""
    now = time.time()
    cutoff = now - max(days, 1) * 86400
    usage_path = _usage_log_path(path)

    providers: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "calls": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "estimated_cost_value": 0.0,
        }
    )
    models: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "calls": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "estimated_cost_value": 0.0,
        }
    )
    sessions: set[str] = set()
    totals = {
        "calls": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "estimated_cost_value": 0.0,
    }

    if usage_path.exists():
        with usage_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ts = float(row.get("timestamp", 0.0) or 0.0)
                if ts < cutoff:
                    continue

                provider = str(row.get("provider", "unknown") or "unknown")
                model = str(row.get("model", "unknown") or "unknown")
                session_id = str(row.get("session_id", "") or "")
                input_tokens = int(row.get("input_tokens", 0) or 0)
                output_tokens = int(row.get("output_tokens", 0) or 0)
                total_tokens = int(row.get("total_tokens", input_tokens + output_tokens) or 0)
                estimated_cost_value = float(row.get("estimated_cost_value", 0.0) or 0.0)

                if session_id:
                    sessions.add(session_id)

                totals["calls"] += 1
                totals["input_tokens"] += input_tokens
                totals["output_tokens"] += output_tokens
                totals["total_tokens"] += total_tokens
                totals["estimated_cost_value"] += estimated_cost_value

                p = providers[provider]
                p["calls"] += 1
                p["input_tokens"] += input_tokens
                p["output_tokens"] += output_tokens
                p["total_tokens"] += total_tokens
                p["estimated_cost_value"] += estimated_cost_value

                m = models[model]
                m["calls"] += 1
                m["input_tokens"] += input_tokens
                m["output_tokens"] += output_tokens
                m["total_tokens"] += total_tokens
                m["estimated_cost_value"] += estimated_cost_value

    by_provider = dict(sorted(providers.items(), key=lambda kv: kv[0]))
    by_model = dict(sorted(models.items(), key=lambda kv: kv[0]))
    for data in by_provider.values():
        data["estimated_cost"] = format_cost(float(data["estimated_cost_value"]))
    for data in by_model.values():
        data["estimated_cost"] = format_cost(float(data["estimated_cost_value"]))

    return {
        "window_days": days,
        "sessions": len(sessions),
        "calls": totals["calls"],
        "total_input_tokens": totals["input_tokens"],
        "total_output_tokens": totals["output_tokens"],
        "total_tokens": totals["total_tokens"],
        "estimated_cost_value": totals["estimated_cost_value"],
        "estimated_cost": format_cost(float(totals["estimated_cost_value"])),
        "by_provider": by_provider,
        "by_model": by_model,
    }


def summarize_session_usage(
    session_id: str,
    *,
    days: int = 30,
    path: Path | None = None,
) -> dict[str, Any]:
    """Return usage summary for one session from the persistent ledger."""
    now = time.time()
    cutoff = now - max(days, 1) * 86400
    usage_path = _usage_log_path(path)

    summary: dict[str, Any] = {
        "session_id": session_id,
        "calls": 0,
        "session_tokens": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "estimated_cost_value": 0.0,
        "estimated_cost": format_cost(0.0),
    }
    if not usage_path.exists():
        return summary

    with usage_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if str(row.get("session_id", "")) != session_id:
                continue
            ts = float(row.get("timestamp", 0.0) or 0.0)
            if ts < cutoff:
                continue
            input_tokens = int(row.get("input_tokens", 0) or 0)
            output_tokens = int(row.get("output_tokens", 0) or 0)
            summary["calls"] += 1
            summary["input_tokens"] += input_tokens
            summary["output_tokens"] += output_tokens
            summary["session_tokens"] += int(row.get("total_tokens", input_tokens + output_tokens) or 0)
            summary["estimated_cost_value"] += float(row.get("estimated_cost_value", 0.0) or 0.0)

    summary["estimated_cost"] = format_cost(float(summary["estimated_cost_value"]))
    return summary


def aggregate_usage_daily(*, days: int = 7, path: Path | None = None) -> list[dict[str, Any]]:
    """Aggregate usage by day. Returns list of {date: YYYY-MM-DD, tokens: int}."""
    import datetime as dt

    now = time.time()
    cutoff = now - max(days, 1) * 86400
    usage_path = _usage_log_path(path)
    daily: dict[str, int] = defaultdict(int)

    if usage_path.exists():
        with usage_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ts = float(row.get("timestamp", 0.0) or 0.0)
                if ts < cutoff:
                    continue
                inp = int(row.get("input_tokens", 0) or 0)
                out = int(row.get("output_tokens", 0) or 0)
                raw_total = row.get("total_tokens") or (inp + out)
                total_tokens = int(raw_total)
                d = dt.datetime.fromtimestamp(ts, tz=dt.UTC).strftime("%Y-%m-%d")
                daily[d] += total_tokens

    dates = sorted(daily.keys())
    return [{"date": d, "tokens": daily[d]} for d in dates]


def aggregate_usage_hourly(*, days: int = 7, path: Path | None = None) -> list[int]:
    """Aggregate usage by hour (0-23). Returns 24-element list of token counts."""
    now = time.time()
    cutoff = now - max(days, 1) * 86400
    usage_path = _usage_log_path(path)
    hourly: list[int] = [0] * 24

    if usage_path.exists():
        import datetime as dt

        with usage_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ts = float(row.get("timestamp", 0.0) or 0.0)
                if ts < cutoff:
                    continue
                inp = int(row.get("input_tokens", 0) or 0)
                out = int(row.get("output_tokens", 0) or 0)
                raw_total = row.get("total_tokens") or (inp + out)
                total_tokens = int(raw_total)
                hour = dt.datetime.fromtimestamp(ts, tz=dt.UTC).hour
                hourly[hour] += total_tokens

    return hourly


def list_sessions_with_usage(
    *,
    days: int = 7,
    sort: str = "tokens",
    limit: int = 50,
    path: Path | None = None,
) -> list[dict[str, Any]]:
    """List sessions with token usage from the ledger, sorted by tokens or updated."""
    now = time.time()
    cutoff = now - max(days, 1) * 86400
    usage_path = _usage_log_path(path)
    by_session: dict[str, dict[str, Any]] = {}

    if usage_path.exists():
        with usage_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ts = float(row.get("timestamp", 0.0) or 0.0)
                if ts < cutoff:
                    continue
                session_id = str(row.get("session_id", "") or "")
                if not session_id:
                    continue
                if session_id not in by_session:
                    by_session[session_id] = {
                        "sessionKey": session_id,
                        "path": session_id,
                        "tokens": 0,
                        "inputTokens": 0,
                        "outputTokens": 0,
                        "updated": ts,
                        "calls": 0,
                    }
                s = by_session[session_id]
                inp = int(row.get("input_tokens", 0) or 0)
                out = int(row.get("output_tokens", 0) or 0)
                tot = int(row.get("total_tokens", inp + out) or inp + out)
                s["tokens"] += tot
                s["inputTokens"] += inp
                s["outputTokens"] += out
                s["calls"] += 1
                s["updated"] = max(s["updated"], ts)

    result = list(by_session.values())
    if sort == "tokens":
        result.sort(key=lambda x: -x["tokens"])
    else:
        result.sort(key=lambda x: -x["updated"])
    return result[:limit]
