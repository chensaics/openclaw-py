"""Web tools — HTTP fetch and web search."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from pyclaw.agents.tools.base import BaseTool
from pyclaw.agents.types import ToolResult

_MAX_RESPONSE_BYTES = 512 * 1024  # 512 KiB
_FETCH_TIMEOUT = 30  # seconds

# SSRF protection: block private/reserved IP ranges
_BLOCKED_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "[::1]"}


def _is_url_safe(url: str) -> str | None:
    """Return an error message if the URL looks like an SSRF target."""
    try:
        parsed = urlparse(url)
    except Exception:
        return "Invalid URL."

    if parsed.scheme not in ("http", "https"):
        return f"Unsupported scheme: {parsed.scheme}. Only http/https allowed."

    host = (parsed.hostname or "").lower()
    if host in _BLOCKED_HOSTS:
        return f"Blocked host: {host}"

    # Block private IP ranges (10.x, 172.16-31.x, 192.168.x)
    if re.match(r"^(10\.|172\.(1[6-9]|2\d|3[01])\.|192\.168\.)", host):
        return f"Blocked private IP: {host}"

    return None


class WebFetchTool(BaseTool):
    """Fetch content from a URL and return readable text."""

    @property
    def name(self) -> str:
        return "web_fetch"

    @property
    def description(self) -> str:
        return (
            "Fetch and extract readable content from a URL. "
            "By default, HTML is converted to clean text. Set raw_html=true to get raw HTML. "
            "Only http/https URLs are allowed. Private/internal IPs and localhost are blocked (SSRF protection)."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "The URL to fetch (http/https only)."},
                "raw_html": {
                    "type": "boolean",
                    "description": "If true, return the raw HTML instead of extracted text (default false).",
                },
            },
            "required": ["url"],
        }

    async def execute(self, tool_call_id: str, arguments: dict[str, Any]) -> ToolResult:
        url = arguments.get("url", "")
        if not url:
            return ToolResult.text("Error: url is required.", is_error=True)

        if err := _is_url_safe(url):
            return ToolResult.text(f"Error: {err}", is_error=True)

        extract_text = not arguments.get("raw_html", False)

        import httpx

        try:
            async with httpx.AsyncClient(
                timeout=_FETCH_TIMEOUT,
                follow_redirects=True,
                headers={"User-Agent": "pyclaw/1.0"},
            ) as client:
                resp = await client.get(url)
                resp.raise_for_status()
        except httpx.TimeoutException:
            return ToolResult.text(f"Request timed out after {_FETCH_TIMEOUT}s.", is_error=True)
        except httpx.HTTPStatusError as e:
            return ToolResult.text(f"HTTP {e.response.status_code}: {e.response.reason_phrase}", is_error=True)
        except Exception as e:
            return ToolResult.text(f"Fetch error: {e}", is_error=True)

        raw = resp.text[:_MAX_RESPONSE_BYTES]

        if not extract_text:
            return ToolResult.text(raw)

        content_type = resp.headers.get("content-type", "")
        if "html" in content_type:
            return ToolResult.text(_extract_text_from_html(raw))

        return ToolResult.text(raw)


def _extract_text_from_html(html: str) -> str:
    """Best-effort text extraction from HTML without heavy dependencies."""
    # Strip script/style blocks
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
    # Strip HTML tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    # Decode common HTML entities
    for entity, char in [
        ("&amp;", "&"),
        ("&lt;", "<"),
        ("&gt;", ">"),
        ("&quot;", '"'),
        ("&#39;", "'"),
        ("&nbsp;", " "),
    ]:
        text = text.replace(entity, char)
    return text


class WebSearchTool(BaseTool):
    """Search the web using a configurable search provider."""

    def __init__(self, *, api_key: str | None = None, provider: str = "brave") -> None:
        self._api_key = api_key
        self._provider = provider

    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return (
            "Search the web using the Brave Search API. Returns a ranked list of results with title, URL, and snippet."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query string."},
                "num_results": {
                    "type": "integer",
                    "description": "Number of results to return (default 5, max 10).",
                },
                "country": {
                    "type": "string",
                    "description": "Two-letter country code for regional results (e.g. 'us', 'cn').",
                },
                "freshness": {
                    "type": "string",
                    "description": "Filter by recency: 'pd' (past day), 'pw' (past week), 'pm' (past month), 'py' (past year).",
                },
            },
            "required": ["query"],
        }

    async def execute(self, tool_call_id: str, arguments: dict[str, Any]) -> ToolResult:
        query = arguments.get("query", "")
        if not query:
            return ToolResult.text("Error: query is required.", is_error=True)

        num_results = min(arguments.get("num_results", 5), 10)
        country = arguments.get("country")
        freshness = arguments.get("freshness")

        if self._provider == "brave" and self._api_key:
            return await self._search_brave(query, num_results, country=country, freshness=freshness)

        return ToolResult.text(
            f"Web search not configured. Provider: {self._provider}. Set a search API key in the configuration.",
            is_error=True,
        )

    async def _search_brave(
        self,
        query: str,
        count: int,
        *,
        country: str | None = None,
        freshness: str | None = None,
    ) -> ToolResult:
        import httpx

        params: dict[str, Any] = {"q": query, "count": count}
        if country:
            params["country"] = country
        if freshness:
            params["freshness"] = freshness

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    "https://api.search.brave.com/res/v1/web/search",
                    params=params,
                    headers={
                        "Accept": "application/json",
                        "X-Subscription-Token": self._api_key or "",
                    },
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            return ToolResult.text(f"Search error: {e}", is_error=True)

        results = data.get("web", {}).get("results", [])
        if not results:
            return ToolResult.text("No results found.")

        lines: list[str] = []
        for i, r in enumerate(results[:count], 1):
            title = r.get("title", "")
            url = r.get("url", "")
            snippet = r.get("description", "")
            lines.append(f"{i}. [{title}]({url})\n   {snippet}")

        return ToolResult.text("\n\n".join(lines))
