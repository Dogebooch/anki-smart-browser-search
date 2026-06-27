# -*- coding: utf-8 -*-
"""Read-only invariant — defense in depth.

The collection is protected *by construction*: the add-on never imports a write
path. This module makes that claim auditable. ``run_self_check()`` scans the
add-on's own Python source for any call that could mutate the collection and
reports violations. It is wired to a button in the settings dialog so a cautious
user can verify the guarantee themselves, and it runs once on load when debug
logging is enabled.

If you are extending this add-on: adding any of the forbidden patterns below is a
bug, not a feature. There is no legitimate reason for a *search* tool to write.
"""

from __future__ import annotations

import os
import re

from . import log, paths

# Calls that mutate the collection (or its scheduler/media). Matched against our
# own source. ``colread.py`` is the only sanctioned collection-access module and
# contains none of these.
FORBIDDEN_PATTERNS: list[str] = [
    r"\.flush\s*\(",
    r"\.add_note\s*\(",
    r"\.add_notes\s*\(",
    r"\.update_note\s*\(",
    r"\.update_notes\s*\(",
    r"\.update_card\s*\(",
    r"\.update_cards\s*\(",
    r"\.remove_notes\s*\(",
    r"\.remove_cards_and_orphaned_notes\s*\(",
    r"\.remove_cards\s*\(",
    r"\.set_due_date\s*\(",
    r"\.suspend_cards\s*\(",
    r"\.unsuspend_cards\s*\(",
    r"\.bury_cards\s*\(",
    r"\.add_tags\b",
    r"\.remove_tags\b",
    r"\.bulk_add_tags\b",
    r"\.bulk_remove_tags\b",
    r"CollectionOp\s*\(",
    # raw write SQL against the collection db
    r"col\.db\.execute\s*\(\s*['\"]\s*(insert|update|delete|drop|alter)",
]

_COMPILED = [re.compile(p, re.IGNORECASE) for p in FORBIDDEN_PATTERNS]

# Files allowed to mention forbidden patterns (this file lists them as strings).
_ALLOWLIST = {"safety.py"}


def _iter_source_files() -> list[str]:
    files: list[str] = []
    for root, _dirs, names in os.walk(paths.ADDON_DIR):
        if "user_files" in root:
            continue
        for name in names:
            if name.endswith(".py"):
                files.append(os.path.join(root, name))
    return files


def run_self_check() -> list[str]:
    """Return a list of human-readable violations (empty == safe)."""
    violations: list[str] = []
    for path in _iter_source_files():
        if os.path.basename(path) in _ALLOWLIST:
            continue
        try:
            with open(path, "r", encoding="utf-8") as fh:
                lines = fh.readlines()
        except Exception:
            continue
        for i, line in enumerate(lines, 1):
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            for rx in _COMPILED:
                if rx.search(line):
                    rel = os.path.relpath(path, paths.ADDON_DIR)
                    violations.append(f"{rel}:{i}: {line.strip()}")
    return violations


def assert_read_only() -> bool:
    """Log the result of the self-check. Returns True if clean."""
    violations = run_self_check()
    if violations:
        log.error("READ-ONLY INVARIANT VIOLATED:\n  " + "\n  ".join(violations))
        return False
    log.debug("Read-only self-check passed: no mutating calls in add-on source.")
    return True
