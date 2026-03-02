"""Subsystem logger — colored, categorized logging.

Each subsystem (e.g. ``gateway/heartbeat``, ``channels/telegram``) gets a
named logger with a deterministic color for easy visual identification.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

# ANSI 256-color palette for subsystem labels
_SUBSYSTEM_COLORS = [
    "\033[38;5;33m",   # blue
    "\033[38;5;35m",   # green
    "\033[38;5;136m",  # yellow
    "\033[38;5;166m",  # orange
    "\033[38;5;125m",  # magenta
    "\033[38;5;37m",   # cyan
    "\033[38;5;61m",   # slate
    "\033[38;5;172m",  # amber
]
_RESET = "\033[0m"


def _color_for_subsystem(subsystem: str) -> str:
    h = hash(subsystem) % len(_SUBSYSTEM_COLORS)
    return _SUBSYSTEM_COLORS[h]


CHANNEL_SUBSYSTEM_PREFIXES = frozenset({
    "channels/", "telegram/", "discord/", "slack/",
    "whatsapp/", "signal/", "imessage/",
})


class SubsystemLogger:
    """Wrapper around stdlib logger with subsystem prefix and color."""

    def __init__(self, subsystem: str) -> None:
        self.subsystem = subsystem
        self._logger = logging.getLogger(f"pyclaw.{subsystem.replace('/', '.')}")
        self._color = _color_for_subsystem(subsystem)
        self._prefix = f"{self._color}[{subsystem}]{_RESET} "

    def _log(self, level: int, msg: str, *args: Any, **kwargs: Any) -> None:
        if self._logger.isEnabledFor(level):
            self._logger.log(level, self._prefix + msg, *args, **kwargs)

    def trace(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._log(logging.DEBUG - 5, msg, *args, **kwargs)

    def debug(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._log(logging.DEBUG, msg, *args, **kwargs)

    def info(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._log(logging.INFO, msg, *args, **kwargs)

    def warn(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._log(logging.WARNING, msg, *args, **kwargs)

    def error(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._log(logging.ERROR, msg, *args, **kwargs)

    def fatal(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._log(logging.CRITICAL, msg, *args, **kwargs)

    def child(self, sub: str) -> SubsystemLogger:
        return SubsystemLogger(f"{self.subsystem}/{sub}")


def create_subsystem_logger(subsystem: str) -> SubsystemLogger:
    return SubsystemLogger(subsystem)
