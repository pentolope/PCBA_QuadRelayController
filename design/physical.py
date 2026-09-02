from __future__ import annotations

import hashlib
import json
import os
import sys

from . import layout

sys.path.insert(0, os.path.join(layout.REPO_ROOT, "tooling",
                                "PCBA_AutoDesignAndTest"))

from pcbqa import extract, headless  # noqa: E402
from pcbqa.fabricators.store import CatalogStore  # noqa: E402

REPO_ROOT = layout.REPO_ROOT
REQUIREMENTS_PATH = os.path.join(REPO_ROOT, "fab", "requirements.json")
PHYSICAL_PATH = os.path.join(REPO_ROOT, "fab", "physical_inputs.json")
CATALOG_ROOT = os.path.join(REPO_ROOT, "tooling", "PCBA_AutoDesignAndTest",
                            "profiles", "jlcpcb")


def _approved():
    approved = CatalogStore(CATALOG_ROOT).approved()
    if approved is None:
        raise RuntimeError(
            "no approved fabricator catalog, so no physical input can be "
            "resolved from evidence")
    return approved


def resolve():
    """Finished copper and board thickness, from the approved catalog.

    Resolved here rather than in a gate: validation must not be able to
    reach the fabricator package, and so cannot reach the network by
    accident. Each value comes out as a parameter record carrying its
    source type and the catalog's digest, so what a gate later reads is
    checkable without the catalog being present.
    """
    import pcbnew

    headless.suppress_blocking_ui()
    with open(REQUIREMENTS_PATH, "rb") as handle:
        raw = handle.read()
    requirements = json.loads(raw.decode("utf-8"))
    board = pcbnew.LoadBoard(layout.BOARD_PATH)
    stack = [board.GetLayerName(layer)
             for layer in board.GetEnabledLayers().CuStack()]
    approved = _approved()
    return {
        "copper_thickness_mm": extract.approved_finished_copper(
            approved,
            extract.copper_assignments_from_requirements(requirements, stack)),
        "board_thickness_mm": extract.requirements_board_thickness(
            requirements, hashlib.sha256(raw).hexdigest()),
    }


def verify(document=None):
    """Every approved-evidence parameter still agrees with the catalog."""
    if document is None:
        with open(PHYSICAL_PATH, encoding="utf-8") as handle:
            document = json.load(handle)
    approved = _approved()
    problems = []
    records = dict(document["copper_thickness_mm"])
    records["board_thickness_mm"] = document["board_thickness_mm"]
    for label, record in sorted(records.items()):
        if record["source_type"] != "approved-evidence":
            continue
        try:
            extract.verify_approved_parameter(record, approved)
        except extract.ExtractionError as exc:
            problems.append({"parameter": label, "issue": str(exc)})
    return problems


def write():
    document = resolve()
    os.makedirs(os.path.dirname(PHYSICAL_PATH), exist_ok=True)
    with open(PHYSICAL_PATH, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(document, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return PHYSICAL_PATH


if __name__ == "__main__":
    sys.stdout.write(write() + "\n")
