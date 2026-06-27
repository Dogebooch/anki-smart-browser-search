# -*- coding: utf-8 -*-
"""Settings dialog — reachable from Tools menu and the add-on Config button."""

from __future__ import annotations

from aqt import mw
from aqt.qt import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
                    QFormLayout, QGroupBox, QHBoxLayout, QKeySequenceEdit, QLabel,
                    QLineEdit, QListWidget, QListWidgetItem, QPushButton, QSpinBox,
                    Qt, QVBoxLayout, QWidget, qconnect)
from aqt.utils import tooltip

from .. import cfg as cfgmod
from .. import const, ops, safety
from ..ai.client import AIClient
from ..index import indexer
from ..search import semantic


def _model_installed(name: str, installed: set[str]) -> bool:
    """True if ``name`` is among Ollama's installed tags, tolerating the implicit
    ``:latest`` tag (Ollama stores ``nomic-embed-text`` as ``nomic-embed-text:latest``)."""
    if name in installed:
        return True
    if ":" not in name and f"{name}:latest" in installed:
        return True
    return False


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent or mw)
        self.setWindowTitle("Smart AI Search — Settings")
        self.setMinimumWidth(540)
        self.cfg = cfgmod.get()
        self._build()
        self._load()

    # ------------------------------------------------------------------ #
    def _build(self) -> None:
        root = QVBoxLayout(self)

        # --- Connection ---
        conn = QGroupBox("Local AI connection")
        form = QFormLayout(conn)
        self.backend = QComboBox()
        self.backend.addItem("Ollama (native)", const.BACKEND_OLLAMA)
        self.backend.addItem("OpenAI-compatible (LM Studio, llama.cpp, Jan…)",
                             const.BACKEND_OPENAI)
        self.endpoint = QLineEdit()
        self.api_key = QLineEdit()
        self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key.setPlaceholderText("(usually blank for local servers)")
        test_row = QHBoxLayout()
        self.test_btn = QPushButton("Test connection")
        self.detect_btn = QPushButton("Detect installed models")
        self.conn_label = QLabel("")
        test_row.addWidget(self.test_btn)
        test_row.addWidget(self.detect_btn)
        test_row.addStretch(1)
        test_wrap = QWidget()
        test_wrap.setLayout(test_row)
        form.addRow("Backend", self.backend)
        form.addRow("Endpoint URL", self.endpoint)
        form.addRow("API key", self.api_key)
        form.addRow("", test_wrap)
        form.addRow("", self.conn_label)
        root.addWidget(conn)

        # --- Recommended models (hardware tier) ---
        rec = QGroupBox("Recommended models — pick by your hardware")
        rec_l = QVBoxLayout(rec)
        self.preset_combo = QComboBox()
        for p in const.MODEL_PRESETS:
            self.preset_combo.addItem(p["label"], p["id"])
        self.preset_guidance = QLabel("")
        self.preset_guidance.setWordWrap(True)
        self.preset_guidance.setTextFormat(Qt.TextFormat.RichText)
        prow = QHBoxLayout()
        self.use_preset_btn = QPushButton("Use these models")
        self.download_preset_btn = QPushButton("Download with Ollama")
        prow.addWidget(self.use_preset_btn)
        prow.addWidget(self.download_preset_btn)
        prow.addStretch(1)
        prow_wrap = QWidget()
        prow_wrap.setLayout(prow)
        self.preset_status = QLabel("")
        self.preset_status.setWordWrap(True)
        rec_l.addWidget(self.preset_combo)
        rec_l.addWidget(self.preset_guidance)
        rec_l.addWidget(prow_wrap)
        rec_l.addWidget(self.preset_status)
        root.addWidget(rec)

        # --- Models ---
        models = QGroupBox("Models (advanced — or set them with a preset above)")
        mform = QFormLayout(models)
        self.chat_model = QComboBox()
        self.chat_model.setEditable(True)
        self.embed_model = QComboBox()
        self.embed_model.setEditable(True)
        self.vision_model = QComboBox()
        self.vision_model.setEditable(True)
        self.temperature = QDoubleSpinBox()
        self.temperature.setRange(0.0, 2.0)
        self.temperature.setSingleStep(0.1)
        mform.addRow("Chat model", self.chat_model)
        mform.addRow("Embedding model", self.embed_model)
        mform.addRow("Vision model", self.vision_model)
        mform.addRow("Temperature", self.temperature)
        root.addWidget(models)

        # --- Search behaviour ---
        beh = QGroupBox("Search behaviour")
        bform = QFormLayout(beh)
        self.max_results = QSpinBox()
        self.max_results.setRange(1, 200)
        self.semantic_enabled = QCheckBox("Enable semantic search (needs an index)")
        self.image_search_enabled = QCheckBox(
            "Index card images for picture search (slow first build)")
        self.exclude_suspended = QCheckBox("Exclude suspended cards")
        idx_row = QHBoxLayout()
        self.build_btn = QPushButton("Build / update index")
        self.rebuild_btn = QPushButton("Rebuild from scratch")
        idx_row.addWidget(self.build_btn)
        idx_row.addWidget(self.rebuild_btn)
        idx_row.addStretch(1)
        idx_wrap = QWidget()
        idx_wrap.setLayout(idx_row)
        self.index_label = QLabel("")
        bform.addRow("Max results", self.max_results)
        bform.addRow("", self.semantic_enabled)
        bform.addRow("", self.image_search_enabled)
        bform.addRow("", self.exclude_suspended)
        bform.addRow("Index", idx_wrap)
        bform.addRow("", self.index_label)
        root.addWidget(beh)

        # --- Scope ---
        scope = QGroupBox("Scope (which decks are searchable — none checked = all)")
        sl = QVBoxLayout(scope)
        self.deck_list = QListWidget()
        self.deck_list.setMaximumHeight(140)
        sl.addWidget(self.deck_list)
        root.addWidget(scope)

        # --- Appearance & safety ---
        appg = QGroupBox("Appearance & safety")
        aform = QFormLayout(appg)
        self.shortcut = QKeySequenceEdit()
        self.dock_area = QComboBox()
        self.dock_area.addItem("Right", "right")
        self.dock_area.addItem("Left", "left")
        self.open_on_start = QCheckBox("Open panel automatically with the Browser")
        self.show_latency = QCheckBox("Show speed/model footer")
        self.debug_logging = QCheckBox("Write a debug log to user_files")
        self.safety_btn = QPushButton("Run read-only safety self-check")
        self.safety_label = QLabel("")
        aform.addRow("Toggle shortcut", self.shortcut)
        aform.addRow("Dock side", self.dock_area)
        aform.addRow("", self.open_on_start)
        aform.addRow("", self.show_latency)
        aform.addRow("", self.debug_logging)
        aform.addRow("Safety", self.safety_btn)
        aform.addRow("", self.safety_label)
        root.addWidget(appg)

        # --- Buttons ---
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Save
                              | QDialogButtonBox.StandardButton.Cancel)
        root.addWidget(bb)
        qconnect(bb.accepted, self._save)
        qconnect(bb.rejected, self.reject)

        qconnect(self.test_btn.clicked, self._test)
        qconnect(self.detect_btn.clicked, self._detect)
        qconnect(self.preset_combo.currentIndexChanged, self._update_preset_guidance)
        qconnect(self.use_preset_btn.clicked, self._apply_preset)
        qconnect(self.download_preset_btn.clicked, self._download_preset)
        qconnect(self.build_btn.clicked, lambda: self._build_index(False))
        qconnect(self.rebuild_btn.clicked, lambda: self._build_index(True))
        qconnect(self.safety_btn.clicked, self._safety_check)

    # ------------------------------------------------------------------ #
    def _load(self) -> None:
        c = self.cfg
        self._set_combo_data(self.backend, c.get("backend"))
        self.endpoint.setText(c.get("endpoint", ""))
        self.api_key.setText(c.get("api_key", ""))
        self.chat_model.setEditText(c.get("chat_model", ""))
        self.embed_model.setEditText(c.get("embed_model", ""))
        self.vision_model.setEditText(c.get("vision_model", ""))
        self._select_matching_preset(c.get("chat_model", ""))
        self._update_preset_guidance()
        self.temperature.setValue(float(c.get("temperature", 0.2)))
        self.max_results.setValue(int(c.get("max_results", 25)))
        self.semantic_enabled.setChecked(bool(c.get("semantic_enabled")))
        self.image_search_enabled.setChecked(bool(c.get("image_search_enabled")))
        self.exclude_suspended.setChecked(bool(c.get("exclude_suspended")))
        try:
            from aqt.qt import QKeySequence
            self.shortcut.setKeySequence(QKeySequence(c.get("shortcut", "")))
        except Exception:
            pass
        self._set_combo_data(self.dock_area, c.get("dock_area", "right"))
        self.open_on_start.setChecked(bool(c.get("open_on_browser_start")))
        self.show_latency.setChecked(bool(c.get("show_latency", True)))
        self.debug_logging.setChecked(bool(c.get("debug_logging")))
        self._load_decks(c.get("scope_decks", []))
        self._refresh_index_label()

    def _load_decks(self, selected: list[str]) -> None:
        self.deck_list.clear()
        try:
            names = sorted(d.name for d in mw.col.decks.all_names_and_ids())
        except Exception:
            names = []
        sel = set(selected or [])
        for name in names:
            item = QListWidgetItem(name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if name in sel
                               else Qt.CheckState.Unchecked)
            self.deck_list.addItem(item)

    def _set_combo_data(self, combo: QComboBox, value) -> None:
        for i in range(combo.count()):
            if combo.itemData(i) == value:
                combo.setCurrentIndex(i)
                return

    # ------------------------------------------------------------------ #
    def _client(self) -> AIClient:
        return AIClient(self._collect())

    def _alive(self) -> bool:
        """False once the dialog's C++ object is gone (closed mid-request, M4)."""
        try:
            from aqt.qt import sip
            return not sip.isdeleted(self)
        except Exception:
            return True

    def _set_conn(self, text: str) -> None:
        if self._alive():
            self.conn_label.setText(text)

    def _test(self) -> None:
        self.conn_label.setText("Testing…")
        client = self._client()
        ops.run_network(
            client.is_alive,
            lambda ok: self._set_conn("✓ Connected" if ok else "✗ Not reachable"),
            lambda e: self._set_conn(f"✗ {e}"))

    def _detect(self) -> None:
        self.conn_label.setText("Detecting models…")
        client = self._client()
        ops.run_network(
            client.list_models,
            lambda models: self._fill_models(models) if self._alive() else None,
            lambda e: self._set_conn(f"✗ {e}"))

    def _fill_models(self, models: list[str]) -> None:
        self.conn_label.setText(f"✓ {len(models)} models found")
        for combo in (self.chat_model, self.embed_model, self.vision_model):
            current = combo.currentText()
            combo.clear()
            combo.addItems(models)
            combo.setEditText(current)

    # ------------------------------------------------------------------ #
    # Recommended-model presets
    # ------------------------------------------------------------------ #
    def _current_preset(self) -> dict:
        idx = max(0, self.preset_combo.currentIndex())
        return const.MODEL_PRESETS[idx]

    def _select_matching_preset(self, chat_model: str) -> None:
        """Highlight the tier whose chat model matches the saved config."""
        for i, p in enumerate(const.MODEL_PRESETS):
            if p["chat_model"] == chat_model:
                self.preset_combo.setCurrentIndex(i)
                return

    def _update_preset_guidance(self, *_args) -> None:
        p = self._current_preset()
        self.preset_guidance.setText(
            f"<b>Chat:</b> {p['chat_model']} &nbsp;·&nbsp; "
            f"<b>Embeddings:</b> {p['embed_model']} &nbsp;·&nbsp; "
            f"<b>Vision:</b> {p['vision_model']}<br>"
            f"≈ {p['chat_gb']:.1f} GB chat-model download &nbsp;·&nbsp; "
            f"needs about {p['min_vram_gb']} GB of GPU memory (or runs on CPU, slower)."
            f"<br><b>Pick this if you have:</b> {p['gpu']}")

    def _apply_preset(self) -> None:
        p = self._current_preset()
        self.chat_model.setEditText(p["chat_model"])
        self.embed_model.setEditText(p["embed_model"])
        self.vision_model.setEditText(p["vision_model"])
        tooltip(f"Set to the {p['id']} models — click Save to keep them, "
                f"then “Download with Ollama” if you don’t have them yet.",
                parent=self)

    def _set_preset_status(self, text: str) -> None:
        """Thread-safe status update for the preset row (M4-style alive guard)."""
        def _u() -> None:
            if self._alive():
                self.preset_status.setText(text)
        ops.on_main(_u)

    def _download_preset(self) -> None:
        p = self._current_preset()
        client = self._client()
        if client.backend != const.BACKEND_OLLAMA:
            tooltip("Downloading models requires the Ollama backend. For LM Studio / "
                    "llama.cpp, load the models in that app instead.", parent=self)
            return
        # Deduplicate while preserving order (embed model is shared across tiers).
        wanted = list(dict.fromkeys(
            m for m in (p["chat_model"], p["embed_model"], p["vision_model"]) if m))
        self.preset_status.setText("Checking which models you already have…")

        def task():
            installed = set(client.list_models())
            todo = [m for m in wanted if not _model_installed(m, installed)]
            if not todo:
                return {"already": True}
            for m in todo:
                def prog(status, completed, total, _m=m):
                    pct = f" — {completed * 100 // total}%" if total else ""
                    self._set_preset_status(f"Downloading {_m}: {status}{pct}")
                client.pull_model(m, on_progress=prog)
            return {"pulled": todo}

        def ok(res):
            if not self._alive():
                return
            if res.get("already"):
                self.preset_status.setText("✓ All recommended models are already installed.")
            else:
                self.preset_status.setText("✓ Downloaded: " + ", ".join(res["pulled"]))
            self._detect()  # refresh the model dropdowns from the server

        def fail(exc):
            self._set_preset_status(f"✗ Download failed: {exc}")

        ops.run_network(task, ok, fail)

    def _build_index(self, force: bool) -> None:
        # Persist current choices first so the indexer uses them.
        self._save(close=False)
        indexer.run_index(force_rebuild=force, on_done=self._after_index)

    def _after_index(self, stats: dict) -> None:
        semantic.invalidate_cache()
        if self._alive():
            self._refresh_index_label()

    def _refresh_index_label(self) -> None:
        try:
            from ..index.store import IndexStore
            from .. import paths
            store = IndexStore(paths.index_db_path())
            try:
                counts = store.counts()
                meta = store.get_meta()
            finally:
                store.close()
            self.index_label.setText(
                f"Index: {counts['notes']} notes, {counts['image_vectors']} image "
                f"captions — model {meta.get('model', '(none)')}")
        except Exception:
            self.index_label.setText("Index: not built yet")

    def _safety_check(self) -> None:
        violations = safety.run_self_check()
        if violations:
            self.safety_label.setText(f"⚠ {len(violations)} potential write call(s) found")
        else:
            self.safety_label.setText("✓ Verified read-only — the add-on cannot modify your deck")

    # ------------------------------------------------------------------ #
    def _collect(self) -> dict:
        c = cfgmod.get()
        c["backend"] = self.backend.currentData()
        c["endpoint"] = self.endpoint.text().strip()
        c["api_key"] = self.api_key.text()
        c["chat_model"] = self.chat_model.currentText().strip()
        c["embed_model"] = self.embed_model.currentText().strip()
        c["vision_model"] = self.vision_model.currentText().strip()
        c["temperature"] = float(self.temperature.value())
        c["max_results"] = int(self.max_results.value())
        c["semantic_enabled"] = self.semantic_enabled.isChecked()
        c["image_search_enabled"] = self.image_search_enabled.isChecked()
        c["exclude_suspended"] = self.exclude_suspended.isChecked()
        try:
            c["shortcut"] = self.shortcut.keySequence().toString()
        except Exception:
            pass
        c["dock_area"] = self.dock_area.currentData()
        c["open_on_browser_start"] = self.open_on_start.isChecked()
        c["show_latency"] = self.show_latency.isChecked()
        c["debug_logging"] = self.debug_logging.isChecked()
        decks = []
        for i in range(self.deck_list.count()):
            item = self.deck_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                decks.append(item.text())
        c["scope_decks"] = decks
        return c

    def _save(self, close: bool = True) -> None:
        cfgmod.write(self._collect())
        if close:
            tooltip("Smart AI Search settings saved", parent=mw)
            self.accept()


_dialog = None


def open_settings(parent=None) -> None:
    global _dialog
    _dialog = SettingsDialog(parent)
    _dialog.show()
    _dialog.raise_()
