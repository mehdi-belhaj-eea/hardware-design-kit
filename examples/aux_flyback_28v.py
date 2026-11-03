"""Example 3 — isolated 15 V auxiliary flyback supplied from a 28 V bus.

All values are illustrative. The core is an EFD20-class ferrite: its effective
parameters follow the usual data-sheet values for that size, the bobbin values
(winding area, width, mean turn) are assumed. The material is an N87-class
ferrite described by one data-sheet loss point and assumed Steinmetz exponents.

If ngspice is installed, the design is also simulated in open loop and the
waveforms are compared with the model.

Run:  python examples/aux_flyback_28v.py
Writes docs/example_flyback_28v.md and docs/img/flyback_waveforms.png.
"""

from __future__ import annotations

import pathlib
from dataclasses import replace

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from hdk import spice  # noqa: E402
from hdk.magnetics import cores  # noqa: E402
from hdk.magnetics import transformer as tr  # noqa: E402
from hdk.power import flyback as fb  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
IMG = ROOT / "docs" / "img"
IMG.mkdir(parents=True, exist_ok=True)
_trapezoid = getattr(np, "trapezoid", None) or np.trapz

# ----------------------------------------------------------------- specification (illustrative)
SPEC = fb.FlybackSpec(v_in_min=18.0, v_in_max=32.0, v_out=15.0, i_out=1.0, f_sw=200e3,
                      efficiency=0.85, v_f=0.5, d_max=0.45, k_rp=0.5)
CORE = cores.Core("EFD20-class", ae=31e-6, le=47e-3, ve=1460e-9,
                  aw=25e-6, mlt=34e-3, winding_width=12.5e-3, mu_r=2000.0)
FERRITE = cores.Material("N87-class ferrite at 100 °C", b_sat=0.39, pv_ref=375e3, f_ref=100e3,
                         b_ref=0.2, alpha=1.4, beta=2.6)
B_MAX, J_MAX = 0.25, 5e6
LEAKAGE = 0.015               # leakage inductance as a fraction of L_m
K_CLAMP = 2.0                 # clamp voltage = K_CLAMP · V_OR
C_OUT = 22e-6                 # effective output capacitance (F)
DV_OUT = 0.15                 # allowed output ripple (V, peak to peak)

t = tr.design_transformer(SPEC, CORE, FERRITE, b_max=B_MAX, j_max=J_MAX)
conv = t.converter
low, high = conv.low_line, conv.high_line
l_lk = LEAKAGE * conv.l_m
clamp = fb.rcd_clamp(l_lk, conv.i_p_peak_max, SPEC.f_sw, conv.v_or, SPEC.v_in_max, k_clamp=K_CLAMP)
cap = fb.output_capacitor(low, SPEC.f_sw, DV_OUT, esr_share=0.2)
f_rhpz = fb.rhp_zero(SPEC, low, conv.n, conv.l_m)

report = ["# Example 3 — 15 V auxiliary flyback from a 28 V bus (illustrative values)", ""]
report += [f"Input {SPEC.v_in_min:.0f}–{SPEC.v_in_max:.0f} V, output {SPEC.v_out:.0f} V / {SPEC.i_out:.0f} A "
           f"({SPEC.p_out:.0f} W, isolated), {SPEC.f_sw / 1e3:.0f} kHz. Sizing assumptions: efficiency "
           f"{100 * (SPEC.efficiency):.0f} %, rectifier drop {SPEC.v_f} V, duty cycle {SPEC.d_max} at minimum input, "
           f"ripple ratio K_RP = {SPEC.k_rp} (continuous mode at full load).", ""]

# ----------------------------------------------------------------- 1. turns and inductance
report += [
    "## 1. Turns ratio and magnetising inductance", "",
    f"The ideal ratio is n = N_p/N_s = {fb.turns_ratio(SPEC):.3f}. With whole turns, the fewest that keep the "
    f"peak flux density below {B_MAX} T are N_p : N_s = {t.n_p} : {t.n_s}, so the converter is redesigned "
    f"with n = {conv.n:.3f}: V_OR = {conv.v_or:.1f} V and L_m = {conv.l_m * 1e6:.1f} µH.", "",
    f"| Operating point | {low.v_in:.0f} V, full load | {high.v_in:.0f} V, full load |",
    "| --- | --- | --- |",
    f"| Mode | {low.mode} | {high.mode} |",
    f"| Duty cycle | {low.duty:.3f} | {high.duty:.3f} |",
    f"| Primary current: peak / valley / RMS | {low.i_p_peak:.2f} / {low.i_p_valley:.2f} / {low.i_p_rms:.2f} A | "
    f"{high.i_p_peak:.2f} / {high.i_p_valley:.2f} / {high.i_p_rms:.2f} A |",
    f"| Secondary current: peak / RMS | {low.i_s_peak:.2f} / {low.i_s_rms:.2f} A | "
    f"{high.i_s_peak:.2f} / {high.i_s_rms:.2f} A |",
    f"| Output capacitor RMS current | {low.i_cout_rms:.2f} A | {high.i_cout_rms:.2f} A |", "",
]

# ----------------------------------------------------------------- 2. stresses and clamp
report += [
    "## 2. Voltage stresses and RCD clamp", "",
    f"Leakage inductance assumed at {100 * (LEAKAGE):.1f} % of L_m ({l_lk * 1e6:.2f} µH). Clamp voltage "
    f"{K_CLAMP:g} × V_OR = {clamp.v_clamp:.1f} V above the input.", "",
    "| Quantity | Value |", "| --- | --- |",
    f"| Drain voltage before the leakage spike (V_in,max + V_OR) | {conv.v_ds_off:.1f} V |",
    f"| Drain peak with the clamp (V_in,max + V_clamp) | {clamp.v_ds_peak:.1f} V |",
    f"| Rectifier reverse voltage (V_out + V_in,max/n) | {conv.v_diode_reverse:.1f} V |",
    f"| Clamp power | {clamp.p_clamp:.2f} W |",
    f"| Clamp resistor / capacitor (10 % ripple) | {clamp.r / 1e3:.2f} kΩ / {clamp.c * 1e9:.0f} nF |", "",
    f"A 100 V MOSFET keeps {100 * (100 / clamp.v_ds_peak - 1):.0f} % headroom over the clamped drain peak. The "
    f"rectifier sees {conv.v_diode_reverse:.0f} V plus its turn-off ringing, so a 100 V Schottky is the safe "
    f"choice. The clamp dissipates {100 * (clamp.p_clamp / SPEC.p_out):.0f} % of the output power: interleaved "
    "windings, which lower the leakage, pay back directly here.", "",
]

# ----------------------------------------------------------------- 3. transformer
p, s = t.primary, t.secondary
report += [
    f"## 3. Transformer on an {CORE.name} core", "",
    f"Core A_e = {CORE.ae * 1e6:.0f} mm², l_e = {CORE.le * 1e3:.0f} mm, V_e = {CORE.ve * 1e9:.0f} mm³; "
    f"bobbin (assumed): winding area {CORE.aw * 1e6:.0f} mm², width {CORE.winding_width * 1e3:.1f} mm, "
    f"mean turn {CORE.mlt * 1e3:.0f} mm. Material: {FERRITE.name}, {FERRITE.pv_ref / 1e3:.0f} kW/m³ at "
    f"{FERRITE.f_ref / 1e3:.0f} kHz and {FERRITE.b_ref * 1e3:.0f} mT, α = {FERRITE.alpha}, β = {FERRITE.beta}.", "",
    "| Quantity | Value |", "| --- | --- |",
    f"| Turns N_p : N_s | {t.n_p} : {t.n_s} |",
    f"| Total air gap (fringing factor {t.fringing:.2f} included) | {t.gap * 1e3:.2f} mm |",
    f"| Peak flux density | {t.b_peak:.3f} T (saturation {FERRITE.b_sat} T: margin × {t.saturation_margin:.1f}) |",
    f"| Largest flux swing (peak to peak) | {t.delta_b:.3f} T |",
    f"| Core loss (iGSE, triangular flux) | {t.p_core:.2f} W |",
    f"| Primary (inner): {p.strands} × Ø{p.d * 1e3:.3f} mm, {p.layers} layers | J = {p.current_density / 1e6:.1f} "
    f"A/mm², R_dc = {p.r_dc * 1e3:.0f} mΩ at {t.t_c:.0f} °C; loss {p.p_ac:.2f} W from its own current "
    f"(×{p.f_r:.1f} the DC loss) + {p.p_idle:.2f} W induced by the secondary field |",
    f"| Secondary (outer): {s.strands} × Ø{s.d * 1e3:.3f} mm, {s.layers} layers | J = "
    f"{s.current_density / 1e6:.1f} A/mm², R_dc = {s.r_dc * 1e3:.0f} mΩ; loss {s.p_ac:.2f} W "
    f"(×{s.f_r:.1f} the DC loss) |",
    f"| Copper fill factor | {100 * (t.fill):.0f} % |",
    f"| Total loss and temperature rise (estimate) | {t.p_core:.2f} W core + {t.p_copper:.2f} W copper = "
    f"{t.p_total:.2f} W, about {t.delta_t:.0f} K |", "",
    "Strands thinner than two skin depths keep the skin effect low, but the harmonics of the trapezoidal "
    "currents and the proximity effect between layers still multiply the copper loss: Dowell's factor is "
    "applied harmonic by harmonic. The windings of a flyback never conduct together, so nothing cancels "
    "the field of the conducting one: while the secondary conducts, its full field crosses the primary "
    f"wound next to the gapped centre leg, which loses {p.p_idle:.2f} W although it carries no current. "
    "Interleaving (half primary, secondary, half primary) cuts this loss and the leakage inductance. "
    "With a spacer under all three legs, the spacer is half the total gap.", "",
]

# ----------------------------------------------------------------- 4. output capacitor and loop
report += [
    "## 4. Output capacitor and control loop", "",
    f"For {DV_OUT * 1e3:.0f} mV of ripple: effective capacitance ≥ {cap.c_min * 1e6:.0f} µF (ceramic, after DC-bias "
    f"derating), ESR ≤ {cap.esr_max * 1e3:.0f} mΩ, RMS current {cap.i_rms:.2f} A.", "",
    f"Right-half-plane zero at {SPEC.v_in_min:.0f} V and full load: {f_rhpz / 1e3:.0f} kHz. "
    f"Cross the loop over below about {f_rhpz / 5e3:.0f} kHz.", "",
]

# ----------------------------------------------------------------- 5. ngspice check
fig_path = IMG / "flyback_waveforms.png"
if spice.available():
    rows = []
    sims = {}
    for v_in in (SPEC.v_in_min, SPEC.v_in_max):
        data = spice.run(fb.spice_netlist(conv, v_in, l_lk, clamp, C_OUT),
                         ["i(vsense)", "i(vssense)", "v(sw)", "v(out)", "v(cl)"])
        time, i_p, i_s, v_sw, v_out, v_cl = data.T
        span = time[-1] - time[0]
        mean = lambda y: _trapezoid(y, time) / span  # noqa: E731
        i_in = mean(i_p) - (mean(v_cl) - v_in) / clamp.r
        vo = mean(v_out)
        eff = vo ** 2 / (SPEC.v_out / SPEC.i_out) / (v_in * i_in)
        # Model at the simulated operating point (same output power and efficiency).
        spec_sim = replace(SPEC, v_out=vo, i_out=vo / (SPEC.v_out / SPEC.i_out), efficiency=eff)
        op = fb.operating_point(spec_sim, conv.n, conv.l_m + l_lk, v_in)
        rows.append(f"| {v_in:.0f} V | {vo:.2f} V | {100 * (eff):.1f} % | {i_p.max():.3f} A / {op.i_p_peak:.3f} A | "
                    f"{mean(v_cl) - v_in:.1f} V / "
                    f"{fb.clamp_voltage(l_lk, i_p.max(), SPEC.f_sw, conv.v_or, clamp.r):.1f} V | "
                    f"{v_sw.max():.1f} V |")
        sims[v_in] = (time, i_p, i_s, v_sw, op)
    report += [
        "## 5. Check against a switching simulation (ngspice)", "",
        f"Open loop at the design duty cycle, with the {100 * (LEAKAGE):.1f} % leakage, the RCD clamp, a Schottky-like "
        f"rectifier and {C_OUT * 1e6:.0f} µF at the output (netlist: `hdk.power.flyback.spice_netlist`). "
        "The model is evaluated at the simulated output power and efficiency.", "",
        "| Input | Output (open loop) | Efficiency | Primary peak: simulation / model | "
        "Clamp voltage: simulation / formula | Drain peak |",
        "| --- | --- | --- | --- | --- | --- |", *rows, "",
        "The simulated converter has no core or switching losses, so it runs above the 85 % assumed for "
        "sizing. The clamp formula ignores the snubber and the switch capacitance, which absorb part of "
        "the leakage energy.", "",
        "![Flyback waveforms: model and ngspice](img/flyback_waveforms.png)", "",
    ]
    time, i_p, i_s, v_sw, op = sims[SPEC.v_in_min]
    period = 1.0 / SPEC.f_sw
    t0 = np.floor(time[-1] / period - 1e-9) * period - 2 * period
    sel = (time >= t0) & (time <= t0 + 2 * period)
    tm, ipm, ism = fb.waveforms(op, SPEC.f_sw, 2000)
    tm2 = np.concatenate([tm, tm + period])
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(7.5, 5.2), sharex=True)
    a1.plot((time[sel] - t0) * 1e6, i_p[sel], color="#2c3e50", lw=1.8, label="primary, ngspice")
    a1.plot((time[sel] - t0) * 1e6, i_s[sel], color="#27ae60", lw=1.8, label="secondary, ngspice")
    a1.plot(tm2 * 1e6, np.tile(ipm, 2), "--", color="#c0392b", lw=1.2, label="model")
    a1.plot(tm2 * 1e6, np.tile(ism, 2), "--", color="#c0392b", lw=1.2)
    a1.set_ylabel("current (A)")
    a1.set_title(f"Flyback at {SPEC.v_in_min:.0f} V, full load: currents and drain voltage")
    a1.grid(alpha=0.3)
    a1.legend(fontsize=8, loc="upper center", ncol=3)
    a1.set_ylim(-0.5, 3.7)
    a2.plot((time[sel] - t0) * 1e6, v_sw[sel], color="#2c3e50", lw=1.2, label="drain, ngspice")
    a2.axhline(SPEC.v_in_min + conv.v_or, color="#7f8c8d", ls="--", lw=1, label="V_in + V_OR")
    a2.axhline(SPEC.v_in_min + clamp.v_clamp, color="#c0392b", ls=":", lw=1.2, label="V_in + V_clamp (design)")
    a2.set_xlabel("time (µs)")
    a2.set_ylabel("voltage (V)")
    a2.grid(alpha=0.3)
    a2.legend(fontsize=8, loc="lower right")
    a2.set_ylim(-2, 56)
    fig.tight_layout()
    fig.savefig(fig_path, dpi=150)
    plt.close(fig)
else:
    report += ["## 5. Check against a switching simulation", "",
               "ngspice is not installed: the comparison was skipped.", ""]

(ROOT / "docs" / "example_flyback_28v.md").write_text("\n".join(report), encoding="utf-8")
print("\n".join(report))
