"""Core and copper losses for non-sinusoidal waveforms.

Core loss: improved generalised Steinmetz equation (iGSE)
---------------------------------------------------------
For any periodic flux waveform with peak-to-peak swing ΔB (Venkatachalam et al., 2002):

    P_v = (1/T) ∫ k_i · |dB/dt|^α · ΔB^(β−α) dt
    k_i = k / ((2π)^(α−1) · ∫_0^2π |cos θ|^α · 2^(β−α) dθ)

It reduces to the Steinmetz equation for a sine. For a triangular flux that
rises during D·T and falls during (1 − D)·T (flyback in CCM):

    P_v = k_i · ΔB^β · f^α · (D^(1−α) + (1 − D)^(1−α))

Copper: skin effect and Dowell's AC resistance
----------------------------------------------
Skin depth δ = √(ρ / (π·f·μ0)). For a winding portion of p layers of round
wires of diameter d (Dowell, 1966), with the equivalent foil thickness
h = (√π/2)·d, the layer porosity η = N_l·h / b_w and Δ = (h/δ)·√η:

    F_R = Δ·[ (sinh 2Δ + sin 2Δ)/(cosh 2Δ − cos 2Δ)
              + (2(p² − 1)/3)·(sinh Δ − sin Δ)/(cosh Δ + cos Δ) ]

For a non-sinusoidal current, each harmonic h of rms value I_h sees F_R(h·f):
P = I_dc²·R_dc + Σ I_h²·R_dc·F_R(h·f).

A winding that carries no current but sits in the field H of another winding
(equal on both faces of each layer) still has eddy losses. Per layer, relative
to the DC loss of the current that would create a field step H in that layer,
the factor is 2·Δ·(sinh Δ − sin Δ)/(cosh Δ + cos Δ) (Dowell's layer formula with
H1 = H2). For an idle winding A of p_A layers and N_A turns in the field of a
winding B of N_B turns carrying i_B:

    P = Σ_h R_dc,A · p_A² · (N_B/N_A)² · I_B,h² · 2·Δ_h·(sinh Δ_h − sin Δ_h)/(cosh Δ_h + cos Δ_h)
"""

from __future__ import annotations

import math

import numpy as np
from scipy.integrate import quad

from .cores import Material

MU0 = 4e-7 * math.pi
RHO_CU_20C = 1.72e-8        # Ω·m
ALPHA_CU = 0.00393          # 1/K


def copper_resistivity(t_c: float = 20.0) -> float:
    """Copper resistivity at temperature t_c (°C)."""
    return RHO_CU_20C * (1.0 + ALPHA_CU * (t_c - 20.0))


def skin_depth(f: float, t_c: float = 20.0) -> float:
    """Skin depth in copper (m)."""
    return math.sqrt(copper_resistivity(t_c) / (math.pi * f * MU0))


# --------------------------------------------------------------------------- core loss
def steinmetz(material: Material, f: float, b_peak: float) -> float:
    """Core loss density for a sinusoidal flux of peak value b_peak (W/m³)."""
    return material.k * f ** material.alpha * b_peak ** material.beta


def igse_ki(material: Material) -> float:
    """Coefficient k_i of the iGSE."""
    a, b = material.alpha, material.beta
    integral, _ = quad(lambda th: abs(math.cos(th)) ** a, 0.0, 2.0 * math.pi, limit=200)
    return material.k / ((2.0 * math.pi) ** (a - 1.0) * integral * 2.0 ** (b - a))


def igse_piecewise_linear(material: Material, segments, period: float) -> float:
    """Core loss density for a piecewise-linear flux waveform (W/m³).

    ``segments`` is a list of ``(delta_b, duration)`` that covers one period;
    flat segments (delta_b = 0) add no loss.
    """
    b = np.cumsum([0.0] + [s[0] for s in segments])
    b_pp = float(b.max() - b.min())
    a = material.alpha
    total = sum(abs(db / dt) ** a * dt for db, dt in segments if dt > 0.0 and db != 0.0)
    return igse_ki(material) * b_pp ** (material.beta - a) * total / period


def igse_triangular(material: Material, f: float, delta_b: float, duty: float) -> float:
    """Core loss density for a triangular flux of swing delta_b, rising during duty·T (W/m³)."""
    t = 1.0 / f
    return igse_piecewise_linear(material, [(delta_b, duty * t), (-delta_b, (1.0 - duty) * t)], t)


# --------------------------------------------------------------------------- copper loss
def dowell_fr(delta: float, layers: float) -> float:
    """Dowell's AC resistance factor R_ac/R_dc for Δ = h/δ·√η and p layers."""
    if delta <= 0.0:
        return 1.0
    if delta < 1e-3:
        return 1.0 + (5.0 * layers ** 2 - 1.0) / 45.0 * delta ** 4   # series expansion
    x = 2.0 * delta
    first = (math.sinh(x) + math.sin(x)) / (math.cosh(x) - math.cos(x))
    second = (math.sinh(delta) - math.sin(delta)) / (math.cosh(delta) + math.cos(delta))
    return delta * (first + 2.0 * (layers ** 2 - 1.0) / 3.0 * second)


def round_wire_delta(d: float, conductors_per_layer: float, winding_width: float,
                     f: float, t_c: float = 20.0) -> float:
    """Dowell's Δ for a layer of round wires (equivalent foil and porosity)."""
    h = math.sqrt(math.pi) / 2.0 * d
    porosity = min(conductors_per_layer * h / winding_width, 1.0)
    return h / skin_depth(f, t_c) * math.sqrt(porosity)


def harmonic_rms(samples, harmonics: int = 60):
    """DC value and RMS value of each harmonic of a waveform sampled uniformly over one period."""
    x = np.asarray(samples, dtype=float)
    c = np.fft.rfft(x) / x.size
    n = min(harmonics, c.size - 1)
    rms = np.sqrt(2.0) * np.abs(c[1:n + 1])
    if x.size % 2 == 0 and n == c.size - 1:
        rms[-1] = abs(c[-1])      # the Nyquist bin of an even-length record is not mirrored
    return float(c[0].real), rms


def winding_loss(samples, f: float, r_dc: float, d: float, conductors_per_layer: float,
                 layers: float, winding_width: float, t_c: float = 20.0,
                 harmonics: int = 200) -> tuple[float, float]:
    """(DC-only loss, total loss with skin and proximity effects) of a winding (W)."""
    i_dc, i_h = harmonic_rms(samples, harmonics)
    p_rms_dc = r_dc * float(np.mean(np.asarray(samples, dtype=float) ** 2))
    total = r_dc * i_dc ** 2
    for h, i in enumerate(i_h, start=1):
        delta = round_wire_delta(d, conductors_per_layer, winding_width, h * f, t_c)
        total += r_dc * dowell_fr(delta, layers) * i ** 2
    return p_rms_dc, total


def idle_layer_factor(delta: float) -> float:
    """Eddy loss of a layer with no net current between equal fields, relative to the
    DC loss of the current that creates the same field step: 2·Δ·(sinh Δ − sin Δ)/(cosh Δ + cos Δ)."""
    if delta <= 0.0:
        return 0.0
    if delta < 1e-3:
        return delta ** 4 / 3.0   # series expansion
    return 2.0 * delta * (math.sinh(delta) - math.sin(delta)) / (math.cosh(delta) + math.cos(delta))


def idle_winding_loss(source_samples, f: float, source_turns: int, r_dc: float, turns: int,
                      layers: float, d: float, conductors_per_layer: float, winding_width: float,
                      t_c: float = 20.0, harmonics: int = 200) -> float:
    """Eddy loss (W) of a winding that carries no current while it sits in the field of
    another winding of ``source_turns`` turns carrying ``source_samples`` (one period).

    The field is taken as uniform across the idle winding, as for the winding next to
    the gap of a flyback while the other winding conducts. The DC component adds no loss.
    """
    _, i_h = harmonic_rms(source_samples, harmonics)
    scale = r_dc * layers ** 2 * (source_turns / turns) ** 2
    total = 0.0
    for h, i in enumerate(i_h, start=1):
        delta = round_wire_delta(d, conductors_per_layer, winding_width, h * f, t_c)
        total += scale * idle_layer_factor(delta) * i ** 2
    return total
