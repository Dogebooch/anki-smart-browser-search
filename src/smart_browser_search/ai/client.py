# -*- coding: utf-8 -*-
"""Runtime-agnostic local-AI client — standard library only (urllib + json).

Targets two surfaces with one class:

* **Ollama native** (``backend="ollama"``) at ``{endpoint}/api/*`` — used for
  chat, embeddings, vision, and the *enhanced* features that have no OpenAI
  equivalent: model discovery (``/api/tags``) and capability detection
  (``/api/show``).
* **OpenAI-compatible** (``backend="openai"``) at ``{endpoint}/...`` where
  ``endpoint`` already ends in ``/v1`` — works for LM Studio, llama.cpp,
  Jan, GPT4All, and Ollama's own ``/v1`` shim.

No third-party or compiled dependencies, so it can never break on an Anki Python
bump and needs nothing installed beyond the AI server itself.
"""

from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request
from typing import Any

from .. import const, log


class AIError(Exception):
    """Generic AI backend error with a user-friendly message."""


class AIConnectionError(AIError):
    """The AI server could not be reached (not running / wrong URL)."""


def _is_conn_error(exc: BaseException) -> bool:
    if isinstance(exc, urllib.error.URLError) and not isinstance(exc, urllib.error.HTTPError):
        return True
    return isinstance(exc, (ConnectionError, TimeoutError, OSError))


class AIClient:
    def __init__(self, cfg: dict):
        self.backend = cfg.get("backend", const.BACKEND_OLLAMA)
        self.endpoint = (cfg.get("endpoint") or "").rstrip("/")
        self.api_key = cfg.get("api_key") or ""
        self.chat_model = cfg.get("chat_model") or ""
        self.embed_model = cfg.get("embed_model") or ""
        self.vision_model = cfg.get("vision_model") or ""
        self.temperature = float(cfg.get("temperature", 0.2))
        self.num_ctx = int(cfg.get("num_ctx", 8192))
        self.request_timeout = int(cfg.get("request_timeout", 120))
        self.connect_timeout = int(cfg.get("connect_timeout", 3))

    # ------------------------------------------------------------------ #
    # Low-level HTTP
    # ------------------------------------------------------------------ #
    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def _post(self, url: str, payload: dict, timeout: int) -> dict:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=self._headers(), method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8", "replace")[:500]
            except Exception:
                pass
            raise AIError(f"HTTP {e.code} from {url}: {body or e.reason}") from e
        except Exception as e:
            if _is_conn_error(e):
                raise AIConnectionError(str(e)) from e
            raise AIError(str(e)) from e
        try:
            return json.loads(raw)
        except Exception as e:
            raise AIError(f"Invalid JSON from {url}: {raw[:200]}") from e

    def _get(self, url: str, timeout: int) -> dict:
        req = urllib.request.Request(url, headers=self._headers(), method="GET")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            raise AIError(f"HTTP {e.code} from {url}: {e.reason}") from e
        except Exception as e:
            if _is_conn_error(e):
                raise AIConnectionError(str(e)) from e
            raise AIError(str(e)) from e

    # ------------------------------------------------------------------ #
    # Liveness & discovery
    # ------------------------------------------------------------------ #
    def is_alive(self) -> bool:
        try:
            self.list_models()
            return True
        except Exception:
            return False

    def list_models(self) -> list[str]:
        if self.backend == const.BACKEND_OLLAMA:
            data = self._get(f"{self.endpoint}/api/tags", self.connect_timeout)
            return sorted(m.get("name", "") for m in data.get("models", []) if m.get("name"))
        data = self._get(f"{self.endpoint}/models", self.connect_timeout)
        return sorted(m.get("id", "") for m in data.get("data", []) if m.get("id"))

    def running_models(self) -> list[str]:
        """Currently-loaded (warm) models — Ollama only; [] elsewhere."""
        if self.backend != const.BACKEND_OLLAMA:
            return []
        try:
            data = self._get(f"{self.endpoint}/api/ps", self.connect_timeout)
            return [m.get("name", "") for m in data.get("models", []) if m.get("name")]
        except Exception:
            return []

    def pull_model(self, model: str, on_progress=None, cancel=None) -> None:
        """Download a model via Ollama's ``/api/pull`` (streaming NDJSON progress).

        Ollama only — OpenAI-compatible servers can't fetch models on demand.
        ``on_progress(status, completed, total)`` is called as bytes arrive (called
        from the calling thread — marshal to the UI thread yourself); ``cancel``
        (a ``threading.Event``) aborts the stream between chunks.
        """
        if self.backend != const.BACKEND_OLLAMA:
            raise AIError("Model download is only available with the Ollama backend. "
                          "For LM Studio / llama.cpp, load the model in that app instead.")
        if not model:
            raise AIError("No model name given.")
        url = f"{self.endpoint}/api/pull"
        data = json.dumps({"model": model, "stream": True}).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=self._headers(), method="POST")
        # A multi-GB pull streams continuously; the timeout is per blocking read,
        # so a generous value tolerates slow mirrors without hanging forever.
        timeout = max(self.request_timeout, 300)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                for raw in resp:
                    if cancel is not None and cancel.is_set():
                        return
                    line = raw.decode("utf-8", "replace").strip()
                    if not line:
                        continue
                    try:
                        msg = json.loads(line)
                    except Exception:
                        continue
                    if msg.get("error"):
                        raise AIError(str(msg["error"]))
                    if on_progress is not None:
                        on_progress(
                            str(msg.get("status", "")),
                            int(msg.get("completed") or 0),
                            int(msg.get("total") or 0),
                        )
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8", "replace")[:300]
            except Exception:
                pass
            raise AIError(f"HTTP {e.code} from {url}: {body or e.reason}") from e
        except AIError:
            raise
        except Exception as e:
            if _is_conn_error(e):
                raise AIConnectionError(str(e)) from e
            raise AIError(str(e)) from e

    def capabilities(self, model: str) -> set[str]:
        """Capability set for a model (e.g. {'vision','embedding'}).

        Uses Ollama's ``/api/show``; on other backends falls back to name-based
        heuristics so the UI can still warn before a feature fails.
        """
        if self.backend == const.BACKEND_OLLAMA:
            try:
                data = self._post(f"{self.endpoint}/api/show", {"model": model},
                                  self.connect_timeout)
                caps = data.get("capabilities") or []
                if caps:
                    return {str(c).lower() for c in caps}
            except Exception:
                pass
        return _guess_capabilities(model)

    # ------------------------------------------------------------------ #
    # Chat
    # ------------------------------------------------------------------ #
    def chat(self, messages: list[dict], *, json_mode: bool = False,
             json_schema: dict | None = None, model: str | None = None) -> str:
        """Non-streaming chat completion. Returns the assistant message text."""
        model = model or self.chat_model
        if not model:
            raise AIError("No chat model configured.")
        if self.backend == const.BACKEND_OLLAMA:
            payload: dict[str, Any] = {
                "model": model,
                "messages": messages,
                "stream": False,
                "options": {"temperature": self.temperature, "num_ctx": self.num_ctx},
            }
            if json_schema is not None:
                payload["format"] = json_schema
            elif json_mode:
                payload["format"] = "json"
            data = self._post(f"{self.endpoint}/api/chat", payload, self.request_timeout)
            return (data.get("message") or {}).get("content", "") or ""
        # OpenAI-compatible
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "temperature": self.temperature,
        }
        if json_mode or json_schema is not None:
            payload["response_format"] = {"type": "json_object"}
        data = self._post(f"{self.endpoint}/chat/completions", payload, self.request_timeout)
        choices = data.get("choices") or []
        if not choices:
            return ""
        return (choices[0].get("message") or {}).get("content", "") or ""

    # ------------------------------------------------------------------ #
    # Vision
    # ------------------------------------------------------------------ #
    def vision_describe(self, image_bytes: bytes, prompt: str,
                        mime: str = "image/png", model: str | None = None) -> str:
        model = model or self.vision_model
        if not model:
            raise AIError("No vision model configured.")
        b64 = base64.b64encode(image_bytes).decode("ascii")
        if self.backend == const.BACKEND_OLLAMA:
            messages = [{"role": "user", "content": prompt, "images": [b64]}]
            payload = {
                "model": model,
                "messages": messages,
                "stream": False,
                "options": {"temperature": 0.1, "num_ctx": self.num_ctx},
            }
            data = self._post(f"{self.endpoint}/api/chat", payload, self.request_timeout)
            return (data.get("message") or {}).get("content", "") or ""
        # OpenAI-compatible: object form with data: URI prefix.
        messages = [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url",
                 "image_url": {"url": f"data:{mime};base64,{b64}"}},
            ],
        }]
        payload = {"model": model, "messages": messages, "stream": False, "temperature": 0.1}
        data = self._post(f"{self.endpoint}/chat/completions", payload, self.request_timeout)
        choices = data.get("choices") or []
        if not choices:
            return ""
        return (choices[0].get("message") or {}).get("content", "") or ""

    # ------------------------------------------------------------------ #
    # Embeddings
    # ------------------------------------------------------------------ #
    def embed(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        """Embed a batch of texts. Returns one vector per input, in order."""
        model = model or self.embed_model
        if not model:
            raise AIError("No embedding model configured.")
        if not texts:
            return []
        if self.backend == const.BACKEND_OLLAMA:
            return self._embed_ollama(texts, model)
        return self._embed_openai(texts, model)

    def _embed_ollama(self, texts: list[str], model: str) -> list[list[float]]:
        payload = {
            "model": model,
            "input": texts,
            "options": {"num_ctx": self.num_ctx},
        }
        try:
            data = self._post(f"{self.endpoint}/api/embed", payload, self.request_timeout)
            embs = data.get("embeddings")
            if embs is not None:
                return [[float(x) for x in v] for v in embs]
        except AIError as e:
            log.warn(f"/api/embed failed ({e}); falling back to /api/embeddings")
        # Legacy fallback: one request per text. A single failing item (e.g. one
        # over-long note the batch endpoint rejected) yields an empty vector and
        # is skipped by the caller rather than aborting the whole batch.
        out: list[list[float]] = []
        for t in texts:
            try:
                data = self._post(f"{self.endpoint}/api/embeddings",
                                  {"model": model, "prompt": t}, self.request_timeout)
                out.append([float(x) for x in data.get("embedding", [])])
            except AIError as e:
                log.warn(f"/api/embeddings skipped one input ({e})")
                out.append([])
        return out

    def _embed_openai(self, texts: list[str], model: str) -> list[list[float]]:
        payload = {"model": model, "input": texts}
        data = self._post(f"{self.endpoint}/embeddings", payload, self.request_timeout)
        rows = sorted(data.get("data", []), key=lambda d: d.get("index", 0))
        return [[float(x) for x in r.get("embedding", [])] for r in rows]


def _guess_capabilities(model: str) -> set[str]:
    name = (model or "").lower()
    caps: set[str] = {"completion"}
    if any(k in name for k in ("embed", "bge", "minilm", "arctic", "nomic", "mxbai")):
        caps.add("embedding")
    if any(k in name for k in ("vl", "vision", "llava", "moondream", "minicpm-v",
                               "qwen2-vl", "qwen2.5vl", "qwen2.5-vl", "gemma3")):
        caps.add("vision")
    return caps


def extract_json(text: str) -> dict:
    """Robustly pull a JSON object out of a model reply.

    Handles ```json fences, leading prose, and trailing chatter by scanning for
    the first balanced ``{ ... }`` block. Returns {} on failure.
    """
    if not text:
        return {}
    s = text.strip()
    if s.startswith("```"):
        s = s.strip("`")
        nl = s.find("\n")
        if nl != -1:
            s = s[nl + 1:]
    try:
        return json.loads(s)
    except Exception:
        pass
    # Scan for the first balanced object.
    start = s.find("{")
    while start != -1:
        depth = 0
        in_str = False
        esc = False
        for i in range(start, len(s)):
            ch = s[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
            else:
                if ch == '"':
                    in_str = True
                elif ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        chunk = s[start:i + 1]
                        try:
                            return json.loads(chunk)
                        except Exception:
                            break
        start = s.find("{", start + 1)
    return {}
