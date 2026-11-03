"""Flyback transformer (coupled inductor) design.

Turns
-----
N_p ≥ L_m·I_pk / (B_max·A_e) keeps the peak flux density below B_max. Turns are
integers, so N_p/N_s differs slightly from the ideal ratio: the converter is
redesigned with the actual ratio, which moves the duty cycle and L_m a little.

Gap
---
A gapped core gives L = F·μ0·N²·A_e / (l_g + l_e/μ_r). The fringing factor
(McLyman) F = 1 + (l_g/√A_e)·ln(2·b_w/l_g), with b_w the winding width, raises
the inductance, so the gap is found by iteration. l_g is the total gap in the
magnetic path: with a spacer under all the legs of an E core, the spacer
thickness is l_g/2.

Flux
----
B_pk = L_m·I_pk / (N_p·A_e) and ΔB = L_m·ΔI / (N_p·A_e). The core loss uses the
iGSE on the piecewise-linear flux waveform (CCM: rise during D, fall during 1 − D;
DCM: rise, fall, then flat).

Windings
--------
Strands of diameter d ≤ 2δ limit the skin effect; their number sets the current
density J = I_rms / A_cu. The copper fill factor K_u = A_cu,total / A_w must
leave room for insulation, margins and tape (about 0.3 to 0.4 on a bobbin).

The windings of a flyback never conduct together, so nothing cancels the field
of the conducting winding. With the gap in the centre leg, the window field is
zero on the outer-leg side and grows towards the centre leg. While the inner
winding conducts, the field drops to zero across its own layers and the outer
winding sees none. While the outer winding conducts, its full field crosses the
idle inner winding, which then has eddy losses although it carries no current.
Each winding gets Dowell's loss for its own layers; the inner one also gets this
idle-winding loss.

Temperature rise (McLyman): ΔT ≈ 450·(P_total / A_t)^0.826, P in W, A_t in cm².
It is a first estimate for natural convection.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

from ..power import flyback
from .cores import Core, Material
from .losses import (MU0, copper_resistivity, idle_winding_loss, igse_piecewise_linear, skin_depth,
                     winding_loss)

# Nominal conductor diameters of enamelled round wire (R20 series, IEC 60317), in mm.
R20_DIAMETERS_MM = (0.100, 0.112, 0.125, 0.140, 0.160, 0.180, 0.200, 0.224, 0.250, 0.280,
                    0.315, 0.355, 0.400, 0.450, 0.500, 0.560, 0.630, 0.710, 0.800, 0.900, 1.000)


def fringing_factor(l_g: float, core: Core) -> float:
    """McLyman's fringing factor F = 1 + (l_g/√A_e)·ln(2·b_w/l_g)."""
    if l_g <= 0.0:
        return 1.0
    return 1.0 + l_g / math.sqrt(core.ae) * math.log(2.0 * core.winding_width / l_g)


def inductance(turns: int, core: Core, l_g: float, fringing: bool = True) -> float:
    """Inductance of a winding on a gapped core (H)."""
    f = fringing_factor(l_g, core) if fringing else 1.0
    return f * MU0 * turns ** 2 * core.ae / (l_g + core.le / core.mu_r)


def gap_length(turns: int, l_m: float, core: Core, fringing: bool = True) -> tuple[float, float]:
    """Total gap length (m) and fringing factor for an inductance l_m."""
    x = MU0 * turns ** 2 * core.ae / l_m
    l_g = x - core.le / core.mu_r
    if l_g <= 0.0:
        raise ValueError("the ungapped core already gives less inductance than required")
    if not fringing:
        return l_g, 1.0
    for _ in range(200):
        new = fringing_factor(l_g, core) * x - core.le / core.mu_r
        if abs(new - l_g) < 1e-12:
            break
        l_g = new
    return l_g, fringing_factor(l_g, core)


def choose_wire(i_rms: float, f_sw: float, j_max: float, t_c: float = 100.0,
                max_d_over_skin: float = 2.0) -> tuple[float, int]:
    """Largest standard diameter not above max_d_over_skin·δ, and the number of strands for J ≤ j_max."""
    limit = max_d_over_skin * skin_depth(f_sw, t_c)
    choices = [d * 1e-3 for d in R20_DIAMETERS_MM if d * 1e-3 <= limit]
    d = choices[-1] if choices else R20_DIAMETERS_MM[0] * 1e-3
    strands = max(1, math.ceil(i_rms / (j_max * math.pi * d * d / 4.0)))
    return d, strands


def winding_layers(turns: int, strands: int, d: float, winding_width: float,
                   insulation: float = 1.1) -> tuple[int, float]:
    """Number of layers and average conductors per layer for a winding of round wires."""
    per_layer = max(1, math.floor(winding_width / (d * insulation)))
    total = turns * strands
    layers = math.ceil(total / per_layer)
    return layers, total / layers


def temperature_rise(p_total: float, core: Core) -> float:
    """McLyman's natural-convection estimate (K)."""
    return 450.0 * (p_total / (core.surface_area * 1e4)) ** 0.826


@dataclass(frozen=True)
class Winding:
    name: str
    turns: int
    strands: int
    d: float                   # strand diameter (m)
    layers: int
    conductors_per_layer: float
    copper_area: float         # copper cross-section of one turn (m²)
    r_dc: float                # DC resistance at the winding temperature (Ω)
    i_rms: float
    p_dc: float                # I_rms²·R_dc (W)
    p_ac: float                # while conducting, with skin and proximity effects (W)
    p_idle: float = 0.0        # eddy loss while the other winding conducts (W)

    @property
    def current_density(self) -> float:
        return self.i_rms / self.copper_area

    @property
    def f_r(self) -> float:
        """AC-to-DC loss ratio of the winding's own current."""
        return self.p_ac / self.p_dc

    @property
    def p_total(self) -> float:
        return self.p_ac + self.p_idle


@dataclass(frozen=True)
class TransformerDesign:
    converter: flyback.FlybackDesign   # converter redesigned with the actual turns ratio
    core: Core
    material: Material
    n_p: int
    n_s: int
    gap: float                 # total gap in the magnetic path (m)
    fringing: float
    b_peak: float              # T
    delta_b: float             # largest flux swing, peak to peak (T)
    p_core: float              # W
    primary: Winding
    secondary: Winding
    fill: float                # copper fill factor of the winding area
    t_c: float                 # winding temperature used for the copper (°C)
    inner: str = "primary"     # winding next to the centre leg (and its gap)

    @property
    def p_copper(self) -> float:
        return self.primary.p_total + self.secondary.p_total

    @property
    def p_total(self) -> float:
        return self.p_core + self.p_copper

    @property
    def delta_t(self) -> float:
        return temperature_rise(self.p_total, self.core)

    @property
    def saturation_margin(self) -> float:
        return self.material.b_sat / self.b_peak


def choose_turns(spec: flyback.FlybackSpec, core: Core, b_max: float,
                 ratio_tolerance: float = 0.1, n_s_max: int = 200):
    """Fewest total turns whose ratio is within ``ratio_tolerance`` of the ideal one and
    whose peak flux density stays below ``b_max`` once the converter is redesigned
    with that ratio. Returns (N_p, N_s, redesigned converter)."""
    n_target = flyback.turns_ratio(spec)
    best = None
    for n_s in range(1, n_s_max + 1):
        if best is not None and n_s >= best[0]:
            break
        for n_p in sorted({max(1, math.floor(n_target * n_s)), max(1, math.ceil(n_target * n_s))}):
            error = abs(n_p / n_s - n_target) / n_target
            if error > ratio_tolerance:
                continue
            conv = flyback.design(spec, n=n_p / n_s)
            if conv.l_m * conv.i_p_peak_max / (n_p * core.ae) > b_max:
                continue
            key = (n_p + n_s, error)
            if best is None or key < best[0:2]:
                best = (n_p + n_s, error, n_p, n_s, conv)
    if best is None:
        raise ValueError("no turns combination meets b_max on this core: choose a larger core")
    return best[2], best[3], best[4]


def _flux_segments(op: flyback.OperatingPoint, delta_b: float, f_sw: float):
    t = 1.0 / f_sw
    segments = [(delta_b, op.duty * t), (-delta_b, op.d_off * t)]
    rest = 1.0 - op.duty - op.d_off
    if rest > 1e-9:
        segments.append((0.0, rest * t))
    return segments


def _winding(name: str, turns: int, samples, i_rms: float, core: Core, f_sw: float,
             j_max: float, t_c: float, insulation: float) -> Winding:
    d, strands = choose_wire(i_rms, f_sw, j_max, t_c)
    area = strands * math.pi * d * d / 4.0
    r_dc = copper_resistivity(t_c) * turns * core.mlt / area
    layers, per_layer = winding_layers(turns, strands, d, core.winding_width, insulation)
    p_dc, p_ac = winding_loss(samples, f_sw, r_dc, d, per_layer, layers, core.winding_width, t_c)
    return Winding(name, turns, strands, d, layers, per_layer, area, r_dc, i_rms, p_dc, max(p_ac, p_dc))


def design_transformer(spec: flyback.FlybackSpec, core: Core, material: Material,
                       b_max: float = 0.25, j_max: float = 5e6, t_c: float = 100.0,
                       ratio_tolerance: float = 0.1, insulation: float = 1.1,
                       n_s_max: int = 200, points: int = 4000,
                       inner: str = "primary") -> TransformerDesign:
    """Turns, gap, flux, windings and losses of a flyback transformer on a given core.

    ``inner`` is the winding wound first, next to the gapped centre leg: it also
    carries the eddy loss caused by the other winding's field.
    """
    if inner not in ("primary", "secondary"):
        raise ValueError("inner must be 'primary' or 'secondary'")
    n_p, n_s, conv = choose_turns(spec, core, b_max, ratio_tolerance, n_s_max)

    gap, fr = gap_length(n_p, conv.l_m, core)
    b_peak = conv.l_m * conv.i_p_peak_max / (n_p * core.ae)

    p_core, delta_b = 0.0, 0.0
    for op in (conv.low_line, conv.high_line):
        db = conv.l_m * op.delta_i / (n_p * core.ae)
        pv = igse_piecewise_linear(material, _flux_segments(op, db, spec.f_sw), 1.0 / spec.f_sw)
        p_core = max(p_core, pv * core.ve)
        delta_b = max(delta_b, db)

    op_p = max((conv.low_line, conv.high_line), key=lambda op: op.i_p_rms)
    op_s = max((conv.low_line, conv.high_line), key=lambda op: op.i_s_rms)
    _, i_p, _ = flyback.waveforms(op_p, spec.f_sw, points)
    _, _, i_s = flyback.waveforms(op_s, spec.f_sw, points)
    primary = _winding("primary", n_p, i_p, op_p.i_p_rms, core, spec.f_sw, j_max, t_c, insulation)
    secondary = _winding("secondary", n_s, i_s, op_s.i_s_rms, core, spec.f_sw, j_max, t_c, insulation)

    def idle(w: Winding, source_samples, source_turns: int) -> Winding:
        loss = idle_winding_loss(source_samples, spec.f_sw, source_turns, w.r_dc, w.turns, w.layers,
                                 w.d, w.conductors_per_layer, core.winding_width, t_c)
        return replace(w, p_idle=loss)

    if inner == "primary":
        primary = idle(primary, i_s, n_s)
    else:
        secondary = idle(secondary, i_p, n_p)
    fill = (n_p * primary.copper_area + n_s * secondary.copper_area) / core.aw
    return TransformerDesign(conv, core, material, n_p, n_s, gap, fr, b_peak, delta_b, p_core,
                             primary, secondary, fill, t_c, inner)
