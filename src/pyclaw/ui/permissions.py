"""Mobile platform permissions — Flet permission requests for iOS/Android.

Provides a unified API to request and check runtime permissions
across mobile platforms.  On desktop, all permissions are treated
as granted.
"""

from __future__ import annotations

import logging
import platform
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class PermissionKind(str, Enum):
    MICROPHONE = "microphone"
    CAMERA = "camera"
    STORAGE = "storage"
    NOTIFICATIONS = "notifications"
    LOCATION = "location"
    CONTACTS = "contacts"
    PHOTOS = "photos"
    BLUETOOTH = "bluetooth"


class PermissionStatus(str, Enum):
    GRANTED = "granted"
    DENIED = "denied"
    RESTRICTED = "restricted"
    NOT_DETERMINED = "not_determined"


@dataclass
class PermissionResult:
    kind: PermissionKind
    status: PermissionStatus
    can_request_again: bool = True


def _is_mobile() -> bool:
    """Heuristic: detect iOS/Android via platform markers."""
    sys_name = platform.system().lower()
    machine = platform.machine().lower()
    if sys_name == "darwin" and machine in ("iphone", "ipad", "arm64e"):
        return True
    if "android" in sys_name or "linux" in sys_name and "android" in machine:
        return True
    return False


_IS_MOBILE = _is_mobile()


async def check_permission(kind: PermissionKind) -> PermissionResult:
    """Check current permission status.

    On desktop, always returns ``GRANTED``.
    On mobile (Flet), delegates to ``flet.permissions``.
    """
    if not _IS_MOBILE:
        return PermissionResult(kind=kind, status=PermissionStatus.GRANTED, can_request_again=False)

    try:
        import flet as ft  # type: ignore[import-untyped]

        ph = ft.PermissionHandler()
        status = await ph.check_permission(kind.value)
        mapped = _map_status(status)
        return PermissionResult(kind=kind, status=mapped)
    except Exception as exc:
        logger.debug("Permission check failed for %s: %s", kind.value, exc)
        return PermissionResult(kind=kind, status=PermissionStatus.NOT_DETERMINED)


async def request_permission(kind: PermissionKind) -> PermissionResult:
    """Request a runtime permission.

    On desktop, returns ``GRANTED`` immediately.
    On mobile, shows the native permission dialog.
    """
    if not _IS_MOBILE:
        return PermissionResult(kind=kind, status=PermissionStatus.GRANTED, can_request_again=False)

    try:
        import flet as ft  # type: ignore[import-untyped]

        ph = ft.PermissionHandler()
        status = await ph.request_permission(kind.value)
        mapped = _map_status(status)
        return PermissionResult(
            kind=kind, status=mapped, can_request_again=mapped != PermissionStatus.RESTRICTED
        )
    except Exception as exc:
        logger.debug("Permission request failed for %s: %s", kind.value, exc)
        return PermissionResult(kind=kind, status=PermissionStatus.DENIED)


async def request_multiple(kinds: list[PermissionKind]) -> list[PermissionResult]:
    """Request multiple permissions in sequence."""
    results: list[PermissionResult] = []
    for kind in kinds:
        results.append(await request_permission(kind))
    return results


async def ensure_permission(kind: PermissionKind, page: Any = None) -> bool:
    """Check then request a permission, optionally showing a Flet snackbar on denial."""
    result = await check_permission(kind)
    if result.status == PermissionStatus.GRANTED:
        return True

    result = await request_permission(kind)
    if result.status == PermissionStatus.GRANTED:
        return True

    if page is not None:
        try:
            import flet as ft  # type: ignore[import-untyped]

            page.snack_bar = ft.SnackBar(
                ft.Text(f"Permission denied: {kind.value}"),
                open=True,
            )
            page.update()
        except Exception:
            pass

    return False


def _map_status(raw: Any) -> PermissionStatus:
    """Map a raw Flet permission status to our enum."""
    raw_str = str(raw).lower()
    if "granted" in raw_str:
        return PermissionStatus.GRANTED
    if "denied" in raw_str:
        return PermissionStatus.DENIED
    if "restricted" in raw_str or "permanently" in raw_str:
        return PermissionStatus.RESTRICTED
    return PermissionStatus.NOT_DETERMINED
