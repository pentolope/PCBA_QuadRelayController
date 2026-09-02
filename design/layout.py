from __future__ import annotations

import json
import math
import os
import sys

from . import clearance, ksym, netlist

_TOOLKIT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "tooling", "PCBA_AutoDesignAndTest")
if _TOOLKIT not in sys.path:
    sys.path.insert(0, _TOOLKIT)

from pcbqa import headless  # noqa: E402

headless.suppress_blocking_ui()

import pcbnew  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOARD_PATH = os.path.join(REPO_ROOT, netlist.PROJECT_NAME + ".kicad_pcb")

FOOTPRINT_SEARCH_PATHS = (
    os.path.join(REPO_ROOT, "library"),
    "/usr/share/kicad/footprints",
)

#: Board coordinates run x right and y UP from the lower-left corner, which is
#: the frame every dimension in this module and in the clearance rules is
#: stated in. KiCad's own y runs down, so the mapping is applied once here.
ORIGIN_MM = (30.0, 118.0)

BOARD_W_MM = 140.0
BOARD_H_MM = 88.0

CHANNEL_CENTRES_MM = (19.0, 53.0, 87.0, 121.0)

# --- switched side -------------------------------------------------------
TERMINAL_PIN_Y_MM = 13.0
TERMINAL_PITCH_MM = 9.5
RELAY_COIL_Y_MM = 47.0
RELAY_PIN_SPAN_MM = 7.5
#: Relay contact rows, as the Omron drawing places them relative to the coil.
RELAY_CONTACT_OFFSETS_MM = {"NC": 15.0, "COM": 20.0, "NO": 25.0}
#: The relay's contact pin pair is centred on the terminal position its own
#: net drops straight down to; the other two contacts escape sideways. This is
#: the only assignment that routes the three contacts to three in-line
#: terminals without a crossing or a layer change.
RELAY_CENTRE_OFFSET_MM = -TERMINAL_PITCH_MM
TERMINAL_FUNCTIONS = netlist.TERMINAL_FUNCTIONS

SWITCHED_TRACK_MM = clearance.SWITCHED_TRACK_MM
RELAY_PAD_RADIUS_MM = 1.0

#: The isolation boundary. No copper of any net, on any layer, lies between
#: these two lines; a keepout rule area makes that a design rule rather than a
#: property of this generator. Both lines are derived - the switched side ends
#: at the topmost contact pad the relay puts there, and the logic side starts
#: the required reinforced figure above it - so neither can drift away from
#: the clearance the board claims.
BOUNDARY_MARGIN_MM = 1.0
SWITCHED_MAX_Y_MM = (RELAY_COIL_Y_MM - RELAY_CONTACT_OFFSETS_MM["NC"]
                     + RELAY_PAD_RADIUS_MM)
LOGIC_MIN_Y_MM = (SWITCHED_MAX_Y_MM + clearance.BOUNDARY_MM
                  + BOUNDARY_MARGIN_MM)

# --- logic side ----------------------------------------------------------
DRIVER_ROW_Y_MM = 53.0
GATE_ROW_Y_MM = 56.5
INDICATOR_ROW_Y_MM = 59.5
TESTPOINT_ROW_Y_MM = 62.0

EDGE_WIDTH_MM = 0.1
TRACK_WIDTH_MM = 0.25
CLEARANCE_MM = 0.15
EDGE_CLEARANCE_MM = 0.3
VIA_DIAMETER_MM = 0.6
VIA_DRILL_MM = 0.3
STITCH_TRACK_WIDTH_MM = 0.4
STITCH_GAP_MM = 0.35
ZONE_INSET_MM = 0.5

#: Every fastener is on the logic side and no closer to switched copper than
#: the boundary figure: a screw is a conductor at an unknown potential. The
#: switched edge is therefore unsupported between mounting points and relies
#: on the enclosure, which is recorded as an assumption rather than designed
#: around.
MOUNTING_HOLES_MM = {
    "H1": (5.0, 83.0),
    "H2": (135.0, 83.0),
    "H3": (32.5, 56.0),
    "H4": (100.5, 56.0),
}

#: Parts whose position is the design rather than a search space: the relays
#: straddle the boundary, the terminals sit under them at the pitch the
#: switched copper is generated from, and the mounting holes are mechanical.
#: They are locked in the board file so a placement search cannot move them.
def _anchored_references():
    refs = set(MOUNTING_HOLES_MM)
    for channel in range(1, netlist.CHANNEL_COUNT + 1):
        refs.add("K%d" % channel)
        refs.add("J%d" % (channel + 1))
    return frozenset(refs)


#: The flyback diodes. Their poses are not a search variable either, but for a
#: different reason: what makes them right is the area of the loop they close
#: with the coil pins, and a placement cost function that scores wirelength
#: and crossings cannot see a loop area at all.
def _loop_critical_references():
    return frozenset("D%d" % channel
                     for channel in range(1, netlist.CHANNEL_COUNT + 1))


SHARED_PLACEMENT = {
    "J1": (17.0, 81.0, 0.0),
    "D10": (26.0, 81.0, 0.0),
    "Q5": (30.0, 81.0, 180.0),
    "C1": (35.0, 81.0, 0.0),
    "C2": (39.5, 81.0, 0.0),
    "R16": (44.0, 81.0, 0.0),
    "C3": (48.5, 81.0, 0.0),
    "TP1": (25.0, 77.0, 0.0),
    "R14": (30.0, 77.0, 0.0),
    "TP2": (35.0, 77.0, 0.0),
    "R13": (39.5, 77.0, 0.0),
    "D9": (44.0, 77.0, 0.0),
    "TP3": (48.5, 77.0, 0.0),
    "TP4": (52.5, 77.0, 0.0),
    "U1": (60.0, 78.0, 180.0),
    "C4": (55.0, 73.0, 0.0),
    "D11": (60.0, 73.0, 0.0),
    "C5": (65.0, 73.0, 0.0),
    "C6": (54.0, 83.0, 0.0),
    "R15": (66.0, 83.0, 0.0),
    "J6": (76.0, 85.0, 0.0),
    "D12": (81.0, 76.0, 0.0),
    "D13": (81.0, 79.0, 0.0),
    "D14": (81.0, 82.0, 0.0),
    "J7": (92.0, 85.0, 0.0),
    "D15": (97.0, 79.0, 0.0),
    "D16": (97.0, 82.0, 0.0),
}


ANCHORED_REFERENCES = _anchored_references()
LOOP_CRITICAL_REFERENCES = _loop_critical_references()
#: Everything a placement search may not move.
LOCKED_REFERENCES = ANCHORED_REFERENCES | LOOP_CRITICAL_REFERENCES


def to_board(x_mm, y_mm):
    return (ORIGIN_MM[0] + x_mm, ORIGIN_MM[1] - y_mm)


def _point(x_mm, y_mm):
    bx, by = to_board(x_mm, y_mm)
    return pcbnew.VECTOR2I(pcbnew.FromMM(bx), pcbnew.FromMM(by))


def relay_origin(centre_mm):
    """Footprint origin (coil pin A1) for the relay of one channel."""
    return (centre_mm + RELAY_CENTRE_OFFSET_MM - RELAY_PIN_SPAN_MM / 2.0,
            RELAY_COIL_Y_MM)


def terminal_origin(centre_mm):
    return (centre_mm - TERMINAL_PITCH_MM, TERMINAL_PIN_Y_MM)


PLACEMENT_PATH = os.path.join(REPO_ROOT, "constraints", "placement.json")


def accepted_placement():
    """The placement a search accepted, if one has been recorded.

    Absent, the seed below is the placement. Present, it replaces the seed for
    every part that is not an anchor - an anchor is locked in the board file
    and the search cannot have moved it, so accepting one from this file would
    be accepting a value that never came from a search.
    """
    if not os.path.isfile(PLACEMENT_PATH):
        return {}
    with open(PLACEMENT_PATH, encoding="utf-8") as handle:
        document = json.load(handle)
    return {reference: tuple(pose)
            for reference, pose in document["placement"].items()
            if reference not in LOCKED_REFERENCES}


def fixed_placements():
    placed = dict(SHARED_PLACEMENT)
    for reference, (x, y) in MOUNTING_HOLES_MM.items():
        placed[reference] = (x, y, 0.0)
    for index, centre in enumerate(CHANNEL_CENTRES_MM):
        channel = index + 1
        x0, y0 = relay_origin(centre)
        placed["K%d" % channel] = (x0, y0, 0.0)
        placed["J%d" % (channel + 1)] = terminal_origin(centre) + (0.0,)
        placed["D%d" % channel] = (centre - 9.5, DRIVER_ROW_Y_MM, 0.0)
        placed["Q%d" % channel] = (centre - 4.0, DRIVER_ROW_Y_MM, 180.0)
        placed["R%d" % channel] = (centre + 1.5, DRIVER_ROW_Y_MM, 180.0)
        placed["R%d" % (channel + 4)] = (centre - 0.5, GATE_ROW_Y_MM, 0.0)
        placed["R%d" % (channel + 8)] = (centre + 5.5, GATE_ROW_Y_MM, 0.0)
        placed["D%d" % (channel + 4)] = (centre + 5.5, INDICATOR_ROW_Y_MM,
                                         0.0)
        placed["TP%d" % (channel + 4)] = (centre - 1.0, TESTPOINT_ROW_Y_MM,
                                          0.0)
        placed["TP%d" % (channel + 8)] = (centre - 7.0, TESTPOINT_ROW_Y_MM,
                                          0.0)
    for reference, pose in accepted_placement().items():
        if reference not in placed:
            raise KeyError("accepted placement names an unknown part: "
                           + reference)
        placed[reference] = pose
    return placed


def _footprint_dir(footprint):
    library, _, name = footprint.partition(":")
    for base in FOOTPRINT_SEARCH_PATHS:
        candidate = os.path.join(base, library + ".pretty")
        if os.path.isfile(os.path.join(candidate, name + ".kicad_mod")):
            return candidate, name
    raise FileNotFoundError(footprint)


_PIN_NAMES = {}


def _pin_name(lib_id, number):
    if lib_id not in _PIN_NAMES:
        library = ksym.Library(netlist.SYMBOL_LIBRARY_PATHS)
        _PIN_NAMES[lib_id] = {
            key: pins[0].name for key, pins in library.pins(lib_id).items()}
    return _PIN_NAMES[lib_id].get(number, "")


def _floating_net(board, reference, number):
    lib_id = netlist.PARTS[reference]["lib_id"]
    name = "unconnected-(%s-%s-Pad%s)" % (
        reference, _pin_name(lib_id, number).replace("/", "{slash}"), number)
    existing = board.GetNetInfo().GetNetItem(name)
    if existing is not None and existing.GetNetCode() != 0:
        return existing
    net = pcbnew.NETINFO_ITEM(board, name)
    board.Add(net)
    return net


def _load(board, reference, part, x, y, rotation, pin_net, nets):
    library_dir, name = _footprint_dir(part["footprint"])
    footprint = pcbnew.FootprintLoad(library_dir, name)
    if footprint is None:
        raise RuntimeError("could not load " + part["footprint"])
    library = part["footprint"].partition(":")[0]
    footprint.SetFPID(pcbnew.LIB_ID(library, name))
    footprint.SetPosition(_point(x, y))
    footprint.SetOrientationDegrees(rotation)
    footprint.SetReference(reference)
    footprint.SetValue(part["value"])
    footprint.Reference().SetLayer(pcbnew.F_Fab)
    footprint.Value().SetLayer(pcbnew.F_Fab)
    for key, value in (("MPN", part["mpn"]), ("LCSC", part["lcsc"]),
                       ("Manufacturer", part["manufacturer"])):
        if not value:
            continue
        footprint.SetField(key, value)
        for field in footprint.GetFields():
            if field.GetName() == key:
                field.SetLayer(pcbnew.F_Fab)
                field.SetVisible(False)
    if not part["in_bom"]:
        footprint.SetExcludedFromBOM(True)
    if reference in LOCKED_REFERENCES:
        footprint.SetLocked(True)
    for pad in footprint.Pads():
        number = pad.GetNumber()
        if not number:
            continue
        net_name = pin_net.get("%s.%s" % (reference, number))
        if net_name:
            pad.SetNet(nets[net_name])
        else:
            pad.SetNet(_floating_net(board, reference, number))
    board.Add(footprint)
    return footprint


def _nets(board):
    created = {}
    for name in sorted(netlist.NETS):
        net = pcbnew.NETINFO_ITEM(board, name)
        board.Add(net)
        created[name] = net
    return created


def _design_settings(board):
    board.SetCopperLayerCount(2)
    settings = board.GetDesignSettings()
    settings.m_TrackMinWidth = pcbnew.FromMM(0.15)
    settings.m_ViasMinSize = pcbnew.FromMM(0.45)
    settings.m_MinThroughDrill = pcbnew.FromMM(0.25)
    settings.m_CopperEdgeClearance = pcbnew.FromMM(EDGE_CLEARANCE_MM)
    settings.m_HoleClearance = pcbnew.FromMM(0.25)
    settings.m_HoleToHoleMin = pcbnew.FromMM(0.25)
    settings.m_ViasMinAnnularWidth = pcbnew.FromMM(0.1)
    settings.m_MinClearance = pcbnew.FromMM(CLEARANCE_MM)
    default_class = settings.m_NetSettings.GetDefaultNetclass()
    default_class.SetClearance(pcbnew.FromMM(CLEARANCE_MM))
    default_class.SetTrackWidth(pcbnew.FromMM(TRACK_WIDTH_MM))
    default_class.SetViaDiameter(pcbnew.FromMM(VIA_DIAMETER_MM))
    default_class.SetViaDrill(pcbnew.FromMM(VIA_DRILL_MM))


def _add_outline(board):
    corners = [(0.0, 0.0), (BOARD_W_MM, 0.0), (BOARD_W_MM, BOARD_H_MM),
               (0.0, BOARD_H_MM)]
    closed = corners + [corners[0]]
    for start, end in zip(closed, closed[1:]):
        shape = pcbnew.PCB_SHAPE(board)
        shape.SetShape(pcbnew.SHAPE_T_SEGMENT)
        shape.SetStart(_point(*start))
        shape.SetEnd(_point(*end))
        shape.SetLayer(pcbnew.Edge_Cuts)
        shape.SetWidth(pcbnew.FromMM(EDGE_WIDTH_MM))
        board.Add(shape)


def _rectangle_zone(board, corners, layers):
    zone = pcbnew.ZONE(board)
    layer_set = pcbnew.LSET()
    for layer in layers:
        layer_set.addLayer(layer)
    zone.SetLayerSet(layer_set)
    outline = zone.Outline()
    outline.NewOutline()
    for x, y in corners:
        bx, by = to_board(x, y)
        outline.Append(pcbnew.FromMM(bx), pcbnew.FromMM(by))
    return zone


def _add_ground_zone(board, net):
    """B.Cu ground, over the logic region only.

    The pour stops at the boundary line rather than being clipped by the
    keepout, so the file states the intent and the keepout proves it.
    """
    corners = [
        (ZONE_INSET_MM, LOGIC_MIN_Y_MM),
        (BOARD_W_MM - ZONE_INSET_MM, LOGIC_MIN_Y_MM),
        (BOARD_W_MM - ZONE_INSET_MM, BOARD_H_MM - ZONE_INSET_MM),
        (ZONE_INSET_MM, BOARD_H_MM - ZONE_INSET_MM),
    ]
    zone = _rectangle_zone(board, corners, (pcbnew.B_Cu,))
    zone.SetNet(net)
    zone.SetAssignedPriority(0)
    zone.SetLocalClearance(pcbnew.FromMM(CLEARANCE_MM))
    zone.SetMinThickness(pcbnew.FromMM(0.2))
    zone.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
    zone.SetThermalReliefGap(pcbnew.FromMM(0.3))
    zone.SetThermalReliefSpokeWidth(pcbnew.FromMM(0.4))
    board.Add(zone)
    return zone


def _add_boundary_keepout(board):
    """The switched/logic boundary, as a rule the DRC enforces.

    Nothing conductive may be inside it on either layer, so the separation
    survives a router, a plugin or a hand edit rather than depending on this
    generator having drawn the copper where it meant to.
    """
    corners = [
        (0.0, SWITCHED_MAX_Y_MM),
        (BOARD_W_MM, SWITCHED_MAX_Y_MM),
        (BOARD_W_MM, LOGIC_MIN_Y_MM),
        (0.0, LOGIC_MIN_Y_MM),
    ]
    zone = _rectangle_zone(board, corners, (pcbnew.F_Cu, pcbnew.B_Cu))
    zone.SetIsRuleArea(True)
    zone.SetDoNotAllowZoneFills(True)
    zone.SetDoNotAllowVias(True)
    zone.SetDoNotAllowTracks(True)
    zone.SetDoNotAllowPads(True)
    zone.SetDoNotAllowFootprints(False)
    board.Add(zone)
    return zone


def _add_track(board, start, end, layer, net, width_mm):
    track = pcbnew.PCB_TRACK(board)
    track.SetStart(start)
    track.SetEnd(end)
    track.SetLayer(layer)
    track.SetNet(net)
    track.SetWidth(pcbnew.FromMM(width_mm))
    board.Add(track)
    return track


def _add_via(board, position, net):
    via = pcbnew.PCB_VIA(board)
    via.SetPosition(position)
    via.SetWidth(pcbnew.F_Cu, pcbnew.FromMM(VIA_DIAMETER_MM))
    via.SetDrill(pcbnew.FromMM(VIA_DRILL_MM))
    via.SetNet(net)
    via.SetViaType(pcbnew.VIATYPE_THROUGH)
    via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    board.Add(via)
    return via


def _route(board, net, points, width_mm=TRACK_WIDTH_MM, layer=None):
    layer = pcbnew.F_Cu if layer is None else layer
    for start, end in zip(points, points[1:]):
        if start == end:
            continue
        _add_track(board, _point(*start), _point(*end), layer, net, width_mm)


def pad_of(footprint, number):
    for pad in footprint.Pads():
        if pad.GetNumber() == number:
            return pad
    raise KeyError("%s has no pad %s" % (footprint.GetReference(), number))


def pad_xy(footprint, number):
    position = pad_of(footprint, number).GetPosition()
    return (pcbnew.ToMM(position.x) - ORIGIN_MM[0],
            ORIGIN_MM[1] - pcbnew.ToMM(position.y))


def switched_paths(centre_mm):
    """The three contact routes of one channel, in board coordinates.

    Generated rather than listed: every vertex follows from the relay's pin
    pitch and the terminal's, so a change to either cannot leave a stale
    coordinate behind.
    """
    left = centre_mm + RELAY_CENTRE_OFFSET_MM - RELAY_PIN_SPAN_MM / 2.0
    right = left + RELAY_PIN_SPAN_MM
    drop = {name: centre_mm + (index - 1) * TERMINAL_PITCH_MM
            for index, name in enumerate(TERMINAL_FUNCTIONS)}
    rows = {name: RELAY_COIL_Y_MM - offset
            for name, offset in RELAY_CONTACT_OFFSETS_MM.items()}
    paths = {}
    for name in ("NC", "COM", "NO"):
        row = rows[name]
        target = drop[name]
        if left <= target <= right:
            paths[name] = [
                [(left, row), (target, row), (right, row)],
                [(target, row), (target, TERMINAL_PIN_Y_MM)],
            ]
        elif target > right:
            paths[name] = [[(left, row), (right, row), (target, row),
                            (target, TERMINAL_PIN_Y_MM)]]
        else:
            paths[name] = [[(right, row), (left, row), (target, row),
                            (target, TERMINAL_PIN_Y_MM)]]
    return paths


def _route_switched(board, nets):
    for index, centre in enumerate(CHANNEL_CENTRES_MM):
        channel = index + 1
        for name, polylines in sorted(switched_paths(centre).items()):
            net = nets["CH%d_%s" % (channel, name)]
            for points in polylines:
                _route(board, net, points, SWITCHED_TRACK_MM)


def _stitch(board, footprint, pad, net):
    """Drop a via just outside a surface pad and bond it to the plane."""
    position = pad.GetPosition()
    size = pad.GetSize()
    angle = math.radians(footprint.GetOrientationDegrees())
    long_axis_x = size.x >= size.y
    reach = (pcbnew.ToMM(size.x if long_axis_x else size.y) / 2.0
             + VIA_DIAMETER_MM / 2.0 + STITCH_GAP_MM)
    centre = footprint.GetPosition()
    delta_x = position.x - centre.x
    delta_y = position.y - centre.y
    if long_axis_x:
        axis = (math.cos(angle), math.sin(angle))
    else:
        axis = (-math.sin(angle), math.cos(angle))
    projection = axis[0] * delta_x + axis[1] * delta_y
    if abs(projection) < pcbnew.FromMM(0.05):
        others = [other.GetPosition() for other in footprint.Pads()
                  if other.GetNumber() != pad.GetNumber()]
        if others:
            nearest = min(others, key=lambda point: (
                (point.x - position.x) ** 2 + (point.y - position.y) ** 2))
            away_x = position.x - nearest.x
            away_y = position.y - nearest.y
        else:
            away_x, away_y = 0, -pcbnew.FromMM(1.0)
        length = math.hypot(away_x, away_y) or 1.0
        axis = (away_x / length, away_y / length)
    elif projection < 0:
        axis = (-axis[0], -axis[1])
    via_position = pcbnew.VECTOR2I(
        int(position.x + axis[0] * pcbnew.FromMM(reach)),
        int(position.y + axis[1] * pcbnew.FromMM(reach)))
    _add_via(board, via_position, net)
    _add_track(board, position, via_position, pcbnew.F_Cu, net,
               STITCH_TRACK_WIDTH_MM)


def _stitch_ground(board, footprints, nets):
    ground = nets["GND"]
    for reference, footprint in sorted(footprints.items()):
        for pad in footprint.Pads():
            if pad.GetNetname() != "GND":
                continue
            if pad.GetAttribute() != pcbnew.PAD_ATTRIB_SMD:
                continue
            _stitch(board, footprint, pad, ground)


def build(with_copper=True):
    """The board.

    `with_copper=False` produces the same placement with no tracks, vias or
    pours: the placement search refuses a board that already carries copper,
    because moving a footprint would leave its copper behind. Everything
    conductive is generated from the placement afterwards, so the two forms
    cannot disagree about where a part is.
    """
    board = pcbnew.CreateEmptyBoard()
    _design_settings(board)
    nets = _nets(board)
    pin_net = netlist.pin_to_net()

    footprints = {}
    placed = fixed_placements()
    for reference, (x, y, rotation) in sorted(placed.items()):
        part = netlist.PARTS[reference]
        if not part["footprint"]:
            continue
        footprints[reference] = _load(
            board, reference, part, x, y, rotation, pin_net, nets)

    _add_outline(board)
    _add_boundary_keepout(board)
    if with_copper:
        _add_ground_zone(board, nets["GND"])
        _route_switched(board, nets)
        _stitch_ground(board, footprints, nets)
    _add_silkscreen(board, placed, footprints)
    return board, footprints


SILK_LAYER = pcbnew.F_SilkS
SILK_TEXT_MM = 1.2
SILK_THICKNESS_MM = 0.2

#: Where the relay's own silkscreen sits, relative to the channel centre. The
#: relay body deliberately spans the boundary, so the boundary marking is
#: drawn in the gaps between relays rather than through them.
RELAY_SILK_X_MM = (-16.4, -2.9)
TERMINAL_LABEL_Y_MM = 18.6
BOUNDARY_MARK_Y_MM = (34.0, 41.0)
NOTICE_Y_MM = 65.5


def _text(board, value, x, y, size_mm=SILK_TEXT_MM, layer=None):
    item = pcbnew.PCB_TEXT(board)
    item.SetText(value)
    item.SetPosition(_point(x, y))
    item.SetLayer(SILK_LAYER if layer is None else layer)
    item.SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(size_mm),
                                     pcbnew.FromMM(size_mm)))
    item.SetTextThickness(pcbnew.FromMM(SILK_THICKNESS_MM))
    item.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_CENTER)
    item.SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_CENTER)
    board.Add(item)
    return item


def _silk_line(board, x0, x1, y):
    shape = pcbnew.PCB_SHAPE(board)
    shape.SetShape(pcbnew.SHAPE_T_SEGMENT)
    shape.SetStart(_point(x0, y))
    shape.SetEnd(_point(x1, y))
    shape.SetLayer(SILK_LAYER)
    shape.SetWidth(pcbnew.FromMM(0.25))
    board.Add(shape)
    return shape


def rating_text():
    rating = netlist.SWITCHED_RATING
    return "%gV~ %gA" % (rating["voltage_rms_v"], rating["current_a"])


def boundary_gaps_mm(margin_mm=1.0):
    """The x spans in which the boundary marking may be drawn.

    Everything except the relays, whose bodies are the one thing that crosses
    the boundary and whose own silkscreen is already there.
    """
    blocked = sorted((centre + RELAY_SILK_X_MM[0] - margin_mm,
                      centre + RELAY_SILK_X_MM[1] + margin_mm)
                     for centre in CHANNEL_CENTRES_MM)
    gaps = []
    cursor = margin_mm
    for low, high in blocked:
        if low - cursor > 2 * margin_mm:
            gaps.append((cursor, low))
        cursor = max(cursor, high)
    if BOARD_W_MM - margin_mm - cursor > 2 * margin_mm:
        gaps.append((cursor, BOARD_W_MM - margin_mm))
    return gaps


#: Which nets a labelled probe carries, keyed by its reference. The label is
#: what makes the probe usable; the reference designator is on the fabrication
#: layer and invisible on the assembled board.
def probe_labels():
    labels = {"TP1": "V5IN", "TP2": "VCOIL", "TP3": "+5V", "TP4": "GND"}
    for channel in range(1, netlist.CHANNEL_COUNT + 1):
        labels["TP%d" % (channel + 4)] = "%dG" % channel
        labels["TP%d" % (channel + 8)] = "%dC" % channel
    return labels


#: Where a probe label may go, in preference order: beside it, then above or
#: below, then the diagonals, then further out.
LABEL_OFFSETS_MM = tuple(
    (round(radius * dx, 3), round(radius * dy, 3))
    for radius in (2.0, 2.8, 3.6)
    for dx, dy in ((1.0, 0.0), (-1.0, 0.0), (0.0, 1.0), (0.0, -1.0),
                   (0.7, 0.7), (-0.7, 0.7), (0.7, -0.7), (-0.7, -0.7)))
LABEL_TEXT_MM = 0.8
LABEL_MARGIN_MM = 0.2


def _label_half_mm(text):
    """Half the box a centred silkscreen label occupies, plus its margin."""
    width = 0.75 * LABEL_TEXT_MM * len(text) + SILK_THICKNESS_MM
    return (width / 2.0 + LABEL_MARGIN_MM,
            LABEL_TEXT_MM / 2.0 + SILK_THICKNESS_MM + LABEL_MARGIN_MM)


def _courtyard_boxes(footprints, exclude):
    """Every placed part's courtyard, in board coordinates."""
    boxes = []
    for reference, footprint in footprints.items():
        if reference == exclude:
            continue
        box = footprint.GetCourtyard(pcbnew.F_CrtYd).BBox()
        if box.GetWidth() <= 0 or box.GetHeight() <= 0:
            box = footprint.GetBoundingBox(False, False)
        x0 = pcbnew.ToMM(box.GetLeft()) - ORIGIN_MM[0]
        x1 = pcbnew.ToMM(box.GetRight()) - ORIGIN_MM[0]
        y0 = ORIGIN_MM[1] - pcbnew.ToMM(box.GetBottom())
        y1 = ORIGIN_MM[1] - pcbnew.ToMM(box.GetTop())
        boxes.append((min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)))
    return boxes


def _label_position(footprints, reference, text):
    """The first offset whose label box clears every other part.

    The probe positions come from the placement search, so a fixed offset
    would collide with whatever the search moved next to them; this picks a
    free side instead of assuming one.
    """
    origin = footprints[reference].GetPosition()
    x = pcbnew.ToMM(origin.x) - ORIGIN_MM[0]
    y = ORIGIN_MM[1] - pcbnew.ToMM(origin.y)
    half_x, half_y = _label_half_mm(text)
    boxes = _courtyard_boxes(footprints, reference)
    for dx, dy in LABEL_OFFSETS_MM:
        lx, ly = x + dx, y + dy
        box = (lx - half_x, ly - half_y, lx + half_x, ly + half_y)
        if not (LABEL_MARGIN_MM < box[0] and box[2] < BOARD_W_MM
                and LOGIC_MIN_Y_MM < box[1] and box[3] < BOARD_H_MM):
            continue
        if all(box[2] <= other[0] or box[0] >= other[2]
               or box[3] <= other[1] or box[1] >= other[3]
               for other in boxes):
            return lx, ly
    return None


def _add_silkscreen(board, placed, footprints):
    """What a person has to be able to read off the assembled board.

    The terminal functions and the per-channel rating are stated
    requirements; the boundary marking is what makes the two halves obvious
    without a drawing to hand.
    """
    for index, centre in enumerate(CHANNEL_CENTRES_MM):
        channel = index + 1
        for position, name in enumerate(TERMINAL_FUNCTIONS):
            _text(board, "CH%d %s" % (channel, name),
                  centre + (position - 1) * TERMINAL_PITCH_MM,
                  TERMINAL_LABEL_Y_MM, 1.0)
        _text(board, rating_text(), centre + 2.0,
              sum(BOUNDARY_MARK_Y_MM) / 2.0, 1.2)
    for y in BOUNDARY_MARK_Y_MM:
        for x0, x1 in boundary_gaps_mm():
            _silk_line(board, x0, x1, y)
    _text(board, "SWITCHED SIDE BELOW THE GAP - HAZARDOUS LIVE",
          BOARD_W_MM / 2.0, NOTICE_Y_MM, 1.5)
    _text(board, "5V IN %g-%g V dc"
          % (netlist.INPUT_SUPPLY["min_v"], netlist.INPUT_SUPPLY["max_v"]),
          placed["J1"][0], placed["J1"][1] - 7.4, 1.0)
    for reference, label in sorted(probe_labels().items()):
        position = _label_position(footprints, reference, label)
        if position is None:
            raise RuntimeError(
                "no free side to label probe %s; the placement leaves it "
                "boxed in" % reference)
        _text(board, label, position[0], position[1], LABEL_TEXT_MM)
    for reference, label in (("J6", "SWD"), ("J7", "UART")):
        x, y, _rotation = placed[reference]
        _text(board, label, x + 3.4, y, 1.0)


def fill_zones(board):
    """Cache the pour in the file, so the board describes its own copper."""
    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(board.Zones())
    board.BuildConnectivity()
    return board


def write():
    board, _ = build()
    fill_zones(board)
    pcbnew.SaveBoard(BOARD_PATH, board)
    return BOARD_PATH


def write_placement_board(path):
    """The placement search's input: parts, outline and keepout, no copper."""
    board, _ = build(with_copper=False)
    pcbnew.SaveBoard(path, board)
    return path


if __name__ == "__main__":
    sys.stdout.write(write() + "\n")
