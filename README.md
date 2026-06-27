# Smart Browser Search — an AI card finder for Anki

> Ask for a card in plain English. Get the matching cards, a copy/paste search
> string, and related concepts — powered entirely by **local** AI, **read-only**,
> right inside Anki's Browser.

Built for medical residents and attendings drowning in a 30,000-card board deck,
but useful for anyone with a big collection. Type *"that syndrome with hypertension
and low potassium"* and it finds your Conn's / hyperaldosteronism cards — even if
the card never says "low potassium."

- **100% local & private** — runs on Ollama (or any OpenAI-compatible server). No
  cloud, no API keys, nothing leaves your computer.
- **Read-only by construction** — it physically cannot edit, add, delete, or
  reschedule a card. There's a one-click proof in Settings.
- **No heavy dependencies** — pure Python standard library, so it won't break when
  Anki updates its Python.

---

## Table of contents

1. [What it does](#what-it-does)
2. [Requirements](#requirements)
3. [Install](#install)
4. [Choosing your AI model (Light / Medium / High)](#choosing-your-ai-model)
5. [How to use it](#how-to-use-it) — with descriptions of every screen
6. [The Settings dialog, field by field](#the-settings-dialog-field-by-field)
7. [Semantic search & picture search](#semantic-search--picture-search)
8. [Is my deck safe? (Yes)](#is-my-deck-safe-yes)
9. [Troubleshooting](#troubleshooting)
10. [How it works](#how-it-works)
11. [Privacy](#privacy)
12. [For developers](#for-developers)
13. [License](#license)

---

## What it does

- 🧠 **Natural-language search.** Describe a topic, fact, or concept; the assistant
  turns it into a real Anki search and shows the matching cards.
- 🩺 **Speaks medicine.** Expands acronyms (MI → myocardial infarction / STEMI),
  brand ↔ generic (Lasix ↔ furosemide), eponyms, and classic findings — so searches
  are high-recall.
- 📋 **Hands you the search string.** Every answer includes a copy/paste-ready
  Browser search string with **Copy** and **Run in Browser** buttons, so you can
  keep scrolling the results natively.
- 🖼 **Picture search.** Optionally indexes your card images (captions + OCR via a
  local vision model) — ideal for Image Occlusion, where the answer lives *in* the
  image. You can even drop in a screenshot and find matching cards.
- 💬 **Acts like an assistant.** Asks a clarifying question when your request is
  ambiguous (tap a quick-reply chip), and suggests **related concepts** when nothing
  matches exactly.
- 🔒 **Cannot harm your deck.** Read-only by construction; a built-in safety
  self-check proves it.
- ⚡ **Never freezes Anki.** All model calls and scans run in the background. A
  40,000-card deck searches in milliseconds with zero compiled dependencies.
- 🎨 **Native look.** A dockable panel that matches Anki's light/dark theme.

---

## Requirements

- **Anki 24.06 or newer** (Qt6 build), desktop. Not the mobile apps.
- **A local AI runtime.** The add-on talks to AI you run on your own machine; it does
  **not** bundle one. Two supported options:
  - **[Ollama](https://ollama.com)** — recommended, free, one-click installer.
  - Any **OpenAI-compatible** server: LM Studio, llama.cpp, Jan, GPT4All.
- Enough disk and memory for one chat model (as little as ~2 GB on the Light tier —
  see [Choosing your AI model](#choosing-your-ai-model)).

> A dedicated GPU makes it fast but is **not required** — the Light tier runs on CPU,
> integrated graphics, or a laptop. It's just slower per query.

---

## Install

### Step 1 — install a local AI runtime (one-time)

**Ollama (recommended):** download from <https://ollama.com> and run the installer.
Ollama then runs quietly in the background and the add-on talks to it automatically.
You don't have to pull any models by hand — the add-on can download them for you
(see the next section).

> Prefer **LM Studio / llama.cpp / Jan**? Install it, load a model, and start its
> local server. Then in the add-on's Settings choose the *OpenAI-compatible* backend
> and point it at that server's URL (e.g. `http://localhost:1234/v1`).

### Step 2 — install the add-on

Pick whichever applies:

- **From AnkiWeb (easiest):** in Anki, **Tools → Add-ons → Get Add-ons…**, paste the
  add-on's code, click **OK**, then restart Anki.
- **From a file:** **Tools → Add-ons → Install from file…** and choose
  `smart_browser_search.ankiaddon`. Restart Anki.
- **From source:** run `python build.py` and install the `.ankiaddon` it writes to
  `dist/`. (Or copy `src/smart_browser_search` into your Anki `addons21/` folder.)

### Step 3 — pick and download a model

Open **Tools → Smart Browser Search: Settings…**, choose a tier under **Recommended
models**, click **Use these models**, then **Download with Ollama**. Details below.

---

## Choosing your AI model

The add-on ships set to the **Light** tier so it works on any machine out of the box.
If your computer is stronger, switch to **Medium** or **High** for sharper results —
the heavier the model, the better it understands messy, abbreviation-heavy requests.

In **Settings → Recommended models**, pick the tier that matches your graphics card,
click **Use these models** (fills in the model names), then **Download with Ollama**
(fetches any you don't already have). The NVIDIA cards below are a baseline; an AMD
or Apple chip with similar memory works the same.

| Tier | Chat model | Chat download | GPU memory needed | Pick this if you have… |
|------|-----------|---------------|-------------------|------------------------|
| **Light** *(default)* | `qwen2.5:3b-instruct` | ≈ 1.9 GB | ~4 GB, or **no GPU** (CPU works, slower) | No dedicated GPU, integrated graphics, most laptops, Apple M1/M2, or NVIDIA **GTX 1650 / RTX 3050** (~4 GB) |
| **Medium** | `qwen2.5:7b-instruct` | ≈ 4.7 GB | ~8 GB | A mainstream gaming GPU with 8–12 GB: NVIDIA **RTX 3060 / 4060 / 4060 Ti / 3070**, or Apple M-series with 16 GB |
| **High** | `qwen2.5:14b-instruct` | ≈ 9 GB | ~16 GB | A high-end GPU with 16 GB+: NVIDIA **RTX 4070 Ti / 4080 / 3090 / 4090**, or AMD **RX 7900 XT / XTX** |

Every tier also uses:

- **Embeddings:** `nomic-embed-text` (~0.3 GB) — only needed if you turn on semantic
  search. Same on all tiers.
- **Vision:** `moondream` (~1.7 GB) on Light, `qwen2.5vl:7b` (~6 GB) on Medium/High —
  only needed if you turn on picture search, and it only loads while indexing images.

**Rules of thumb**

- *Not sure?* Stay on **Light**. It's instant to set up and good enough for most
  searches.
- *Have a gaming PC from the last few years?* Use **Medium** — the best
  quality-for-size balance.
- *Have a 16 GB+ enthusiast card?* Use **High** for the most accurate medical reasoning.
- *Downloading is too slow / disk is tight?* You only need the **chat** model to start;
  embeddings and vision are optional and only matter once you enable semantic or
  picture search.

> **Using LM Studio / llama.cpp instead of Ollama?** The **Download with Ollama**
> button is Ollama-only. Load equivalent models in your app, then type their names
> into the **Models** fields in Settings.

---

## How to use it

### Opening the panel

1. Open Anki's **Browse** window (press `b`, or **Tools → Browse**).
2. A panel docks on the **right** side of the Browse window. Toggle it any time with
   **Ctrl+Shift+F** (you can rebind this in Settings).

**What you see:** a slim panel with a header reading **✦ Smart AI Search** and two
icon buttons in the top-right — **⟲** (start a new chat) and **⚙** (open Settings).
Before you've typed anything, the body shows a welcome card — *"Find any card, in
plain English"* — with a row of example chips you can click to try
(*inferior MI ECG findings*, *cards with ECG images*, *Wellens syndrome*, etc.). At
the very bottom is the composer: a **🖼** image button, a text box reading *"Ask about
your cards…"*, and a **➤** send button.

> **If your AI isn't running**, a yellow banner appears under the header:
> *"⚠ Local AI offline"* with **Start Ollama** and **Retry** buttons. Click **Start
> Ollama** (or launch your server), then **Retry**. If a needed model is missing, the
> banner instead says *"Model not installed…"* with the exact `ollama pull` command —
> or just use **Settings → Download with Ollama**.

### Asking a question

Type a request — for example *"inferior MI ECG findings"* — and press **Enter** (or
click **➤**). A brief "thinking" indicator appears, then the assistant replies.

**What a reply looks like,** top to bottom:

1. **A short text reply** in a chat bubble.
2. **A search-string card** — a boxed Anki search query (e.g.
   `deck:Cardiology (inferior OR "II III aVF") ECG`) with two buttons:
   - **Copy** — copies the string to your clipboard (the button flashes *"Copied ✓"*).
   - **Run in Browser ▶** — runs that exact search in the Browse window so you can
     scroll the results natively.
3. **A Results list** headed *"Results"*. Each row shows the card's title, a snippet,
   and a meta line with a colored flag dot, deck name, note type, and up to a few
   tags. A **🖼** badge marks cards that matched on (or contain) an image. **Click any
   result** to select and reveal that card in the Browse table.
4. **Related concepts** — a row of tappable pills. Click one to search it next.
5. **A faint footer** like *"12 cards · 840 ms · qwen2.5:3b-instruct"* (hide it in
   Settings if you don't want it).

### When the assistant asks you a question

If your request is ambiguous, instead of guessing the assistant shows a **clarifying
question** with **quick-reply chips**. Tap a chip to answer in one click (e.g. *"Did
you mean the EKG findings or the management?"* → **EKG findings** / **Management**),
and it continues with your choice.

### Searching by picture

Two ways:

- **Drop in an image:** click the **🖼** button in the composer and pick an image
  file (e.g. a screenshot of an ECG). A small chip shows the attached image's name
  (clear it with **✕**). Send your message and it finds cards whose images match.
- **Make image-only cards findable:** turn on **picture search** in Settings (see
  below) so the content *inside* your card images (great for Image Occlusion) becomes
  searchable by text.

### New chat / settings

- **⟲** in the header clears the conversation and starts fresh.
- **⚙** in the header opens the same Settings dialog as the Tools menu.

---

## The Settings dialog, field by field

Open it from **Tools → Smart Browser Search: Settings…**, the **⚙** button in the
panel, or the **Config** button on the add-on's row in **Tools → Add-ons**. Everything
lives in this one dialog. It's organized top-to-bottom into these sections:

### Local AI connection
- **Backend** — *Ollama (native)* or *OpenAI-compatible (LM Studio, llama.cpp, Jan…)*.
- **Endpoint URL** — your server's address. Ollama: `http://localhost:11434`.
  OpenAI-compatible: include `/v1`, e.g. `http://localhost:1234/v1`.
- **API key** — leave blank for local servers (some require any non-empty value).
- **Test connection** — confirms the server is reachable (shows *✓ Connected*).
- **Detect installed models** — lists the models your server already has and fills
  the dropdowns below.

### Recommended models — pick by your hardware
- **Tier dropdown** — Light / Medium / High. Selecting one shows the exact models,
  the download size, the GPU memory it needs, and which hardware it suits.
- **Use these models** — fills the Chat / Embeddings / Vision fields with that tier.
- **Download with Ollama** — downloads any of those models you don't already have,
  with live progress (*"Downloading qwen2.5:3b-instruct: … 42%"*). Ollama only.

See [Choosing your AI model](#choosing-your-ai-model) for the full table.

### Models (advanced)
Set the model names directly if you want something custom. Each box is editable and,
after **Detect installed models**, becomes a dropdown of what you have installed:
- **Chat model** — the assistant/reasoning model (runs on every search).
- **Embedding model** — used by semantic search; changing it rebuilds the index.
- **Vision model** — used by picture search / image captioning.
- **Temperature** — creativity knob; 0.2 (default) keeps searches focused.

### Search behaviour
- **Max results** — how many cards to show per search.
- **Enable semantic search (needs an index)** — turns on meaning-based search
  (Tier 2). Off by default; requires building an index once.
- **Index card images for picture search** — captions your card images so their
  contents are searchable. Slow first build; runs in the background.
- **Exclude suspended cards** — skip suspended cards in results.
- **Build / update index** / **Rebuild from scratch** — build or refresh the
  semantic/picture index. The line beneath shows what's indexed (e.g.
  *"Index: 12,403 notes, 512 image captions — model nomic-embed-text"*).

### Scope (which decks are searchable — none checked = all)
A checklist of your decks. Leave everything unchecked to search your whole
collection, or check specific decks to limit search and indexing to them.

### Appearance & safety
- **Toggle shortcut** — the hotkey that shows/hides the panel (default Ctrl+Shift+F).
- **Dock side** — Right or Left.
- **Open panel automatically with the Browser** — show the panel whenever Browse opens.
- **Show speed/model footer** — the *"N cards · ms · model"* line under each answer.
- **Write a debug log to user_files** — for troubleshooting only.
- **Run read-only safety self-check** — scans the add-on's own code for any
  card-modifying call and reports the result (see below).

Click **Save** to apply, **Cancel** to discard.

---

## Semantic search & picture search

Plain **keyword search works instantly with no setup** — the AI rewrites your request
into an Anki search string and runs it. The two opt-in tiers add deeper matching:

- **Semantic search** finds cards by *meaning*, even when they share no words with
  your query. Turn on **Enable semantic search** in Settings and click **Build /
  update index**. The first build embeds every in-scope note once (a few minutes for a
  large deck); after that it updates only changed cards, so re-runs are quick.
- **Picture search** makes the content *inside* card images findable. Turn on **Index
  card images for picture search** and rebuild. A local vision model captions/OCRs
  each image in the background — slow the first time, incremental afterward.

Both run entirely in the background with a progress bar and never block Anki. You can
keep using Anki while indexing.

---

## Is my deck safe? (Yes)

This add-on **only reads**. It calls Anki's search and note-reading APIs and nothing
else — there is no code path that writes, and it never imports a write or scheduler
API. Its index lives in a **separate** database (`user_files/index.db`) that physically
cannot touch your `collection.anki2`.

You don't have to take our word for it: **Settings → Run read-only safety self-check**
scans the add-on's own source for any mutating call and reports the result. See
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full design.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| Yellow **"Local AI offline"** banner | Start your model server. Click **Start Ollama** in the banner, or launch Ollama / your server, then **Retry**. |
| **"Model not installed"** banner | Open **Settings → Download with Ollama**, or run the `ollama pull …` shown in the banner. |
| **Test connection** fails | Check the **Endpoint URL**. Ollama → `http://localhost:11434`. OpenAI-compatible → must end in `/v1`. |
| Answers are slow on the first query | The model is loading into memory (cold start). Later queries are fast. If it's always slow, drop to a lighter tier. |
| Results are weak or miss obvious cards | Switch to a heavier model tier, or click **Run in Browser** and tweak the generated search string by hand. |
| **Semantic search** finds nothing | Enable it in Settings and click **Build / update index**. |
| **Picture search** misses a card | Enable image indexing and rebuild; captioning is a one-time background pass. |
| **Download with Ollama** is greyed-out behavior / errors | That button is Ollama-only. On LM Studio / llama.cpp, load models in that app and type their names into the **Models** fields. |
| Panel doesn't appear | Make sure you're in the **Browse** window; press **Ctrl+Shift+F** to toggle it. |

---

## How it works

- **Tier 1 — keyword (always on, no index):** the local LLM, grounded in *your*
  decks/tags/note-types, rewrites your request into a valid Anki search string and
  runs it through Anki's fast native search.
- **Tier 2 — semantic (opt-in):** notes are embedded once and stored as
  binary-quantized vectors; queries are matched with a CPU popcount scan + float32
  rescore, then fused with the keyword results via Reciprocal Rank Fusion.
- **Picture search:** a vision model captions/OCRs card images at index time; those
  captions are embedded into the same index.

No numpy, no torch, no compiled wheels — just Python's standard library and your local
AI server. That's what keeps it plug-and-play across platforms and durable across Anki
updates.

---

## Privacy

Everything runs on your machine. Your cards, your queries, and your images are sent
only to the local AI server you configure (Ollama or your OpenAI-compatible app on
`localhost`). There is no telemetry, no account, and no external network call.

---

## For developers

```
src/smart_browser_search/   the add-on
  ├─ ai/        runtime-agnostic local-AI client (urllib only) + prompts
  ├─ index/     SQLite store, embedder, dirty-tracking, image captioning
  ├─ search/    query building, keyword + semantic search, fusion, pipeline
  ├─ ui/        dock, webview panel controller, settings dialog
  └─ web/       panel HTML/CSS/JS (inherits Anki's theme)
build.py        package into dist/*.ankiaddon
docs/           architecture & setup notes
```

Build the installable package:

```
python build.py        # writes dist/smart_browser_search.ankiaddon
```

The package contains files at the zip root (no top folder) and excludes caches and
user data, as AnkiWeb requires.

---

## License

[MIT](LICENSE).
