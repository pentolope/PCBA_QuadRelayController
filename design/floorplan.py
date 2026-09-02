"""Floorplan intent: where each part belongs, and what it may not cross.

This is the placement contract the search engine works inside. It is derived
from the same constants the layout and the clearance policy use, in the page
coordinates the routing toolchain reads, so a zone cannot drift away from the
boundary it is supposed to describe.
"""
from __future__ import annotations

import json
import os
import sys

from . import clearance, layout, netlist

INTENT_PATH = os.path.join(layout.REPO_ROOT, "constraints", "floorplan.json")

#: What the search may not move: the relays and terminals whose pitches the
#: switched copper is generated from, the mechanical fasteners, and the
#: flyback diodes, whose loop area no placement cost function can see.
LOCKED_GLOBS = tuple(sorted(layout.LOCKED_REFERENCES))

#: Bands, in board coordinates (y up from the lower-left corner).
TERMINAL_BAND = (0.0, layout.TERMINAL_PIN_Y_MM + 5.0)
RELAY_BAND = (TERMINAL_BAND[1], layout.RELAY_COIL_Y_MM + 3.0)
DRIVER_BAND = (RELAY_BAND[1], layout.TESTPOINT_ROW_Y_MM + 2.5)
SHARED_BAND = (DRIVER_BAND[1] + 2.0, layout.BOARD_H_MM)

#: How far either side of its channel centre a driver cell may spread.
CHANNEL_HALF_WIDTH_MM = 17.0


def to_page(x_mm, y_mm):
    return layout.to_board(x_mm, y_mm)


def _rect(x0, y0, x1, y1):
    """A board-coordinate rectangle as the page-coordinate rect intent wants."""
    ax, ay = to_page(x0, y0)
    bx, by = to_page(x1, y1)
    return [round(min(ax, bx), 4), round(min(ay, by), 4),
            round(max(ax, bx), 4), round(max(ay, by), 4)]


def channel_refs(channel):
    """Every part of one channel's driver cell."""
    return ["D%d" % channel, "Q%d" % channel, "R%d" % channel,
            "R%d" % (channel + 4), "R%d" % (channel + 8),
            "D%d" % (channel + 4), "TP%d" % (channel + 4),
            "TP%d" % (channel + 8)]


def shared_refs():
    return sorted(set(layout.SHARED_PLACEMENT) - set(LOCKED_GLOBS))


def blocks():
    entries = [
        {"name": "switched_terminals",
         "refs": sorted("J%d" % (channel + 1)
                        for channel in range(1, netlist.CHANNEL_COUNT + 1)),
         "zone": _rect(0.0, TERMINAL_BAND[0],
                       layout.BOARD_W_MM, TERMINAL_BAND[1]),
         "side": "F",
         "exclusive": True,
         "note": "the only parts allowed below the boundary are the "
                 "terminals the switched contacts leave through"},
        {"name": "relays",
         "refs": sorted("K%d" % channel
                        for channel in range(1, netlist.CHANNEL_COUNT + 1)),
         "zone": _rect(0.0, RELAY_BAND[0],
                       layout.BOARD_W_MM, RELAY_BAND[1]),
         "side": "F",
         "note": "each relay body spans the boundary; its coil pins are on "
                 "the logic side and its contact pins on the switched side"},
    ]
    for index, centre in enumerate(layout.CHANNEL_CENTRES_MM):
        channel = index + 1
        entries.append({
            "name": "driver_ch%d" % channel,
            "refs": channel_refs(channel),
            "zone": _rect(centre - CHANNEL_HALF_WIDTH_MM, DRIVER_BAND[0],
                          centre + CHANNEL_HALF_WIDTH_MM, DRIVER_BAND[1]),
            "side": "F",
            "note": "channel %d driver, flyback and indicator stay above "
                    "their own relay" % channel,
        })
    entries.append({
        "name": "shared_logic",
        "refs": shared_refs(),
        "zone": _rect(0.0, SHARED_BAND[0], layout.BOARD_W_MM, SHARED_BAND[1]),
        "side": "F",
        "note": "supply input, protection, MCU and the two host-facing "
                "headers",
    })
    return entries


def keepouts():
    return [{
        "name": "isolation_boundary",
        "rect": _rect(0.0, layout.SWITCHED_MAX_Y_MM,
                      layout.BOARD_W_MM, layout.LOGIC_MIN_Y_MM),
        "sides": ["F", "B"],
        "allow": sorted("K%d" % channel
                        for channel in range(1, netlist.CHANNEL_COUNT + 1)),
        "note": "%g mm of bare laminate; only the relay bodies cross it, and "
                "they carry no pad inside it"
                % (layout.LOGIC_MIN_Y_MM - layout.SWITCHED_MAX_Y_MM),
        "context": {
            "derived_from": "IEC 60664-1 reinforced creepage at %g V rms, "
                            "pollution degree %d, material group %s"
                            % (clearance.WORKING_VOLTAGE_V,
                               clearance.POLLUTION_DEGREE,
                               clearance.MATERIAL_GROUP),
            "required_mm": clearance.BOUNDARY_MM,
        },
    }]


def edge_connectors():
    entries = []
    span = layout.BOARD_W_MM
    for index, centre in enumerate(layout.CHANNEL_CENTRES_MM):
        entries.append({
            "ref": "J%d" % (index + 2),
            "edge": "south",
            "along_edge_band": {"from": round((centre - 6.0) / span, 4),
                                "to": round((centre + 6.0) / span, 4)},
            "note": "field wiring leaves the switched edge, away from the "
                    "logic side",
        })
    for reference in ("J1", "J6", "J7"):
        entries.append({
            "ref": reference,
            "edge": "north",
            "note": "logic-side connector, reachable without crossing the "
                    "boundary",
        })
    return entries


def document():
    return {
        "schema": 1,
        "kind": "floorplan-intent",
        "units": "mm",
        "board": netlist.PROJECT_NAME + ".kicad_pcb",
        "defaults": {"zone_tolerance_mm": 0.5},
        "blocks": blocks(),
        "keepouts": keepouts(),
        "edge_connectors": edge_connectors(),
        "must_lock": list(LOCKED_GLOBS),
        "severity": {"decap_ungraded": "warn"},
        "context": {
            "generated_by": "design/floorplan.py",
            "frame": "page millimetres; the board's lower-left corner is at "
                     "page (%g, %g)" % layout.ORIGIN_MM,
        },
    }


def write():
    os.makedirs(os.path.dirname(INTENT_PATH), exist_ok=True)
    with open(INTENT_PATH, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(document(), handle, indent=2, sort_keys=True)
        handle.write("\n")
    return INTENT_PATH


if __name__ == "__main__":
    sys.stdout.write(write() + "\n")
