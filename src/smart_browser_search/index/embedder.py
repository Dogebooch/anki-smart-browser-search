# -*- coding: utf-8 -*-
"""Turn text into stored vectors (binary code + float32), with hashing helpers."""

from __future__ import annotations

import hashlib

from .. import vectors
from ..ai import prompts
from ..ai.client import AIClient


def hash_text(text: str) -> str:
    return hashlib.sha1((text or "").encode("utf-8", "replace")).hexdigest()


def hash_images(filenames: list[str]) -> str:
    joined = "\n".join(sorted(filenames))
    return hashlib.sha1(joined.encode("utf-8", "replace")).hexdigest()


def embed_batch(client: AIClient, model: str, texts: list[str], kind: str
                ) -> tuple[list[tuple[bytes, bytes]], int]:
    """Embed ``texts`` and return packed (binary, float32) pairs plus the dim.

    ``kind`` is "document" or "query"; the right model-specific prefix is applied.
    """
    if not texts:
        return [], 0
    prefix = prompts.embed_prefix(model, kind)
    prepared = [prefix + (t or "") for t in texts]
    raw = client.embed(prepared, model=model)
    out: list[tuple[bytes, bytes]] = []
    dim = 0
    for vec in raw:
        if not vec:
            out.append((b"", b""))
            continue
        dim = len(vec)
        normed = vectors.l2_normalize(vec)
        bin_bytes = vectors.binarize_to_bytes(normed, dim)
        f32_bytes = vectors.pack_f32(normed)
        out.append((bin_bytes, f32_bytes))
    return out, dim


def embed_query(client: AIClient, model: str, text: str
                ) -> tuple[int, list[float]] | None:
    """Embed a single query. Returns (binary_as_int, normalized_f32)."""
    pairs, _dim = embed_batch(client, model, [text], "query")
    if not pairs or not pairs[0][0]:
        return None
    bin_bytes, f32_bytes = pairs[0]
    return vectors.bytes_to_int(bin_bytes), vectors.unpack_f32(f32_bytes)
