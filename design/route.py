from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import subprocess
import sys

import pcbnew

from . import build, layout, netlist

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "tooling", "PCBA_AutoDesignAndTest"))

from pcbqa import routing_record  # noqa: E402

REPO_ROOT = layout.REPO_ROOT
CANDIDATE_ROOT = os.path.join(REPO_ROOT, "candidates")
CANDIDATE_NAME = "route-current"
PROVENANCE_PATH = os.path.join(REPO_ROOT, "generated", "routing.json")

MANIFEST = os.path.join(REPO_ROOT, "board", "manifest.json")
VALIDATOR = os.path.join(REPO_ROOT, "tooling", "PCBA_AutoDesignAndTest",
                         "run.py")


def routed_nets():
    """Everything the search is allowed to draw.

    Ground is a plane with a stitched via at every surface pad, and the
    switched side is generated deterministically because its topology and its
    clearances are the design, not a search space. What is left is ordinary
    logic connectivity.
    """
    reserved = {"GND"} | set(netlist.SWITCHED_NETS)
    return tuple(sorted(name for name in netlist.NETS
                        if name not in reserved))


#: The router is given a wider clearance than the rule the board is judged by.
#: It takes the figure from the project's Default net class, not from its own
#: --clearance flag, and its 45-degree segments then land short of it: asked
#: for 0.15 mm it produced copper KiCad measured at 0.114 mm. So the candidate
#: is routed against a project carrying this margin, and judged against the
#: authoritative one, which `_adopt` restores.
ROUTER_CLEARANCE_MM = 0.25

ROUTER_OPTIONS = (
    "--track-width", str(layout.TRACK_WIDTH_MM),
    "--clearance", str(ROUTER_CLEARANCE_MM),
    "--via-size", str(layout.VIA_DIAMETER_MM),
    "--via-drill", str(layout.VIA_DRILL_MM),
    "--board-edge-clearance", "0.45",
    "--hole-to-hole-clearance", "0.3",
    "--same-net-pad-clearance", "0.3",
)

# The router is deterministic for a fixed input, so a bare retry explores
# nothing. Each attempt varies the net-ordering strategy instead, which is
# what actually produces a different candidate.
ATTEMPT_ORDERINGS = ("inside_out", "original", "mps")
MAX_ATTEMPTS = len(ATTEMPT_ORDERINGS)

SNAP_TOLERANCE_MM = 0.25
TOUCH_TOLERANCE_MM = 0.01


def _krt():
    sys.path.insert(0, os.path.join(REPO_ROOT, "tooling",
                                    "PCBA_AutoDesignAndTest"))
    from pcbqa import krt
    return krt


def digest(path):
    hasher = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _summary(text):
    for line in text.splitlines():
        if line.strip().startswith("JSON_SUMMARY_MIN:"):
            return json.loads(line.split("JSON_SUMMARY_MIN:", 1)[1])
    return {}


def _route_once(krt, resolved, candidate, attempt, placed_pcb):
    stage_dir = os.path.join(candidate, "attempt-%02d" % attempt)
    os.makedirs(stage_dir, exist_ok=True)
    source_pcb = os.path.join(stage_dir, "source.kicad_pcb")
    shutil.copy(placed_pcb, source_pcb)
    shutil.copy(os.path.join(REPO_ROOT, netlist.PROJECT_NAME + ".kicad_dru"),
                os.path.join(stage_dir, "source.kicad_dru"))
    _write_routing_project(os.path.join(stage_dir, "source.kicad_pro"))
    routed_pcb = os.path.join(stage_dir, "routed.kicad_pcb")
    command = [sys.executable,
               os.path.join(resolved["path"], "py_router", "route.py"),
               source_pcb, routed_pcb, "--nets"] + list(routed_nets()) \
        + list(ROUTER_OPTIONS) \
        + ["--ordering", ATTEMPT_ORDERINGS[attempt - 1]]
    completed = subprocess.run(command, capture_output=True, text=True)
    summary = _summary(completed.stdout)
    if completed.returncode != 0 or summary.get("failed"):
        raise RuntimeError("routing failed: rc=%s summary=%s"
                           % (completed.returncode, summary))
    tidied_pcb = os.path.join(stage_dir, "tidied.kicad_pcb")
    shutil.copy(routed_pcb, tidied_pcb)
    transform = tidy(tidied_pcb)
    return {
        "attempt": attempt,
        "source_sha256": digest(source_pcb),
        "accepted": False,
        "stages": [
            {"stage": "routed", "produced_by": "router",
             "sha256": digest(routed_pcb)},
            {"stage": "tidied", "produced_by": "transform",
             "sha256": digest(tidied_pcb),
             "transform": "snap track endpoints onto same-net via centres; "
                          "prune dangling track ends, keeping any removal "
                          "only while connectivity is unchanged; refill the "
                          "zones so the pour is knocked out around the "
                          "copper the router added",
             "effects": transform,
             "parameters": {"snap_tolerance_mm": SNAP_TOLERANCE_MM,
                            "touch_tolerance_mm": TOUCH_TOLERANCE_MM}},
        ],
        "context": {"router_summary": summary,
                    "ordering": ATTEMPT_ORDERINGS[attempt - 1]},
        "board": tidied_pcb,
    }


def _write_routing_project(path):
    """The project the router sees: the design's, with the clearance margin."""
    document = build.project_document(
        str(build.schematic._uuid("sheet", netlist.PROJECT_NAME)))
    document["board"]["design_settings"]["rules"]["min_clearance"] = \
        ROUTER_CLEARANCE_MM
    for entry in document["net_settings"]["classes"]:
        if entry["name"] == "Default":
            entry["clearance"] = ROUTER_CLEARANCE_MM
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(document, handle, indent=2)
        handle.write("\n")
    return path


#: Candidate acceptance judges the toolkit's design gate class - every gate
#: that judges the design itself, expanded by the toolkit so the selection
#: cannot rot as gates are added - plus ROUTE.PROVENANCE, whose record this
#: loop writes before judging, so the record-board agreement is judged per
#: candidate exactly as it was under the hand-written list.
ACCEPTANCE_SELECTION = "design,ROUTE.PROVENANCE"


def _gates_pass():
    """Judge the design, not the release artifacts.

    The fabrication outputs are generated FROM the board a search has not
    finished choosing, so gates over those artifacts are stale by
    construction during routing and would reject every candidate. The
    manifest names the subset that judges the design itself; everything else
    is judged once, afterwards, by a full validate.
    """
    completed = subprocess.run(
        [sys.executable, VALIDATOR, "validate", MANIFEST,
         "--only=" + ACCEPTANCE_SELECTION],
        capture_output=True, text=True, cwd=REPO_ROOT)
    return completed.returncode == 0


def _write_record(placed_pcb, attempts, accepted, krt, resolved):
    record = {
        "kind": routing_record.KIND,
        "source_sha256": digest(placed_pcb),
        "attempts": attempts,
        "accepted_attempt": accepted["attempt"] if accepted else None,
        "adopted_sha256": (digest(layout.BOARD_PATH) if accepted else None),
        "context": {
            "router": krt.provenance(resolved["path"], sys.executable),
            "resolution": resolved,
            "routed_nets": list(routed_nets()),
            "reserved_nets": sorted({"GND"} | set(netlist.SWITCHED_NETS)),
            "options": list(ROUTER_OPTIONS),
            "reproducibility": "the router is not bit-reproducible; "
                               "candidates are generated until one passes "
                               "the board gates and every attempt is "
                               "recorded here",
        },
    }
    routing_record.validate(record)
    os.makedirs(os.path.dirname(PROVENANCE_PATH), exist_ok=True)
    with open(PROVENANCE_PATH, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(record, handle, indent=2, sort_keys=True, default=str)
        handle.write("\n")
    return record


def _adopt(candidate_board):
    """Install a candidate, then rewrite everything derived from the board.

    The router writes its own project file beside the candidate - loosening
    a track width, pinning an edge clearance, silencing severities - so the
    authoritative project and rule file are regenerated from the design
    source rather than inherited from whatever the search left behind.
    """
    shutil.copy(candidate_board, layout.BOARD_PATH)
    build.write_project()


def run():
    krt = _krt()
    resolved = krt.resolve()
    candidate = os.path.join(CANDIDATE_ROOT, CANDIDATE_NAME)
    shutil.rmtree(candidate, ignore_errors=True)
    os.makedirs(candidate, exist_ok=True)
    layout.write()
    placed_pcb = os.path.join(candidate, "placed.kicad_pcb")
    shutil.copy(layout.BOARD_PATH, placed_pcb)

    attempts = []
    accepted = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        result = _route_once(krt, resolved, candidate, attempt, placed_pcb)
        entry = {key: value for key, value in result.items() if key != "board"}
        _adopt(result["board"])
        # The record must describe the board the gates are about to judge,
        # ROUTE.PROVENANCE included, so it is written before the judgement
        # and rewritten if the candidate is rejected.
        entry["accepted"] = True
        _write_record(placed_pcb, attempts + [entry], entry, krt, resolved)
        if _gates_pass():
            accepted = entry
            attempts.append(entry)
            break
        entry["accepted"] = False
        attempts.append(entry)

    if accepted is None:
        _adopt(placed_pcb)
        _write_record(placed_pcb, attempts, None, krt, resolved)
        raise RuntimeError(
            "no routing candidate passed the board gates in %d attempts; "
            "the placed, unrouted board has been restored so no failing "
            "copper stays in the tree" % MAX_ATTEMPTS)
    return layout.BOARD_PATH, PROVENANCE_PATH


#: A track arm shorter than this is pad or via entry geometry rather than a
#: routing decision: it is the stub the router lays to reach a pad centre
#: from the direction it approached in. Set from the narrowest pad on the
#: board, because a stub cannot be longer than the pad it enters and still be
#: entry geometry.
PAD_ENTRY_ARM_MM = 0.15


def angle_census(board_path=None):
    """Every corner in the routing, grouped by how far off 45-degree it turns.

    This board declares no angle style, so nothing judges this. It is measured
    anyway: "the board makes no such declaration" and "nobody looked" are
    different statements, and only the first is worth recording.
    """
    board = pcbnew.LoadBoard(board_path or layout.BOARD_PATH)
    segments = [track for track in board.GetTracks()
                if isinstance(track, pcbnew.PCB_TRACK)
                and not isinstance(track, pcbnew.PCB_VIA)]
    joins = {}
    for track in segments:
        for point in _endpoints(track):
            joins.setdefault((track.GetLayer(), point.x, point.y),
                             []).append(track)
    on_style, off_style = 0, []
    for (layer, px, py), group in joins.items():
        if len(group) != 2:
            continue
        arms = []
        for track in group:
            start, end = track.GetStart(), track.GetEnd()
            other = end if (start.x, start.y) == (px, py) else start
            arms.append((other.x - px, other.y - py))
        (ax, ay), (bx, by) = arms
        na, nb = math.hypot(ax, ay), math.hypot(bx, by)
        if not na or not nb:
            continue
        cosine = max(-1.0, min(1.0, (ax * bx + ay * by) / (na * nb)))
        turn = 180.0 - math.degrees(math.acos(cosine))
        if min(abs(turn - permitted)
               for permitted in (0.0, 45.0, 90.0, 135.0, 180.0)) <= 1e-6:
            on_style += 1
            continue
        off_style.append({
            "net": group[0].GetNetname(),
            "layer": board.GetLayerName(layer),
            "turn_deg": round(turn, 3),
            "shortest_arm_mm": round(pcbnew.ToMM(min(na, nb)), 4),
        })
    beyond = [entry for entry in off_style
              if entry["shortest_arm_mm"] > PAD_ENTRY_ARM_MM]
    return {
        "corners": on_style + len(off_style),
        "on_multiples_of_45_deg": on_style,
        "off_style": len(off_style),
        "off_style_beyond_pad_entry": sorted(
            beyond, key=lambda entry: -entry["shortest_arm_mm"]),
        "pad_entry_arm_mm": PAD_ENTRY_ARM_MM,
        "detail": sorted(off_style, key=lambda entry: -entry["turn_deg"]),
    }


def _endpoints(track):
    return (track.GetStart(), track.GetEnd())


def _supported(point, track, board, vias, tracks, epsilon):
    for via in vias:
        if via.GetNetCode() != track.GetNetCode():
            continue
        centre = via.GetPosition()
        if math.hypot(point.x - centre.x, point.y - centre.y) <= epsilon:
            return True
    for footprint in board.GetFootprints():
        for pad in footprint.Pads():
            if pad.GetNetCode() != track.GetNetCode():
                continue
            if pad.HitTest(point, 0):
                return True
    for other in tracks:
        if str(other.m_Uuid) == str(track.m_Uuid):
            continue
        if other.GetNetCode() != track.GetNetCode():
            continue
        if other.Type() == pcbnew.PCB_VIA_T:
            continue
        if other.GetLayer() != track.GetLayer():
            continue
        if other.HitTest(point, int(epsilon)):
            return True
    return False


def tidy(path):
    board = pcbnew.LoadBoard(path)
    epsilon = pcbnew.FromMM(TOUCH_TOLERANCE_MM)
    snapped = 0
    for _ in range(4):
        vias = [t for t in board.GetTracks() if t.Type() == pcbnew.PCB_VIA_T]
        moved = 0
        for track in board.GetTracks():
            if track.Type() == pcbnew.PCB_VIA_T:
                continue
            for get, set_ in ((track.GetStart, track.SetStart),
                              (track.GetEnd, track.SetEnd)):
                point = get()
                for via in vias:
                    if via.GetNetCode() != track.GetNetCode():
                        continue
                    centre = via.GetPosition()
                    distance = math.hypot(point.x - centre.x,
                                          point.y - centre.y)
                    if epsilon < distance <= pcbnew.FromMM(SNAP_TOLERANCE_MM):
                        set_(centre)
                        moved += 1
                        break
        snapped += moved
        if not moved:
            break

    # Prune what the router left unattached. A track whose removal would
    # break the net is kept and skipped rather than ending the pass, because
    # one such track used to hide every dangling end behind it.
    removed = 0
    keep = set()
    while True:
        board.BuildConnectivity()
        baseline = board.GetConnectivity().GetUnconnectedCount(True)
        vias = [t for t in board.GetTracks() if t.Type() == pcbnew.PCB_VIA_T]
        tracks = [t for t in board.GetTracks()
                  if t.Type() != pcbnew.PCB_VIA_T]
        victim = None
        for track in tracks:
            if str(track.m_Uuid) in keep:
                continue
            if track.GetLength() == 0:
                victim = track
                break
            if all(_supported(point, track, board, vias, tracks, epsilon)
                   for point in _endpoints(track)):
                continue
            victim = track
            break
        if victim is None:
            break
        uuid = str(victim.m_Uuid)
        board.Remove(victim)
        board.BuildConnectivity()
        if board.GetConnectivity().GetUnconnectedCount(True) > baseline:
            board.Add(victim)
            board.BuildConnectivity()
            keep.add(uuid)
            continue
        removed += 1

    # The router adds copper the pour was not knocked out around, so the fill
    # is recomputed here rather than left describing earlier copper.
    layout.fill_zones(board)
    pcbnew.SaveBoard(path, board)
    return {"endpoints_snapped": snapped,
            "dangling_tracks_removed": removed,
            "zones_refilled": len(list(board.Zones()))}


if __name__ == "__main__":
    for path in run():
        sys.stdout.write(path + "\n")
