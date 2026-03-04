"""Models deep — probe, scan, set default, auth overview, table formatting.

Ported from ``src/commands/models*.ts``.

Provides:
- Model probe: availability testing for a specific model
- Model scan: test all configured providers
- Set default model
- Auth overview: which providers are configured
- Table formatting for model lists
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ProbeResult:
    """Result of probing a model's availability."""
    model: str
    provider: str
    available: bool
    latency_ms: float = 0.0
    error: str = ""
    context_window: int = 0
    supports_tools: bool = False
    supports_vision: bool = False
    supports_streaming: bool = True


@dataclass
class ScanResult:
    """Result of scanning all providers."""
    results: list[ProbeResult] = field(default_factory=list)
    total_providers: int = 0
    available_count: int = 0
    scan_duration_ms: float = 0.0

    @property
    def unavailable_count(self) -> int:
        return self.total_providers - self.available_count


@dataclass
class AuthOverviewEntry:
    """Auth status for a provider."""
    provider: str
    configured: bool
    auth_method: str = ""  # api_key | oauth | none
    key_prefix: str = ""
    expires_at: float = 0.0

    @property
    def is_expired(self) -> bool:
        return self.expires_at > 0 and time.time() > self.expires_at


def probe_model(
    model: str,
    provider: str,
    *,
    api_key: str = "",
    timeout_s: float = 10.0,
) -> ProbeResult:
    """Probe a model for availability (sync, non-network)."""
    from pyclaw.agents.model_catalog import ModelCatalog as _MC

    cat = _MC()
    info = cat.get(provider, model)
    caps: dict[str, Any] = {}
    if info:
        caps = {"context": info.context_window, "tools": info.supports_tools, "vision": info.supports_vision}
    if not api_key and provider not in ("ollama", "lmstudio"):
        return ProbeResult(
            model=model, provider=provider, available=False,
            error="No API key configured",
        )

    return ProbeResult(
        model=model,
        provider=provider,
        available=True,
        context_window=caps.get("context", 0),
        supports_tools=caps.get("tools", False),
        supports_vision=caps.get("vision", False),
    )


def scan_providers(
    providers: dict[str, str],
) -> ScanResult:
    """Scan all configured providers for availability."""
    start = time.time()
    results: list[ProbeResult] = []

    from pyclaw.agents.model_catalog import ModelCatalog as _MC

    _cat = _MC()

    for provider, api_key in providers.items():
        model = _cat.default_model_for_provider(provider) or "unknown"
        result = probe_model(model, provider, api_key=api_key)
        results.append(result)

    return ScanResult(
        results=results,
        total_providers=len(providers),
        available_count=sum(1 for r in results if r.available),
        scan_duration_ms=(time.time() - start) * 1000,
    )


def get_auth_overview(
    providers: dict[str, str],
) -> list[AuthOverviewEntry]:
    """Get auth configuration overview for all providers."""
    entries: list[AuthOverviewEntry] = []
    for provider, key in providers.items():
        entries.append(AuthOverviewEntry(
            provider=provider,
            configured=bool(key),
            auth_method="api_key" if key else "none",
            key_prefix=key[:8] + "..." if key and len(key) > 8 else "",
        ))
    return entries


@dataclass
class ModelDefaultConfig:
    """Current default model configuration."""
    model: str = ""
    provider: str = ""
    image_model: str = ""
    fallback_model: str = ""


def set_default_model(
    current: ModelDefaultConfig,
    *,
    model: str = "",
    provider: str = "",
    image_model: str = "",
) -> ModelDefaultConfig:
    """Set the default model, returning updated config."""
    return ModelDefaultConfig(
        model=model or current.model,
        provider=provider or current.provider,
        image_model=image_model or current.image_model,
        fallback_model=current.fallback_model,
    )


# ---------------------------------------------------------------------------
# Table formatting
# ---------------------------------------------------------------------------

def format_models_table(
    results: list[ProbeResult],
) -> str:
    """Format probe results as a text table."""
    if not results:
        return "No models found."

    lines: list[str] = []
    lines.append(f"{'Model':<25} {'Provider':<12} {'Status':<10} {'Context':<10} {'Tools':<6} {'Vision':<6}")
    lines.append("-" * 75)

    for r in results:
        status = "OK" if r.available else "FAIL"
        ctx = f"{r.context_window // 1000}K" if r.context_window else "-"
        tools = "Yes" if r.supports_tools else "No"
        vision = "Yes" if r.supports_vision else "No"
        lines.append(f"{r.model:<25} {r.provider:<12} {status:<10} {ctx:<10} {tools:<6} {vision:<6}")

    return "\n".join(lines)


def format_auth_table(entries: list[AuthOverviewEntry]) -> str:
    """Format auth overview as a text table."""
    if not entries:
        return "No providers configured."

    lines: list[str] = []
    lines.append(f"{'Provider':<15} {'Status':<12} {'Method':<10} {'Key':<15}")
    lines.append("-" * 55)

    for e in entries:
        status = "Configured" if e.configured else "Missing"
        lines.append(f"{e.provider:<15} {status:<12} {e.auth_method:<10} {e.key_prefix:<15}")

    return "\n".join(lines)
