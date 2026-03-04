"""Hooks system — event-driven plugin framework.

Ported from ``src/hooks/hooks.ts``.
"""

from pyclaw.hooks.loader import load_hook_entries, load_workspace_hooks
from pyclaw.hooks.registry import (
    clear_hooks,
    create_hook_event,
    register_hook,
    trigger_hook,
    unregister_hook,
)
from pyclaw.hooks.types import HookEvent, HookEventType, HookHandler

__all__ = [
    "HookEvent",
    "HookEventType",
    "HookHandler",
    "clear_hooks",
    "create_hook_event",
    "load_hook_entries",
    "load_workspace_hooks",
    "register_hook",
    "trigger_hook",
    "unregister_hook",
]
