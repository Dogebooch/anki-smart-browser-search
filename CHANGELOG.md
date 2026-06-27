# Changelog

All notable changes to Smart Browser Search are documented here.

## 1.0.1

- **Fixed a crash when indexing long notes.** A note whose text exceeded the
  embedding model's context window made Ollama return HTTP 400; inputs are now
  capped before embedding, and an over-long single note is skipped (and retried
  next run) rather than failing its whole batch.
- **Logging can no longer crash the add-on.** Under Anki 25.09's stderr
  redirection, echoing a warning could raise `AttributeError: 'ErrorHandler'
  object has no attribute 'flush'` and turn a recoverable warning into a fatal
  error dialog. The stderr echo is now guarded.

## Unreleased

- **Single Tools-menu entry.** Everything now lives under **Tools → Smart Browser
  Search: Settings…** (index building, connection test, model downloads, scope, and
  the safety check are all inside that one dialog).
- **Hardware-tier model presets.** A new *Recommended models* section in Settings
  lets you pick **Light / Medium / High** by your GPU (keyed to NVIDIA baselines),
  apply the models with one click, and **Download with Ollama** any you're missing,
  with live progress.
- **Lighter default.** Ships with the Light tier (`qwen2.5:3b-instruct` +
  `moondream`) so it runs on almost any machine out of the box; switch up in Settings.
- **Comprehensive README** with step-by-step usage, screen-by-screen descriptions,
  and the model-tier guidance.

## 1.0.0

Initial release.

- Natural-language card search docked in the Anki Browser.
- Medical synonym / acronym / brand↔generic expansion grounded in your real
  decks, tags, and note types.
- Copy/paste Anki search string with **Copy** and **Run in Browser**.
- Clarifying questions (quick-reply chips) and related-concept suggestions.
- Tier-1 keyword search (always on, no index) + Tier-2 opt-in semantic search
  (binary-quantized vectors, popcount scan, float32 rescore, RRF fusion).
- Picture search: local vision-model caption/OCR of card images (great for Image
  Occlusion) and search-by-image.
- Runtime-agnostic local AI: Ollama (native) and any OpenAI-compatible server
  (LM Studio, llama.cpp, Jan, GPT4All). Standard library only — no compiled deps.
- Read-only by construction, with a one-click safety self-check.
- Native light/dark theming; configurable shortcut and dock side.
- Settings dialog under Tools menu and the add-on Config button.
