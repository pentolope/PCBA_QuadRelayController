"""Where the assembly library's zero is, relative to the footprint's zero.

A placement angle is not a property of the board alone. The part number's
orientation in the assembly house's library has its own zero, and where that
differs from the footprint's zero, every instance of the part is fitted turned
by the difference. The correction is therefore a property of the part, looked
up by distributor part number, and it has to come from evidence rather than
from a table somebody typed.

The evidence here is the component record the library itself serves, frozen
into this repository: the raw response body, byte for byte, and a normalised
extract of the pad positions it contains. Both are committed. The extract is
re-derived from the body every time it is read, and the offsets are scored
from the body rather than from the extract, so editing the extract cannot move
an offset - it can only make the mismatch visible.

How an offset is derived
------------------------
Each pad of the library part and each pad of the KiCad footprint is placed in
one right-handed frame, y up, measured from its own pad centroid. Pairing them
gives, per pad, the rotation that carries the library pad onto the footprint
pad. A rigid rotation makes every pad agree; the spread between them is what
says whether the evidence decides anything.

Pairing is by pad number where the two libraries number their pads the same
way, which is the strong form: it distinguishes a part from the same part
turned end for end, so it settles polarity. Where the numbering differs - a
relay whose footprint names its pads by function and whose library numbers
them by position - pairing falls back to nearest neighbour at each candidate
rotation, which decides only what the pad geometry decides. Which mode was
used is recorded per part, because the two are not equally strong.

Nothing here reaches the network unless it is asked to: `derive` reads only
committed files, and `freeze` is the separate, deliberate step that puts a
response on disk in the first place.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES = os.path.join(HERE, "fabrication", "jlc_orientation")
BOARD = os.path.join(HERE, "quad_relay_controller.kicad_pcb")

#: The library API this evidence comes from. Pinned including its version
#: parameter: a different version is a different response and a different
#: digest, which is the point.
SOURCE_URL = ("https://easyeda.com/api/products/{lcsc}"
              "/components?version=6.4.19.5")

#: How this tool identifies itself when it freezes evidence. Recorded in
#: each frozen record, so what retrieved a response is part of the evidence.
USER_AGENT = "pcbqa-jlc-orientation/1 (+board evidence freeze)"

#: One library unit is ten mil.
UNIT_MM = 0.254

#: Offsets a library is allowed to have. Multiples of 45 degrees, because a
#: library zero that were anything else would not be a convention but an
#: error, and scoring against a continuum would let noise choose.
CANDIDATE_OFFSETS_DEG = tuple(range(0, 360, 45))

#: How far the least-agreeing pad may sit from the consensus rotation before
#: the pad sets are not the same rigid shape. Land patterns from two libraries
#: differ in aspect - a SOT-23 pad sits at 1.00 mm in one and 0.94 mm in the
#: other - so this is not zero and must not be.
MAX_SPREAD_DEG = 8.0

#: How much worse the runner-up candidate must be. Below this the evidence
#: does not choose between two rotations, and saying so is the honest answer.
MIN_MARGIN_DEG = 30.0

BY_NUMBER = "pad number"
BY_POSITION = "nearest position"


class OrientationEvidenceError(Exception):
    """The frozen evidence cannot answer. Never defaulted around."""


# ---------------------------------------------------------------------------
# the frozen evidence

def raw_path(lcsc):
    return os.path.join(FIXTURES, "raw", lcsc + ".json")


def extract_path(lcsc):
    return os.path.join(FIXTURES, lcsc + ".json")


def frozen_parts():
    if not os.path.isdir(FIXTURES):
        return []
    return sorted(name[:-5] for name in os.listdir(FIXTURES)
                  if name.endswith(".json"))


def pads_from_raw(body):
    """Pad centres from a raw library response, in millimetres, y up.

    Measured from the package's own origin, which the response states, so the
    numbers do not depend on where the library happened to draw the part on
    its canvas.
    """
    document = json.loads(body.decode("utf-8"))
    if not document.get("success"):
        raise OrientationEvidenceError("the response reports no success")
    detail = document["result"].get("packageDetail")
    if not detail:
        raise OrientationEvidenceError("the response carries no package")
    data = detail["dataStr"]
    origin_x = float(data["head"]["x"])
    origin_y = float(data["head"]["y"])
    pads = {}
    for index, shape in enumerate(data["shape"]):
        if not shape.startswith("PAD~"):
            continue
        field = shape.split("~")
        number = field[8].strip()
        x = (float(field[2]) - origin_x) * UNIT_MM
        # The library's y runs down the screen; every frame here runs up.
        y = -(float(field[3]) - origin_y) * UNIT_MM
        pads.setdefault(number, []).append([round(x, 6), round(y, 6)])
    if not pads:
        raise OrientationEvidenceError("the package carries no pads")
    return {number: sorted(points) for number, points in sorted(pads.items())}


def load(lcsc):
    with open(extract_path(lcsc), encoding="utf-8") as handle:
        return json.load(handle)


def verify(lcsc):
    """`(problems, pads)` - the pads being the ones the RAW body derives.

    Three things a determined edit could touch, checked separately: the body
    can be changed, the extract can be changed to disagree with the body, and
    the body can be removed. The pads returned are always the body's, so a
    caller that scores with them scores the evidence rather than the summary.
    """
    problems = []
    raw = raw_path(lcsc)
    if not os.path.isfile(raw):
        return ([{"lcsc": lcsc,
                  "issue": "the raw library response is not committed, so "
                           "nothing behind the extract can be checked"}], None)
    with open(raw, "rb") as handle:
        body = handle.read()
    digest = hashlib.sha256(body).hexdigest()
    try:
        pads = pads_from_raw(body)
    except (OrientationEvidenceError, ValueError, KeyError) as exc:
        return ([{"lcsc": lcsc,
                  "issue": "the raw response yields no pads: %s" % exc}], None)
    try:
        record = load(lcsc)
    except (OSError, ValueError) as exc:
        problems.append({"lcsc": lcsc,
                         "issue": "the extract cannot be read: %s" % exc})
        return problems, pads
    if record.get("raw_sha256") != digest:
        problems.append({
            "lcsc": lcsc,
            "issue": "the raw response on disk does not have the digest the "
                     "extract records"})
    if record.get("raw_bytes") != len(body):
        problems.append({
            "lcsc": lcsc,
            "issue": "the raw response on disk is not the length the extract "
                     "records"})
    if record.get("pads") != pads:
        problems.append({
            "lcsc": lcsc,
            "issue": "the extract's pads are not what the raw response "
                     "derives"})
    return problems, pads


# ---------------------------------------------------------------------------
# the board side

def footprint_pads(board_path, part_number_field):
    """`{part number: {"footprint":…, "pads":…, "references":…}}`, y up.

    Pad positions are footprint-local, so they describe the footprint's own
    zero rather than however this board happens to have turned an instance.
    """
    import pcbnew

    found = {}
    for footprint in pcbnew.LoadBoard(board_path).GetFootprints():
        number = ""
        for field in footprint.GetFields():
            if field.GetName() == part_number_field and \
                    field.GetText().strip():
                number = field.GetText().strip()
        if not number:
            continue
        reference = footprint.GetReference()
        if number in found:
            found[number]["references"].append(reference)
            continue
        pads = {}
        for pad in footprint.Pads():
            position = pad.GetFPRelativePosition()
            pads.setdefault(pad.GetNumber().strip(), []).append(
                [round(pcbnew.ToMM(position.x), 6),
                 # KiCad's internal y runs down; every frame here runs up.
                 round(-pcbnew.ToMM(position.y), 6)])
        found[number] = {
            "footprint": footprint.GetFPIDAsString(),
            "pads": {key: sorted(value) for key, value in sorted(pads.items())},
            "references": [reference],
        }
    for record in found.values():
        record["references"].sort()
    return found


# ---------------------------------------------------------------------------
# scoring

def _flatten(pads):
    return [tuple(point) for points in pads.values() for point in points]


def _centre(points):
    if not points:
        return []
    cx = sum(x for x, _ in points) / len(points)
    cy = sum(y for _, y in points) / len(points)
    return [(x - cx, y - cy) for x, y in points]


def _centred(pads):
    """Every pad centre, moved so the set's centroid is the origin."""
    flat = _flatten(pads)
    cx = sum(x for x, _ in flat) / len(flat)
    cy = sum(y for _, y in flat) / len(flat)
    return {number: [(x - cx, y - cy) for x, y in points]
            for number, points in pads.items()}


def _rotate(point, degrees):
    angle = math.radians(degrees)
    x, y = point
    return (x * math.cos(angle) - y * math.sin(angle),
            x * math.sin(angle) + y * math.cos(angle))


def _circular_distance(a, b):
    return abs(((a - b + 180.0) % 360.0) - 180.0)


def _implied(board_point, library_point):
    """The rotation carrying one library pad onto its board pad, in degrees."""
    bx, by = board_point
    lx, ly = library_point
    if math.hypot(bx, by) < 1e-9 or math.hypot(lx, ly) < 1e-9:
        return None
    return (math.degrees(math.atan2(by, bx) - math.atan2(ly, lx))) % 360.0


def _pair_by_number(board_pads, library_pads):
    """Pairs where both libraries agree on how pads are numbered."""
    shared = sorted(set(board_pads) & set(library_pads))
    if not shared:
        return None
    pairs = []
    for number in shared:
        board_points = board_pads[number]
        library_points = library_pads[number]
        if len(board_points) != len(library_points):
            return None
        for board_point, library_point in zip(board_points, library_points):
            pairs.append((board_point, library_point))
    return pairs


def _pair_by_position(board_pads, library_pads, degrees):
    """Nearest-neighbour pairs at one candidate rotation, each used once."""
    library = [(_rotate(point, degrees), point)
               for point in _flatten(library_pads)]
    pairs, taken = [], set()
    for board_point in _flatten(board_pads):
        best, best_distance = None, None
        for index, (rotated, original) in enumerate(library):
            if index in taken:
                continue
            distance = math.hypot(rotated[0] - board_point[0],
                                  rotated[1] - board_point[1])
            if best_distance is None or distance < best_distance:
                best, best_distance = index, distance
        if best is None:
            return None
        taken.add(best)
        pairs.append((board_point, library[best][1]))
    return pairs


def _score(pairs):
    """`(consensus rotation, per-pad rotations)` for one pairing."""
    implied = [value for value in
               (_implied(board_point, library_point)
                for board_point, library_point in pairs)
               if value is not None]
    if not implied:
        return None, []
    sin = sum(math.sin(math.radians(value)) for value in implied)
    cos = sum(math.cos(math.radians(value)) for value in implied)
    if abs(sin) < 1e-12 and abs(cos) < 1e-12:
        return None, implied
    return math.degrees(math.atan2(sin, cos)) % 360.0, implied


def offset_for(board_pads, library_pads):
    """The library-zero offset the two pad sets imply, and how well.

    Candidates are the eight multiples of 45 degrees. Each is scored by the
    furthest any single pad sits from it, so a candidate only wins by
    explaining every pad rather than most of them.
    """
    board_pads = _centred(board_pads)
    library_pads = _centred(library_pads)
    pairs = _pair_by_number(board_pads, library_pads)
    mode = BY_NUMBER
    scores = {}
    if pairs is not None:
        consensus, implied = _score(pairs)
        for candidate in CANDIDATE_OFFSETS_DEG:
            scores[candidate] = (max(_circular_distance(value, candidate)
                                     for value in implied)
                                 if implied else 360.0)
    else:
        mode = BY_POSITION
        consensus, implied = None, []
        best_pairs = None
        for candidate in CANDIDATE_OFFSETS_DEG:
            paired = _pair_by_position(board_pads, library_pads, candidate)
            if paired is None:
                scores[candidate] = 360.0
                continue
            _, values = _score(paired)
            scores[candidate] = (max(_circular_distance(value, candidate)
                                     for value in values)
                                 if values else 360.0)
            if best_pairs is None or scores[candidate] < scores[best_pairs[0]]:
                best_pairs = (candidate, paired)
        if best_pairs is not None:
            consensus, implied = _score(best_pairs[1])
    if not scores:
        return {"error": "no candidate rotation could be scored"}
    ranked = sorted(scores.items(), key=lambda item: item[1])
    best, best_worst = ranked[0]
    margin = ranked[1][1] - best_worst if len(ranked) > 1 else 360.0
    return {
        "best_offset_deg": float(best),
        "best_worst_deg": round(best_worst, 4),
        "margin_deg": round(margin, 4),
        "consensus_deg": None if consensus is None else round(consensus, 4),
        "pairing": mode,
        "pads_compared": len(implied),
        "decisive": bool(best_worst <= MAX_SPREAD_DEG
                         and margin >= MIN_MARGIN_DEG),
        "candidate_scores_deg": {str(k): round(v, 4)
                                 for k, v in sorted(scores.items())},
    }


# ---------------------------------------------------------------------------
# the offline derivation, which is what a release reads

def derive(part_number_field="LCSC", board_path=None):
    """Every frozen part's offset, scored against this board's footprints.

    Reads committed files only. A part the board does not carry is still
    scored as far as the evidence alone allows and reported without a
    footprint, because a registry entry for a part that has left the board is
    a fact worth seeing rather than one to hide.
    """
    board = footprint_pads(board_path or BOARD, part_number_field)
    out = {}
    for lcsc in frozen_parts():
        problems, library_pads = verify(lcsc)
        if library_pads is None:
            out[lcsc] = {"error": "no usable frozen evidence",
                         "evidence_problems": problems}
            continue
        record = {"evidence_problems": problems}
        try:
            record["evidence_sha256"] = hashlib.sha256(
                open(raw_path(lcsc), "rb").read()).hexdigest()
        except OSError as exc:                             # pragma: no cover
            record["error"] = str(exc)
            out[lcsc] = record
            continue
        entry = board.get(lcsc)
        if entry is None:
            record["error"] = ("the board carries no footprint with this part "
                               "number, so no offset can be derived for it")
            out[lcsc] = record
            continue
        record.update(offset_for(entry["pads"], library_pads))
        record["kicad_footprint"] = entry["footprint"]
        record["references"] = entry["references"]
        out[lcsc] = record
    return out


# ---------------------------------------------------------------------------
# the online step, which a release never takes

def fetch(lcsc):                                           # pragma: no cover
    """The raw response body. Called only by `freeze`, never by `derive`."""
    import subprocess

    url = SOURCE_URL.format(lcsc=lcsc)
    completed = subprocess.run(
        ["curl", "-sS", "--fail", "--max-time", "30",
         "-A", USER_AGENT, "-H", "Accept: application/json", url],
        capture_output=True)
    if completed.returncode != 0:
        raise OrientationEvidenceError(
            "retrieval of %s failed: %s"
            % (lcsc, (completed.stderr or b"").decode("utf-8", "replace")))
    return url, completed.stdout


def freeze(lcsc, retrieved_utc, body=None):                # pragma: no cover
    """Put one part's evidence on disk: the body, and an extract of it.

    Retrieval and freezing are separate steps. A body already retrieved can
    be passed in, which is what happens when the endpoint rate-limits a run
    partway through: the response that was actually served is what gets
    committed, rather than a second, different one fetched later.
    """
    if body is None:
        url, body = fetch(lcsc)
    else:
        url = SOURCE_URL.format(lcsc=lcsc)
    pads = pads_from_raw(body)
    os.makedirs(os.path.dirname(raw_path(lcsc)), exist_ok=True)
    with open(raw_path(lcsc), "wb") as handle:
        handle.write(body)
    record = {
        "kind": "normalised extract",
        "lcsc": lcsc,
        "pads": pads,
        "raw_sha256": hashlib.sha256(body).hexdigest(),
        "raw_bytes": len(body),
        "source_url": url,
        "retrieved_utc": retrieved_utc,
        "units": "mm, measured from the package origin, y up",
        "derived_by": "tools/jlc_orientation.py pads_from_raw",
        "user_agent": USER_AGENT,
    }
    with open(extract_path(lcsc), "w", encoding="utf-8", newline="\n") as h:
        json.dump(record, h, indent=2, sort_keys=True)
        h.write("\n")
    return raw_path(lcsc), extract_path(lcsc)


if __name__ == "__main__":
    if len(sys.argv) > 3 and sys.argv[1] == "freeze":
        supplied = None
        if len(sys.argv) > 4:
            with open(sys.argv[4], "rb") as handle:
                supplied = handle.read()
        for path in freeze(sys.argv[2], sys.argv[3], supplied):
            sys.stdout.write(path + "\n")
    else:
        for lcsc, record in sorted(derive().items()):
            sys.stdout.write(
                "%-10s %-7s %6.1f deg  worst %6.2f  margin %6.2f  %s%s\n" % (
                    lcsc, "OK" if record.get("decisive") else "UNDECIDED",
                    record.get("best_offset_deg", float("nan")),
                    record.get("best_worst_deg", float("nan")),
                    record.get("margin_deg", float("nan")),
                    record.get("pairing", "-"),
                    "  " + record["error"] if "error" in record else ""))
