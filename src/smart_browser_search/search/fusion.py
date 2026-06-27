# -*- coding: utf-8 -*-
"""Reciprocal Rank Fusion — blend keyword and semantic result lists.

RRF needs no comparable score scales: an item's fused score is the sum over each
ranked list of ``1 / (k + rank)``. It is parameter-light (k≈60) and robust.
"""

from __future__ import annotations


def rrf(rankings: list[list[int]], k: int = 60, weights: list[float] | None = None
        ) -> list[tuple[int, float]]:
    """Fuse several ranked id lists into one ordered ``[(id, score), ...]``."""
    scores: dict[int, float] = {}
    if weights is None:
        weights = [1.0] * len(rankings)
    for ranking, weight in zip(rankings, weights):
        for rank, item in enumerate(ranking):
            scores[item] = scores.get(item, 0.0) + weight * (1.0 / (k + rank + 1))
    return sorted(scores.items(), key=lambda kv: kv[1], reverse=True)


def fuse_ids(rankings: list[list[int]], k: int = 60,
             weights: list[float] | None = None) -> list[int]:
    return [item for item, _score in rrf(rankings, k, weights)]
