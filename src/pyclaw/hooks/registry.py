"""Hook registration and dispatch.

Handlers are keyed by ``type`` or ``type:action``.  When an event fires,
both the broad (type-only) and specific (type:action) handlers run.
Errors in individual handlers are logged and swallowed so remaining handlers
always execute.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from pyclaw.hooks.types import HookEvent, HookEventType, HookHandler

logger = logging.getLogger(__name__)

_hooks: dict[str, list[HookHandler]] = {}


def register_hook(event_key: str, handler: HookHandler) -> None:
    """Register *handler* for *event_key* (``type`` or ``type:action``)."""
    _hooks.setdefault(event_key, []).append(handler)


def unregister_hook(event_key: str, handler: HookHandler) -> None:
    handlers = _hooks.get(event_key, [])
    try:
        handlers.remove(handler)
    except ValueError:
        pass


def clear_hooks() -> None:
    _hooks.clear()


def create_hook_event(
    event_type: HookEventType | str,
    action: str,
    session_key: str = "",
    context: dict[str, Any] | None = None,
    messages: list[dict[str, Any]] | None = None,
) -> HookEvent:
    if isinstance(event_type, str):
        event_type = HookEventType(event_type)
    return HookEvent(
        type=event_type,
        action=action,
        session_key=session_key,
        context=context or {},
        timestamp=time.time(),
        messages=messages or [],
    )


async def trigger_hook(event: HookEvent) -> None:
    """Dispatch *event* to all matching handlers.

    Both ``type`` and ``type:action`` handlers are invoked.
    """
    keys = [event.type.value, f"{event.type.value}:{event.action}"]
    for key in keys:
        for handler in list(_hooks.get(key, [])):
            try:
                result = handler(event)
                if asyncio.iscoroutine(result):
                    await result
            except Exception:
                logger.exception("Hook handler error for %s", key)
