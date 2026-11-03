"""Voltage measurement with a resistive divider and an ADC.

Ratio k = R_b / (R_t + R_b). The relative sensitivity of k to the resistors is

    dk/k = (1 − k)·(dR_b/R_b − dR_t/R_t)

so with tolerance t on each resistor the worst-case ratio error is 2·(1 − k)·t,
and a temperature change ΔT adds 2·(1 − k)·TCR·ΔT (or (1 − k)·TCR_tracking·ΔT for
a matched network). High voltages are split over several top resistors to stay
within their voltage rating and creepage.
"""

from __future__ import annotations

from dataclasses import dataclass

from .budget import ErrorTerm

E96 = (1.00, 1.02, 1.05, 1.07, 1.10, 1.13, 1.15, 1.18, 1.21, 1.24, 1.27, 1.30, 1.33, 1.37,
       1.40, 1.43, 1.47, 1.50, 1.54, 1.58, 1.62, 1.65, 1.69, 1.74, 1.78, 1.82, 1.87, 1.91,
       1.96, 2.00, 2.05, 2.10, 2.15, 2.21, 2.26, 2.32, 2.37, 2.43, 2.49, 2.55, 2.61, 2.67,
       2.74, 2.80, 2.87, 2.94, 3.01, 3.09, 3.16, 3.24, 3.32, 3.40, 3.48, 3.57, 3.65, 3.74,
       3.83, 3.92, 4.02, 4.12, 4.22, 4.32, 4.42, 4.53, 4.64, 4.75, 4.87, 4.99, 5.11, 5.23,
       5.36, 5.49, 5.62, 5.76, 5.90, 6.04, 6.19, 6.34, 6.49, 6.65, 6.81, 6.98, 7.15, 7.32,
       7.50, 7.68, 7.87, 8.06, 8.25, 8.45, 8.66, 8.87, 9.09, 9.31, 9.53, 9.76)


def e96_values(min_ohm: float = 1.0, max_ohm: float = 10e6) -> list[float]:
    """All E96 values between min_ohm and max_ohm."""
    out = []
    decade = 1.0
    while decade <= max_ohm:
        out += [round(m * decade, 6) for m in E96 if min_ohm <= m * decade <= max_ohm]
        decade *= 10.0
    return out


def e96_nearest(value: float) -> float:
    return min(e96_values(), key=lambda r: abs(r / value - 1.0))


def e96_floor(value: float) -> float:
    return max(r for r in e96_values() if r <= value * (1.0 + 1e-12))


@dataclass(frozen=True)
class Divider:
    r_top_each: float
    n_top: int
    r_bottom: float

    @property
    def r_top(self) -> float:
        return self.r_top_each * self.n_top

    @property
    def ratio(self) -> float:
        return self.r_bottom / (self.r_top + self.r_bottom)

    @property
    def r_source(self) -> float:
        """Thévenin resistance seen by the ADC (Ω)."""
        return self.r_top * self.r_bottom / (self.r_top + self.r_bottom)

    def v_out(self, v_in: float) -> float:
        return v_in * self.ratio

    def current(self, v_in: float) -> float:
        return v_in / (self.r_top + self.r_bottom)

    def v_top_each(self, v_in: float) -> float:
        """Voltage across each top resistor (V)."""
        return self.current(v_in) * self.r_top_each

    def p_top_each(self, v_in: float) -> float:
        """Power in each top resistor (W)."""
        return self.current(v_in) ** 2 * self.r_top_each


def design_divider(v_max: float, v_fs: float, r_top_total: float = 1e6, n_top: int = 1,
                   headroom: float = 0.95) -> Divider:
    """Divider with standard E96 values that maps v_max to at most headroom·v_fs."""
    r_each = e96_nearest(r_top_total / n_top)
    r_top = r_each * n_top
    k_max = headroom * v_fs / v_max
    r_b = e96_floor(k_max * r_top / (1.0 - k_max))
    return Divider(r_each, n_top, r_b)


def divider_terms(div: Divider, tol: float, tcr_ppm: float, delta_t: float,
                  tcr_tracking_ppm: float | None = None) -> list[ErrorTerm]:
    """Ratio errors of the divider, relative to the reading."""
    k = div.ratio
    drift = (1.0 - k) * (tcr_tracking_ppm * 1e-6 * delta_t if tcr_tracking_ppm is not None
                         else 2.0 * tcr_ppm * 1e-6 * delta_t)
    return [ErrorTerm("divider tolerance", 2.0 * (1.0 - k) * tol, calibratable=True),
            ErrorTerm("divider drift", drift)]


def adc_terms(bits: int, v_fs: float, span: float, ref_tol: float, ref_tc_ppm: float,
              delta_t: float, gain_error: float, offset_lsb: float, inl_lsb: float,
              v_zero: float = 0.0) -> list[ErrorTerm]:
    """ADC and reference errors, relative to the signal span at the ADC input (V).

    ``v_zero`` is the ADC input at zero signal (mid-scale for a bidirectional
    chain): the ADC gain error then also shifts the zero, by gain_error·v_zero.
    The reference is assumed ratiometric with that zero level (for example, the
    amplifier reference derived from the ADC reference), so its error acts on the
    span only.
    """
    lsb = v_fs / 2 ** bits
    terms = [ErrorTerm("reference accuracy", ref_tol, calibratable=True),
             ErrorTerm("reference drift", ref_tc_ppm * 1e-6 * delta_t),
             ErrorTerm("ADC gain error", gain_error, calibratable=True),
             ErrorTerm("ADC offset", offset_lsb * lsb / span, calibratable=True),
             ErrorTerm("ADC non-linearity", inl_lsb * lsb / span),
             ErrorTerm("quantization", 0.5 * lsb / span)]
    if v_zero > 0.0:
        terms.insert(3, ErrorTerm("ADC gain error on the zero level", gain_error * v_zero / span,
                                  calibratable=True))
    return terms
