# -*- coding: utf-8 -*-
"""Tiny, dependency-free logger.

Writes to ``user_files/smart_search.log`` only when ``debug_logging`` is on, and
always echoes warnings/errors to stderr so they show up in Anki's console. Never
raises — logging must not be able to break the add-on.
"""

from __future__ import annotations

import sys
import time
import traceback

from . import paths

_DEBUG = False


def set_debug(enabled: bool) -> None:
    global _DEBUG
    _DEBUG = bool(enabled)


def _write(level: str, msg: str) -> None:
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} [{level}] {msg}"
    if level in ("WARN", "ERROR"):
        # Anki may redirect sys.stderr to a wrapper (e.g. colorama over an
        # ErrorHandler) that lacks .flush(); a failing echo must never turn a
        # logged warning into a fatal exception. Guard it and move on.
        try:
            print(f"[SmartBrowserSearch] {line}", file=sys.stderr, flush=False)
        except Exception:
            pass
    if not _DEBUG and level == "DEBUG":
        return
    try:
        with open(paths.log_path(), "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass  # logging must never raise


def debug(msg: str) -> None:
    if _DEBUG:
        _write("DEBUG", msg)


def info(msg: str) -> None:
    _write("INFO", msg)


def warn(msg: str) -> None:
    _write("WARN", msg)


def error(msg: str, exc: BaseException | None = None) -> None:
    if exc is not None:
        msg = f"{msg}\n{''.join(traceback.format_exception(type(exc), exc, exc.__traceback__))}"
    _write("ERROR", msg)
