# -*- coding: utf-8 -*-
"""Dock the Smart AI Search panel into the Anki Browser.

Creates one ``QDockWidget`` per Browser window (idempotent), a checkable toggle
action with a configurable shortcut, and persists nothing in the collection.
"""

from __future__ import annotations

from aqt.qt import (QAction, QDockWidget, QKeySequence, Qt, qconnect)

from .. import cfg as cfgmod
from .. import log
from .panel import SmartSearchPanel, make_webview

_PANEL_TITLE = "Smart AI Search"


def _dock_area(name: str):
    if (name or "right").lower() == "left":
        return Qt.DockWidgetArea.LeftDockWidgetArea
    return Qt.DockWidgetArea.RightDockWidgetArea


def setup_browser(browser) -> None:
    """Attach the panel to a Browser window (called from browser_will_show)."""
    if getattr(browser, "_smart_search_dock", None) is not None:
        return  # already attached to this window

    cfg = cfgmod.get()
    dock = QDockWidget(_PANEL_TITLE, browser)
    dock.setObjectName("SmartBrowserSearchDock")
    dock.setAllowedAreas(
        Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
    )
    dock.setFeatures(
        QDockWidget.DockWidgetFeature.DockWidgetClosable
        | QDockWidget.DockWidgetFeature.DockWidgetMovable
        | QDockWidget.DockWidgetFeature.DockWidgetFloatable
    )

    web = make_webview(dock)
    web.setMinimumWidth(320)
    panel = SmartSearchPanel(browser, web)
    dock.setWidget(web)

    try:
        browser.addDockWidget(_dock_area(cfg.get("dock_area", "right")), dock)
    except Exception as e:  # extremely defensive; dock API has been stable
        log.error("addDockWidget failed", e)
        return

    start_visible = bool(cfg.get("open_on_browser_start"))
    dock.setVisible(start_visible)
    panel.render_initial()

    # Toggle action: checkable, shortcut-bound, two-way synced with the dock.
    act = QAction(f"{_PANEL_TITLE}", browser)
    act.setCheckable(True)
    act.setChecked(start_visible)
    shortcut = (cfg.get("shortcut") or "").strip()
    if shortcut:
        try:
            act.setShortcut(QKeySequence(shortcut))
        except Exception as e:
            log.warn(f"invalid shortcut {shortcut!r}: {e}")
    qconnect(act.toggled, dock.setVisible)
    qconnect(dock.visibilityChanged, act.setChecked)

    # Make the shortcut active in the Browser and add a discoverable menu entry.
    browser.addAction(act)
    _add_to_menu(browser, act)

    browser._smart_search_dock = dock
    browser._smart_search_panel = panel
    browser._smart_search_action = act


def _add_to_menu(browser, act: QAction) -> None:
    # Prefer an existing top-level menu; fall back to the menubar itself.
    form = getattr(browser, "form", None)
    # 'menuqt_accel_view' is the real object name of the Browser's View menu;
    # 'menuJump' is a stable fallback. Both exist on current builds.
    for attr in ("menuqt_accel_view", "menuJump", "menu_View"):
        menu = getattr(form, attr, None)
        if menu is not None:
            try:
                menu.addSeparator()
                menu.addAction(act)
                return
            except Exception:
                continue
    menubar = getattr(form, "menubar", None)
    if menubar is not None:
        try:
            menubar.addAction(act)
        except Exception as e:
            log.warn(f"could not add menu action: {e}")


def open_panel(browser) -> None:
    """Programmatically reveal the panel (used by the Tools-menu shortcut)."""
    dock = getattr(browser, "_smart_search_dock", None)
    if dock is None:
        setup_browser(browser)
        dock = getattr(browser, "_smart_search_dock", None)
    if dock is not None:
        dock.setVisible(True)
        dock.raise_()
