# -*- coding: utf-8 -*-
"""SQLite-backed semantic index.

Lives in ``user_files/index.db`` — a database physically separate from the
user's ``collection.anki2``, so indexing literally cannot touch their data.
Uses only the stdlib ``sqlite3``. All writes are transactional, so a crash
mid-reindex never corrupts the index.

Tables
------
``meta``     key/value: embedding model, dimension, schema version.
``notes``    per-note dirty-tracking state (mod, content hash, image hash).
``vectors``  one row per embedded chunk (a note's text, or one image caption);
             holds the packed binary code (scanned) and float32 bytes (rescore).
``images``   per-image caption text (for display / debugging).
"""

from __future__ import annotations

import os
import sqlite3
from typing import Iterable

from .. import const, log


class IndexStore:
    def __init__(self, path: str):
        self.path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.con = sqlite3.connect(path, timeout=30)
        self.con.execute("PRAGMA journal_mode=WAL")
        self.con.execute("PRAGMA synchronous=NORMAL")
        self._ensure_schema()

    # ------------------------------------------------------------------ #
    def _ensure_schema(self) -> None:
        c = self.con
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT
            );
            CREATE TABLE IF NOT EXISTS notes (
                note_id INTEGER PRIMARY KEY,
                mod INTEGER,
                content_hash TEXT,
                img_hash TEXT
            );
            CREATE TABLE IF NOT EXISTS vectors (
                vid INTEGER PRIMARY KEY AUTOINCREMENT,
                note_id INTEGER NOT NULL,
                kind TEXT NOT NULL,
                ref TEXT DEFAULT '',
                bin_vec BLOB NOT NULL,
                f32_vec BLOB
            );
            CREATE INDEX IF NOT EXISTS ix_vectors_note ON vectors(note_id);
            CREATE TABLE IF NOT EXISTS images (
                note_id INTEGER NOT NULL,
                filename TEXT NOT NULL,
                caption TEXT,
                PRIMARY KEY (note_id, filename)
            );
            """
        )
        c.commit()

    # ------------------------------------------------------------------ #
    # Meta / compatibility
    # ------------------------------------------------------------------ #
    def get_meta(self) -> dict:
        rows = self.con.execute("SELECT key, value FROM meta").fetchall()
        return {k: v for k, v in rows}

    def set_meta(self, model: str, dim: int) -> None:
        items = {
            "model": model,
            "dim": str(dim),
            "schema_version": str(const.SCHEMA_VERSION),
        }
        self.con.executemany(
            "INSERT INTO meta(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            list(items.items()),
        )
        self.con.commit()

    def is_compatible(self, model: str, dim: int) -> bool:
        meta = self.get_meta()
        if not meta:
            return True  # fresh index
        return (
            meta.get("model") == model
            and meta.get("dim") == str(dim)
            and meta.get("schema_version") == str(const.SCHEMA_VERSION)
        )

    def reset(self) -> None:
        """Wipe all vectors/notes (e.g. when the embedding model changed)."""
        self.con.executescript(
            "DELETE FROM vectors; DELETE FROM notes; DELETE FROM images; DELETE FROM meta;"
        )
        self.con.commit()

    # ------------------------------------------------------------------ #
    # Dirty tracking
    # ------------------------------------------------------------------ #
    def all_note_states(self) -> dict[int, tuple[int, str, str]]:
        rows = self.con.execute(
            "SELECT note_id, mod, content_hash, img_hash FROM notes"
        ).fetchall()
        return {r[0]: (r[1], r[2] or "", r[3] or "") for r in rows}

    def upsert_note_state(self, note_id: int, mod: int, content_hash: str,
                          img_hash: str) -> None:
        self.con.execute(
            "INSERT INTO notes(note_id, mod, content_hash, img_hash) VALUES(?,?,?,?) "
            "ON CONFLICT(note_id) DO UPDATE SET mod=excluded.mod, "
            "content_hash=excluded.content_hash, img_hash=excluded.img_hash",
            (note_id, mod, content_hash, img_hash),
        )

    def delete_notes(self, note_ids: Iterable[int]) -> None:
        ids = [(int(n),) for n in note_ids]
        if not ids:
            return
        self.con.executemany("DELETE FROM vectors WHERE note_id=?", ids)
        self.con.executemany("DELETE FROM notes WHERE note_id=?", ids)
        self.con.executemany("DELETE FROM images WHERE note_id=?", ids)
        self.con.commit()

    # ------------------------------------------------------------------ #
    # Vector writes
    # ------------------------------------------------------------------ #
    def replace_text_vector(self, note_id: int, bin_vec: bytes,
                            f32_vec: bytes | None) -> None:
        self.con.execute(
            "DELETE FROM vectors WHERE note_id=? AND kind='text'", (note_id,)
        )
        self.con.execute(
            "INSERT INTO vectors(note_id, kind, ref, bin_vec, f32_vec) "
            "VALUES(?, 'text', '', ?, ?)",
            (note_id, bin_vec, f32_vec),
        )

    def replace_image_vectors(self, note_id: int,
                              rows: list[tuple[str, str, bytes, bytes | None]]) -> None:
        """rows: list of (filename, caption, bin_vec, f32_vec)."""
        self.con.execute(
            "DELETE FROM vectors WHERE note_id=? AND kind='image'", (note_id,)
        )
        self.con.execute("DELETE FROM images WHERE note_id=?", (note_id,))
        for filename, caption, bin_vec, f32_vec in rows:
            self.con.execute(
                "INSERT INTO vectors(note_id, kind, ref, bin_vec, f32_vec) "
                "VALUES(?, 'image', ?, ?, ?)",
                (note_id, filename, bin_vec, f32_vec),
            )
            self.con.execute(
                "INSERT INTO images(note_id, filename, caption) VALUES(?,?,?) "
                "ON CONFLICT(note_id, filename) DO UPDATE SET caption=excluded.caption",
                (note_id, filename, caption),
            )

    def commit(self) -> None:
        self.con.commit()

    # ------------------------------------------------------------------ #
    # Reads for the scan
    # ------------------------------------------------------------------ #
    def load_scan(self) -> tuple[list[int], list[int], list[int], list[str]]:
        """Return parallel lists (vids, note_ids, bin_ints, kinds) for scanning."""
        vids: list[int] = []
        note_ids: list[int] = []
        bins: list[int] = []
        kinds: list[str] = []
        for vid, nid, kind, blob in self.con.execute(
            "SELECT vid, note_id, kind, bin_vec FROM vectors"
        ):
            vids.append(vid)
            note_ids.append(nid)
            kinds.append(kind)
            bins.append(int.from_bytes(blob, "big"))
        return vids, note_ids, bins, kinds

    def fetch_f32(self, vids: list[int]) -> dict[int, bytes]:
        if not vids:
            return {}
        out: dict[int, bytes] = {}
        # Chunk to keep the SQL parameter list sane.
        for i in range(0, len(vids), 400):
            chunk = vids[i:i + 400]
            ph = ",".join("?" * len(chunk))
            for vid, blob in self.con.execute(
                f"SELECT vid, f32_vec FROM vectors WHERE vid IN ({ph})", chunk
            ):
                if blob is not None:
                    out[vid] = blob
        return out

    def counts(self) -> dict:
        nv = self.con.execute("SELECT COUNT(*) FROM vectors").fetchone()[0]
        nn = self.con.execute("SELECT COUNT(*) FROM notes").fetchone()[0]
        ni = self.con.execute(
            "SELECT COUNT(*) FROM vectors WHERE kind='image'"
        ).fetchone()[0]
        return {"vectors": nv, "notes": nn, "image_vectors": ni}

    # ------------------------------------------------------------------ #
    def close(self) -> None:
        try:
            self.con.close()
        except Exception as e:  # pragma: no cover
            log.warn(f"index close failed: {e}")

    def __enter__(self) -> "IndexStore":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
