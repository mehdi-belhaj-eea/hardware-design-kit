"""Error budget of a measurement chain.

Each term is a relative error at full scale (±). Worst case adds the magnitudes;
the root sum of squares (RSS) assumes independent, random terms. A two-point
calibration (offset and gain) at production removes the initial tolerances, but
not the drifts with temperature and time, the non-linearity or the noise.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class ErrorTerm:
    name: str
    value: float               # ± relative error at full scale
    calibratable: bool = False  # removed by a two-point calibration


@dataclass(frozen=True)
class Budget:
    name: str
    terms: tuple[ErrorTerm, ...]

    def _kept(self, calibrated: bool):
        return [t.value for t in self.terms if not (calibrated and t.calibratable)]

    def worst_case(self, calibrated: bool = False) -> float:
        return sum(abs(v) for v in self._kept(calibrated))

    def rss(self, calibrated: bool = False) -> float:
        return math.sqrt(sum(v * v for v in self._kept(calibrated)))

    def largest(self, calibrated: bool = False) -> ErrorTerm:
        terms = [t for t in self.terms if not (calibrated and t.calibratable)]
        return max(terms, key=lambda t: abs(t.value))
