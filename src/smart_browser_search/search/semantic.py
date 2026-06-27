# -*- coding: utf-8 -*-
"""Tier-2 retrieval: binary popcount scan + float32 rescore over the index.

The scan loads packed binary codes into Python ints once per session (cached and
invalidated when the index changes), then scores every vector with a C-level
``(a ^ q).bit_count()``. The best ``candidates`` are exactly re-ranked with
float32 cosine. ~7 ms for 40k vectors, no numpy.
"""

from __future__ import annotations

import os
import threading

from .. import log, paths, vectors
from ..index.store import IndexStore

_lock = threading.Lock()
_cache: dict = {"key": None, "vids": [], "note_ids": [], "bins": [], "kinds": [], "dim": 0}


def invalidate_cache() -> None:
    with _lock:
        _cache["key"] = None


def _index_signature(path: str) -> tuple | None:
    if not os.path.exists(path):
        return None
    sig = [os.path.getmtime(path), os.path.getsize(path)]
    for suffix in ("-wal", "-shm"):
        p = path + suffix
        if os.path.exists(p):
            sig.append(os.path.getmtime(p))
            sig.append(os.path.getsize(p))
    return tuple(sig)


def _load_arrays(path: str) -> dict:
    sig = _index_signature(path)
    with _lock:
        if _cache["key"] == sig and sig is not None:
            return _cache
    store = IndexStore(path)
    try:
        vids, note_ids, bins, kinds = store.load_scan()
        dim = int(store.get_meta().get("dim", "0") or 0)
    finally:
        store.close()
    with _lock:
        _cache.update({"key": sig, "vids": vids, "note_ids": note_ids,
                       "bins": bins, "kinds": kinds, "dim": dim})
    return _cache


def has_index() -> bool:
    arrays = _load_arrays(paths.index_db_path())
    return bool(arrays["bins"])


def search(query_bin: int, query_f32: list[float], top_k: int,
           candidates: int = 300,
           allowed: set[int] | None = None) -> list[tuple[int, float, str]]:
    """Return ``[(note_id, score, kind), ...]`` best-first.

    ``kind`` is 'text' or 'image' (so the UI can flag picture hits). ``allowed``,
    if given, restricts the scan to those note ids (the configured scope) BEFORE
    truncation so scoping never starves the result set.

    Returns ``[]`` if the query's embedding dimension doesn't match the stored
    index (e.g. the embedding model changed without a rebuild) — the caller then
    falls back to keyword-only rather than ranking on garbage Hamming distances.
    """
    path = paths.index_db_path()
    arrays = _load_arrays(path)
    bins = arrays["bins"]
    if not bins:
        return []
    note_ids = arrays["note_ids"]
    vids = arrays["vids"]
    kinds = arrays["kinds"]
    dim = arrays["dim"] or 1

    # Guard: query and index must share an embedding space, or Hamming is meaningless.
    if query_f32 and dim and len(query_f32) != dim:
        log.warn(f"semantic skipped: query dim {len(query_f32)} != index dim {dim} "
                 f"(rebuild the index after changing the embedding model)")
        return []

    # Stage 1: Hamming over all (in-scope) vectors — the fast popcount scan.
    scored: list[tuple[int, int]] = []
    if allowed is None:
        for idx, b in enumerate(bins):
            scored.append(((b ^ query_bin).bit_count(), idx))
    else:
        for idx, b in enumerate(bins):
            if note_ids[idx] in allowed:
                scored.append(((b ^ query_bin).bit_count(), idx))
    if not scored:
        return []
    scored.sort(key=lambda t: t[0])
    cand = scored[: max(candidates, top_k)]

    # Stage 2: exact float32 cosine rescore of the candidates.
    cand_vids = [vids[idx] for _h, idx in cand]
    store = IndexStore(path)
    try:
        f32map = store.fetch_f32(cand_vids)
    except Exception as e:
        log.warn(f"f32 rescore fetch failed: {e}")
        f32map = {}
    finally:
        store.close()

    best: dict[int, tuple[float, str]] = {}
    for h, idx in cand:
        vid = vids[idx]
        nid = note_ids[idx]
        kind = kinds[idx]
        blob = f32map.get(vid)
        if blob:
            score = vectors.cosine(query_f32, vectors.unpack_f32(blob))
        else:
            # Fallback mapped to cosine's [-1, 1] range so mixed rows rank fairly.
            score = 1.0 - 2.0 * (h / dim)
        prev = best.get(nid)
        if prev is None or score > prev[0]:
            best[nid] = (score, kind)

    ranked = sorted(best.items(), key=lambda kv: kv[1][0], reverse=True)
    return [(nid, sc, kind) for nid, (sc, kind) in ranked[:top_k]]
