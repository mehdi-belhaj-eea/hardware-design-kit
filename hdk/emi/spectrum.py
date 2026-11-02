"""Spectrum of trapezoidal switching waveforms.

A trapezoid of amplitude A, period T = 1/f_sw, pulse width τ = D·T (at 50 %)
and equal rise/fall times t_r has harmonics of peak amplitude

    c_n = 2·A·D · |sinc(n·D)| · |sinc(n·f_sw·t_r)|,   sinc(x) = sin(πx)/(πx)

The envelope is flat up to f_1 = 1/(π·τ), falls at −20 dB/decade up to
f_2 = 1/(π·t_r), then at −40 dB/decade (C. R. Paul, *Introduction to
Electromagnetic Compatibility*).

EMI receivers are calibrated in RMS for a continuous sine, so a steady
harmonic reads the same on the peak, quasi-peak and average detectors:
compare c_n/√2 with the limit, and the *average* limit is the one that binds.
"""

from __future__ import annotations

import math

import numpy as np


def trapezoid_harmonics(amplitude: float, f_sw: float, duty: float, t_rise: float,
                        f_max: float = 30e6) -> tuple[np.ndarray, np.ndarray]:
    """Frequencies and peak amplitudes of the harmonics up to ``f_max``."""
    if not 0.0 < duty < 1.0:
        raise ValueError("duty must be between 0 and 1")
    n = np.arange(1, int(math.floor(f_max / f_sw)) + 1)
    f = n * f_sw
    c = 2.0 * amplitude * duty * np.abs(np.sinc(n * duty)) * np.abs(np.sinc(n * f_sw * t_rise))
    return f, c


def envelope_corners(f_sw: float, duty: float, t_rise: float) -> tuple[float, float]:
    """Corner frequencies f_1 = 1/(π·τ) and f_2 = 1/(π·t_r) of the envelope."""
    tau = duty / f_sw
    return 1.0 / (math.pi * tau), 1.0 / (math.pi * t_rise)


def to_rms(peak):
    """RMS value of a sinusoidal harmonic from its peak amplitude."""
    return np.asarray(peak) / math.sqrt(2.0)
