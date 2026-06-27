# -*- coding: utf-8 -*-
"""Tier-1 retrieval: run an (LLM-expanded) keyword query via Anki's native FTS.

This is the always-on baseline. It needs no index and is backed by Anki's
Rust search engine, so it stays instant even on a huge collection.
"""

from __future__ import annotations

from .. import colread
from . import query_builder


def run(col, cfg: dict, search_string: str, limit: int = 0) -> list[int]:
    """Return note ids matching the scoped search string (read-only)."""
    if not (search_string or "").strip():
        return []
    q = query_builder.scoped(cfg, search_string)
    nids = colread.find_note_ids(col, q)
    return nids[:limit] if limit else nids
