"""Core and material data used by the magnetics calculators.

A core is described by its effective parameters (A_e, l_e, V_e) and by the
winding window of its bobbin (winding area, winding width, mean length of turn).
Take them from the core and bobbin data sheets: the examples use illustrative
values.

Core losses follow the Steinmetz equation for a sinusoidal flux of peak value B:

    P_v = k · f^α · B^β   (W/m³)

The material is described by one data-sheet point (P_v at f_ref and B_ref) and
the exponents α and β, fitted on the data-sheet curves near the operating point.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Core:
    name: str
    ae: float               # effective cross-section (m²)
    le: float               # effective magnetic path length (m)
    ve: float               # effective volume (m³)
    aw: float               # winding area of the bobbin (m²)
    mlt: float              # mean length of one turn (m)
    winding_width: float    # usable winding width of the bobbin (m)
    mu_r: float = 2000.0    # relative permeability of the ungapped material

    @property
    def area_product(self) -> float:
        """A_p = A_w·A_e (m⁴)."""
        return self.aw * self.ae

    @property
    def surface_area(self) -> float:
        """Outer surface of the wound core (m²), McLyman's estimate A_t = 41.3·A_p^0.5 (cm², cm⁴)."""
        return 41.3 * math.sqrt(self.area_product * 1e8) * 1e-4


@dataclass(frozen=True)
class Material:
    name: str
    b_sat: float       # saturation flux density at the operating temperature (T)
    pv_ref: float      # core loss density at the reference point (W/m³)
    f_ref: float       # reference frequency (Hz)
    b_ref: float       # reference peak flux density, sinusoidal (T)
    alpha: float       # frequency exponent
    beta: float        # flux-density exponent

    @property
    def k(self) -> float:
        """Steinmetz coefficient k, in W/m³ for f in Hz and B in T."""
        return self.pv_ref / (self.f_ref ** self.alpha * self.b_ref ** self.beta)
