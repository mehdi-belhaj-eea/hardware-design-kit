import math
from dataclasses import replace

import numpy as np
import pytest

from hdk import spice
from hdk.power import flyback as fb

needs_ngspice = pytest.mark.skipif(not spice.available(), reason="ngspice not installed")
_trapezoid = getattr(np, "trapezoid", None) or np.trapz

SPEC = fb.FlybackSpec(v_in_min=18.0, v_in_max=32.0, v_out=15.0, i_out=1.0, f_sw=200e3,
                      efficiency=0.85, v_f=0.5, d_max=0.45, k_rp=0.5)


def test_design_meets_duty_and_ripple_ratio():
    d = fb.design(SPEC)
    assert d.low_line.duty == pytest.approx(SPEC.d_max)
    assert d.low_line.delta_i / d.low_line.i_p_peak == pytest.approx(SPEC.k_rp)
    assert d.v_ds_off == pytest.approx(SPEC.v_in_max + d.v_or)
    assert d.v_diode_reverse == pytest.approx(SPEC.v_out + SPEC.v_in_max / d.n)


def test_charge_balance_in_ccm():
    d = fb.design(SPEC)
    for op in (d.low_line, d.high_line):
        assert op.mode == "CCM"
        assert op.i_in == pytest.approx(op.duty * (op.i_p_peak + op.i_p_valley) / 2.0)
        # the secondary carries the reflected magnetising current: its average includes the losses
        assert op.i_s_peak == pytest.approx(d.n * op.i_p_peak)
        assert op.i_s_avg == pytest.approx(SPEC.p_in / (SPEC.v_out + SPEC.v_f))
        assert op.output_scale * op.i_s_avg == pytest.approx(SPEC.i_out)


def test_rms_formula_matches_waveform():
    d = fb.design(SPEC)
    for op in (d.low_line, fb.operating_point(SPEC, d.n, d.l_m, 32.0, i_out=0.1)):
        _, i_p, i_s = fb.waveforms(op, SPEC.f_sw, 200000)
        assert math.sqrt(np.mean(i_p ** 2)) == pytest.approx(op.i_p_rms, rel=1e-3)
        assert math.sqrt(np.mean(i_s ** 2)) == pytest.approx(op.i_s_rms, rel=1e-3)


def test_light_load_is_dcm():
    d = fb.design(SPEC)
    op = fb.operating_point(SPEC, d.n, d.l_m, 32.0, i_out=0.1)
    assert op.mode == "DCM"
    assert 0.5 * d.l_m * op.i_p_peak ** 2 * SPEC.f_sw == pytest.approx(SPEC.v_out * 0.1 / SPEC.efficiency)
    assert op.duty + op.d_off < 1.0


def test_boundary_mode_is_consistent():
    spec = replace(SPEC, k_rp=1.0)
    d = fb.design(spec)
    assert d.low_line.i_p_valley == pytest.approx(0.0, abs=1e-9)
    assert 0.5 * d.l_m * d.low_line.i_p_peak ** 2 * spec.f_sw == pytest.approx(spec.p_in, rel=1e-9)


def test_rejects_bad_spec():
    with pytest.raises(ValueError):
        replace(SPEC, k_rp=1.5)
    with pytest.raises(ValueError):
        replace(SPEC, v_in_min=40.0)


def test_clamp_roundtrip():
    c = fb.rcd_clamp(0.5e-6, 3.0, 200e3, 15.0, 32.0, k_clamp=2.0)
    assert c.p_clamp == pytest.approx(0.5 * 0.5e-6 * 9.0 * 200e3 * 2.0)
    assert fb.clamp_voltage(0.5e-6, 3.0, 200e3, 15.0, c.r) == pytest.approx(c.v_clamp)
    assert c.v_ds_peak == pytest.approx(62.0)
    with pytest.raises(ValueError):
        fb.rcd_clamp(0.5e-6, 3.0, 200e3, 15.0, 32.0, k_clamp=0.9)


def test_rhp_zero_and_output_capacitor_in_ccm():
    d = fb.design(SPEC)
    op = d.low_line
    f_z = fb.rhp_zero(SPEC, op, d.n, d.l_m)
    assert f_z == pytest.approx((1 - op.duty) ** 2 * 15.0 * d.n ** 2 / (2 * math.pi * op.duty * d.l_m))
    # the scaled secondary current stays above I_out: the capacitor feeds the load during D·T only
    assert op.output_scale * op.i_s_valley > SPEC.i_out
    cap = fb.output_capacitor(op, SPEC.f_sw, 0.15, esr_share=0.2)
    assert cap.c_min == pytest.approx(1.0 * op.duty / (SPEC.f_sw * 0.15 * 0.8), rel=1e-3)
    assert cap.esr_max * op.i_s_peak == pytest.approx(0.03)


def test_output_capacitor_charge_in_dcm():
    d = fb.design(SPEC)
    op = fb.operating_point(SPEC, d.n, d.l_m, 32.0, i_out=0.3)
    assert op.mode == "DCM"
    peak = op.output_scale * op.i_s_peak          # triangle of average I_out
    expected = (peak - 0.3) ** 2 * op.d_off / (SPEC.f_sw * 2.0 * peak)
    assert fb.capacitor_charge(op, SPEC.f_sw) == pytest.approx(expected, rel=1e-3)
    assert expected > 0.3 * (1.0 - op.d_off) / SPEC.f_sw   # more than the "rectifier off" estimate


@needs_ngspice
@pytest.mark.parametrize("v_in", [18.0, 32.0])
def test_against_ngspice_switching_model(v_in):
    d = fb.design(SPEC, n=1.0)
    l_lk = 0.015 * d.l_m
    clamp = fb.rcd_clamp(l_lk, d.i_p_peak_max, SPEC.f_sw, d.v_or, SPEC.v_in_max)
    data = spice.run(fb.spice_netlist(d, v_in, l_lk, clamp, 22e-6), ["i(vsense)", "v(out)", "v(cl)"])
    t, i_p, v_out, v_cl = data.T
    duration = t[-1] - t[0]

    def avg(y):
        return _trapezoid(y, t) / duration

    # The clamp current loops back to the input node: remove it from the primary current.
    i_in = avg(i_p) - (avg(v_cl) - v_in) / clamp.r
    duty = fb.ccm_duty(v_in, d.v_or)
    period = 1.0 / SPEC.f_sw
    di = v_in * duty * period / (d.l_m + l_lk)
    assert i_p.max() == pytest.approx(i_in / duty + di / 2.0, rel=0.02)

    # Slope of the primary current in the middle of the last on-time.
    start = math.floor(t[-1] / period - 1e-9) * period - period
    on = (t > start + 0.3 * duty * period) & (t < start + 0.9 * duty * period)
    slope = np.polyfit(t[on], i_p[on], 1)[0]
    assert slope == pytest.approx(v_in / (d.l_m + l_lk), rel=0.01)

    assert avg(v_cl) - v_in == pytest.approx(
        fb.clamp_voltage(l_lk, i_p.max(), SPEC.f_sw, d.v_or, clamp.r), rel=0.1)
    assert avg(v_out) == pytest.approx(SPEC.v_out, rel=0.05)
