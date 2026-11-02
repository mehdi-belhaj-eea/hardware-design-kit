"""Conducted-emission limit lines.

A limit is a list of segments ``(f_start, f_stop, level_start, level_stop)``
with the level linear in log(f). Where two segments meet, the lower (stricter)
value applies.

The CISPR 32 class B lines below are a well-known public reference used for
illustration. Use the limit that applies to your product (CISPR 11, CISPR 14,
CISPR 25, DO-160 Section 21, MIL-STD-461 CE102, ...).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class LimitLine:
    name: str
    unit: str
    segments: tuple[tuple[float, float, float, float], ...]

    def __call__(self, f):
        f = np.asarray(f, dtype=float)
        out = np.full(f.shape, np.nan)
        for f1, f2, l1, l2 in self.segments:
            inside = (f >= f1) & (f <= f2)
            frac = (np.log10(np.clip(f, f1, f2)) - math.log10(f1)) / (math.log10(f2) - math.log10(f1))
            level = l1 + (l2 - l1) * frac
            out = np.where(inside & np.isnan(out), level, out)
            out = np.where(inside & ~np.isnan(out), np.minimum(out, level), out)
        return out

    @property
    def f_min(self) -> float:
        return min(s[0] for s in self.segments)

    @property
    def f_max(self) -> float:
        return max(s[1] for s in self.segments)


CISPR32_CLASS_B_MAINS_QP = LimitLine(
    "CISPR 32 class B, AC mains port, quasi-peak", "dBµV",
    ((150e3, 500e3, 66.0, 56.0), (500e3, 5e6, 56.0, 56.0), (5e6, 30e6, 60.0, 60.0)),
)

CISPR32_CLASS_B_MAINS_AV = LimitLine(
    "CISPR 32 class B, AC mains port, average", "dBµV",
    ((150e3, 500e3, 56.0, 46.0), (500e3, 5e6, 46.0, 46.0), (5e6, 30e6, 50.0, 50.0)),
)


def margin(levels_db, f, limit: LimitLine):
    """Limit minus level (dB); positive means the level is below the limit."""
    return limit(f) - np.asarray(levels_db, dtype=float)
