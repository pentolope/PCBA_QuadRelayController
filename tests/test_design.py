from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from design import (build, clearance, cost, evidence, floorplan,  # noqa: E402
                    ksym, layout, models, netlist, place, requirements,
                    route, rules, simulation)

TOOLKIT_ROOT = os.path.join(REPO_ROOT, "tooling", "PCBA_AutoDesignAndTest")
if TOOLKIT_ROOT not in sys.path:
    sys.path.insert(0, TOOLKIT_ROOT)

from pcbqa.sim import scenario as sim_scenario  # noqa: E402


class DesignSource(unittest.TestCase):
    def test_pin_assignment_is_unique(self):
        mapping = netlist.pin_to_net()
        self.assertEqual(len(mapping),
                         sum(len(pins) for pins in netlist.NETS.values()))

    def test_every_symbol_pin_is_connected_or_declared_no_connect(self):
        library = ksym.Library(netlist.SYMBOL_LIBRARY_PATHS)
        mapping = netlist.pin_to_net()
        declared = set(netlist.NO_CONNECT)
        unresolved = []
        for reference, part in netlist.PARTS.items():
            for number in library.pins(part["lib_id"]):
                pin_ref = "%s.%s" % (reference, number)
                if pin_ref not in mapping and pin_ref not in declared:
                    unresolved.append(pin_ref)
        self.assertEqual(unresolved, [])

    def test_declared_pins_exist_on_the_symbol(self):
        library = ksym.Library(netlist.SYMBOL_LIBRARY_PATHS)
        missing = []
        for pin_ref in list(netlist.pin_to_net()) + list(netlist.NO_CONNECT):
            reference, _, number = pin_ref.partition(".")
            lib_id = netlist.PARTS[reference]["lib_id"]
            if number not in library.pins(lib_id):
                missing.append(pin_ref)
        self.assertEqual(missing, [])

    def test_switched_and_logic_nets_partition_the_netlist(self):
        self.assertEqual(
            sorted(set(netlist.SWITCHED_NETS) | set(netlist.LOGIC_NETS)),
            sorted(netlist.NETS))
        self.assertFalse(set(netlist.SWITCHED_NETS)
                         & set(netlist.LOGIC_NETS))

    def test_no_net_reaches_both_sides_of_the_boundary(self):
        mapping = netlist.pin_to_net()
        switched_pins = {pin for pin, net in mapping.items()
                         if net in netlist.SWITCHED_NETS}
        relay_or_terminal = re.compile(r"^(K\d+|J[2-9])\.")
        strays = sorted(pin for pin in switched_pins
                        if not relay_or_terminal.match(pin))
        self.assertEqual(strays, [])


class ChannelTopology(unittest.TestCase):
    def setUp(self):
        self.mapping = netlist.pin_to_net()

    def test_every_channel_has_a_driver_a_flyback_and_an_indicator(self):
        for channel in range(1, netlist.CHANNEL_COUNT + 1):
            coil = "RLY%d_C" % channel
            gate = "RLY%d_G" % channel
            self.assertEqual(self.mapping["Q%d.3" % channel], coil)
            self.assertEqual(self.mapping["Q%d.2" % channel], "GND")
            self.assertEqual(self.mapping["Q%d.1" % channel], gate)
            self.assertEqual(self.mapping["K%d.A2" % channel], coil)
            self.assertEqual(self.mapping["K%d.A1" % channel], "VCOIL")
            self.assertEqual(self.mapping["D%d.1" % channel], "VCOIL")
            self.assertEqual(self.mapping["D%d.2" % channel], coil)
            self.assertEqual(self.mapping["R%d.2" % (channel + 4)], "GND")
            self.assertEqual(self.mapping["R%d.1" % (channel + 4)], gate)
            self.assertEqual(self.mapping["D%d.1" % (channel + 4)], "GND")

    def test_each_contact_reaches_its_own_terminal_position(self):
        for channel in range(1, netlist.CHANNEL_COUNT + 1):
            for position, function in enumerate(netlist.TERMINAL_FUNCTIONS):
                net = "CH%d_%s" % (channel, function)
                self.assertEqual(
                    self.mapping["K%d.%s" % (channel,
                                             netlist.CONTACT_PINS[function])],
                    net)
                self.assertEqual(
                    self.mapping["J%d.%d" % (channel + 1, position + 1)], net)

    def test_the_command_pins_are_distinct_and_on_the_mcu(self):
        self.assertEqual(len(set(netlist.CHANNEL_COMMAND_PINS)),
                         netlist.CHANNEL_COUNT)
        for pin in netlist.CHANNEL_COMMAND_PINS:
            self.assertIn("U1.%s" % pin, self.mapping)


class Insulation(unittest.TestCase):
    def test_the_derived_figures_come_from_the_frozen_table(self):
        record = clearance.requirement_record()
        self.assertEqual(record["document"], clearance.EVIDENCE_DOCUMENT)
        self.assertIn(record["document"],
                      evidence.load_index()["documents"])
        self.assertGreaterEqual(record["within_channel_design_mm"],
                                record["basic_creepage_mm"])
        self.assertGreaterEqual(record["boundary_design_mm"],
                                record["reinforced_creepage_mm"])
        self.assertGreaterEqual(record["boundary_design_mm"],
                                record["reinforced_clearance_mm"])

    def test_the_reinforced_figure_is_at_least_the_relay_s_own(self):
        parameters = rules.load_parameters()
        relay = parameters["parts"][netlist.PARTS["K1"]["mpn"]]
        for key in ("clearance_mm", "creepage_mm"):
            self.assertGreaterEqual(clearance.BOUNDARY_MM,
                                    relay["isolation"][key]["value"])

    def test_the_committed_rules_are_the_ones_the_design_source_derives(self):
        with open(build.rules_path(), encoding="utf-8") as handle:
            self.assertEqual(handle.read(), clearance.rules_text())

    def test_the_boundary_band_is_the_derived_figure_plus_margin(self):
        band = layout.LOGIC_MIN_Y_MM - layout.SWITCHED_MAX_Y_MM
        self.assertGreaterEqual(band, clearance.BOUNDARY_MM)


class Placement(unittest.TestCase):
    def test_the_accepted_placement_never_names_an_anchor(self):
        accepted = layout.accepted_placement()
        self.assertTrue(accepted, "no placement has been accepted")
        self.assertFalse(set(accepted) & layout.LOCKED_REFERENCES)

    def test_every_accepted_pose_belongs_to_a_part(self):
        for reference in layout.accepted_placement():
            self.assertIn(reference, netlist.PARTS)

    def test_the_intent_locks_exactly_what_the_board_file_locks(self):
        self.assertEqual(sorted(floorplan.LOCKED_GLOBS),
                         sorted(layout.LOCKED_REFERENCES))

    def test_the_flyback_diodes_are_not_a_search_variable(self):
        for channel in range(1, netlist.CHANNEL_COUNT + 1):
            self.assertIn("D%d" % channel, layout.LOCKED_REFERENCES)

    def test_every_part_the_search_may_move_sits_in_a_declared_zone(self):
        zoned = set()
        for block in floorplan.blocks():
            zoned.update(block["refs"])
        movable = set(layout.fixed_placements()) - layout.LOCKED_REFERENCES
        self.assertEqual(sorted(movable - zoned), [])


class Evidence(unittest.TestCase):
    def test_the_frozen_documents_are_intact_and_all_referenced(self):
        self.assertEqual(evidence.verify(), [])

    def test_every_parameter_names_a_frozen_document(self):
        documents = set(evidence.load_index()["documents"])
        missing = []

        def walk(node, path):
            if isinstance(node, dict):
                if "document" in node:
                    if node["document"] not in documents:
                        missing.append((path, node["document"]))
                for key, value in node.items():
                    walk(value, path + "." + str(key))
            elif isinstance(node, list):
                for index, value in enumerate(node):
                    walk(value, "%s[%d]" % (path, index))

        walk(rules.load_parameters()["parts"], "parts")
        self.assertEqual(missing, [])

    def test_every_bom_part_has_a_catalogue_entry(self):
        catalog = cost.load_catalog()["parts"]
        for reference, part in sorted(netlist.PARTS.items()):
            if not part["in_bom"]:
                continue
            self.assertTrue(part["lcsc"], reference)
            self.assertIn(part["lcsc"], catalog, reference)

    def test_every_bom_part_has_frozen_parameters(self):
        parameters = rules.load_parameters()["parts"]
        for reference, part in sorted(netlist.PARTS.items()):
            if part["in_bom"]:
                self.assertIn(part["mpn"], parameters, reference)


class Requirements(unittest.TestCase):
    def test_no_board_rule_fails(self):
        failures = [(result["id"], result["identity"])
                    for result in rules.evaluate_all()
                    if result["verdict"]["result"] == "FAIL"]
        self.assertEqual(failures, [])

    def test_the_only_unresolved_claim_is_the_one_that_needs_a_measurement(self):
        unresolved = sorted(
            result["id"] for result in rules.evaluate_all()
            if result["verdict"]["result"] == "UNKNOWN")
        self.assertEqual(unresolved, ["switched_copper_temperature_rise"])

    def test_the_committed_requirement_evidence_is_current(self):
        with open(rules.REPORT_PATH, encoding="utf-8") as handle:
            committed = json.load(handle)
        self.assertEqual(committed["summary"],
                         rules.summarise(rules.evaluate_all()))
        self.assertEqual(len(committed["results"]),
                         sum(committed["summary"].values()))

    def test_every_probe_required_net_exists(self):
        for net in rules.PROBE_REQUIRED_NETS:
            self.assertIn(net, netlist.NETS)

    def test_every_entering_conductor_is_clamped_or_exempt(self):
        clamped = set()
        mapping = netlist.pin_to_net()
        for reference, part in netlist.PARTS.items():
            if part["mpn"] == "TPD1E10B06DPYR":
                clamped.add(mapping["%s.2" % reference])
        for net in rules.entering_conductors():
            if net in rules.ESD_EXEMPT:
                continue
            self.assertIn(net, clamped, net)


class Scenarios(unittest.TestCase):
    def test_every_scenario_validates(self):
        registry = os.path.basename(models.MODELS_PATH)
        for name in sorted(os.listdir(os.path.join(REPO_ROOT, "sim"))):
            if name == registry:
                continue
            path = os.path.join(REPO_ROOT, "sim", name)
            with open(path, encoding="utf-8") as handle:
                sim_scenario.validate_scenario(json.load(handle))

    def test_the_committed_scenarios_are_the_generated_ones(self):
        parameters = simulation._parameters()
        expected = {
            "pre_layout_rail_droop.json":
                simulation.rail_droop_scenario(parameters),
            "pre_layout_gate_hold_off.json":
                simulation.gate_hold_off_scenario(parameters),
            "pre_layout_coil_turn_off.json":
                simulation.coil_turn_off_scenario(parameters),
            "post_layout_rail_droop.json": simulation.rail_droop_scenario(
                parameters, simulation.EXTRACTED_MODEL_ALIAS),
        }
        for name, document in expected.items():
            with open(os.path.join(REPO_ROOT, "sim", name),
                      encoding="utf-8") as handle:
                self.assertEqual(json.load(handle), document, name)

    def test_the_extracted_model_alias_is_registered(self):
        with open(os.path.join(REPO_ROOT, "board", "manifest.json"),
                  encoding="utf-8") as handle:
            manifest = json.load(handle)
        paths = manifest["simulation"]["extracted_models"]["paths"]
        self.assertIn(simulation.EXTRACTED_MODEL_ALIAS, paths)


class Routing(unittest.TestCase):
    def test_the_router_never_touches_the_switched_side_or_the_plane(self):
        reserved = {"GND"} | set(netlist.SWITCHED_NETS)
        self.assertFalse(set(route.routed_nets()) & reserved)
        self.assertEqual(sorted(set(route.routed_nets()) | reserved),
                         sorted(netlist.NETS))

    def test_the_router_is_given_more_clearance_than_the_rule(self):
        self.assertGreater(route.ROUTER_CLEARANCE_MM, layout.CLEARANCE_MM)

    def test_the_recorded_route_adopted_the_board_in_the_tree(self):
        with open(route.PROVENANCE_PATH, encoding="utf-8") as handle:
            record = json.load(handle)
        self.assertIsNotNone(record["accepted_attempt"])
        self.assertEqual(record["adopted_sha256"],
                         route.digest(layout.BOARD_PATH))

    def test_the_recorded_placement_describes_the_intent_in_the_tree(self):
        with open(place.PROVENANCE_PATH, encoding="utf-8") as handle:
            record = json.load(handle)
        self.assertEqual(record["intent_sha256"],
                         route.digest(floorplan.INTENT_PATH))


class GeneratedArtifacts(unittest.TestCase):
    def test_the_committed_schematic_is_the_generated_one(self):
        with open(build.schematic_path(), encoding="utf-8") as handle:
            self.assertEqual(handle.read(), build.generate_schematic_text())

    def test_the_committed_intent_is_the_generated_one(self):
        with open(floorplan.INTENT_PATH, encoding="utf-8") as handle:
            self.assertEqual(json.load(handle), floorplan.document())

    def test_the_committed_evidence_index_is_the_computed_one(self):
        self.assertEqual(evidence.load_index(), evidence.compute_index())

    def test_the_physical_inputs_still_agree_with_the_approved_catalog(self):
        from design import physical
        self.assertEqual(physical.verify(), [])


class Manufacturability(unittest.TestCase):
    def test_the_fabrication_selection_is_feasible(self):
        with open(os.path.join(REPO_ROOT, "fab", "selection.json"),
                  encoding="utf-8") as handle:
            selection = json.load(handle)
        self.assertTrue(selection["feasible"])
        self.assertEqual(selection["rejections"], [])

    def test_the_requirements_match_what_the_board_actually_uses(self):
        with open(os.path.join(REPO_ROOT, "fab", "requirements.json"),
                  encoding="utf-8") as handle:
            requirements = json.load(handle)
        self.assertEqual(requirements["min_space_mm"],
                         build.DESIGN_RULES["min_clearance"])
        self.assertEqual(requirements["min_drill_mm"], layout.VIA_DRILL_MM)
        self.assertEqual(requirements["min_via_diameter_mm"],
                         layout.VIA_DIAMETER_MM)

    def test_the_build_can_be_supplied(self):
        limits = cost.stock_limited_boards()
        self.assertTrue(all(limit > 0 for limit in limits.values()), limits)


class RequirementRegister(unittest.TestCase):
    """Every requirement says what kind of statement it is."""

    def test_register_is_well_formed(self):
        self.assertTrue(requirements.check())

    def test_every_judged_requirement_is_registered(self):
        for result in rules.evaluate_all():
            requirement = result["claim"].get("requirement")
            if requirement:
                self.assertIn(requirement["name"], requirements.REGISTER,
                              "%s judges an unregistered requirement"
                              % result["id"])

    def test_every_registered_requirement_is_judged(self):
        self.assertTrue(rules.check_register_join(rules.evaluate_all()))

    def test_claim_sources_name_the_statement_kind(self):
        kinds = set(requirements.KINDS)
        for result in rules.evaluate_all():
            requirement = result["claim"].get("requirement")
            if not requirement:
                continue
            kind = requirement["source"].split(":", 1)[0]
            self.assertIn(kind, kinds,
                          "%s does not name a statement kind" % result["id"])

    def test_no_requirement_is_sourced_only_to_the_brief(self):
        """The defect this register exists to fix, kept fixed.

        Every requirement used to be recorded as though the brief had stated
        it, including thresholds this design derived and thresholds it simply
        chose. A bare brief path as a source is that defect returning.
        """
        for result in rules.evaluate_all():
            requirement = result["claim"].get("requirement")
            if requirement:
                self.assertNotEqual(requirement["source"],
                                    requirements.BRIEF, result["id"])

    def test_brief_clauses_cited_by_user_requirements_exist(self):
        anchors = requirements._brief_anchors()
        for name, record in requirements.REGISTER.items():
            if record["kind"] != requirements.USER:
                continue
            for clause in record["derived_from"]:
                self.assertIn(clause.split("#", 1)[1], anchors, name)

    def test_the_brief_open_choices_are_all_closed_by_a_decision(self):
        decisions = [record for record in requirements.STATEMENTS.values()
                     if record["kind"] == requirements.DECISION]
        self.assertGreaterEqual(len(decisions), 3, requirements.STATEMENTS)

    def test_the_unknown_claim_declares_a_physical_test(self):
        """An unprovable requirement has to say so, not go quiet."""
        for result in rules.evaluate_all():
            if result["verdict"]["result"] != "UNKNOWN":
                continue
            record = requirements.entry(
                result["claim"]["requirement"]["name"])
            self.assertTrue(record["physical_test_still_required"],
                            result["id"])

    def test_the_register_document_round_trips(self):
        path = requirements.write()
        with open(path, encoding="utf-8") as handle:
            document = json.load(handle)
        self.assertEqual(
            {entry["name"] for entry in document["requirements"]},
            set(requirements.REGISTER))


class BoardInTheTree(unittest.TestCase):
    """The routed board is a generated artifact; nothing may quietly replace
    it.

    Regenerating the board from the design source produces the placement and
    the switched copper but not the router's output, so a stray call to the
    layout writer leaves a file that still opens, still passes a casual look,
    and has lost every routed net. The routing record names the digest of the
    candidate that was accepted, so the check costs a hash.
    """

    def test_the_board_is_the_accepted_routing_candidate(self):
        with open(os.path.join(REPO_ROOT, "generated", "routing.json"),
                  encoding="utf-8") as handle:
            record = json.load(handle)
        self.assertEqual(route.digest(layout.BOARD_PATH),
                         record["adopted_sha256"],
                         "the board in the tree is not the routed candidate "
                         "generated/routing.json accepted; regenerate the "
                         "routing rather than committing this")


class DiodeModel(unittest.TestCase):
    """The flyback model is an upper bound, and only where it says it is."""

    def test_the_fit_reproduces_both_datasheet_points(self):
        parameters = rules.load_parameters()
        points = rules._spec(parameters, "D1")["diode"]["forward_voltage_max_v"]
        for current in models.FIT_CURRENTS_A:
            self.assertAlmostEqual(
                models.forward_voltage(parameters, current),
                points["%g" % current]["value"], places=9)

    def test_the_fit_bounds_the_datasheet_points_it_was_not_fitted_through(
            self):
        """Below the fitted range the chord is an extrapolation, and it is a
        low one: the model refuses there rather than returning a number that
        would understate the drop."""
        parameters = rules.load_parameters()
        points = rules._spec(parameters, "D1")["diode"]["forward_voltage_max_v"]
        for current in sorted(float(key) for key in points):
            if current in models.FIT_CURRENTS_A:
                continue
            with self.assertRaises(ValueError):
                models.forward_voltage(parameters, current)

    def test_the_bound_is_above_the_true_curve_of_a_diode_with_series_r(self):
        """The convexity argument, checked on a device that meets both limits.

        A diode with a positive series resistance passing through the same two
        datasheet maxima must lie at or below the chord everywhere between
        them; that is what licenses the fit to be called an upper bound.
        """
        import math
        parameters = rules.load_parameters()
        points = rules._spec(parameters, "D1")["diode"]["forward_voltage_max_v"]
        low, high = models.FIT_CURRENTS_A
        v_low = points["%g" % low]["value"]
        v_high = points["%g" % high]["value"]
        n_vt = 2.0 * models.thermal_voltage(25.0)
        series_ohm = ((v_high - v_low) - n_vt * math.log(high / low)) \
            / (high - low)
        self.assertGreater(series_ohm, 0.0)
        saturation = low * math.exp(-(v_low - low * series_ohm) / n_vt)
        for step in range(1, 20):
            current = low + (high - low) * step / 20.0
            physical = n_vt * math.log(current / saturation) \
                + current * series_ohm
            self.assertLessEqual(physical,
                                 models.forward_voltage(parameters, current)
                                 + 1e-12, current)

    def test_the_coil_current_is_inside_the_fitted_range(self):
        self.assertTrue(models.check())

    def test_the_registry_document_is_the_generated_one(self):
        with open(models.MODELS_PATH, encoding="utf-8") as handle:
            self.assertEqual(json.load(handle), json.loads(json.dumps(
                models.records(), sort_keys=True)))

    def test_the_manifest_declares_the_registry(self):
        with open(os.path.join(REPO_ROOT, "board", "manifest.json"),
                  encoding="utf-8") as handle:
            manifest = json.load(handle)
        self.assertEqual(manifest["simulation"]["models"],
                         os.path.relpath(models.MODELS_PATH, REPO_ROOT))


if __name__ == "__main__":
    unittest.main()
