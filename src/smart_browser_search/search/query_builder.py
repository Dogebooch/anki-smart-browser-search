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
    Anki's parser. Counting is string- and escape-aware so we don't miscount
    escaped quotes or parentheses *inside* a quoted value like ``deck:"Cardio
    (old)"``. We do NOT try to be clever beyond that — Anki's parser is the
    source of truth, and the keyword search catches any remaining error.
    """
    if not search_string:
        return ""
    s = " ".join(search_string.split()).strip()

    in_str = False
    esc = False
    depth = 0
    open_quotes = 0
    for ch in s:
        if esc:
            esc = False
            continue
        if ch == "\\":
            esc = True
            continue
        if ch == '"':
            in_str = not in_str
            open_quotes += 1
            continue
        if not in_str:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth = max(0, depth - 1)

    if open_quotes % 2 == 1:  # unbalanced quote
        s += '"'
        in_str = False
    if depth > 0:
        s += ")" * depth
    return s


def scoped(cfg: dict, search_string: str) -> str:
    """AND the configured scope onto a search string."""
    scope = colread.build_scope_query(cfg)
    s = sanitize(search_string)
    if scope and s:
        return f"({scope}) ({s})"
    return scope or s
