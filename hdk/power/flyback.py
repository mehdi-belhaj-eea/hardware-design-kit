"""Flyback converter design: turns ratio, magnetising inductance, currents and stresses.

Notation
--------
n = N_p / N_s                  primary-to-secondary turns ratio
V_OR = n·(V_out + V_F)         output voltage reflected to the primary during the off-time
K_RP = ΔI / I_pk               ripple ratio of the primary current (1 = boundary mode)

Continuous conduction (CCM): the volt-second balance of the magnetising
inductance gives V_in·D = V_OR·(1 − D), so D = V_OR / (V_OR + V_in). The duty
cycle is largest at the minimum input voltage, where the design starts:

    n = V_in,min·D_max / ((V_out + V_F)·(1 − D_max))

Primary current during the on-time: average I_in/D, ripple ΔI = V_in·D / (f·L_m):

    I_pk = I_in/D + ΔI/2,   L_m = V_in,min·D / (f·K_RP·I_pk)

When the valley current I_in/D − ΔI/2 reaches zero (light load, high line), the
converter enters discontinuous mode (DCM), where P_in = ½·L_m·I_pk²·f and the
magnetising inductance resets in a fraction D2 = V_in·D / V_OR of the period.

RMS of a current that ramps from I_a to I_b during a fraction δ of the period:

    I_rms = √(δ·(I_a² + I_a·I_b + I_b²) / 3)

Losses are lumped into the efficiency η: the primary carries P_out/η. The
secondary carries the magnetising current reflected at the commutation (n·i_p,
from n·I_pk down to n·I_valley in CCM), so its peak and RMS values are slightly
conservative: their average exceeds I_out by the losses lumped into η. The
output-capacitor current is computed on the same waveform scaled to an average
of exactly I_out.

Leakage inductance and RCD clamp
--------------------------------
At turn-off the leakage inductance L_lk keeps the primary current flowing into
the clamp until it resets under V_clamp − V_OR. The clamp absorbs

    P_clamp = ½·L_lk·I_pk²·f · V_clamp / (V_clamp − V_OR)

and the drain reaches V_in + V_clamp. A resistor R = V_clamp² / P_clamp holds the
clamp voltage and the capacitor sets its ripple.

Right-half-plane zero (CCM)
---------------------------
    f_RHPZ = (1 − D)²·R_load·n² / (2π·D·L_m)

The control loop must cross over well below it (a fifth or less).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class FlybackSpec:
    v_in_min: float          # minimum input voltage (V)
    v_in_max: float          # maximum input voltage (V)
    v_out: float             # output voltage (V)
    i_out: float             # full-load output current (A)
    f_sw: float              # switching frequency (Hz)
    efficiency: float = 0.85
    v_f: float = 0.5         # forward drop of the output rectifier (V)
    d_max: float = 0.45      # duty cycle at minimum input, full load
    k_rp: float = 0.5        # ripple ratio ΔI / I_pk at minimum input, full load

    def __post_init__(self):
        if not 0.0 < self.k_rp <= 1.0:
            raise ValueError("k_rp must be in (0, 1]")
        if not 0.0 < self.d_max < 1.0:
            raise ValueError("d_max must be in (0, 1)")
        if not 0.0 < self.efficiency <= 1.0:
            raise ValueError("efficiency must be in (0, 1]")
        if self.v_in_min > self.v_in_max:
            raise ValueError("v_in_min must not exceed v_in_max")

    @property
    def p_out(self) -> float:
        return self.v_out * self.i_out

    @property
    def p_in(self) -> float:
        return self.p_out / self.efficiency


def turns_ratio(spec: FlybackSpec) -> float:
    """Ideal turns ratio n = N_p/N_s that gives D_max at the minimum input voltage."""
    return spec.v_in_min * spec.d_max / ((spec.v_out + spec.v_f) * (1.0 - spec.d_max))


def ccm_duty(v_in: float, v_or: float) -> float:
    """Duty cycle in continuous mode."""
    return v_or / (v_or + v_in)


def trapezoid_rms(i_a: float, i_b: float, fraction: float) -> float:
    """RMS value of a current ramping from i_a to i_b during ``fraction`` of the period."""
    return math.sqrt(fraction * (i_a * i_a + i_a * i_b + i_b * i_b) / 3.0)


@dataclass(frozen=True)
class OperatingPoint:
    v_in: float
    i_out: float
    mode: str               # "CCM" or "DCM"
    duty: float             # on-time fraction of the switch
    d_off: float            # fraction of the period where the rectifier conducts
    i_in: float             # average input current (A)
    i_p_peak: float
    i_p_valley: float       # primary current at turn-on (0 in DCM)
    i_p_rms: float
    delta_i: float          # primary current ripple, peak to peak
    i_s_peak: float         # n·I_pk (conservative, see the module notes)
    i_s_valley: float       # n·I_valley (0 in DCM)
    i_s_rms: float
    i_cout_rms: float       # RMS current in the output capacitor

    @property
    def i_s_avg(self) -> float:
        """Average of the reflected secondary current (≥ I_out by the lumped losses)."""
        return (self.i_s_peak + self.i_s_valley) / 2.0 * self.d_off

    @property
    def output_scale(self) -> float:
        """Factor that scales the secondary waveform to an average of exactly I_out."""
        return self.i_out / self.i_s_avg


def operating_point(spec: FlybackSpec, n: float, l_m: float, v_in: float,
                    i_out: float | None = None) -> OperatingPoint:
    """Currents at a given input voltage and load, in CCM or DCM."""
    i_out = spec.i_out if i_out is None else i_out
    p_in = spec.v_out * i_out / spec.efficiency
    f = spec.f_sw
    v_or = n * (spec.v_out + spec.v_f)
    d = ccm_duty(v_in, v_or)
    i_in = p_in / v_in
    di = v_in * d / (f * l_m)
    i_on = i_in / d
    valley = i_on - di / 2.0
    if valley > 1e-9 * max(i_on, 1e-12):
        mode = "CCM"
        i_pk = i_on + di / 2.0
        d_off = 1.0 - d
    else:
        mode = "DCM"
        i_pk = math.sqrt(2.0 * p_in / (l_m * f))
        d = i_pk * l_m * f / v_in
        valley = 0.0
        di = i_pk
        d_off = v_in * d / v_or
    is_pk, is_v = n * i_pk, n * valley
    i_p_rms = trapezoid_rms(valley, i_pk, d)
    i_s_rms = trapezoid_rms(is_pk, is_v, d_off)
    scale = i_out / ((is_pk + is_v) / 2.0 * d_off)
    return OperatingPoint(
        v_in=v_in, i_out=i_out, mode=mode, duty=d, d_off=d_off, i_in=i_in,
        i_p_peak=i_pk, i_p_valley=valley, i_p_rms=i_p_rms, delta_i=di,
        i_s_peak=is_pk, i_s_valley=is_v, i_s_rms=i_s_rms,
        i_cout_rms=math.sqrt(max((scale * i_s_rms) ** 2 - i_out ** 2, 0.0)),
    )


@dataclass(frozen=True)
class FlybackDesign:
    spec: FlybackSpec
    n: float                 # turns ratio N_p/N_s
    v_or: float              # reflected voltage (V)
    l_m: float               # magnetising inductance (H)
    low_line: OperatingPoint
    high_line: OperatingPoint
    v_ds_off: float          # V_in,max + V_OR: drain voltage before the leakage spike (V)
    v_diode_reverse: float   # V_out + V_in,max / n: rectifier reverse voltage (V)

    @property
    def worst(self) -> OperatingPoint:
        """Operating point with the highest primary peak current."""
        return max((self.low_line, self.high_line), key=lambda op: op.i_p_peak)

    @property
    def i_p_peak_max(self) -> float:
        return self.worst.i_p_peak


def design(spec: FlybackSpec, n: float | None = None) -> FlybackDesign:
    """Size the turns ratio and the magnetising inductance.

    ``n`` overrides the ideal turns ratio, for example after rounding the turns:
    the duty cycle at minimum input then follows from n, and L_m keeps the
    ripple ratio K_RP at minimum input and full load.
    """
    n = turns_ratio(spec) if n is None else n
    v_or = n * (spec.v_out + spec.v_f)
    d = ccm_duty(spec.v_in_min, v_or)
    i_on = spec.p_in / spec.v_in_min / d
    i_pk = i_on / (1.0 - spec.k_rp / 2.0)
    l_m = spec.v_in_min * d / (spec.f_sw * spec.k_rp * i_pk)
    return FlybackDesign(
        spec=spec, n=n, v_or=v_or, l_m=l_m,
        low_line=operating_point(spec, n, l_m, spec.v_in_min),
        high_line=operating_point(spec, n, l_m, spec.v_in_max),
        v_ds_off=spec.v_in_max + v_or,
        v_diode_reverse=spec.v_out + spec.v_in_max / n,
    )


# --------------------------------------------------------------------------- clamp
@dataclass(frozen=True)
class RCDClamp:
    v_clamp: float      # clamp capacitor voltage above the input (V)
    p_clamp: float      # power dissipated in the clamp (W)
    r: float            # clamp resistor (Ω)
    c: float            # clamp capacitor (F)
    v_ds_peak: float    # drain peak V_in,max + V_clamp (V)


def rcd_clamp(l_lk: float, i_pk: float, f_sw: float, v_or: float, v_in_max: float,
              k_clamp: float = 2.0, ripple: float = 0.1) -> RCDClamp:
    """Size an RCD clamp for a clamp voltage k_clamp·V_OR and a relative ripple."""
    if k_clamp <= 1.0:
        raise ValueError("the clamp voltage must exceed the reflected voltage (k_clamp > 1)")
    v_cl = k_clamp * v_or
    p = 0.5 * l_lk * i_pk ** 2 * f_sw * v_cl / (v_cl - v_or)
    r = v_cl ** 2 / p
    return RCDClamp(v_cl, p, r, 1.0 / (ripple * r * f_sw), v_in_max + v_cl)


def clamp_voltage(l_lk: float, i_pk: float, f_sw: float, v_or: float, r: float) -> float:
    """Clamp voltage reached with a given resistor: positive root of V² − V_OR·V − R·E·f = 0."""
    e = 0.5 * l_lk * i_pk ** 2
    return 0.5 * (v_or + math.sqrt(v_or ** 2 + 4.0 * r * e * f_sw))


# --------------------------------------------------------------------------- output side
@dataclass(frozen=True)
class OutputCapacitor:
    c_min: float        # minimum effective capacitance (F)
    esr_max: float      # maximum ESR (Ω)
    i_rms: float        # RMS ripple current (A)


def capacitor_charge(op: OperatingPoint, f_sw: float, points: int = 20000) -> float:
    """Charge the output capacitor gives and takes back each period (C).

    It is the charge of the rectifier current above I_out, on the secondary
    waveform scaled to an average of I_out. In CCM, when the secondary current
    stays above I_out, it reduces to I_out·D·T; in DCM the capacitor also feeds the
    load in the tail of the rectifier current.
    """
    _, _, i_s = waveforms(op, f_sw, points)
    return float(np.mean(np.clip(op.output_scale * i_s - op.i_out, 0.0, None))) / f_sw


def output_capacitor(op: OperatingPoint, f_sw: float, dv: float,
                     esr_share: float = 0.5) -> OutputCapacitor:
    """Capacitance and ESR for a peak-to-peak ripple ``dv``.

    ``esr_share`` is the part of the ripple allotted to the ESR (small for
    ceramics). The ESR sees the step of the rectifier current, taken as n·I_pk.
    """
    c = capacitor_charge(op, f_sw) / (dv * (1.0 - esr_share))
    return OutputCapacitor(c, dv * esr_share / op.i_s_peak, op.i_cout_rms)


def rhp_zero(spec: FlybackSpec, op: OperatingPoint, n: float, l_m: float) -> float:
    """Right-half-plane zero frequency in CCM (Hz)."""
    if op.mode != "CCM":
        raise ValueError("the right-half-plane zero exists in continuous mode only")
    r_load = spec.v_out / op.i_out
    return (1.0 - op.duty) ** 2 * r_load * n ** 2 / (2.0 * math.pi * op.duty * l_m)


def spice_netlist(conv: FlybackDesign, v_in: float, l_lk: float, clamp: RCDClamp, c_out: float,
                  periods: int = 400, record_periods: int = 10, r_on: float = 0.02,
                  step: float = 5e-9) -> str:
    """Open-loop switching netlist of the design at its CCM duty cycle (for ngspice).

    The transformer is two coupled inductors (L_s = L_m/n², k = 0.9999) with the
    leakage inductance in series with the primary, an RCD clamp to the input,
    a Schottky-like rectifier and a resistive load. The output and clamp
    capacitors start charged to shorten the transient. Probes: i(vsense) is the
    primary current, i(vssense) the rectifier current, v(sw) the drain voltage and
    v(cl) − v(in) the clamp voltage. No ``.end`` and no
    ``.control`` block: use :func:`hdk.spice.run` or add them.
    """
    spec = conv.spec
    period = 1.0 / spec.f_sw
    t_on = ccm_duty(v_in, conv.v_or) * period
    return "\n".join([
        "* Flyback converter, open loop at the design duty cycle (hdk.power.flyback.spice_netlist)",
        f"Vin in 0 {v_in:.6g}",
        "Vsense in pin 0",
        f"Lp pin p1 {conv.l_m:.6g}",
        f"Ls 0 sa {conv.l_m / conv.n ** 2:.6g}",
        "K1 Lp Ls 0.9999",
        f"Llk p1 sw {l_lk:.6g}",
        "S1 sw 0 g 0 swm",
        f".model swm SW(VT=0.5 VH=0.1 RON={r_on:.6g} ROFF=1e7)",
        f"Vg g 0 PULSE(0 1 0 5n 5n {t_on - 5e-9:.6g} {period:.6g})",
        "Coss sw 0 150p",
        "Rsn sw snb 33",
        "Csn snb 0 220p",
        "Dcl sw cl dcl",
        f"Rcl cl in {clamp.r:.6g}",
        f"Ccl cl in {clamp.c:.6g}",
        "Vssense sa sd 0",
        "Do sd out dout",
        f"Cout out 0 {c_out:.6g}",
        f"Rload out 0 {spec.v_out / spec.i_out:.6g}",
        ".model dout D(IS=5u N=1.1 RS=20m)",
        ".model dcl D(IS=1n N=1.6 RS=50m)",
        f".ic v(out)={spec.v_out:.6g} v(cl)={v_in + clamp.v_clamp:.6g}",
        ".options method=gear",
        f".tran {step:.3g} {periods * period:.6g} {(periods - record_periods) * period:.6g} uic",
    ]) + "\n"


def waveforms(op: OperatingPoint, f_sw: float, points: int = 1000):
    """Ideal primary and secondary currents over one period: (t, i_p, i_s)."""
    t = np.linspace(0.0, 1.0 / f_sw, points, endpoint=False)
    x = t * f_sw
    i_p = np.where(x < op.duty, op.i_p_valley + (op.i_p_peak - op.i_p_valley) * x / op.duty, 0.0)
    y = (x - op.duty) / op.d_off
    i_s = np.where((x >= op.duty) & (y < 1.0),
                   op.i_s_peak + (op.i_s_valley - op.i_s_peak) * y, 0.0)
    return t, i_p, i_s
