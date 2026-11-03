"""hardware-design-kit — design calculators for the power side of an electronic board.

Input protections and EMI filters (hdk.protection, hdk.emi), flyback converter and
transformer (hdk.power, hdk.magnetics), measurement chains (hdk.measure) and PCB
rules (hdk.pcb).

Every calculator is a small, documented function based on textbook equations.
The test suite cross-checks the analytic results against ngspice simulations.

Values used in the examples are illustrative. They are not taken from any
industrial project.
"""

__version__ = "0.2.0"
