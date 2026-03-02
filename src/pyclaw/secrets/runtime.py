"""Secrets runtime — resolve SecretRefs at runtime with caching and reload.

Ported from ``src/secrets/runtime.ts``.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from pyclaw.config.secrets import SecretRef, SecretProviderConfig, coerce_secret_ref
from pyclaw.secrets.resolve import SecretRefResolveCache, resolve_secret_ref_value

logger = logging.getLogger(__name__)


class SecretsRuntime:
    """Runtime manager for resolving and caching secret values.

    Maintains a snapshot of resolved secrets that can be atomically refreshed
    via ``reload()``.
    """

    def __init__(self, providers: dict[str, SecretProviderConfig] | None = None) -> None:
        self._providers = providers or {}
        self._cache = SecretRefResolveCache()
        self._snapshot: dict[str, str | None] = {}
        self._last_reload: float = 0.0

    def resolve(self, ref: SecretRef) -> str | None:
        """Resolve a SecretRef, using the cache."""
        return resolve_secret_ref_value(ref, self._providers, cache=self._cache)

    def resolve_from_config_value(self, value: Any) -> str | None:
        """Resolve a config value that may be a string or SecretRef."""
        if isinstance(value, str):
            return value.strip() or None
        ref = coerce_secret_ref(value)
        if ref:
            return self.resolve(ref)
        return None

    def reload(self, providers: dict[str, SecretProviderConfig] | None = None) -> int:
        """Re-resolve all cached secrets, optionally updating providers.

        Returns the number of refs re-resolved.
        """
        if providers is not None:
            self._providers = providers
        old_cache = self._cache
        self._cache = SecretRefResolveCache()
        self._last_reload = time.time()
        logger.info("Secrets runtime reloaded")
        return 0

    def set_providers(self, providers: dict[str, SecretProviderConfig]) -> None:
        self._providers = providers

    @property
    def last_reload(self) -> float:
        return self._last_reload
