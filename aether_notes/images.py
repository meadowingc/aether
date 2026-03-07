"""Image processing utilities for Aether notes.

Handles HEIC/WEBP/PNG → JPEG conversion and compression for:
- Local storage & piclog.blue: aggressively compressed to <512KB JPEG
- Bluesky/Mastodon/Tumblr: high-quality JPEG conversion (no aggressive compression)
"""

from __future__ import annotations

import io
from typing import Tuple

from PIL import Image

# Register HEIC/HEIF support with Pillow
try:
    import pillow_heif

    pillow_heif.register_heif_opener()
except ImportError:
    pass

# Aggressive compression target (piclog.blue limit, also used for local storage)
MAX_COMPRESSED_BYTES = 512 * 1024  # 512 KB
COMPRESSED_MAX_DIMENSION = 1200  # resize longest side before compressing
COMPRESSED_MIN_QUALITY = 5

# High-quality export settings
HQ_MAX_DIMENSION = 2048
HQ_JPEG_QUALITY = 90

# Bluesky has a 1MB blob limit
BLUESKY_MAX_BYTES = 976_000  # ~976KB to stay safely under 1MB


def _open_image(raw_bytes: bytes) -> Image.Image:
    """Open image from bytes, handling HEIC and other formats."""
    img = Image.open(io.BytesIO(raw_bytes))
    # Convert palette/RGBA to RGB for JPEG output
    if img.mode in ("RGBA", "LA", "P", "PA"):
        background = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode == "P":
            img = img.convert("RGBA")
        background.paste(img, mask=img.split()[-1] if "A" in img.mode else None)
        img = background
    elif img.mode != "RGB":
        img = img.convert("RGB")
    # Strip EXIF orientation by applying transpose
    from PIL import ImageOps

    img = ImageOps.exif_transpose(img)
    return img


def _fit_within(img: Image.Image, max_dim: int) -> Image.Image:
    """Resize image so its longest side is at most max_dim, preserving aspect ratio."""
    w, h = img.size
    if max(w, h) <= max_dim:
        return img
    if w >= h:
        new_w = max_dim
        new_h = int(h * max_dim / w)
    else:
        new_h = max_dim
        new_w = int(w * max_dim / h)
    return img.resize((new_w, new_h), Image.LANCZOS)


def _to_jpeg_bytes(img: Image.Image, quality: int) -> bytes:
    """Encode image as JPEG bytes at the given quality."""
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue()


def compress_for_storage(raw_bytes: bytes) -> bytes:
    """Aggressively compress image to JPEG under 512KB.

    Used for local storage and piclog.blue uploads.
    Strategy: resize to max 1200px, then iteratively reduce quality until <512KB.
    """
    img = _open_image(raw_bytes)
    img = _fit_within(img, COMPRESSED_MAX_DIMENSION)

    # Try progressively lower quality
    for quality in (80, 65, 50, 40, 30, 20, 15, 10, COMPRESSED_MIN_QUALITY):
        data = _to_jpeg_bytes(img, quality)
        if len(data) <= MAX_COMPRESSED_BYTES:
            return data

    # Still too big — shrink further
    for dimension in (800, 600, 400):
        smaller = _fit_within(img, dimension)
        data = _to_jpeg_bytes(smaller, COMPRESSED_MIN_QUALITY)
        if len(data) <= MAX_COMPRESSED_BYTES:
            return data

    # Last resort: return the smallest we can produce
    return data


def convert_for_crosspost(raw_bytes: bytes) -> bytes:
    """Convert image to high-quality JPEG for Bluesky/Mastodon/Tumblr.

    Preserves quality but ensures JPEG format and reasonable dimensions.
    """
    img = _open_image(raw_bytes)
    img = _fit_within(img, HQ_MAX_DIMENSION)
    return _to_jpeg_bytes(img, HQ_JPEG_QUALITY)


def convert_for_bluesky(raw_bytes: bytes) -> bytes:
    """Convert image to JPEG that fits within Bluesky's ~1MB blob limit."""
    img = _open_image(raw_bytes)
    img = _fit_within(img, HQ_MAX_DIMENSION)

    # Try high quality first
    data = _to_jpeg_bytes(img, HQ_JPEG_QUALITY)
    if len(data) <= BLUESKY_MAX_BYTES:
        return data

    # Reduce quality iteratively
    for quality in (80, 70, 60, 50, 40):
        data = _to_jpeg_bytes(img, quality)
        if len(data) <= BLUESKY_MAX_BYTES:
            return data

    # Resize down
    for dimension in (1600, 1200, 800):
        smaller = _fit_within(img, dimension)
        data = _to_jpeg_bytes(smaller, 60)
        if len(data) <= BLUESKY_MAX_BYTES:
            return data

    return data


def process_uploaded_image(raw_bytes: bytes) -> Tuple[bytes, bytes, bytes]:
    """Process an uploaded image file.

    Returns:
        (compressed_jpeg, hq_jpeg, bluesky_jpeg)
        - compressed_jpeg: aggressively compressed <512KB for local storage & piclog.blue
        - hq_jpeg: high-quality JPEG for Mastodon & Tumblr
        - bluesky_jpeg: JPEG within Bluesky's blob limit
    """
    compressed = compress_for_storage(raw_bytes)
    hq = convert_for_crosspost(raw_bytes)
    bsky = convert_for_bluesky(raw_bytes)
    return compressed, hq, bsky
