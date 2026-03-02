"""Node command policy — platform-specific command allowlists and capability discovery.

Ported from ``src/gateway/node-command-policy.ts``.
Defines which node.invoke commands are available on each platform
(Android, iOS, macOS) and provides capability-based filtering.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Platform command constants
# ---------------------------------------------------------------------------

DEVICE_COMMANDS = ["device.info", "device.status"]

ANDROID_DEVICE_COMMANDS = [*DEVICE_COMMANDS, "device.permissions", "device.health"]
IOS_DEVICE_COMMANDS = [*DEVICE_COMMANDS]
MACOS_DEVICE_COMMANDS = [*DEVICE_COMMANDS]

CAMERA_COMMANDS = ["camera.list"]
ANDROID_CAMERA_COMMANDS = [*CAMERA_COMMANDS, "camera.snap", "camera.clip"]
IOS_CAMERA_COMMANDS = [*CAMERA_COMMANDS]

NOTIFICATION_COMMANDS = ["notifications.list"]
ANDROID_NOTIFICATION_COMMANDS = [*NOTIFICATION_COMMANDS, "notifications.actions"]

CONTACTS_COMMANDS = ["contacts.search"]
ANDROID_CONTACTS_COMMANDS = [*CONTACTS_COMMANDS, "contacts.add"]

CALENDAR_COMMANDS = ["calendar.events"]
ANDROID_CALENDAR_COMMANDS = [*CALENDAR_COMMANDS, "calendar.add"]

PHOTOS_COMMANDS = ["photos.latest"]

MOTION_COMMANDS = ["motion.activity", "motion.pedometer"]

SYSTEM_COMMANDS = ["system.run", "system.which"]
ANDROID_SYSTEM_COMMANDS = [*SYSTEM_COMMANDS, "system.notify"]

# ---------------------------------------------------------------------------
# Aggregated platform allowlists
# ---------------------------------------------------------------------------

ANDROID_ALL_COMMANDS = sorted(set(
    ANDROID_DEVICE_COMMANDS
    + ANDROID_CAMERA_COMMANDS
    + ANDROID_NOTIFICATION_COMMANDS
    + ANDROID_CONTACTS_COMMANDS
    + ANDROID_CALENDAR_COMMANDS
    + PHOTOS_COMMANDS
    + MOTION_COMMANDS
    + ANDROID_SYSTEM_COMMANDS
))

IOS_ALL_COMMANDS = sorted(set(
    IOS_DEVICE_COMMANDS
    + IOS_CAMERA_COMMANDS
    + PHOTOS_COMMANDS
    + SYSTEM_COMMANDS
))

MACOS_ALL_COMMANDS = sorted(set(
    MACOS_DEVICE_COMMANDS
    + SYSTEM_COMMANDS
))

PLATFORM_COMMANDS: dict[str, list[str]] = {
    "android": ANDROID_ALL_COMMANDS,
    "ios": IOS_ALL_COMMANDS,
    "macos": MACOS_ALL_COMMANDS,
    "linux": MACOS_ALL_COMMANDS,
    "windows": MACOS_ALL_COMMANDS,
}


# ---------------------------------------------------------------------------
# Capability-based filtering
# ---------------------------------------------------------------------------

@dataclass
class NodeCapabilities:
    """Capabilities advertised by a connected node."""

    platform: str = ""
    commands: list[str] = field(default_factory=list)
    caps: dict[str, bool] = field(default_factory=dict)


def get_allowed_commands(platform: str) -> list[str]:
    """Get the command allowlist for a given platform."""
    return PLATFORM_COMMANDS.get(platform.lower(), SYSTEM_COMMANDS)


def is_command_allowed(command: str, platform: str, node_caps: NodeCapabilities | None = None) -> bool:
    """Check if a command is allowed for the given platform and node capabilities."""
    allowed = get_allowed_commands(platform)
    if command not in allowed:
        return False

    if node_caps and node_caps.commands:
        return command in node_caps.commands

    return True


def filter_commands_by_capabilities(
    commands: list[str],
    node_caps: NodeCapabilities,
) -> list[str]:
    """Filter commands to those advertised by the node."""
    if not node_caps.commands:
        return commands
    advertised = set(node_caps.commands)
    return [cmd for cmd in commands if cmd in advertised]


# ---------------------------------------------------------------------------
# Tool definitions for node commands
# ---------------------------------------------------------------------------

_NODE_TOOL_DEFS: dict[str, dict[str, Any]] = {
    "device.info": {
        "description": "Get device hardware and software information.",
        "parameters": {"type": "object", "properties": {}},
    },
    "device.status": {
        "description": "Get device status (battery, connectivity, storage).",
        "parameters": {"type": "object", "properties": {}},
    },
    "device.permissions": {
        "description": "Get granted/denied runtime permissions.",
        "parameters": {"type": "object", "properties": {}},
    },
    "device.health": {
        "description": "Get device health metrics (memory, CPU, temperature).",
        "parameters": {"type": "object", "properties": {}},
    },
    "camera.list": {
        "description": "List available cameras on the device.",
        "parameters": {"type": "object", "properties": {}},
    },
    "camera.snap": {
        "description": "Take a photo with a device camera.",
        "parameters": {
            "type": "object",
            "properties": {
                "camera_id": {"type": "string", "description": "Camera identifier"},
            },
        },
    },
    "notifications.list": {
        "description": "List active notifications on the device.",
        "parameters": {"type": "object", "properties": {}},
    },
    "notifications.actions": {
        "description": "Perform an action on a notification (open, dismiss, reply).",
        "parameters": {
            "type": "object",
            "properties": {
                "notification_id": {"type": "string"},
                "action": {"type": "string", "description": "open | dismiss | reply"},
                "reply_text": {"type": "string"},
            },
            "required": ["notification_id", "action"],
        },
    },
    "contacts.search": {
        "description": "Search contacts by name or phone number.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
            },
            "required": ["query"],
        },
    },
    "contacts.add": {
        "description": "Add a new contact.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "phone": {"type": "string"},
                "email": {"type": "string"},
            },
            "required": ["name"],
        },
    },
    "calendar.events": {
        "description": "List upcoming calendar events.",
        "parameters": {
            "type": "object",
            "properties": {
                "days": {"type": "integer", "description": "Number of days to look ahead", "default": 7},
            },
        },
    },
    "calendar.add": {
        "description": "Add a calendar event.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "start": {"type": "string", "description": "ISO 8601 start time"},
                "end": {"type": "string", "description": "ISO 8601 end time"},
                "location": {"type": "string"},
            },
            "required": ["title", "start"],
        },
    },
    "photos.latest": {
        "description": "Get the most recent photos from the device gallery.",
        "parameters": {
            "type": "object",
            "properties": {
                "count": {"type": "integer", "default": 5},
            },
        },
    },
    "motion.activity": {
        "description": "Get current motion activity (walking, running, driving, stationary).",
        "parameters": {"type": "object", "properties": {}},
    },
    "motion.pedometer": {
        "description": "Get step count and distance data.",
        "parameters": {
            "type": "object",
            "properties": {
                "days": {"type": "integer", "default": 1},
            },
        },
    },
    "system.run": {
        "description": "Execute a shell command on the device.",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to run"},
                "cwd": {"type": "string", "description": "Working directory"},
                "timeout_ms": {"type": "integer", "default": 30000},
            },
            "required": ["command"],
        },
    },
    "system.which": {
        "description": "Check if a command exists on the device.",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Command name to look up"},
            },
            "required": ["command"],
        },
    },
    "system.notify": {
        "description": "Show a notification on the device.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "body": {"type": "string"},
            },
            "required": ["title", "body"],
        },
    },
}


def get_node_tool_definitions(platform: str, node_caps: NodeCapabilities | None = None) -> list[dict[str, Any]]:
    """Get tool definitions for available node commands on a platform."""
    commands = get_allowed_commands(platform)
    if node_caps:
        commands = filter_commands_by_capabilities(commands, node_caps)

    tools: list[dict[str, Any]] = []
    for cmd in commands:
        tool_def = _NODE_TOOL_DEFS.get(cmd)
        if tool_def:
            tools.append({
                "name": f"node_{cmd.replace('.', '_')}",
                "description": tool_def["description"],
                "parameters": tool_def["parameters"],
                "_node_command": cmd,
            })
    return tools
