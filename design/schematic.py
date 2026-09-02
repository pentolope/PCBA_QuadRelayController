from __future__ import annotations

import uuid

from . import ksym, sexpr

NAMESPACE = uuid.UUID("6f2b1d9c-4a35-5f18-9c77-1b0e3a5d7c42")

CELL_MM = 63.5
COLUMNS = 12
ORIGIN_MM = (38.1, 38.1)
FONT = ["effects", ["font", ["size", "1.27", "1.27"]]]


def _uuid(*parts):
    return sexpr.Quoted(str(uuid.uuid5(NAMESPACE, "/".join(parts))))


def _fmt(value):
    text = "%.4f" % value
    text = text.rstrip("0").rstrip(".")
    return text if text not in ("", "-0") else "0"


def _property(key, value, x, y, hide):
    node = ["property", sexpr.Quoted(key), sexpr.Quoted(value),
            ["at", _fmt(x), _fmt(y), "0"]]
    if hide:
        node.append(["hide", "yes"])
    node.append(list(FONT))
    return node


def _cell_origin(index):
    column = index % COLUMNS
    row = index // COLUMNS
    return (ORIGIN_MM[0] + column * CELL_MM, ORIGIN_MM[1] + row * CELL_MM)


def pin_positions(library, lib_id, origin):
    positions = {}
    for number, pins in library.pins(lib_id).items():
        pin = pins[0]
        positions[number] = (origin[0] + pin.x, origin[1] - pin.y)
    return positions


def build(parts, nets, no_connect, project_name):
    library = ksym.Library(_library_paths())
    schematic_uuid = _uuid("sheet", project_name)

    placement = {}
    for index, reference in enumerate(sorted(parts, key=_reference_key)):
        placement[reference] = _cell_origin(index)

    lib_symbols = ["lib_symbols"]
    for lib_id in sorted({part["lib_id"] for part in parts.values()}):
        node = library.resolve(lib_id)
        node[1] = sexpr.Quoted(lib_id)
        lib_symbols.append(node)

    body = []
    for reference in sorted(parts, key=_reference_key):
        part = parts[reference]
        origin = placement[reference]
        body.append(_symbol_instance(
            reference, part, origin, schematic_uuid, project_name, library))

    pin_net = {}
    for net_name, pin_refs in nets.items():
        for pin_ref in pin_refs:
            pin_net[pin_ref] = net_name

    for reference in sorted(parts, key=_reference_key):
        part = parts[reference]
        origin = placement[reference]
        positions = pin_positions(library, part["lib_id"], origin)
        for number in sorted(positions):
            pin_ref = "%s.%s" % (reference, number)
            x, y = positions[number]
            if pin_ref in pin_net:
                body.append(_global_label(pin_net[pin_ref], x, y, pin_ref))
            elif pin_ref in no_connect:
                body.append(["no_connect", ["at", _fmt(x), _fmt(y)],
                             ["uuid", _uuid("nc", pin_ref)]])
            else:
                raise ValueError(
                    "pin %s is neither connected nor declared no-connect"
                    % pin_ref)

    return ["kicad_sch",
            ["version", "20251006"],
            ["generator", sexpr.Quoted("quad-relay-controller-design-source")],
            ["generator_version", sexpr.Quoted("10.0")],
            ["uuid", schematic_uuid],
            ["paper", sexpr.Quoted("User"), "850", "500"],
            lib_symbols] + body + [
            ["sheet_instances", ["path", sexpr.Quoted("/"),
                                 ["page", sexpr.Quoted("1")]]],
            ["embedded_fonts", "no"]]


def _library_paths():
    from .netlist import SYMBOL_LIBRARY_PATHS
    return SYMBOL_LIBRARY_PATHS


def _reference_key(reference):
    prefix = reference.rstrip("0123456789")
    digits = reference[len(prefix):]
    return (prefix, int(digits) if digits else 0)


def _symbol_instance(reference, part, origin, schematic_uuid, project_name,
                     library):
    x, y = origin
    node = ["symbol",
            ["lib_id", sexpr.Quoted(part["lib_id"])],
            ["at", _fmt(x), _fmt(y), "0"],
            ["unit", "1"],
            ["exclude_from_sim", "no"],
            ["in_bom", "yes" if part["in_bom"] else "no"],
            ["on_board", "yes" if part["on_board"] else "no"],
            ["dnp", "no"],
            ["uuid", _uuid("symbol", reference)],
            _property("Reference", reference, x, y - 22.86, False),
            _property("Value", part["value"], x, y - 20.32, False),
            _property("Footprint", part["footprint"], x, y, True),
            _property("Datasheet", part["datasheet"], x, y, True)]
    if part["mpn"]:
        node.append(_property("MPN", part["mpn"], x, y, True))
    if part["manufacturer"]:
        node.append(_property("Manufacturer", part["manufacturer"], x, y,
                              True))
    if part.get("lcsc"):
        node.append(_property("LCSC", part["lcsc"], x, y, True))
    node.append(["instances",
                 ["project", sexpr.Quoted(project_name),
                  ["path", sexpr.Quoted("/" + str(schematic_uuid)),
                   ["reference", sexpr.Quoted(reference)],
                   ["unit", "1"]]]])
    return node


def _global_label(net_name, x, y, pin_ref):
    return ["global_label", sexpr.Quoted(net_name),
            ["shape", "bidirectional"],
            ["at", _fmt(x), _fmt(y), "0"],
            list(FONT) + [["justify", "left"]],
            ["uuid", _uuid("label", pin_ref)]]


def render(tree):
    return sexpr.dump(tree) + "\n"
