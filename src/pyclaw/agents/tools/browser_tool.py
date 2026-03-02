"""Browser automation tool — Playwright-based."""

from __future__ import annotations

import json
from typing import Any

from pyclaw.agents.tools.base import BaseTool
from pyclaw.agents.types import ToolResult


class BrowserTool(BaseTool):
    """Control a headless browser via Playwright."""

    def __init__(self, *, headless: bool = True) -> None:
        self._headless = headless
        self._browser: Any = None
        self._page: Any = None

    @property
    def name(self) -> str:
        return "browser"

    @property
    def description(self) -> str:
        return (
            "Control a headless web browser. Supports navigating to URLs, "
            "clicking elements, filling forms, taking screenshots, and "
            "extracting page content via CSS selectors."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": (
                        "Action to perform: 'navigate', 'click', 'fill', "
                        "'screenshot', 'content', 'evaluate', 'close'."
                    ),
                },
                "url": {
                    "type": "string",
                    "description": "URL for 'navigate' action.",
                },
                "selector": {
                    "type": "string",
                    "description": "CSS selector for 'click', 'fill', 'content' actions.",
                },
                "value": {
                    "type": "string",
                    "description": "Value for 'fill' action, or JS expression for 'evaluate'.",
                },
            },
            "required": ["action"],
        }

    async def _ensure_browser(self) -> None:
        if self._page:
            return
        try:
            from playwright.async_api import async_playwright

            pw = await async_playwright().start()
            self._browser = await pw.chromium.launch(headless=self._headless)
            self._page = await self._browser.new_page()
        except ImportError:
            raise RuntimeError(
                "playwright is not installed. Run: pip install playwright && playwright install chromium"
            )

    async def execute(self, tool_call_id: str, arguments: dict[str, Any]) -> ToolResult:
        action = arguments.get("action", "")
        if not action:
            return ToolResult.text("Error: action is required.", is_error=True)

        try:
            await self._ensure_browser()
        except RuntimeError as e:
            return ToolResult.text(str(e), is_error=True)

        page = self._page

        if action == "navigate":
            url = arguments.get("url", "")
            if not url:
                return ToolResult.text("Error: url is required for navigate.", is_error=True)
            await page.goto(url, wait_until="domcontentloaded")
            return ToolResult.text(f"Navigated to {page.url} — title: {await page.title()}")

        if action == "click":
            selector = arguments.get("selector", "")
            if not selector:
                return ToolResult.text("Error: selector is required for click.", is_error=True)
            await page.click(selector)
            return ToolResult.text(f"Clicked: {selector}")

        if action == "fill":
            selector = arguments.get("selector", "")
            value = arguments.get("value", "")
            if not selector:
                return ToolResult.text("Error: selector is required for fill.", is_error=True)
            await page.fill(selector, value)
            return ToolResult.text(f"Filled {selector} with value.")

        if action == "screenshot":
            data = await page.screenshot(type="png")
            import base64

            b64 = base64.b64encode(data).decode("ascii")
            return ToolResult.text(
                f"Screenshot taken ({len(data)} bytes). Base64 length: {len(b64)}"
            )

        if action == "content":
            selector = arguments.get("selector")
            if selector:
                el = await page.query_selector(selector)
                text = await el.inner_text() if el else "(element not found)"
            else:
                text = await page.content()
            # Truncate large content
            if len(text) > 50_000:
                text = text[:50_000] + "\n... (truncated)"
            return ToolResult.text(text)

        if action == "evaluate":
            expr = arguments.get("value", "")
            if not expr:
                return ToolResult.text(
                    "Error: value (JS expression) is required for evaluate.", is_error=True
                )
            result = await page.evaluate(expr)
            return ToolResult.text(json.dumps(result, default=str, ensure_ascii=False))

        if action == "close":
            if self._browser:
                await self._browser.close()
                self._browser = None
                self._page = None
            return ToolResult.text("Browser closed.")

        return ToolResult.text(f"Unknown action: {action}", is_error=True)
