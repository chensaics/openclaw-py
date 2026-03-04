"""Navigation guard — SSRF-safe navigation policy for browser automation.

Integrates with ``security/ssrf.py`` to intercept unsafe navigations.

Provides:
- Pre-navigation URL validation
- Redirect chain checking
- Domain allowlist/blocklist for browser navigations
- Navigation event logging
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from urllib.parse import urlparse

from pyclaw.security.ssrf import SSRFConfig, SSRFGuard

logger = logging.getLogger(__name__)


@dataclass
class NavigationPolicy:
    """Policy for browser navigation safety."""

    enabled: bool = True
    allow_data_urls: bool = False
    allow_blob_urls: bool = False
    allow_javascript_urls: bool = False
    max_redirects: int = 10
    ssrf_config: SSRFConfig = field(default_factory=lambda: SSRFConfig(resolve_dns=False))
    allowed_schemes: frozenset[str] = field(default_factory=lambda: frozenset({"http", "https"}))


@dataclass
class NavigationCheckResult:
    """Result of a navigation safety check."""

    allowed: bool
    url: str
    reason: str = ""
    redirect_count: int = 0


@dataclass
class NavigationEvent:
    """Record of a navigation attempt."""

    url: str
    allowed: bool
    reason: str = ""
    timestamp: float = 0.0

    def __post_init__(self) -> None:
        if self.timestamp == 0:
            self.timestamp = time.time()


class NavigationGuard:
    """SSRF-safe navigation guard for browser automation.

    Checks URLs before allowing Playwright to navigate to them.
    Integrates with the existing SSRF infrastructure.
    """

    def __init__(self, policy: NavigationPolicy | None = None) -> None:
        self._policy = policy or NavigationPolicy()
        self._ssrf_guard = SSRFGuard(self._policy.ssrf_config)
        self._history: list[NavigationEvent] = []
        self._max_history = 200

    def check_url(self, url: str) -> NavigationCheckResult:
        """Check if a URL is safe to navigate to."""
        if not self._policy.enabled:
            return NavigationCheckResult(allowed=True, url=url)

        try:
            parsed = urlparse(url)
        except Exception:
            result = NavigationCheckResult(allowed=False, url=url, reason="Invalid URL")
            self._record(result)
            return result

        scheme = parsed.scheme.lower()

        if scheme == "data" and not self._policy.allow_data_urls:
            result = NavigationCheckResult(allowed=False, url=url, reason="data: URLs blocked")
            self._record(result)
            return result

        if scheme == "blob" and not self._policy.allow_blob_urls:
            result = NavigationCheckResult(allowed=False, url=url, reason="blob: URLs blocked")
            self._record(result)
            return result

        if scheme == "javascript" and not self._policy.allow_javascript_urls:
            result = NavigationCheckResult(allowed=False, url=url, reason="javascript: URLs blocked")
            self._record(result)
            return result

        # Explicitly allowed special schemes — pass through without SSRF check
        if scheme == "data" and self._policy.allow_data_urls:
            return NavigationCheckResult(allowed=True, url=url)
        if scheme == "blob" and self._policy.allow_blob_urls:
            return NavigationCheckResult(allowed=True, url=url)

        # about:blank is always safe
        if url in ("about:blank", "about:srcdoc"):
            return NavigationCheckResult(allowed=True, url=url)

        if scheme and scheme not in self._policy.allowed_schemes:
            result = NavigationCheckResult(allowed=False, url=url, reason=f"Blocked scheme: {scheme}")
            self._record(result)
            return result

        # Delegate to SSRF guard for HTTP(S) URLs
        ssrf_result = self._ssrf_guard.check(url)
        if not ssrf_result.allowed:
            result = NavigationCheckResult(allowed=False, url=url, reason=ssrf_result.reason)
            self._record(result)
            return result

        result = NavigationCheckResult(allowed=True, url=url)
        self._record(result)
        return result

    def check_redirect_chain(self, urls: list[str]) -> NavigationCheckResult:
        """Check a redirect chain for safety."""
        if len(urls) > self._policy.max_redirects:
            return NavigationCheckResult(
                allowed=False,
                url=urls[-1] if urls else "",
                reason=f"Too many redirects ({len(urls)} > {self._policy.max_redirects})",
                redirect_count=len(urls),
            )

        for url in urls:
            result = self.check_url(url)
            if not result.allowed:
                result.redirect_count = urls.index(url)
                return result

        return NavigationCheckResult(
            allowed=True,
            url=urls[-1] if urls else "",
            redirect_count=len(urls),
        )

    def add_allowed_domain(self, domain: str) -> None:
        self._ssrf_guard.add_allowed_domain(domain)

    def add_blocked_domain(self, domain: str) -> None:
        self._ssrf_guard.add_blocked_domain(domain)

    def _record(self, result: NavigationCheckResult) -> None:
        self._history.append(
            NavigationEvent(
                url=result.url,
                allowed=result.allowed,
                reason=result.reason,
            )
        )
        if len(self._history) > self._max_history:
            self._history.pop(0)

    @property
    def blocked_count(self) -> int:
        return self._ssrf_guard.blocked_count

    @property
    def history(self) -> list[NavigationEvent]:
        return list(self._history)

    @property
    def policy(self) -> NavigationPolicy:
        return self._policy
