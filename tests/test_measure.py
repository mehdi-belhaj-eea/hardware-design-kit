import pytest

from hdk.measure import adc, budget, divider, shunt


def test_e96_series():
    assert len(divider.E96) == 96
    assert list(divider.E96) == sorted(divider.E96)
    assert divider.e96_floor(6284.0) == 6190.0
    assert divider.e96_nearest(250e3) == 249e3


def test_divider_design_uses_the_range():
    d = divider.design_divider(500.0, 3.3, r_top_total=1e6, n_top=4, headroom=0.95)
    assert d.r_top_each == 249e3 and d.n_top == 4
    assert d.v_out(500.0) <= 0.95 * 3.3
    values = divider.e96_values()
    bigger = values[values.index(d.r_bottom) + 1]
    assert 500.0 * bigger / (d.r_top + bigger) > 0.95 * 3.3
    assert d.v_top_each(500.0) == pytest.approx(500.0 * 249e3 / (d.r_top + d.r_bottom))


def test_divider_tolerance_term_matches_perturbation():
    d = divider.Divider(249e3, 4, 6190.0)
    tol = 1e-3
    worst = divider.Divider(249e3 * (1 - tol), 4, 6190.0 * (1 + tol))
    term = divider.divider_terms(d, tol, 25.0, 50.0)[0]
    assert worst.ratio / d.ratio - 1.0 == pytest.approx(term.value, rel=0.01)


def test_budget_sums():
    b = budget.Budget("test", (budget.ErrorTerm("a", 0.003, calibratable=True),
                               budget.ErrorTerm("b", -0.004)))
    assert b.worst_case() == pytest.approx(0.007)
    assert b.rss() == pytest.approx(0.005)
    assert b.worst_case(calibrated=True) == pytest.approx(0.004)
    assert b.largest().name == "b"


def test_adc_helpers():
    assert adc.lsb(3.3, 12) == pytest.approx(3.3 / 4096)
    c_f = adc.min_filter_capacitance(15e-12, 12)
    assert adc.kickback_error(15e-12, c_f) == pytest.approx(0.5 / 4096)
    assert adc.settling_time(1e-6, 12) == pytest.approx(1e-6 * 13 * 0.6931471805599453)
    assert adc.quantization_error(12) == pytest.approx(0.5 / 4096)


def test_sampling_load():
    f_max = adc.max_sample_rate(6150.0, 15e-12, 12)
    assert adc.sampling_load_error(6150.0, 15e-12, f_max) == pytest.approx(0.5 / 4096)
    x = 6150.0 * 15e-12 * 10e3
    assert adc.sampling_load_error(6150.0, 15e-12, 10e3) == pytest.approx(x / (1 + x))
    # a larger filter capacitor does not appear: only R, C_s and the sample rate matter
    assert 500.0 < f_max < 1500.0


def test_adc_terms_with_a_mid_scale_zero():
    plain = {t.name: t for t in divider.adc_terms(12, 3.3, 1.0, 0.001, 20.0, 50.0, 0.001, 2.0, 1.0)}
    bipolar = {t.name: t for t in divider.adc_terms(12, 3.3, 1.0, 0.001, 20.0, 50.0, 0.001, 2.0, 1.0,
                                                    v_zero=1.65)}
    assert "ADC gain error on the zero level" not in plain
    assert bipolar["ADC gain error on the zero level"].value == pytest.approx(0.001 * 1.65)
    assert bipolar["ADC gain error on the zero level"].calibratable


def test_shunt_chain():
    c = shunt.ShuntChain(1e-3, 50.0, 1.65, 3.3)
    assert c.v_out(20.0) == pytest.approx(2.65)
    assert c.i_max_positive == pytest.approx(33.0)
    assert c.power(10.0) == pytest.approx(0.1)
    terms = {t.name: t for t in shunt.shunt_terms(c, 20.0, 0.01, 50.0, 60.0, 100e-6, 0.5e-6, 0.002, 10.0)}
    assert terms["amplifier offset"].value == pytest.approx(100e-6 / (1e-3 * 20.0))
    assert terms["shunt drift"].value == pytest.approx(50e-6 * 60.0)
    assert terms["shunt tolerance"].calibratable and not terms["shunt drift"].calibratable
