# hardware-design-kit

[![tests](https://github.com/mehdi-belhaj-eea/hardware-design-kit/actions/workflows/ci.yml/badge.svg)](https://github.com/mehdi-belhaj-eea/hardware-design-kit/actions/workflows/ci.yml)

Design calculators for the power input of an electronic board: inrush precharge, reverse
polarity, lightning and surge (TVS), ESD, hold-up, and the differential- and common-mode EMI
filter with its damping and stability check. Written in Python; every model is checked
against closed-form results and ngspice simulations in the test suite.

> Personal self-training project (2026). All values in the examples are illustrative: no data
> from any employer, customer or program is used.

## What it covers

| Module | What it sizes or checks |
| --- | --- |
| `hdk.protection.precharge` | Precharge resistor, time constant, bypass time, pulse energy in the resistor, inrush envelope |
| `hdk.protection.reverse` | Schottky diode versus MOSFET ("ideal diode"): drop and losses with R_DS(on) at temperature |
| `hdk.protection.surge` | Double-exponential transient source (DO-160G Section 22, IEC 61000-4-5), TVS clamp, pulse-power check, required rating |
| `hdk.protection.esd` | IEC 61000-4-2 currents, clamp and rating check, capacitance budget of a data line |
| `hdk.protection.holdup` | Hold-up energy, minimum and nominal capacitance (tolerance, ageing), direct versus boosted storage |
| `hdk.emi.spectrum` | Harmonics of trapezoidal switching waveforms and their envelope |
| `hdk.emi.limits` | Conducted-emission limit lines (CISPR 32 class B as a reference), margins |
| `hdk.emi.filters` | DM π filter with parasitics, optimum damping, Middlebrook stability, CM choke and Y capacitors |

The equations and assumptions are in [docs/methods.md](docs/methods.md).

## Worked examples

### 1. 28 V aircraft-style input protections — [full report](docs/example_aero_28v.md)

| Check | Result |
| --- | --- |
| Precharge of 220 µF at 32 V, 15 A max | 2.13 Ω, τ = 0.47 ms, 112 mJ pulse in the resistor; inrush envelope met |
| Reverse polarity at 9.3 A | Schottky 5.1 W, MOSFET 0.5 W |
| 1500 W TVS, pin injection level 3, WF4 (300 V, 5 Ω) | 46 A, clamped at 72 V: pass |
| Same TVS, WF5A (300 V, 1 Ω) | 153 A, 147 V: fail. The protection must carry 220 A with R_d ≤ 182 mΩ |
| Hold-up, 20 ms at 150 W | 20.1 mF on the 28 V bus, or 2.9 mF on a 60 V storage bus |

<img src="docs/img/aero28_precharge.png" width="49%"> <img src="docs/img/aero28_lightning.png" width="49%">

### 2. 48 V industrial buck converter, input EMI filter — [full report](docs/example_industrial_48v.md)

| Step | Result |
| --- | --- |
| DM attenuation needed at 250 kHz (6 dB margin) | 60.6 dB, corner f0 ≤ 7.6 kHz |
| DM filter | L_f = 15 µH, C_f = 7 × 4.7 µF; worst margin 7.5 dB |
| Damping across the converter's 10 µF | R_d = 688 mΩ + C_d = 47 µF |
| Middlebrook check at 36 V, 240 W | peak \|Z_o\| = 0.94 Ω against a 2.48 Ω limit (undamped: 300 Ω) |
| Common mode, 30 pF to chassis | 1 mH choke + 2 × 22 nF: worst margin 7.0 dB |

<img src="docs/img/emi48_stability.png" width="49%"> <img src="docs/img/emi48_dm_spectrum.png" width="49%">

## Validation

- **Tests** (`pytest`): closed-form checks of every calculator, and cross-checks against
  **ngspice**: precharge transient, TVS clamp, DM noise path from 1 kHz to 30 MHz with all
  parasitics (difference below 0.05 dB), filter output impedance.
- **Optimum damping**: the closed-form R_d is compared with a numerical minimisation of the
  output-impedance peak.
- **Standalone netlists** in [spice/](spice/) reproduce the examples and print their results
  with `.meas`.
- **CI**: GitHub Actions runs the tests and both examples on Python 3.10 and 3.12, with ngspice.

## Quick start

```bash
git clone https://github.com/mehdi-belhaj-eea/hardware-design-kit.git
cd hardware-design-kit
pip install -e ".[dev]"
pytest                                  # ngspice tests are skipped if ngspice is not installed
python examples/aero_28v_protection.py
python examples/industrial_48v_emi.py
```

```python
from hdk.protection import precharge, surge

d = precharge.design_precharge(v_bus=32.0, c_bus=220e-6, i_peak_max=15.0)
print(f"R = {d.r_pre:.2f} ohm, tau = {d.tau * 1e3:.2f} ms, E_R = {d.energy_resistor * 1e3:.0f} mJ")

wf4 = surge.double_exponential(t_peak=6.4e-6, t_half=69e-6)
tvs = surge.TVS("1500 W, 36 V", v_wm=36.0, v_br=40.0, v_c=58.1, i_pp=25.8, p_pp=1500.0)
r = surge.clamp_response(tvs, v_oc=300.0, r_source=5.0, wave=wf4)
print(f"TVS current {r.i_peak:.0f} A, clamped at {r.v_peak:.0f} V")
```

## Limits

- Ideal trapezoidal waveforms: ringing, diode recovery and layout resonances are not modelled.
- Linearised TVS and a t^(−1/2) pulse-power estimate: confirm with the datasheet curves.
- CISPR 32 is used as a well-known public reference. Use the limit that applies to the product
  (DO-160 Section 21, MIL-STD-461 CE102, CISPR 25, ...).
- These calculators help size and review a design; they do not replace qualification tests.

## Roadmap

- [x] Input protections and EMI filter (this release)
- [ ] Flyback converter and transformer design; voltage and current measurement chains
- [ ] PCB rules: trace width and temperature rise (IPC-2221), creepage and clearance (IEC 60664-1, altitude correction)
- [ ] KiCad 4-layer board applying these rules

## About

Mehdi Belhaj, power electronics and embedded systems engineer, Toulouse —
[mehdi-belhaj-eea.github.io](https://mehdi-belhaj-eea.github.io)

I used an AI assistant (Claude) to help write the code and documentation. The equations are
written out in [docs/methods.md](docs/methods.md), and every result is checked by the tests.

Licence: MIT.

---

### En bref (français)

Calculateurs pour l'étage d'entrée d'une carte électronique : précharge (limitation du courant
d'appel), protection contre l'inversion de polarité, foudre et surtensions (TVS), ESD,
maintien (hold-up), et filtre CEM de mode différentiel et de mode commun avec amortissement et
critère de stabilité de Middlebrook. Chaque modèle est vérifié par des tests, dont des
comparaisons avec ngspice. Deux exemples : une entrée 28 V de type aéronautique (DO-160G
section 22, niveau 3) et un convertisseur abaisseur 48 V (CISPR 32 classe B). Projet personnel
d'autoformation ; toutes les valeurs sont illustratives.
