"""Surge and lightning-transient protection with TVS diodes.

Source model
------------
The transient is a Thévenin source: open-circuit voltage V_oc·w(t) behind a
resistance R_s = V_oc / I_sc. The shape w(t) is a double exponential with a
given time to peak and time to half value (both measured from t = 0):

    w(t) = k · (exp(−α·t) − exp(−β·t))

This is a simplification: the standards define front times differently (for
example IEC 61000-4-5 uses a virtual front time), which is fine for sizing.

TVS model
---------
A linearised clamp: no current below the breakdown voltage V_BR, then

    V_TVS = V_BR + R_d · I,   R_d = (V_C − V_BR) / I_PP

taken from the datasheet point (V_C at I_PP). The model is accurate near I_PP
and optimistic far above it: confirm the final part with the datasheet curves.

Power rating
------------
The peak pulse power a TVS can absorb rises for shorter pulses. Without the
datasheet curve, the usual first estimate is P(t) ≈ P_ref · (t / t_ref)^(−1/2)
(adiabatic heating), with P_ref given for a 10/1000 µs pulse (t_ref = 1 ms).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

import numpy as np
from scipy.optimize import brentq

_trapezoid = getattr(np, "trapezoid", None) or np.trapz


@dataclass(frozen=True)
class DoubleExponential:
    """Normalised double-exponential wave (peak value 1)."""

    t_peak: float
    t_half: float
    alpha: float
    beta: float
    k: float

    def __call__(self, t):
        t = np.asarray(t, dtype=float)
        w = self.k * (np.exp(-self.alpha * t) - np.exp(-self.beta * t))
        return np.where(t >= 0.0, w, 0.0)


def double_exponential(t_peak: float, t_half: float) -> DoubleExponential:
    """Fit α and β so that the wave peaks at ``t_peak`` and falls to 50 % at ``t_half``."""
    if t_half <= 2.7 * t_peak:
        raise ValueError("t_half must be greater than about 2.7 × t_peak for this wave shape")

    def alpha_of(r: float) -> float:
        return math.log(r) / (t_peak * (r - 1.0))

    def normalised(t: float, r: float) -> float:
        a = alpha_of(r)
        b = r * a
        s = lambda x: math.exp(-a * x) - math.exp(-b * x)  # noqa: E731
        return s(t) / s(t_peak)

    r = brentq(lambda r: normalised(t_half, r) - 0.5, 1.0 + 1e-9, 1e9, xtol=1e-12, maxiter=500)
    a = alpha_of(r)
    b = r * a
    k = 1.0 / (math.exp(-a * t_peak) - math.exp(-b * t_peak))
    return DoubleExponential(t_peak, t_half, a, b, k)


@dataclass(frozen=True)
class TVS:
    """Datasheet values of one TVS diode (unidirectional or one polarity of a bidirectional)."""

    name: str
    v_wm: float          # working (stand-off) voltage (V)
    v_br: float          # breakdown voltage (V)
    v_c: float           # clamping voltage at i_pp (V)
    i_pp: float          # peak pulse current at the reference waveform (A)
    p_pp: float          # peak pulse power at the reference waveform (W)
    t_ref: float = 1e-3  # reference pulse width (10/1000 µs ≈ 1 ms)
    n_series: int = 1

    @property
    def r_dyn(self) -> float:
        """Dynamic resistance of one diode (Ω)."""
        return (self.v_c - self.v_br) / self.i_pp

    def stack(self, n_series: int) -> "TVS":
        """The same part with ``n_series`` diodes in series."""
        return replace(self, n_series=n_series)

    @property
    def v_wm_total(self) -> float:
        return self.n_series * self.v_wm

    @property
    def v_br_total(self) -> float:
        return self.n_series * self.v_br

    @property
    def r_dyn_total(self) -> float:
        return self.n_series * self.r_dyn

    @property
    def p_pp_total(self) -> float:
        return self.n_series * self.p_pp


@dataclass(frozen=True)
class ClampResult:
    t: np.ndarray
    i: np.ndarray        # TVS current (A)
    v: np.ndarray        # protected-node voltage (V)
    p: np.ndarray        # TVS power (W)
    i_peak: float
    v_peak: float
    p_peak: float
    energy: float        # energy absorbed by the TVS stack (J)


def clamp_response(tvs: TVS, v_oc: float, r_source: float, wave: DoubleExponential,
                   t=None) -> ClampResult:
    """Current, clamped voltage and energy when the transient hits the TVS stack."""
    if t is None:
        t = np.linspace(0.0, 6.0 * wave.t_half, 60001)
    t = np.asarray(t, dtype=float)
    voc = v_oc * wave(t)
    i = np.clip((voc - tvs.v_br_total) / (r_source + tvs.r_dyn_total), 0.0, None)
    v = np.where(i > 0.0, tvs.v_br_total + tvs.r_dyn_total * i, voc)
    p = v * i
    return ClampResult(t, i, v, p, float(i.max()), float(v.max()), float(p.max()),
                       float(_trapezoid(p, t)))


def allowed_peak_power(tvs: TVS, t_pulse: float, exponent: float = -0.5) -> float:
    """First-estimate pulse power rating of the stack for a pulse of width ``t_pulse``."""
    return tvs.p_pp_total * (t_pulse / tvs.t_ref) ** exponent


@dataclass(frozen=True)
class TVSCheck:
    standoff_ok: bool     # no conduction at the highest operating voltage
    clamp_ok: bool        # clamped voltage below the downstream absolute maximum
    power_ok: bool        # peak power within the (estimated) rating
    p_allowed: float
    clamp_margin: float   # V
    power_margin: float   # ratio allowed / actual

    @property
    def ok(self) -> bool:
        return self.standoff_ok and self.clamp_ok and self.power_ok


def check(tvs: TVS, result: ClampResult, t_pulse: float, v_operating_max: float,
          v_abs_max_downstream: float) -> TVSCheck:
    """Pass/fail of the three usual TVS criteria."""
    p_allowed = allowed_peak_power(tvs, t_pulse)
    return TVSCheck(
        standoff_ok=tvs.v_wm_total >= v_operating_max,
        clamp_ok=result.v_peak <= v_abs_max_downstream,
        power_ok=result.p_peak <= p_allowed,
        p_allowed=p_allowed,
        clamp_margin=v_abs_max_downstream - result.v_peak,
        power_margin=p_allowed / result.p_peak if result.p_peak > 0 else math.inf,
    )


@dataclass(frozen=True)
class TVSRequirement:
    i_peak: float     # current the protection must carry (A)
    p_peak: float     # peak power at the clamp limit (W)
    r_dyn_max: float  # largest acceptable dynamic resistance of the stack (Ω)


def required_rating(v_oc: float, r_source: float, v_clamp_max: float,
                    v_br_total: float) -> TVSRequirement:
    """What a protection must achieve to keep the node below ``v_clamp_max``."""
    i_pk = (v_oc - v_clamp_max) / r_source
    return TVSRequirement(i_pk, v_clamp_max * i_pk, (v_clamp_max - v_br_total) / i_pk)
