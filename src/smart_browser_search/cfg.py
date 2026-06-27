# -*- coding: utf-8 -*-
"""Config access with defensive defaulting.

``get()`` always returns a complete dict: the user's saved config from
``meta.json`` merged on top of the shipped defaults, so code can read any key
without a ``KeyError`` even right after an upgrade adds new keys.
"""

from __future__ import annotations

import copy
from typing import Any

from . import const, log, paths


def _manager():
    from aqt import mw

    return mw.addonManager


def get() -> dict:
    """Return the effective config (defaults <- shipped json <- user edits)."""
    cfg = copy.deepcopy(const.DEFAULTS)
    try:
        saved = _manager().getConfig(paths.ADDON_PACKAGE)
        if isinstance(saved, dict):
            cfg.update(saved)  # user values win, including falsy ones
    except Exception as e:  # pragma: no cover - defensive
        log.warn(f"getConfig failed, using defaults: {e}")
    # Backfill any keys a user's saved file is missing (e.g. after an upgrade).
    for k, v in const.DEFAULTS.items():
        cfg.setdefault(k, v)
    log.set_debug(bool(cfg.get("debug_logging")))
    return cfg


def write(cfg: dict) -> None:
    try:
        _manager().writeConfig(paths.ADDON_PACKAGE, cfg)
        log.set_debug(bool(cfg.get("debug_logging")))
    except Exception as e:  # pragma: no cover - defensive
        log.error("writeConfig failed", e)


def set_value(key: str, value: Any) -> dict:
    cfg = get()
    cfg[key] = value
    write(cfg)
    return cfg
