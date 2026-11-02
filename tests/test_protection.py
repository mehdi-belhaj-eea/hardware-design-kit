import math

import numpy as np
import pytest

from hdk import spice
from hdk.protection import esd, holdup, precharge, reverse, surge

needs_ngspice = pytest.mark.skipif(not spice.available(), reason="ngspice not installed")
_trapezoid = getattr(np, "trapezoid", None) or np.trapz


# --------------------------------------------------------------------------- precharge
def test_precharge_design_values():
    d = precharge.design_precharge(28.0, 220e-6, 10.0, 0.9)
    assert d.r_pre == pytest.approx(2.8)
    assert d.tau == pytest.approx(2.8 * 220e-6)
    assert d.t_bypass == pytest.approx(d.tau * math.log(10.0))
    assert d.energy_full == pytest.approx(0.5 * 220e-6 * 28.0 ** 2)
    assert d.energy_resistor == pytest.approx(d.energy_full * 0.99)
    assert d.v_residual == pytest.approx(2.8)


def test_precharge_energy_matches_integral():
    d = precharge.design_precharge(60.0, 470e-6, 15.0, 0.95)
    t = np.linspace(0.0, d.t_bypass, 400001)
    v, i = precharge.waveforms(d.v_bus, d.r_pre, d.c_bus, t)
    assert _trapezoid(i ** 2 * d.r_pre, t) == pytest.approx(d.energy_resistor, rel=1e-4)
    assert v[-1] == pytest.approx(0.95 * 60.0, rel=1e-9)


def test_precharge_envelope():
    rows = precharge.check_inrush_envelope(10.0, 1e-3, [(0.0, 1e-3, 12.0), (1e-3, 1e-2, 3.0)])
    assert rows[0].ok
    assert rows[1].i_worst == pytest.approx(10.0 * math.exp(-1.0))
    assert not rows[1].ok


def test_precharge_rejects_bad_fraction():
    with pytest.raises(ValueError):
        precharge.design_precharge(28.0, 1e-4, 10.0, 1.2)


@needs_ngspice
def test_precharge_against_ngspice():
    d = precharge.design_precharge(28.0, 220e-6, 10.0, 0.9)
    net = f"""* precharge RC charge
V1 in 0 PWL(0 0 1n {d.v_bus})
R1 in a {d.r_pre}
C1 a 0 {d.c_bus}
.tran 0.5u {2 * d.t_bypass} 0 0.5u
"""
    data = spice.run(net, ["v(a)", "i(v1)"])
    t, v, i = data[:, 0], data[:, 1], -data[:, 2]
    assert i.max() == pytest.approx(d.i_peak, rel=0.01)
    assert np.interp(d.t_bypass, t, v) == pytest.approx(0.9 * d.v_bus, rel=0.005)


# --------------------------------------------------------------------------- reverse polarity
def test_reverse_comparison():
    r = reverse.compare(7.25, 0.6, 3e-3, t_j=100.0, alpha=0.006)
    assert r.diode_loss == pytest.approx(0.6 * 7.25)
    assert r.mosfet_rds_hot == pytest.approx(3e-3 * 1.45)
    assert r.mosfet_loss == pytest.approx(7.25 ** 2 * 3e-3 * 1.45)
    assert r.loss_ratio > 10.0


def test_junction_temperature():
    assert reverse.junction_temperature(2.0, 40.0, 85.0) == pytest.approx(165.0)


# --------------------------------------------------------------------------- hold-up
def test_holdup_roundtrip():
    e = holdup.energy([(150.0, 0.02)], efficiency=0.9)
    assert e == pytest.approx(150.0 * 0.02 / 0.9)
    c = holdup.capacitance_min(e, 28.0, 18.0)
    assert holdup.holdup_time(c, 28.0, 18.0, 150.0, 0.9) == pytest.approx(0.02)


def test_holdup_profile_and_nominal():
    e = holdup.energy([(10.0, 0.024), (3.0, 0.176)])
    assert e == pytest.approx(0.768)
    assert holdup.capacitance_nominal(100e-6, 0.2, 0.1) == pytest.approx(100e-6 / 0.72)


def test_boosted_storage_needs_less_capacitance():
    e = holdup.energy([(150.0, 0.02)], 0.9)
    assert holdup.capacitance_min(e, 60.0, 20.0) < holdup.capacitance_min(e, 28.0, 18.0) / 5.0


def test_holdup_rejects_bad_voltages():
    with pytest.raises(ValueError):
        holdup.capacitance_min(1.0, 10.0, 20.0)


# --------------------------------------------------------------------------- surge / TVS
@pytest.mark.parametrize("t_peak,t_half", [(6.4e-6, 69e-6), (40e-6, 120e-6), (1.2e-6, 50e-6)])
def test_double_exponential_fit(t_peak, t_half):
    w = surge.double_exponential(t_peak, t_half)
    assert float(w(t_peak)) == pytest.approx(1.0, rel=1e-9)
    assert float(w(t_half)) == pytest.approx(0.5, rel=1e-6)
    t = np.linspace(0.0, 3.0 * t_half, 300001)
    assert t[np.argmax(w(t))] == pytest.approx(t_peak, rel=1e-3)


EXAMPLE_TVS = surge.TVS("1500 W, 36 V class", v_wm=36.0, v_br=40.0, v_c=58.1, i_pp=25.8, p_pp=1500.0)


def test_clamp_peak_current_closed_form():
    w = surge.double_exponential(6.4e-6, 69e-6)
    res = surge.clamp_response(EXAMPLE_TVS, 300.0, 5.0, w)
    expected = (300.0 - 40.0) / (5.0 + EXAMPLE_TVS.r_dyn)
    assert res.i_peak == pytest.approx(expected, rel=1e-4)
    assert res.v_peak == pytest.approx(40.0 + EXAMPLE_TVS.r_dyn * expected, rel=1e-4)
    assert res.energy > 0.0


def test_series_stack_and_requirement():
    s = EXAMPLE_TVS.stack(2)
    assert s.v_br_total == pytest.approx(80.0)
    assert s.r_dyn_total == pytest.approx(2 * EXAMPLE_TVS.r_dyn)
    req = surge.required_rating(300.0, 1.0, 80.0, 40.0)
    assert req.i_peak == pytest.approx(220.0)
    assert req.p_peak == pytest.approx(17600.0)
    assert req.r_dyn_max == pytest.approx(40.0 / 220.0)


def test_allowed_power_scaling():
    assert surge.allowed_peak_power(EXAMPLE_TVS, 1e-3) == pytest.approx(1500.0)
    assert surge.allowed_peak_power(EXAMPLE_TVS, 0.25e-3) == pytest.approx(3000.0)


@needs_ngspice
def test_clamp_against_ngspice():
    w = surge.double_exponential(6.4e-6, 69e-6)
    res = surge.clamp_response(EXAMPLE_TVS, 300.0, 5.0, w)
    net = f"""* TVS clamp under a double-exponential transient
B1 src 0 V = {300.0 * w.k}*(exp(-{w.alpha}*time)-exp(-{w.beta}*time))
Rs src out 5
Vm out tv 0
D1 0 tv dtvs
.model dtvs D(BV={EXAMPLE_TVS.v_br} IBV=1m RS={EXAMPLE_TVS.r_dyn})
.tran 20n 300u 0 20n
"""
    data = spice.run(net, ["i(vm)", "v(tv)"])
    assert data[:, 1].max() == pytest.approx(res.i_peak, rel=0.02)
    assert data[:, 2].max() == pytest.approx(res.v_peak, rel=0.02)


# --------------------------------------------------------------------------- ESD
def test_esd_currents_and_capacitance():
    cd = esd.contact_discharge(8.0)
    assert (cd.i_first_peak, cd.i_30ns, cd.i_60ns) == pytest.approx((30.0, 16.0, 8.0))
    c_max = esd.max_line_capacitance(1e6, 50.0)
    assert c_max == pytest.approx(0.1 / (2.2 * 50.0 * 1e6))
    assert esd.check_device(8.0, 8.0, 12.0, 15.0, 0.4e-9, c_max).ok
    assert not esd.check_device(4.0, 8.0, 12.0, 15.0, 0.4e-9, c_max).ok
