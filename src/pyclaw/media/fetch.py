"""Media fetch — download remote media with caching, size limits, and MIME validation.

Provides a unified ``fetch_media`` function used by channels, browser tool,
and other subsystems that need to retrieve remote media files.
"""

from __future__ import annotations

import hashlib
import logging
import mimetypes
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_MAX_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB
DEFAULT_TIMEOUT_S = 60.0

ALLOWED_MIME_PREFIXES = ("image/", "audio/", "video/", "application/pdf")


class FetchResult:
    """Result of a media fetch operation."""

    __slots__ = ("path", "mime_type", "size", "url", "cached", "error")

    def __init__(
        self,
        *,
        path: str = "",
        mime_type: str = "",
        size: int = 0,
        url: str = "",
        cached: bool = False,
        error: str = "",
    ) -> None:
        self.path = path
        self.mime_type = mime_type
        self.size = size
        self.url = url
        self.cached = cached
        self.error = error

    @property
    def ok(self) -> bool:
        return bool(self.path) and not self.error

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "mimeType": self.mime_type,
            "size": self.size,
            "url": self.url,
            "cached": self.cached,
            "error": self.error,
        }


class MediaFetcher:
    """Download remote media files with caching and validation."""

    def __init__(
        self,
        *,
        cache_dir: Path | None = None,
        max_size: int = DEFAULT_MAX_SIZE_BYTES,
        timeout: float = DEFAULT_TIMEOUT_S,
        allowed_mimes: tuple[str, ...] | None = None,
    ) -> None:
        self._cache_dir = cache_dir or Path(tempfile.gettempdir()) / "pyclaw-media-cache"
        self._max_size = max_size
        self._timeout = timeout
        self._allowed_mimes = allowed_mimes or ALLOWED_MIME_PREFIXES

    def _cache_key(self, url: str) -> str:
        return hashlib.sha256(url.encode()).hexdigest()[:24]

    def _check_cache(self, url: str) -> FetchResult | None:
        key = self._cache_key(url)
        for p in self._cache_dir.iterdir() if self._cache_dir.exists() else []:
            if p.stem == key:
                mime = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
                return FetchResult(
                    path=str(p),
                    mime_type=mime,
                    size=p.stat().st_size,
                    url=url,
                    cached=True,
                )
        return None

    async def fetch(self, url: str) -> FetchResult:
        """Download a remote media file. Returns a FetchResult."""
        cached = self._check_cache(url)
        if cached:
            return cached

        try:
            import httpx
        except ImportError:
            return FetchResult(url=url, error="httpx not installed")

        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
                follow_redirects=True,
                limits=httpx.Limits(max_connections=5),
            ) as client:
                async with client.stream("GET", url) as resp:
                    resp.raise_for_status()

                    content_type = resp.headers.get("content-type", "")
                    mime = content_type.split(";")[0].strip() or "application/octet-stream"

                    if not any(mime.startswith(p) for p in self._allowed_mimes):
                        return FetchResult(
                            url=url,
                            mime_type=mime,
                            error=f"MIME type '{mime}' not allowed",
                        )

                    content_length = int(resp.headers.get("content-length", 0))
                    if content_length > self._max_size:
                        return FetchResult(
                            url=url,
                            size=content_length,
                            error=f"File too large ({content_length} > {self._max_size})",
                        )

                    chunks: list[bytes] = []
                    total = 0
                    async for chunk in resp.aiter_bytes(chunk_size=65536):
                        total += len(chunk)
                        if total > self._max_size:
                            return FetchResult(
                                url=url,
                                size=total,
                                error=f"Download exceeded size limit ({self._max_size})",
                            )
                        chunks.append(chunk)

            data = b"".join(chunks)

            self._cache_dir.mkdir(parents=True, exist_ok=True)
            ext = mimetypes.guess_extension(mime) or ".bin"
            key = self._cache_key(url)
            file_path = self._cache_dir / f"{key}{ext}"
            file_path.write_bytes(data)

            return FetchResult(
                path=str(file_path),
                mime_type=mime,
                size=len(data),
                url=url,
            )

        except httpx.HTTPStatusError as exc:
            return FetchResult(url=url, error=f"HTTP {exc.response.status_code}")
        except httpx.HTTPError as exc:
            return FetchResult(url=url, error=str(exc))
        except Exception as exc:
            logger.debug("Media fetch error", exc_info=True)
            return FetchResult(url=url, error=str(exc))

    def clear_cache(self) -> int:
        """Remove all cached files. Returns count of removed files."""
        if not self._cache_dir.exists():
            return 0
        count = 0
        for p in self._cache_dir.iterdir():
            if p.is_file():
                p.unlink()
                count += 1
        return count


_default_fetcher: MediaFetcher | None = None


def get_media_fetcher() -> MediaFetcher:
    """Get or create the default MediaFetcher singleton."""
    global _default_fetcher
    if _default_fetcher is None:
        _default_fetcher = MediaFetcher()
    return _default_fetcher


async def fetch_media(url: str) -> FetchResult:
    """Convenience function: fetch a remote media file."""
    return await get_media_fetcher().fetch(url)
