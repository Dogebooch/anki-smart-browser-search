# Smart Browser Search — configuration

Most people never need to touch this. Use **Tools → Smart AI Search Settings…** for a
friendly dialog instead. This page documents every key for power users.

> **Safety:** this add-on is **read-only**. It never edits, adds, deletes, or
> reschedules cards. It only *reads* your notes and *emits search strings*.

## Connection

- **`backend`** — `"ollama"` (native API, recommended) or `"openai"` (any
  OpenAI-compatible server: LM Studio, llama.cpp, Jan, GPT4All…).
- **`endpoint`** — base URL of your local AI server.
  Ollama → `http://localhost:11434`. For an OpenAI-compatible server include the
  `/v1` suffix, e.g. LM Studio → `http://localhost:1234/v1`.
- **`api_key`** — usually blank for local servers. Some clients require a
  non-empty string; any value works for Ollama.
- **`request_timeout`** — seconds to wait for a generation (cold model loads can
  be slow; keep this generous).
- **`connect_timeout`** — seconds for the quick "is the server up?" probe.

## Models

- **`chat_model`** — the assistant/reasoning model, e.g. `qwen2.5:7b-instruct`,
  `llama3.1:8b`, `llama3.2:3b` (smaller/faster).
- **`embed_model`** — embeddings model for semantic search, e.g.
  `nomic-embed-text` (768-dim, fast). Changing this rebuilds the index.
- **`vision_model`** — vision model for picture search / image captioning, e.g.
  `qwen2.5vl:7b`, `llava`, `moondream` (small/fast).
- **`temperature`**, **`num_ctx`** — generation knobs passed to the model.

Install the defaults with:
```
ollama pull qwen2.5:7b-instruct
ollama pull nomic-embed-text
ollama pull qwen2.5vl:7b
```

## Retrieval

- **`max_results`** — how many cards to show per search.
- **`semantic_enabled`** — turn on Tier-2 semantic search (requires building an
  index once). Off by default; keyword search works without it.
- **`image_search_enabled`** — index card images by captioning them with the
  vision model. Slow first pass; runs in the background.
- **`rrf_k`** — Reciprocal-Rank-Fusion constant (≈60) used to blend keyword and
  semantic results.
- **`semantic_candidates`** — how many nearest neighbours to rescore exactly.

## Scope (limit what gets searched/indexed)

- **`scope_decks`** — list of deck names to restrict to. Empty = all decks.
- **`scope_note_types`** — list of note type names. Empty = all.
- **`scope_fields`** — field names to include when embedding. Empty = all fields.
- **`exclude_suspended`** — skip suspended cards.

## UI / behaviour

- **`shortcut`** — keyboard shortcut to toggle the panel in the Browser.
- **`dock_area`** — `"right"` or `"left"`.
- **`open_on_browser_start`** — auto-open the panel when the Browser opens.
- **`auto_run_search`** — pressing *Run* also focuses the results table.
- **`show_latency`** — show the "N cards · ms · model" footer.
- **`max_history_turns`** — how many prior conversation turns to send the model.
- **`context_card_chars`** — max characters of a note shown to the model.
- **`ground_max_decks` / `ground_max_tags`** — how much of your deck/tag taxonomy
  to share with the model so it builds valid search strings.

## Diagnostics

- **`debug_logging`** — write a log to `user_files/smart_search.log`.
