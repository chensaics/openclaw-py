"""Mobile platform permissions — Flet permission requests for iOS/Android.

Provides a unified API to request and check runtime permissions
across mobile platforms.  On desktop, all permissions are treated
as granted.

Includes a ``PermissionGuardPanel`` Flet control that shows pending
permission requests with explanations on mobile startup.
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
    BACKGROUND_REFRESH = "background_refresh"


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


# Per-permission user-facing explanation
PERMISSION_EXPLANATIONS: dict[str, str] = {
    "microphone": "Voice input and speech-to-text require microphone access.",
    "camera": "Camera access is needed for QR code scanning and media capture.",
    "storage": "Storage access is needed for file attachments and backups.",
    "notifications": "Notifications keep you informed about new messages and events.",
    "photos": "Photo library access is needed for sending images.",
    "background_refresh": "Background refresh lets the app receive messages when minimized.",
}


def _detect_platform() -> str:
    """Return 'ios', 'android', 'macos', 'windows', 'linux', or 'web'."""
    sys_name = platform.system().lower()
    machine = platform.machine().lower()
    if sys_name == "darwin" and machine in ("iphone", "ipad", "arm64e"):
        return "ios"
    if "android" in sys_name or ("linux" in sys_name and "android" in machine):
        return "android"
    if sys_name == "darwin":
        return "macos"
    if sys_name == "windows":
        return "windows"
    if sys_name == "linux":
        return "linux"
    return "web"


CURRENT_PLATFORM = _detect_platform()
_IS_MOBILE = CURRENT_PLATFORM in ("ios", "android")

# Platform-specific permission requirements
PLATFORM_REQUIRED_PERMISSIONS: dict[str, list[PermissionKind]] = {
    "ios": [PermissionKind.NOTIFICATIONS, PermissionKind.MICROPHONE],
    "android": [PermissionKind.NOTIFICATIONS, PermissionKind.MICROPHONE, PermissionKind.STORAGE],
    "macos": [],
    "windows": [],
    "linux": [],
    "web": [],
}


async def check_permission(kind: PermissionKind) -> PermissionResult:
    """Check current permission status.

    On desktop, always returns ``GRANTED``.
    On mobile (Flet), delegates to ``flet.permissions``.
    """
    if not _IS_MOBILE:
        return PermissionResult(kind=kind, status=PermissionStatus.GRANTED, can_request_again=False)

    try:
        import flet as ft

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
        import flet as ft

        ph = ft.PermissionHandler()
        status = await ph.request_permission(kind.value)
        mapped = _map_status(status)
        return PermissionResult(kind=kind, status=mapped, can_request_again=mapped != PermissionStatus.RESTRICTED)
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
            import flet as ft

            explanation = PERMISSION_EXPLANATIONS.get(kind.value, "")
            msg = f"Permission denied: {kind.value}"
            if explanation:
                msg = f"{msg} — {explanation}"
            sb = ft.SnackBar(ft.Text(msg), open=True)
            page.overlay.append(sb)
            page.update()
        except Exception:
            pass

    return False


async def ensure_platform_permissions(page: Any = None) -> list[PermissionResult]:
    """Request all platform-required permissions for the current platform.

    Returns a list of results. On desktop, returns empty (all auto-granted).
    """
    required = PLATFORM_REQUIRED_PERMISSIONS.get(CURRENT_PLATFORM, [])
    if not required:
        return []
    results: list[PermissionResult] = []
    for kind in required:
        granted = await ensure_permission(kind, page)
        results.append(
            PermissionResult(
                kind=kind,
                status=PermissionStatus.GRANTED if granted else PermissionStatus.DENIED,
            )
        )
    return results


def build_permission_guard_panel(
    on_continue: Any = None,
) -> Any:
    """Build a Flet panel that shows pending permissions with explanations.

    Returns a ``ft.Column`` control. On desktop, returns None (no guard needed).
    """
    if not _IS_MOBILE:
        return None

    try:
        import flet as ft
    except ImportError:
        return None

    required = PLATFORM_REQUIRED_PERMISSIONS.get(CURRENT_PLATFORM, [])
    if not required:
        return None

    rows: list[ft.Control] = [
        ft.Text("Permissions Required", size=18, weight=ft.FontWeight.BOLD),
        ft.Text(
            "The app needs the following permissions to work properly.",
            size=13,
            color=ft.Colors.ON_SURFACE_VARIANT,
        ),
        ft.Divider(height=1),
    ]

    for kind in required:
        explanation = PERMISSION_EXPLANATIONS.get(kind.value, "")
        rows.append(
            ft.Container(
                content=ft.Row(
                    [
                        ft.Icon(_permission_icon(kind), size=24, color=ft.Colors.PRIMARY),
                        ft.Column(
                            [
                                ft.Text(kind.value.replace("_", " ").title(), size=14, weight=ft.FontWeight.BOLD),
                                ft.Text(explanation, size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                            ],
                            spacing=2,
                            expand=True,
                            tight=True,
                        ),
                    ],
                    spacing=12,
                ),
                padding=ft.Padding.symmetric(horizontal=8, vertical=6),
            )
        )

    async def _handle_continue(e: Any) -> None:
        await ensure_platform_permissions(e.page if hasattr(e, "page") else None)
        if on_continue:
            await on_continue()

    rows.append(ft.Container(height=12))
    rows.append(
        ft.Button(
            "Grant Permissions & Continue",
            icon=ft.Icons.CHECK_CIRCLE,
            on_click=_handle_continue,
        )
    )

    return ft.Column(
        controls=rows,
        spacing=8,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        expand=True,
        scroll=ft.ScrollMode.AUTO,
    )


def _permission_icon(kind: PermissionKind) -> str:
    import flet as ft

    return {
        PermissionKind.MICROPHONE: ft.Icons.MIC,
        PermissionKind.CAMERA: ft.Icons.CAMERA_ALT,
        PermissionKind.STORAGE: ft.Icons.FOLDER,
        PermissionKind.NOTIFICATIONS: ft.Icons.NOTIFICATIONS,
        PermissionKind.PHOTOS: ft.Icons.PHOTO_LIBRARY,
        PermissionKind.BACKGROUND_REFRESH: ft.Icons.SYNC,
        PermissionKind.LOCATION: ft.Icons.LOCATION_ON,
        PermissionKind.CONTACTS: ft.Icons.CONTACTS,
        PermissionKind.BLUETOOTH: ft.Icons.BLUETOOTH,
    }.get(kind, ft.Icons.SECURITY)


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
