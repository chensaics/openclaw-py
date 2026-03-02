"""Media storage — persistent file-based media storage with references.

Stores media files (images, audio, etc.) in a local directory and
provides reference URLs/paths for retrieval.
"""

from __future__ import annotations

import hashlib
import time
from pathlib import Path
from typing import Any

from pyclaw.media.mime import detect_mime_type


class MediaStore:
    """File-system based media storage."""

    def __init__(self, base_dir: Path) -> None:
        self._base_dir = base_dir

    def ensure_dir(self) -> None:
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def store(
        self,
        data: bytes,
        *,
        filename: str | None = None,
        mime_type: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Store media data and return a reference dict.

        Returns:
            dict with ``path``, ``mime``, ``size``, ``hash``, ``storedAt`` keys.
        """
        self.ensure_dir()

        content_hash = hashlib.sha256(data).hexdigest()[:16]
        mime = mime_type or detect_mime_type(data)

        if filename:
            stem = Path(filename).stem
            suffix = Path(filename).suffix
        else:
            ext_map: dict[str, str] = {
                "image/jpeg": ".jpg",
                "image/png": ".png",
                "image/gif": ".gif",
                "image/webp": ".webp",
                "audio/mpeg": ".mp3",
                "audio/ogg": ".ogg",
                "audio/wav": ".wav",
                "video/mp4": ".mp4",
            }
            suffix = ext_map.get(mime, ".bin")
            stem = f"media-{content_hash}"

        final_name = f"{stem}-{content_hash}{suffix}"
        file_path = self._base_dir / final_name
        file_path.write_bytes(data)

        return {
            "path": str(file_path),
            "filename": final_name,
            "mime": mime,
            "size": len(data),
            "hash": content_hash,
            "storedAt": time.time(),
        }

    def get(self, filename: str) -> bytes | None:
        """Retrieve stored media by filename."""
        path = self._base_dir / filename
        if path.is_file():
            return path.read_bytes()
        return None

    def delete(self, filename: str) -> bool:
        """Delete a stored media file."""
        path = self._base_dir / filename
        if path.is_file():
            path.unlink()
            return True
        return False

    def list_files(self) -> list[dict[str, Any]]:
        """List all stored media files."""
        self.ensure_dir()
        files = []
        for p in sorted(self._base_dir.iterdir()):
            if p.is_file() and not p.name.startswith("."):
                files.append({
                    "filename": p.name,
                    "size": p.stat().st_size,
                    "mime": detect_mime_type(path=p),
                })
        return files
