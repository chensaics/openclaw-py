"""Sandbox boundary enforcement — path sanitization, workspace limits, config hardening.

Ported from ``src/security/sandbox.ts`` and ``src/config/include-loader.ts``.

Provides path traversal prevention, workspace boundary checks, and
safe ``config.$include`` resolution to prevent directory escape attacks.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Path sanitization
# ---------------------------------------------------------------------------

_TRAVERSAL_PATTERNS = [
    re.compile(r"\.\./"),
    re.compile(r"/\.\./"),
    re.compile(r"\\\.\\\.\\"),
    re.compile(r"~"),
    re.compile(r"\$\{"),
    re.compile(r"\$\("),
]


def sanitize_path(path: str) -> str:
    """Sanitize a file path by removing traversal sequences.

    Strips ``../``, ``~/``, and variable interpolation attempts.
    Returns the cleaned path.
    """
    result = path.strip()

    # Normalize separators
    result = result.replace("\\", "/")

    # Remove null bytes
    result = result.replace("\x00", "")

    # Collapse multiple slashes
    result = re.sub(r"/{2,}", "/", result)

    # Remove traversal sequences
    while "../" in result:
        result = result.replace("../", "")
    while "..\\" in result:
        result = result.replace("..\\", "")

    # Remove leading tilde expansion
    if result.startswith("~/") or result.startswith("~\\"):
        result = result[2:]
    elif result == "~":
        result = ""

    # Remove variable interpolation
    result = re.sub(r"\$\{[^}]*\}", "", result)
    result = re.sub(r"\$\([^)]*\)", "", result)

    return result


def is_path_within(path: str | Path, boundary: str | Path) -> bool:
    """Check if a resolved path is within a boundary directory.

    Both paths are resolved to absolute form before comparison.
    """
    try:
        resolved = Path(path).resolve()
        boundary_resolved = Path(boundary).resolve()
        return str(resolved).startswith(str(boundary_resolved) + os.sep) or resolved == boundary_resolved
    except (OSError, ValueError):
        return False


# ---------------------------------------------------------------------------
# Workspace boundary
# ---------------------------------------------------------------------------


class WorkspaceBoundary:
    """Enforces file access within a workspace root."""

    def __init__(self, root: str | Path, *, allowed_external: list[str] | None = None) -> None:
        self._root = Path(root).resolve()
        self._allowed_external = [Path(p).resolve() for p in (allowed_external or [])]

    @property
    def root(self) -> Path:
        return self._root

    def check(self, path: str | Path) -> bool:
        """Check if a path is within the workspace boundary."""
        resolved = Path(path).resolve()

        if is_path_within(resolved, self._root):
            return True

        return any(is_path_within(resolved, ext) for ext in self._allowed_external)

    def resolve(self, path: str) -> Path | None:
        """Resolve a path within the workspace, returning None if out of bounds."""
        sanitized = sanitize_path(path)

        resolved = Path(sanitized).resolve() if os.path.isabs(sanitized) else (self._root / sanitized).resolve()

        if self.check(resolved):
            return resolved

        logger.warning(
            "Path %r resolves to %s which is outside workspace %s",
            path,
            resolved,
            self._root,
        )
        return None


# ---------------------------------------------------------------------------
# Config $include hardening
# ---------------------------------------------------------------------------

MAX_INCLUDE_DEPTH = 5
MAX_INCLUDE_FILES = 20


def resolve_config_include(
    include_path: str,
    *,
    config_dir: str | Path,
    workspace_root: str | Path | None = None,
    depth: int = 0,
) -> Path | None:
    """Safely resolve a ``$include`` path from a config file.

    Prevents:
    - Path traversal beyond config directory or workspace
    - Excessive include depth (circular references)
    - Absolute paths outside workspace
    - Variable interpolation in include paths

    Returns the resolved Path or None if the include is rejected.
    """
    if depth >= MAX_INCLUDE_DEPTH:
        logger.warning("$include depth exceeded (%d): %s", depth, include_path)
        return None

    sanitized = sanitize_path(include_path)
    if not sanitized:
        logger.warning("$include path sanitized to empty: %r", include_path)
        return None

    config_dir = Path(config_dir).resolve()
    boundary = Path(workspace_root).resolve() if workspace_root else config_dir

    resolved = Path(sanitized).resolve() if os.path.isabs(sanitized) else (config_dir / sanitized).resolve()

    if not is_path_within(resolved, boundary):
        logger.warning(
            "$include path %r resolves outside boundary %s",
            include_path,
            boundary,
        )
        return None

    if not resolved.exists():
        logger.warning("$include file does not exist: %s", resolved)
        return None

    if not resolved.is_file():
        logger.warning("$include path is not a file: %s", resolved)
        return None

    return resolved


class ConfigIncludeLoader:
    """Safe loader for ``$include`` directives in config files."""

    def __init__(
        self,
        config_dir: str | Path,
        *,
        workspace_root: str | Path | None = None,
    ) -> None:
        self._config_dir = Path(config_dir).resolve()
        self._workspace_root = Path(workspace_root).resolve() if workspace_root else self._config_dir
        self._loaded_files: set[str] = set()

    def resolve_include(self, include_path: str, *, depth: int = 0) -> Path | None:
        """Resolve an include path safely."""
        if len(self._loaded_files) >= MAX_INCLUDE_FILES:
            logger.warning("Max include files (%d) reached", MAX_INCLUDE_FILES)
            return None

        resolved = resolve_config_include(
            include_path,
            config_dir=self._config_dir,
            workspace_root=self._workspace_root,
            depth=depth,
        )

        if resolved:
            resolved_str = str(resolved)
            if resolved_str in self._loaded_files:
                logger.warning("Circular $include detected: %s", resolved)
                return None
            self._loaded_files.add(resolved_str)

        return resolved

    @property
    def loaded_count(self) -> int:
        return len(self._loaded_files)
