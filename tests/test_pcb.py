import math

import pytest

from hdk.pcb import insulation as ins
from hdk.pcb import traces

OZ = 35e-6


def test_ipc2221_known_point():
    # 1 A, 10 °C rise, 1 oz, external layer: about 12 mil (0.30 mm)
    assert traces.ipc2221_width(1.0, OZ, 10.0) == pytest.approx(0.30e-3, rel=0.02)


def test_ipc2221_roundtrip_and_layers():
    w = traces.ipc2221_width(5.0, OZ, 20.0)
    assert traces.ipc2221_current(w, OZ, 20.0) == pytest.approx(5.0)
    assert traces.ipc2221_width(5.0, OZ, 20.0, external=False) > w
    assert traces.ipc2221_width(5.0, 2 * OZ, 20.0) == pytest.approx(w / 2.0)


def test_trace_resistance_and_via():
    assert traces.trace_resistance(1e-3, OZ, 0.1) == pytest.approx(1.72e-8 * 0.1 / (1e-3 * OZ))
    assert traces.trace_resistance(1e-3, OZ, 0.1, t_c=120.0) > traces.trace_resistance(1e-3, OZ, 0.1)
    # plating grows inside the drilled hole: annulus between d/2 − t and d/2
    d, t = 0.3e-3, 25e-6
    area = math.pi * ((d / 2) ** 2 - (d / 2 - t) ** 2)
    assert traces.via_current(d, t) == pytest.approx(0.024 * 10 ** 0.44 * (area / traces.MIL ** 2) ** 0.725)
    assert 0.8 < traces.via_current(0.3e-3) < 0.9


def test_ipc2221_range():
    assert traces.in_ipc2221_range(traces.ipc2221_width(5.0, OZ, 10.0), 5.0)
    assert not traces.in_ipc2221_range(traces.ipc2221_width(10.0, OZ, 10.0, external=False), 10.0)
    assert not traces.in_ipc2221_range(1e-3, 40.0)


def test_rated_impulse_voltage():
    assert ins.rated_impulse_voltage(230.0, 2) == 2500.0
    assert ins.rated_impulse_voltage(120.0, 3) == 2500.0
    assert ins.rated_impulse_voltage(48.0, 1) == 330.0
    with pytest.raises(ValueError):
        ins.rated_impulse_voltage(230.0, 5)


def test_clearance():
    assert ins.clearance(2500.0, 2) == pytest.approx(1.5)
    assert ins.clearance(500.0, 2) == pytest.approx(0.2)       # pollution degree 2 minimum
    assert ins.clearance(500.0, 1) == pytest.approx(0.04)
    assert ins.clearance(2500.0, 2, reinforced=True) == pytest.approx(3.0)   # 4 kV row
    assert ins.clearance(2500.0, 2, altitude_m=3000.0) == pytest.approx(1.5 * 1.14)
    # outside the preferred series, reinforced insulation takes 160 % of the impulse voltage
    assert ins.reinforced_impulse(3000.0) == pytest.approx(4800.0)
    assert ins.clearance(3000.0, 2, reinforced=True) == pytest.approx(4.0)     # 5 kV row
    assert ins.reinforced_impulse(2500.0) == 4000.0


def test_altitude_factor():
    assert ins.altitude_factor(0.0) == 1.0
    assert ins.altitude_factor(2500.0) == pytest.approx(1.07)
    assert ins.altitude_factor(10000.0) == pytest.approx(3.02)
    with pytest.raises(ValueError):
        ins.altitude_factor(25000.0)


def test_creepage():
    assert ins.creepage_pwb(400.0) == pytest.approx(2.0)
    assert ins.creepage_pwb(300.0) == pytest.approx(1.0 + (300 - 250) / (320 - 250) * 0.6)
    assert ins.creepage_pwb(400.0, reinforced=True) == pytest.approx(4.0)
    assert ins.creepage_pwb(400.0, pollution_degree=1) == pytest.approx(1.0)
    with pytest.raises(NotImplementedError):
        ins.creepage_pwb(400.0, pollution_degree=3)


def test_creepage_never_below_clearance():
    s = ins.spacing(230.0, 2, 400.0, 2, altitude_m=10000.0)
    assert s.clearance == pytest.approx(1.5 * 3.02)
    assert s.creepage == pytest.approx(s.clearance)
    r = ins.spacing(230.0, 2, 400.0, 2, reinforced=True)
    assert (r.clearance, r.creepage) == pytest.approx((3.0, 4.0))
