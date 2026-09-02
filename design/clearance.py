"""Insulation coordination for the switched/logic boundary.

Everything the board separates the two halves by is derived here, from the
frozen tables, and nowhere else: the design rules KiCad enforces, the figures
the documentation quotes and the checks in `rules.py` all read these values.

The tables are IEC 60664-1's, as reproduced in the two Texas Instruments
seminar papers this repository freezes (SLUP419 and SLUP421, "Demystifying
Clearance and Creepage Distance for High-Voltage End Equipment"). The papers
carry only four working-voltage rows, and state that linear interpolation
between the nearest two points is permitted and that reinforced creepage is
twice basic; both of those rules are applied below rather than assumed.
"""
from __future__ import annotations

import json
import os

from . import netlist

EVIDENCE_DOCUMENT = "clearance_creepage_ti_slup421"
CORROBORATING_DOCUMENT = "clearance_creepage_ti_slup419"

#: IEC 60664-1 Table F.4 (creepage, mm), pollution degree 2, by material
#: group, at the working voltages the frozen subset lists.
CREEPAGE_PD2_MM = {
    "I": {63.0: 0.63, 400.0: 2.0, 800.0: 4.0, 1000.0: 5.0},
    "II": {63.0: 0.90, 400.0: 2.8, 800.0: 5.6, 1000.0: 7.1},
    "III": {63.0: 1.25, 400.0: 4.0, 800.0: 8.0, 1000.0: 10.0},
}

#: IEC 60664-1 Table F.1: rated impulse voltage (V peak) by mains voltage
#: line to neutral and overvoltage category.
IMPULSE_V = {
    50.0: {"I": 330, "II": 500, "III": 800, "IV": 1500},
    150.0: {"I": 800, "II": 1500, "III": 2500, "IV": 4000},
    300.0: {"I": 1500, "II": 2500, "III": 4000, "IV": 6000},
    600.0: {"I": 2500, "II": 4000, "III": 6000, "IV": 8000},
}

#: IEC 60664-1 Table F.2: minimum clearance (mm) at pollution degree 2, by
#: rated impulse withstand voltage (V peak).
CLEARANCE_PD2_MM = {500: 0.2, 1500: 0.5, 2500: 1.5, 4000: 3.0, 6000: 5.5}

#: Conditions the derivation is made under. Each is an assumption about how
#: the board is installed, not something the board can establish by itself.
POLLUTION_DEGREE = 2
MATERIAL_GROUP = "III"
OVERVOLTAGE_CATEGORY = "II"

WORKING_VOLTAGE_V = netlist.SWITCHED_RATING["voltage_rms_v"]


def _interpolate(table, voltage):
    """Linear interpolation between the nearest two rows, as the source allows."""
    points = sorted(table)
    if voltage <= points[0]:
        return table[points[0]]
    for low, high in zip(points, points[1:]):
        if voltage <= high:
            span = high - low
            return table[low] + (table[high] - table[low]) * (voltage - low) / span
    raise ValueError("working voltage %g V is above the frozen table" % voltage)


def basic_creepage_mm(voltage_v=None):
    return _interpolate(CREEPAGE_PD2_MM[MATERIAL_GROUP],
                        WORKING_VOLTAGE_V if voltage_v is None else voltage_v)


def reinforced_creepage_mm(voltage_v=None):
    return 2.0 * basic_creepage_mm(voltage_v)


def _impulse_row(voltage_v):
    for limit in sorted(IMPULSE_V):
        if voltage_v <= limit:
            return IMPULSE_V[limit]
    raise ValueError("working voltage %g V is above the frozen table"
                     % voltage_v)


def basic_clearance_mm(voltage_v=None):
    voltage = WORKING_VOLTAGE_V if voltage_v is None else voltage_v
    impulse = _impulse_row(voltage)[OVERVOLTAGE_CATEGORY]
    return CLEARANCE_PD2_MM[impulse]


def reinforced_clearance_mm(voltage_v=None):
    """One step up the impulse column, per IEC 60664-1 section 5.1.6."""
    voltage = WORKING_VOLTAGE_V if voltage_v is None else voltage_v
    row = _impulse_row(voltage)
    order = ["I", "II", "III", "IV"]
    index = order.index(OVERVOLTAGE_CATEGORY)
    if index + 1 >= len(order):
        raise ValueError("no category above " + OVERVOLTAGE_CATEGORY)
    return CLEARANCE_PD2_MM[row[order[index + 1]]]


def _ceil_to(value, step):
    return step * (int(value / step) + (1 if value % step else 0))


#: What the board actually keeps. Both are rounded up from the derived
#: requirement to a round figure the layout can be checked against, and the
#: reinforced figure is additionally at least the relay's own stated
#: contact-to-coil clearance and creepage, so the PCB is not the weaker
#: element of the barrier the relay forms.
RELAY_STATED_ISOLATION_MM = 8.0

WITHIN_CHANNEL_MM = _ceil_to(
    max(basic_creepage_mm(), basic_clearance_mm()), 0.1)
BOUNDARY_MM = max(
    _ceil_to(max(reinforced_creepage_mm(), reinforced_clearance_mm()), 0.5),
    RELAY_STATED_ISOLATION_MM)

SWITCHED_TRACK_MM = 2.0


def requirement_record():
    """Every number the board's separation claim rests on, and where from."""
    return {
        "document": EVIDENCE_DOCUMENT,
        "corroborating_document": CORROBORATING_DOCUMENT,
        "standard": "IEC 60664-1 tables F.1, F.2 and F.4",
        "working_voltage_rms_v": WORKING_VOLTAGE_V,
        "pollution_degree": POLLUTION_DEGREE,
        "material_group": MATERIAL_GROUP,
        "overvoltage_category": OVERVOLTAGE_CATEGORY,
        "basic_creepage_mm": basic_creepage_mm(),
        "reinforced_creepage_mm": reinforced_creepage_mm(),
        "basic_clearance_mm": basic_clearance_mm(),
        "reinforced_clearance_mm": reinforced_clearance_mm(),
        "relay_stated_isolation_mm": RELAY_STATED_ISOLATION_MM,
        "within_channel_design_mm": WITHIN_CHANNEL_MM,
        "boundary_design_mm": BOUNDARY_MM,
    }


RECORD_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "constraints", "insulation.json")


def write_record():
    """The derivation, as a committed record rather than only as code.

    The brief requires the rating, the standard the clearance was derived
    from and the resulting dimension to be documented; this is that document,
    in the form a later reader can check the board against.
    """
    os.makedirs(os.path.dirname(RECORD_PATH), exist_ok=True)
    with open(RECORD_PATH, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(requirement_record(), handle, indent=2, sort_keys=True)
        handle.write("\n")
    return RECORD_PATH


def rules_text():
    """The board's clearance policy as design rules KiCad enforces.

    The conditions match net names rather than net classes: a net class is a
    project-file property, and `kicad-cli pcb drc` - the tool that judges this
    board - assigns every net to Default regardless of what the project
    declares, so a class-based rule would silently match nothing. Net names
    are on the board itself and were verified to match.

    The two conditions of each pair are mutually exclusive, so which rule
    applies never depends on the order they are written in.
    """
    lines = [
        "(version 1)",
        "",
        "# Generated by design/clearance.py. Do not edit: the numbers are",
        "# derived from the frozen IEC 60664-1 subsets, and the layout, the",
        "# documentation and rules.py read the same derivation.",
    ]
    for channel in range(1, netlist.CHANNEL_COUNT + 1):
        pattern = "CH%d_*" % channel
        lines += [
            "",
            '(rule "functional_insulation_ch%d"' % channel,
            "\t(constraint clearance (min %gmm))" % WITHIN_CHANNEL_MM,
            "\t(condition \"A.NetName == '%s' && B.NetName == '%s'\"))"
            % (pattern, pattern),
            "",
            '(rule "reinforced_insulation_ch%d"' % channel,
            "\t(constraint clearance (min %gmm))" % BOUNDARY_MM,
            "\t(condition \"A.NetName == '%s' && B.NetName != '%s'\"))"
            % (pattern, pattern),
        ]
    return "\n".join(lines) + "\n"


def channel_net_pattern(channel):
    return "CH%d_*" % channel
