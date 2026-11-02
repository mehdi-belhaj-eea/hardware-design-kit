"""Example 1 — input protections of a 28 VDC aircraft-style board.

All values are illustrative: they are not taken from any aircraft program.
Lightning levels are the pin-injection waveforms WF4 and WF5A at level 3, as
published for DO-160G Section 22 (V_oc / I_sc pairs). Inrush envelope, voltage
range and hold-up time are invented for the example: use your program's
requirements instead.

Run:  python examples/aero_28v_protection.py
Writes docs/example_aero_28v.md and three figures in docs/img/.
"""

from __future__ import annotations

import pathlib

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from hdk.protection import holdup, precharge, reverse, surge  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
IMG = ROOT / "docs" / "img"
IMG.mkdir(parents=True, exist_ok=True)

# ----------------------------------------------------------------- specification (illustrative)
V_NOM, V_MAX, V_MIN = 28.0, 32.0, 18.0       # bus voltages (V)
P_OUT, EFF = 150.0, 0.90                     # downstream converter
C_BUS = 220e-6                               # bulk capacitance to precharge (F)
I_PEAK_MAX = 15.0                            # allowed inrush peak (A)
V_ABS_MAX_DOWNSTREAM = 80.0                  # converter input absolute maximum (V)
HOLDUP_TIME = 20e-3                          # required hold-up (s)

report: list[str] = ["# Example 1 — 28 VDC input protections (illustrative values)", ""]
report += [f"Bus {V_NOM:.0f} V nominal ({V_MIN:.0f}–{V_MAX:.0f} V), load {P_OUT:.0f} W at η = {EFF:.2f}, "
           f"bulk capacitance {C_BUS * 1e6:.0f} µF.", ""]

# ----------------------------------------------------------------- 1. precharge
d = precharge.design_precharge(V_MAX, C_BUS, I_PEAK_MAX, bypass_fraction=0.9)
i_nom = P_OUT / EFF / V_NOM
envelope = [(0.0, 1e-3, 20.0), (1e-3, 10e-3, 8.0), (10e-3, 1.0, 2.0 * i_nom)]
rows = precharge.check_inrush_envelope(d.i_peak, d.tau, envelope)
report += [
    "## 1. Precharge (inrush limiting)", "",
    "Sized at the maximum bus voltage, where the peak current V/R is highest.", "",
    "| Quantity | Value |", "| --- | --- |",
    f"| Resistor R = V_max / I_peak | {d.r_pre:.2f} Ω |",
    f"| Time constant τ = R·C | {d.tau * 1e3:.3f} ms |",
    f"| Bypass at 90 % of V_max after | {d.t_bypass * 1e3:.3f} ms |",
    f"| Energy in R until bypass | {d.energy_resistor * 1e3:.1f} mJ |",
    f"| Average power in R until bypass | {d.p_avg_resistor:.1f} W |",
    f"| Voltage step when the bypass closes | {d.v_residual:.1f} V |", "",
    "Check against the (illustrative) inrush envelope:", "",
    "| Window | Worst current | Limit | Result |", "| --- | --- | --- | --- |",
]
for r in rows:
    report.append(f"| {r.t_start * 1e3:g}–{r.t_end * 1e3:g} ms | {r.i_worst:.2f} A | {r.i_limit:.1f} A | "
                  f"{'pass' if r.ok else 'FAIL'} |")
report += ["", "Pick a resistor rated for the pulse energy above (pulse-load or wire-wound type), "
           "and repeat the energy check for the worst case: a restart before the capacitor has discharged.", "",
           "![Precharge current and voltage](img/aero28_precharge.png)", ""]

t = np.linspace(0.0, 12e-3, 3000)
v_c, i_c = precharge.waveforms(V_MAX, d.r_pre, C_BUS, t)
fig, ax = plt.subplots(figsize=(7.0, 3.6))
ax.plot(t * 1e3, i_c, color="#c0392b", lw=2, label="inrush current")
for t0, t1, lim in envelope:
    ax.hlines(lim, t0 * 1e3, min(t1, t[-1]) * 1e3, colors="#7f8c8d", linestyles="--", lw=1.5)
ax.set_xlabel("time (ms)")
ax.set_ylabel("current (A)")
ax.set_ylim(0, 22)
ax.grid(alpha=0.3)
ax2 = ax.twinx()
ax2.plot(t * 1e3, v_c, color="#2c3e50", lw=1.5, label="bus capacitor voltage")
ax2.axhline(0.9 * V_MAX, color="#2c3e50", lw=0.8, ls=":")
ax2.set_ylabel("voltage (V)")
ax.set_title(f"Precharge through {d.r_pre:.2f} Ω into {C_BUS * 1e6:.0f} µF (dashed: limit envelope)")
fig.legend(loc="upper right", bbox_to_anchor=(0.86, 0.86), fontsize=8)
fig.tight_layout()
fig.savefig(IMG / "aero28_precharge.png", dpi=150)
plt.close(fig)

# ----------------------------------------------------------------- 2. reverse polarity
i_max = P_OUT / EFF / V_MIN
rp = reverse.compare(i_max, vf_diode=0.55, rds_on_25c=4e-3, t_j=100.0)
report += [
    "## 2. Reverse-polarity protection", "",
    f"Worst-case input current at {V_MIN:.0f} V: {i_max:.2f} A.", "",
    "| Solution | Drop | Loss |", "| --- | --- | --- |",
    f"| Schottky diode, V_F = 0.55 V | {rp.diode_drop:.2f} V | {rp.diode_loss:.2f} W |",
    f"| MOSFET 4 mΩ at 25 °C ({rp.mosfet_rds_hot * 1e3:.1f} mΩ at 100 °C) | {rp.mosfet_drop * 1e3:.0f} mV | "
    f"{rp.mosfet_loss:.2f} W |", "",
    f"The MOSFET dissipates {rp.loss_ratio:.0f} times less and keeps more input voltage for the converter.", "",
]

# ----------------------------------------------------------------- 3. lightning (pin injection)
tvs = surge.TVS("1500 W TVS, 36 V stand-off (example datasheet values)",
                v_wm=36.0, v_br=40.0, v_c=58.1, i_pp=25.8, p_pp=1500.0)
cases = [("WF4", 300.0, 60.0, 6.4e-6, 69e-6), ("WF5A", 300.0, 300.0, 40e-6, 120e-6)]
report += [
    "## 3. Lightning transients (pin injection, level 3)", "",
    f"Candidate: {tvs.name}: V_BR = {tvs.v_br:.0f} V, V_C = {tvs.v_c} V at {tvs.i_pp} A, "
    f"so R_d = {tvs.r_dyn:.2f} Ω. Downstream absolute maximum: {V_ABS_MAX_DOWNSTREAM:.0f} V.", "",
    "| Waveform | Source | Peak current | Clamped voltage | Peak power | Estimated rating | Result |",
    "| --- | --- | --- | --- | --- | --- | --- |",
]
fig, axes = plt.subplots(1, 2, figsize=(8.5, 3.4))
for name, voc, isc, tp, th in cases:
    w = surge.double_exponential(tp, th)
    rs = voc / isc
    res = surge.clamp_response(tvs, voc, rs, w)
    chk = surge.check(tvs, res, t_pulse=th, v_operating_max=V_MAX, v_abs_max_downstream=V_ABS_MAX_DOWNSTREAM)
    report.append(f"| {name} {tp * 1e6:g}/{th * 1e6:g} µs | {voc:.0f} V / {isc:.0f} A ({rs:g} Ω) | "
                  f"{res.i_peak:.0f} A | {res.v_peak:.0f} V | {res.p_peak / 1e3:.1f} kW | "
                  f"{chk.p_allowed / 1e3:.1f} kW | {'pass' if chk.ok else 'FAIL'} |")
    if not chk.ok:
        req = surge.required_rating(voc, rs, V_ABS_MAX_DOWNSTREAM, tvs.v_br_total)
        failed = (name, req)
    axes[0].plot(res.t * 1e6, res.i, lw=2, label=name)
    axes[1].plot(res.t * 1e6, res.v, lw=2, label=name)
axes[0].set_xlabel("time (µs)")
axes[0].set_ylabel("TVS current (A)")
axes[1].set_xlabel("time (µs)")
axes[1].set_ylabel("protected node (V)")
axes[1].axhline(V_ABS_MAX_DOWNSTREAM, color="#c0392b", ls="--", lw=1, label="abs. max")
for a in axes:
    a.set_xlim(0, 300)
    a.grid(alpha=0.3)
    a.legend(fontsize=8)
fig.suptitle("1500 W TVS under level-3 pin injection")
fig.tight_layout()
fig.savefig(IMG / "aero28_lightning.png", dpi=150)
plt.close(fig)
name, req = failed
report += [
    "", f"The 1500 W part passes WF4 but not {name}: the 1 Ω source pushes far more current. "
    f"To stay below {V_ABS_MAX_DOWNSTREAM:.0f} V, the protection must carry {req.i_peak:.0f} A "
    f"({req.p_peak / 1e3:.1f} kW peak) with a dynamic resistance of at most {req.r_dyn_max * 1e3:.0f} mΩ: "
    "a high-power TVS (or several in parallel, matched) is needed. "
    "WF5A drives the choice on power inputs fed by long harnesses.", "",
    "The pulse-power rating is a first estimate (P ∝ t^-1/2 from the 10/1000 µs value); "
    "confirm with the datasheet derating curve.", "",
    "![TVS current and clamped voltage](img/aero28_lightning.png)", "",
]

# ----------------------------------------------------------------- 4. hold-up
e = holdup.energy([(P_OUT, HOLDUP_TIME)], EFF)
c_direct = holdup.capacitance_nominal(holdup.capacitance_min(e, V_NOM, V_MIN))
c_boost = holdup.capacitance_nominal(holdup.capacitance_min(e, 60.0, 20.0))
report += [
    "## 4. Hold-up", "",
    f"Energy for {HOLDUP_TIME * 1e3:.0f} ms at {P_OUT:.0f} W (η = {EFF}): {e:.2f} J.", "",
    "| Storage | Voltage window | Nominal capacitance (−20 % tolerance, −10 % ageing) |",
    "| --- | --- | --- |",
    f"| On the 28 V bus | {V_NOM:.0f} → {V_MIN:.0f} V | {c_direct * 1e3:.1f} mF |",
    f"| Boosted storage bus | 60 → 20 V | {c_boost * 1e3:.2f} mF |", "",
    f"Storing at 60 V divides the capacitance by {c_direct / c_boost:.1f}, because the usable energy grows with V².", "",
]

(ROOT / "docs" / "example_aero_28v.md").write_text("\n".join(report), encoding="utf-8")
print("\n".join(report))
