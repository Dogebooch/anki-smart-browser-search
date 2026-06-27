# -*- coding: utf-8 -*-
"""Filesystem locations for the add-on.

Everything the add-on writes lives under ``user_files/`` — the only folder Anki
preserves across add-on updates — and is therefore physically separate from the
user's ``collection.anki2``. Nothing here can touch the collection.
"""

from __future__ import annotations

import os

# Root of the add-on package directory (the folder containing this file).
ADDON_DIR = os.path.dirname(os.path.abspath(__file__))

# The top-level module name, e.g. "smart_browser_search" (folder install) or the
# numeric id assigned by AnkiWeb. Used for getConfig/setConfig and web exports.
ADDON_PACKAGE = __name__.split(".")[0]


def user_files_dir() -> str:
    path = os.path.join(ADDON_DIR, "user_files")
    os.makedirs(path, exist_ok=True)
    return path


def web_dir() -> str:
    return os.path.join(ADDON_DIR, "web")


def index_db_path() -> str:
    return os.path.join(user_files_dir(), "index.db")


def log_path() -> str:
    return os.path.join(user_files_dir(), "smart_search.log")


def web_base_url() -> str:
    """URL prefix Anki's media server uses to serve our ``web/`` assets."""
    return f"/_addons/{ADDON_PACKAGE}/web"
