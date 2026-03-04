"""Link understanding — URL parsing, Open Graph metadata extraction, and summarization.

Ported from ``src/link-understanding/`` in the TypeScript codebase.

Provides:
- URL extraction from text
- Open Graph / meta tag parsing
- Content type detection (article, video, image, document)
- Link metadata formatting for agent context injection
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


@dataclass
class LinkMetadata:
    """Extracted metadata from a URL."""

    url: str
    title: str = ""
    description: str = ""
    site_name: str = ""
    content_type: str = ""  # "article" | "video" | "image" | "document" | "unknown"
    og_image: str = ""
    og_type: str = ""
    author: str = ""
    published_date: str = ""
    domain: str = ""
    is_valid: bool = True
    error: str = ""


# ---------------------------------------------------------------------------
# URL extraction
# ---------------------------------------------------------------------------

_URL_PATTERN = re.compile(
    r"https?://[^\s<>\"')\]]+",
    re.IGNORECASE,
)

_IGNORED_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".svg",
    ".ico",
    ".mp3",
    ".mp4",
    ".wav",
    ".ogg",
    ".webm",
    ".zip",
    ".tar",
    ".gz",
    ".rar",
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
}


def extract_urls(text: str) -> list[str]:
    """Extract HTTP/HTTPS URLs from text.

    Deduplicates and preserves order.
    """
    matches = _URL_PATTERN.findall(text)
    seen: set[str] = set()
    result: list[str] = []

    for url in matches:
        # Strip trailing punctuation
        url = url.rstrip(".,;:!?)")
        if url not in seen:
            seen.add(url)
            result.append(url)

    return result


def classify_url_content_type(url: str) -> str:
    """Classify a URL's likely content type from its path/extension."""
    parsed = urlparse(url)
    path = parsed.path.lower()

    for ext in _IGNORED_EXTENSIONS:
        if path.endswith(ext):
            if ext in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"):
                return "image"
            if ext in (".mp3", ".wav", ".ogg"):
                return "audio"
            if ext in (".mp4", ".webm"):
                return "video"
            if ext in (".pdf", ".doc", ".docx"):
                return "document"
            return "file"

    # Video platforms
    video_domains = {"youtube.com", "youtu.be", "vimeo.com", "twitch.tv"}
    domain = parsed.netloc.lower().removeprefix("www.")
    if domain in video_domains:
        return "video"

    return "article"


def is_fetchable_url(url: str) -> bool:
    """Check if a URL is worth fetching for understanding.

    Skips images, media files, and known non-article URLs.
    """
    content_type = classify_url_content_type(url)
    return content_type in ("article", "unknown")


# ---------------------------------------------------------------------------
# HTML metadata parsing
# ---------------------------------------------------------------------------


def parse_og_metadata(html: str, *, url: str = "") -> LinkMetadata:
    """Parse Open Graph and meta tags from HTML content.

    Extracts:
    - og:title, og:description, og:image, og:type, og:site_name
    - <title>, <meta name="description">, <meta name="author">
    """
    metadata = LinkMetadata(url=url)

    if url:
        parsed = urlparse(url)
        metadata.domain = parsed.netloc.removeprefix("www.")

    # OG tags
    og_patterns: list[tuple[str, str]] = [
        (r'<meta\s+(?:property|name)="og:title"\s+content="([^"]*)"', "title"),
        (r'<meta\s+content="([^"]*)"\s+(?:property|name)="og:title"', "title"),
        (r'<meta\s+(?:property|name)="og:description"\s+content="([^"]*)"', "description"),
        (r'<meta\s+content="([^"]*)"\s+(?:property|name)="og:description"', "description"),
        (r'<meta\s+(?:property|name)="og:image"\s+content="([^"]*)"', "og_image"),
        (r'<meta\s+content="([^"]*)"\s+(?:property|name)="og:image"', "og_image"),
        (r'<meta\s+(?:property|name)="og:type"\s+content="([^"]*)"', "og_type"),
        (r'<meta\s+content="([^"]*)"\s+(?:property|name)="og:type"', "og_type"),
        (r'<meta\s+(?:property|name)="og:site_name"\s+content="([^"]*)"', "site_name"),
        (r'<meta\s+content="([^"]*)"\s+(?:property|name)="og:site_name"', "site_name"),
    ]

    for pattern, attr in og_patterns:
        match = re.search(pattern, html, re.IGNORECASE)
        if match and not getattr(metadata, attr):
            setattr(metadata, attr, match.group(1).strip())

    # Fallback to standard meta tags
    if not metadata.title:
        match = re.search(r"<title[^>]*>([^<]+)</title>", html, re.IGNORECASE)
        if match:
            metadata.title = match.group(1).strip()

    if not metadata.description:
        match = re.search(
            r'<meta\s+name="description"\s+content="([^"]*)"',
            html,
            re.IGNORECASE,
        )
        if match:
            metadata.description = match.group(1).strip()

    # Author
    match = re.search(
        r'<meta\s+name="author"\s+content="([^"]*)"',
        html,
        re.IGNORECASE,
    )
    if match:
        metadata.author = match.group(1).strip()

    # Published date
    for date_prop in ["article:published_time", "datePublished", "date"]:
        match = re.search(
            rf'<meta\s+(?:property|name)="{re.escape(date_prop)}"\s+content="([^"]*)"',
            html,
            re.IGNORECASE,
        )
        if match:
            metadata.published_date = match.group(1).strip()
            break

    # Content type from og:type
    if metadata.og_type:
        og = metadata.og_type.lower()
        if "video" in og:
            metadata.content_type = "video"
        elif "article" in og or "blog" in og:
            metadata.content_type = "article"
        else:
            metadata.content_type = classify_url_content_type(url)
    else:
        metadata.content_type = classify_url_content_type(url)

    return metadata


# ---------------------------------------------------------------------------
# Formatting for agent context
# ---------------------------------------------------------------------------


def format_link_context(metadata: LinkMetadata) -> str:
    """Format link metadata as a context block for agent injection."""
    parts: list[str] = []

    if metadata.title:
        parts.append(f"**{metadata.title}**")
    if metadata.site_name:
        parts.append(f"*{metadata.site_name}*")
    elif metadata.domain:
        parts.append(f"*{metadata.domain}*")
    if metadata.description:
        desc = metadata.description[:300]
        parts.append(desc)
    if metadata.author:
        parts.append(f"Author: {metadata.author}")
    if metadata.published_date:
        parts.append(f"Published: {metadata.published_date}")

    parts.append(f"URL: {metadata.url}")

    return "\n".join(parts)


def format_multiple_links(links: list[LinkMetadata]) -> str:
    """Format multiple link metadata blocks for agent context."""
    if not links:
        return ""

    sections = []
    for i, link in enumerate(links, 1):
        prefix = f"[Link {i}] " if len(links) > 1 else ""
        sections.append(f"{prefix}{format_link_context(link)}")

    return "\n\n---\n\n".join(sections)
