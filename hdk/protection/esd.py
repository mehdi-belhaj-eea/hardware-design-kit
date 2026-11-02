"""ESD protection of connector pins (IEC 61000-4-2 contact discharge).

The IEC 61000-4-2 generator (150 pF, 330 Ω) delivers, per kV of test voltage,
about 3.75 A at the first peak, 2 A at 30 ns and 1 A at 60 ns
(8 kV contact: 30 A, 16 A, 8 A).

On a signal line the protection diode adds capacitance. A simple rule keeps
the 10-90 % rise time 2.2·R·C below a fraction of the bit time:

    C_max = fraction / (2.2 · R_source · bit_rate)
"""

from __future__ import annotations

from dataclasses import dataclass

CONTACT_KV = {1: 2.0, 2: 4.0, 3: 6.0, 4: 8.0}
AIR_KV = {1: 2.0, 2: 4.0, 3: 8.0, 4: 15.0}


@dataclass(frozen=True)
class ContactDischarge:
    level_kv: float
    i_first_peak: float
    i_30ns: float
    i_60ns: float


def contact_discharge(level_kv: float) -> ContactDischarge:
    """Generator currents for a contact discharge at ``level_kv``."""
    return ContactDischarge(level_kv, 3.75 * level_kv, 2.0 * level_kv, 1.0 * level_kv)


def max_line_capacitance(bit_rate: float, r_source: float, fraction: float = 0.1) -> float:
    """Largest capacitance a line can take before its edges slow down too much."""
    return fraction / (2.2 * r_source * bit_rate)


@dataclass(frozen=True)
class ESDCheck:
    rating_ok: bool
    clamp_ok: bool
    capacitance_ok: bool

    @property
    def ok(self) -> bool:
        return self.rating_ok and self.clamp_ok and self.capacitance_ok


def check_device(rating_contact_kv: float, level_kv: float, v_clamp_at_16a: float,
                 v_abs_max_pin: float, c_device: float, c_max: float) -> ESDCheck:
    """Check an ESD diode against the test level, the pin rating and the line budget.

    ``v_clamp_at_16a`` is the clamping voltage at 16 A (TLP), the 30 ns current of
    an 8 kV discharge, which is the value most datasheets give.
    """
    return ESDCheck(
        rating_ok=rating_contact_kv >= level_kv,
        clamp_ok=v_clamp_at_16a <= v_abs_max_pin,
        capacitance_ok=c_device <= c_max,
    )
