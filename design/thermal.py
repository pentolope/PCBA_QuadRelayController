"""What this board's heat does, and where the answer stops.

The brief conditions its dissipation requirement on "maximum ambient" and
names no figure, so the board declares one. Everything here follows from it:
package ratings are derated to it, every part's stated ambient range is
checked against it, and the relay's coil drive margin is evaluated from it.

Three things are worth separating.

What is established: the dissipation of every part at the worst case its own
electrical analysis allows, package ratings at the declared ambient rather
than at whatever ambient the datasheet happened to quote, and the
junction-to-lead rise, which is a package property and does not depend on the
board the part sits on.

What is bounded but conditional: a junction temperature computed from a
datasheet's junction-to-ambient figure. That figure is measured on the
datasheet's own test board - for the drivers here, one square inch of two
ounce copper in still air - and this is neither that board nor that copper
weight. Rather than claim a junction temperature this board cannot support,
the margin is reported as the factor by which this board's thermal path could
be worse than the datasheet's before the junction limit is reached.

What is not established at all: the board's own temperature rise. That needs
either a thermal solve over this copper or a measurement on an assembled
board, and until there is one, every junction temperature on this board is
unknown above its ambient. The claim says so rather than going quiet.
"""
from __future__ import annotations

import json
import os
import sys

from . import netlist, rules

REPO_ROOT = rules.REPO_ROOT
REPORT_PATH = os.path.join(REPO_ROOT, "generated", "thermal.json")

#: Resistance temperature coefficient of annealed copper at 20 degC, the
#: value the International Annealed Copper Standard fixes. Asserted by this
#: board rather than read from a document frozen here; every conclusion that
#: uses it reports how far it could be wrong before the conclusion changes.
COPPER_TEMPCO_PER_C = 0.00393

#: The temperature the relay's coil resistance and operating characteristics
#: are specified at. Stated by the datasheet, not chosen here.
COIL_SPEC_TEMPERATURE_C = 23.0


def _document(record):
    return record.get("document")


def steady_state_power_limit_w(spec, ambient_c=None):
    """What a part may dissipate at the declared ambient, from its own limits.

    Derived rather than read: a datasheet's headline power figure is quoted at
    whatever ambient suited the datasheet, and for these drivers it is quoted
    against a ten-second thermal resistance, which is not a rating for a part
    that is on continuously.
    """
    ambient_c = netlist.MAX_AMBIENT_C if ambient_c is None else ambient_c
    budget_c = spec["junction_max_c"]["value"] - ambient_c
    return budget_c / spec["theta_ja_steady_max_c_per_w"]["value"]


# ---------------------------------------------------------------------------
# the dissipation inventory

def dissipation(parameters):
    """Every part's worst-case dissipation, by source.

    Each term is that part's own worst case, so the total is an upper bound
    rather than an operating point: the coil current is maximised at minimum
    coil resistance while the MCU is loaded at its datasheet maximum, and no
    single supply condition produces both at once.
    """
    supply = rules.Supply(parameters)
    relay = rules._spec(parameters, "K1")
    nfet = rules._spec(parameters, "Q1")["fet"]
    pfet = rules._spec(parameters, "Q5")["fet"]
    terminal = rules._spec(parameters, "J2")
    channels = netlist.CHANNEL_COUNT
    switched_a = netlist.SWITCHED_RATING["current_a"]

    coil_each = supply.coil_rail_max_v * supply.coil_current_max_a
    driver_each = supply.coil_current_max_a ** 2 * max(
        entry["value"] for entry in nfet["rds_on_ohm"].values())
    contact_each = switched_a ** 2 * relay["contacts"]["resistance_ohm"][
        "value"]
    # Load current enters a channel through one terminal contact and leaves
    # through another, so two of the three contacts carry it.
    terminal_each = 2 * switched_a ** 2 * terminal["contact_resistance_ohm"][
        "value"]

    resistors = sum(entry["measured_w"]
                    for entry in rules.evaluate_resistor_dissipation(
                        parameters))
    # evaluate_indicators states one indicator; every indicator on the board
    # is identical and all of them can be lit at once.
    indicator_count = len([reference for reference in netlist.PARTS
                           if netlist.PARTS[reference]["lib_id"]
                           == netlist.PARTS["D5"]["lib_id"]])
    indicators = indicator_count * sum(
        entry["measured_w"]
        for entry in rules.evaluate_indicators(parameters)
        if entry["id"] == "indicator_dissipation_within_rating")

    logic = {
        "relay_coils": {
            "watts": channels * coil_each,
            "detail": "%d coils at the top of the coil rail and the bottom "
                      "of the coil's resistance tolerance"
                      % channels,
            "documents": ["g2rl_omron"]},
        "mcu": {
            "watts": supply.logic_rail_max_v * supply.mcu_current_max_a,
            "detail": "the datasheet's own maximum current into VCC, which "
                      "is far above the part's typical consumption",
            "documents": ["py32f003_puya"]},
        "rail_series_resistor": {
            "watts": supply.mcu_current_max_a ** 2 * supply.series_ohm,
            "detail": "the element between the coil supply and the logic "
                      "rail, carrying the whole MCU supply current",
            "documents": ["res_0603_uniroyal"]},
        "gate_and_indicator_networks": {
            "watts": resistors - supply.mcu_current_max_a ** 2
            * supply.series_ohm,
            "detail": "every resistor except the rail series element",
            "documents": ["res_0603_uniroyal"]},
        "indicators": {
            "watts": indicators,
            "detail": "all %d indicators lit" % indicator_count,
            "documents": ["kt0603r_kento"]},
        "reverse_polarity_device": {
            "watts": supply.total_current_max_a ** 2
            * supply.pfet_rds_on_ohm,
            "detail": "the whole board current through the input device",
            "documents": ["ao3401a_aos"]},
        "channel_drivers": {
            "watts": channels * driver_each,
            "detail": "%d drivers conducting their coil current" % channels,
            "documents": ["ao3400a_aos"]},
    }
    switched = {
        "relay_contacts": {
            "watts": channels * contact_each,
            "detail": "%d closed contacts each carrying the marked %g A at "
                      "the datasheet's MAXIMUM contact resistance, which is "
                      "an initial low-current measurement limit; the relay's "
                      "own %g A carry rating could not be met if the "
                      "resistance at rated current were really that high, so "
                      "this bounds the dissipation from well above"
                      % (channels, switched_a,
                         relay["contacts"]["rated_load_a"]["value"]),
            "documents": ["g2rl_omron"]},
        "switched_terminals": {
            "watts": channels * terminal_each,
            "detail": "two contacts per channel carrying the marked %g A"
                      % switched_a,
            "documents": ["hb9500m_kangnex"]},
    }
    return {"logic_side": logic, "switched_side": switched}


def totals(parameters):
    inventory = dissipation(parameters)
    return {side: sum(entry["watts"] for entry in group.values())
            for side, group in inventory.items()}


# ---------------------------------------------------------------------------
# claims

def _ambient_records(parameters):
    """(reference, mpn, stated maximum ambient or None) for every part."""
    found = []
    def order(reference):
        prefix = reference.rstrip("0123456789")
        return prefix, int(reference[len(prefix):] or 0)

    for reference in sorted(netlist.PARTS, key=order):
        mpn = netlist.PARTS[reference]["mpn"]
        if mpn is None:
            # Bare copper and mechanical features: a test-point pad, a
            # mounting hole, a schematic power flag. Nothing is fitted, so
            # there is no part rating to cover.
            continue
        spec = parameters["parts"][mpn]
        stated, document = None, None
        for holder in (spec, spec.get("led") or {}, spec.get("capacitor") or {},
                       spec.get("resistor") or {}):
            for key in ("ambient_max_c", "full_rating_ambient_max_c"):
                record = holder.get(key)
                if record is not None:
                    stated, document = record["value"], _document(record)
                    break
            if stated is not None:
                break
        if stated is None:
            record = (spec.get("ambient_temperature_c") or {}).get("max")
            if record is not None:
                stated, document = record["value"], _document(record)
        if stated is None and "junction_max_c" in (spec.get("fet") or {}):
            # A discrete whose datasheet bounds the junction rather than the
            # ambient is covered by its own junction claim, not by this one.
            continue
        if stated is None and "junction_max_c" in (spec.get("diode") or {}):
            continue
        found.append((reference, mpn, stated, document))
    return found


def evaluate_ambient_coverage(parameters):
    records = _ambient_records(parameters)
    stated = [row for row in records if row[2] is not None]
    unstated = sorted({row[1] for row in records if row[2] is None})
    violations = ["%s (%s) rated to %g degC"
                  % (reference, mpn, ceiling)
                  for reference, mpn, ceiling, _ in stated
                  if ceiling < netlist.MAX_AMBIENT_C]
    documents = sorted({row[3] for row in stated if row[3]})
    results = [{
        "id": "every_stated_ambient_rating_covers_the_declared_maximum",
        "identity": "declared_ambient",
        "measured_parts": len(stated),
        "claim": rules._claim(
            "declared_ambient", "violations", "thermal",
            float(len(violations)), rules.DIRECT, documents,
            rules._requirement("covers_the_declared_maximum_ambient", "<=",
                               0.0),
            assumptions=(
                "for the resistors the figure compared against is the top of "
                "their full-rating range rather than the top of their "
                "operating range, which the datasheet gives only as a "
                "derating figure; it is a lower bound on their operating "
                "ceiling, so this check errs towards failing",))}]
    if unstated:
        results.append({
            "id": "parts_whose_datasheet_states_no_ambient_rating",
            "identity": "declared_ambient",
            "measured_parts": len(unstated),
            "claim": rules._claim(
                "declared_ambient", "degC", "thermal", None, rules.ASSUMED,
                (), rules._requirement("an_ambient_rating_is_established",
                                       ">=", netlist.MAX_AMBIENT_C),
                scope_level="group",
                assumptions=(
                    "the datasheets frozen for %s state no operating "
                    "temperature range, so their suitability at the declared "
                    "ambient is not established here"
                    % ", ".join(unstated),),
                omissions=(
                    "the ambient rating of every part whose datasheet does "
                    "not state one; a vendor confirmation or a qualification "
                    "test is what would close this",))})
    return results


def evaluate_resistor_derating(parameters):
    spec = rules._spec(parameters, "R1")["resistor"]
    ceiling = spec["full_rating_ambient_max_c"]["value"]
    return [{
        "id": "the_resistor_rating_applies_at_the_declared_ambient",
        "identity": "R1..R%d" % len(
            [ref for ref in netlist.PARTS if ref.startswith("R")]),
        "measured_c": netlist.MAX_AMBIENT_C,
        "claim": rules._claim(
            "resistors", "degC", "thermal", netlist.MAX_AMBIENT_C,
            rules.DIRECT, ("res_0603_uniroyal",),
            rules._requirement("below_the_derating_knee", "<=", ceiling),
            scope_level="group",
            assumptions=("the full power rating is continuous up to this "
                         "temperature, so no derating is applied below it",))}]


def _semiconductors(parameters):
    """Every part with a junction limit and a dissipation to compare to it."""
    supply = rules.Supply(parameters)
    nfet = rules._spec(parameters, "Q1")["fet"]
    pfet = rules._spec(parameters, "Q5")["fet"]
    driver_w = supply.coil_current_max_a ** 2 * max(
        entry["value"] for entry in nfet["rds_on_ohm"].values())
    input_w = supply.total_current_max_a ** 2 * supply.pfet_rds_on_ohm
    return (("Q1..Q%d" % netlist.CHANNEL_COUNT, nfet, driver_w,
             "ao3400a_aos",
             "conducting its coil current at the highest on-resistance the "
             "datasheet characterises"),
            ("Q%d" % (netlist.CHANNEL_COUNT + 1), pfet, input_w,
             "ao3401a_aos",
             "carrying the whole board current at its on-resistance"))


def evaluate_junction_paths(parameters):
    results = []
    for identity, spec, power_w, document, detail in _semiconductors(
            parameters):
        budget_c = spec["junction_max_c"]["value"] - netlist.MAX_AMBIENT_C
        lead_rise_c = power_w * spec["theta_jl_steady_max_c_per_w"]["value"]
        board_rise_c = power_w * spec["theta_ja_steady_max_c_per_w"]["value"]
        results.append({
            "id": "junction_to_lead_rise_within_the_budget",
            "identity": identity,
            "measured_c": lead_rise_c,
            "claim": rules._claim(
                identity, "degC", "thermal", lead_rise_c, rules.DIRECT,
                (document,),
                rules._requirement("within_the_junction_budget", "<=",
                                   budget_c),
                scope_level="group",
                assumptions=(
                    "the part is %s" % detail,
                    "junction to lead is a package property and does not "
                    "depend on the board, so this rise is established; it is "
                    "a LOWER bound on the total junction rise, because the "
                    "lead-to-ambient path is on top of it",))})
        results.append({
            "id": "junction_margin_on_the_datasheet_test_board",
            "identity": identity,
            "measured_factor": budget_c / board_rise_c,
            "claim": rules._claim(
                identity, "x", "thermal", budget_c / board_rise_c,
                rules.DIRECT, (document,),
                rules._requirement("at_or_above_the_datasheet_board", ">=",
                                   1.0),
                scope_level="group",
                assumptions=(
                    "the factor is how many times worse this board's "
                    "junction-to-ambient path could be than the datasheet's "
                    "test board before the junction limit is reached at the "
                    "declared ambient",
                    "the datasheet figure is measured on %s, which is "
                    "neither this board nor this copper weight, so it is "
                    "used as a reference point and not as this board's "
                    "thermal resistance"
                    % spec["theta_ja_steady_max_c_per_w"]["conditions"]
                    .split(";")[0],))})
    return results


def coil_critical_temperature_c(parameters):
    """The coil temperature at which the drive margin runs out.

    Pull-in is set by ampere-turns, so the voltage a coil must see to operate
    scales with its resistance, and its resistance scales with temperature.
    The margin between the voltage this board delivers and the datasheet's
    must-operate voltage therefore buys a temperature rise, and this is it.
    """
    supply = rules.Supply(parameters)
    coil = rules._spec(parameters, "K1")["coil"]
    must_operate_v = (coil["rated_voltage_v"]["value"]
                      * coil["must_operate_fraction"]["value"])
    ratio = supply.coil_voltage_min_v / must_operate_v
    rise_c = (ratio - 1.0) / COPPER_TEMPCO_PER_C
    return COIL_SPEC_TEMPERATURE_C + rise_c, ratio, must_operate_v


def evaluate_coil_drive_over_temperature(parameters):
    relay = rules._spec(parameters, "K1")
    rated_ambient_c = relay["ambient_temperature_c"]["max"]["value"]
    critical_c, ratio, must_operate_v = coil_critical_temperature_c(parameters)
    # How wrong the temperature coefficient could be before the conclusion
    # changes: the value at which the critical temperature falls to the
    # relay's own rated ambient.
    critical_tempco = (ratio - 1.0) / (rated_ambient_c
                                       - COIL_SPEC_TEMPERATURE_C)
    return [{
        "id": "coil_drive_survives_to_the_relays_rated_ambient",
        "identity": "K1..K%d" % netlist.CHANNEL_COUNT,
        "measured_c": critical_c,
        "claim": rules._claim(
            "relay_coils", "degC", "thermal", critical_c, rules.DERIVED,
            ("g2rl_omron",),
            rules._requirement("at_or_above_the_relay_rated_ambient", ">=",
                               rated_ambient_c),
            scope_level="group",
            assumptions=(
                "the relay's coil resistance and its %g V must-operate "
                "voltage are both specified at %g degC, and pull-in is set by "
                "ampere-turns, so the must-operate voltage scales with coil "
                "resistance and therefore with temperature"
                % (must_operate_v, COIL_SPEC_TEMPERATURE_C),
                "annealed copper's resistance temperature coefficient is "
                "taken as %.5f per degC; the conclusion holds for any value "
                "below %.5f per degC, which is above every published figure "
                "for copper" % (COPPER_TEMPCO_PER_C, critical_tempco),
                "this is the coil's own temperature, which is the ambient "
                "plus a self-heating rise this board does not establish",))}]


def evaluate_board_rise(parameters):
    """The one this board cannot answer, said out loud."""
    relay = rules._spec(parameters, "K1")
    headroom_c = (relay["ambient_temperature_c"]["max"]["value"]
                  - netlist.MAX_AMBIENT_C)
    inventory = totals(parameters)
    return [{
        "id": "board_temperature_rise_above_ambient",
        "identity": "board",
        "measured_c": None,
        "claim": rules._claim(
            "board", "degC", "thermal", None, rules.ASSUMED, (),
            rules._requirement("within_the_ambient_headroom", "<=",
                               headroom_c),
            scope_level="board",
            assumptions=(
                "the board dissipates at most %.3f W on the logic side and a "
                "further %.3f W in the switched contacts and terminals with "
                "every channel closed at the marked current, each term at its "
                "own worst case, so the total bounds any single operating "
                "point from above"
                % (inventory["logic_side"], inventory["switched_side"]),
                "the headroom is measured to the lowest rated ambient on the "
                "board, which is the relay's",),
            omissions=(
                "the board's thermal resistance to ambient: no thermal solve "
                "over this copper and no measurement on an assembled board "
                "exists, so the rise the stated dissipation produces is not "
                "established and every junction temperature on this board is "
                "unknown above its ambient",
                "airflow: still air is neither assumed nor established, and "
                "the orientation the board is mounted in is not specified",))}]


def evaluate_all(parameters):
    results = []
    for producer in (evaluate_ambient_coverage, evaluate_resistor_derating,
                     evaluate_junction_paths,
                     evaluate_coil_drive_over_temperature,
                     evaluate_board_rise):
        results.extend(producer(parameters))
    return results


# ---------------------------------------------------------------------------

def document(parameters=None):
    parameters = parameters or rules.load_parameters()
    inventory = dissipation(parameters)
    critical_c, _, must_operate_v = coil_critical_temperature_c(parameters)
    return {
        "kind": "thermal-estimate",
        "estimate_class": "simple: a dissipation inventory and package-limit "
                          "derating at a declared ambient. No thermal solve, "
                          "no copper spreading model, no airflow assumption, "
                          "and therefore no board temperature and no junction "
                          "temperature.",
        "declared_max_ambient_c": netlist.MAX_AMBIENT_C,
        "dissipation_w": inventory,
        "totals_w": totals(parameters),
        "worst_case": "every term is that part's own worst case, so the "
                      "total bounds any single operating point from above "
                      "rather than describing one",
        "coil_drive": {
            "must_operate_v_at_%g_c" % COIL_SPEC_TEMPERATURE_C:
                must_operate_v,
            "critical_coil_temperature_c": critical_c,
            "copper_tempco_per_c": COPPER_TEMPCO_PER_C,
        },
        "not_established": [
            "board temperature rise above ambient",
            "junction temperature of any part",
            "airflow and mounting orientation",
            "the operating ambient range of the terminal blocks and headers, "
            "whose datasheets state none",
        ],
        "context": {"generated_by": "design/thermal.py"},
    }


def write():
    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(document(), handle, indent=2, sort_keys=True)
        handle.write("\n")
    return REPORT_PATH


if __name__ == "__main__":
    parameters = rules.load_parameters()
    inventory = dissipation(parameters)
    for side, group in sorted(inventory.items()):
        sys.stdout.write("%s\n" % side)
        for name, entry in sorted(group.items(),
                                  key=lambda item: -item[1]["watts"]):
            sys.stdout.write("  %-30s %8.4f W\n" % (name, entry["watts"]))
    for side, total in sorted(totals(parameters).items()):
        sys.stdout.write("%-32s %8.4f W\n" % (side + " total", total))
    critical_c, ratio, must_operate_v = coil_critical_temperature_c(parameters)
    sys.stdout.write("\ncoil must-operate %.3f V, margin x%.4f, "
                     "critical coil temperature %.1f degC\n"
                     % (must_operate_v, ratio, critical_c))
    sys.stdout.write(write() + "\n")
