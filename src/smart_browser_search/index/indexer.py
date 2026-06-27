# -*- coding: utf-8 -*-
"""Index orchestration: dirty-diff (read-only) -> embed/caption -> store.

Two stages so we never hold the collection during slow network calls:

1. **Scan** (``QueryOp``, read-only collection): figure out which notes are new,
   changed, or deleted by comparing ``(mod, content_hash, img_hash)`` against the
   index. Reads note text/images only — no embedding here.
2. **Embed** (``taskman`` worker, no collection): call the embedding/vision models
   in batches, write vectors to ``index.db`` with a determinate progress bar.

Re-running is cheap: an unchanged 40k-note deck does stage 1 (hashing) and stops.
"""

from __future__ import annotations

import threading
from typing import Callable

from .. import cfg as cfgmod
from .. import colread, log, ops, paths
from ..ai.client import AIClient
from . import embedder, images
from .store import IndexStore

EMBED_BATCH = 48
_running = False


def is_running() -> bool:
    return _running


# --------------------------------------------------------------------------- #
# Stage 1: scan (read-only collection)
# --------------------------------------------------------------------------- #
def _scan(col, cfg: dict, force_rebuild: bool) -> dict:
    fields_filter = cfg.get("scope_fields") or None
    max_chars = 0  # embed full note text; context truncation is a UI concern
    image_enabled = bool(cfg.get("image_search_enabled"))
    model = cfg.get("embed_model") or ""

    store = IndexStore(paths.index_db_path())
    try:
        if force_rebuild or (store.get_meta() and store.get_meta().get("model") != model):
            store.reset()
        indexed = store.all_note_states()
    finally:
        store.close()

    scope_nids = colread.scoped_note_ids(col, cfg)
    scope_set = set(scope_nids)
    to_delete = [nid for nid in indexed.keys() if nid not in scope_set]

    work: list[dict] = []
    for nid, mod, text, imgs in colread.iter_index_rows(
        col, scope_nids, fields_filter, max_chars
    ):
        content_hash = embedder.hash_text(text)
        img_hash = embedder.hash_images(imgs) if image_enabled else ""
        prev = indexed.get(nid)
        need_text = prev is None or prev[1] != content_hash
        need_images = image_enabled and (prev is None or prev[2] != img_hash) and bool(imgs)
        if need_text or need_images:
            work.append({
                "note_id": nid, "mod": mod, "text": text,
                "content_hash": content_hash, "images": imgs, "img_hash": img_hash,
                "need_text": need_text, "need_images": need_images,
            })

    return {
        "work": work,
        "to_delete": to_delete,
        "model": model,
        "image_enabled": image_enabled,
        "scope_total": len(scope_nids),
    }


# --------------------------------------------------------------------------- #
# Stage 2: embed + caption (no collection)
# --------------------------------------------------------------------------- #
# After this many consecutive failed batches we assume the server died and stop,
# rather than grinding through the whole deck hitting timeouts.
_MAX_CONSECUTIVE_FAILURES = 3


def _progress(value: int, maximum: int, label: str, cancel) -> None:
    """Marshal a progress update to the main thread and, while there, read the
    cancel flag off the (Qt) progress dialog and mirror it into ``cancel`` — so
    the worker thread never touches Qt directly (M1)."""
    from aqt import mw

    def _u():
        try:
            mw.progress.update(value=value, max=maximum, label=label)
            if mw.progress.want_cancel():
                cancel.set()
        except Exception:
            pass
    ops.on_main(_u)


def _embed_and_store(payload: dict, cfg: dict, cancel) -> dict:
    client = AIClient(cfg)
    model = payload["model"]
    media_dir = payload.get("media_dir", "")
    work = payload["work"]
    to_delete = payload["to_delete"]
    image_enabled = payload["image_enabled"]

    stats = {"embedded": 0, "captioned": 0, "deleted": len(to_delete),
             "skipped": 0, "cancelled": False, "errors": 0}

    store = IndexStore(paths.index_db_path())
    try:
        if to_delete:
            store.delete_notes(to_delete)

        text_items = [w for w in work if w["need_text"]]
        total = len(text_items) + sum(1 for w in work if w["need_images"])
        done = 0
        consecutive_failures = 0

        # --- text vectors, batched ---
        for i in range(0, len(text_items), EMBED_BATCH):
            if cancel.is_set():
                stats["cancelled"] = True
                break
            batch = text_items[i:i + EMBED_BATCH]
            texts = [w["text"] for w in batch]
            try:
                pairs, d = embedder.embed_batch(client, model, texts, "document")
                consecutive_failures = 0
            except Exception as e:
                log.error("embedding batch failed", e)
                stats["errors"] += 1
                consecutive_failures += 1
                # Skip just this batch (its notes stay dirty and retry next run);
                # bail only if the server appears to be down (H5a).
                if consecutive_failures >= _MAX_CONSECUTIVE_FAILURES:
                    break
                done += len(batch)
                _progress(done, total, f"Embedding cards… {done}/{total}", cancel)
                continue
            if d:
                if not store.is_compatible(model, d):
                    store.reset()
                store.set_meta(model, d)
            for w, (bin_bytes, f32_bytes) in zip(batch, pairs):
                if bin_bytes:
                    store.replace_text_vector(w["note_id"], bin_bytes, f32_bytes)
                    store.upsert_note_state(w["note_id"], w["mod"],
                                            w["content_hash"], w["img_hash"])
                    stats["embedded"] += 1
                else:
                    stats["skipped"] += 1
            store.commit()
            done += len(batch)
            _progress(done, total, f"Embedding cards… {done}/{total}", cancel)

        # --- image captions (optional, slow) ---
        if image_enabled and not stats["cancelled"]:
            image_items = [w for w in work if w["need_images"]]
            for w in image_items:
                if cancel.is_set():
                    stats["cancelled"] = True
                    break
                captions: list[str] = []
                for fn in w["images"]:
                    cap = images.caption_image(client, media_dir, fn)
                    if cap:
                        captions.append(f"{fn}: {cap}")
                        stats["captioned"] += 1
                if captions:
                    combined = "  ".join(captions)
                    try:
                        pairs, d = embedder.embed_batch(client, model, [combined], "document")
                        if d:
                            if not store.is_compatible(model, d):  # L8: mirror text path
                                store.reset()
                            store.set_meta(model, d)
                        bin_bytes, f32_bytes = pairs[0]
                        if bin_bytes:
                            ref = ";".join(w["images"])[:300]
                            store.replace_image_vectors(
                                w["note_id"], [(ref, combined, bin_bytes, f32_bytes)]
                            )
                    except Exception as e:
                        # Don't loop forever re-captioning: record the hash anyway
                        # (the note just won't be image-searchable until it changes
                        # or a full rebuild) (H5b).
                        log.error("image caption embed failed", e)
                        stats["errors"] += 1
                # Mark this note's image state clean so we don't re-caption it.
                store.upsert_note_state(w["note_id"], w["mod"],
                                        w["content_hash"], w["img_hash"])
                store.commit()
                done += 1
                _progress(done, total, f"Reading images… {done}/{total}", cancel)

        store.commit()
        stats["counts"] = store.counts()
    finally:
        store.close()
    return stats


# --------------------------------------------------------------------------- #
# Public entry
# --------------------------------------------------------------------------- #
_progress_open = False


def run_index(force_rebuild: bool = False,
              on_done: Callable[[dict], None] | None = None) -> None:
    """Build/refresh the semantic index in the background. Safe to call anytime.

    Nothing here blocks the UI thread: the liveness probe, the collection scan,
    and the embedding all run in the background, with a single progress dialog.
    """
    global _running
    from aqt.utils import tooltip

    if _running:
        tooltip("Smart Search: indexing already in progress…")
        return

    cfg = cfgmod.get()
    _running = True
    cancel = threading.Event()

    # 1) Liveness probe OFF the main thread (H2).
    def probe() -> bool:
        return AIClient(cfg).is_alive()

    def after_probe(alive: bool) -> None:
        if not alive:
            _finish({"error": "offline"}, on_done)
            return
        _start_progress("Smart Search: scanning notes…")
        ops.run_query(scan_op, after_scan, scan_fail, uses_collection=True)

    # 2) Read-only collection scan.
    def scan_op(col) -> dict:
        payload = _scan(col, cfg, force_rebuild)
        payload["media_dir"] = colread.media_dir(col)
        return payload

    def after_scan(payload: dict) -> None:
        work = payload.get("work", [])
        to_delete = payload.get("to_delete", [])
        if not work and not to_delete:
            _finish({"embedded": 0, "deleted": 0, "skipped": 0,
                     "cancelled": False, "up_to_date": True}, on_done)
            return
        text_n = sum(1 for w in work if w["need_text"])
        img_n = sum(1 for w in work if w["need_images"])
        _update_progress(
            f"Smart Search: indexing {text_n} cards"
            + (f", {img_n} with images" if img_n else "") + "…",
            text_n + img_n)
        # 3) Embed/caption OFF the collection executor (no collection needed).
        ops.run_network(
            lambda: _embed_and_store(payload, cfg, cancel),
            success=lambda stats: _finish(stats, on_done),
            failure=lambda exc: _finish({"error": str(exc)}, on_done),
        )

    def scan_fail(exc: Exception) -> None:
        _finish({"error": str(exc)}, on_done)

    ops.run_network(probe, after_probe,
                    failure=lambda exc: _finish({"error": str(exc)}, on_done))


def _start_progress(label: str) -> None:
    global _progress_open
    from aqt import mw
    try:
        mw.progress.start(label=label, immediate=True)
        _progress_open = True
    except Exception:
        _progress_open = False


def _update_progress(label: str, maximum: int) -> None:
    from aqt import mw
    try:
        mw.progress.update(label=label, value=0, max=maximum)
    except Exception:
        pass


def _finish(stats: dict, on_done: Callable[[dict], None] | None) -> None:
    global _running, _progress_open
    from aqt import mw
    from aqt.utils import tooltip

    _running = False
    if _progress_open:
        try:
            mw.progress.finish()
        except Exception:
            pass
        _progress_open = False

    # Make any newly written vectors visible to the next search immediately (L9).
    try:
        from ..search import semantic
        semantic.invalidate_cache()
    except Exception:
        pass

    errors = stats.get("errors", 0)
    if stats.get("error") == "offline":
        tooltip("Smart Search: local AI isn't reachable — start it, then rebuild.")
    elif "error" in stats:
        tooltip(f"Smart Search: indexing error — {stats['error']}")
    elif stats.get("up_to_date"):
        tooltip("Smart Search: index already up to date ✓")
    elif stats.get("cancelled"):
        tooltip(f"Smart Search: indexing cancelled ({stats.get('embedded',0)} done)")
    else:
        msg = f"Smart Search: indexed {stats.get('embedded',0)} cards"
        if stats.get("captioned"):
            msg += f", {stats['captioned']} images"
        if errors:
            msg += f" ⚠ {errors} batch(es) failed — rerun to finish"
        tooltip(msg + (" ✓" if not errors else ""))
    if on_done:
        on_done(stats)
