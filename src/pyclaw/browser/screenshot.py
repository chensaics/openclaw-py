"""Screenshot service — capture, crop, resize, and encode screenshots.

Provides:
- Full-page and element screenshots via Playwright
- Region-based cropping
- Resize/scale for LLM vision input
- Base64 encoding for API transport
- CDP-based screenshot fallback
"""

from __future__ import annotations

import base64
import io
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class ScreenshotFormat(str, Enum):
    PNG = "png"
    JPEG = "jpeg"


@dataclass
class ScreenshotOptions:
    """Options for taking a screenshot."""

    full_page: bool = True
    format: ScreenshotFormat = ScreenshotFormat.PNG
    quality: int = 80  # JPEG only (1-100)
    selector: str = ""
    clip: ScreenshotClip | None = None
    max_width: int = 0
    max_height: int = 0
    omit_background: bool = False


@dataclass
class ScreenshotClip:
    """Clipping region for a screenshot."""

    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0


@dataclass
class ScreenshotResult:
    """Result of a screenshot capture."""

    data: bytes = b""
    format: ScreenshotFormat = ScreenshotFormat.PNG
    width: int = 0
    height: int = 0
    error: str = ""

    @property
    def success(self) -> bool:
        return bool(self.data) and not self.error

    def to_base64(self) -> str:
        if not self.data:
            return ""
        return base64.b64encode(self.data).decode("ascii")

    def to_data_url(self) -> str:
        if not self.data:
            return ""
        mime = f"image/{self.format.value}"
        return f"data:{mime};base64,{self.to_base64()}"

    @property
    def size_bytes(self) -> int:
        return len(self.data)


class ScreenshotPage(Protocol):
    """Minimal page interface for screenshots."""

    async def screenshot(self, **kwargs: Any) -> bytes: ...


class ScreenshotService:
    """Take and process screenshots from Playwright pages."""

    def __init__(self, *, default_options: ScreenshotOptions | None = None) -> None:
        self._defaults = default_options or ScreenshotOptions()
        self._capture_count = 0

    async def capture(
        self,
        page: ScreenshotPage,
        options: ScreenshotOptions | None = None,
    ) -> ScreenshotResult:
        """Capture a screenshot from a Playwright page."""
        opts = options or self._defaults

        try:
            pw_args: dict[str, Any] = {
                "full_page": opts.full_page,
                "type": opts.format.value,
            }

            if opts.format == ScreenshotFormat.JPEG:
                pw_args["quality"] = opts.quality

            if opts.omit_background:
                pw_args["omit_background"] = True

            if opts.clip:
                pw_args["clip"] = {
                    "x": opts.clip.x,
                    "y": opts.clip.y,
                    "width": opts.clip.width,
                    "height": opts.clip.height,
                }
                pw_args["full_page"] = False

            raw = await page.screenshot(**pw_args)

            result = ScreenshotResult(data=raw, format=opts.format)

            if opts.max_width or opts.max_height:
                result = self._resize(result, opts.max_width, opts.max_height)

            self._capture_count += 1
            return result

        except Exception as e:
            return ScreenshotResult(error=str(e))

    def _resize(self, result: ScreenshotResult, max_w: int, max_h: int) -> ScreenshotResult:
        """Resize screenshot if it exceeds max dimensions.

        Uses PIL if available, otherwise returns original.
        """
        try:
            from PIL import Image
        except ImportError:
            return result

        img: Image.Image = Image.open(io.BytesIO(result.data))
        w, h = img.size
        result.width = w
        result.height = h

        need_resize = False
        if max_w and w > max_w:
            need_resize = True
        if max_h and h > max_h:
            need_resize = True

        if not need_resize:
            return result

        ratio = min(
            (max_w / w) if max_w else 1.0,
            (max_h / h) if max_h else 1.0,
        )
        new_w = int(w * ratio)
        new_h = int(h * ratio)
        img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

        buf = io.BytesIO()
        fmt = "PNG" if result.format == ScreenshotFormat.PNG else "JPEG"
        img.save(buf, format=fmt)

        return ScreenshotResult(
            data=buf.getvalue(),
            format=result.format,
            width=new_w,
            height=new_h,
        )

    @property
    def capture_count(self) -> int:
        return self._capture_count


# ---------------------------------------------------------------------------
# CDP Screenshot (fallback for raw CDP connections)
# ---------------------------------------------------------------------------


@dataclass
class CDPScreenshotParams:
    """Parameters for a CDP-based screenshot."""

    format: str = "png"
    quality: int = 80
    from_surface: bool = True
    clip: dict[str, float] | None = None

    def to_cdp_params(self) -> dict[str, Any]:
        params: dict[str, Any] = {
            "format": self.format,
            "fromSurface": self.from_surface,
        }
        if self.format == "jpeg":
            params["quality"] = self.quality
        if self.clip:
            params["clip"] = {**self.clip, "scale": 1}
        return params


def decode_cdp_screenshot(b64_data: str) -> ScreenshotResult:
    """Decode a base64 screenshot from CDP response."""
    try:
        data = base64.b64decode(b64_data)
        return ScreenshotResult(data=data, format=ScreenshotFormat.PNG)
    except Exception as e:
        return ScreenshotResult(error=f"Failed to decode CDP screenshot: {e}")
