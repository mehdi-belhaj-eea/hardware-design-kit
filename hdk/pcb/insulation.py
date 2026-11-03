"""Clearance and creepage on a printed board, after IEC 60664-1 (insulation coordination).

Method
------
1. Rated impulse voltage from the supply voltage line-to-neutral and the
   overvoltage category (OVC I to IV).
2. Clearance (through air) from the impulse voltage, for an inhomogeneous field
   (case A, the usual one on a board), with a minimum per pollution degree.
   Above 2000 m the clearance is multiplied by an altitude factor, because the
   breakdown voltage of air falls with pressure.
3. Creepage (along the surface) from the working voltage (RMS or DC), the
   pollution degree and the material. Altitude does not change creepage. A
   creepage distance is never smaller than the associated clearance.
4. Reinforced insulation: clearance for the next rated impulse voltage of the
   preferred series (160 % of the basic value when that value is not in the
   series), creepage doubled.

Only the cases used here are tabulated: clearance case A, creepage for printed
wiring material in pollution degrees 1 and 2 (all material groups except IIIb
for PD2), altitude up to 20 000 m. The values are transcribed from the standard
for illustration: check them against the edition you design to, together with
the product standard, which may set larger distances.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# Rated impulse voltage (V) by line-to-neutral voltage (V, up to and including) and OVC I..IV.
RATED_IMPULSE = {
    50: (330, 500, 800, 1500),
    100: (500, 800, 1500, 2500),
    150: (800, 1500, 2500, 4000),
    300: (1500, 2500, 4000, 6000),
    600: (2500, 4000, 6000, 8000),
    1000: (4000, 6000, 8000, 12000),
}
PREFERRED_IMPULSE = (330, 500, 800, 1500, 2500, 4000, 6000, 8000, 12000)

# Clearance (mm) for an inhomogeneous field (case A), up to 2000 m, by impulse voltage (kV).
CLEARANCE_CASE_A = ((0.33, 0.01), (0.40, 0.02), (0.50, 0.04), (0.60, 0.06), (0.80, 0.10),
                    (1.0, 0.15), (1.2, 0.25), (1.5, 0.5), (2.0, 1.0), (2.5, 1.5), (3.0, 2.0),
                    (4.0, 3.0), (5.0, 4.0), (6.0, 5.5), (8.0, 8.0), (10.0, 11.0), (12.0, 14.0))
MIN_CLEARANCE = {1: 0.0, 2: 0.2, 3: 0.8}       # mm, by pollution degree

# Altitude correction factor for clearances (altitude in m).
ALTITUDE_FACTOR = ((2000, 1.00), (3000, 1.14), (4000, 1.29), (5000, 1.48), (6000, 1.70),
                   (7000, 1.95), (8000, 2.25), (9000, 2.62), (10000, 3.02), (15000, 6.67),
                   (20000, 14.50))

# Creepage (mm) on printed wiring material, by working voltage (V): (PD1, PD2).
CREEPAGE_PWB = ((10, 0.025, 0.04), (12.5, 0.025, 0.04), (16, 0.025, 0.04), (20, 0.025, 0.04),
                (25, 0.025, 0.04), (32, 0.025, 0.04), (40, 0.025, 0.04), (50, 0.025, 0.04),
                (63, 0.040, 0.063), (80, 0.063, 0.10), (100, 0.10, 0.16), (125, 0.16, 0.25),
                (160, 0.25, 0.40), (200, 0.40, 0.63), (250, 0.56, 1.0), (320, 0.75, 1.6),
                (400, 1.0, 2.0), (500, 1.3, 2.5), (630, 1.8, 3.2), (800, 2.4, 4.0),
                (1000, 3.2, 5.0))


def rated_impulse_voltage(v_line_neutral: float, ovc: int) -> float:
    """Rated impulse voltage (V) for a supply voltage line-to-neutral and an OVC (1 to 4)."""
    if ovc not in (1, 2, 3, 4):
        raise ValueError("overvoltage category must be 1, 2, 3 or 4")
    for v, row in RATED_IMPULSE.items():
        if v_line_neutral <= v:
            return float(row[ovc - 1])
    raise ValueError("supply voltage above 1000 V is outside this table")


def next_preferred_impulse(v_impulse: float) -> float:
    """Next value of the preferred series above v_impulse (for reinforced insulation)."""
    for v in PREFERRED_IMPULSE:
        if v > v_impulse:
            return float(v)
    raise ValueError("no higher preferred value in the table")


def reinforced_impulse(v_impulse: float) -> float:
    """Impulse voltage for reinforced insulation: one step up the preferred series,
    or 160 % of the basic value when it is not in that series."""
    if any(abs(v_impulse - v) < 1e-9 for v in PREFERRED_IMPULSE):
        return next_preferred_impulse(v_impulse)
    return 1.6 * v_impulse


def altitude_factor(altitude_m: float) -> float:
    """Clearance multiplication factor, interpolated linearly between the table rows."""
    if altitude_m <= 2000.0:
        return 1.0
    h, f = zip(*ALTITUDE_FACTOR)
    if altitude_m > h[-1]:
        raise ValueError("altitude above 20 000 m is outside the table")
    return float(np.interp(altitude_m, h, f))


def clearance(v_impulse: float, pollution_degree: int = 2, altitude_m: float = 0.0,
              reinforced: bool = False) -> float:
    """Minimum clearance (mm), case A, using the next table row at or above the impulse voltage."""
    if pollution_degree not in MIN_CLEARANCE:
        raise ValueError("pollution degree must be 1, 2 or 3")
    if reinforced:
        v_impulse = reinforced_impulse(v_impulse)
    kv = v_impulse / 1000.0
    for v, d in CLEARANCE_CASE_A:
        if kv <= v + 1e-9:
            base = d
            break
    else:
        raise ValueError("impulse voltage above 12 kV is outside this table")
    return max(base, MIN_CLEARANCE[pollution_degree]) * altitude_factor(altitude_m)


def creepage_pwb(v_working: float, pollution_degree: int = 2, reinforced: bool = False) -> float:
    """Minimum creepage (mm) on printed wiring material, interpolated linearly between rows."""
    if pollution_degree not in (1, 2):
        raise NotImplementedError("printed wiring columns exist for pollution degrees 1 and 2 only")
    v, pd1, pd2 = zip(*CREEPAGE_PWB)
    if v_working > v[-1]:
        raise ValueError("working voltage above 1000 V is outside this table")
    column = pd1 if pollution_degree == 1 else pd2
    base = float(np.interp(max(v_working, v[0]), v, column))
    return 2.0 * base if reinforced else base


@dataclass(frozen=True)
class Spacing:
    v_impulse: float      # rated impulse voltage used (V), before any reinforced step-up
    clearance: float      # mm, altitude included
    creepage: float       # mm, at least the clearance


def spacing(v_line_neutral: float, ovc: int, v_working: float, pollution_degree: int = 2,
            altitude_m: float = 0.0, reinforced: bool = False) -> Spacing:
    """Clearance and creepage for one insulation on a printed board."""
    v_imp = rated_impulse_voltage(v_line_neutral, ovc)
    c = clearance(v_imp, pollution_degree, altitude_m, reinforced)
    s = max(creepage_pwb(v_working, pollution_degree, reinforced), c)
    return Spacing(v_imp, c, s)
