# Changelog

All notable changes to Smart Browser Search are documented here.

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
