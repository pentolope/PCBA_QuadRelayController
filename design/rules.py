"""Board-level electrical checks, stated as claims with their evidence.

Every number here comes from `components/parameters.json` (which cites the
frozen document it was read from), from the netlist, or from the board's own
geometry. Nothing is asserted that a document, a component value or a
measurement does not support, and a quantity that cannot be established is
reported as UNKNOWN rather than assumed.
"""
from __future__ import annotations

import json
import os
import re
import sys

from . import clearance, layout, netlist

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARAMETERS_PATH = os.path.join(REPO_ROOT, "components", "parameters.json")
TOOLKIT_ROOT = os.path.join(REPO_ROOT, "tooling", "PCBA_AutoDesignAndTest")
FOOTPRINT_ROOT = "/usr/share/kicad/footprints"

if TOOLKIT_ROOT not in sys.path:
    sys.path.insert(0, TOOLKIT_ROOT)

from pcbqa import claim  # noqa: E402

DIRECT = "direct"
ASSUMED = "assumed"
DERIVED = "derived"

EVIDENCE_CLASSES = {
    DIRECT: "datasheet-behavioral",
    ASSUMED: "assumed-behavioral",
    DERIVED: "design-source",
}

BRIEF = "BRIEF.md"

#: Nets that must reach a probe, from the brief's bring-up requirement.
PROBE_REQUIRED_NETS = ("V5IN", "VCOIL", "+5V", "GND") + tuple(
    "RLY%d_%s" % (channel, node)
    for channel in range(1, netlist.CHANNEL_COUNT + 1)
    for node in ("G", "C"))

#: Every conductor that enters the board on the logic side, and the connector
#: it enters through. Each one has to survive ESD and a hot connection.
def entering_conductors():
    entering = {}
    for reference, functions in netlist.CONNECTOR_FUNCTION_NETS.items():
        for net in functions.values():
            entering.setdefault(net, []).append(reference)
    return {net: sorted(refs) for net, refs in entering.items()}


#: A conductor that needs no clamp of its own, and why.
ESD_EXEMPT = {
    "GND": "the reference the clamps divert into",
    "+5V": "clamped at V5IN, and reachable from a connector only through the "
           "series element that feeds it",
}


def load_parameters():
    with open(PARAMETERS_PATH, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _mpn(reference):
    return netlist.PARTS[reference]["mpn"]


def _spec(parameters, reference):
    return parameters["parts"][_mpn(reference)]


def _pin_map():
    mapping = {}
    for net_name, pin_refs in netlist.NETS.items():
        for pin_ref in pin_refs:
            mapping[pin_ref] = net_name
    return mapping


def _evidence(basis, documents, assumptions=(), omissions=()):
    provenance = {"source": "components/parameters.json",
                  "documents": sorted(set(documents))}
    return claim.evidence(
        "device_electrical", EVIDENCE_CLASSES.get(basis, "design-source"),
        provenance, assumptions=list(assumptions),
        omitted_contributions=list(omissions))


def _requirement(name, op, value):
    return claim.requirement(name, BRIEF, {"op": op, "value": value})


def _claim(identity, units, significance, value, basis, documents,
           requirement, knowledge=claim.EXACT, scope_level="net",
           assumptions=(), omissions=()):
    if value is None:
        return claim.claim(
            scope_level, identity, units, claim.UNKNOWN, {},
            _evidence(basis, documents, assumptions, omissions),
            significance, None, requirement)
    basis_record = None
    if knowledge != claim.EXACT:
        basis_record = claim.knowledge_basis(
            basis, "datasheet_limit" if basis == DIRECT else basis)
    return claim.claim(
        scope_level, identity, units, knowledge, {"value": value},
        _evidence(basis, documents, assumptions, omissions),
        significance, basis_record, requirement)


def _structural(identity, significance, violations, requirement_name,
                documents=(), basis=DERIVED):
    """A count of violations: zero is the only acceptable answer."""
    return _claim(identity, "violations", significance, float(len(violations)),
                  basis, documents, _requirement(requirement_name, "<=", 0.0))


def _resistor_ohms(reference):
    value = netlist.PARTS[reference]["value"]
    if value.endswith("k"):
        return float(value[:-1]) * 1e3
    if value.endswith("R"):
        return float(value[:-1])
    if "R" in value:
        whole, _, fraction = value.partition("R")
        return float("%s.%s" % (whole, fraction or "0"))
    raise ValueError("resistor %s carries the unparsable value %r"
                     % (reference, value))


def _capacitance_farads(reference):
    value = netlist.PARTS[reference]["value"]
    if value.endswith("uF"):
        return float(value[:-2]) * 1e-6
    if value.endswith("nF"):
        return float(value[:-2]) * 1e-9
    raise ValueError("capacitor %s carries the unparsable value %r"
                     % (reference, value))


# ---------------------------------------------------------------------------
# the supply model every rail claim is built on

class Supply:
    """Worst-case rail voltages and currents, from parameters and values.

    Currents are upper bounds: each is computed at the highest rail and the
    lowest resistance the tolerance permits, so nothing downstream can be
    under-stated. The MCU's own consumption is bounded by the datasheet's
    maximum for current into VCC rather than by a typical, because the
    datasheet states no maximum for run-mode consumption.
    """

    def __init__(self, parameters):
        self.parameters = parameters
        relay = parameters["parts"][_mpn("K1")]
        mcu = parameters["parts"][_mpn("U1")]
        pfet = parameters["parts"][_mpn("Q5")]
        led = parameters["parts"][_mpn("D5")]
        self.documents = {"g2rl_omron", "py32f003_puya", "ao3401a_aos",
                          "kt0603r_kento"}

        self.input_min_v = netlist.INPUT_SUPPLY["min_v"]
        self.input_max_v = netlist.INPUT_SUPPLY["max_v"]

        tolerance = relay["coil"]["resistance_tolerance"]["value"]
        nominal = relay["coil"]["resistance_ohm"]["value"]
        self.coil_resistance_min_ohm = nominal * (1.0 - tolerance)
        self.coil_resistance_max_ohm = nominal * (1.0 + tolerance)
        self.coil_current_max_a = self.input_max_v / self.coil_resistance_min_ohm

        self.pfet_rds_on_ohm = pfet["fet"]["rds_on_ohm"]["4.5"]["value"]
        self.mcu_current_max_a = mcu["supply"]["max_supply_current_a"]["value"]

        # The indicator draws no more than the rail across its series
        # resistor: no forward-voltage figure is needed for an upper bound.
        self.indicator_current_max_a = (
            self.input_max_v / _resistor_ohms("R13"))
        self.led_current_max_a = self.input_max_v / _resistor_ohms("R9")
        self.gate_current_max_a = self.input_max_v / (
            _resistor_ohms("R1") + _resistor_ohms("R5"))
        self.led = led

        self.total_current_max_a = (
            netlist.CHANNEL_COUNT * self.coil_current_max_a
            + self.mcu_current_max_a + self.indicator_current_max_a)

        self.pfet_drop_max_v = self.total_current_max_a * self.pfet_rds_on_ohm
        # The field wiring and the source are not on this board, so their
        # resistance is a declared budget rather than a measurement. It is
        # carried in the model instead of being omitted from it: an omitted
        # contribution would make every rail figure an upper bound, and an
        # upper bound cannot show a rail stays above a threshold.
        self.input_path_drop_max_v = (self.total_current_max_a
                                      * netlist.INPUT_PATH_BUDGET_OHM)
        self.coil_rail_min_v = (self.input_min_v - self.pfet_drop_max_v
                                - self.input_path_drop_max_v)
        self.coil_rail_max_v = self.input_max_v

        self.series_ohm = _resistor_ohms(netlist.LOGIC_RAIL_SERIES_REFERENCE)
        self.series_drop_max_v = self.mcu_current_max_a * self.series_ohm
        self.logic_rail_min_v = self.coil_rail_min_v - self.series_drop_max_v
        self.logic_rail_max_v = self.coil_rail_max_v

        self.coil_voltage_min_v = self.coil_rail_min_v - (
            self.coil_current_max_a
            * parameters["parts"][_mpn("Q1")]["fet"]["rds_on_ohm"]["2.5"]["value"])


# ---------------------------------------------------------------------------
# drive

def evaluate_gate_drive(parameters):
    """The driver is fully on at the level the MCU guarantees."""
    supply = Supply(parameters)
    mcu = _spec(parameters, "U1")
    nfet = _spec(parameters, "Q1")
    results = []
    characterised_vgs_v = min(float(key)
                              for key in nfet["fet"]["rds_on_ohm"])
    for channel in range(1, netlist.CHANNEL_COUNT + 1):
        pin = netlist.CHANNEL_COMMAND_PINS[channel - 1]
        output = mcu["digital_outputs"][pin]
        series = _resistor_ohms("R%d" % channel)
        pulldown = _resistor_ohms("R%d" % (channel + 4))
        pin_v = supply.logic_rail_min_v + output["voh_min"][
            "offset_from_supply"]
        gate_v = pin_v * pulldown / (series + pulldown)
        results.append({
            "id": "driver_fully_on_at_guaranteed_drive",
            "identity": "RLY%d_G" % channel,
            "measured_v": gate_v,
            "claim": _claim(
                "RLY%d_G" % channel, "V", "gate_drive", gate_v, DIRECT,
                ("py32f003_puya", "ao3400a_aos"),
                _requirement("gate_at_or_above_characterised_drive", ">=",
                             characterised_vgs_v),
                assumptions=(
                    "the output high level is the datasheet minimum at its "
                    "stated 8 mA test current; the pin sources less than "
                    "that here, and the level can only be higher",)),
        })
    return results


def evaluate_hold_off(parameters):
    """The coil is de-energised whenever the MCU pin is not driving.

    Evaluated against an internal pull-up at its minimum, not against the
    reset state: the datasheet says every port is a floating input after
    reset, and this asks the stronger question of what happens if one is not.
    """
    supply = Supply(parameters)
    mcu = _spec(parameters, "U1")
    nfet = _spec(parameters, "Q1")
    threshold_v = nfet["fet"]["vgs_threshold_min_v"]["value"]
    pull_up_ohm = mcu["pull_resistor_ohm"]["min"]["value"]
    results = []
    for channel in range(1, netlist.CHANNEL_COUNT + 1):
        series = _resistor_ohms("R%d" % channel)
        pulldown = _resistor_ohms("R%d" % (channel + 4))
        gate_v = supply.logic_rail_max_v * pulldown / (
            pull_up_ohm + series + pulldown)
        results.append({
            "id": "driver_held_off_when_the_pin_does_not_drive",
            "identity": "RLY%d_G" % channel,
            "measured_v": gate_v,
            "claim": _claim(
                "RLY%d_G" % channel, "V", "safe_state", gate_v, DIRECT,
                ("py32f003_puya", "ao3400a_aos"),
                _requirement("gate_below_threshold", "<=", threshold_v),
                assumptions=(
                    "the worst case is an internal pull-up at its minimum "
                    "resistance, which is stronger than the floating input "
                    "the datasheet states for the reset state",)),
        })
    return results


# ---------------------------------------------------------------------------
# rails

def evaluate_rails(parameters):
    supply = Supply(parameters)
    mcu = _spec(parameters, "U1")
    brown_out = mcu["reset"]["brown_out_thresholds_v"][
        netlist.BROWN_OUT_OPTION]["rising_max"]["value"]
    documents = ("py32f003_puya", "g2rl_omron", "ao3401a_aos")
    return [
        {"id": "logic_rail_stays_above_brown_out",
         "identity": "+5V",
         "measured_v": supply.logic_rail_min_v,
         "claim": _claim(
             "+5V", "V", "rail_margin", supply.logic_rail_min_v, DIRECT,
             documents, _requirement("above_%s" % netlist.BROWN_OUT_OPTION,
                                     ">=", brown_out),
             assumptions=(
                 "every coil energised at once, each drawing the maximum its "
                 "resistance tolerance allows, with the MCU rail loaded to "
                 "the datasheet's own maximum current into VCC",
                 "the board is fed at the low end of its declared input "
                 "range",
                 "the field wiring and the source feeding the input terminal "
                 "together present no more than %g ohm, which is a budget "
                 "this board states rather than a property it can measure"
                 % netlist.INPUT_PATH_BUDGET_OHM,))},
        {"id": "logic_rail_within_operating_range",
         "identity": "+5V",
         "measured_v": supply.logic_rail_max_v,
         "claim": _claim(
             "+5V", "V", "absolute_maximum", supply.logic_rail_max_v, DIRECT,
             documents, _requirement("below_characterised_maximum", "<=",
                                     mcu["supply"]["characterised_max_v"][
                                         "value"]))},
        {"id": "input_current_budget",
         "identity": "V5IN",
         "measured_a": supply.total_current_max_a,
         "claim": _claim(
             "V5IN", "A", "supply_budget", supply.total_current_max_a,
             DIRECT, documents,
             _requirement("within_the_terminal_rating", "<=",
                          parameters["parts"][_mpn("J1")][
                              "contact_current_max_a"]["value"]))},
        {"id": "mcu_supply_current_within_its_maximum",
         "identity": "+5V",
         "measured_a": supply.mcu_current_max_a,
         "claim": _claim(
             "+5V", "A", "absolute_maximum", supply.mcu_current_max_a,
             DIRECT, ("py32f003_puya",),
             _requirement("within_ivcc_maximum", "<=",
                          mcu["supply"]["max_supply_current_a"]["value"]))},
    ]


def evaluate_coil(parameters):
    supply = Supply(parameters)
    relay = _spec(parameters, "K1")
    rated = relay["coil"]["rated_voltage_v"]["value"]
    operate_v = rated * relay["coil"]["must_operate_fraction"]["value"]
    maximum_v = rated * relay["coil"]["max_voltage_fraction"]["value"]
    return [
        {"id": "coil_reaches_must_operate_voltage",
         "identity": "VCOIL",
         "measured_v": supply.coil_voltage_min_v,
         "claim": _claim(
             "VCOIL", "V", "actuation", supply.coil_voltage_min_v, DIRECT,
             ("g2rl_omron", "ao3400a_aos"),
             _requirement("above_must_operate", ">=", operate_v))},
        {"id": "coil_voltage_within_its_maximum",
         "identity": "VCOIL",
         "measured_v": supply.coil_rail_max_v,
         "claim": _claim(
             "VCOIL", "V", "absolute_maximum", supply.coil_rail_max_v,
             DIRECT, ("g2rl_omron",),
             _requirement("below_coil_maximum", "<=", maximum_v))},
    ]


def evaluate_flyback(parameters):
    supply = Supply(parameters)
    diode = _spec(parameters, "D1")
    nfet = _spec(parameters, "Q1")
    forward = diode["diode"]["forward_voltage_max_v"]
    worst_vf = max(entry["value"] for entry in forward.values())
    clamp_v = supply.coil_rail_max_v + worst_vf
    results = [
        {"id": "flyback_carries_the_coil_current",
         "identity": "flyback",
         "measured_a": supply.coil_current_max_a,
         "claim": _claim(
             "flyback", "A", "component_rating", supply.coil_current_max_a,
             DIRECT, ("g2rl_omron", "1n4148w_semtech"),
             _requirement("within_average_forward_current", "<=",
                          diode["diode"]["average_forward_current_a"][
                              "value"]),
             scope_level="group")},
        {"id": "flyback_clamps_below_the_driver_breakdown",
         "identity": "flyback",
         "measured_v": clamp_v,
         "claim": _claim(
             "flyback", "V", "absolute_maximum", clamp_v, DIRECT,
             ("1n4148w_semtech", "ao3400a_aos"),
             _requirement("below_drain_source_breakdown", "<=",
                          nfet["fet"]["vds_max_v"]["value"]),
             scope_level="group",
             assumptions=(
                 "the forward drop is taken at the highest current the "
                 "datasheet characterises, which is above the coil current",))
         },
    ]
    return results


def evaluate_driver_dissipation(parameters):
    supply = Supply(parameters)
    nfet = _spec(parameters, "Q1")
    on_resistance = max(entry["value"]
                        for entry in nfet["fet"]["rds_on_ohm"].values())
    power_w = supply.coil_current_max_a ** 2 * on_resistance
    return [{
        "id": "driver_dissipation_within_rating",
        "identity": "Q1..Q%d" % netlist.CHANNEL_COUNT,
        "measured_w": power_w,
        "claim": _claim(
            "channel_driver", "W", "thermal", power_w, DIRECT,
            ("ao3400a_aos", "g2rl_omron"),
            _requirement("within_package_dissipation", "<=",
                         nfet["fet"]["power_max_w_70c"]["value"]),
            scope_level="group",
            assumptions=("the on-resistance is taken at the lowest gate "
                         "drive the datasheet characterises, which is below "
                         "the drive this board applies",))}]


def evaluate_pin_loading(parameters):
    supply = Supply(parameters)
    mcu = _spec(parameters, "U1")
    per_pin_a = supply.led_current_max_a + supply.gate_current_max_a
    output = mcu["digital_outputs"][netlist.CHANNEL_COMMAND_PINS[0]]
    return [
        {"id": "command_pin_current_within_absolute_maximum",
         "identity": "RLY_CMD",
         "measured_a": per_pin_a,
         "claim": _claim(
             "RLY_CMD", "A", "absolute_maximum", per_pin_a, DIRECT,
             ("py32f003_puya", "kt0603r_kento"),
             _requirement("within_per_pin_source_current", "<=",
                          mcu["io"]["source_current_max_a"]["value"]))},
        {"id": "command_pin_current_keeps_the_output_level_valid",
         "identity": "RLY_CMD",
         "measured_a": per_pin_a,
         "claim": _claim(
             "RLY_CMD", "A", "gate_drive", per_pin_a, DIRECT,
             ("py32f003_puya",),
             _requirement("at_or_below_the_voh_test_current", "<=",
                          output["voh_min"]["ioh_max_a"]))},
    ]


def evaluate_indicators(parameters):
    supply = Supply(parameters)
    led = _spec(parameters, "D5")
    power_w = supply.led_current_max_a * led["led"][
        "forward_voltage_max_v"]["value"]
    return [
        {"id": "indicator_current_within_rating",
         "identity": "LED",
         "measured_a": supply.led_current_max_a,
         "claim": _claim(
             "indicator", "A", "component_rating", supply.led_current_max_a,
             DIRECT, ("kt0603r_kento",),
             _requirement("within_forward_current", "<=",
                          led["led"]["forward_current_max_a"]["value"]),
             scope_level="group",
             assumptions=("the current is bounded by the series resistor and "
                          "the rail alone, with no credit for the forward "
                          "drop, so no forward-voltage figure is needed",))},
        {"id": "indicator_dissipation_within_rating",
         "identity": "LED",
         "measured_w": power_w,
         "claim": _claim(
             "indicator", "W", "thermal", power_w, DIRECT,
             ("kt0603r_kento",),
             _requirement("within_package_dissipation", "<=",
                          led["led"]["power_max_w"]["value"]),
             scope_level="group")},
    ]


def evaluate_reverse_polarity(parameters):
    supply = Supply(parameters)
    pfet = _spec(parameters, "Q5")
    return [
        {"id": "reverse_protection_gate_stress",
         "identity": "PFET_G",
         "measured_v": supply.input_max_v,
         "claim": _claim(
             "PFET_G", "V", "absolute_maximum", supply.input_max_v, DIRECT,
             ("ao3401a_aos",),
             _requirement("within_gate_source_maximum", "<=",
                          pfet["fet"]["vgs_max_v"]["value"]),
             assumptions=("the gate is held at the reference through its "
                          "pull-down, so the gate-source stress is the input "
                          "voltage in either polarity",))},
        {"id": "reverse_protection_drop",
         "identity": "V5IN",
         "measured_v": supply.pfet_drop_max_v,
         "claim": _claim(
             "V5IN", "V", "rail_margin", supply.pfet_drop_max_v, DIRECT,
             ("ao3401a_aos",),
             _requirement("below_a_tenth_of_the_input", "<=",
                          supply.input_min_v / 10.0))},
    ]


def _resistor_terminals():
    pin_map = _pin_map()
    return {reference: (pin_map[reference + ".1"], pin_map[reference + ".2"])
            for reference in netlist.PARTS
            if re.match(r"^R\d+$", reference)}


def _interior_nets(terminals):
    """Nets that join exactly two resistors and nothing that drives them.

    Such a net is the midpoint of a divider, so the two resistors either side
    of it carry the same current. A net a pin drives, or a rail, is where a
    chain ends instead.
    """
    pin_map = _pin_map()
    driven = set(netlist.RAILS)
    for pin_ref, net in pin_map.items():
        if pin_ref.split(".")[0] == "U1":
            driven.add(net)
    counts = {}
    for reference, nets in terminals.items():
        for net in nets:
            counts.setdefault(net, []).append(reference)
    return {net: members for net, members in counts.items()
            if len(members) == 2 and net not in driven and net != "GND"}


def series_chain(reference, terminals=None, interior=None):
    """The resistors in series with `reference`, and the net that drives them.

    Returns (members, driver_net) or (None, None) when the resistor does not
    sit on a simple chain to the reference - an indicator's series resistor,
    whose other end is a diode, is bounded by the rail alone instead.
    """
    terminals = terminals or _resistor_terminals()
    interior = interior if interior is not None else _interior_nets(terminals)
    if "GND" not in terminals[reference]:
        return None, None
    members = [reference]
    node = [net for net in terminals[reference] if net != "GND"][0]
    while node in interior:
        following = [other for other in interior[node]
                     if other not in members]
        if len(following) != 1:
            break
        nxt = following[0]
        members.append(nxt)
        node = [net for net in terminals[nxt] if net != node][0]
    return members, node


def evaluate_resistor_dissipation(parameters):
    """Every resistor, at the worst case its own topology permits."""
    supply = Supply(parameters)
    terminals = _resistor_terminals()
    interior = _interior_nets(terminals)
    chains = {}
    # Chains are found from the reference end, then indexed by every member:
    # a resistor in the middle of a divider carries the chain's current even
    # though neither of its own terminals is the reference.
    for reference in sorted(terminals):
        members, driver = series_chain(reference, terminals, interior)
        if members is None:
            continue
        for member in members:
            chains.setdefault(member, (members, driver))
    results = []
    for reference in sorted(terminals):
        rating = parameters["parts"][_mpn(reference)]["resistor"][
            "power_max_w"]["value"]
        ohms = _resistor_ohms(reference)
        if reference == netlist.LOGIC_RAIL_SERIES_REFERENCE:
            current_a = supply.mcu_current_max_a
            basis_note = ("the rail series element carries the whole MCU "
                          "supply current, bounded by the datasheet maximum "
                          "for current into VCC")
        else:
            members, driver = chains.get(reference, (None, None))
            if members is None:
                current_a = supply.input_max_v / ohms
                basis_note = ("no forward drop is credited to the device in "
                              "series, so the rail across this resistor "
                              "alone bounds the current")
            else:
                total = sum(_resistor_ohms(member) for member in members)
                current_a = supply.logic_rail_max_v / total
                basis_note = ("in series with %s from %s to the reference"
                              % (", ".join(sorted(set(members) -
                                                  {reference})) or "nothing",
                                 driver))
        power_w = current_a ** 2 * ohms
        results.append({
            "id": "resistor_dissipation_within_rating",
            "identity": reference,
            "measured_w": power_w,
            "claim": _claim(
                reference, "W", "thermal", power_w, DIRECT,
                ("res_0603_uniroyal",),
                _requirement("within_resistor_rating", "<=", rating),
                scope_level="group",
                assumptions=(basis_note,
                             "the driving node is at the top of its declared "
                             "range and the resistors are at nominal value",)),
        })
    return results


# ---------------------------------------------------------------------------
# protection and ratings

def evaluate_esd_coverage(parameters):
    pin_map = _pin_map()
    clamped = {}
    for reference, part in netlist.PARTS.items():
        if part["mpn"] != "TPD1E10B06DPYR":
            continue
        protected = pin_map["%s.2" % reference]
        reference_net = pin_map["%s.1" % reference]
        clamped.setdefault(protected, []).append((reference, reference_net))
    violations = []
    for net, connectors in sorted(entering_conductors().items()):
        if net in ESD_EXEMPT:
            continue
        if net not in clamped:
            violations.append({"net": net, "connectors": connectors,
                               "issue": "no clamp to the reference"})
            continue
        for reference, reference_net in clamped[net]:
            if reference_net != "GND":
                violations.append({"net": net, "clamp": reference,
                                   "issue": "clamp does not return to the "
                                            "reference"})
    results = [{
        "id": "every_entering_logic_conductor_is_clamped",
        "identity": "esd",
        "violations": violations,
        "claim": _structural("esd", "esd_protection", violations,
                             "every_entering_conductor_clamped",
                             documents=("tpd1e10b06_ti",)),
    }]
    standoff = parameters["parts"]["TPD1E10B06DPYR"]["reverse_standoff_v"]
    supply = Supply(parameters)
    for net in sorted(clamped):
        maximum = netlist.RAILS.get(net, {}).get(
            "max_v", netlist.NODE_VOLTAGE_RANGES.get(net, {}).get(
                "max_v", supply.logic_rail_max_v))
        results.append({
            "id": "clamp_standoff_covers_the_working_voltage",
            "identity": net,
            "measured_v": maximum,
            "claim": _claim(
                net, "V", "absolute_maximum", maximum, DIRECT,
                ("tpd1e10b06_ti",),
                _requirement("within_reverse_standoff", "<=",
                             standoff["value"])),
        })
    return results


def evaluate_switched_ratings(parameters):
    """Nothing in the switched path is rated below what the board is marked."""
    rating = netlist.SWITCHED_RATING
    results = []
    for reference, voltage_key, current_key in (
            ("K1", "rated_load_vac", "rated_load_a"),
            ("J2", "contact_voltage_max_v", "contact_current_max_a")):
        spec = _spec(parameters, reference)
        source = spec.get("contacts", spec)
        document = source[voltage_key]["document"]
        results.append({
            "id": "switched_path_voltage_rating",
            "identity": reference,
            "measured_v": rating["voltage_rms_v"],
            "claim": _claim(
                reference, "V", "component_rating", rating["voltage_rms_v"],
                DIRECT, (document,),
                _requirement("within_the_component_rating", "<=",
                             source[voltage_key]["value"]),
                scope_level="group"),
        })
        results.append({
            "id": "switched_path_current_rating",
            "identity": reference,
            "measured_a": rating["current_a"],
            "claim": _claim(
                reference, "A", "component_rating", rating["current_a"],
                DIRECT, (document,),
                _requirement("within_the_component_rating", "<=",
                             source[current_key]["value"]),
                scope_level="group"),
        })
    return results


def evaluate_absolute_maximum(parameters):
    """Every device supply pin against the rail it is tied to."""
    pin_map = _pin_map()
    results = []
    for reference in sorted(netlist.PARTS):
        spec = parameters["parts"].get(_mpn(reference) or "")
        if not spec:
            continue
        for pin in spec.get("supply_pins", []):
            net = pin_map.get("%s.%s" % (reference, pin))
            if net is None:
                continue
            maximum = netlist.RAILS[net]["max_v"]
            limit = spec["supply"]["abs_max_v"]
            results.append({
                "id": "supply_pin_within_absolute_maximum",
                "identity": "%s.%s" % (reference, pin),
                "measured_v": maximum,
                "claim": _claim(
                    "%s.%s" % (reference, pin), "V", "absolute_maximum",
                    maximum, DIRECT, (limit["document"],),
                    _requirement("within_absolute_maximum", "<=",
                                 limit["value"]),
                    scope_level="group"),
            })
    return results


# ---------------------------------------------------------------------------
# geometry the board itself has to demonstrate

def _board():
    import pcbnew
    return pcbnew.LoadBoard(layout.BOARD_PATH)


def _copper_items(board):
    """Every copper item, with its net and the board-coordinate y range."""
    import pcbnew
    items = []
    for track in board.GetTracks():
        ys = [layout.ORIGIN_MM[1] - pcbnew.ToMM(point.y)
              for point in (track.GetStart(), track.GetEnd())]
        half = pcbnew.ToMM(track.GetWidth()) / 2.0
        items.append({"net": track.GetNetname(), "kind": "track",
                      "y_min": min(ys) - half, "y_max": max(ys) + half})
    for footprint in board.GetFootprints():
        for pad in footprint.Pads():
            box = pad.GetBoundingBox()
            items.append({
                "net": pad.GetNetname(),
                "kind": "pad",
                "reference": footprint.GetReference(),
                "y_min": layout.ORIGIN_MM[1] - pcbnew.ToMM(box.GetBottom()),
                "y_max": layout.ORIGIN_MM[1] - pcbnew.ToMM(box.GetTop()),
            })
    for zone in board.Zones():
        if zone.GetIsRuleArea():
            continue
        box = zone.GetBoundingBox()
        items.append({
            "net": zone.GetNetname(), "kind": "zone",
            "y_min": layout.ORIGIN_MM[1] - pcbnew.ToMM(box.GetBottom()),
            "y_max": layout.ORIGIN_MM[1] - pcbnew.ToMM(box.GetTop()),
        })
    return items


def evaluate_boundary(parameters):
    """The isolation boundary, measured on the board rather than declared.

    Two separate claims: that the band is empty of copper on every layer, and
    that every switched conductor stays below it while every other conductor
    stays above it.
    """
    board = _board()
    switched = set(netlist.SWITCHED_NETS)
    inside, misplaced = [], []
    for item in _copper_items(board):
        overlaps = (item["y_max"] > layout.SWITCHED_MAX_Y_MM
                    and item["y_min"] < layout.LOGIC_MIN_Y_MM)
        if overlaps:
            inside.append({k: round(v, 4) if isinstance(v, float) else v
                           for k, v in item.items()})
        if item["net"] in switched:
            if item["y_max"] > layout.SWITCHED_MAX_Y_MM:
                misplaced.append({"net": item["net"], "kind": item["kind"],
                                  "y_max_mm": round(item["y_max"], 4)})
        elif item["net"] and item["y_min"] < layout.LOGIC_MIN_Y_MM:
            misplaced.append({"net": item["net"], "kind": item["kind"],
                              "y_min_mm": round(item["y_min"], 4)})
    band_mm = layout.LOGIC_MIN_Y_MM - layout.SWITCHED_MAX_Y_MM
    return [
        {"id": "boundary_band_is_free_of_copper_on_every_layer",
         "identity": "isolation_boundary",
         "violations": inside,
         "claim": _structural("isolation_boundary", "isolation", inside,
                              "no_copper_crosses_the_boundary")},
        {"id": "every_conductor_is_on_its_own_side",
         "identity": "isolation_boundary",
         "violations": misplaced,
         "claim": _structural("isolation_boundary", "isolation", misplaced,
                              "switched_and_logic_copper_are_separated")},
        {"id": "boundary_width_meets_the_derived_figure",
         "identity": "isolation_boundary",
         "measured_mm": band_mm,
         "claim": _claim(
             "isolation_boundary", "mm", "isolation", band_mm, DIRECT,
             (clearance.EVIDENCE_DOCUMENT, "g2rl_omron"),
             _requirement("at_or_above_the_reinforced_figure", ">=",
                          clearance.BOUNDARY_MM),
             assumptions=(
                 "pollution degree %d, material group %s and overvoltage "
                 "category %s, which describe the installation rather than "
                 "the board" % (clearance.POLLUTION_DEGREE,
                                clearance.MATERIAL_GROUP,
                                clearance.OVERVOLTAGE_CATEGORY),))},
    ]


def _pad_position(footprints, reference, number):
    import pcbnew
    for pad in footprints[reference].Pads():
        if pad.GetNumber() == number:
            point = pad.GetPosition()
            return (pcbnew.ToMM(point.x) - layout.ORIGIN_MM[0],
                    layout.ORIGIN_MM[1] - pcbnew.ToMM(point.y))
    raise KeyError("%s has no pad %s" % (reference, number))


def evaluate_flyback_loop(parameters):
    """The turn-off loop each flyback closes with its coil pins.

    The enclosing rectangle of the four pads the current circulates through,
    which is what the brief's "small turn-off loop" is asking about and what
    a placement search optimising wirelength would happily give away.
    """
    board = _board()
    footprints = {footprint.GetReference(): footprint
                  for footprint in board.GetFootprints()}
    results = []
    for channel in range(1, netlist.CHANNEL_COUNT + 1):
        corners = [_pad_position(footprints, "K%d" % channel, "A1"),
                   _pad_position(footprints, "D%d" % channel, "1"),
                   _pad_position(footprints, "D%d" % channel, "2"),
                   _pad_position(footprints, "K%d" % channel, "A2")]
        xs = [point[0] for point in corners]
        ys = [point[1] for point in corners]
        area = (max(xs) - min(xs)) * (max(ys) - min(ys))
        results.append({
            "id": "flyback_turn_off_loop_is_small",
            "identity": "RLY%d_C" % channel,
            "measured_mm2": area,
            "claim": _claim(
                "RLY%d_C" % channel, "mm2", "switching_loop", area, DERIVED,
                (), _requirement("within_the_declared_loop_target", "<=",
                                 netlist.FLYBACK_LOOP_AREA_TARGET_MM2),
                assumptions=("the enclosing rectangle of the four pads bounds "
                             "the area the turn-off current encloses",)),
        })
    return results


def board_silkscreen_texts():
    import pcbnew
    board = _board()
    texts = []
    for item in board.GetDrawings():
        if item.GetClass() != "PCB_TEXT":
            continue
        if item.GetLayer() == pcbnew.F_SilkS:
            texts.append(item.GetText())
    return texts


def evaluate_markings(parameters):
    """What the brief requires a person to be able to read off the board."""
    texts = set(board_silkscreen_texts())
    missing = []
    for channel in range(1, netlist.CHANNEL_COUNT + 1):
        for function in netlist.TERMINAL_FUNCTIONS:
            label = "CH%d %s" % (channel, function)
            if label not in texts:
                missing.append(label)
    rating = layout.rating_text()
    if rating not in texts:
        missing.append(rating)
    return [{
        "id": "the_board_carries_its_terminal_and_rating_markings",
        "identity": "silkscreen",
        "violations": missing,
        "claim": _structural("silkscreen", "marking", missing,
                             "every_required_marking_present"),
    }]


def evaluate_probe_access(parameters):
    pin_map = _pin_map()
    probed = set()
    for pin_ref, net in pin_map.items():
        if pin_ref.split(".")[0].startswith("TP"):
            probed.add(net)
    missing = [net for net in PROBE_REQUIRED_NETS if net not in probed]
    return [{
        "id": "every_required_node_reaches_a_probe",
        "identity": "bring_up",
        "violations": missing,
        "claim": _structural("bring_up", "test_access", missing,
                             "every_required_node_probed"),
    }]


def evaluate_assembly(parameters):
    """One side, one reflow pass, and every hand-fitted part accounted for."""
    import pcbnew
    board = _board()
    policy = netlist.ASSEMBLY_POLICY
    flipped = sorted(footprint.GetReference()
                     for footprint in board.GetFootprints()
                     if footprint.IsFlipped())
    through_hole = sorted(
        footprint.GetReference() for footprint in board.GetFootprints()
        if any(pad.GetAttribute() == pcbnew.PAD_ATTRIB_PTH
               for pad in footprint.Pads()))
    return [
        {"id": "all_parts_on_one_side",
         "identity": "assembly",
         "violations": flipped,
         "claim": _structural("assembly", "assembly", flipped,
                              "single_placement_side")},
        {"id": "through_hole_population_as_declared",
         "identity": "assembly",
         "measured": len(through_hole),
         "claim": _claim(
             "assembly", "parts", "assembly", float(len(through_hole)),
             DERIVED, (),
             _requirement("as_declared", "<=",
                          float(policy["through_hole_soldered_parts"])),
             scope_level="board")},
    ]


# ---------------------------------------------------------------------------
# what the board cannot establish by itself

def evaluate_switched_copper_ampacity(parameters):
    """Temperature rise of the switched copper at the marked current.

    The width is measured and the current is declared, but the relation
    between them is an empirical curve this repository holds no copy of. The
    quantity is therefore reported as UNKNOWN with the verification method it
    needs, rather than as a number a formula produced from memory.
    """
    return [{
        "id": "switched_copper_temperature_rise",
        "identity": "switched_copper",
        "measured_c": None,
        "verification_method": "PHYSICAL_TEST",
        "claim": _claim(
            "switched_copper", "degC", "thermal", None, ASSUMED, (),
            _requirement("temperature_rise_within_20C", "<=", 20.0),
            scope_level="board",
            omissions=("no conductor-sizing standard is frozen in this "
                       "repository, so the rise at the marked current is not "
                       "established; the width is a design choice pending a "
                       "measurement on an assembled board",)),
    }]


# ---------------------------------------------------------------------------

def evaluate_all():
    parameters = load_parameters()
    results = []
    for producer in (evaluate_gate_drive, evaluate_hold_off, evaluate_rails,
                     evaluate_coil, evaluate_flyback,
                     evaluate_driver_dissipation, evaluate_pin_loading,
                     evaluate_indicators, evaluate_reverse_polarity,
                     evaluate_resistor_dissipation, evaluate_esd_coverage,
                     evaluate_switched_ratings, evaluate_absolute_maximum,
                     evaluate_boundary, evaluate_flyback_loop,
                     evaluate_markings, evaluate_probe_access,
                     evaluate_assembly,
                     evaluate_switched_copper_ampacity):
        results.extend(producer(parameters))
    for result in results:
        result["verdict"] = claim.verdict(result["claim"])
    return results


REPORT_PATH = os.path.join(REPO_ROOT, "generated", "requirements.json")


def write_report():
    """The whole claim set, as an artifact rather than a console report.

    Each entry carries what was measured, the evidence class it rests on, the
    documents behind it, the assumptions it was evaluated under and the
    verdict - so a later reader can see not only that the board passed but
    what "passed" was allowed to mean.
    """
    evaluated = evaluate_all()
    document = {
        "kind": "board-requirement-evidence",
        "summary": summarise(evaluated),
        "results": [
            {"id": result["id"], "identity": result["identity"],
             "claim": result["claim"], "verdict": result["verdict"]}
            for result in sorted(evaluated,
                                 key=lambda item: (item["id"],
                                                   item["identity"]))],
    }
    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(document, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return REPORT_PATH


def summarise(results):
    counts = {}
    for result in results:
        counts[result["verdict"]["result"]] = counts.get(
            result["verdict"]["result"], 0) + 1
    return counts


if __name__ == "__main__":
    evaluated = evaluate_all()
    write_report()
    for result in sorted(evaluated, key=lambda item: (
            item["verdict"]["result"], item["id"], item["identity"])):
        value = result["claim"]["quantity"].get("value")
        rendered = "-" if value is None else "%.6g" % value
        sys.stdout.write("%-8s %-46s %-22s %12s %s\n" % (
            result["verdict"]["result"], result["id"], result["identity"],
            rendered, result["claim"]["units"]))
    sys.stdout.write("\n" + json.dumps(summarise(evaluated), sort_keys=True)
                     + "\n")
