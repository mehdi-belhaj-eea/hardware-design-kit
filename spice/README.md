# Standalone ngspice netlists

The same circuits as the two examples, ready to open in ngspice. Each file prints
its key results with `.meas`, so you can compare them with the Python model
without running any Python. The test suite builds similar netlists and runs the
comparison automatically (`tests/`).

```bash
ngspice -b precharge.cir
ngspice -b tvs_clamp.cir
ngspice -b dm_filter_ac.cir
ngspice -b zout_damping_ac.cir
```

Results with ngspice 42:

| Netlist | Quantity | ngspice | Python model |
| --- | --- | --- | --- |
| `precharge.cir` | Peak inrush current | 15.00 A | 15.00 A |
| | Time to 90 % of 32 V | 1.0807 ms | 1.0807 ms |
| | Energy in the resistor until then | 111.5 mJ | 111.5 mJ |
| `tvs_clamp.cir` | WF4: peak current / clamped voltage | 45.6 A / 72.2 V | 45.6 A / 72.0 V |
| | WF5A: peak current / clamped voltage | 152.6 A / 147.4 V | 152.8 A / 147.2 V |
| `dm_filter_ac.cir` | LISN reading per ampere of noise at 250 kHz, with filter | −86.36 dB | −86.36 dB |
| | Same, without filter | −24.24 dB | −24.24 dB |
| | Insertion loss at 250 kHz | 62.12 dB | 62.12 dB |
| `zout_damping_ac.cir` | Peak output impedance, undamped | 299.9 Ω | 300.0 Ω |
| | Peak output impedance, damped | 0.945 Ω | 0.944 Ω |

The small TVS difference comes from the SPICE diode, whose breakdown knee is
exponential where the Python model uses a straight line (V_BR + R_d·I).

Notes:

- The lightning sources are behavioural voltage sources (`B` elements) with the
  double-exponential coefficients computed by `hdk.protection.surge.double_exponential`.
- The two AC netlists use a `.control` block, because ngspice measures AC
  magnitudes (`vdb`, `vm`) more cleanly there than with `.meas` cards.
- The undamped filter resonance has a Q of about 245, so its peak is only about
  50 Hz wide: `zout_damping_ac.cir` uses a fine sweep to catch it.
