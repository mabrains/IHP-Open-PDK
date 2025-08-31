from typing import List, Optional
from dataclasses import dataclass


@dataclass
class TimingArc:
    out_pin: str
    related_pin: str
    timing_sense: Optional[str]
    timing_type: Optional[str]
    kind: str  # cell_rise, cell_fall, rise_transition, fall_transition
    i: int
    j: int
    slew_ns: Optional[float]
    load_pf: Optional[float]
    value_ns: float


@dataclass
class PowerArc:
    pin: str
    related_pin: str
    kind: str  # rise_power, fall_power
    i: int
    j: int
    slew_ns: Optional[float]
    load_pf: Optional[float]
    value_mw: float


@dataclass
class PinCapacitance:
    pin: str
    direction: Optional[str]
    capacitance: Optional[float]
    rise_capacitance: Optional[float]
    fall_capacitance: Optional[float]
    min_capacitance: Optional[float]
    max_capacitance: Optional[float]


@dataclass
class LeakagePower:
    value: Optional[float]
    when: Optional[str]


@dataclass
class CellSummary:
    cell: str
    area: Optional[float]
    footprint: Optional[str]
    cell_leakage_power: Optional[float]
    leakage_modes: List[LeakagePower]
