# -*- coding: utf-8 -*-
"""Smart Browser Search — an AI assistant in Anki's Browser that finds cards.

Entry point. Registers hooks, the Tools-menu settings action, and the Browser
dock. Kept deliberately thin: heavy modules are imported lazily so opening Anki
stays fast and a failure in one feature never blocks startup.

SAFETY: this add-on is read-only. It never modifies, adds, deletes, or
reschedules cards. See ``safety.py`` for the enforced invariant.
"""

from __future__ import annotations


def _init() -> None:
    try:
        from aqt import gui_hooks, mw
        from aqt.qt import QAction, qconnect
    except Exception:
        # Not running inside Anki (e.g. imported by a test). Do nothing.
        return

    from . import cfg as cfgmod
    from . import const, log, paths, safety

    # Apply debug-logging preference early.
    try:
        log.set_debug(bool(cfgmod.get().get("debug_logging")))
    except Exception:
        pass

    # ------------------------------------------------------------------ #
    # Tools menu + Config button
    # ------------------------------------------------------------------ #
    def open_settings(*_args) -> None:
        from .ui.settings import open_settings as _open
        _open(mw)

    def build_index(*_args) -> None:
        from .index import indexer
        indexer.run_index(force_rebuild=False)

    def add_tools_menu() -> None:
        try:
            menu = mw.form.menuTools
        except Exception as e:
            log.warn(f"Tools menu unavailable: {e}")
            return
        settings_action = QAction(f"{const.ADDON_NAME}: Settings…", mw)
        qconnect(settings_action.triggered, open_settings)
        menu.addAction(settings_action)

        index_action = QAction(f"{const.ADDON_NAME}: Build / update index", mw)
        qconnect(index_action.triggered, build_index)
        menu.addAction(index_action)

    # The Config button in the add-on manager opens our dialog instead of raw JSON.
    try:
        mw.addonManager.setConfigAction(paths.ADDON_PACKAGE, open_settings)
    except Exception as e:
        log.warn(f"setConfigAction failed: {e}")

    # Make sure our web assets are served by the media server.
    try:
        mw.addonManager.setWebExports(paths.ADDON_PACKAGE, r"web/.*")
    except Exception as e:
        log.warn(f"setWebExports failed: {e}")

    # ------------------------------------------------------------------ #
    # Browser dock
    # ------------------------------------------------------------------ #
    def on_browser_will_show(browser) -> None:
        try:
            from .ui.dock import setup_browser
            setup_browser(browser)
        except Exception as e:
            log.error("failed to set up Smart Search panel", e)

    # ------------------------------------------------------------------ #
    # Theme refresh for live panels
    # ------------------------------------------------------------------ #
    def register_theme() -> None:
        try:
            from .ui.panel import notify_theme_changed
            gui_hooks.theme_did_change.append(notify_theme_changed)
        except Exception as e:
            log.warn(f"theme hook registration failed: {e}")

    # profile_did_open fires on every profile switch; do one-time, non-idempotent
    # setup (Tools menu, theme hook, safety self-check) only once (M3, L4).
    state = {"setup_done": False}

    def on_profile_open() -> None:
        if state["setup_done"]:
            return
        state["setup_done"] = True
        add_tools_menu()
        register_theme()
        safety.assert_read_only()  # cheap regex scan; logs any future regression

    gui_hooks.profile_did_open.append(on_profile_open)
    gui_hooks.browser_will_show.append(on_browser_will_show)


_init()
