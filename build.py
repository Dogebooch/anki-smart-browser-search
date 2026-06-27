#!/usr/bin/env python3
"""Package the add-on into an installable `.ankiaddon` zip.

Usage:  python build.py

Produces `dist/smart_browser_search.ankiaddon` with files at the zip root (no top
folder, as AnkiWeb requires), excluding caches, the user's runtime data, and
version-control noise. Double-click the result in Anki, or drag it onto the
Browser, to install.
"""

from __future__ import annotations

import os
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "src", "smart_browser_search")
DIST = os.path.join(HERE, "dist")
OUT = os.path.join(DIST, "smart_browser_search.ankiaddon")

# Files/dirs never shipped.
EXCLUDE_DIRS = {"__pycache__", ".git", ".mypy_cache", ".ruff_cache", ".pytest_cache"}
EXCLUDE_NAMES = {"meta.json", ".DS_Store", "Thumbs.db", "desktop.ini"}
# Inside user_files we ship only the README placeholder (so the dir exists).
USER_FILES_KEEP = {"README.md"}


def _included(rel_path: str) -> bool:
    parts = rel_path.replace("\\", "/").split("/")
    if any(p in EXCLUDE_DIRS for p in parts):
        return False
    name = parts[-1]
    if name in EXCLUDE_NAMES:
        return False
    if name.endswith((".pyc", ".pyo", ".log")):
        return False
    if parts[0] == "user_files" and name not in USER_FILES_KEEP:
        return False
    return True


def main() -> None:
    if not os.path.isdir(SRC):
        raise SystemExit(f"Source not found: {SRC}")
    os.makedirs(DIST, exist_ok=True)
    if os.path.exists(OUT):
        os.remove(OUT)

    count = 0
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(SRC):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            for fn in files:
                abs_path = os.path.join(root, fn)
                rel = os.path.relpath(abs_path, SRC)
                if not _included(rel):
                    continue
                zf.write(abs_path, rel.replace("\\", "/"))
                count += 1

    size_kb = os.path.getsize(OUT) / 1024
    print(f"Wrote {OUT}")
    print(f"  {count} files, {size_kb:.1f} KB")


if __name__ == "__main__":
    main()
