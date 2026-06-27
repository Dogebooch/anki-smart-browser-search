# -*- coding: utf-8 -*-
"""Prompts, the structured-output contract, and per-model embedding prefixes."""

from __future__ import annotations

import json

# --------------------------------------------------------------------------- #
# The assistant contract. The model must return ONLY this JSON object.
# --------------------------------------------------------------------------- #
RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "reply": {"type": "string"},
        "search_string": {"type": ["string", "null"]},
        "clarifying_question": {"type": ["string", "null"]},
        "quick_replies": {"type": "array", "items": {"type": "string"}},
        "related": {"type": "array", "items": {"type": "string"}},
        "needs_semantic": {"type": "boolean"},
    },
    "required": ["reply"],
}

SYSTEM_PROMPT = """\
You are Smart Browser Search, an assistant embedded in the Anki flashcard app for \
a medical professional studying for board exams (ABIM/ABEM). Your ONLY job is to \
help the user FIND flashcards in their collection. You never create, edit, grade, \
or delete cards — you only build search queries and suggest concepts.

You will be given a snapshot of the user's actual decks, tags, and note types. \
Use ONLY decks/tags that appear in that snapshot when you scope a query; never \
invent deck or tag names.

Translate the user's natural-language request into a valid Anki Browser search \
string. Anki search grammar you may use:
- Bare words match anywhere; space = AND; `or` = OR; `-term` negates; group with ().
- `deck:"Name"` (includes subdecks), `tag:name` (includes subtags), `note:"Type"`.
- Field match: `"Front:re-entrant"`; wildcard `*` (any chars), `_` (one char).
- `is:due is:new is:suspended`, `flag:1`..`flag:7`, `added:30`, `prop:ivl>=21`.
- `nid:..,..` matches specific notes; `nc:term` ignores diacritics.
- Quote any multi-word value, e.g. `deck:"Master Deck::Cardiology"`.

Be an expert at MEDICAL synonym/abbreviation expansion so the search is high-recall:
expand acronyms ("MI" -> myocardial infarction / "heart attack" / STEMI), map brand \
to generic and back (Lasix <-> furosemide), include eponyms and classic findings \
(Wellens, "II III aVF" for inferior MI). Combine variants with OR inside a group.

Behaviour:
- If the request is clear, return a `search_string` and a one-line `reply`.
- If it is genuinely ambiguous in a way that changes the search, ask ONE short \
  `clarifying_question` and offer 2-4 `quick_replies` (tappable answers). Still \
  provide your best-guess `search_string` so the user is never stuck.
- Always populate `related` with 3-6 short, clickable neighbouring concepts the \
  user might also want (sibling diagnoses, mechanisms, complications). This powers \
  the "similar / related concepts" feature.
- Set `needs_semantic` true when the request is conceptual/paraphrased and keyword \
  matching is likely to miss (e.g. "that syndrome with hypertension and low potassium").
- Keep `reply` concise and friendly. Do not include the search string inside `reply` \
  (it is shown separately).

Return ONLY a single JSON object matching this shape (no markdown, no prose):
{"reply": str, "search_string": str|null, "clarifying_question": str|null, \
"quick_replies": [str], "related": [str], "needs_semantic": bool}
"""


def build_messages(history: list[dict], user_text: str, summary: dict,
                   image_caption: str | None = None) -> list[dict]:
    """Assemble the chat messages for one assistant turn."""
    messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.append({"role": "system", "content": _format_summary(summary)})
    for turn in history:
        role = turn.get("role")
        content = turn.get("content", "")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})
    user_payload = user_text or ""
    if image_caption:
        user_payload = (
            f"{user_payload}\n\n[The user attached an image. A local vision model "
            f"described it as:]\n{image_caption}"
        ).strip()
    messages.append({"role": "user", "content": user_payload})
    return messages


def _format_summary(summary: dict) -> str:
    decks = summary.get("decks", [])
    tags = summary.get("tags", [])
    nts = summary.get("note_types", [])
    lines = ["Here is a snapshot of the user's collection (use real names only):"]
    lines.append(f"\nDECKS ({summary.get('deck_count', len(decks))} total, showing {len(decks)}):")
    lines.append(", ".join(decks) if decks else "(none)")
    lines.append(f"\nTAGS ({summary.get('tag_count', len(tags))} total, showing {len(tags)}):")
    lines.append(", ".join(tags) if tags else "(none)")
    lines.append("\nNOTE TYPES (name: fields):")
    for nt in nts[:25]:
        fields = ", ".join(nt.get("fields", []))
        lines.append(f"- {nt.get('name','')}: {fields}")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Embedding prefixes. Several models need a task instruction prefixed to each
# input or recall degrades noticeably.
# --------------------------------------------------------------------------- #
def embed_prefix(model: str, kind: str) -> str:
    """Return the prefix to prepend to an embedding input.

    ``kind`` is "document" (a note being indexed) or "query" (the user's search).
    """
    name = (model or "").lower()
    if "nomic" in name:
        return "search_document: " if kind == "document" else "search_query: "
    if "mxbai" in name:
        # mxbai prefixes queries only.
        return "" if kind == "document" else \
            "Represent this sentence for searching relevant passages: "
    if "e5" in name or "multilingual-e5" in name:
        return "passage: " if kind == "document" else "query: "
    if "bge" in name:
        return "" if kind == "document" else \
            "Represent this sentence for searching relevant passages: "
    return ""


# --------------------------------------------------------------------------- #
# Vision prompts.
# --------------------------------------------------------------------------- #
VISION_CAPTION_PROMPT = (
    "You are indexing a medical flashcard image for search. First transcribe ALL "
    "visible text and labels verbatim. Then, in one or two sentences, describe what "
    "the image shows (anatomy, ECG, imaging modality, pathology, diagram type). Be "
    "concise and factual. Output plain text only."
)

VISION_QUERY_PROMPT = (
    "Describe this medical image so it can be matched against flashcards. Transcribe "
    "any visible text/labels, then name the structures, modality, and likely "
    "diagnosis or concept in a few keywords. Output plain text only."
)


def schema_as_text() -> str:
    return json.dumps(RESPONSE_SCHEMA)
