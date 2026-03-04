"""Inline directives — parse and apply @think, @model, @verbose, etc.

Ported from ``src/auto-reply/reply/directive-handling*.ts``.

Provides:
- Directive parsing from message text
- Directive application (modify agent config for current turn)
- Fast-lane directives (apply immediately without agent turn)
- Directive persistence (sticky across turns)
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

_DIRECTIVE_PATTERN = re.compile(
    r"@(think|model|verbose|reasoning|elevated|exec)\b\s*(\S*)",
    re.IGNORECASE,
)


@dataclass
class ParsedDirective:
    """A single parsed inline directive."""

    name: str  # "think" | "model" | "verbose" | "reasoning" | "elevated" | "exec"
    value: str = ""  # e.g. "low", "gpt-4o", ""
    raw: str = ""


@dataclass
class DirectiveSet:
    """Collection of directives parsed from a message."""

    directives: list[ParsedDirective] = field(default_factory=list)
    cleaned_text: str = ""  # Text with directives removed

    @property
    def has_directives(self) -> bool:
        return len(self.directives) > 0

    def get(self, name: str) -> ParsedDirective | None:
        for d in self.directives:
            if d.name == name:
                return d
        return None

    @property
    def think_level(self) -> str | None:
        d = self.get("think")
        return d.value if d else None

    @property
    def model_override(self) -> str | None:
        d = self.get("model")
        return d.value if d else None

    @property
    def is_verbose(self) -> bool:
        return self.get("verbose") is not None

    @property
    def is_reasoning(self) -> bool:
        return self.get("reasoning") is not None

    @property
    def is_elevated(self) -> bool:
        return self.get("elevated") is not None

    @property
    def is_exec(self) -> bool:
        return self.get("exec") is not None


def parse_directives(text: str) -> DirectiveSet:
    """Parse inline directives from message text.

    Directives are ``@name`` or ``@name value`` patterns.
    Returns cleaned text with directives removed.
    """
    directives: list[ParsedDirective] = []

    for match in _DIRECTIVE_PATTERN.finditer(text):
        name = match.group(1).lower()
        value = match.group(2).strip()
        directives.append(
            ParsedDirective(
                name=name,
                value=value,
                raw=match.group(0),
            )
        )

    cleaned = _DIRECTIVE_PATTERN.sub("", text).strip()
    cleaned = re.sub(r"\s{2,}", " ", cleaned)

    return DirectiveSet(directives=directives, cleaned_text=cleaned)


# ---------------------------------------------------------------------------
# Directive application
# ---------------------------------------------------------------------------


@dataclass
class DirectiveOverrides:
    """Overrides to apply for the current agent turn."""

    model: str | None = None
    think_level: str | None = None
    verbose: bool = False
    reasoning: bool = False
    elevated: bool = False
    exec_mode: bool = False


def apply_directives(directive_set: DirectiveSet) -> DirectiveOverrides:
    """Convert parsed directives into agent overrides."""
    overrides = DirectiveOverrides()

    if directive_set.model_override:
        overrides.model = directive_set.model_override

    if directive_set.think_level:
        level = directive_set.think_level.lower()
        if level in ("low", "medium", "high"):
            overrides.think_level = level

    overrides.verbose = directive_set.is_verbose
    overrides.reasoning = directive_set.is_reasoning
    overrides.elevated = directive_set.is_elevated
    overrides.exec_mode = directive_set.is_exec

    return overrides


# ---------------------------------------------------------------------------
# Fast-lane detection
# ---------------------------------------------------------------------------

_FAST_LANE_DIRECTIVES = {"think", "model"}


def is_fast_lane(directive_set: DirectiveSet) -> bool:
    """Check if the directives are fast-lane (apply without agent turn).

    A message is fast-lane if it ONLY contains directives (no other text)
    and all directives are in the fast-lane set.
    """
    if not directive_set.has_directives:
        return False

    if directive_set.cleaned_text:
        return False

    return all(d.name in _FAST_LANE_DIRECTIVES for d in directive_set.directives)


# ---------------------------------------------------------------------------
# Directive persistence
# ---------------------------------------------------------------------------


class DirectivePersistence:
    """Track sticky directives across turns."""

    def __init__(self) -> None:
        self._sticky: dict[str, str] = {}

    def update(self, directive_set: DirectiveSet) -> None:
        """Update sticky directives from a new message."""
        for d in directive_set.directives:
            if d.name in ("think", "model"):
                self._sticky[d.name] = d.value

    def get_sticky_overrides(self) -> DirectiveOverrides:
        """Get overrides from sticky directives."""
        overrides = DirectiveOverrides()
        if "model" in self._sticky:
            overrides.model = self._sticky["model"]
        if "think" in self._sticky:
            overrides.think_level = self._sticky["think"]
        return overrides

    def clear(self) -> None:
        self._sticky.clear()

    def remove(self, name: str) -> None:
        self._sticky.pop(name, None)
