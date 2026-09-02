"""What kind of statement each requirement is, and how it is established.

A claim carries a number, an evidence class and a verdict. What it does not
carry is where the requirement it is judged against came from, and that is a
distinction worth keeping: a board can fail because the brief asked for the
wrong thing, because the agent derived the wrong requirement from it, because
a threshold was a choice nobody wrote down, or because the implementation is
simply wrong. Collapsing all four into one source string makes those failures
look identical.

So every requirement name a claim uses is registered here with:

  * its kind - stated by the brief, derived by this design, chosen by this
    design, or assumed pending evidence;
  * what it was derived from, for the derived ones;
  * why, for the ones a reader would otherwise have to guess at;
  * the alternatives, for the ones that were a choice;
  * the verification methods that establish it, and whether a physical test
    is still required.

The register is joined to the claim set by requirement name, and the join is
total in both directions: a claim judged against an unregistered requirement
and a registered requirement nothing is judged against are both errors. That
is what stops this becoming prose that drifts away from the design.
"""
from __future__ import annotations

import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTER_PATH = os.path.join(REPO_ROOT, "constraints", "requirements.json")

BRIEF = "BRIEF.md"

# ---------------------------------------------------------------------------
# statement kinds

USER = "user_requirement"
DERIVED = "derived_requirement"
ASSUMPTION = "assumption"
DECISION = "design_decision"
KINDS = (USER, DERIVED, ASSUMPTION, DECISION)

# ---------------------------------------------------------------------------
# verification methods

STATIC = "STATIC"
GEOMETRY = "GEOMETRY"
ANALYTIC = "ANALYTIC"
CIRCUIT_SIM = "CIRCUIT_SIM"
DIGITAL_SIM = "DIGITAL_SIM"
EXTRACTED = "EXTRACTED"
EM_SIM = "EM_SIM"
THERMAL_SIM = "THERMAL_SIM"
MANUFACTURING_CHECK = "MANUFACTURING_CHECK"
PHYSICAL_TEST = "PHYSICAL_TEST"
DOCUMENTATION = "DOCUMENTATION"

METHODS = (STATIC, GEOMETRY, ANALYTIC, CIRCUIT_SIM, DIGITAL_SIM, EXTRACTED,
           EM_SIM, THERMAL_SIM, MANUFACTURING_CHECK, PHYSICAL_TEST,
           DOCUMENTATION)

#: Brief clauses, as the anchors a reader can follow.
POWER = BRIEF + "#power-and-rails"
FUNCTION = BRIEF + "#functional-requirements"
DRIVE = BRIEF + "#relay-drive-and-flyback-suppression"
CONNECTORS = BRIEF + "#connectors-and-programming-interface"
SEPARATION = BRIEF + "#separation-clearance-and-markings"
BRING_UP = BRIEF + "#test-and-bring-up"
OPEN = BRIEF + "#open-choices"


def _user(statement, clause, verified_by, physical_test=False):
    return {"kind": USER, "statement": statement, "derived_from": (clause,),
            "origin": clause, "verified_by": verified_by,
            "physical_test_still_required": physical_test}


def _derived(statement, clause, origin, rationale, verified_by,
             physical_test=False):
    return {"kind": DERIVED, "statement": statement,
            "derived_from": (clause,) if isinstance(clause, str)
            else tuple(clause),
            "origin": origin, "rationale": rationale,
            "verified_by": verified_by,
            "physical_test_still_required": physical_test}


def _decision(statement, rationale, alternatives, verified_by,
              physical_test=False):
    return {"kind": DECISION, "statement": statement, "rationale": rationale,
            "alternatives_considered": tuple(alternatives),
            "verified_by": verified_by,
            "physical_test_still_required": physical_test}


# ---------------------------------------------------------------------------
# the requirements every claim is judged against

REGISTER = {

    # --- rails -------------------------------------------------------------

    "above_VBOR8": _derived(
        "the logic rail stays above the MCU's brown-out reset threshold with "
        "every coil energising at once",
        POWER, "py32f003_puya",
        "the brief says 'above brown-out' without naming a number; the number "
        "that phrase refers to is the rising threshold of the option-byte "
        "level this board configures, which is a property of the chosen MCU "
        "rather than of the brief",
        (ANALYTIC, CIRCUIT_SIM, EXTRACTED)),

    "below_characterised_maximum": _derived(
        "the logic rail stays inside the supply range the MCU is "
        "characterised over",
        POWER, "py32f003_puya",
        "the brief's 'inside the MCU's operating range' is bounded above as "
        "well as below, and the upper bound is the datasheet's characterised "
        "supply maximum rather than its absolute maximum",
        (ANALYTIC, CIRCUIT_SIM, EXTRACTED)),

    "within_absolute_maximum": _derived(
        "the supply pin never sees more than its absolute maximum rating",
        POWER, "py32f003_puya",
        "an operating-range requirement does not by itself establish that the "
        "destructive limit is respected at the top of the input tolerance",
        (ANALYTIC,)),

    "within_ivcc_maximum": _derived(
        "the MCU draws no more than the datasheet's maximum current into VCC",
        POWER, "py32f003_puya",
        "the rail model loads the MCU at a fixed current, and that figure has "
        "to be one the part is allowed to draw",
        (ANALYTIC,)),

    "within_the_terminal_rating": _derived(
        "the total board input current stays within the input terminal's "
        "current rating",
        POWER, "hb9500m_kangnex",
        "the brief specifies a 5 V input but not what it may draw; the ceiling "
        "is set by the connector the input arrives through",
        (ANALYTIC, DOCUMENTATION)),

    # --- coil and driver ---------------------------------------------------

    "above_must_operate": _derived(
        "the coil supply reaches the relay's must-operate voltage at the "
        "worst-case combination of input tolerance and series drops",
        FUNCTION, "g2rl_omron",
        "'independently commandable' presupposes that a commanded coil "
        "actually transfers its contacts, which the relay states as a "
        "must-operate voltage",
        (ANALYTIC,), physical_test=True),

    "below_coil_maximum": _derived(
        "the coil supply stays below the relay's maximum continuous coil "
        "voltage",
        FUNCTION, "g2rl_omron",
        "the same supply that must reach must-operate at its low end must not "
        "exceed the coil's continuous rating at its high end",
        (ANALYTIC,)),

    "gate_at_or_above_characterised_drive": _derived(
        "each driver gate reaches at least the gate-source voltage the FET's "
        "on-resistance is characterised at",
        DRIVE, ("ao3400a_aos", "py32f003_puya"),
        "the brief asks for a stage 'fully on at the drive level the chosen "
        "MCU guarantees'; 'fully on' is only meaningful against a drive level "
        "the FET datasheet actually characterises",
        (ANALYTIC, GEOMETRY)),

    "gate_below_threshold": _derived(
        "each driver gate stays below the FET's minimum gate-source threshold "
        "when the MCU pin does not drive it",
        DRIVE, ("ao3400a_aos", "py32f003_puya"),
        "the brief requires the input to be 'resistively held de-energised'; "
        "the level that qualifies as de-energised is the FET's own minimum "
        "threshold, not zero",
        (ANALYTIC, CIRCUIT_SIM)),

    "within_package_dissipation": _derived(
        "no part dissipates more than its package is rated for with all four "
        "channels on",
        DRIVE, ("ao3400a_aos", "kt0603r_kento"),
        "the brief conditions this on maximum ambient; the package figures "
        "used here are the datasheet ratings at their own reference ambient, "
        "so this establishes the dissipation and not the junction temperature",
        (ANALYTIC,), physical_test=True),

    "within_per_pin_source_current": _derived(
        "no MCU pin sources more than its per-pin absolute maximum",
        DRIVE, "py32f003_puya",
        "the brief's 'total pin current within ratings' is bounded per pin as "
        "well as in aggregate, and the per-pin figure is the tighter one here "
        "because each command pin also drives an indicator",
        (ANALYTIC, GEOMETRY)),

    "at_or_below_the_voh_test_current": _derived(
        "each command pin sources no more than the current its output-high "
        "level is specified at",
        DRIVE, "py32f003_puya",
        "the guaranteed drive level used by the gate claim is only guaranteed "
        "at the datasheet's stated test current; drawing more would make that "
        "level an extrapolation",
        (ANALYTIC, GEOMETRY)),

    "within_resistor_rating": _derived(
        "every resistor dissipates less than its package rating",
        DRIVE, "res_0603_uniroyal",
        "the gate, pull-down and indicator networks were sized for current, "
        "and the dissipation that follows has to fit the 0603 body chosen",
        (ANALYTIC,)),

    "within_forward_current": _derived(
        "each indicator runs below the LED's maximum forward current",
        FUNCTION, "kt0603r_kento",
        "the brief requires status indication but sets no current; the "
        "ceiling is the LED's own rating",
        (ANALYTIC,)),

    # --- flyback -----------------------------------------------------------

    "within_average_forward_current": _derived(
        "each flyback device carries the coil current within its average "
        "forward-current rating",
        DRIVE, ("1n4148w_semtech", "g2rl_omron"),
        "the brief requires the flyback device to be 'rated for the coil "
        "current'; the applicable rating is the average forward current",
        (ANALYTIC,)),

    "below_drain_source_breakdown": _derived(
        "the clamped turn-off voltage stays below the driver FET's "
        "drain-source breakdown",
        DRIVE, ("1n4148w_semtech", "ao3400a_aos"),
        "the brief requires clamping 'below the driver's breakdown voltage', "
        "which is the FET's BVdss plus the diode's forward drop as the clamp "
        "level",
        (ANALYTIC, CIRCUIT_SIM)),

    "within_the_declared_loop_target": _decision(
        "each flyback turn-off loop encloses no more than the declared area "
        "target",
        "the brief asks for 'a small turn-off loop' without a number; a "
        "declared area target makes 'small' checkable and lets the placement "
        "search be told to leave the loop alone",
        ("no numeric target, with the loop left to the placement cost "
         "function, which cannot see loop area at all",
         "a tighter target reached by placing the diode under the relay body, "
         "rejected because it puts copper where the coil pins need clearance"),
        (GEOMETRY,)),

    # --- input protection --------------------------------------------------

    "within_gate_source_maximum": _derived(
        "the reverse-polarity FET's gate-source stress stays within its "
        "maximum in either input polarity",
        POWER, "ao3401a_aos",
        "a gate-referenced reverse-polarity stage sees the full input across "
        "its gate-source junction when the input is reversed, which is the "
        "case the brief's 'tolerate reverse polarity' has to survive",
        (ANALYTIC,)),

    "below_a_tenth_of_the_input": _decision(
        "the reverse-polarity device drops less than a tenth of the input "
        "voltage at full load",
        "the brief requires reverse-polarity tolerance but says nothing about "
        "the forward drop it may cost; a tenth of the input is the budget "
        "this design allocates, and it is what leaves the coil rail above "
        "must-operate at the low end of the input tolerance",
        ("a series Schottky, rejected because its drop would consume most of "
         "the margin between the input minimum and the coil's must-operate "
         "voltage",
         "a larger drop absorbed by raising the input minimum, rejected "
         "because the brief fixes the input at 5 V"),
        (ANALYTIC,)),

    "within_reverse_standoff": _derived(
        "every clamp's reverse standoff voltage covers the working voltage of "
        "the conductor it protects",
        POWER, "tpd1e10b06_ti",
        "a clamp whose standoff is below the line's normal working voltage "
        "conducts in normal operation, so the brief's ESD requirement implies "
        "a standoff floor",
        (ANALYTIC,)),

    "every_entering_conductor_clamped": _user(
        "every logic-side conductor entering the board reaches a clamp, or is "
        "exempt for a stated reason",
        POWER, (STATIC, GEOMETRY), physical_test=True),

    # --- separation and insulation -----------------------------------------

    "no_copper_crosses_the_boundary": _user(
        "no conductor lies inside the isolation boundary on any layer except "
        "the relay contact pins and their terminals",
        SEPARATION, (GEOMETRY,)),

    "switched_and_logic_copper_are_separated": _user(
        "every conductor is wholly on the switched side or wholly on the "
        "logic side of the boundary",
        SEPARATION, (GEOMETRY,)),

    "at_or_above_the_reinforced_figure": _derived(
        "the boundary is at least as wide as the reinforced creepage the "
        "documented rating requires",
        SEPARATION, "clearance_creepage_ti_slup421",
        "the brief requires a figure 'derived from the documented rating'; "
        "the derivation is IEC 60664-1's creepage table at the selected "
        "pollution degree and material group, doubled for reinforced "
        "insulation",
        (GEOMETRY, DOCUMENTATION)),

    "at_or_above_the_component_creepage": _derived(
        "the boundary is at least as wide as the creepage the barrier "
        "component is itself certified for",
        SEPARATION, "g2rl_omron",
        "the relay body spans the boundary, so the board's own separation "
        "should not be the weaker of the two paths in parallel",
        (GEOMETRY, DOCUMENTATION)),

    "reinforced_clearance_at_category_III": _derived(
        "the boundary also meets reinforced clearance at the overvoltage "
        "category the relay is certified for, not only the category this "
        "board is designed to",
        SEPARATION, "clearance_creepage_ti_slup421",
        "the board is designed to category II; the relay carries a category "
        "III certification, and a boundary that fell short of category III "
        "would make the relay's certification the misleading part of the "
        "documentation",
        (GEOMETRY, DOCUMENTATION)),

    "within_the_certified_insulation_voltage": _derived(
        "the documented switched voltage is within the rated insulation "
        "voltage the barrier component is certified at",
        SEPARATION, "g2rl_omron",
        "the coil-to-contact barrier is the relay, and its certificate states "
        "the voltage that certification is valid at",
        (DOCUMENTATION,)),

    "assumptions_agree_with_the_certification": _derived(
        "the material group the clearance derivation assumed is no better "
        "than the one the barrier component is certified for",
        SEPARATION, "g2rl_omron",
        "the derivation picks a material group before any part is chosen; if "
        "the chosen barrier is certified for a worse group than the "
        "derivation assumed, the derived figure is optimistic",
        (DOCUMENTATION,)),

    # --- switched path -----------------------------------------------------

    "within_the_component_rating": _user(
        "the documented switched voltage and current are within the rating of "
        "every component in the switched path",
        CONNECTORS, (DOCUMENTATION,)),

    "temperature_rise_within_20C": _decision(
        "switched copper carries the marked current at no more than a 20 degC "
        "rise",
        "the brief sets no conductor temperature limit; 20 degC is the rise "
        "this design sizes switched copper for. No conductor-sizing standard "
        "is frozen in this repository, so the rise at the marked current is "
        "not established here and the claim is reported as unknown rather "
        "than assumed to pass",
        ("sizing against IPC-2152, which cannot be frozen into this "
         "repository as evidence",
         "a wider conductor chosen without a stated rise, which would make "
         "the width unreviewable"),
        (PHYSICAL_TEST,), physical_test=True),

    # --- markings, bring-up, assembly --------------------------------------

    "every_required_marking_present": _user(
        "the silkscreen carries each terminal's channel and contact function "
        "and the per-channel maximum voltage and current",
        SEPARATION, (GEOMETRY,)),

    "every_required_node_probed": _user(
        "the 5 V rail, ground, the coil supply and every driver input and "
        "coil node reach a probe on the logic side",
        BRING_UP, (GEOMETRY,)),

    "single_placement_side": _decision(
        "every part is placed on the front side",
        "a single placement side halves assembly setup and removes the "
        "second-side reflow the through-hole parts would otherwise "
        "complicate; nothing on this board needs the second side",
        ("both sides populated, which would shrink the board but add a "
         "placement side to the assembly quote",
         "logic parts on the back, rejected because it would put copper and "
         "parts on the layer the boundary keepout has to clear"),
        (GEOMETRY, MANUFACTURING_CHECK)),

    "as_declared": _decision(
        "the number of through-hole parts matches the assembly policy this "
        "board declares",
        "through-hole count drives the hand-soldering line on an assembly "
        "quote, so it is declared rather than discovered at quote time",
        ("no declared count, leaving the figure to be read off the board",),
        (GEOMETRY, MANUFACTURING_CHECK)),

    "at_or_above_the_planned_build_quantity": _derived(
        "the catalogue can supply the planned build quantity of the binding "
        "part",
        OPEN, "jlcpcb_catalogue_snapshot",
        "the relay is a single-sourced part with the lowest stock on the "
        "bill of materials, so the planned build quantity is a requirement on "
        "availability and not only on the design",
        (DOCUMENTATION,)),
}


# ---------------------------------------------------------------------------
# statements that no numeric claim is judged against

STATEMENTS = {

    "mcu_selection": _decision(
        "channel commands come from a PY32F003F18P6TU in a TSSOP-20 package",
        "the brief leaves the MCU open subject to I/O count, a defined reset "
        "state and adequate guaranteed drive; this part has all three, is "
        "stocked in the assembly catalogue, and its floating-input reset "
        "state is what lets the coils be held off by the pull-downs alone",
        ("a larger STM32, rejected as unnecessary I/O and cost for four "
         "channels",
         "a part with a defined pull-up at reset, rejected because it would "
         "fight the gate pull-downs during reset"),
        (STATIC, DOCUMENTATION)),

    "coil_supply_topology": _decision(
        "the coils take their own rail downstream of the reverse-polarity "
        "device, and the logic rail is fed from it through a series element",
        "the brief leaves this open; separating them keeps the coil turn-on "
        "step out of the MCU's supply, which is what makes the rail claim "
        "provable rather than marginal",
        ("coils on the logic rail directly, rejected because four coils "
         "switching together would put the whole step across the MCU",
         "a separate documented coil input, rejected because it would add a "
         "connector and a second supply the brief does not ask for"),
        (ANALYTIC, CIRCUIT_SIM)),

    "command_origin": _decision(
        "channel commands originate in firmware on the on-board MCU, with a "
        "non-isolated UART header for a host",
        "the brief leaves the origin and the isolation of the interface open; "
        "the interface is on the logic side of the boundary, so isolating it "
        "would add cost without changing what the boundary separates",
        ("an isolated host interface, rejected because the interface is "
         "already on the logic side of the reinforced barrier",
         "local switch inputs, rejected because they would need their own "
         "debounce and ESD treatment for no requirement in the brief"),
        (STATIC,)),

    "switched_rating": _decision(
        "the documented switched rating is 250 V rms at 4 A per channel",
        "the brief makes the rating the designer's choice and derives the "
        "clearances from it; 4 A is well inside the relay's 16 A contact "
        "rating and is set by the terminal and the switched copper rather "
        "than by the relay",
        ("the relay's full 16 A, rejected because the terminals and the "
         "switched copper would have to grow to carry it",
         "a low-voltage DC-only rating, rejected because it would waste the "
         "reinforced barrier the relay already provides"),
        (DOCUMENTATION,)),

    "relay_selection": _decision(
        "the barrier component is the Omron G2RL-1-E DC5",
        "it is a current product with a VDE reinforced coil-to-contact "
        "certification at 250 V, 8 mm of certified creepage and a 16 A "
        "contact rating, which leaves the board's 4 A rating limited by parts "
        "that are cheap to change",
        ("Omron G5Q-14 DC5, which would cut the bill of materials by 39 "
         "percent and quadruple available stock, rejected because its "
         "normally-closed contact is rated 3 A rather than 16 A and its "
         "certified creepage is 6.4 mm rather than 8 mm",),
        (DOCUMENTATION,)),

    "terminal_function_order": _decision(
        "each switched terminal presents its contacts in the order "
        "normally-open, common, normally-closed",
        "the three contact paths have to reach the terminal without crossing "
        "and without a via, because no switched conductor may leave the front "
        "layer; that constraint has exactly one planar solution, and this is "
        "it",
        ("normally-closed, common, normally-open, which has no planar "
         "solution for this relay's contact pin order",),
        (GEOMETRY,)),

    "input_path_budget": {
        "kind": ASSUMPTION,
        "statement": "the field wiring and the source feeding the input "
                     "terminal together present no more than 0.5 ohm",
        "reason": "the brief specifies an external 5 V input but nothing "
                  "about the impedance behind it, and every rail claim "
                  "depends on it",
        "revisable": True,
        "invalidated_by": "a measured source and harness resistance above the "
                          "budget, which would lower the coil rail and could "
                          "put it below must-operate",
        "verified_by": (PHYSICAL_TEST,),
        "physical_test_still_required": True,
    },

    "installation_environment": {
        "kind": ASSUMPTION,
        "statement": "the board is installed in a pollution degree 2, "
                     "material group III, overvoltage category II "
                     "environment",
        "reason": "the brief does not describe the installation, and the "
                  "creepage and clearance figures cannot be derived without "
                  "it",
        "revisable": True,
        "invalidated_by": "an installation at pollution degree 3, which the "
                          "relay is certified for but which the frozen table "
                          "subset in this repository carries no column for",
        "verified_by": (DOCUMENTATION,),
        "physical_test_still_required": False,
    },

    "maximum_ambient": {
        "kind": ASSUMPTION,
        "statement": "the maximum ambient the dissipation claims are "
                     "evaluated at is the reference ambient of the package "
                     "ratings they are compared against",
        "reason": "the brief conditions the dissipation requirement on "
                  "'maximum ambient' without stating one, and this board "
                  "does not yet state one either; the dissipation figures are "
                  "therefore established but the junction temperatures they "
                  "imply are not",
        "revisable": True,
        "invalidated_by": "any stated maximum ambient above the package "
                          "ratings' reference ambient, which would derate "
                          "every package figure these claims are judged "
                          "against",
        "verified_by": (THERMAL_SIM, PHYSICAL_TEST),
        "physical_test_still_required": True,
    },
}


# ---------------------------------------------------------------------------
# access

#: Origins that are not datasheets. Each names the file in the tree that the
#: requirement was derived from, so a citation cannot point at nothing.
NON_DOCUMENT_ORIGINS = {
    "jlcpcb_catalogue_snapshot": "components/jlcpcb.json",
}


def _brief_anchors():
    """The anchors BRIEF.md actually offers, from its own headings."""
    anchors = set()
    with open(os.path.join(REPO_ROOT, BRIEF), encoding="utf-8") as handle:
        for line in handle:
            if not line.startswith("#"):
                continue
            title = line.lstrip("#").strip().lower()
            anchors.add("".join(character for character in
                                title.replace(" ", "-").replace("—", "")
                                if character.isalnum() or character == "-"))
    return anchors


def _evidence_ids():
    with open(os.path.join(REPO_ROOT, "evidence", "index.json"),
              encoding="utf-8") as handle:
        index = json.load(handle)
    records = index if isinstance(index, list) else index.get("documents", [])
    if isinstance(records, dict):
        return set(records)
    return {record["id"] for record in records}


def check_origins():
    """Every citation resolves: a brief anchor, a frozen document, or a file.

    A register whose sources point at headings the brief does not have or
    datasheets the repository never froze reads exactly like one whose
    sources are real, which is why this is checked rather than reviewed.
    """
    anchors = _brief_anchors()
    documents = _evidence_ids()
    problems = []
    for name, record in sorted(list(REGISTER.items())
                               + list(STATEMENTS.items())):
        origins = record.get("origin", ())
        origins = (origins,) if isinstance(origins, str) else tuple(origins)
        cited = list(origins) + list(record.get("derived_from", ()))
        for origin in cited:
            if origin == name:
                continue
            if origin.startswith(BRIEF + "#"):
                anchor = origin.split("#", 1)[1]
                if anchor not in anchors:
                    problems.append("%s: %s has no such heading in %s"
                                    % (name, origin, BRIEF))
                continue
            if origin in documents:
                continue
            path = NON_DOCUMENT_ORIGINS.get(origin)
            if path is None:
                problems.append(
                    "%s: origin %r is neither a brief anchor, a frozen "
                    "evidence document, nor a declared file origin"
                    % (name, origin))
            elif not os.path.isfile(os.path.join(REPO_ROOT, path)):
                problems.append("%s: origin %r names %s, which does not exist"
                                % (name, origin, path))
    if problems:
        raise ValueError("requirement register cites sources that do not "
                         "resolve:\n  " + "\n  ".join(problems))
    return True


def entry(name):
    try:
        return REGISTER[name]
    except KeyError:
        raise KeyError(
            "requirement %r is judged by a claim but is not registered in "
            "design/requirements.py; every requirement states what kind of "
            "statement it is" % (name,))


def source_of(name):
    """The string a claim records as its requirement's source.

    Kind first, so a reader of one claim can see whether the requirement came
    from the brief or from this design without opening the register.
    """
    record = entry(name)
    origin = record.get("origin", name)
    if not isinstance(origin, str):
        origin = "+".join(origin)
    return "%s:%s" % (record["kind"], origin)


def _serialise(name, record):
    out = {"name": name}
    for key, value in sorted(record.items()):
        out[key] = list(value) if isinstance(value, tuple) else value
    return out


def check():
    """Every entry is well formed for the kind it declares."""
    problems = []
    for name, record in sorted(list(REGISTER.items())
                               + list(STATEMENTS.items())):
        kind = record.get("kind")
        if kind not in KINDS:
            problems.append("%s: kind %r is not one of %s"
                            % (name, kind, list(KINDS)))
            continue
        if not str(record.get("statement", "")).strip():
            problems.append("%s: no statement" % name)
        methods = record.get("verified_by") or ()
        if not methods:
            problems.append("%s: names no verification method" % name)
        for method in methods:
            if method not in METHODS:
                problems.append("%s: %r is not a verification method"
                                % (name, method))
        if kind == USER and not record.get("derived_from"):
            problems.append("%s: a user requirement cites its brief clause"
                            % name)
        if kind == DERIVED:
            if not record.get("derived_from"):
                problems.append("%s: a derived requirement states what it "
                                "was derived from" % name)
            if not str(record.get("rationale", "")).strip():
                problems.append("%s: a derived requirement states its "
                                "rationale" % name)
        if kind == DECISION:
            if not record.get("alternatives_considered"):
                problems.append("%s: a design decision states the "
                                "alternatives it was chosen over" % name)
            if not str(record.get("rationale", "")).strip():
                problems.append("%s: a design decision states its rationale"
                                % name)
        if kind == ASSUMPTION:
            if record.get("revisable") is not True:
                problems.append("%s: an assumption is revisable" % name)
            for field in ("reason", "invalidated_by"):
                if not str(record.get(field, "")).strip():
                    problems.append("%s: an assumption states its %s"
                                    % (name, field))
    if problems:
        raise ValueError("requirement register is malformed:\n  "
                         + "\n  ".join(problems))
    return check_origins()


def counts():
    tally = {}
    for record in list(REGISTER.values()) + list(STATEMENTS.values()):
        tally[record["kind"]] = tally.get(record["kind"], 0) + 1
    return tally


def document():
    check()
    return {
        "kind": "requirement-register",
        "schema": 1,
        "vocabulary": {"statement_kinds": list(KINDS),
                       "verification_methods": list(METHODS)},
        "requirements": [_serialise(name, record)
                         for name, record in sorted(REGISTER.items())],
        "statements": [_serialise(name, record)
                       for name, record in sorted(STATEMENTS.items())],
        "summary": counts(),
        "context": {
            "generated_by": "design/requirements.py",
            "join": "requirements[].name is the requirement name every claim "
                    "in generated/requirements.json is judged against; the "
                    "join is total in both directions",
            "statements": "statements[] are the design decisions and "
                          "assumptions no numeric claim is judged against, "
                          "including the choices that close the brief's open "
                          "questions",
        },
    }


def write():
    os.makedirs(os.path.dirname(REGISTER_PATH), exist_ok=True)
    with open(REGISTER_PATH, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(document(), handle, indent=2, sort_keys=True)
        handle.write("\n")
    return REGISTER_PATH


if __name__ == "__main__":
    sys.stdout.write(write() + "\n")
