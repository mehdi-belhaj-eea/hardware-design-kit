"""Trace width, resistance and via current (IPC-2221).

IPC-2221 gives the current a trace carries for a temperature rise ΔT (°C):

    I = k · ΔT^0.44 · A^0.725,   A = cross-section in mil²,
    k = 0.048 for external layers, 0.024 for internal layers

(fitted on the historical charts; stated for up to 35 A, 400 mil wide and
ΔT = 10–100 °C). It is conservative for internal layers: IPC-2152, its
successor, shows that internal traces in a real board run nearly as cool as
external ones. A via barrel is estimated as an internal conductor of
cross-section π·t·(d − t): the plating t grows inside the drilled hole d.
"""

from __future__ import annotations

import math

MIL = 25.4e-6                 # m
COPPER_OZ = 35e-6             # m of copper per oz/ft² (1 oz ≈ 1.38 mil)
MAX_WIDTH = 400 * MIL         # widest trace covered by the IPC-2221 fit
MAX_CURRENT = 35.0            # highest current covered by the IPC-2221 fit (A)
RHO_CU_20C = 1.72e-8          # Ω·m
ALPHA_CU = 0.00393            # 1/K


def _k(external: bool) -> float:
    return 0.048 if external else 0.024


def ipc2221_current(width: float, thickness: float, delta_t: float, external: bool = True) -> float:
    """Current (A) for a trace of given width and copper thickness (m) and a rise delta_t (°C)."""
    area_mil2 = width * thickness / MIL ** 2
    return _k(external) * delta_t ** 0.44 * area_mil2 ** 0.725


def ipc2221_width(current: float, thickness: float, delta_t: float, external: bool = True) -> float:
    """Trace width (m) that carries ``current`` with a temperature rise delta_t (°C).

    Check the result with :func:`in_ipc2221_range`: beyond 400 mil or 35 A the
    formula is an extrapolation.
    """
    area_mil2 = (current / (_k(external) * delta_t ** 0.44)) ** (1.0 / 0.725)
    return area_mil2 * MIL ** 2 / thickness


def in_ipc2221_range(width: float, current: float) -> bool:
    """True when the width and current lie inside the range of the IPC-2221 fit."""
    return width <= MAX_WIDTH and current <= MAX_CURRENT


def trace_resistance(width: float, thickness: float, length: float, t_c: float = 20.0) -> float:
    """DC resistance of a trace (Ω) at temperature t_c (°C)."""
    rho = RHO_CU_20C * (1.0 + ALPHA_CU * (t_c - 20.0))
    return rho * length / (width * thickness)


def via_current(drill: float, plating: float = 25e-6, delta_t: float = 10.0) -> float:
    """Estimated current (A) of one plated via (drill diameter, plating thickness in m),
    treated as an internal conductor."""
    area = math.pi * plating * (drill - plating)
    return 0.024 * delta_t ** 0.44 * (area / MIL ** 2) ** 0.725
