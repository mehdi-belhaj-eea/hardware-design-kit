"""Example 2 — input EMI filter of a 48 V → 12 V, 240 W buck converter.

All values are illustrative. The reference limit is CISPR 32 class B (AC mains
port), a well-known public limit used here as a target: use the limit that
applies to your product.

Steps: noise without filter → required attenuation → LC corner → standard
values → optimum damping → Middlebrook stability → full check with parasitics.
Then the same for common mode.

Run:  python examples/industrial_48v_emi.py
Writes docs/example_industrial_48v.md and three figures in docs/img/.
"""

from __future__ import annotations

import math
import pathlib

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from hdk.emi import filters as F  # noqa: E402
from hdk.emi import limits, spectrum  # noqa: E402
from hdk.units import to_dbuv  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
IMG = ROOT / "docs" / "img"
IMG.mkdir(parents=True, exist_ok=True)

# ----------------------------------------------------------------- converter (illustrative)
V_MIN, V_NOM, V_MAX = 36.0, 48.0, 60.0
V_OUT, I_OUT, EFF = 12.0, 20.0, 0.92
P_OUT = V_OUT * I_OUT
F_SW, T_RISE = 250e3, 20e-9
DUTY = V_OUT / (V_NOM * EFF)
CONV = F.ConverterInput(c_in=10e-6, esr=3e-3, esl=1.5e-9)   # converter's own ceramics
MARGIN_DB = 6.0
R0 = 0.5                                                   # impedance level √(L_f/C_f) (Ω)
N_DAMP = 4.0
AV, QP = limits.CISPR32_CLASS_B_MAINS_AV, limits.CISPR32_CLASS_B_MAINS_QP

E6 = [1.0, 1.5, 2.2, 3.3, 4.7, 6.8]


def e6_at_least(x: float) -> float:
    """Smallest E6 value not below ``x``."""
    decade = 10.0 ** math.floor(math.log10(x))
    for m in E6 + [10.0]:
        if m * decade >= x * (1 - 1e-9):
            return m * decade
    raise ValueError(x)


report = ["# Example 2 — 48 V input EMI filter (illustrative values)", ""]
report += [f"Buck {V_NOM:.0f} V → {V_OUT:.0f} V, {I_OUT:.0f} A ({P_OUT:.0f} W), f_sw = {F_SW / 1e3:.0f} kHz, "
           f"D = {DUTY:.3f}, edges {T_RISE * 1e9:.0f} ns, converter input ceramics {CONV.c_in * 1e6:.0f} µF.",
           f"Target: {AV.name}, with {MARGIN_DB:.0f} dB margin. A steady harmonic reads the same on the "
           "quasi-peak and average detectors, so the average limit is the one that binds.", ""]

# ----------------------------------------------------------------- 1. DM noise without filter
f, i_pk = spectrum.trapezoid_harmonics(I_OUT, F_SW, DUTY, T_RISE, f_max=30e6)
keep = f >= AV.f_min
f, i_rms = f[keep], spectrum.to_rms(i_pk[keep])
v0 = to_dbuv(50.0 * np.abs(F.dm_lisn_current_ratio(f, CONV, None)) * i_rms)
need = v0 - AV(f) + MARGIN_DB
f0_each = f * 10.0 ** (-np.clip(need, 0.0, None) / 40.0)
k = int(np.argmin(f0_each))
f0 = float(f0_each[k])
report += ["## 1. Required attenuation (differential mode)", "",
           f"Without filter the worst point is {f[k] / 1e3:.0f} kHz: {v0[k]:.1f} dBµV against "
           f"{AV(f[k]):.1f} dBµV, so {need[k]:.1f} dB of attenuation is needed (margin included).",
           f"With 40 dB/decade above the corner: f0 ≤ {f0 / 1e3:.2f} kHz.", ""]

# ----------------------------------------------------------------- 2. L_f and C_f, standard values
l_calc, cf_calc = F.lc_from_corner(f0, R0)
L = e6_at_least(l_calc)
cf_needed = 1.0 / ((2 * math.pi * f0) ** 2 * L)          # keep f0 with the rounded-up inductor
n_caps = math.ceil(cf_needed / 4.7e-6 - 1e-9)
C_F = n_caps * 4.7e-6
f0_real = 1.0 / (2 * math.pi * math.sqrt(L * C_F))
report += ["## 2. Component values", "",
           f"Topology: LISN ─ C_f ─ L_f ─ converter C_in ∥ damping. Impedance level R0 = √(L_f/C_f) = {R0} Ω.", "",
           "| Element | Calculated | Chosen |", "| --- | --- | --- |",
           f"| L_f | {l_calc * 1e6:.2f} µH | {L * 1e6:.1f} µH (E6, rounded up) |",
           f"| C_f (for the same corner with the chosen L_f) | {cf_needed * 1e6:.1f} µF | "
           f"{C_F * 1e6:.1f} µF = {n_caps} × 4.7 µF ceramic |", "",
           f"Resulting corner: {f0_real / 1e3:.2f} kHz.", ""]

# ----------------------------------------------------------------- 3. damping and stability
DCR = 5e-3
damp0 = F.parallel_rc_damping(L, CONV.c_in, N_DAMP)
CD = e6_at_least(damp0.c_d)
damp = F.parallel_rc_damping(L, CONV.c_in, CD / CONV.c_in)
z_in = F.converter_input_impedance(V_MIN, P_OUT, EFF)
zo_damped = F.peak_output_impedance(L, CONV.c_in, damp, r_l=DCR)
zo_undamped = F.peak_output_impedance(L, CONV.c_in, None, r_l=DCR)
ok = F.middlebrook_ok(zo_damped, z_in, 6.0)
report += ["## 3. Damping and stability (Middlebrook)", "",
           f"On a stiff bus the converter sees L_f resonating with its own {CONV.c_in * 1e6:.0f} µF "
           f"(R0' = √(L_f/C_in) = {damp.r0:.2f} Ω). Damping branch across C_in: "
           f"C_d = {CD * 1e6:.0f} µF (E6 above {N_DAMP:g} × C_in, n = {damp.n:.1f}), "
           f"R_d = {damp.r_d * 1e3:.0f} mΩ (closed-form optimum; the ESR of an electrolytic C_d can provide part of it).", "",
           f"Converter input impedance at {V_MIN:.0f} V, full load: |Z_in| = V²·η/P = {z_in:.2f} Ω.", "",
           "| Filter | Peak output impedance |", "| --- | --- |",
           f"| Undamped (only the {DCR * 1e3:.0f} mΩ winding resistance) | {zo_undamped:.0f} Ω |",
           f"| Damped | {zo_damped:.2f} Ω (closed form {damp.zo_peak:.2f} Ω) |", "",
           f"Requirement with 6 dB margin: ≤ {z_in / 2:.2f} Ω → {'pass' if ok else 'FAIL'}. "
           "Undamped, the filter would make the converter oscillate.", "",
           "![Filter output impedance and stability limit](img/emi48_stability.png)", ""]

fz = np.logspace(2, 7, 3000)
fig, ax = plt.subplots(figsize=(7.0, 3.6))
ax.loglog(fz, np.abs(F.output_impedance(fz, L, CONV.c_in, None, r_l=DCR)), color="#95a5a6", lw=1.5, label="undamped")
ax.loglog(fz, np.abs(F.output_impedance(fz, L, CONV.c_in, damp, r_l=DCR)), color="#2c3e50", lw=2,
          label="damped (optimum R_d)")
ax.axhline(z_in, color="#c0392b", lw=1.5, label="|Z_in| of the converter")
ax.axhline(z_in / 2, color="#c0392b", lw=1, ls="--", label="limit with 6 dB margin")
ax.set_xlabel("frequency (Hz)")
ax.set_ylabel("|Z| (Ω)")
ax.set_title("Filter output impedance versus converter input impedance")
ax.grid(which="both", alpha=0.25)
ax.legend(fontsize=8)
fig.tight_layout()
fig.savefig(IMG / "emi48_stability.png", dpi=150)
plt.close(fig)

# ----------------------------------------------------------------- 4. full check with parasitics
filt = F.DMFilter(l=L, c=C_F, damping=damp, l_dcr=DCR, l_cpar=20e-12, c_esr=1e-3, c_esl=0.5e-9)
v1 = to_dbuv(50.0 * np.abs(F.dm_lisn_current_ratio(f, CONV, filt)) * i_rms)
m_av = limits.margin(v1, f, AV)
worst = int(np.argmin(m_av))
report += ["## 4. Check with parasitics", "",
           f"Inductor {DCR * 1e3:.0f} mΩ DCR and 20 pF parasitic capacitance; C_f bank 1 mΩ ESR and 0.5 nH ESL "
           "(including layout).", "",
           f"Worst margin to the average limit: {m_av[worst]:.1f} dB at {f[worst] / 1e6:.2f} MHz "
           f"({'meets' if m_av[worst] >= MARGIN_DB else 'below'} the {MARGIN_DB:.0f} dB target).", "",
           "Above a few MHz the inductor's parasitic capacitance and the capacitors' ESL limit the "
           "attenuation: keep the filter compact and away from the switching cell.", "",
           "![Differential-mode emission](img/emi48_dm_spectrum.png)", ""]

fig, ax = plt.subplots(figsize=(7.5, 3.8))
fl = np.logspace(np.log10(150e3), np.log10(30e6), 400)
ax.semilogx(fl, QP(fl), color="#7f8c8d", lw=1.5, ls="--", label="limit, quasi-peak")
ax.semilogx(fl, AV(fl), color="#c0392b", lw=2, label="limit, average")
ax.semilogx(f, v0, "o", ms=3, color="#95a5a6", label="without filter")
ax.semilogx(f, v1, "o", ms=3, color="#2c3e50", label="with filter")
ax.set_xlabel("frequency (Hz)")
ax.set_ylabel("LISN voltage (dBµV)")
ax.set_title("Differential-mode emission at the LISN (harmonics of 250 kHz)")
ax.set_ylim(-20, 120)
ax.grid(which="both", alpha=0.25)
ax.legend(fontsize=8, loc="lower left", ncol=2)
fig.tight_layout()
fig.savefig(IMG / "emi48_dm_spectrum.png", dpi=150)
plt.close(fig)

# ----------------------------------------------------------------- 5. common mode
C_PAR = 30e-12                    # switch node to heatsink / chassis (illustrative)
C_Y = 22e-9                       # Y capacitor per line (F)
fv, v_pk = spectrum.trapezoid_harmonics(V_NOM, F_SW, DUTY, T_RISE, f_max=30e6)
sel = fv >= AV.f_min
fv, v_rms = fv[sel], spectrum.to_rms(v_pk[sel])
i_cm = F.cm_noise_current(fv, v_rms, C_PAR)
cm0 = to_dbuv(25.0 * np.abs(F.cm_lisn_current_ratio(fv, None)) * i_cm)
need_cm = cm0 - AV(fv) + MARGIN_DB
f0_cm_each = fv * 10.0 ** (-np.clip(need_cm, 0.0, None) / 40.0)
kc = int(np.argmin(f0_cm_each))
f0_cm = float(f0_cm_each[kc])
l_cm_calc = 1.0 / ((2 * math.pi * f0_cm) ** 2 * 2.0 * C_Y)
cm = F.CMFilter(l_cm=e6_at_least(l_cm_calc), c_y=C_Y, l_cpar=10e-12)
cm1 = to_dbuv(25.0 * np.abs(F.cm_lisn_current_ratio(fv, cm)) * i_cm)
m_cm = limits.margin(cm1, fv, AV)
wc = int(np.argmin(m_cm))
report += ["## 5. Common mode", "",
           f"Switching node {V_NOM:.0f} V with {T_RISE * 1e9:.0f} ns edges, {C_PAR * 1e12:.0f} pF to chassis "
           f"(i = C·dv/dt). Without filter the worst point is {fv[kc] / 1e3:.0f} kHz, {need_cm[kc]:.1f} dB above "
           "the target (margin included).", "",
           f"With Y capacitors of {C_Y * 1e9:.0f} nF per line (2·C_Y for common mode), the corner must be below "
           f"{f0_cm / 1e3:.1f} kHz: L_CM ≥ {l_cm_calc * 1e3:.2f} mH, chosen {cm.l_cm * 1e3:.1f} mH "
           f"(10 pF parasitic). Worst margin with the filter: {m_cm[wc]:.1f} dB at {fv[wc] / 1e6:.2f} MHz.", "",
           "The choke's parasitic capacitance bypasses it at high frequency: there, layout (short Y-capacitor "
           "loops, a low-impedance chassis connection) matters more than the component values.", "",
           "![Common-mode emission](img/emi48_cm_spectrum.png)", ""]

fig, ax = plt.subplots(figsize=(7.5, 3.8))
ax.semilogx(fl, AV(fl), color="#c0392b", lw=2, label="limit, average")
ax.semilogx(fv, cm0, "o", ms=3, color="#95a5a6", label="without CM filter")
ax.semilogx(fv, cm1, "o", ms=3, color="#27ae60", label="with CM filter")
ax.set_xlabel("frequency (Hz)")
ax.set_ylabel("LISN voltage (dBµV)")
ax.set_title("Common-mode emission at the LISN")
ax.set_ylim(-20, 120)
ax.grid(which="both", alpha=0.25)
ax.legend(fontsize=8, loc="lower left", ncol=2)
fig.tight_layout()
fig.savefig(IMG / "emi48_cm_spectrum.png", dpi=150)
plt.close(fig)

(ROOT / "docs" / "example_industrial_48v.md").write_text("\n".join(report), encoding="utf-8")
print("\n".join(report))
