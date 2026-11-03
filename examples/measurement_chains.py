"""Example 4 — voltage and current measurement chains of an inverter (illustrative values).

1. DC-link voltage, up to 500 V, read by a 12-bit SAR ADC (3.3 V) through a divider.
2. Phase current, ±20 A, read through a 1 mΩ shunt and a gain-50 current-sense amplifier.

For each chain: component values, sampling front-end, and the error budget
(worst case and RSS), before and after a two-point calibration at production.
The component figures are typical data-sheet classes, not a specific part.

Run:  python examples/measurement_chains.py
Writes docs/example_measurement.md and docs/img/measurement_budget.png.
"""

from __future__ import annotations

import pathlib

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402
import numpy as np  # noqa: E402

from hdk.measure import adc, budget, divider, shunt  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
IMG = ROOT / "docs" / "img"
IMG.mkdir(parents=True, exist_ok=True)

BITS, V_FS = 12, 3.3
C_SAMPLE = 15e-12             # SAR sampling capacitor (typical)
DELTA_T = 50.0                # temperature range seen by the electronics around calibration (K)
ADC_GAIN, ADC_OFFSET_LSB, ADC_INL_LSB = 0.001, 2.0, 1.0
REF_TOL, REF_TC = 0.001, 20.0  # reference: 0.1 %, 20 ppm/K


def pct(x: float) -> str:
    return f"{100 * x:.3f} %"


def budget_table(b: budget.Budget) -> list[str]:
    rows = ["| Term | Error at full scale | Removed by calibration |", "| --- | --- | --- |"]
    rows += [f"| {t.name} | ±{pct(abs(t.value))} | {'yes' if t.calibratable else 'no'} |" for t in b.terms]
    rows += [f"| **Worst case / RSS, as built** | ±{pct(b.worst_case())} / ±{pct(b.rss())} | |",
             f"| **Worst case / RSS, after calibration** | ±{pct(b.worst_case(True))} / "
             f"±{pct(b.rss(True))} | |"]
    return rows


report = ["# Example 4 — Voltage and current measurement chains (illustrative values)", ""]
report += [f"ADC: {BITS} bits, {V_FS} V full scale, sampling capacitor {C_SAMPLE * 1e12:.0f} pF; "
           f"reference ±{100 * (REF_TOL):.1f} % and {REF_TC:.0f} ppm/K; ADC gain error ±{100 * (ADC_GAIN):.1f} %, offset "
           f"±{ADC_OFFSET_LSB:g} LSB, non-linearity ±{ADC_INL_LSB:g} LSB. Temperature span "
           f"{DELTA_T:.0f} K around the calibration point.", ""]

# ----------------------------------------------------------------- 1. DC-link voltage
V_MAX = 500.0
div = divider.design_divider(V_MAX, V_FS, r_top_total=1e6, n_top=4, headroom=0.95)
span_v = div.v_out(V_MAX)
c_f_min = adc.min_filter_capacitance(C_SAMPLE, BITS)
C_FILTER = 150e-9
F_SAMPLE = 500.0              # sample rate of this channel (Hz)
tau = div.r_source * C_FILTER
f_s_max = adc.max_sample_rate(div.r_source, C_SAMPLE, BITS)
load_10k = adc.sampling_load_error(div.r_source, C_SAMPLE, 10e3) * V_FS / span_v
b_v = budget.Budget("DC-link voltage", tuple(
    divider.divider_terms(div, tol=0.001, tcr_ppm=25.0, delta_t=DELTA_T)
    + divider.adc_terms(BITS, V_FS, span_v, REF_TOL, REF_TC, DELTA_T, ADC_GAIN, ADC_OFFSET_LSB, ADC_INL_LSB)
    + [budget.ErrorTerm(f"sampling load at {F_SAMPLE:.0f} Hz",
                        adc.sampling_load_error(div.r_source, C_SAMPLE, F_SAMPLE) * V_FS / span_v)]))
report += [
    "## 1. DC-link voltage (0 to 500 V)", "",
    f"Divider: {div.n_top} × {div.r_top_each / 1e3:.0f} kΩ on top (0.1 %, 25 ppm/K, 1206), "
    f"{div.r_bottom / 1e3:.2f} kΩ at the bottom, all E96. Splitting the top resistor keeps each part within "
    "its voltage rating and spreads the creepage distance.", "",
    "| Quantity | Value |", "| --- | --- |",
    f"| Ratio | {div.ratio:.5f} ({V_MAX:.0f} V → {span_v:.3f} V, {100 * (span_v / V_FS):.0f} % of the ADC range) |",
    f"| Each top resistor at {V_MAX:.0f} V | {div.v_top_each(V_MAX):.0f} V, {div.p_top_each(V_MAX) * 1e3:.0f} mW |",
    f"| Divider current at {V_MAX:.0f} V | {div.current(V_MAX) * 1e3:.2f} mA |",
    f"| Source resistance seen by the ADC | {div.r_source / 1e3:.2f} kΩ |",
    f"| LSB referred to the DC link | {adc.lsb(V_FS, BITS) / div.ratio * 1e3:.0f} mV |", "",
    "Sampling without a buffer (multiplexed SAR ADC, worst case: the previous channel left the sampling "
    "capacitor at 0 V) sets two separate limits:", "",
    f"- one sample: the filter capacitor must absorb the kick-back of the {C_SAMPLE * 1e12:.0f} pF sampling "
    f"capacitor within ½ LSB, so C_f ≥ {c_f_min * 1e9:.0f} nF. With {C_FILTER * 1e9:.0f} nF the filter corner is "
    f"{adc.rc_corner(div.r_source, C_FILTER):.0f} Hz and a full-scale step settles to ½ LSB in "
    f"{adc.settling_time(tau, BITS) * 1e3:.1f} ms;",
    f"- repeated samples: each conversion draws a charge C_s·ΔV, an average current that the "
    f"{div.r_source / 1e3:.2f} kΩ source cannot supply without an error, whatever C_f is. For ½ LSB the sample "
    f"rate must stay below {f_s_max:.0f} Hz; at {F_SAMPLE:.0f} Hz the error is in the budget below, at 10 kHz it "
    f"would reach {100 * load_10k:.2f} % ({load_10k * 2 ** BITS * span_v / V_FS:.1f} LSB).", "",
    "This front-end suits the monitoring of a slow bus. A control loop sampling at several kilohertz, or an "
    "overvoltage protection, needs an op-amp buffer after the divider (or its own comparator).", "",
    *budget_table(b_v), "",
    f"In volts (all terms referred to the {V_MAX:.0f} V full scale): ±{b_v.worst_case() * V_MAX:.1f} V worst case "
    f"as built, ±{b_v.worst_case(True) * V_MAX:.1f} V after calibration. What remains is drift: "
    f"\"{b_v.largest(True).name}\" leads. A matched resistor network (tracking TCR) would shrink it.", "",
]

# ----------------------------------------------------------------- 2. phase current
I_FS, I_RMS = 20.0, 14.1
chain = shunt.ShuntChain(r_shunt=1e-3, gain=50.0, v_ref=V_FS / 2.0, v_fs=V_FS)
span_i = chain.gain * chain.r_shunt * I_FS
b_i = budget.Budget("Phase current", tuple(
    shunt.shunt_terms(chain, I_FS, tol=0.01, tcr_ppm=50.0, delta_t=DELTA_T, v_offset=100e-6,
                      v_offset_drift=0.5e-6, gain_error=0.002, gain_drift_ppm=10.0)
    + divider.adc_terms(BITS, V_FS, span_i, REF_TOL, REF_TC, DELTA_T, ADC_GAIN, ADC_OFFSET_LSB, ADC_INL_LSB,
                        v_zero=chain.v_ref)))
offset_at_1a = 100e-6 / chain.r_shunt
report += [
    "## 2. Phase current (±20 A)", "",
    f"Shunt {chain.r_shunt * 1e3:.0f} mΩ (1 %, 50 ppm/K), current-sense amplifier gain {chain.gain:.0f} "
    f"(offset 100 µV, 0.5 µV/K; gain error 0.2 %, 10 ppm/K), output referred to mid-scale "
    f"({chain.v_ref:.2f} V) for a bidirectional current. The amplifier reference is derived from the ADC "
    "reference (ratiometric), so a reference error scales the current span only; the ADC gain error, which "
    "acts on the absolute input voltage, also shifts the mid-scale zero.", "",
    "| Quantity | Value |", "| --- | --- |",
    f"| Output at ±{I_FS:.0f} A | {chain.v_out(-I_FS):.2f} V to {chain.v_out(I_FS):.2f} V |",
    f"| Measurable range | −{chain.i_max_negative:.0f} A to +{chain.i_max_positive:.0f} A |",
    f"| Shunt dissipation at {I_RMS:.1f} A rms | {chain.power(I_RMS):.2f} W |",
    f"| LSB referred to the current | {adc.lsb(V_FS, BITS) / (chain.gain * chain.r_shunt) * 1e3:.0f} mA |", "",
    *budget_table(b_i), "",
    f"The amplifier offset alone is {offset_at_1a * 1e3:.0f} mA: {100 * (offset_at_1a / 1.0):.0f} % of a 1 A reading. "
    "Measuring the zero-current output at start-up (all switches off) removes it, which is why motor "
    "drives calibrate the offset at every power-up.", "",
    "![Error budgets](img/measurement_budget.png)", "",
]

# ----------------------------------------------------------------- figure
fig, axes = plt.subplots(1, 2, figsize=(9.5, 3.8))
for ax, b in zip(axes, (b_v, b_i)):
    names = [t.name for t in b.terms][::-1]
    vals = np.array([abs(t.value) * 100 for t in b.terms][::-1])
    colors = ["#95a5a6" if t.calibratable else "#2c3e50" for t in b.terms][::-1]
    ax.barh(names, vals, color=colors)
    ax.set_title(f"{b.name}\nworst case {b.worst_case() * 100:.2f} % → {b.worst_case(True) * 100:.2f} % "
                 "after calibration", fontsize=9)
    ax.set_xlabel("error at full scale (%)")
    ax.tick_params(axis="y", labelsize=8)
    ax.grid(axis="x", alpha=0.3)
    ax.set_xlim(left=0.0)
axes[1].legend(handles=[Patch(color="#95a5a6", label="removed by calibration"),
                        Patch(color="#2c3e50", label="remains")], fontsize=8, loc="lower right")
fig.tight_layout()
fig.savefig(IMG / "measurement_budget.png", dpi=150)
plt.close(fig)

(ROOT / "docs" / "example_measurement.md").write_text("\n".join(report), encoding="utf-8")
print("\n".join(report))
