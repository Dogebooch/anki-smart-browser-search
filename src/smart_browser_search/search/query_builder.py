# -*- coding: utf-8 -*-
"""Helpers for assembling and sanitizing Anki search strings."""

from __future__ import annotations

from .. import colread


def nid_query(nids: list[int]) -> str:
    """A search string matching exactly these notes (the copy/paste fallback)."""
    if not nids:
        return "nid:0"  # matches nothing, but is valid syntax
    return "nid:" + ",".join(str(int(n)) for n in nids)


def sanitize(search_string: str | None) -> str:
    """Light cleanup of an LLM-produced search string.

    We balance stray quotes/parens so a malformed string never throws inside
    Anki's parser. We do NOT try to be clever — Anki's parser is the source of
    truth, and the keyword search catches any remaining error gracefully.
    """
    if not search_string:
        return ""
    s = " ".join(search_string.split()).strip()
    # Balance double quotes.
    if s.count('"') % 2 == 1:
        s += '"'
    # Balance parentheses.
    diff = s.count("(") - s.count(")")
    if diff > 0:
        s += ")" * diff
    elif diff < 0:
        s = "(" * (-diff) + s
    return s


def scoped(cfg: dict, search_string: str) -> str:
    """AND the configured scope onto a search string."""
    scope = colread.build_scope_query(cfg)
    s = sanitize(search_string)
    if scope and s:
        return f"({scope}) ({s})"
    return scope or s
