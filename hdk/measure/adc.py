"""ADC front-end: resolution, sampling kick-back, sampling load, settling and anti-aliasing.

A SAR ADC connects its sampling capacitor C_s to the input at each conversion.
Without a buffer, two separate conditions apply to a source of resistance R
with a filter capacitor C_f:

1. One sample: charge sharing between C_s and C_f gives an immediate error of up
   to C_s / (C_s + C_f) of the step between the input and the voltage left on
   C_s. Keeping it below ½ LSB needs C_f ≥ C_s·(2^N/½ − 1).
2. Repeated samples: each conversion takes a charge C_s·ΔV, so at the sample
   rate f_s the source supplies an average current C_s·ΔV·f_s through R. The
   input then sits below the source by a fraction x/(1 + x), x = R·C_s·f_s,
   whatever C_f is. Keeping it below ½ LSB limits f_s to about 1/(2^(N+1)·R·C_s).

Worst case: a multiplexed ADC whose previous channel left C_s at the other end of
the range (ΔV = full scale). An op-amp buffer removes both limits. Settling of an
RC to within ½ LSB of an N-bit full-scale step takes τ·ln(2^N/½) = τ·(N + 1)·ln 2.
"""

from __future__ import annotations

import math


def lsb(v_fs: float, bits: int) -> float:
    """Size of one LSB (V)."""
    return v_fs / 2 ** bits


def settling_time(tau: float, bits: int, fraction_lsb: float = 0.5) -> float:
    """Time for a full-scale step to settle within fraction_lsb·LSB (s)."""
    return tau * math.log(2 ** bits / fraction_lsb)


def kickback_error(c_sample: float, c_filter: float) -> float:
    """Worst-case charge-sharing error of one sample, relative to full scale."""
    return c_sample / (c_sample + c_filter)


def min_filter_capacitance(c_sample: float, bits: int, fraction_lsb: float = 0.5) -> float:
    """Filter capacitance that keeps the kick-back of one sample below fraction_lsb·LSB (F)."""
    return c_sample * (2 ** bits / fraction_lsb - 1.0)


def sampling_load_error(r_source: float, c_sample: float, f_sample: float) -> float:
    """Worst-case error from the average sampling current, relative to full scale."""
    x = r_source * c_sample * f_sample
    return x / (1.0 + x)


def max_sample_rate(r_source: float, c_sample: float, bits: int, fraction_lsb: float = 0.5) -> float:
    """Highest sample rate whose sampling-load error stays below fraction_lsb·LSB (Hz)."""
    e = fraction_lsb / 2 ** bits
    return e / ((1.0 - e) * r_source * c_sample)


def rc_corner(r: float, c: float) -> float:
    """Corner frequency of an RC filter (Hz)."""
    return 1.0 / (2.0 * math.pi * r * c)


def quantization_error(bits: int) -> float:
    """Maximum quantization error (±½ LSB), relative to full scale."""
    return 0.5 / 2 ** bits
