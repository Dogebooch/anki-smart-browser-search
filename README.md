# Smart Browser Search — AI card finder for Anki

Ask for a card in plain English. Get matching cards, a copy-paste Anki search string, and related concepts — powered entirely by **local** AI, right inside the Browser.

*Type "that syndrome with hypertension and low potassium" → finds your Conn's / hyperaldosteronism cards, even if the card never says "low potassium."*

Built for anyone with a large collection (medical board prep, language learning, law, etc.) who can't always remember the exact words on a card.

---

## Features

- **Natural-language search** — describe a topic, symptom, or concept; the assistant turns it into a real Anki search and shows matching cards
- **Medical synonym expansion** — expands acronyms (MI → STEMI), brand ↔ generic (Lasix ↔ furosemide), eponyms, and classic findings automatically
- **Copy-paste search string** — every answer includes a Browser-ready Anki query with **Copy** and **Run in Browser** buttons
- **Picture search** — indexes card images via local OCR/captioning, ideal for Image Occlusion where the answer lives inside the image
- **Clarifying questions** — asks for clarification when your request is ambiguous; tap a quick-reply chip to continue
- **Related concepts** — suggests adjacent topics when nothing matches exactly
- **100% local & private** — runs on Ollama or any OpenAI-compatible server; nothing leaves your machine, no account required
- **Read-only by construction** — cannot edit, add, delete, or reschedule a card; one-click safety proof in Settings
- **No heavy dependencies** — pure Python standard library; won't break when Anki updates

---

## Requirements

- Anki **24.06 or newer** (Qt6 desktop build — not the mobile apps)
- A local AI runtime running on your machine:
  - **[Ollama](https://ollama.com)** — recommended, free, one-click installer
  - *Or* any OpenAI-compatible server: LM Studio, llama.cpp, Jan, GPT4All
- Disk space for one model — as little as **~2 GB** on the Light tier; CPU-only works (just slower)

---

## Setup

### 1 — Install a local AI runtime

**Ollama (recommended):** download from [ollama.com](https://ollama.com) and run the installer. It runs quietly in the background; the add-on finds it automatically.

Using LM Studio / llama.cpp instead? Install it, load a model, start its server, then in Settings set the backend to *OpenAI-compatible* and paste your server's URL (e.g. `http://localhost:1234/v1`).

### 2 — Install this add-on

**Tools → Add-ons → Get Add-ons…**, enter the add-on code, click **OK**, restart Anki.

### 3 — Download a model

Open **Tools → Smart Browser Search: Settings…**, pick a tier under **Recommended models** that matches your hardware, click **Use these models**, then **Download with Ollama**.

---

## Choosing a model

| Tier | Chat model | Download | GPU memory | Good for |
|---|---|---|---|---|
| **Light** *(default)* | `qwen2.5:3b-instruct` | ~1.9 GB | ~4 GB or CPU | Any machine, laptops, integrated graphics |
| **Medium** | `qwen2.5:7b-instruct` | ~4.7 GB | ~8 GB | Mainstream gaming GPU (RTX 3060 / 4060 class) |
| **High** | `qwen2.5:14b-instruct` | ~9 GB | ~16 GB | High-end GPU (RTX 4070 Ti+, RX 7900 XT/XTX, M-series 32 GB+) |

All tiers also use `nomic-embed-text` for semantic search and `moondream` / `qwen2.5vl:7b` for picture search — both optional and only downloaded if you enable those features.

**Not sure?** Start on **Light** — it works on any machine and you can switch up in Settings at any time.

---

## Usage

1. Open the **Browse** window (**Tools → Browse** or press `b`)
2. The **Smart AI Search** panel appears on the right — toggle it with **Ctrl+Shift+F** (rebindable in Settings)
3. Type your question and press **Enter**

The assistant replies with a short answer, a copy-paste Anki search string with **Copy** and **Run in Browser** buttons, a list of matching cards, and a row of related-concept chips. Click any result to jump to that card in the Browse table.

**Picture search:** click the 🖼 button in the composer to attach an image (e.g. a screenshot of an ECG), or enable *Index card images for picture search* in Settings to make Image Occlusion card contents searchable by text.

**Semantic search (opt-in):** turn on *Enable semantic search* in Settings and click **Build index** for meaning-based matching that works even when card and query share no words. The first build runs in the background; subsequent runs update only changed cards.

---

## Settings

Open via **Tools → Smart Browser Search: Settings…**, the ⚙ button in the panel, or the Config button in **Tools → Add-ons**.

Key options:
- **Backend / Endpoint URL** — choose Ollama or OpenAI-compatible and set the server address
- **Recommended models** — pick Light / Medium / High, apply, and download in one place
- **Scope** — limit search and indexing to specific decks
- **Shortcut / dock side** — rebind the toggle key, move the panel left or right
- **Safety self-check** — scans the add-on's own source for any card-modifying call

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Yellow **"Local AI offline"** banner | Start Ollama / your server, then click **Retry** in the banner |
| **"Model not installed"** banner | Settings → **Download with Ollama**, or run the `ollama pull …` shown |
| Test connection fails | Check the Endpoint URL — Ollama: `http://localhost:11434`; OpenAI-compatible: must end in `/v1` |
| Slow first query | Model is cold-loading into memory; later queries are fast |
| Weak results | Switch to a heavier tier, or enable semantic search and build an index |
| Semantic search finds nothing | Enable it in Settings and click **Build / update index** |
| Panel doesn't appear | Confirm you're in Browse, then press **Ctrl+Shift+F** |
| **Download with Ollama** grayed out | That button is Ollama-only; load models in LM Studio / llama.cpp and type their names into the Models fields |

---

## Is my collection safe?

Yes. This add-on is **read-only by construction** — it only calls Anki's search and note-reading APIs, and has no code path that writes anything. The semantic index lives in a separate database (`user_files/index.db`) that physically cannot touch `collection.anki2`.

Run **Settings → Run read-only safety self-check** to verify this yourself — it scans the add-on's own source and reports the result.

---

## Privacy

Everything runs on your machine. Your cards, queries, and images are sent only to the local AI server you configure on `localhost`. There is no telemetry, no account, and no external network calls of any kind.

---

## Support & source

Bugs and feature requests: <https://github.com/Dogebooch/anki-smart-browser-search>

Source, architecture notes, and build instructions are in the repository above.

---

## License

[MIT](LICENSE)
