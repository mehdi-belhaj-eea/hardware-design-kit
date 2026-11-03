import math

import numpy as np
import pytest
from scipy.integrate import quad

from hdk.magnetics import cores, losses
from hdk.magnetics import transformer as tr
from hdk.power import flyback as fb

MAT = cores.Material("ferrite (test)", b_sat=0.39, pv_ref=375e3, f_ref=100e3, b_ref=0.2,
                     alpha=1.4, beta=2.6)
CORE = cores.Core("EFD20-class (test)", ae=31e-6, le=47e-3, ve=1460e-9, aw=25e-6, mlt=34e-3,
                  winding_width=12.5e-3)
SPEC = fb.FlybackSpec(18.0, 32.0, 15.0, 1.0, 200e3, efficiency=0.85, v_f=0.5, d_max=0.45, k_rp=0.5)


def test_skin_depth():
    assert losses.skin_depth(100e3) == pytest.approx(0.209e-3, rel=0.01)
    assert losses.skin_depth(400e3) == pytest.approx(losses.skin_depth(100e3) / 2.0)
    assert losses.skin_depth(100e3, 100.0) > losses.skin_depth(100e3, 20.0)


def test_steinmetz_reference_point():
    assert losses.steinmetz(MAT, 100e3, 0.2) == pytest.approx(375e3)
    assert losses.steinmetz(MAT, 200e3, 0.1) == pytest.approx(375e3 * 2 ** 1.4 * 0.5 ** 2.6)


def test_igse_equals_steinmetz_for_a_sine():
    f, b_hat = 150e3, 0.08
    ki = losses.igse_ki(MAT)
    period = 1.0 / f

    def integrand(t):
        return abs(2 * math.pi * f * b_hat * math.cos(2 * math.pi * f * t)) ** MAT.alpha

    integral, _ = quad(integrand, 0.0, period, limit=200)
    pv = ki * (2 * b_hat) ** (MAT.beta - MAT.alpha) * integral / period
    assert pv == pytest.approx(losses.steinmetz(MAT, f, b_hat), rel=1e-6)


def test_igse_triangular_closed_form():
    f, db, duty = 200e3, 0.12, 0.3
    expected = (losses.igse_ki(MAT) * db ** MAT.beta * f ** MAT.alpha
                * (duty ** (1 - MAT.alpha) + (1 - duty) ** (1 - MAT.alpha)))
    assert losses.igse_triangular(MAT, f, db, duty) == pytest.approx(expected, rel=1e-9)


def test_flat_segment_adds_no_energy():
    t = 5e-6
    busy = losses.igse_piecewise_linear(MAT, [(0.1, 0.3 * t), (-0.1, 0.4 * t)], 0.7 * t)
    with_flat = losses.igse_piecewise_linear(MAT, [(0.1, 0.3 * t), (-0.1, 0.4 * t), (0.0, 0.3 * t)], t)
    assert with_flat * t == pytest.approx(busy * 0.7 * t)


def test_dowell_factor():
    assert losses.dowell_fr(1e-4, 3) == pytest.approx(1.0, abs=1e-9)
    x = 2.0
    one_layer = (math.sinh(x) + math.sin(x)) / (math.cosh(x) - math.cos(x))
    assert losses.dowell_fr(1.0, 1) == pytest.approx(one_layer)
    assert losses.dowell_fr(1.0, 3) > losses.dowell_fr(1.0, 2) > losses.dowell_fr(1.0, 1)
    # the series expansion and the full formula agree near the switch-over point
    assert losses.dowell_fr(0.999e-3, 4) == pytest.approx(losses.dowell_fr(1.001e-3, 4), rel=1e-6)


def test_harmonics_keep_the_rms_value():
    x = np.where(np.arange(4000) < 1800, np.linspace(1.0, 3.0, 4000), 0.0)
    dc, h = losses.harmonic_rms(x, harmonics=2000)
    assert dc ** 2 + np.sum(h ** 2) == pytest.approx(np.mean(x ** 2), rel=1e-9)


def test_gap_roundtrip_with_and_without_fringing():
    l_target = 29.5e-6
    g0, f0 = tr.gap_length(11, l_target, CORE, fringing=False)
    assert f0 == 1.0
    assert tr.inductance(11, CORE, g0, fringing=False) == pytest.approx(l_target)
    g, f = tr.gap_length(11, l_target, CORE)
    assert tr.inductance(11, CORE, g) == pytest.approx(l_target, rel=1e-9)
    assert f > 1.0 and g > g0


def test_choose_wire():
    d, strands = tr.choose_wire(1.5, 200e3, 5e6, t_c=100.0)
    assert d <= 2.0 * losses.skin_depth(200e3, 100.0)
    assert strands * math.pi * d * d / 4.0 * 5e6 >= 1.5


def test_transformer_design():
    t = tr.design_transformer(SPEC, CORE, MAT, b_max=0.25, j_max=5e6)
    assert t.b_peak <= 0.25
    assert abs(t.n_p / t.n_s - fb.turns_ratio(SPEC)) / fb.turns_ratio(SPEC) <= 0.1
    assert t.converter.n == pytest.approx(t.n_p / t.n_s)
    assert t.primary.current_density <= 5e6 and t.secondary.current_density <= 5e6
    assert 0.0 < t.fill < 0.4
    assert t.primary.p_ac >= t.primary.p_dc and t.secondary.p_ac >= t.secondary.p_dc
    assert t.p_core > 0.0 and t.delta_t > 0.0
    assert tr.inductance(t.n_p, CORE, t.gap) == pytest.approx(t.converter.l_m, rel=1e-9)


def test_idle_layer_factor():
    assert losses.idle_layer_factor(0.0) == 0.0
    assert losses.idle_layer_factor(0.999e-3) == pytest.approx(losses.idle_layer_factor(1.001e-3), rel=1e-5)
    d = 1.3
    s1 = (math.sinh(2 * d) + math.sin(2 * d)) / (math.cosh(2 * d) - math.cos(2 * d))
    s2 = (math.sinh(d) * math.cos(d) + math.cosh(d) * math.sin(d)) / (math.cosh(2 * d) - math.cos(2 * d))
    # Dowell's layer loss with equal fields on both faces: Δ·(2·ς1 − 4·ς2)
    assert losses.idle_layer_factor(d) == pytest.approx(d * (2 * s1 - 4 * s2))


def test_idle_winding_loss_for_a_sine():
    f, i_rms = 200e3, 1.0
    t = np.arange(4000) / 4000.0
    source = np.sqrt(2.0) * i_rms * np.sin(2 * np.pi * t)
    loss = losses.idle_winding_loss(source, f, 22, 0.03, 11, 2, 0.315e-3, 22.0, 12.5e-3, t_c=100.0)
    delta = losses.round_wire_delta(0.315e-3, 22.0, 12.5e-3, f, 100.0)
    assert loss == pytest.approx(0.03 * 2 ** 2 * 2 ** 2 * losses.idle_layer_factor(delta), rel=1e-6)


def test_idle_loss_goes_to_the_inner_winding():
    inner_p = tr.design_transformer(SPEC, CORE, MAT, inner="primary")
    inner_s = tr.design_transformer(SPEC, CORE, MAT, inner="secondary")
    assert inner_p.primary.p_idle > 0.0 and inner_p.secondary.p_idle == 0.0
    assert inner_s.secondary.p_idle > 0.0 and inner_s.primary.p_idle == 0.0
    assert inner_p.p_copper == pytest.approx(inner_p.primary.p_ac + inner_p.primary.p_idle
                                             + inner_p.secondary.p_ac)
    with pytest.raises(ValueError):
        tr.design_transformer(SPEC, CORE, MAT, inner="middle")


def test_small_core_is_rejected():
    tiny = cores.Core("tiny", ae=2e-6, le=10e-3, ve=20e-9, aw=2e-6, mlt=10e-3, winding_width=3e-3)
    with pytest.raises(ValueError):
        tr.design_transformer(SPEC, tiny, MAT, b_max=0.25, ratio_tolerance=0.01, n_s_max=5)
