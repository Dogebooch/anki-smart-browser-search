# Architecture

Smart Browser Search is an AI assistant docked in the Anki Browser that turns
natural-language questions (and images) into ranked card results plus a copy/paste
Anki search string — running against **local** models, **read-only**, without ever
blocking the UI.

## Principles

1. **Read-only by construction.** No write/scheduler API is ever imported. The
   index is a separate database. `safety.py` scans the source to prove it.
2. **Zero compiled dependencies.** Standard library only (`urllib`, `sqlite3`,
   `array`, `hashlib`). No numpy/torch — so it never breaks on an Anki Python bump
   and installs cleanly on every OS.
3. **Never block the UI.** Collection reads run in read-only `QueryOp`s; network
   calls run on `taskman` workers; results are marshalled to the main thread.
4. **Useful instantly.** Tier-1 keyword search needs no index. Semantic and picture
   search are opt-in background builds.

## Module map

| Module | Responsibility |
|---|---|
| `__init__.py` | Register hooks, Tools-menu settings, Browser dock. Thin. |
| `const.py` / `config.json` | Defaults and shared constants. |
| `cfg.py` | Config read/write with defensive backfill. |
| `paths.py` | `user_files/`, `web/`, `index.db` locations. |
| `colread.py` | **The only** collection-access module — strictly read-only. |
| `safety.py` | Source self-scan that enforces the read-only invariant. |
| `ops.py` | `QueryOp` / `taskman` background helpers. |
| `vectors.py` | Binary quantize, popcount Hamming, float32 cosine. |
| `ai/client.py` | Runtime-agnostic client: Ollama `/api` + OpenAI `/v1`. |
| `ai/prompts.py` | System prompt, JSON contract, embedding prefixes, vision prompts. |
| `index/store.py` | SQLite schema, upsert, scan-load, model-change invalidation. |
| `index/embedder.py` | Batch embed + binary/float32 packing + hashing. |
| `index/images.py` | Vision caption/OCR for picture search. |
| `index/indexer.py` | Scan (read-only) → embed/caption (background) orchestration. |
| `search/keyword.py` | Tier-1 keyword retrieval via Anki FTS. |
| `search/semantic.py` | Tier-2 popcount scan + float32 rescore (cached). |
| `search/fusion.py` | Reciprocal Rank Fusion. |
| `search/query_builder.py` | Sanitize/scope/`nid:` search strings. |
| `search/pipeline.py` | One assistant turn: LLM → retrieval → result cards. |
| `ui/dock.py` | `QDockWidget` + toggle action + shortcut. |
| `ui/panel.py` | Webview controller and `pycmd` bridge. |
| `ui/settings.py` | Settings dialog. |
| `web/` | `panel.html` / `.css` / `.js`. |

## Retrieval pipeline (one turn)

```
user text (+ optional image)
        │
        ▼  ai/client.chat  (network worker, no collection lock)
LLM → { reply, search_string, clarifying_question, quick_replies, related, needs_semantic }
        │  (+ optional query embedding if semantic is on)
        ▼  QueryOp  (read-only collection)
 keyword.run(search_string)  ─┐
 semantic.search(query_vec)  ─┤→ fusion.rrf → top-K note ids → result cards
        │
        ▼  back on the main thread
 panel renders reply, search-string card, results, related pills, footer
```

## The performance decision: binary quantization

Anki ships its own Python and **does not bundle numpy**; bundling compiled wheels
cross-platform is exactly what breaks plug-and-play and what breaks on Anki Python
bumps. So the engine uses **no compiled code**.

Each embedding is stored twice:

- a **binary code** (sign of each dimension, packed to `dim/8` bytes). At query
  time these load into Python `int`s and similarity is scored with
  `(a ^ q).bit_count()` — a C-level popcount available since Python 3.10 (Anki's
  minimum). A full 40k×768-bit scan is ~7 ms.
- the **float32** vector, used only to exactly re-rank the top few hundred binary
  candidates so recall stays high (~98%).

Storage is a single SQLite DB in `user_files/`, transactional (a crash mid-reindex
never corrupts it) and incrementally updated via `(mod, content_hash, img_hash)`
dirty-tracking, so re-indexing an unchanged deck is sub-second.

## Picture search reality

Local runtimes (Ollama, etc.) have **no image-embedding endpoint**, so true
image-vector similarity isn't available without heavy compiled deps. Instead we
caption + OCR each card image once with a local vision model and embed the
resulting *text* into the same index. This is exactly right for Image Occlusion
cards. It is honest, caption-based matching — and vision inference never runs on
the query path.

## Verified Anki APIs used

- Hooks: `profile_did_open`, `browser_will_show`, `theme_did_change`.
- Tools menu via `mw.form.menuTools`; Config via `mw.addonManager.setConfigAction`.
- Dock via `browser.addDockWidget` + `QDockWidget`.
- Webview via `AnkiWebView.stdHtml` / `set_bridge_command` / `eval`; assets served
  from `/_addons/<pkg>/web/` with `setWebExports`.
- Read-only: `col.find_notes/find_cards/get_note/get_card`, `col.media.dir()`.
- Drive the Browser: `browser.search_for`, `browser.table.select_single_card`.
- Background: `aqt.operations.QueryOp`, `mw.taskman`.
