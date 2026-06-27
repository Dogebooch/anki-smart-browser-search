# Smart Browser Search — an AI card finder for Anki

> Ask for a card in plain English. Get the cards, a copy/paste search string, and
> related concepts — powered entirely by **local** AI, **read-only**, right inside
> Anki's Browser.

Built for medical residents and attendings drowning in a 30,000-card board deck,
but useful for anyone with a big collection. Type *“that syndrome with hypertension
and low potassium”* and it finds your Conn’s / hyperaldosteronism cards — even if
your card never says “low potassium”.

---

## What it does

- 🧠 **Natural-language search.** Describe a topic, fact, or concept; the assistant
  turns it into a real Anki search and shows the matching cards.
- 🩺 **Speaks medicine.** Expands acronyms (MI → myocardial infarction / STEMI),
  brand↔generic (Lasix ↔ furosemide), eponyms and classic findings — so searches
  are high-recall.
- 📋 **Hands you the search string.** Every answer includes a copy/paste-ready
  Browser search string with **Copy** and **Run in Browser** buttons, so you can
  keep scrolling the results natively.
- 🖼 **Picture search.** Indexes your card images (captions + OCR via a local vision
  model) — ideal for Image Occlusion, where the answer lives *in* the image. You
  can even drop in a screenshot and find matching cards.
- 💬 **Acts like an assistant.** Asks a clarifying question when your request is
  ambiguous (tap a quick-reply chip), and suggests **related / similar concepts**
  when nothing matches exactly.
- 🔒 **Cannot harm your deck.** The add-on is **read-only by construction** — there
  is no code path that edits, adds, deletes, or reschedules a card. A built-in
  one-click safety self-check proves it.
- 🏠 **100% local & private.** Works with Ollama (default) or any OpenAI-compatible
  server (LM Studio, llama.cpp, Jan, GPT4All). No cloud, no API keys, no data leaves
  your machine.
- ⚡ **Never freezes Anki.** All model calls and scans run in the background. The
  semantic engine uses binary-quantized vectors scanned with a CPU popcount — a
  40,000-card deck searches in milliseconds with **zero compiled dependencies**.
- 🎨 **Native look.** A dockable panel that matches Anki’s light/dark theme.

---

## Install

### 1. Install a local AI runtime (one-time)

**Ollama** (recommended — free, simple): download from <https://ollama.com>, then
pull the default models in a terminal:

```bash
ollama pull qwen2.5:7b-instruct     # the assistant (chat/reasoning)
ollama pull nomic-embed-text        # semantic search embeddings
ollama pull qwen2.5vl:7b            # vision model for picture search (optional)
```

> On an AMD GPU (e.g. RX 7900 XTX / gfx1100) Ollama uses ROCm automatically. On a
> small machine, swap the chat model for `llama3.2:3b` and the vision model for
> `moondream`.

Prefer **LM Studio** or **llama.cpp**? That works too — just point the add-on at
its OpenAI-compatible endpoint in Settings (e.g. `http://localhost:1234/v1`).

### 2. Install the add-on

- **From the release:** in Anki, **Tools → Add-ons → Install from file…** and pick
  `smart_browser_search.ankiaddon`.
- **From source:** run `python build.py` and install the file it writes to
  `dist/`. (Or copy `src/smart_browser_search` into your Anki `addons21/` folder.)

Restart Anki.

---

## Using it

1. Open the **Browse** window. A **Smart AI Search** panel docks on the right
   (toggle it with **Ctrl+Shift+F**, configurable).
2. Type a request — *“inferior MI ECG findings”* — and press **Enter**.
3. You get:
   - a short reply,
   - a **search string** (Copy / Run in Browser),
   - clickable **result cards** (click one to select & reveal it in the table),
   - **related concepts** as pills you can tap to explore.
4. Ambiguous request? The assistant asks a quick question with tap-to-answer chips.
5. **Picture search:** click the 🖼 button to search by an image, or enable image
   indexing in Settings so image-only cards become findable by their content.

### Settings

**Tools → Smart Browser Search: Settings…** (or the add-on’s **Config** button):
choose your backend/endpoint, pick models (with **Detect installed models**), set
max results, scope to specific decks, turn on semantic / picture search, rebind the
shortcut, and run the **read-only safety self-check**.

Semantic search and picture search are **opt-in** and build a background index the
first time. Plain keyword search works instantly with no index.

---

## Is my deck safe? (Yes.)

This add-on **only reads**. It calls Anki’s search and note-reading APIs and nothing
else — it never imports a write or scheduler API, and its index lives in a separate
database (`user_files/index.db`) that physically cannot touch `collection.anki2`.

You don’t have to take our word for it: **Settings → Run read-only safety
self-check** scans the add-on’s own source for any mutating call and reports the
result. See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full design.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| “Local AI offline” banner | Start your model server (`ollama serve`), or click **Start Ollama**. |
| “Model not installed” | Run the `ollama pull …` shown in the banner. |
| Semantic search finds nothing | Enable it in Settings and click **Build / update index**. |
| Picture search misses a card | Enable image indexing and rebuild; vision captioning is a one-time background pass. |
| Slow first response | The model is loading into memory (cold start). Subsequent queries are fast. |
| Wrong/no results | Use **Run in Browser** to tweak the generated search string by hand. |

---

## How it works (short version)

- **Tier 1 — keyword (always on, no index):** the local LLM, grounded in *your*
  decks/tags/note-types, rewrites your request into a valid Anki search string and
  runs it through Anki’s fast native search.
- **Tier 2 — semantic (opt-in):** notes are embedded once and stored as
  binary-quantized vectors; queries are matched with a popcount scan + float32
  rescore, then fused with the keyword results via Reciprocal Rank Fusion.
- **Picture search:** a vision model captions/OCRs card images at index time; those
  captions are embedded into the same index.

No numpy, no torch, no compiled wheels — just Python’s standard library and your
local AI server. That’s what keeps it plug-and-play across platforms and durable
across Anki updates.

---

## Development

```
src/smart_browser_search/   the add-on
  ├─ ai/        runtime-agnostic local-AI client + prompts
  ├─ index/     SQLite store, embedder, dirty-tracking, image captioning
  ├─ search/    query building, keyword + semantic search, fusion, pipeline
  ├─ ui/        dock, webview panel controller, settings dialog
  └─ web/       panel HTML/CSS/JS (inherits Anki's theme)
build.py        package into dist/*.ankiaddon
docs/           architecture & setup notes
```

Build: `python build.py`. License: [MIT](LICENSE).
