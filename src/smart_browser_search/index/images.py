# -*- coding: utf-8 -*-
"""Picture search: caption/OCR card images with a local vision model.

Ollama (and OpenAI-compatible servers) have no image-embedding endpoint, so true
image-vector similarity is not available without heavy compiled dependencies —
which we refuse to ship. Instead we caption + OCR each card image once (slow,
background, dirty-tracked) and embed the resulting *text* into the same index.
This is exactly right for Image Occlusion cards, where the answer lives in the
image. It is honest caption-based matching, never on the query path.
"""

from __future__ import annotations

import os

from .. import log
from ..ai import prompts
from ..ai.client import AIClient

# Skip absurdly large images to keep vision latency sane.
_MAX_IMAGE_BYTES = 8 * 1024 * 1024
_MIME = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp",
    ".svg": "image/svg+xml",
}


def _mime_for(name: str) -> str:
    ext = os.path.splitext(name)[1].lower()
    return _MIME.get(ext, "image/png")


def caption_image(client: AIClient, media_dir: str, filename: str) -> str | None:
    """Caption a single image file. Returns caption text or None on failure."""
    if not media_dir:
        return None
    path = os.path.join(media_dir, filename)
    try:
        if not os.path.isfile(path):
            return None
        size = os.path.getsize(path)
        if size == 0 or size > _MAX_IMAGE_BYTES:
            return None
        with open(path, "rb") as fh:
            data = fh.read()
    except Exception as e:
        log.warn(f"could not read image {filename}: {e}")
        return None
    try:
        caption = client.vision_describe(
            data, prompts.VISION_CAPTION_PROMPT, mime=_mime_for(filename)
        )
        return (caption or "").strip() or None
    except Exception as e:
        log.warn(f"vision caption failed for {filename}: {e}")
        return None


def describe_query_image(client: AIClient, image_bytes: bytes,
                         mime: str = "image/png") -> str:
    """Describe a user-supplied query image (search-by-image)."""
    return (client.vision_describe(image_bytes, prompts.VISION_QUERY_PROMPT,
                                   mime=mime) or "").strip()
