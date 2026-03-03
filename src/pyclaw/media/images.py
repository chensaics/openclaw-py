"""Image processing utilities — EXIF orientation, compression, dimensions.

Ported from ``src/media/`` image handling. Uses Pillow.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any, cast


def get_image_dimensions(data: bytes) -> tuple[int, int] | None:
    """Get (width, height) from image data without loading full image."""
    try:
        from PIL import Image
        with Image.open(io.BytesIO(data)) as img:
            return cast(tuple[int, int], img.size)
    except Exception:
        return None


def fix_exif_orientation(data: bytes) -> bytes:
    """Apply EXIF orientation tag and strip it.

    JPEG images from phones often have an EXIF orientation tag
    rather than physically rotated pixels. This normalizes the
    image so the pixel data matches the intended orientation.
    """
    try:
        from PIL import Image, ExifTags
    except ImportError:
        return data

    try:
        img: Image.Image = Image.open(io.BytesIO(data))
    except Exception:
        return data

    try:
        exif = img.getexif()
        orientation_key = None
        for key, val in ExifTags.TAGS.items():
            if val == "Orientation":
                orientation_key = key
                break

        if orientation_key is None or orientation_key not in exif:
            return data

        orientation = exif[orientation_key]
        rotations: dict[int, Any] = {
            3: Image.Transpose.ROTATE_180,
            6: Image.Transpose.ROTATE_270,
            8: Image.Transpose.ROTATE_90,
        }

        if orientation in rotations:
            img = img.transpose(rotations[orientation])

        # Remove orientation from EXIF
        del exif[orientation_key]

        buf = io.BytesIO()
        fmt = img.format or "JPEG"
        img.save(buf, format=fmt, exif=exif.tobytes() if exif else b"")
        return buf.getvalue()
    except Exception:
        return data


def compress_image(
    data: bytes,
    *,
    max_size_bytes: int = 1_048_576,
    quality_steps: list[int] | None = None,
    max_dimension: int | None = None,
) -> bytes:
    """Compress an image using quality-ladder approach.

    Iteratively reduces JPEG quality until the image fits within
    ``max_size_bytes``. Optionally resizes to ``max_dimension``.
    """
    try:
        from PIL import Image
    except ImportError:
        return data

    if len(data) <= max_size_bytes:
        return data

    steps = quality_steps or [85, 70, 55, 40, 25]

    try:
        img: Image.Image = Image.open(io.BytesIO(data))
    except Exception:
        return data

    # Resize if needed
    if max_dimension:
        w, h = img.size
        if w > max_dimension or h > max_dimension:
            ratio = max_dimension / max(w, h)
            new_w, new_h = int(w * ratio), int(h * ratio)
            img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

    # Convert to RGB for JPEG
    if img.mode in ("RGBA", "P", "LA"):
        img = img.convert("RGB")

    for quality in steps:
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        result = buf.getvalue()
        if len(result) <= max_size_bytes:
            return result

    # Return lowest quality result even if still over limit
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=steps[-1], optimize=True)
    return buf.getvalue()
