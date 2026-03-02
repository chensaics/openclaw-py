"""Memory file management — chunking, indexing, hashing, and syncing."""

from __future__ import annotations

import hashlib
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_CHUNK_TOKENS = 512
_DEFAULT_CHUNK_OVERLAP = 64
_CHARS_PER_TOKEN = 4


@dataclass
class MemoryFileEntry:
    """A tracked memory file."""
    path: str
    abs_path: str
    mtime_ms: float
    size: int
    content_hash: str


@dataclass
class MemoryChunk:
    """A chunk of a memory file."""
    start_line: int
    end_line: int
    text: str
    content_hash: str


def hash_text(value: str) -> str:
    """SHA-256 hex digest of a string."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def list_memory_files(
    workspace_dir: str | Path,
    extra_paths: list[str] | None = None,
) -> list[MemoryFileEntry]:
    """Discover memory files in the workspace.

    Scans for: MEMORY.md, memory.md, memory/*.md, and extra paths.
    """
    workspace_dir = Path(workspace_dir).resolve()
    seen_realpaths: set[str] = set()
    entries: list[MemoryFileEntry] = []

    # Standard memory file locations
    candidates = [
        workspace_dir / "MEMORY.md",
        workspace_dir / "memory.md",
    ]

    # memory/ directory
    memory_dir = workspace_dir / "memory"
    if memory_dir.is_dir():
        for f in sorted(memory_dir.rglob("*.md")):
            if f.is_file() and not f.is_symlink():
                candidates.append(f)

    # Extra paths
    if extra_paths:
        for extra in extra_paths:
            p = Path(extra)
            if not p.is_absolute():
                p = workspace_dir / p
            p = p.resolve()
            if p.is_file() and p.suffix == ".md":
                candidates.append(p)
            elif p.is_dir():
                for f in sorted(p.rglob("*.md")):
                    if f.is_file() and not f.is_symlink():
                        candidates.append(f)

    for fpath in candidates:
        if not fpath.is_file():
            continue

        real = str(fpath.resolve())
        if real in seen_realpaths:
            continue
        seen_realpaths.add(real)

        entry = build_file_entry(fpath, workspace_dir)
        if entry:
            entries.append(entry)

    return entries


def build_file_entry(abs_path: Path, workspace_dir: Path) -> MemoryFileEntry | None:
    """Build a MemoryFileEntry from a file path."""
    try:
        stat = abs_path.stat()
        content = abs_path.read_text(encoding="utf-8")
        rel_path = str(abs_path.relative_to(workspace_dir))
    except (OSError, ValueError):
        return None

    return MemoryFileEntry(
        path=rel_path,
        abs_path=str(abs_path),
        mtime_ms=stat.st_mtime * 1000,
        size=stat.st_size,
        content_hash=hash_text(content),
    )


def chunk_markdown(
    content: str,
    *,
    tokens: int = _DEFAULT_CHUNK_TOKENS,
    overlap: int = _DEFAULT_CHUNK_OVERLAP,
) -> list[MemoryChunk]:
    """Split markdown content into line-based chunks with overlap.

    Each chunk targets approximately *tokens* tokens (using a chars-per-token
    heuristic). Overlap provides context continuity between chunks.
    """
    max_chars = tokens * _CHARS_PER_TOKEN
    overlap_chars = overlap * _CHARS_PER_TOKEN

    lines = content.splitlines(keepends=True)
    if not lines:
        return []

    chunks: list[MemoryChunk] = []
    current_lines: list[str] = []
    current_chars = 0
    start_line = 0

    for i, line in enumerate(lines):
        current_lines.append(line)
        current_chars += len(line)

        if current_chars >= max_chars:
            text = "".join(current_lines)
            chunks.append(MemoryChunk(
                start_line=start_line,
                end_line=i,
                text=text,
                content_hash=hash_text(text),
            ))

            # Compute overlap: keep trailing lines that fit within overlap_chars
            overlap_text_len = 0
            overlap_start = len(current_lines)
            for j in range(len(current_lines) - 1, -1, -1):
                overlap_text_len += len(current_lines[j])
                if overlap_text_len >= overlap_chars:
                    overlap_start = j
                    break

            current_lines = current_lines[overlap_start:]
            current_chars = sum(len(l) for l in current_lines)
            start_line = i - len(current_lines) + 1

    # Final chunk
    if current_lines:
        text = "".join(current_lines)
        chunks.append(MemoryChunk(
            start_line=start_line,
            end_line=len(lines) - 1,
            text=text,
            content_hash=hash_text(text),
        ))

    return chunks


def is_memory_path(rel_path: str) -> bool:
    """Check if a relative path is a memory file location."""
    normalized = rel_path.replace("\\", "/").strip("/").lower()
    if normalized in ("memory.md", "MEMORY.md".lower()):
        return True
    if normalized.startswith("memory/"):
        return True
    return False


def normalize_rel_path(value: str) -> str:
    """Normalize a relative path: trim, strip ./, normalize separators."""
    p = value.strip().replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    return p


async def run_with_concurrency(tasks: list[Any], limit: int = 8) -> list[Any]:
    """Run async tasks with concurrency limit."""
    import asyncio

    semaphore = asyncio.Semaphore(limit)
    results: list[Any] = []

    async def _run(task: Any) -> Any:
        async with semaphore:
            return await task

    results = await asyncio.gather(*[_run(t) for t in tasks])
    return list(results)
