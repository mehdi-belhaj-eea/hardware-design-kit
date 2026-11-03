"""Example 5 — PCB rules: trace widths, vias and insulation distances (illustrative values).

1. Trace widths after IPC-2221 for a few currents, copper weights and layers;
   vias for the same currents.
2. Clearance and creepage after IEC 60664-1 for a 400 V DC link behind a PFC
   supplied from a single-phase 230 V network (overvoltage category II,
   pollution degree 2), basic and reinforced, and how the clearance grows with
   altitude.

Run:  python examples/pcb_rules.py
Writes docs/example_pcb_rules.md and docs/img/pcb_clearance_altitude.png.
"""

from __future__ import annotations

import math
import pathlib

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from hdk.pcb import insulation as ins  # noqa: E402
from hdk.pcb import traces  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
IMG = ROOT / "docs" / "img"
IMG.mkdir(parents=True, exist_ok=True)
OZ = traces.COPPER_OZ

report = ["# Example 5 — PCB rules: traces, vias and insulation (illustrative values)", ""]

# ----------------------------------------------------------------- 1. traces and vias
currents = (1.0, 2.0, 5.0, 10.0)
report += ["## 1. Trace width (IPC-2221)", "",
           "Minimum width for a temperature rise of 10 °C and 20 °C above the board.", "",
           "| Current | 1 oz external, 10 °C | 1 oz external, 20 °C | 2 oz external, 10 °C | "
           "1 oz internal, 10 °C | Ø0.3 mm vias needed, 10 °C |",
           "| --- | --- | --- | --- | --- | --- |"]
via_i = traces.via_current(0.3e-3, 25e-6, 10.0)
beyond = False
for i in currents:
    w = [traces.ipc2221_width(i, OZ, 10.0), traces.ipc2221_width(i, OZ, 20.0),
         traces.ipc2221_width(i, 2 * OZ, 10.0), traces.ipc2221_width(i, OZ, 10.0, external=False)]
    cells = []
    for x in w:
        mark = "" if traces.in_ipc2221_range(x, i) else " †"
        beyond = beyond or bool(mark)
        cells.append(f"{x * 1e3:.2f} mm{mark}")
    report.append(f"| {i:g} A | " + " | ".join(cells) + f" | {math.ceil(i / via_i)} |")
if beyond:
    report += ["", "† Wider than 400 mil (10.2 mm): outside the range of the IPC-2221 fit, an extrapolation."]
w5 = traces.ipc2221_width(5.0, OZ, 10.0)
r5 = traces.trace_resistance(w5, OZ, 0.05, t_c=60.0)
report += ["",
           f"One via drilled Ø0.3 mm with 25 µm of plating (grown inside the hole) carries about "
           f"{via_i:.2f} A for a 10 °C rise. A 5 A trace "
           f"of {w5 * 1e3:.1f} mm and 50 mm long has {r5 * 1e3:.1f} mΩ at 60 °C: {5 * r5 * 1e3:.0f} mV and "
           f"{25 * r5 * 1e3:.0f} mW.", "",
           "IPC-2221 is conservative for internal layers. IPC-2152, its successor, shows that a buried trace "
           "in a real board, with planes nearby, runs nearly as cool as an external one: use it, or a "
           "thermal simulation, when the internal widths above do not fit.", ""]

# ----------------------------------------------------------------- 2. insulation
V_LN, OVC, PD, V_WORK = 230.0, 2, 2, 400.0
v_imp = ins.rated_impulse_voltage(V_LN, OVC)
altitudes = (0.0, 2000.0, 3000.0, 4000.0, 5000.0)
report += [
    "## 2. Clearance and creepage (IEC 60664-1)", "",
    f"Converter supplied from a single-phase {V_LN:.0f} V network through a PFC stage that regulates its DC link "
    f"at {V_WORK:.0f} V: line-to-neutral {V_LN:.0f} V, overvoltage category {['I', 'II', 'III', 'IV'][OVC - 1]}, "
    f"so a rated impulse voltage of {v_imp / 1000:.1f} kV. Pollution degree {PD} (non-conductive pollution, "
    f"occasional condensation). Working voltage across the barrier: the {V_WORK:.0f} V DC link. The board is "
    "the insulating material (printed wiring columns). A three-phase 400 V supply would give a DC link "
    "around 565 V, and longer creepage distances.", "",
    "| Altitude | Basic: clearance / creepage | Reinforced (DC link to SELV control): clearance / creepage |",
    "| --- | --- | --- |",
]
for h in altitudes:
    b = ins.spacing(V_LN, OVC, V_WORK, PD, altitude_m=h)
    r = ins.spacing(V_LN, OVC, V_WORK, PD, altitude_m=h, reinforced=True)
    report.append(f"| {h:.0f} m | {b.clearance:.2f} / {b.creepage:.2f} mm | {r.clearance:.2f} / {r.creepage:.2f} mm |")
report += [
    "",
    "Reinforced insulation takes the clearance of the next rated impulse voltage (4 kV) and doubles the "
    "creepage. Creepage depends on the working voltage and does not change with altitude; clearance does, "
    "and once it exceeds the creepage it sets both, since a surface path can never be shorter than the "
    "air gap it bridges.", "",
    "Up to 2000 m the tables apply directly. Above, the factor grows quickly: at 10 000 m it is "
    f"{ins.altitude_factor(10000):.2f}. For equipment in an unpressurised bay, a conformal coating, potting "
    "or a dedicated analysis (partial discharge, Paschen curve) usually replaces the air distances.", "",
    "These distances are a minimum from the basic safety standard: the product standard (IEC 62477-1 for "
    "power converters, IEC 61010-1, IEC 62368-1...) can require more, and the values here must be checked "
    "against the edition of the standard in force.", "",
    "![Reinforced clearance versus altitude](img/pcb_clearance_altitude.png)", "",
]

h = np.linspace(0.0, 15000.0, 301)
cl_b = [ins.spacing(V_LN, OVC, V_WORK, PD, altitude_m=x).clearance for x in h]
cl_r = [ins.spacing(V_LN, OVC, V_WORK, PD, altitude_m=x, reinforced=True).clearance for x in h]
fig, ax = plt.subplots(figsize=(7.0, 3.6))
ax.plot(h / 1000, cl_b, color="#2c3e50", lw=2, label="clearance, basic (2.5 kV)")
ax.plot(h / 1000, cl_r, color="#c0392b", lw=2, label="clearance, reinforced (4 kV)")
ax.axhline(ins.creepage_pwb(V_WORK, PD), color="#2c3e50", ls="--", lw=1, label="creepage, basic (400 V)")
ax.axhline(ins.creepage_pwb(V_WORK, PD, reinforced=True), color="#c0392b", ls="--", lw=1,
           label="creepage, reinforced (400 V)")
ax.axvline(2.0, color="#7f8c8d", ls=":", lw=1)
ax.text(2.15, 12.0, "tables valid\nup to 2000 m", fontsize=8, color="#7f8c8d", va="top")
ax.set_xlabel("altitude (km)")
ax.set_ylabel("minimum distance (mm)")
ax.set_ylim(0, 22)
ax.set_title("Clearance grows with altitude, creepage does not")
ax.grid(alpha=0.3)
ax.legend(fontsize=8, loc="upper left")
fig.tight_layout()
fig.savefig(IMG / "pcb_clearance_altitude.png", dpi=150)
plt.close(fig)

(ROOT / "docs" / "example_pcb_rules.md").write_text("\n".join(report), encoding="utf-8")
print("\n".join(report))
