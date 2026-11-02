"""Reverse-polarity protection: series diode versus MOSFET ("ideal diode").

    Diode:   P = V_F · I
    MOSFET:  P = I² · R_DS(on)(T_J),   R_DS(on)(T_J) ≈ R_DS(on)(25 °C) · (1 + α·(T_J - 25))

α ≈ 0.004 to 0.007 /°C for silicon power MOSFETs; take the real value from the
datasheet curve when you have it.
"""

from __future__ import annotations

from dataclasses import dataclass


def rds_on_at(rds_on_25c: float, t_j: float, alpha: float = 0.006) -> float:
    """On-resistance at junction temperature ``t_j`` (linear model)."""
    return rds_on_25c * (1.0 + alpha * (t_j - 25.0))


def junction_temperature(p_loss: float, rth_ja: float, t_ambient: float) -> float:
    """Steady-state junction temperature T_A + P·Rth(j-a)."""
    return t_ambient + p_loss * rth_ja


@dataclass(frozen=True)
class ReverseProtectionComparison:
    i_load: float
    diode_drop: float
    diode_loss: float
    mosfet_rds_hot: float
    mosfet_drop: float
    mosfet_loss: float

    @property
    def loss_ratio(self) -> float:
        """How many times more the diode dissipates than the MOSFET."""
        return self.diode_loss / self.mosfet_loss


def compare(i_load: float, vf_diode: float, rds_on_25c: float,
            t_j: float = 100.0, alpha: float = 0.006) -> ReverseProtectionComparison:
    """Losses and voltage drops of both solutions at the worst-case current.

    Use the highest input current, which occurs at the *minimum* bus voltage.
    """
    rds = rds_on_at(rds_on_25c, t_j, alpha)
    return ReverseProtectionComparison(
        i_load=i_load,
        diode_drop=vf_diode,
        diode_loss=vf_diode * i_load,
        mosfet_rds_hot=rds,
        mosfet_drop=rds * i_load,
        mosfet_loss=rds * i_load ** 2,
    )
