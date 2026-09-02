from __future__ import annotations

import collections
import json
import os
import sys

from . import netlist

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG_PATH = os.path.join(REPO_ROOT, "components", "jlcpcb.json")

BASIC_LIBRARY_TYPE = "base"

DEFAULT_BUILD_QUANTITIES = (5, 50, 500)


class CostError(Exception):
    pass


def load_catalog():
    with open(CATALOG_PATH, "r", encoding="utf-8") as handle:
        return json.load(handle)


def line_items():
    counts = collections.Counter()
    for reference, part in netlist.PARTS.items():
        if not part["in_bom"]:
            continue
        code = part.get("lcsc")
        if not code:
            raise CostError("BOM part %s has no catalogue code" % reference)
        counts[code] += 1
    return dict(counts)


def unit_price(entry, quantity):
    chosen = None
    for entry_break in entry["price_breaks"]:
        if entry_break["min_qty"] > quantity:
            continue
        upper = entry_break["max_qty"]
        if upper is None or quantity <= upper:
            return entry_break["unit_usd"]
        chosen = entry_break["unit_usd"]
    if chosen is not None:
        return chosen
    if entry["price_breaks"]:
        return entry["price_breaks"][0]["unit_usd"]
    raise CostError("no price breaks recorded")


def bom_cost(build_quantity):
    catalog = load_catalog()["parts"]
    per_board = 0.0
    lines = []
    for code, per_board_count in sorted(line_items().items()):
        if code not in catalog:
            raise CostError("catalogue has no entry for " + code)
        entry = catalog[code]
        order_quantity = per_board_count * build_quantity
        price = unit_price(entry, order_quantity)
        extended = price * per_board_count
        per_board += extended
        lines.append({
            "lcsc": code,
            "mpn": entry["mpn"],
            "per_board": per_board_count,
            "order_quantity": order_quantity,
            "unit_usd": price,
            "per_board_usd": extended,
            "library_type": entry["library_type"],
            "stock": entry["stock"],
        })
    return {"build_quantity": build_quantity,
            "per_board_usd": per_board,
            "lines": sorted(lines, key=lambda item: -item["per_board_usd"])}


def extended_part_codes():
    catalog = load_catalog()["parts"]
    return sorted(code for code in line_items()
                  if catalog[code]["library_type"] != BASIC_LIBRARY_TYPE)


def stock_limited_boards():
    catalog = load_catalog()["parts"]
    limits = {}
    for code, per_board_count in line_items().items():
        limits[code] = catalog[code]["stock"] // per_board_count
    return limits


if __name__ == "__main__":
    for quantity in DEFAULT_BUILD_QUANTITIES:
        report = bom_cost(quantity)
        sys.stdout.write("\nbuild quantity %d -> $%.4f per board\n"
                         % (quantity, report["per_board_usd"]))
        for line in report["lines"]:
            sys.stdout.write(
                "  %-10s %-22s x%-3d %-6s $%.4f ea  $%.4f\n"
                % (line["lcsc"], (line["mpn"] or "")[:22], line["per_board"],
                   line["library_type"], line["unit_usd"],
                   line["per_board_usd"]))
    sys.stdout.write("\nextended parts: %s\n"
                     % ", ".join(extended_part_codes()))
    limits = stock_limited_boards()
    tightest = min(limits, key=limits.get)
    sys.stdout.write("stock limits build to %d boards (%s)\n"
                     % (limits[tightest], tightest))
