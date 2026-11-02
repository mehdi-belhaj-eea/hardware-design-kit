"""Input EMI filter design: differential mode (DM), common mode (CM) and stability.

DM filter topology (π with the converter's own capacitors)
-----------------------------------------------------------

    LISN ── C_f ── L_f ── C_in ∥ (R_d + C_d) ── converter (noise current source)

The converter is a noise current source; its own input capacitors C_in take
most of the ripple. The filter adds L_f in series and C_f across the line on
the LISN side. When |Z_Cin| ≪ |Z_Lf| and |Z_Cf| ≪ R_LISN, the insertion loss is

    IL ≈ ω²·L_f·C_f = (f / f0)²,   f0 = 1/(2π·√(L_f·C_f))

that is 40 dB/decade above f0. A required attenuation A at the noise frequency
f_n therefore gives f0 ≤ f_n · 10^(−A/40); for a chosen impedance level
R0 = √(L_f/C_f):  L_f = R0/ω0,  C_f = 1/(ω0·R0).

Damping (Erickson & Maksimović, Fundamentals of Power Electronics, ch. 10)
--------------------------------------------------------------------------
On a stiff bus, the converter sees L_f resonating with its own C_in. A branch
R_d + C_d across C_in (C_d = n·C_in) damps it; the optimum resistance and the
resulting peak output impedance are, with R0' = √(L_f/C_in),

    R_d,opt = R0' · √( (2 + n)(4 + 3n) / (2·n²·(4 + n)) )
    |Z_o|max = R0' · √(2·(2 + n)) / n

Stability (Middlebrook)
-----------------------
A regulated converter has a negative incremental input resistance of magnitude
|Z_in| = V_in,min² · η / P_out,max. The filter output impedance must stay well
below it at every frequency: |Z_o|max ≤ |Z_in| / margin.

Measurement
-----------
The DM current flows through both 50 Ω LISNs in series (100 Ω); each LISN port
reads 50 Ω × the DM current.

CM: the switching node drives a parasitic capacitance to chassis
(i = C_p·dv/dt); the CM current returns through both LISNs in parallel (25 Ω)
unless the Y capacitors (one per line, 2·C_Y in total for CM) divert it. Each
LISN port reads 50 Ω × i_CM/2 = 25 Ω × i_CM.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy.optimize import minimize_scalar

from ..units import TWO_PI, db20, parallel, undb20


# --------------------------------------------------------------------------- elements
def z_cap(f, c: float, esr: float = 0.0, esl: float = 0.0):
    """Impedance of a capacitor with ESR and ESL."""
    w = TWO_PI * np.asarray(f, dtype=float)
    return esr + 1j * w * esl + 1.0 / (1j * w * c)


def z_ind(f, l: float, r: float = 0.0, c_par: float = 0.0):
    """Impedance of an inductor with winding resistance and parallel parasitic capacitance."""
    w = TWO_PI * np.asarray(f, dtype=float)
    z = r + 1j * w * l
    if c_par > 0.0:
        z = parallel(z, 1.0 / (1j * w * c_par))
    return z


# --------------------------------------------------------------------------- DM design
def corner_for_attenuation(f_noise: float, attenuation_db: float,
                           slope_db_per_decade: float = 40.0) -> float:
    """Highest corner frequency that gives ``attenuation_db`` at ``f_noise``."""
    return f_noise * 10.0 ** (-attenuation_db / slope_db_per_decade)


def lc_from_corner(f0: float, r0: float) -> tuple[float, float]:
    """(L_f, C_f) for a corner ``f0`` and an impedance level ``r0`` = √(L_f/C_f)."""
    w0 = TWO_PI * f0
    return r0 / w0, 1.0 / (w0 * r0)


@dataclass(frozen=True)
class Damping:
    r_d: float
    c_d: float
    n: float
    r0: float
    zo_peak: float


def parallel_rc_damping(l: float, c: float, n: float) -> Damping:
    """Optimum R–C_d damping branch across ``c`` (closed form).

    For the input filter, ``l`` is L_f and ``c`` is the converter-side capacitance C_in.
    """
    r0 = math.sqrt(l / c)
    r_d = r0 * math.sqrt((2.0 + n) * (4.0 + 3.0 * n) / (2.0 * n * n * (4.0 + n)))
    zo = r0 * math.sqrt(2.0 * (2.0 + n)) / n
    return Damping(r_d, n * c, n, r0, zo)


def output_impedance(f, l: float, c: float, damping: Damping | None = None, r_l: float = 0.0):
    """Output impedance seen by the converter on a stiff bus: L_f ∥ C_in ∥ (R_d + C_d).

    ``r_l`` is the inductor winding resistance, the only loss of an undamped filter.
    """
    z = parallel(z_ind(f, l, r_l), z_cap(f, c))
    if damping is not None:
        z = parallel(z, damping.r_d + z_cap(f, damping.c_d))
    return z


def _grid_around(l: float, c: float, points: int = 8001):
    f0 = 1.0 / (TWO_PI * math.sqrt(l * c))
    return np.logspace(math.log10(f0 / 30.0), math.log10(f0 * 30.0), points)


def peak_output_impedance(l: float, c: float, damping: Damping | None = None,
                          r_l: float = 0.0) -> float:
    """Numerical maximum of |Z_o| around the resonance."""
    return float(np.max(np.abs(output_impedance(_grid_around(l, c), l, c, damping, r_l))))


def optimal_damping_numeric(l: float, c: float, n: float) -> Damping:
    """Search R_d that minimises the peak |Z_o| (used to verify the closed form)."""
    r0 = math.sqrt(l / c)

    def peak(log_r: float) -> float:
        d = Damping(10.0 ** log_r, n * c, n, r0, 0.0)
        return peak_output_impedance(l, c, d)

    res = minimize_scalar(peak, bounds=(math.log10(r0) - 3.0, math.log10(r0) + 3.0),
                          method="bounded", options={"xatol": 1e-6})
    r_d = 10.0 ** res.x
    return Damping(r_d, n * c, n, r0, float(res.fun))


# --------------------------------------------------------------------------- stability
def converter_input_impedance(v_in_min: float, p_out_max: float, efficiency: float = 1.0) -> float:
    """Magnitude of the converter's negative input resistance (worst case)."""
    return v_in_min ** 2 * efficiency / p_out_max


def middlebrook_ok(zo_peak: float, z_in: float, margin_db: float = 6.0) -> bool:
    """True when the filter output impedance stays ``margin_db`` below |Z_in|."""
    return zo_peak <= z_in / float(undb20(margin_db))


# --------------------------------------------------------------------------- DM noise path
@dataclass(frozen=True)
class ConverterInput:
    """The converter's own input capacitors (part of the noise source)."""

    c_in: float
    esr: float = 0.0
    esl: float = 0.0


@dataclass(frozen=True)
class DMFilter:
    l: float                # series inductor L_f (H)
    c: float                # LISN-side capacitor C_f (F)
    damping: Damping | None = None   # R_d + C_d across the converter's C_in
    l_dcr: float = 0.0      # inductor winding resistance (Ω)
    l_cpar: float = 0.0     # inductor parasitic capacitance (F)
    c_esr: float = 0.0      # C_f ESR (Ω)
    c_esl: float = 0.0      # C_f ESL (H)
    cd_esr: float = 0.0     # ESR of the damping capacitor (adds to R_d)


def dm_lisn_current_ratio(f, conv: ConverterInput, filt: DMFilter | None = None,
                          r_lisn_dm: float = 100.0):
    """Complex ratio i_LISN / i_noise for the DM path (π topology, see module notes)."""
    z_a = z_cap(f, conv.c_in, conv.esr, conv.esl)
    if filt is None:
        return z_a / (z_a + r_lisn_dm)
    if filt.damping is not None:
        z_a = parallel(z_a, filt.damping.r_d + z_cap(f, filt.damping.c_d, filt.cd_esr))
    z_cf = z_cap(f, filt.c, filt.c_esr, filt.c_esl)
    z_b = parallel(z_cf, r_lisn_dm)
    z_l = z_ind(f, filt.l, filt.l_dcr, filt.l_cpar)
    i_l = z_a / (z_a + z_l + z_b)
    return i_l * z_cf / (z_cf + r_lisn_dm)


def dm_insertion_loss_db(f, conv: ConverterInput, filt: DMFilter, r_lisn_dm: float = 100.0):
    """Insertion loss of the DM filter (dB, positive = attenuation)."""
    without = dm_lisn_current_ratio(f, conv, None, r_lisn_dm)
    with_f = dm_lisn_current_ratio(f, conv, filt, r_lisn_dm)
    return db20(without / with_f)


# --------------------------------------------------------------------------- CM noise path
@dataclass(frozen=True)
class CMFilter:
    l_cm: float          # common-mode inductance of the choke (H)
    c_y: float           # Y capacitor on each line to chassis (F)
    l_cpar: float = 0.0  # choke parasitic capacitance (F)


def cm_corner(l_cm: float, c_y: float) -> float:
    """CM corner frequency: the two Y capacitors act in parallel (2·C_Y)."""
    return 1.0 / (TWO_PI * math.sqrt(l_cm * 2.0 * c_y))


def cm_noise_current(f, v_harmonics, c_parasitic: float):
    """CM current injected through ``c_parasitic`` by the switching-node harmonics."""
    return TWO_PI * np.asarray(f, dtype=float) * c_parasitic * np.asarray(v_harmonics)


def cm_lisn_current_ratio(f, filt: CMFilter | None = None, r_lisn_cm: float = 25.0):
    """Complex ratio i_LISN / i_CM for the CM path."""
    if filt is None:
        return np.ones(np.shape(f), dtype=complex)
    z_y = z_cap(f, 2.0 * filt.c_y)
    z_series = z_ind(f, filt.l_cm, 0.0, filt.l_cpar) + r_lisn_cm
    return z_y / (z_y + z_series)
