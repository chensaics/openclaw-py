"""Provider usage tracking — fetch usage from LLM providers.


Queries real provider APIs where available:
- **OpenAI**: ``/organization/usage/completions`` (date-based, requires org-level API key)
- **Anthropic**: ``/v1/messages/count_tokens`` probe (validates key, no public usage API)
- **Google**: key validation via ``generativelanguage.googleapis.com``
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import timezone
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class UsageWindow:
    label: str = ""
    used_percent: float = 0.0
    reset_at: str = ""
    limit: str = ""
    used: str = ""


@dataclass
class ProviderUsageSnapshot:
    provider_id: str = ""
    display_name: str = ""
    windows: list[UsageWindow] = field(default_factory=list)
    error: str = ""


@dataclass
class UsageSummary:
    snapshots: list[ProviderUsageSnapshot] = field(default_factory=list)
    fetched_at: float = 0.0


async def _fetch_openai_usage(api_key: str) -> ProviderUsageSnapshot:
    """Fetch OpenAI usage via the organization usage endpoint.

    Falls back to a simple /v1/models probe if the org billing API
    is unavailable (most individual accounts).
    """
    from datetime import datetime

    import httpx

    today = datetime.now(timezone.utc)
    start = today.replace(day=1).strftime("%Y-%m-%d")
    end = today.strftime("%Y-%m-%d")
    headers = {"Authorization": f"Bearer {api_key}"}

    async with httpx.AsyncClient(timeout=15) as client:
        # Try org usage endpoint first
        try:
            resp = await client.get(
                "https://api.openai.com/v1/organization/usage/completions",
                headers=headers,
                params={"start_date": start, "end_date": end, "limit": 1},
            )
            if resp.status_code == 200:
                data = resp.json()
                buckets = data.get("data", [])
                total_tokens = sum(
                    r.get("input_tokens", 0) + r.get("output_tokens", 0) for b in buckets for r in b.get("results", [])
                )
                return ProviderUsageSnapshot(
                    provider_id="openai",
                    display_name="OpenAI",
                    windows=[
                        UsageWindow(
                            label=f"Month ({start} — {end})",
                            used=f"{total_tokens:,} tokens",
                        )
                    ],
                )
        except httpx.HTTPError:
            pass

        # Fallback: validate key by listing models
        try:
            resp = await client.get(
                "https://api.openai.com/v1/models",
                headers=headers,
                params={"limit": 1},
            )
            if resp.status_code == 200:
                return ProviderUsageSnapshot(
                    provider_id="openai",
                    display_name="OpenAI",
                    windows=[UsageWindow(label="Key status", used="valid")],
                )
            return ProviderUsageSnapshot(
                provider_id="openai",
                display_name="OpenAI",
                error=f"API returned {resp.status_code}",
            )
        except httpx.HTTPError as exc:
            return ProviderUsageSnapshot(
                provider_id="openai",
                display_name="OpenAI",
                error=str(exc),
            )


async def _fetch_anthropic_usage(api_key: str) -> ProviderUsageSnapshot:
    """Validate Anthropic key and report status.

    Anthropic has no public usage/billing API; we validate the key
    by calling the messages endpoint with a minimal payload.
    """
    import httpx

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    async with httpx.AsyncClient(timeout=15) as client:
        try:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json={
                    "model": "claude-3-haiku-20240307",
                    "max_tokens": 1,
                    "messages": [{"role": "user", "content": "hi"}],
                },
            )
            if resp.status_code in (200, 529):
                return ProviderUsageSnapshot(
                    provider_id="anthropic",
                    display_name="Anthropic",
                    windows=[UsageWindow(label="Key status", used="valid")],
                )
            body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
            err_msg = body.get("error", {}).get("message", f"HTTP {resp.status_code}")
            return ProviderUsageSnapshot(
                provider_id="anthropic",
                display_name="Anthropic",
                error=err_msg,
            )
        except httpx.HTTPError as exc:
            return ProviderUsageSnapshot(
                provider_id="anthropic",
                display_name="Anthropic",
                error=str(exc),
            )


async def _fetch_google_usage(api_key: str) -> ProviderUsageSnapshot:
    """Validate Google Generative AI key by listing models."""
    import httpx

    async with httpx.AsyncClient(timeout=15) as client:
        try:
            resp = await client.get(
                "https://generativelanguage.googleapis.com/v1beta/models",
                params={"key": api_key, "pageSize": 1},
            )
            if resp.status_code == 200:
                return ProviderUsageSnapshot(
                    provider_id="google",
                    display_name="Google Gemini",
                    windows=[UsageWindow(label="Key status", used="valid")],
                )
            return ProviderUsageSnapshot(
                provider_id="google",
                display_name="Google Gemini",
                error=f"API returned {resp.status_code}",
            )
        except httpx.HTTPError as exc:
            return ProviderUsageSnapshot(
                provider_id="google",
                display_name="Google Gemini",
                error=str(exc),
            )


PROVIDER_FETCHERS: dict[str, Any] = {
    "anthropic": _fetch_anthropic_usage,
    "openai": _fetch_openai_usage,
    "google": _fetch_google_usage,
}


async def load_provider_usage_summary(
    provider_keys: dict[str, str] | None = None,
) -> UsageSummary:
    """Load usage summaries for configured providers.

    Args:
        provider_keys: mapping of provider_id → api_key.
    """
    keys = provider_keys or {}
    snapshots: list[ProviderUsageSnapshot] = []

    for provider_id, api_key in keys.items():
        fetcher = PROVIDER_FETCHERS.get(provider_id)
        if not fetcher:
            snapshots.append(
                ProviderUsageSnapshot(
                    provider_id=provider_id,
                    display_name=provider_id.title(),
                    error="No usage fetcher available",
                )
            )
            continue
        try:
            snap = await fetcher(api_key)
            snapshots.append(snap)
        except Exception as exc:
            snapshots.append(
                ProviderUsageSnapshot(
                    provider_id=provider_id,
                    display_name=provider_id.title(),
                    error=str(exc),
                )
            )

    return UsageSummary(snapshots=snapshots, fetched_at=time.time())
