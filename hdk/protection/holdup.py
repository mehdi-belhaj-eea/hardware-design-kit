"""Hold-up (energy reserve) capacitor sizing.

The capacitor must supply the load energy while its voltage falls from V1 to V2
(V2 = minimum input voltage of the downstream converter):

    E = Σ P_i·t_i / η,   C_min = 2·E / (V1² − V2²)

The nominal value covers tolerance and ageing:

    C_nom = C_min / ((1 − tolerance) · (1 − ageing))

Storing the energy at a higher voltage (a boosted storage bus) shrinks C,
because the usable energy grows with V1².
"""

from __future__ import annotations

from typing import Iterable


def energy(segments: Iterable[tuple[float, float]], efficiency: float = 1.0) -> float:
    """Energy drawn from the capacitor for a load profile ``[(P_watts, t_seconds), ...]``."""
    if not 0.0 < efficiency <= 1.0:
        raise ValueError("efficiency must be in (0, 1]")
    return sum(p * t for p, t in segments) / efficiency


def capacitance_min(energy_j: float, v_start: float, v_end: float) -> float:
    """Minimum capacitance that delivers ``energy_j`` between ``v_start`` and ``v_end``."""
    if v_start <= v_end:
        raise ValueError("v_start must be greater than v_end")
    return 2.0 * energy_j / (v_start ** 2 - v_end ** 2)


def capacitance_nominal(c_min: float, tolerance: float = 0.2, ageing: float = 0.1) -> float:
    """Nominal capacitance once tolerance and end-of-life ageing are applied."""
    return c_min / ((1.0 - tolerance) * (1.0 - ageing))


def holdup_time(c: float, v_start: float, v_end: float, p_load: float,
                efficiency: float = 1.0) -> float:
    """Hold-up time provided by capacitance ``c`` at constant load power."""
    return efficiency * c * (v_start ** 2 - v_end ** 2) / (2.0 * p_load)
