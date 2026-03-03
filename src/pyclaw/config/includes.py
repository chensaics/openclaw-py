"""Config includes — ``$include`` path resolution with depth/cycle protection.

Ported from ``src/config/config-includes.ts``.

Provides:
- ``$include`` directive parsing
- Relative and absolute path resolution
- Depth limit to prevent infinite recursion
- Cycle detection to prevent circular includes
- File count limit
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

MAX_INCLUDE_DEPTH = 5
MAX_INCLUDE_FILES = 20
INCLUDE_KEY = "$include"


class IncludeError(Exception):
    """Error during config include resolution."""

    pass


class CircularIncludeError(IncludeError):
    """Circular include detected."""

    def __init__(self, path: str, chain: list[str]) -> None:
        self.path = path
        self.chain = chain
        chain_str = " → ".join(chain + [path])
        super().__init__(f"Circular include detected: {chain_str}")


class MaxDepthError(IncludeError):
    """Include depth limit exceeded."""

    def __init__(self, depth: int) -> None:
        super().__init__(f"Include depth limit exceeded ({depth} > {MAX_INCLUDE_DEPTH})")


class MaxFilesError(IncludeError):
    """Include file count limit exceeded."""

    def __init__(self, count: int) -> None:
        super().__init__(f"Include file count limit exceeded ({count} > {MAX_INCLUDE_FILES})")


@dataclass
class IncludeResult:
    """Result of resolving includes in a config."""

    data: dict[str, Any]
    included_files: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def resolve_include_path(include_path: str, base_dir: str) -> str:
    """Resolve an include path relative to the base directory."""
    if os.path.isabs(include_path):
        return include_path
    return str(Path(base_dir) / include_path)


def _load_file(path: str) -> dict[str, Any]:
    """Load a JSON/JSON5 config file."""
    resolved = Path(path).resolve()
    if not resolved.exists():
        raise IncludeError(f"Include file not found: {path}")

    try:
        with open(resolved) as f:
            result: dict[str, Any] = json.load(f)
            return result
    except json.JSONDecodeError as e:
        raise IncludeError(f"Invalid JSON in {path}: {e}")


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Deep merge two dicts. Override values take precedence."""
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def resolve_includes(
    data: dict[str, Any],
    base_dir: str,
    *,
    _depth: int = 0,
    _chain: list[str] | None = None,
    _file_count: list[int] | None = None,
) -> IncludeResult:
    """Resolve ``$include`` directives in a config dict.

    Include values can be a single path string or a list of paths.
    Included files are deep-merged in order.
    """
    chain = _chain or []
    file_count = _file_count or [0]
    included_files: list[str] = []
    warnings: list[str] = []

    if _depth > MAX_INCLUDE_DEPTH:
        raise MaxDepthError(_depth)

    if INCLUDE_KEY not in data:
        return IncludeResult(data=data, included_files=[], warnings=[])

    includes = data.pop(INCLUDE_KEY)
    if isinstance(includes, str):
        includes = [includes]

    if not isinstance(includes, list):
        warnings.append(f"Invalid $include value (expected string or list): {type(includes)}")
        return IncludeResult(data=data, warnings=warnings)

    merged: dict[str, Any] = {}
    for include_path in includes:
        resolved_path = resolve_include_path(include_path, base_dir)
        abs_path = str(Path(resolved_path).resolve())

        # Cycle detection
        if abs_path in chain:
            raise CircularIncludeError(abs_path, chain)

        # File count limit
        file_count[0] += 1
        if file_count[0] > MAX_INCLUDE_FILES:
            raise MaxFilesError(file_count[0])

        included_data = _load_file(abs_path)
        included_files.append(abs_path)

        # Recurse into included file
        inc_base_dir = str(Path(abs_path).parent)
        sub_result = resolve_includes(
            included_data,
            inc_base_dir,
            _depth=_depth + 1,
            _chain=chain + [abs_path],
            _file_count=file_count,
        )
        included_files.extend(sub_result.included_files)
        warnings.extend(sub_result.warnings)

        merged = _deep_merge(merged, sub_result.data)

    # Main data overrides included data
    result = _deep_merge(merged, data)

    return IncludeResult(
        data=result,
        included_files=included_files,
        warnings=warnings,
    )
