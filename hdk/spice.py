"""Minimal ngspice runner used by the tests and examples to cross-check the calculators."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np


def available() -> bool:
    """True when the ngspice executable is on the PATH."""
    return shutil.which("ngspice") is not None


def run(netlist: str, vectors: list[str], timeout: float = 120.0) -> np.ndarray:
    """Run ``netlist`` in batch mode and return the requested vectors.

    The netlist must contain a title line, the circuit and one analysis card
    (``.tran`` or ``.ac``) but no ``.control`` block and no ``.end``.
    The result is an array whose first column is the scale (time or frequency)
    followed by one column per requested vector expression. Use real-valued
    expressions such as ``mag(i(vsense))`` for AC analyses.
    """
    if not available():
        raise RuntimeError("ngspice is not installed")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        out = tmp_path / "out.txt"
        control = (
            ".control\n"
            "set wr_singlescale\n"
            "set wr_vecnames\n"
            "run\n"
            f"wrdata {out} {' '.join(vectors)}\n"
            "quit\n"
            ".endc\n"
        )
        cir = tmp_path / "circuit.cir"
        cir.write_text(netlist.rstrip() + "\n" + control + ".end\n", encoding="utf-8")
        proc = subprocess.run(
            ["ngspice", "-b", str(cir)], capture_output=True, text=True, timeout=timeout
        )
        if not out.exists():
            raise RuntimeError(f"ngspice failed:\n{proc.stdout}\n{proc.stderr}")
        return np.loadtxt(out, skiprows=1, ndmin=2)
