"""Ollama enhanced — autodiscovery hardening, context window unification, log downgrade.

Ported from ``src/agents/providers/ollama/`` enhancements.

Provides:
- Hardened autodiscovery with timeout, validation, and graceful degradation
- Unified context window resolution across model metadata variants
- Log-level downgrade for empty discovery (warn → debug on repeat)
- Model capability detection from Ollama model info
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_DISCOVERY_TIMEOUT_S = 5.0
DEFAULT_DISCOVERY_RETRY_INTERVAL_S = 60.0


@dataclass
class OllamaModelInfo:
    """Parsed model information from Ollama API."""

    name: str
    size: int = 0
    parameter_size: str = ""
    quantization_level: str = ""
    context_length: int = 0
    family: str = ""
    families: list[str] = field(default_factory=list)
    supports_vision: bool = False
    supports_tools: bool = False
    modified_at: str = ""


@dataclass
class DiscoveryState:
    """State tracking for autodiscovery."""

    last_attempt_at: float = 0.0
    last_success_at: float = 0.0
    consecutive_failures: int = 0
    empty_count: int = 0
    models: list[OllamaModelInfo] = field(default_factory=list)

    @property
    def is_healthy(self) -> bool:
        return self.last_success_at > 0 and self.consecutive_failures == 0


def parse_ollama_model_info(raw: dict[str, Any]) -> OllamaModelInfo:
    """Parse a model entry from the Ollama ``/api/tags`` response."""
    name = raw.get("name", raw.get("model", ""))

    details = raw.get("details", {})
    model_info = raw.get("model_info", {})

    # Context window: check multiple locations
    context_length = 0
    for key in [
        "context_length",
        "num_ctx",
        "context_window",
    ]:
        val = model_info.get(key, details.get(key, 0))
        if val:
            context_length = int(val)
            break

    # Also check top-level modelfile metadata
    if not context_length:
        for key_prefix in ["llama.", "general.", ""]:
            val = model_info.get(f"{key_prefix}context_length", 0)
            if val:
                context_length = int(val)
                break

    # Family detection
    family = details.get("family", "")
    families = details.get("families", [])
    if not families and family:
        families = [family]

    # Vision support
    supports_vision = "clip" in families or any("vision" in f.lower() for f in families)

    # Tool support heuristic
    supports_tools = any(f in families for f in ["llama", "qwen2", "mistral", "command-r"])

    return OllamaModelInfo(
        name=name,
        size=raw.get("size", 0),
        parameter_size=details.get("parameter_size", ""),
        quantization_level=details.get("quantization_level", ""),
        context_length=context_length,
        family=family,
        families=families,
        supports_vision=supports_vision,
        supports_tools=supports_tools,
        modified_at=raw.get("modified_at", ""),
    )


def resolve_context_window(
    model_info: OllamaModelInfo,
    *,
    user_override: int = 0,
    default: int = 4096,
) -> int:
    """Resolve the effective context window for an Ollama model.

    Priority: user override > model metadata > family defaults > global default.
    """
    if user_override > 0:
        return user_override

    if model_info.context_length > 0:
        return model_info.context_length

    # Family-based defaults
    family_defaults: dict[str, int] = {
        "llama": 8192,
        "qwen2": 32768,
        "mistral": 32768,
        "gemma": 8192,
        "phi": 4096,
        "command-r": 131072,
        "deepseek": 16384,
    }

    family = model_info.family.lower()
    if family in family_defaults:
        return family_defaults[family]

    for fam in model_info.families:
        if fam.lower() in family_defaults:
            return family_defaults[fam.lower()]

    return default


class OllamaDiscovery:
    """Hardened Ollama model autodiscovery with graceful degradation."""

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_OLLAMA_BASE_URL,
        timeout_s: float = DEFAULT_DISCOVERY_TIMEOUT_S,
        retry_interval_s: float = DEFAULT_DISCOVERY_RETRY_INTERVAL_S,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_s = timeout_s
        self._retry_interval_s = retry_interval_s
        self._state = DiscoveryState()

    @property
    def state(self) -> DiscoveryState:
        return self._state

    @property
    def models(self) -> list[OllamaModelInfo]:
        return self._state.models

    def should_retry(self) -> bool:
        """Check if enough time has passed for a retry."""
        if self._state.last_attempt_at == 0:
            return True
        elapsed = time.time() - self._state.last_attempt_at
        return elapsed >= self._retry_interval_s

    def process_discovery_response(
        self,
        response: dict[str, Any] | None,
        *,
        error: str = "",
    ) -> list[OllamaModelInfo]:
        """Process the result of a discovery attempt.

        Handles success, empty results, and errors with log-level degradation.
        """
        now = time.time()
        self._state.last_attempt_at = now

        if error:
            self._state.consecutive_failures += 1
            if self._state.consecutive_failures <= 3:
                logger.warning("Ollama discovery failed: %s", error)
            else:
                logger.debug("Ollama discovery failed (repeated): %s", error)
            return self._state.models

        if response is None:
            self._state.consecutive_failures += 1
            return self._state.models

        models_raw = response.get("models", [])

        if not models_raw:
            self._state.empty_count += 1
            if self._state.empty_count <= 2:
                logger.warning("Ollama discovery returned empty model list")
            else:
                logger.debug("Ollama discovery empty (repeated, count=%d)", self._state.empty_count)
            self._state.last_success_at = now
            self._state.consecutive_failures = 0
            self._state.models = []
            return []

        models = [parse_ollama_model_info(m) for m in models_raw]

        self._state.last_success_at = now
        self._state.consecutive_failures = 0
        self._state.empty_count = 0
        self._state.models = models

        logger.info("Ollama discovery found %d models", len(models))
        return models

    def get_model(self, name: str) -> OllamaModelInfo | None:
        """Get a discovered model by name (case-insensitive)."""
        name_lower = name.lower()
        for m in self._state.models:
            if m.name.lower() == name_lower:
                return m
        return None
