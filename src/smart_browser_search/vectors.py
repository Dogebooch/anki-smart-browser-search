# -*- coding: utf-8 -*-
"""Pure-Python vector math — no numpy, no compiled code.

The semantic index stores each embedding twice:

* a **binary** code (one bit per dimension, sign of the value) packed into bytes.
  At query time these load into Python ``int``s and we score similarity with
  ``(a ^ q).bit_count()`` — a C-level popcount available since Python 3.10
  (== Anki's minimum). 40k x 768-bit scans in ~7 ms.
* the **float32** vector, used only to exactly re-rank the top few hundred
  binary candidates so recall stays high.

This is the design decision that lets a 40k-card deck stay interactive with zero
third-party dependencies.
"""

from __future__ import annotations

import array
import math
from typing import Sequence


def l2_normalize(vec: Sequence[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vec))
    if norm == 0.0:
        return list(vec)
    inv = 1.0 / norm
    return [x * inv for x in vec]


def binarize_to_bytes(vec: Sequence[float], dim: int) -> bytes:
    """Sign-threshold each dimension into a packed bit string (dim/8 bytes)."""
    ba = bytearray((dim + 7) >> 3)
    for i, x in enumerate(vec):
        if i >= dim:
            break
        if x > 0.0:
            ba[i >> 3] |= 1 << (i & 7)
    return bytes(ba)


def bytes_to_int(b: bytes) -> int:
    return int.from_bytes(b, "big")


def pack_f32(vec: Sequence[float]) -> bytes:
    return array.array("f", vec).tobytes()


def unpack_f32(b: bytes) -> list[float]:
    a = array.array("f")
    a.frombytes(b)
    return a.tolist()


def hamming(a: int, b: int) -> int:
    return (a ^ b).bit_count()


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine similarity. Robust to non-normalized inputs."""
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


def dot(a: Sequence[float], b: Sequence[float]) -> float:
    s = 0.0
    for x, y in zip(a, b):
        s += x * y
    return s
