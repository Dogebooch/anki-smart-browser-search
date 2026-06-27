# -*- coding: utf-8 -*-
"""Threading helpers so the add-on never blocks Anki's UI thread.

All collection reads run inside a read-only ``QueryOp``; all network calls run
on a background worker via ``taskman``. Results are marshalled back to the main
thread before they touch any Qt/webview object.
"""

from __future__ import annotations

from concurrent.futures import Future
from typing import Any, Callable

from . import log


def on_main(fn: Callable[[], Any]) -> None:
    """Run ``fn`` on the UI thread (safe to call from a worker thread)."""
    from aqt import mw

    if mw is None:
        return
    mw.taskman.run_on_main(fn)


def run_query(
    op: Callable[[Any], Any],
    success: Callable[[Any], None],
    failure: Callable[[Exception], None] | None = None,
    *,
    uses_collection: bool = True,
    with_progress: bool = False,
    label: str = "Smart searching…",
) -> None:
    """Run a READ-ONLY ``op(col)`` in the background, then ``success(result)`` on
    the main thread. ``op`` must not touch Qt or the webview directly.
    """
    from aqt import mw
    from aqt.operations import QueryOp

    def _failure(exc: Exception) -> None:
        log.error("background op failed", exc)
        if failure is not None:
            failure(exc)

    q = QueryOp(parent=mw, op=op, success=success).failure(_failure)
    if not uses_collection:
        q = q.without_collection()
    if with_progress:
        q = q.with_progress(label)
    q.run_in_background()


def run_network(
    task: Callable[[], Any],
    success: Callable[[Any], None],
    failure: Callable[[Exception], None] | None = None,
) -> None:
    """Run a non-collection ``task()`` (e.g. an HTTP call) on a worker thread and
    deliver the result (or error) on the main thread.
    """
    from aqt import mw

    def _done(fut: Future) -> None:
        try:
            result = fut.result()
        except Exception as exc:  # noqa: BLE001
            log.error("network task failed", exc)
            if failure is not None:
                on_main(lambda: failure(exc))
            return
        on_main(lambda: success(result))

    # uses_collection=False keeps network work OFF the single collection-serialized
    # worker, so a slow LLM/embedding call never queues behind a collection op.
    mw.taskman.run_in_background(task, _done, uses_collection=False)
