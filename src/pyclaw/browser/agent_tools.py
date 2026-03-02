"""Agent browser tools — wraps Playwright capabilities as Agent tool protocol.

Provides:
- Action definitions (navigate, click, type, scroll, select, screenshot, evaluate)
- DOM snapshot via accessibility tree
- Form filling
- File upload
- Tool result formatting for LLM consumption
"""

from __future__ import annotations

import base64
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class BrowserActionType(str, Enum):
    NAVIGATE = "navigate"
    CLICK = "click"
    TYPE = "type"
    SCROLL = "scroll"
    SELECT = "select"
    SCREENSHOT = "screenshot"
    EVALUATE = "evaluate"
    GET_TEXT = "get_text"
    GET_ATTRIBUTE = "get_attribute"
    FILL_FORM = "fill_form"
    UPLOAD_FILE = "upload_file"
    SNAPSHOT = "snapshot"
    WAIT = "wait"
    GO_BACK = "go_back"
    GO_FORWARD = "go_forward"
    RELOAD = "reload"
    CLOSE_TAB = "close_tab"
    GET_COOKIES = "get_cookies"
    SET_COOKIE = "set_cookie"


@dataclass
class BrowserAction:
    """A browser action request from the agent."""
    action_type: BrowserActionType
    selector: str = ""
    value: str = ""
    url: str = ""
    options: dict[str, Any] = field(default_factory=dict)


@dataclass
class BrowserActionResult:
    """Result of a browser action."""
    success: bool
    action_type: BrowserActionType
    data: Any = None
    error: str = ""
    screenshot_b64: str = ""
    elapsed_ms: float = 0.0
    url: str = ""
    title: str = ""

    def to_tool_result(self) -> str:
        """Format as a concise string for LLM consumption."""
        if not self.success:
            return f"[Browser Error] {self.error}"

        parts: list[str] = []
        if self.url:
            parts.append(f"URL: {self.url}")
        if self.title:
            parts.append(f"Title: {self.title}")

        if isinstance(self.data, str):
            text = self.data
            if len(text) > 4000:
                text = text[:4000] + f"\n... (truncated, {len(self.data)} chars total)"
            parts.append(text)
        elif isinstance(self.data, dict):
            import json
            parts.append(json.dumps(self.data, indent=2, ensure_ascii=False)[:4000])
        elif isinstance(self.data, list):
            import json
            parts.append(json.dumps(self.data, indent=2, ensure_ascii=False)[:4000])
        elif self.data is not None:
            parts.append(str(self.data))

        if self.screenshot_b64:
            parts.append(f"[Screenshot captured: {len(self.screenshot_b64)} bytes base64]")

        return "\n".join(parts) if parts else "[Action completed successfully]"


# ---------------------------------------------------------------------------
# Page Protocol — abstracts Playwright Page for testability
# ---------------------------------------------------------------------------

class PageProtocol(Protocol):
    """Minimal page interface for browser tools."""
    async def goto(self, url: str, **kwargs: Any) -> Any: ...
    async def click(self, selector: str, **kwargs: Any) -> None: ...
    async def fill(self, selector: str, value: str, **kwargs: Any) -> None: ...
    async def evaluate(self, expression: str) -> Any: ...
    async def screenshot(self, **kwargs: Any) -> bytes: ...
    async def title(self) -> str: ...
    @property
    def url(self) -> str: ...
    async def content(self) -> str: ...
    async def go_back(self, **kwargs: Any) -> Any: ...
    async def go_forward(self, **kwargs: Any) -> Any: ...
    async def reload(self, **kwargs: Any) -> Any: ...
    async def close(self) -> None: ...


# ---------------------------------------------------------------------------
# Action Executor
# ---------------------------------------------------------------------------

class BrowserToolExecutor:
    """Execute browser actions via Playwright page."""

    def __init__(self, *, timeout_ms: int = 30000) -> None:
        self._timeout_ms = timeout_ms

    async def execute(
        self,
        page: PageProtocol,
        action: BrowserAction,
    ) -> BrowserActionResult:
        """Execute a browser action and return the result."""
        start = time.time()
        try:
            result = await self._dispatch(page, action)
            result.elapsed_ms = (time.time() - start) * 1000
            return result
        except Exception as e:
            return BrowserActionResult(
                success=False,
                action_type=action.action_type,
                error=str(e),
                elapsed_ms=(time.time() - start) * 1000,
            )

    async def _dispatch(
        self, page: PageProtocol, action: BrowserAction
    ) -> BrowserActionResult:
        at = action.action_type

        if at == BrowserActionType.NAVIGATE:
            await page.goto(action.url or action.value, timeout=self._timeout_ms)
            return BrowserActionResult(
                success=True, action_type=at,
                url=page.url, title=await page.title(),
            )

        if at == BrowserActionType.CLICK:
            await page.click(action.selector, timeout=self._timeout_ms)
            return BrowserActionResult(
                success=True, action_type=at,
                url=page.url, title=await page.title(),
            )

        if at == BrowserActionType.TYPE:
            await page.fill(action.selector, action.value, timeout=self._timeout_ms)
            return BrowserActionResult(success=True, action_type=at)

        if at == BrowserActionType.EVALUATE:
            result = await page.evaluate(action.value)
            return BrowserActionResult(success=True, action_type=at, data=result)

        if at == BrowserActionType.SCREENSHOT:
            raw = await page.screenshot(
                full_page=action.options.get("full_page", True),
                type="png",
            )
            b64 = base64.b64encode(raw).decode("ascii")
            return BrowserActionResult(
                success=True, action_type=at,
                screenshot_b64=b64,
                url=page.url, title=await page.title(),
            )

        if at == BrowserActionType.GET_TEXT:
            text = await page.evaluate(
                f'document.querySelector("{action.selector}")?.innerText || ""'
            )
            return BrowserActionResult(success=True, action_type=at, data=text)

        if at == BrowserActionType.GET_ATTRIBUTE:
            attr = action.options.get("attribute", "href")
            val = await page.evaluate(
                f'document.querySelector("{action.selector}")?.getAttribute("{attr}")'
            )
            return BrowserActionResult(success=True, action_type=at, data=val)

        if at == BrowserActionType.SNAPSHOT:
            html = await page.content()
            title = await page.title()
            return BrowserActionResult(
                success=True, action_type=at,
                data={"html_length": len(html), "title": title, "url": page.url},
                url=page.url, title=title,
            )

        if at == BrowserActionType.GO_BACK:
            await page.go_back(timeout=self._timeout_ms)
            return BrowserActionResult(
                success=True, action_type=at,
                url=page.url, title=await page.title(),
            )

        if at == BrowserActionType.GO_FORWARD:
            await page.go_forward(timeout=self._timeout_ms)
            return BrowserActionResult(
                success=True, action_type=at,
                url=page.url, title=await page.title(),
            )

        if at == BrowserActionType.RELOAD:
            await page.reload(timeout=self._timeout_ms)
            return BrowserActionResult(
                success=True, action_type=at,
                url=page.url, title=await page.title(),
            )

        if at == BrowserActionType.CLOSE_TAB:
            await page.close()
            return BrowserActionResult(success=True, action_type=at)

        if at == BrowserActionType.WAIT:
            wait_ms = action.options.get("ms", 1000)
            import asyncio
            await asyncio.sleep(wait_ms / 1000)
            return BrowserActionResult(success=True, action_type=at)

        return BrowserActionResult(
            success=False, action_type=at,
            error=f"Unknown action type: {at}",
        )


# ---------------------------------------------------------------------------
# Tool definitions for Agent tool registry
# ---------------------------------------------------------------------------

BROWSER_TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "browser_navigate",
        "description": "Navigate to a URL in the browser",
        "parameters": {"url": {"type": "string", "required": True}},
    },
    {
        "name": "browser_click",
        "description": "Click an element by CSS selector",
        "parameters": {"selector": {"type": "string", "required": True}},
    },
    {
        "name": "browser_type",
        "description": "Type text into an input field",
        "parameters": {
            "selector": {"type": "string", "required": True},
            "text": {"type": "string", "required": True},
        },
    },
    {
        "name": "browser_screenshot",
        "description": "Take a screenshot of the current page",
        "parameters": {"full_page": {"type": "boolean", "default": True}},
    },
    {
        "name": "browser_evaluate",
        "description": "Evaluate JavaScript in the page context",
        "parameters": {"expression": {"type": "string", "required": True}},
    },
    {
        "name": "browser_get_text",
        "description": "Get text content of an element",
        "parameters": {"selector": {"type": "string", "required": True}},
    },
    {
        "name": "browser_snapshot",
        "description": "Get a DOM snapshot of the current page",
        "parameters": {},
    },
    {
        "name": "browser_go_back",
        "description": "Navigate back in browser history",
        "parameters": {},
    },
]


def parse_browser_tool_call(
    tool_name: str,
    args: dict[str, Any],
) -> BrowserAction | None:
    """Parse an agent tool call into a BrowserAction."""
    mapping: dict[str, BrowserActionType] = {
        "browser_navigate": BrowserActionType.NAVIGATE,
        "browser_click": BrowserActionType.CLICK,
        "browser_type": BrowserActionType.TYPE,
        "browser_screenshot": BrowserActionType.SCREENSHOT,
        "browser_evaluate": BrowserActionType.EVALUATE,
        "browser_get_text": BrowserActionType.GET_TEXT,
        "browser_snapshot": BrowserActionType.SNAPSHOT,
        "browser_go_back": BrowserActionType.GO_BACK,
    }

    action_type = mapping.get(tool_name)
    if not action_type:
        return None

    return BrowserAction(
        action_type=action_type,
        selector=args.get("selector", ""),
        value=args.get("text", args.get("expression", "")),
        url=args.get("url", ""),
        options={"full_page": args.get("full_page", True)},
    )
