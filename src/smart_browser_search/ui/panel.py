# -*- coding: utf-8 -*-
"""The Smart AI Search panel — an AnkiWebView controller living in a Browser dock.

Owns the chat UI, the JS<->Python bridge, and every user action. All collection
access is read-only and all model calls run off the UI thread (see ``ops`` and
``search.pipeline``). The HTML/CSS/JS lives in ``web/`` and inherits Anki's theme.
"""

from __future__ import annotations

import json
import os
import weakref

from aqt import mw
from aqt.qt import QApplication, QFileDialog
from aqt.utils import tooltip
from aqt.webview import AnkiWebView

from .. import cfg as cfgmod
from .. import colread, log, ops, paths, safety
from ..ai.client import AIClient, AIConnectionError
from ..index import images as image_index
from ..index import indexer
from ..search import pipeline, semantic

try:
    from aqt.webview import AnkiWebViewKind
    _HAS_KIND = True
except Exception:  # pragma: no cover - older Anki
    AnkiWebViewKind = None
    _HAS_KIND = False

# Live panels (so the theme hook can refresh them). Weak so closing a Browser
# lets its panel be collected.
_live_panels: "weakref.WeakSet" = weakref.WeakSet()


def make_webview(parent, title: str = "smart_browser_search") -> AnkiWebView:
    if _HAS_KIND:
        try:
            return AnkiWebView(parent=parent, title=title, kind=AnkiWebViewKind.DEFAULT)
        except Exception:
            pass
    return AnkiWebView(parent=parent, title=title)


class SmartSearchPanel:
    def __init__(self, browser, web: AnkiWebView):
        self.browser = browser
        self.web = web
        self.history: list[dict] = []
        self.summary: dict | None = None
        self.busy = False
        self.pending_image: dict | None = None  # {"caption": str, "name": str}
        self._turn_seq = 0
        self.web.set_bridge_command(self.on_cmd, self)
        _live_panels.add(self)

    # ------------------------------------------------------------------ #
    # Rendering
    # ------------------------------------------------------------------ #
    def render_initial(self) -> None:
        base = paths.web_base_url()
        body = _read_web("panel.html")
        self.web.stdHtml(
            body,
            css=[f"{base}/panel.css"],
            js=[f"{base}/panel.js"],
            context=self,
        )

    def _emit(self, kind: str, data) -> None:
        try:
            payload = json.dumps(data)
        except Exception:
            payload = "null"
        js = f"window.SmartSearch && SmartSearch.handle({json.dumps(kind)}, {payload});"
        self.web.eval(js)

    # ------------------------------------------------------------------ #
    # Bridge dispatch (runs on the main thread)
    # ------------------------------------------------------------------ #
    def on_cmd(self, cmd: str):
        try:
            prefix, _, rest = cmd.partition(":")
            handler = getattr(self, f"_cmd_{prefix}", None)
            if handler is None:
                return
            return handler(rest)
        except Exception as e:  # never let a bridge call crash Anki
            log.error(f"bridge command failed: {cmd[:60]}", e)

    def _cmd_ready(self, _rest: str) -> None:
        cfg = cfgmod.get()
        self._emit("init", {
            "config": _public_config(cfg),
            "night": _is_night(),
        })
        self._probe_connection()

    def _cmd_send(self, rest: str) -> None:
        text = rest.strip()
        if text:
            self._start_turn(text)

    def _cmd_answer(self, rest: str) -> None:
        text = rest.strip()
        if text:
            self._emit("echo_user", {"text": text})
            self._start_turn(text)

    def _cmd_run_search(self, rest: str) -> None:
        self._run_in_browser(rest)

    def _cmd_reveal_many(self, rest: str) -> None:
        self._run_in_browser(rest)

    def _cmd_copy(self, rest: str) -> None:
        clip = QApplication.clipboard()
        if clip is not None:
            clip.setText(rest)
        self._emit("copied", {})

    def _cmd_reveal_card(self, rest: str) -> None:
        try:
            cid = int(rest)
        except ValueError:
            return
        try:
            self.browser.table.select_single_card(cid)
        except Exception as e:
            log.warn(f"select_single_card failed: {e}")
            self._run_in_browser(f"cid:{cid}")

    def _cmd_open_settings(self, _rest: str) -> None:
        from .settings import open_settings
        open_settings(self.browser)

    def _cmd_build_index(self, _rest: str) -> None:
        indexer.run_index(force_rebuild=False, on_done=lambda s: self._after_index(s))

    def _cmd_rebuild_index(self, _rest: str) -> None:
        indexer.run_index(force_rebuild=True, on_done=lambda s: self._after_index(s))

    def _cmd_new_chat(self, _rest: str) -> None:
        self.history = []
        self.pending_image = None
        self._emit("cleared", {})

    def _cmd_stop(self, _rest: str) -> None:
        self._turn_seq += 1  # invalidate any in-flight turn
        self.busy = False
        self._emit("thinking", {"on": False})

    def _cmd_pick_image(self, _rest: str) -> None:
        self._pick_image()

    def _cmd_clear_image(self, _rest: str) -> None:
        self.pending_image = None
        self._emit("image_cleared", {})

    def _cmd_start_ai(self, _rest: str) -> None:
        self._start_ai_server()

    def _cmd_retry_conn(self, _rest: str) -> None:
        self._probe_connection()

    def _cmd_safety_check(self, _rest: str) -> None:
        violations = safety.run_self_check()
        if violations:
            self._emit("toast", {"text": f"⚠ {len(violations)} read-only issue(s)"})
        else:
            self._emit("toast", {"text": "Read-only verified ✓ — your deck is safe"})

    # ------------------------------------------------------------------ #
    # Turn flow
    # ------------------------------------------------------------------ #
    def _start_turn(self, text: str) -> None:
        if self.busy:
            self._emit("toast", {"text": "Still working on the last request…"})
            return
        self.busy = True
        self._turn_seq += 1
        seq = self._turn_seq
        self._emit("thinking", {"on": True})

        image_caption = (self.pending_image or {}).get("caption")

        def proceed(summary: dict) -> None:
            if seq != self._turn_seq:
                return
            pipeline.run_turn(
                history=self.history[-2 * int(cfgmod.get().get("max_history_turns", 8)):],
                user_text=text,
                summary=summary,
                image_caption=image_caption,
                on_result=lambda res: self._on_result(seq, text, res),
                on_error=lambda exc: self._on_error(seq, exc),
            )

        self._ensure_summary(proceed)

    def _on_result(self, seq: int, user_text: str, res: dict) -> None:
        if seq != self._turn_seq:
            return
        self.busy = False
        self._emit("thinking", {"on": False})
        assistant = res.get("assistant", {})
        self.history.append({"role": "user", "content": user_text})
        self.history.append({"role": "assistant", "content": assistant.get("reply", "")})
        had_image = self.pending_image is not None
        self.pending_image = None
        cfg = cfgmod.get()
        self._emit("assistant", {
            "reply": assistant.get("reply", ""),
            "clarifying_question": assistant.get("clarifying_question"),
            "quick_replies": assistant.get("quick_replies", []),
            "related": assistant.get("related", []),
            "search_string": res.get("copy_string", ""),
            "runnable_string": res.get("runnable_string", ""),
            "results": res.get("results", []),
            "counts": res.get("counts", {}),
            "timing_ms": res.get("timing_ms", 0),
            "model": res.get("model", ""),
            "show_latency": bool(cfg.get("show_latency", True)),
        })
        if had_image:
            self._emit("image_cleared", {})

    def _on_error(self, seq: int, exc: Exception) -> None:
        if seq != self._turn_seq:
            return
        self.busy = False
        self._emit("thinking", {"on": False})
        if isinstance(exc, AIConnectionError):
            self._emit("connection", {"online": False})
            self._emit("error", {"kind": "offline",
                                  "text": "Local AI isn't responding."})
        else:
            self._emit("error", {"kind": "generic", "text": str(exc)[:300]})

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _ensure_summary(self, cb) -> None:
        if self.summary is not None:
            cb(self.summary)
            return
        cfg = cfgmod.get()

        def op(col):
            return colread.collection_summary(
                col, int(cfg.get("ground_max_decks", 60)),
                int(cfg.get("ground_max_tags", 80)))

        def done(summary):
            self.summary = summary
            cb(summary)

        ops.run_query(op, done, lambda e: cb({"decks": [], "tags": [], "note_types": []}))

    def _run_in_browser(self, query: str) -> None:
        query = query.strip()
        if not query:
            return
        try:
            self.browser.search_for(query)
            # Optionally hand keyboard focus to the results table so the user can
            # arrow through the matched cards immediately.
            if cfgmod.get().get("auto_run_search"):
                try:
                    self.browser.form.tableView.setFocus()
                except Exception:
                    pass
        except Exception as e:
            log.warn(f"search_for failed: {e}")
            try:
                self.browser.form.searchEdit.lineEdit().setText(query)
                self.browser.onSearchActivated()
            except Exception as e2:
                log.error("could not run search in browser", e2)

    def _probe_connection(self) -> None:
        cfg = cfgmod.get()

        def task():
            client = AIClient(cfg)
            alive = client.is_alive()
            models = client.list_models() if alive else []
            return {"online": alive, "models": models}

        def done(info):
            self._emit("connection", info)
            if not info["online"]:
                return
            cfg2 = cfgmod.get()
            warn = []
            models = info.get("models", [])
            if cfg2.get("chat_model") and cfg2["chat_model"] not in models:
                warn.append(cfg2["chat_model"])
            if cfg2.get("semantic_enabled") and cfg2.get("embed_model") \
                    and cfg2["embed_model"] not in models:
                warn.append(cfg2["embed_model"])
            if warn:
                self._emit("missing_models", {"models": warn})

        ops.run_network(task, done, lambda e: self._emit("connection", {"online": False}))

    def _pick_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self.browser, "Pick an image to search by",
            "", "Images (*.png *.jpg *.jpeg *.gif *.webp *.bmp)")
        if not path:
            return
        try:
            with open(path, "rb") as fh:
                data = fh.read()
        except Exception as e:
            tooltip(f"Couldn't read image: {e}")
            return
        name = os.path.basename(path)
        ext = os.path.splitext(name)[1].lower().lstrip(".") or "png"
        mime = "image/jpeg" if ext in ("jpg", "jpeg") else f"image/{ext}"
        self._emit("image_pending", {"name": name})
        cfg = cfgmod.get()

        def task():
            client = AIClient(cfg)
            return image_index.describe_query_image(client, data, mime=mime)

        def done(caption):
            self.pending_image = {"caption": caption or "", "name": name}
            self._emit("image_attached", {"name": name, "caption": (caption or "")[:200]})

        def fail(exc):
            self.pending_image = None
            self._emit("image_cleared", {})
            tooltip(f"Vision model error: {exc}")

        ops.run_network(task, done, fail)

    def _start_ai_server(self) -> None:
        import subprocess
        import sys
        cfg = cfgmod.get()
        started = False
        creationflags = 0
        if sys.platform == "win32":
            # Don't flash a console window or tie the child to Anki's lifetime.
            creationflags = (getattr(subprocess, "CREATE_NO_WINDOW", 0)
                             | getattr(subprocess, "DETACHED_PROCESS", 0))
        if cfg.get("backend") == "ollama":
            for args in (["ollama", "serve"],):
                try:
                    subprocess.Popen(  # type: ignore[call-overload]
                        args, stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        creationflags=creationflags)
                    started = True
                    break
                except Exception:
                    continue
        if started:
            self._emit("toast", {"text": "Starting local AI… give it a few seconds"})

            def recheck():
                self._probe_connection()
            mw.progress.timer(2500, recheck, False, parent=self.browser)
        else:
            self._emit("toast", {"text": "Couldn't auto-start. Open a terminal and run 'ollama serve'."})

    def _after_index(self, stats: dict) -> None:
        semantic.invalidate_cache()
        self._emit("index_done", {"stats": _jsonable(stats)})

    # ------------------------------------------------------------------ #
    def refresh_theme(self) -> None:
        self._emit("theme", {"night": _is_night()})


# --------------------------------------------------------------------------- #
# Module-level helpers
# --------------------------------------------------------------------------- #
def notify_theme_changed() -> None:
    for panel in list(_live_panels):
        try:
            panel.refresh_theme()
        except Exception:
            pass


def _read_web(name: str) -> str:
    path = os.path.join(paths.web_dir(), name)
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()
    except Exception as e:
        log.error(f"could not read web asset {name}", e)
        return "<div>Smart Browser Search failed to load its UI.</div>"


def _is_night() -> bool:
    try:
        from aqt.theme import theme_manager
        return bool(theme_manager.night_mode)
    except Exception:
        return False


def _public_config(cfg: dict) -> dict:
    return {
        "backend": cfg.get("backend"),
        "chat_model": cfg.get("chat_model"),
        "embed_model": cfg.get("embed_model"),
        "vision_model": cfg.get("vision_model"),
        "semantic_enabled": bool(cfg.get("semantic_enabled")),
        "image_search_enabled": bool(cfg.get("image_search_enabled")),
        "show_latency": bool(cfg.get("show_latency", True)),
    }


def _jsonable(obj):
    try:
        json.dumps(obj)
        return obj
    except Exception:
        return {"info": str(obj)}
