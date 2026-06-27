# -*- coding: utf-8 -*-
"""Orchestrate one assistant turn: LLM reasoning -> retrieval -> result cards.

Staged to keep the UI responsive and the collection unlocked during network I/O:

1. ``assistant_step`` (network worker, no collection): ask the local model for a
   reply + search string + clarifying question + related concepts; optionally
   embed the query for semantic search.
2. ``retrieval_step`` (read-only ``QueryOp``): run the keyword search, optionally
   the semantic scan, fuse with RRF, and build display cards.

The panel calls :func:`run_turn`, which chains these and reports back on the main
thread. Everything is read-only.
"""

from __future__ import annotations

import time
from typing import Callable

from .. import cfg as cfgmod
from .. import colread, log, ops
from ..ai import prompts
from ..ai.client import AIClient, extract_json
from ..index import embedder
from . import fusion, keyword, query_builder, semantic


# --------------------------------------------------------------------------- #
# Stage 1 — assistant reasoning + optional query embedding (network only)
# --------------------------------------------------------------------------- #
def assistant_step(cfg: dict, history: list[dict], user_text: str,
                   summary: dict, image_caption: str | None) -> dict:
    client = AIClient(cfg)
    messages = prompts.build_messages(history, user_text, summary, image_caption)
    raw = client.chat(messages, json_mode=True, json_schema=prompts.RESPONSE_SCHEMA)
    data = extract_json(raw)
    assistant = _normalize_assistant(data, raw)

    query_vec = None
    if cfg.get("semantic_enabled"):
        seed = " ".join(filter(None, [user_text, image_caption])).strip()
        if seed:
            try:
                query_vec = embedder.embed_query(client, cfg.get("embed_model", ""), seed)
            except Exception as e:
                log.warn(f"query embed failed: {e}")
    return {"assistant": assistant, "query_vec": query_vec}


def _normalize_assistant(data: dict, raw: str) -> dict:
    if not isinstance(data, dict):
        data = {}
    reply = (data.get("reply") or "").strip()
    if not reply:
        # Model didn't follow the JSON contract; degrade gracefully.
        reply = (raw or "").strip()[:500] or "Here's what I found."
    return {
        "reply": reply,
        "search_string": (data.get("search_string") or "").strip() or None,
        "clarifying_question": (data.get("clarifying_question") or "").strip() or None,
        "quick_replies": [str(x) for x in (data.get("quick_replies") or [])][:4],
        "related": [str(x) for x in (data.get("related") or [])][:6],
        "needs_semantic": bool(data.get("needs_semantic")),
    }


# --------------------------------------------------------------------------- #
# Stage 2 — retrieval (read-only collection)
# --------------------------------------------------------------------------- #
def retrieval_step(col, cfg: dict, payload: dict) -> dict:
    assistant = payload["assistant"]
    query_vec = payload.get("query_vec")
    search_string = assistant.get("search_string")
    max_results = int(cfg.get("max_results", 25))

    keyword_ids = keyword.run(col, cfg, search_string, limit=max_results * 4) \
        if search_string else []

    semantic_ids: list[int] = []
    image_hits: set[int] = set()
    if query_vec is not None:
        qbin, qf32 = query_vec
        # Restrict the semantic scan to the configured scope BEFORE truncation so a
        # subdeck scope never starves the top-K (C1).
        scope = colread.build_scope_query(cfg)
        allowed = set(colread.find_note_ids(col, scope)) if scope else None
        sem = semantic.search(qbin, qf32, top_k=max_results * 2,
                              candidates=int(cfg.get("semantic_candidates", 300)),
                              allowed=allowed)
        semantic_ids = [nid for nid, _score, _kind in sem]
        image_hits = {nid for nid, _s, kind in sem if kind == "image"}

    rankings = [r for r in (keyword_ids, semantic_ids) if r]
    if len(rankings) >= 2:
        final_ids = fusion.fuse_ids(rankings, k=int(cfg.get("rrf_k", 60)))
    elif rankings:
        final_ids = rankings[0]
    else:
        final_ids = []
    final_ids = final_ids[:max_results]

    results = _build_results(col, final_ids, image_hits)

    # The copy/paste string the user runs in the Browser. Prefer the readable
    # LLM string (lets them keep scrolling related cards); fall back to an exact
    # nid: match of what we actually surfaced.
    copy_string = search_string or query_builder.nid_query(final_ids)
    runnable = query_builder.scoped(cfg, search_string) if search_string \
        else query_builder.nid_query(final_ids)

    return {
        "results": results,
        "copy_string": copy_string,
        "runnable_string": runnable,
        "counts": {
            "keyword": len(keyword_ids),
            "semantic": len(semantic_ids),
            "shown": len(results),
        },
    }


def _build_results(col, note_ids: list[int], image_hits: set[int]) -> list[dict]:
    out: list[dict] = []
    for nid in note_ids:
        try:
            note = col.get_note(nid)
        except Exception:
            continue
        text = colread.note_to_text(note, None, 0)
        title = _first_field(note) or text[:80]
        cid = colread.first_card_id_for_note(col, nid)
        deck = ""
        flag = 0
        if cid is not None:
            try:
                card = col.get_card(cid)
                flag = int(getattr(card, "flags", 0) or 0)
                deck = col.decks.name(card.did)
            except Exception:
                pass
        out.append({
            "note_id": nid,
            "card_id": cid or 0,
            "title": title.strip()[:120],
            "snippet": text[:240],
            "note_type": colread.note_type_name(note),
            "tags": list(note.tags)[:6],
            "deck": deck,
            "flag": flag,
            "has_image": bool(colread.note_images(note)),
            "is_image_hit": nid in image_hits,
        })
    return out


def _first_field(note) -> str:
    try:
        for value in note.fields:
            t = colread.strip_html(value)
            if t:
                return t
    except Exception:
        pass
    return ""


# --------------------------------------------------------------------------- #
# Public: run a full turn
# --------------------------------------------------------------------------- #
def run_turn(history: list[dict], user_text: str, summary: dict,
             image_caption: str | None,
             on_result: Callable[[dict], None],
             on_error: Callable[[Exception], None]) -> None:
    cfg = cfgmod.get()
    started = time.monotonic()

    def net() -> dict:
        return assistant_step(cfg, history, user_text, summary, image_caption)

    def after_net(stage1: dict) -> None:
        def col_op(col) -> dict:
            stage2 = retrieval_step(col, cfg, stage1)
            stage2["assistant"] = stage1["assistant"]
            return stage2

        def after_col(stage2: dict) -> None:
            stage2["timing_ms"] = int((time.monotonic() - started) * 1000)
            stage2["model"] = cfg.get("chat_model", "")
            on_result(stage2)

        ops.run_query(col_op, after_col, on_error, uses_collection=True)

    ops.run_network(net, after_net, on_error)
