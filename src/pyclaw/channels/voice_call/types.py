"""Voice call types and provider abstraction."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CallState(str, Enum):
    RINGING = "ringing"
    IN_PROGRESS = "in-progress"
    COMPLETED = "completed"
    FAILED = "failed"
    NO_ANSWER = "no-answer"
    BUSY = "busy"
    CANCELED = "canceled"


@dataclass
class CallInfo:
    call_sid: str
    from_number: str
    to_number: str
    state: CallState = CallState.RINGING
    direction: str = "inbound"
    duration_s: int = 0
    recording_url: str = ""
    transcript: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class VoiceResponse:
    """TwiML-like voice response builder."""

    actions: list[dict[str, Any]] = field(default_factory=list)

    def say(self, text: str, *, voice: str = "alice", language: str = "en-US") -> VoiceResponse:
        self.actions.append({"type": "say", "text": text, "voice": voice, "language": language})
        return self

    def gather(
        self,
        *,
        input_type: str = "speech",
        timeout: int = 5,
        action_url: str = "",
    ) -> VoiceResponse:
        self.actions.append(
            {
                "type": "gather",
                "input": input_type,
                "timeout": timeout,
                "action": action_url,
            }
        )
        return self

    def play(self, url: str) -> VoiceResponse:
        self.actions.append({"type": "play", "url": url})
        return self

    def hangup(self) -> VoiceResponse:
        self.actions.append({"type": "hangup"})
        return self

    def pause(self, length: int = 1) -> VoiceResponse:
        self.actions.append({"type": "pause", "length": length})
        return self

    def redirect(self, url: str) -> VoiceResponse:
        self.actions.append({"type": "redirect", "url": url})
        return self


class VoiceProvider(ABC):
    """Abstract voice call provider."""

    @abstractmethod
    async def make_call(self, to: str, from_: str, url: str) -> CallInfo: ...

    @abstractmethod
    async def answer_call(self, call_sid: str, response: VoiceResponse) -> None: ...

    @abstractmethod
    async def hang_up(self, call_sid: str) -> None: ...

    @abstractmethod
    async def get_call(self, call_sid: str) -> CallInfo | None: ...

    @abstractmethod
    def parse_webhook(self, data: dict[str, Any]) -> CallInfo: ...
