"""Small helpers for decibels and impedances."""

from __future__ import annotations

import numpy as np

TWO_PI = 2.0 * np.pi


def db20(x):
    """Magnitude in dB (20·log10|x|)."""
    return 20.0 * np.log10(np.abs(x))


def undb20(db):
    """Inverse of :func:`db20`."""
    return 10.0 ** (np.asarray(db, dtype=float) / 20.0)


def to_dbua(i_amps):
    """Current in dBµA."""
    return 20.0 * np.log10(np.abs(i_amps) / 1e-6)


def to_dbuv(v_volts):
    """Voltage in dBµV."""
    return 20.0 * np.log10(np.abs(v_volts) / 1e-6)


def from_dbua(db):
    """dBµA to amperes."""
    return 1e-6 * undb20(db)


def from_dbuv(db):
    """dBµV to volts."""
    return 1e-6 * undb20(db)


def parallel(*impedances):
    """Parallel combination of complex impedances (scalars or arrays)."""
    total = 0.0
    for z in impedances:
        total = total + 1.0 / np.asarray(z, dtype=complex)
    return 1.0 / total
