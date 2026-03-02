"""Intent analyzer — rule-based user intent classification.

Classifies incoming user messages into intents (stop, correction, append,
continue, new_topic) to drive the interrupt system.  Pure rule-based with
bilingual (Chinese + English) keyword matching — no LLM calls required.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class UserIntent(str, Enum):
    CONTINUE = "continue"
    CORRECTION = "correction"
    APPEND = "append"
    NEW_TOPIC = "new_topic"
    STOP = "stop"


@dataclass
class IntentResult:
    """Result of intent analysis."""

    intent: UserIntent
    confidence: float
    is_interrupt: bool
    explanation: str = ""


_STOP_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"^stop$",
        r"^cancel$",
        r"^abort$",
        r"^quit$",
        r"^停[止下]",
        r"^取消",
        r"^算了$",
        r"^够了$",
        r"^别[说继]",
        r"^不[要用]了",
        r"stop\s*generat",
        r"停止生成",
    ]
]

_CORRECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"^不对",
        r"^错了",
        r"^不是这样",
        r"^搞错了",
        r"^重[来做]",
        r"^等一下",
        r"^wait",
        r"^no[,.\s]",
        r"^wrong",
        r"^that'?s\s+(not|wrong|incorrect)",
        r"^change\s+to",
        r"^instead",
        r"^actually[,\s]",
        r"^correction",
    ]
]

_APPEND_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"^对了",
        r"^还有",
        r"^补充",
        r"^另外",
        r"^顺便",
        r"^by\s+the\s+way",
        r"^also[,\s]",
        r"^additionally",
        r"^oh\s+and",
        r"^one\s+more\s+thing",
        r"^and\s+also",
        r"^p\.?s\.?",
    ]
]

_CONTINUE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"^继续$",
        r"^接着[做说来]?$",
        r"^go\s+on$",
        r"^continue$",
        r"^keep\s+going$",
        r"^proceed$",
        r"^next$",
        r"^下一步$",
    ]
]


class IntentAnalyzer:
    """Rule-based intent classifier for user messages during agent execution."""

    SHORT_MESSAGE_THRESHOLD = 20

    def analyze(self, message: str, *, is_agent_running: bool = False) -> IntentResult:
        """Classify a user message into an intent.

        Priority order: stop > correction > append > continue > short-message heuristic > new_topic.
        """
        text = message.strip()

        if not text:
            return IntentResult(
                intent=UserIntent.NEW_TOPIC,
                confidence=0.5,
                is_interrupt=False,
                explanation="empty message",
            )

        if _matches_any(text, _STOP_PATTERNS):
            return IntentResult(
                intent=UserIntent.STOP,
                confidence=0.95,
                is_interrupt=True,
                explanation="stop keyword detected",
            )

        if _matches_any(text, _CORRECTION_PATTERNS):
            return IntentResult(
                intent=UserIntent.CORRECTION,
                confidence=0.85,
                is_interrupt=True,
                explanation="correction keyword detected",
            )

        if _matches_any(text, _APPEND_PATTERNS):
            return IntentResult(
                intent=UserIntent.APPEND,
                confidence=0.80,
                is_interrupt=False,
                explanation="append keyword detected",
            )

        if _matches_any(text, _CONTINUE_PATTERNS):
            return IntentResult(
                intent=UserIntent.CONTINUE,
                confidence=0.90,
                is_interrupt=False,
                explanation="continue keyword detected",
            )

        if is_agent_running and len(text) < self.SHORT_MESSAGE_THRESHOLD:
            return IntentResult(
                intent=UserIntent.CORRECTION,
                confidence=0.60,
                is_interrupt=True,
                explanation="short message during agent run — likely correction",
            )

        return IntentResult(
            intent=UserIntent.NEW_TOPIC,
            confidence=0.50,
            is_interrupt=False,
            explanation="no special intent detected",
        )


def _matches_any(text: str, patterns: list[re.Pattern[str]]) -> bool:
    return any(p.search(text) for p in patterns)
