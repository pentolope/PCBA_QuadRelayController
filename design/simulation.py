"""Circuit scenarios, and what each one is allowed to establish.

Two questions the schematic can answer before any copper exists: whether the
logic rail survives four coils energising at once, and whether the drivers are
held off when nothing drives their gates. Both are re-asked after layout with
the coil supply's real copper substituted for the budget it was designed
against.
"""
from __future__ import annotations

import json
import os
import sys

from . import layout, netlist, rules

REPO_ROOT = layout.REPO_ROOT
SIM_DIR = os.path.join(REPO_ROOT, "sim")
PARAMETERS_PATH = os.path.join(REPO_ROOT, "components", "parameters.json")

#: The name the manifest registers the extracted copper model under. The
#: measured identity embeds the board digest, so only an alias can be written
#: into a stored scenario.
EXTRACTED_MODEL_ALIAS = "coil_supply_copper"

#: How long the rail is watched after the coils are switched on.
DROOP_WINDOW_S = 2.0e-3


def _parameters():
    with open(PARAMETERS_PATH, encoding="utf-8") as handle:
        return json.load(handle)


def _sum_capacitance(*nets):
    total = 0.0
    for net in nets:
        for pin_ref in netlist.NETS[net]:
            reference = pin_ref.split(".", 1)[0]
            if reference.startswith("C"):
                total += rules._capacitance_farads(reference)
    return total


def _ideal(records):
    return {name: {"stands_in_for": detail,
                   "accepted_for_design_decision": True}
            for name, detail in records.items()}


def _measurement(name, kind, node, op=None, value=None, knowledge=None):
    record = {"name": name, "kind": kind, "node": node}
    if op is not None:
        record["assertion"] = {"op": op, "value": value}
    if knowledge is not None:
        record["knowledge"] = knowledge
    return record


def rail_droop_scenario(parameters, model_identity=None):
    """Four coils energising at once, against the supply path budget.

    Pre-layout the path between the input terminal and the coils is one
    budgeted resistance. Post-layout the board's own copper is measured and
    put in series with it - but the extraction omits via barrel resistance, so
    the measured copper is a LOWER bound and every rail voltage computed from
    it is an UPPER bound. An upper bound settles "never exceeds the maximum"
    and cannot settle "stays above the brown-out level", so the post-layout
    form asserts only the first and reports the second as a measurement.
    """
    supply = rules.Supply(parameters)
    mcu = parameters["parts"][rules._mpn("U1")]
    brown_out = mcu["reset"]["brown_out_thresholds_v"][
        netlist.BROWN_OUT_OPTION]["rising_max"]["value"]
    extracted = model_identity is not None
    feed_node = "path" if extracted else "rail"
    elements = [
        {"kind": "vsource_dc", "name": "SRC", "nodes": ["src", "0"],
         "value": supply.input_min_v},
        {"kind": "resistor", "name": "RPATH", "nodes": ["src", feed_node],
         "value": netlist.INPUT_PATH_BUDGET_OHM + supply.pfet_rds_on_ohm},
    ]
    if extracted:
        elements.append({"kind": "model_instance", "name": "COPPER",
                         "nodes": ["path", "rail"], "model": model_identity})
    elements.extend([
        {"kind": "capacitor", "name": "CBULK", "nodes": ["rail", "0"],
         "value": _sum_capacitance("VCOIL", "+5V")},
        {"kind": "resistor", "name": "RCOILS", "nodes": ["rail", "sink"],
         "value": supply.coil_resistance_min_ohm / netlist.CHANNEL_COUNT},
        {"kind": "vsource_pulse", "name": "SWITCH", "nodes": ["sink", "0"],
         "pulse": {"v1": supply.input_min_v, "v2": 0.0,
                   "delay_s": DROOP_WINDOW_S / 20.0,
                   "rise_s": 1e-9, "fall_s": 1e-9,
                   "width_s": DROOP_WINDOW_S, "period_s": 2 * DROOP_WINDOW_S}},
        {"kind": "resistor", "name": "RLOGIC", "nodes": ["rail", "logic"],
         "value": supply.series_ohm},
        {"kind": "resistor", "name": "RMCU", "nodes": ["logic", "0"],
         "value": supply.input_min_v / supply.mcu_current_max_a},
    ])
    ideal = {
        "SRC": "the external supply held at the low end of the board's "
               "declared input range, as an ideal source with no output "
               "impedance of its own",
        "RPATH": "the field wiring, the source and the reverse-polarity "
                 "device as one series resistance; the wiring part is a "
                 "budget this board states rather than measures",
        "CBULK": "every bulk and decoupling capacitance on the coil supply "
                 "and the logic rail as one ideal capacitor, with no ESR, no "
                 "ESL and no DC bias derating",
        "RCOILS": "all four coils as one resistance at the low end of their "
                  "tolerance, which draws more than four real coils would",
        "SWITCH": "the instant firmware energises every channel at once, as "
                  "an ideal switch with no on-resistance",
        "RLOGIC": "the series element between the coil supply and the logic "
                  "rail, at its nominal value",
        "RMCU": "the MCU's draw as a fixed resistance at the datasheet's own "
                "maximum current into VCC, which is far above its stated "
                "typical consumption",
    }
    scenario = {
        "name": ("rail_droop_over_extracted_copper" if extracted
                 else "rail_droop_on_all_coils_energising"),
        "elements": elements,
        "analyses": [{"kind": "tran", "step_s": DROOP_WINDOW_S / 2000.0,
                      "stop_s": DROOP_WINDOW_S}],
        "assumptions": _ideal(ideal),
    }
    ceiling = mcu["supply"]["characterised_max_v"]["value"]
    if not extracted:
        scenario["measurements"] = [
            _measurement("logic_rail_minimum", "tran_min_voltage", "logic",
                         ">=", brown_out),
            _measurement("logic_rail_maximum", "tran_max_voltage", "logic",
                         "<=", ceiling),
        ]
        return scenario
    bound = {
        "kind": "upper_bound",
        "basis": {
            "kind": "assumed",
            "detail": "the extracted copper resistance is a lower bound - "
                      "via barrel resistance is omitted by the extraction - "
                      "and the rail falls monotonically with series "
                      "resistance, so every simulated rail voltage bounds "
                      "the true one from above",
        },
    }
    scenario["measurements"] = [
        _measurement("logic_rail_maximum", "tran_max_voltage", "logic",
                     "<=", ceiling, knowledge=bound),
        _measurement("logic_rail_minimum", "tran_min_voltage", "logic",
                     knowledge=bound),
    ]
    scenario["required_coverage"] = {
        "interconnect_dc": ["geometry-derived", "quasi-static-extracted",
                            "full-wave-extracted", "measured"]}
    return scenario


def gate_hold_off_scenario(parameters):
    """The gate with nothing driving it, against a worst-case pull-up.

    The datasheet says every port is a floating input after reset, so the
    real reset case is the pull-down alone. This asks the stronger question:
    what the gate reaches if an internal pull-up is enabled at the lowest
    resistance the datasheet permits.
    """
    supply = rules.Supply(parameters)
    mcu = parameters["parts"][rules._mpn("U1")]
    nfet = parameters["parts"][rules._mpn("Q1")]
    return {
        "name": "driver_gate_held_off_against_a_worst_case_pull_up",
        "elements": [
            {"kind": "vsource_dc", "name": "RAIL", "nodes": ["rail", "0"],
             "value": supply.logic_rail_max_v},
            {"kind": "resistor", "name": "RPULLUP", "nodes": ["rail", "pin"],
             "value": mcu["pull_resistor_ohm"]["min"]["value"]},
            {"kind": "resistor", "name": "RSERIES", "nodes": ["pin", "gate"],
             "value": rules._resistor_ohms("R1")},
            {"kind": "resistor", "name": "RPULLDOWN", "nodes": ["gate", "0"],
             "value": rules._resistor_ohms("R5")},
        ],
        "analyses": [{"kind": "op"}],
        "measurements": [
            _measurement("gate_voltage", "op_voltage", "gate", "<=",
                         nfet["fet"]["vgs_threshold_min_v"]["value"]),
        ],
        "assumptions": _ideal({
            "RAIL": "the logic rail at the top of its declared range",
            "RPULLUP": "an internal pull-up at the lowest resistance the "
                       "datasheet permits, which is stronger than the "
                       "floating input the reset state actually gives",
            "RSERIES": "the gate series resistor at its nominal value",
            "RPULLDOWN": "the gate pull-down at its nominal value, with no "
                         "tolerance and no temperature coefficient",
        }),
    }


def _write(path, document):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(document, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return path


def write():
    parameters = _parameters()
    written = []
    for name, document in (
            ("pre_layout_rail_droop.json", rail_droop_scenario(parameters)),
            ("pre_layout_gate_hold_off.json",
             gate_hold_off_scenario(parameters)),
            ("post_layout_rail_droop.json",
             rail_droop_scenario(parameters, EXTRACTED_MODEL_ALIAS))):
        written.append(_write(os.path.join(SIM_DIR, name), document))
    return written


if __name__ == "__main__":
    for path in write():
        sys.stdout.write(path + "\n")
