"""The reviewed library-zero registry, built from the frozen evidence.

Every placement angle a release ships is the board's own angle plus a
correction that belongs to the part number rather than to the board: where the
assembly library's zero orientation differs from the footprint's, every
instance is fitted turned by the difference.

The corrections are not written here. They are derived by tools/jlc_orientation
from the library responses frozen in fabrication/jlc_orientation, and this
module only assembles what that derivation produced into the registry the
manifest carries - refusing any part whose evidence did not decide an offset,
because an entry with a number nothing established is exactly what a registry
is supposed to make impossible.

The derivation runs again during validation, from the same committed files,
and the gate fails if it disagrees with what is recorded here. So this file
is a cache of a computation, not a table of opinions, and it is regenerated
rather than edited.
"""
from __future__ import annotations

import json
import os
import sys

from . import netlist

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST_PATH = os.path.join(REPO_ROOT, "board", "manifest.json")
TOOL_DIR = os.path.join(REPO_ROOT, "tools")
FIXTURE_DIR = os.path.join(REPO_ROOT, "fabrication", "jlc_orientation")

PART_NUMBER_FIELD = "LCSC"

#: What the registry's review status is claiming, recorded per entry so a
#: reader can see what "reviewed" was allowed to mean here.
REVIEW_BASIS = (
    "derived from the frozen library response by tools/jlc_orientation.py, "
    "which pairs the library's pads with the footprint's and requires every "
    "pad to agree on one rotation; re-derived from the same committed "
    "evidence on every release and compared against this entry"
)


def _tool():
    if TOOL_DIR not in sys.path:
        sys.path.insert(0, TOOL_DIR)
    import jlc_orientation
    return jlc_orientation


def _package_name(tool, lcsc):
    """The library's own name for the package, from the frozen response."""
    with open(tool.raw_path(lcsc), "rb") as handle:
        document = json.loads(handle.read().decode("utf-8"))
    head = document["result"]["packageDetail"]["dataStr"]["head"]
    return head.get("c_para", {}).get("package", "")


def _mpn_by_part_number():
    return {part["lcsc"]: part["mpn"]
            for part in netlist.PARTS.values() if part.get("lcsc")}


def registry():
    """One row per part number, or a refusal naming what is not established."""
    tool = _tool()
    derived = tool.derive(PART_NUMBER_FIELD)
    mpn = _mpn_by_part_number()
    rows, refused = [], []
    for lcsc, record in sorted(derived.items()):
        if record.get("error"):
            refused.append({"lcsc": lcsc, "issue": record["error"]})
            continue
        if record.get("evidence_problems"):
            refused.append({"lcsc": lcsc,
                            "issue": "the frozen evidence does not check out",
                            "problems": record["evidence_problems"]})
            continue
        if not record.get("decisive"):
            refused.append({
                "lcsc": lcsc,
                "issue": "the evidence does not decide an offset",
                "best_worst_deg": record.get("best_worst_deg"),
                "margin_deg": record.get("margin_deg")})
            continue
        rows.append({
            "lcsc": lcsc,
            "mpn": mpn.get(lcsc, ""),
            "package": _package_name(tool, lcsc),
            "kicad_footprint": record["kicad_footprint"],
            "offset_deg": record["best_offset_deg"],
            "review_status": "reviewed",
            "x_review_basis": REVIEW_BASIS,
            "evidence_file": os.path.relpath(tool.extract_path(lcsc),
                                             REPO_ROOT).replace("\\", "/"),
            "raw_file": os.path.relpath(tool.raw_path(lcsc),
                                        REPO_ROOT).replace("\\", "/"),
            "evidence_sha256": record["evidence_sha256"],
            "x_pairing": record["pairing"],
            "x_worst_pad_disagreement_deg": record["best_worst_deg"],
            "x_margin_over_runner_up_deg": record["margin_deg"],
            "x_references": record["references"],
        })
    return rows, refused


def specification():
    rows, refused = registry()
    if refused:
        raise ValueError(
            "the orientation evidence does not establish an offset for %d "
            "part number(s): %s"
            % (len(refused), json.dumps(refused, indent=2)))
    return {
        "part_number_field": PART_NUMBER_FIELD,
        "normalize_range_deg": [0, 360],
        "angle_decimals": 4,
        "evidence": {
            "fixtures": "fabrication/jlc_orientation/*.json",
            "note": "the raw library response and a normalised extract of it "
                    "are both committed; the extract is re-derived from the "
                    "body whenever it is read, and the offsets are scored "
                    "from the body rather than from the extract",
        },
        "reproduction_inputs": {
            "required_globs": [
                "tools/jlc_orientation.py",
                "fabrication/jlc_orientation/*.json",
                "fabrication/jlc_orientation/raw/*.json",
            ],
        },
        "registry": rows,
    }


def write():
    document = specification()
    with open(MANIFEST_PATH, encoding="utf-8") as handle:
        manifest = json.load(handle)
    manifest["release_generation"]["cpl_orientation"] = document
    with open(MANIFEST_PATH, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(manifest, handle, indent=2)
        handle.write("\n")
    return MANIFEST_PATH


if __name__ == "__main__":
    rows, refused = registry()
    for row in rows:
        sys.stdout.write("%-10s %-24s %-46s %5.0f deg  %s\n" % (
            row["lcsc"], row["mpn"][:24], row["kicad_footprint"][:46],
            row["offset_deg"], row["x_pairing"]))
    for entry in refused:
        sys.stdout.write("REFUSED %s\n" % json.dumps(entry))
    sys.stdout.write("\n" + write() + "\n")
