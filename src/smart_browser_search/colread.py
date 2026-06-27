# -*- coding: utf-8 -*-
"""Read-only collection access layer.

THIS IS THE ONLY MODULE ALLOWED TO TOUCH ``col``. Every function here is
strictly read-only: it calls ``find_notes`` / ``find_cards`` / ``get_note`` /
``get_card`` / ``media.dir()`` and note read-accessors, and nothing else. There
is deliberately no function in this module that writes, adds, removes, flushes,
or reschedules anything. ``safety.py`` enforces this by scanning the source.

Keeping all collection access behind this single surface is what makes the
"never harm the deck" guarantee auditable.
"""

from __future__ import annotations

import html as _html
import re
from typing import Iterable, Iterator

from . import log

_IMG_RE = re.compile(r"""<img[^>]*\bsrc\s*=\s*['"]([^'"]+)['"]""", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_SOUND_RE = re.compile(r"\[sound:[^\]]+\]")


# --------------------------------------------------------------------------- #
# Text extraction
# --------------------------------------------------------------------------- #
def strip_html(value: str) -> str:
    """Turn a field's HTML into clean searchable plain text."""
    if not value:
        return ""
    value = _SOUND_RE.sub(" ", value)
    value = _IMG_RE.sub(lambda m: " " + _img_alt_hint(m.group(1)) + " ", value)
    value = _TAG_RE.sub(" ", value)
    value = _html.unescape(value)
    value = _WS_RE.sub(" ", value)
    return value.strip()


def _img_alt_hint(src: str) -> str:
    """Use the image filename as a weak text hint (e.g. 'ecg-inferior-mi.png')."""
    name = src.rsplit("/", 1)[-1]
    name = re.sub(r"\.[a-zA-Z0-9]+$", "", name)
    name = re.sub(r"[-_]+", " ", name)
    return name


def note_images(note) -> list[str]:
    """Image filenames referenced by a note's fields (read-only)."""
    out: list[str] = []
    for value in note.fields:
        for m in _IMG_RE.finditer(value or ""):
            src = m.group(1)
            if not src.lower().startswith(("http://", "https://", "data:")):
                out.append(src.rsplit("/", 1)[-1])
    return out


def note_to_text(note, fields_filter: list[str] | None, max_chars: int = 0) -> str:
    """Concatenate a note's (filtered) fields into clean text for embedding."""
    parts: list[str] = []
    try:
        items = list(note.items())  # [(field_name, value), ...]
    except Exception:
        items = list(zip(note.keys(), note.fields))
    for name, value in items:
        if fields_filter and name not in fields_filter:
            continue
        text = strip_html(value)
        if text:
            parts.append(text)
    joined = "  ".join(parts)
    if max_chars and len(joined) > max_chars:
        joined = joined[:max_chars]
    return joined


def note_type_name(note) -> str:
    try:
        nt = note.note_type()
        if nt:
            return nt.get("name", "")
    except Exception:
        pass
    return ""


# --------------------------------------------------------------------------- #
# Search (read-only)
# --------------------------------------------------------------------------- #
def find_note_ids(col, query: str) -> list[int]:
    try:
        return list(col.find_notes(query))
    except Exception as e:
        log.warn(f"find_notes failed for {query!r}: {e}")
        return []


def find_card_ids(col, query: str) -> list[int]:
    try:
        return list(col.find_cards(query))
    except Exception as e:
        log.warn(f"find_cards failed for {query!r}: {e}")
        return []


def first_card_id_for_note(col, nid: int) -> int | None:
    try:
        note = col.get_note(nid)
        cids = note.card_ids() if hasattr(note, "card_ids") else [c.id for c in note.cards()]
        return cids[0] if cids else None
    except Exception:
        return None


# --------------------------------------------------------------------------- #
# Scope query building
# --------------------------------------------------------------------------- #
def quote(value: str) -> str:
    """Quote a search term value, escaping embedded quotes."""
    value = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{value}"'


def build_scope_query(cfg: dict) -> str:
    """A search fragment restricting to the configured decks/note types/state."""
    clauses: list[str] = []
    decks = [d for d in cfg.get("scope_decks", []) if d]
    if decks:
        clauses.append("(" + " OR ".join(f"deck:{quote(d)}" for d in decks) + ")")
    nts = [n for n in cfg.get("scope_note_types", []) if n]
    if nts:
        clauses.append("(" + " OR ".join(f"note:{quote(n)}" for n in nts) + ")")
    if cfg.get("exclude_suspended"):
        clauses.append("-is:suspended")
    return " ".join(clauses)


def scoped_note_ids(col, cfg: dict) -> list[int]:
    """All note ids within the configured scope (empty scope = whole deck)."""
    scope = build_scope_query(cfg)
    return find_note_ids(col, scope if scope else "")


# --------------------------------------------------------------------------- #
# Indexing iteration
# --------------------------------------------------------------------------- #
def iter_index_rows(col, nids: Iterable[int], fields_filter: list[str] | None,
                    max_chars: int) -> Iterator[tuple[int, int, str, list[str]]]:
    """Yield (note_id, mod, text, image_filenames) for the given notes.

    Pure reads. ``mod`` is the note's modification timestamp used for
    dirty-tracking; ``text`` is the concatenated field text for embedding.
    """
    for nid in nids:
        try:
            note = col.get_note(nid)
        except Exception:
            continue
        text = note_to_text(note, fields_filter, max_chars)
        images = note_images(note)
        yield int(nid), int(getattr(note, "mod", 0) or 0), text, images


# --------------------------------------------------------------------------- #
# Grounding summary (decks/tags/note types) for the LLM
# --------------------------------------------------------------------------- #
def collection_summary(col, max_decks: int, max_tags: int) -> dict:
    """A compact, read-only snapshot of the user's taxonomy to ground the model
    so it generates search strings that reference decks/tags that actually exist.
    """
    decks = _deck_names(col)
    tags = _tag_names(col)
    note_types = _note_type_info(col)
    return {
        "decks": _cap(decks, max_decks),
        "deck_count": len(decks),
        "tags": _cap(tags, max_tags),
        "tag_count": len(tags),
        "note_types": note_types,
    }


def _cap(items: list[str], n: int) -> list[str]:
    return items[:n] if n and len(items) > n else items


def _deck_names(col) -> list[str]:
    try:
        return sorted(d.name for d in col.decks.all_names_and_ids())
    except Exception:
        try:
            return sorted(d["name"] for d in col.decks.all())
        except Exception as e:
            log.warn(f"deck listing failed: {e}")
            return []


def _tag_names(col) -> list[str]:
    try:
        return sorted(col.tags.all())
    except Exception as e:
        log.warn(f"tag listing failed: {e}")
        return []


def _note_type_info(col) -> list[dict]:
    out: list[dict] = []
    try:
        for nt in col.models.all():
            out.append({
                "name": nt.get("name", ""),
                "fields": [f.get("name", "") for f in nt.get("flds", [])],
            })
    except Exception as e:
        log.warn(f"note type listing failed: {e}")
    return out


def media_dir(col) -> str:
    try:
        return col.media.dir()
    except Exception:
        return ""
