"""Current measurement with a shunt and a current-sense amplifier.

V_out = V_ref + G·R_shunt·I. For a bidirectional current, V_ref sits at mid-scale.
Errors relative to the full-scale current I_fs: shunt tolerance and drift act on
the gain; the amplifier offset V_os gives a fixed current error V_os / R_shunt,
which dominates at low currents unless it is calibrated out at zero current.
A larger shunt lowers that error but dissipates more: P = R·I_rms².
"""

from __future__ import annotations

from dataclasses import dataclass

from .budget import ErrorTerm


@dataclass(frozen=True)
class ShuntChain:
    r_shunt: float      # Ω
    gain: float         # V/V
    v_ref: float        # output at zero current (V)
    v_fs: float         # ADC full scale (V)

    def v_out(self, current: float) -> float:
        return self.v_ref + self.gain * self.r_shunt * current

    @property
    def i_max_positive(self) -> float:
        """Current that drives the output to the ADC full scale (A)."""
        return (self.v_fs - self.v_ref) / (self.gain * self.r_shunt)

    @property
    def i_max_negative(self) -> float:
        """Magnitude of the negative current that drives the output to zero (A)."""
        return self.v_ref / (self.gain * self.r_shunt)

    def power(self, i_rms: float) -> float:
        """Shunt dissipation (W)."""
        return self.r_shunt * i_rms ** 2


def shunt_terms(chain: ShuntChain, i_fs: float, tol: float, tcr_ppm: float, delta_t: float,
                v_offset: float, v_offset_drift: float, gain_error: float,
                gain_drift_ppm: float) -> list[ErrorTerm]:
    """Shunt and amplifier errors, relative to the full-scale current.

    v_offset is the input offset of the amplifier (V), v_offset_drift its drift (V/K).
    """
    i_err = 1.0 / (chain.r_shunt * i_fs)
    return [ErrorTerm("shunt tolerance", tol, calibratable=True),
            ErrorTerm("shunt drift", tcr_ppm * 1e-6 * delta_t),
            ErrorTerm("amplifier offset", v_offset * i_err, calibratable=True),
            ErrorTerm("amplifier offset drift", v_offset_drift * delta_t * i_err),
            ErrorTerm("amplifier gain error", gain_error, calibratable=True),
            ErrorTerm("amplifier gain drift", gain_drift_ppm * 1e-6 * delta_t)]
