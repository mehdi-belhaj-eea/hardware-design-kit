"""Inrush limiting with a precharge resistor and a bypass switch.

A bus capacitor C charged from a voltage V through a resistor R draws

    i(t) = V/R · exp(-t/τ),   v_C(t) = V · (1 - exp(-t/τ)),   τ = R·C

The resistor dissipates ½·C·V² over a full charge, the same energy that ends
up stored in the capacitor. A bypass switch (relay or MOSFET) shorts the
resistor once v_C reaches a fraction k of V; the time and energy up to that
point are

    t_k = -τ · ln(1 - k),   E_R(t_k) = ½·C·V² · (1 - (1 - k)²)

Design at the *maximum* bus voltage: the peak current V/R is highest there.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

import numpy as np


@dataclass(frozen=True)
class PrechargeDesign:
    v_bus: float          # maximum bus voltage used for the design (V)
    c_bus: float          # bus capacitance (F)
    r_pre: float          # precharge resistance (Ω)
    bypass_fraction: float
    i_peak: float         # peak inrush current V/R (A)
    tau: float            # time constant R·C (s)
    t_bypass: float       # time to reach the bypass threshold (s)
    energy_resistor: float  # energy dissipated in R until the bypass closes (J)
    energy_full: float    # ½·C·V², energy for a full charge through R (J)
    p_avg_resistor: float   # average power in R until the bypass closes (W)
    v_residual: float     # voltage still across R when the bypass closes (V)


def design_precharge(v_bus: float, c_bus: float, i_peak_max: float,
                     bypass_fraction: float = 0.9) -> PrechargeDesign:
    """Size the precharge resistor for a maximum inrush current.

    Parameters
    ----------
    v_bus: maximum bus voltage (V).
    c_bus: total capacitance to charge (F).
    i_peak_max: allowed peak inrush current (A).
    bypass_fraction: fraction of ``v_bus`` at which the bypass switch closes.
    """
    if not 0.0 < bypass_fraction < 1.0:
        raise ValueError("bypass_fraction must be between 0 and 1")
    if min(v_bus, c_bus, i_peak_max) <= 0:
        raise ValueError("v_bus, c_bus and i_peak_max must be positive")
    r = v_bus / i_peak_max
    tau = r * c_bus
    t_k = -tau * math.log(1.0 - bypass_fraction)
    e_full = 0.5 * c_bus * v_bus ** 2
    e_r = e_full * (1.0 - (1.0 - bypass_fraction) ** 2)
    return PrechargeDesign(
        v_bus=v_bus, c_bus=c_bus, r_pre=r, bypass_fraction=bypass_fraction,
        i_peak=v_bus / r, tau=tau, t_bypass=t_k, energy_resistor=e_r,
        energy_full=e_full, p_avg_resistor=e_r / t_k,
        v_residual=(1.0 - bypass_fraction) * v_bus,
    )


def waveforms(v_bus: float, r: float, c: float, t) -> tuple[np.ndarray, np.ndarray]:
    """Capacitor voltage and inrush current versus time (no bypass)."""
    t = np.asarray(t, dtype=float)
    tau = r * c
    i = v_bus / r * np.exp(-t / tau)
    v = v_bus * (1.0 - np.exp(-t / tau))
    return v, i


def bypass_step_current(design: PrechargeDesign, r_loop: float) -> float:
    """Current step when the bypass closes, limited by the loop resistance
    (switch on-resistance + capacitor ESR + wiring)."""
    return design.v_residual / r_loop


@dataclass(frozen=True)
class EnvelopeCheck:
    t_start: float
    t_end: float
    i_worst: float
    i_limit: float
    ok: bool


def check_inrush_envelope(i_peak: float, tau: float,
                          segments: Iterable[tuple[float, float, float]]) -> list[EnvelopeCheck]:
    """Compare the exponential inrush current with a stepped limit envelope.

    ``segments`` is a list of ``(t_start, t_end, i_limit)`` in seconds and
    amperes. The current decays, so its worst value in a segment is the one at
    ``t_start``. Use the envelope your program or product standard specifies.
    """
    rows = []
    for t0, t1, i_lim in segments:
        i_worst = i_peak * math.exp(-t0 / tau)
        rows.append(EnvelopeCheck(t0, t1, i_worst, i_lim, i_worst <= i_lim))
    return rows
