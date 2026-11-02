import math

import numpy as np
import pytest

from hdk import spice
from hdk.emi import filters as F
from hdk.emi import limits, spectrum

needs_ngspice = pytest.mark.skipif(not spice.available(), reason="ngspice not installed")


# --------------------------------------------------------------------------- spectrum
def test_square_wave_harmonics():
    f, c = spectrum.trapezoid_harmonics(1.0, 100e3, 0.5, 1e-15, f_max=1e6)
    assert f[0] == pytest.approx(100e3)
    assert c[0] == pytest.approx(2.0 / math.pi, rel=1e-9)
    assert c[1] == pytest.approx(0.0, abs=1e-12)
    assert c[2] == pytest.approx(2.0 / (3.0 * math.pi), rel=1e-9)


def test_envelope_corners():
    f1, f2 = spectrum.envelope_corners(250e3, 0.25, 20e-9)
    assert f1 == pytest.approx(1.0 / (math.pi * 1e-6))
    assert f2 == pytest.approx(1.0 / (math.pi * 20e-9))


# --------------------------------------------------------------------------- limits
def test_cispr32_lines():
    qp, av = limits.CISPR32_CLASS_B_MAINS_QP, limits.CISPR32_CLASS_B_MAINS_AV
    assert qp(150e3) == pytest.approx(66.0)
    assert qp(500e3) == pytest.approx(56.0)
    assert qp(5e6) == pytest.approx(56.0)     # the stricter value applies at the step
    assert qp(30e6) == pytest.approx(60.0)
    expected = 66.0 - 10.0 * math.log10(250e3 / 150e3) / math.log10(500e3 / 150e3)
    assert qp(250e3) == pytest.approx(expected)
    assert av(1e6) == pytest.approx(46.0)
    assert np.isnan(qp(100e3))


# --------------------------------------------------------------------------- DM design
def test_corner_and_lc():
    f0 = F.corner_for_attenuation(250e3, 60.0)
    assert f0 == pytest.approx(250e3 * 10 ** -1.5)
    l, c = F.lc_from_corner(f0, 0.5)
    assert math.sqrt(l / c) == pytest.approx(0.5)
    assert 1.0 / (2 * math.pi * math.sqrt(l * c)) == pytest.approx(f0)


@pytest.mark.parametrize("n", [0.5, 1.0, 2.0, 4.0, 8.0])
def test_damping_closed_form_matches_numeric_optimum(n):
    l, c = 10e-6, 40e-6
    closed = F.parallel_rc_damping(l, c, n)
    numeric = F.optimal_damping_numeric(l, c, n)
    assert closed.zo_peak == pytest.approx(numeric.zo_peak, rel=2e-3)
    assert F.peak_output_impedance(l, c, closed) == pytest.approx(closed.zo_peak, rel=2e-3)


def test_damping_lowers_the_peak():
    l, c = 10e-6, 40e-6
    undamped = F.peak_output_impedance(l, c, None)
    damped = F.peak_output_impedance(l, c, F.parallel_rc_damping(l, c, 4.0))
    assert damped < undamped / 10.0


def test_middlebrook():
    z_in = F.converter_input_impedance(36.0, 240.0, 0.92)
    assert z_in == pytest.approx(36.0 ** 2 * 0.92 / 240.0)
    assert F.middlebrook_ok(0.4, z_in)
    assert not F.middlebrook_ok(z_in, z_in)


def _example_dm():
    conv = F.ConverterInput(10e-6, esr=3e-3, esl=1.5e-9)
    damp = F.parallel_rc_damping(15e-6, conv.c_in, 4.0)
    filt = F.DMFilter(l=15e-6, c=33e-6, damping=damp, l_dcr=5e-3, l_cpar=20e-12,
                      c_esr=2e-3, c_esl=1e-9)
    return conv, damp, filt


def test_dm_insertion_loss_is_40db_per_decade():
    conv = F.ConverterInput(10e-6)
    filt = F.DMFilter(l=15e-6, c=33e-6)
    f0 = 1.0 / (2 * math.pi * math.sqrt(15e-6 * 33e-6))
    il = F.dm_insertion_loss_db(np.array([30 * f0, 300 * f0]), conv, filt)
    assert il[1] - il[0] == pytest.approx(40.0, abs=1.0)
    assert il[0] == pytest.approx(40 * math.log10(30), abs=3.0)


@needs_ngspice
def test_dm_noise_path_against_ngspice():
    conv, damp, filt = _example_dm()
    net = f"""* DM noise path: converter current source -> pi filter -> 100 ohm LISN
I1 0 a AC 1
Cin a cin1 {conv.c_in}
Rin cin1 cin2 {conv.esr}
Lin cin2 0 {conv.esl}
Rd a d1 {damp.r_d}
Cd d1 0 {damp.c_d}
L1 a l1 {filt.l}
Rl l1 b {filt.l_dcr}
Cp a b {filt.l_cpar}
Cf b cf1 {filt.c}
Rf cf1 cf2 {filt.c_esr}
Lf cf2 0 {filt.c_esl}
Vs b c 0
Rlisn c 0 100
.ac dec 40 1k 30meg
"""
    data = spice.run(net, ["mag(i(vs))"])
    f, sim = data[:, 0], data[:, 1]
    calc = np.abs(F.dm_lisn_current_ratio(f, conv, filt))
    assert np.max(np.abs(20 * np.log10(sim / calc))) < 0.05


@needs_ngspice
def test_output_impedance_against_ngspice():
    conv, damp, filt = _example_dm()
    net = f"""* filter output impedance seen by the converter, stiff bus
I1 0 a AC 1
Cin a 0 {conv.c_in}
Rd a d1 {damp.r_d}
Cd d1 0 {damp.c_d}
L1 a l1 {filt.l}
Rl l1 0 {filt.l_dcr}
.ac dec 200 1k 1meg
"""
    data = spice.run(net, ["mag(v(a))"])
    f, sim = data[:, 0], data[:, 1]
    calc = np.abs(F.output_impedance(f, filt.l, conv.c_in, damp, r_l=filt.l_dcr))
    assert np.max(np.abs(20 * np.log10(sim / calc))) < 0.05
    assert sim.max() == pytest.approx(damp.zo_peak, rel=0.03)


def test_cm_path():
    filt = F.CMFilter(l_cm=1e-3, c_y=4.7e-9)
    f0 = F.cm_corner(filt.l_cm, filt.c_y)
    assert f0 == pytest.approx(1.0 / (2 * math.pi * math.sqrt(1e-3 * 9.4e-9)))
    assert abs(F.cm_lisn_current_ratio(np.array([1.0]), filt)[0]) == pytest.approx(1.0, rel=1e-3)
    high = abs(F.cm_lisn_current_ratio(np.array([100 * f0]), filt)[0])
    assert 20 * math.log10(high) < -75.0
    i = F.cm_noise_current(np.array([1e6]), np.array([10.0]), 10e-12)
    assert i[0] == pytest.approx(2 * math.pi * 1e6 * 10e-12 * 10.0)
