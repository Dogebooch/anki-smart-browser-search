# -*- coding: utf-8 -*-
"""Shared constants and small helpers for Smart Browser Search.

This module must stay import-light: it is pulled in by almost everything else
and must never import Qt or anki at module load time beyond the cheap bits.
"""

from __future__ import annotations

ADDON_NAME = "Smart Browser Search"
DOCK_OBJECT_NAME = "SmartBrowserSearchDock"  # stable id for Qt state save/restore

# Index/schema versioning. Bump SCHEMA_VERSION if the SQLite layout changes in a
# way that requires a rebuild.
SCHEMA_VERSION = 1

# Backend identifiers.
BACKEND_OLLAMA = "ollama"          # native http://host:11434/api/*
BACKEND_OPENAI = "openai"          # OpenAI-compatible http://host:port/v1/*

# --------------------------------------------------------------------------- #
# Curated model presets, by home-PC hardware tier.
#
# Each tier names a chat + embedding + vision model and guidance on who should
# pick it, keyed to an NVIDIA GPU baseline so users can self-select. The shipped
# default is the LIGHT tier so the add-on works on almost any machine out of the
# box; users with more GPU pick a heavier tier in Settings. ``chat_gb`` is the
# approximate download size of the chat model (the one that runs on every query);
# the embedding model is tiny (~0.3 GB) and the vision model only loads during
# picture indexing.
# --------------------------------------------------------------------------- #
MODEL_PRESETS: list[dict] = [
    {
        "id": "light",
        "label": "Light — runs on almost anything (default)",
        "chat_model": "qwen2.5:3b-instruct",
        "embed_model": "nomic-embed-text",
        "vision_model": "moondream",
        "chat_gb": 1.9,
        "min_vram_gb": 4,
        "gpu": "No dedicated GPU (CPU works, just slower), integrated graphics, "
               "most laptops, Apple M1/M2, or an NVIDIA GTX 1650 / RTX 3050 (~4 GB).",
    },
    {
        "id": "medium",
        "label": "Medium — mainstream gaming PC",
        "chat_model": "qwen2.5:7b-instruct",
        "embed_model": "nomic-embed-text",
        "vision_model": "qwen2.5vl:7b",
        "chat_gb": 4.7,
        "min_vram_gb": 8,
        "gpu": "A mid-range gaming GPU with 8–12 GB VRAM: NVIDIA RTX 3060 / 4060 / "
               "4060 Ti / 3070, or an Apple M-series with 16 GB unified memory.",
    },
    {
        "id": "high",
        "label": "High — enthusiast / workstation GPU",
        "chat_model": "qwen2.5:14b-instruct",
        "embed_model": "nomic-embed-text",
        "vision_model": "qwen2.5vl:7b",
        "chat_gb": 9.0,
        "min_vram_gb": 16,
        "gpu": "A high-end GPU with 16 GB+ VRAM: NVIDIA RTX 4070 Ti / 4080 / 3090 / "
               "4090, or AMD RX 7900 XT / XTX. Sharpest medical reasoning and recall.",
    },
]
DEFAULT_PRESET_ID = "light"

# Roles for chat messages.
ROLE_SYSTEM = "system"
ROLE_USER = "user"
ROLE_ASSISTANT = "assistant"

# Bridge command prefixes (JS -> Python). Keep in sync with web/panel.js.
# Payload is the plain text/value after the first ':' (colons in the value are
# preserved). Not JSON-encoded.
CMD_SEND = "send"                  # send:<raw user text>
CMD_RUN_SEARCH = "run_search"      # run_search:<query>
CMD_COPY = "copy"                  # copy:<text>
CMD_REVEAL_CARD = "reveal_card"    # reveal_card:<cid>
CMD_REVEAL_MANY = "reveal_many"    # reveal_many:<query>
CMD_QUICK_REPLY = "answer"         # answer:<text>
CMD_PICK_IMAGE = "pick_image"      # pick_image
CMD_START_AI = "start_ai"          # start_ai
CMD_RETRY_CONN = "retry_conn"      # retry_conn
CMD_OPEN_SETTINGS = "open_settings"  # open_settings
CMD_BUILD_INDEX = "build_index"    # build_index
CMD_READY = "ready"                # ready  (webview finished loading)
CMD_NEW_CHAT = "new_chat"          # new_chat
CMD_STOP = "stop"                  # stop  (cancel in-flight request)

# Default config. The shipped config.json must mirror this exactly; this copy is
# the source of truth used to backfill any keys the user's saved config lacks
# (so upgrades that add new keys never crash on a missing key).
DEFAULTS: dict = {
    "backend": BACKEND_OLLAMA,
    "endpoint": "http://localhost:11434",
    "api_key": "",  # ignored by local servers; some require a non-empty string
    # Ships with the LIGHT tier (see MODEL_PRESETS) so it runs on any machine.
    "chat_model": "qwen2.5:3b-instruct",
    "embed_model": "nomic-embed-text",
    "vision_model": "moondream",
    "temperature": 0.2,
    "num_ctx": 8192,
    "request_timeout": 120,   # seconds for generation
    "connect_timeout": 3,     # seconds for liveness probes
    # Retrieval
    "max_results": 25,
    "semantic_enabled": False,       # Tier-2 is opt-in
    "image_search_enabled": False,   # picture indexing is opt-in (slow first pass)
    "rrf_k": 60,
    "semantic_candidates": 300,      # top-N by Hamming before float rescore
    # Scope: which decks/note types/fields are searchable. Empty = everything.
    "scope_decks": [],
    "scope_note_types": [],
    "scope_fields": [],              # field names to embed; empty = all fields
    "exclude_suspended": False,
    # UI / behaviour
    "shortcut": "Ctrl+Shift+F",
    "dock_area": "right",            # "right" or "left"
    "open_on_browser_start": False,
    "auto_run_search": False,        # if True, pressing Run also focuses table
    "show_latency": True,
    "max_history_turns": 8,          # how many prior turns to send to the model
    "context_card_chars": 600,       # max chars of a note shown to the model
    # Index grounding: how many decks/tags/note types to show the model.
    "ground_max_decks": 60,
    "ground_max_tags": 80,
    # Safety / diagnostics
    "debug_logging": False,
}

# Sentinel marking work that must never run on the UI thread carelessly.
INTERACTIVE_BUDGET_MS = 300
