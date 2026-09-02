"""Placement search: the seed is intent, the accepted poses are a result.

The design source states where each part belongs - a zone, an edge, a lock -
and seeds a position that satisfies it. This module hands that seed to the
placement optimizer, which searches the freedom that is left, and records the
poses it accepted so the board can be regenerated from them.

The search runs on a board with no copper. Moving a footprint does not move
copper, so a routed board cannot be re-placed; everything conductive is
generated afterwards, from the accepted poses.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys

import pcbnew

from . import build, floorplan, layout, netlist, route

REPO_ROOT = layout.REPO_ROOT
CANDIDATE_ROOT = os.path.join(REPO_ROOT, "candidates")
CANDIDATE_NAME = "place-current"
PLACEMENT_PATH = layout.PLACEMENT_PATH
PROVENANCE_PATH = os.path.join(REPO_ROOT, "generated", "placement.json")

#: How far a part may travel from the seed. Small on purpose: the seed carries
#: intent the cost function cannot see - the flyback loop kept tight around
#: its coil pins, decoupling beside its supply pin - and a large radius trades
#: that away for wirelength.
MAX_DISPLACEMENT_MM = 3.0


def _optimizer(krt):
    return os.path.join(krt.resolve()["path"], "py_placer", "place_optimize.py")


def _summary(text):
    for line in text.splitlines():
        if line.strip().startswith("JSON_SUMMARY:"):
            return json.loads(line.split("JSON_SUMMARY:", 1)[1])
    return {}


def poses(board_path):
    """Every part's pose, in the board coordinates the design source uses."""
    board = pcbnew.LoadBoard(board_path)
    found = {}
    for footprint in board.GetFootprints():
        reference = footprint.GetReference()
        if not reference:
            continue
        position = footprint.GetPosition()
        found[reference] = (
            round(pcbnew.ToMM(position.x) - layout.ORIGIN_MM[0], 4),
            round(layout.ORIGIN_MM[1] - pcbnew.ToMM(position.y), 4),
            round(footprint.GetOrientationDegrees() % 360.0, 3),
        )
    return found


def _searchable(found):
    return {reference: pose for reference, pose in sorted(found.items())
            if reference not in layout.LOCKED_REFERENCES}


def _write_placement(found, provenance):
    document = {
        "kind": "accepted-placement",
        "units": "mm",
        "frame": "board coordinates: x right and y up from the lower-left "
                 "corner, degrees counter-clockwise",
        "placement": _searchable(found),
    }
    os.makedirs(os.path.dirname(PLACEMENT_PATH), exist_ok=True)
    with open(PLACEMENT_PATH, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(document, handle, indent=2, sort_keys=True)
        handle.write("\n")
    os.makedirs(os.path.dirname(PROVENANCE_PATH), exist_ok=True)
    with open(PROVENANCE_PATH, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(provenance, handle, indent=2, sort_keys=True, default=str)
        handle.write("\n")
    return PLACEMENT_PATH, PROVENANCE_PATH


def run():
    krt = route._krt()
    resolved = krt.resolve()
    candidate = os.path.join(CANDIDATE_ROOT, CANDIDATE_NAME)
    shutil.rmtree(candidate, ignore_errors=True)
    os.makedirs(candidate, exist_ok=True)

    intent = floorplan.write()
    # The search starts from the seed, never from a previously accepted
    # result: optimising an optimised board compounds whatever the cost
    # function likes and drifts away from the intent the seed carries.
    if os.path.isfile(PLACEMENT_PATH):
        os.remove(PLACEMENT_PATH)
    seed = os.path.join(candidate, "seed.kicad_pcb")
    layout.write_placement_board(seed)
    shutil.copy(os.path.join(REPO_ROOT, netlist.PROJECT_NAME + ".kicad_dru"),
                os.path.join(candidate, "seed.kicad_dru"))
    route._write_routing_project(os.path.join(candidate, "seed.kicad_pro"))

    optimized = os.path.join(candidate, "optimized.kicad_pcb")
    command = [sys.executable, _optimizer(krt), seed, optimized,
               "--intent", intent,
               "--max-displacement", str(MAX_DISPLACEMENT_MM),
               "--clearance", str(route.ROUTER_CLEARANCE_MM)]
    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.returncode != 0:
        raise RuntimeError("placement optimisation failed: rc=%s\n%s"
                           % (completed.returncode,
                              (completed.stderr or "")[-2000:]))
    summary = _summary(completed.stdout)
    if summary.get("intent_moves_refused_by_rule", {}) and not summary:
        raise RuntimeError("placement optimisation produced no summary")

    found = poses(optimized)
    provenance = {
        "kind": "accepted-placement-provenance",
        "seed_sha256": route.digest(seed),
        "optimized_sha256": route.digest(optimized),
        "intent_sha256": route.digest(intent),
        "max_displacement_mm": MAX_DISPLACEMENT_MM,
        "locked": sorted(layout.LOCKED_REFERENCES),
        "optimizer": krt.provenance(resolved["path"], sys.executable),
        "resolution": resolved,
        "summary": summary,
    }
    written = _write_placement(found, provenance)
    layout.write()
    return (intent,) + written


if __name__ == "__main__":
    for path in run():
        sys.stdout.write(path + "\n")
