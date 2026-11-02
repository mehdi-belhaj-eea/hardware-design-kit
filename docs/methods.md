# Methods

The equations behind each calculator, with their assumptions. Symbols follow
the code. Section numbers match the modules.

## 1. Precharge (`hdk.protection.precharge`)

A bus capacitor C charged from a voltage V through a resistor R:

```math
i(t) = \frac{V}{R}\,e^{-t/\tau}, \qquad v_C(t) = V\left(1 - e^{-t/\tau}\right), \qquad \tau = RC
```

- Sizing: R = V_max / I_peak, at the **maximum** bus voltage, where the peak current is highest.
- A bypass switch shorts R when v_C reaches k·V. Time and energy in R up to that point:

```math
t_k = -\tau \ln(1-k), \qquad
E_R(t_k) = \int_0^{t_k} R\,i^2\,dt = \tfrac{1}{2} C V^2 \left[1 - (1-k)^2\right]
```

- Over a full charge the resistor dissipates ½·C·V², exactly what the capacitor stores, whatever R is.
  The resistor must take this as a pulse (pulse-load or wire-wound part), and more if the
  equipment can be switched off and on again before the capacitor discharges.
- When the bypass closes, (1 − k)·V is still across R: the current step is limited only by the
  loop resistance (switch, capacitor ESR, wiring), `bypass_step_current`.
- Envelope check: the current decreases monotonically, so its worst value in a window
  [t0, t1] is i(t0). The envelope itself comes from the program or the product standard.

## 2. Reverse polarity (`hdk.protection.reverse`)

```math
P_\text{diode} = V_F\, I, \qquad
P_\text{MOSFET} = R_{DS(on)}(T_J)\, I^2, \qquad
R_{DS(on)}(T_J) \approx R_{DS(on),25}\,\bigl[1 + \alpha\,(T_J - 25)\bigr]
```

- α ≈ 0.4 to 0.7 %/K for silicon power MOSFETs (0.6 %/K by default); use the datasheet curve when available.
- Size at the highest input current, I = P_out / (η·V_min), which occurs at the **minimum** bus voltage.
- Junction temperature: T_J = T_A + R_th(j-a)·P.

## 3. Lightning and surge with TVS diodes (`hdk.protection.surge`)

**Source.** A Thévenin source: open-circuit voltage V_oc·w(t) behind R_s = V_oc / I_sc.
The shape is a double exponential normalised to a peak of 1:

```math
w(t) = k\left(e^{-\alpha t} - e^{-\beta t}\right), \qquad
t_\text{peak} = \frac{\ln(\beta/\alpha)}{\beta - \alpha}
```

With r = β/α, α = ln r / (t_peak·(r − 1)); r is found numerically (Brent's method) so that
w(t_half) = 0.5. Its tail cannot fall faster than that of t·e^(−t/t_peak) (the limit r → 1), so the
shape requires t_half / t_peak > 2.68 (the code asks for more than 2.7). The standards define front times in
their own ways (IEC 61000-4-5 uses a virtual front time); peak time and time to half value are
enough for sizing.

**TVS.** Linearised clamp from the datasheet point (V_C at I_PP):

```math
R_d = \frac{V_C - V_{BR}}{I_{PP}}, \qquad
i(t) = \max\!\left(0,\ \frac{V_{oc}\,w(t) - V_{BR}}{R_s + R_d}\right), \qquad
v(t) = V_{BR} + R_d\, i(t)
```

The straight line is accurate near I_PP and optimistic far above it. For n diodes in series,
V_BR, R_d and the power rating are multiplied by n.

**Power rating.** The peak pulse power a TVS absorbs rises for shorter pulses. Without the
datasheet curve, the first estimate scales with t^(−1/2) (adiabatic heating of the junction)
from the 10/1000 µs rating, with the time to half value as the pulse width:

```math
P_\text{allowed}(t) = P_{PP}\left(\frac{t}{1\ \text{ms}}\right)^{-1/2}
```

**Requirement.** To keep the protected node below V_max, the protection must carry, and
dissipate at the peak:

```math
I_{pk} = \frac{V_{oc} - V_\text{max}}{R_s}, \qquad
P_{pk} = V_\text{max}\, I_{pk}, \qquad
R_d \le \frac{V_\text{max} - V_{BR}}{I_{pk}}
```

**Pin-injection levels used in Example 1** (DO-160G Section 22, level 3):

| Waveform | Shape | V_oc | I_sc | R_s |
| --- | --- | --- | --- | --- |
| WF4 | 6.4 / 69 µs | 300 V | 60 A | 5 Ω |
| WF5A | 40 / 120 µs | 300 V | 300 A | 1 Ω |

The damped-sine waveform WF3 and multiple-stroke or multiple-burst tests are not modelled.
Use the waveform set and level that the equipment specification calls for.

## 4. ESD (`hdk.protection.esd`)

IEC 61000-4-2 contact discharge (150 pF, 330 Ω), per kV of test voltage: about 3.75 A at the
first peak, 2 A at 30 ns and 1 A at 60 ns. At 8 kV: 30 A, 16 A and 8 A. The 16 A at 30 ns is the
usual reference for the clamping voltage given by TLP measurements.

On a data line, the protection's capacitance slows the edges. Keeping the 10–90 % rise time
2.2·R·C below a fraction of the bit time gives:

```math
C_\text{max} = \frac{\text{fraction}}{2.2\, R_\text{source}\, f_\text{bit}}
```

## 5. Hold-up (`hdk.protection.holdup`)

```math
E = \frac{\sum_i P_i\, t_i}{\eta}, \qquad
C_\text{min} = \frac{2E}{V_1^2 - V_2^2}, \qquad
C_\text{nom} = \frac{C_\text{min}}{(1 - \text{tolerance})(1 - \text{ageing})}
```

V_2 is the minimum input voltage of the downstream converter. Because the usable energy grows
with V_1² − V_2², storing it on a boosted bus (60 V in Example 1) divides the capacitance by
about 7 compared with the 28 V bus.

## 6. Switching spectrum (`hdk.emi.spectrum`)

A trapezoid of amplitude A, frequency f_sw, duty cycle D and rise/fall time t_r has harmonics
of peak amplitude

```math
c_n = 2AD\,\left|\mathrm{sinc}(nD)\right|\,\left|\mathrm{sinc}(n f_{sw} t_r)\right|,
\qquad \mathrm{sinc}(x) = \frac{\sin(\pi x)}{\pi x}
```

The envelope is flat up to f_sw/(π·D), falls at −20 dB/decade up to 1/(π·t_r), then at
−40 dB/decade. The examples use the buck input current (amplitude I_out) for differential
mode and the switching-node voltage (amplitude V_in) for common mode.

## 7. Limit lines and detectors (`hdk.emi.limits`)

CISPR 32 class B, AC mains port (dBµV), used as a well-known public reference:

| Frequency | Quasi-peak | Average |
| --- | --- | --- |
| 0.15–0.5 MHz | 66 → 56 (linear in log f) | 56 → 46 |
| 0.5–5 MHz | 56 | 46 |
| 5–30 MHz | 60 | 50 |

At a step, the lower value applies. EMI receivers are calibrated in RMS for a continuous sine,
so a steady harmonic reads the same on the peak, quasi-peak and average detectors: compare
c_n/√2 with the limit, and the **average** limit binds.

## 8. Differential-mode filter (`hdk.emi.filters`)

```
 LISN (2 × 50 Ω)        filter                 converter
   ──┬──────────────┬──── L_f ────┬─────────────┬───────────┐
     │              │             │             │           │
  100 Ω (DM)       C_f           C_in       R_d + C_d    i_noise
     │              │             │             │           │
   ──┴──────────────┴─────────────┴─────────────┴───────────┘
```

The converter is a noise current source; its own input capacitors C_in take most of the
ripple. With Z_A = Z_Cin ∥ (R_d + Z_Cd) and Z_B = Z_Cf ∥ 100 Ω:

```math
\frac{i_\text{LISN}}{i_\text{noise}} =
\frac{Z_A}{Z_A + Z_{Lf} + Z_B}\cdot\frac{Z_{Cf}}{Z_{Cf} + 100\ \Omega}
```

Inductor DCR and parasitic capacitance, capacitor ESR and ESL are included. Each LISN port reads
50 Ω × i_LISN. Well above the corner, the insertion loss is

```math
IL \approx \left(\frac{f}{f_0}\right)^2 \;(40\ \text{dB/decade}), \qquad
f_0 = \frac{1}{2\pi\sqrt{L_f C_f}}
```

Design steps: for each harmonic, the attenuation needed is A_n = level_n − limit(f_n) + margin;
the corner must satisfy f_0 ≤ f_n·10^(−A_n/40) for all n. For an impedance level
R_0 = √(L_f/C_f): L_f = R_0/ω_0 and C_f = 1/(ω_0·R_0). After rounding L_f to a standard value,
C_f is recomputed to keep the corner.

## 9. Damping and stability (`hdk.emi.filters`)

On a stiff bus, C_f is shorted by the source and the converter sees L_f resonating with its
own C_in. A branch R_d + C_d across C_in, with C_d = n·C_in, damps it. With R_0' = √(L_f/C_in),
the optimum (Erickson & Maksimović) is

```math
R_{d,\text{opt}} = R_0' \sqrt{\frac{(2+n)(4+3n)}{2n^2(4+n)}}, \qquad
\lVert Z_o \rVert_\text{max} = R_0' \,\frac{\sqrt{2(2+n)}}{n}
```

The tests compare this closed form with a numerical minimisation of the peak (n = 0.5 to 8).

A regulated converter draws constant power, so it has a negative incremental input resistance

```math
\lvert Z_\text{in} \rvert = \frac{V_\text{in,min}^2\,\eta}{P_\text{out,max}}
```

Middlebrook's criterion: the filter output impedance must stay well below it at every frequency,
here |Z_o|max ≤ |Z_in| / 2 (6 dB margin). An undamped filter fails by orders of magnitude.

## 10. Common mode (`hdk.emi.filters`)

The switching node drives a parasitic capacitance C_p to chassis: i_CM = 2π·f·C_p·V_n
(a current source, since |Z_Cp| is in the kΩ range). The CM current returns through both LISNs
in parallel (25 Ω), unless the Y capacitors (2·C_Y in total) divert it:

```math
\frac{i_\text{LISN}}{i_{CM}} = \frac{Z_{2C_Y}}{Z_{2C_Y} + Z_{L_{CM}} + 25\ \Omega}, \qquad
f_{0,CM} = \frac{1}{2\pi\sqrt{L_{CM}\cdot 2C_Y}}
```

Each LISN port reads 25 Ω × i_CM. The choke's parasitic capacitance bypasses it at high
frequency. The Y capacitance is often capped by leakage-current or safety rules.

## 11. Limits of the models

- Ideal trapezoids: no ringing, no diode reverse recovery, no resonance of the layout. The real
  spectrum must be measured.
- The LISN is represented by its 50 Ω ports, which is valid over the 150 kHz–30 MHz band; its
  50 µH network is not modelled.
- The stability check assumes a stiff source. With a long supply line, add its inductance.
- Coupling between components and layout loops is not modelled.
- Lumped parasitics only; component values vary with temperature, DC bias (ceramics) and current
  (inductors).
- These calculators help size and review a design. They do not replace qualification tests.

## 12. How the models are checked (`tests/`)

| Check | Reference |
| --- | --- |
| Precharge current peak and time to 90 % | ngspice transient |
| Precharge energy | numerical integration of R·i² |
| Double-exponential fit (several shapes) | peak and half-value times recovered |
| TVS clamp: peak current and voltage | closed form and ngspice transient |
| DM noise path, 1 kHz–30 MHz with all parasitics | ngspice AC (difference < 0.05 dB) |
| Filter output impedance and damped peak | ngspice AC |
| Optimum damping, closed form | numerical minimisation |
| Insertion-loss slope | 40 dB/decade above the corner |
| Hold-up, ESD, limit lines, CM path | closed-form values |

## References

- R. W. Erickson, D. Maksimović, *Fundamentals of Power Electronics*, 2nd ed., Kluwer, 2001, ch. 10 "Input Filter Design".
- R. D. Middlebrook, "Input filter considerations in design and application of switching regulators", IEEE IAS Annual Meeting, 1976.
- C. R. Paul, *Introduction to Electromagnetic Compatibility*, 2nd ed., Wiley, 2006.
- RTCA DO-160G, *Environmental Conditions and Test Procedures for Airborne Equipment*, Section 22 "Lightning Induced Transient Susceptibility", 2010.
- IEC 61000-4-2 (electrostatic discharge immunity) and IEC 61000-4-5 (surge immunity).
- CISPR 32, *Electromagnetic compatibility of multimedia equipment — Emission requirements*.
- ngspice, open-source circuit simulator: <https://ngspice.sourceforge.io>.
