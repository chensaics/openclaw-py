"""Video understanding pipeline — video providers, audio precheck, concurrency.

Ported from ``src/media/understanding/video*.ts``.

Provides:
- Video understanding pipeline with frame extraction
- Moonshot/MiniMax video provider adapters
- Audio track precheck
- Concurrency control for video processing
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, cast

logger = logging.getLogger(__name__)


class VideoProcessingState(str, Enum):
    PENDING = "pending"
    EXTRACTING = "extracting"
    UNDERSTANDING = "understanding"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class VideoConfig:
    """Configuration for video understanding."""

    max_frames: int = 10
    max_duration_s: int = 300
    max_file_size_mb: int = 100
    max_concurrent: int = 2
    audio_precheck: bool = True
    frame_interval_s: float = 5.0


@dataclass
class VideoFrame:
    """An extracted video frame."""

    index: int
    timestamp_s: float
    data: bytes = b""
    url: str = ""
    mime_type: str = "image/jpeg"


@dataclass
class VideoInfo:
    """Metadata about a video file."""

    duration_s: float = 0.0
    width: int = 0
    height: int = 0
    fps: float = 0.0
    has_audio: bool = False
    file_size_bytes: int = 0
    codec: str = ""
    mime_type: str = ""


@dataclass
class VideoUnderstandingRequest:
    """Request for video understanding."""

    video_url: str = ""
    video_data: bytes = b""
    prompt: str = ""
    max_frames: int = 0
    include_audio: bool = True


@dataclass
class VideoUnderstandingResult:
    """Result from video understanding."""

    description: str
    provider: str
    frames_analyzed: int = 0
    audio_transcript: str = ""
    duration_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Video Provider Adapters
# ---------------------------------------------------------------------------


@dataclass
class MoonshotVideoConfig:
    api_key: str = ""
    base_url: str = "https://api.moonshot.cn/v1"
    model: str = "moonshot-v1-128k"


class MoonshotVideoProvider:
    """Moonshot video understanding via frame extraction + vision."""

    def __init__(self, config: MoonshotVideoConfig) -> None:
        self._config = config

    @property
    def name(self) -> str:
        return "moonshot-video"

    def build_frame_request(self, frames: list[VideoFrame], prompt: str) -> dict[str, Any]:
        """Build a chat completion request with extracted frames."""
        content: list[dict[str, Any]] = [{"type": "text", "text": prompt or "Describe this video."}]
        for frame in frames:
            if frame.url:
                content.append({"type": "image_url", "image_url": {"url": frame.url}})

        return {
            "url": f"{self._config.base_url}/chat/completions",
            "headers": {
                "Authorization": f"Bearer {self._config.api_key}",
                "Content-Type": "application/json",
            },
            "body": {
                "model": self._config.model,
                "messages": [{"role": "user", "content": content}],
            },
        }

    def parse_response(self, response: dict[str, Any]) -> str:
        choices = response.get("choices", [])
        if choices:
            return cast(str, choices[0].get("message", {}).get("content", ""))
        return ""


@dataclass
class MiniMaxVideoConfig:
    api_key: str = ""
    base_url: str = "https://api.minimax.chat/v1"
    model: str = "abab6.5s-chat"


class MiniMaxVideoProvider:
    """MiniMax video understanding via frame extraction + vision."""

    def __init__(self, config: MiniMaxVideoConfig) -> None:
        self._config = config

    @property
    def name(self) -> str:
        return "minimax-video"

    def build_frame_request(self, frames: list[VideoFrame], prompt: str) -> dict[str, Any]:
        content: list[dict[str, Any]] = [{"type": "text", "text": prompt or "Describe this video."}]
        for frame in frames:
            if frame.url:
                content.append({"type": "image_url", "image_url": {"url": frame.url}})

        return {
            "url": f"{self._config.base_url}/chat/completions",
            "headers": {
                "Authorization": f"Bearer {self._config.api_key}",
                "Content-Type": "application/json",
            },
            "body": {
                "model": self._config.model,
                "messages": [{"role": "user", "content": content}],
            },
        }

    def parse_response(self, response: dict[str, Any]) -> str:
        choices = response.get("choices", [])
        if choices:
            return cast(str, choices[0].get("message", {}).get("content", ""))
        return ""


# ---------------------------------------------------------------------------
# Video Pipeline
# ---------------------------------------------------------------------------


def compute_frame_timestamps(
    duration_s: float,
    *,
    max_frames: int = 10,
    interval_s: float = 5.0,
) -> list[float]:
    """Compute timestamps for frame extraction."""
    if duration_s <= 0:
        return [0.0]

    timestamps: list[float] = []
    t = 0.0
    while t < duration_s and len(timestamps) < max_frames:
        timestamps.append(t)
        t += interval_s

    if not timestamps:
        timestamps.append(0.0)

    return timestamps


def should_precheck_audio(video_info: VideoInfo, config: VideoConfig) -> bool:
    """Determine if audio precheck should run."""
    if not config.audio_precheck:
        return False
    return video_info.has_audio


def validate_video(video_info: VideoInfo, config: VideoConfig) -> list[str]:
    """Validate a video against config limits. Returns list of issues."""
    issues: list[str] = []

    if video_info.duration_s > config.max_duration_s:
        issues.append(f"Video too long: {video_info.duration_s:.0f}s > {config.max_duration_s}s")

    size_mb = video_info.file_size_bytes / (1024 * 1024)
    if size_mb > config.max_file_size_mb:
        issues.append(f"Video too large: {size_mb:.1f}MB > {config.max_file_size_mb}MB")

    return issues


class VideoConcurrencyLimiter:
    """Limit concurrent video processing tasks."""

    def __init__(self, max_concurrent: int = 2) -> None:
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._active = 0

    async def acquire(self) -> None:
        await self._semaphore.acquire()
        self._active += 1

    def release(self) -> None:
        self._active -= 1
        self._semaphore.release()

    @property
    def active_count(self) -> int:
        return self._active

    @property
    def available(self) -> int:
        return self._semaphore._value
