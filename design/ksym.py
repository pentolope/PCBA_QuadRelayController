from __future__ import annotations

import copy
import os

from . import sexpr


class SymbolError(Exception):
    pass


class Pin:
    __slots__ = ("number", "name", "electrical_type", "x", "y", "unit")

    def __init__(self, number, name, electrical_type, x, y, unit):
        self.number = number
        self.name = name
        self.electrical_type = electrical_type
        self.x = x
        self.y = y
        self.unit = unit


class Library:
    def __init__(self, search_paths):
        self.search_paths = list(search_paths)
        self._files = {}

    def _load(self, library_name):
        if library_name in self._files:
            return self._files[library_name]
        for base in self.search_paths:
            path = os.path.join(base, library_name + ".kicad_sym")
            if os.path.isfile(path):
                with open(path, "r", encoding="utf-8") as handle:
                    tree = sexpr.parse(handle.read())
                index = {}
                for node in sexpr.find_all(tree, "symbol"):
                    index[str(node[1])] = node
                self._files[library_name] = index
                return index
        raise SymbolError("symbol library not found: " + library_name)

    def resolve(self, lib_id):
        library_name, _, symbol_name = lib_id.partition(":")
        if not symbol_name:
            raise SymbolError("lib_id must be LIBRARY:SYMBOL, got " + lib_id)
        index = self._load(library_name)
        if symbol_name not in index:
            raise SymbolError("symbol not in library: " + lib_id)
        node = index[symbol_name]
        extends = sexpr.find(node, "extends")
        if extends is None:
            return copy.deepcopy(node)
        parent_name = str(extends[1])
        if parent_name not in index:
            raise SymbolError(
                "parent symbol missing for " + lib_id + ": " + parent_name)
        merged = copy.deepcopy(index[parent_name])
        merged[1] = sexpr.Quoted(symbol_name)
        _rename_units(merged, parent_name, symbol_name)
        for child_property in sexpr.find_all(node, "property"):
            _set_property(merged, child_property)
        return merged

    def pins(self, lib_id):
        node = self.resolve(lib_id)
        found = []
        for unit_symbol in sexpr.find_all(node, "symbol"):
            unit = _unit_number(str(unit_symbol[1]))
            for pin in sexpr.find_all(unit_symbol, "pin"):
                at = sexpr.find(pin, "at")
                number = sexpr.find(pin, "number")
                name = sexpr.find(pin, "name")
                found.append(Pin(
                    str(number[1]),
                    str(name[1]),
                    str(pin[1]),
                    float(at[1]),
                    float(at[2]),
                    unit))
        by_number = {}
        for pin in found:
            by_number.setdefault(pin.number, []).append(pin)
        return by_number

    def property_value(self, lib_id, key):
        node = self.resolve(lib_id)
        for entry in sexpr.find_all(node, "property"):
            if str(entry[1]) == key:
                return str(entry[2])
        return None


def _unit_number(unit_symbol_name):
    parts = unit_symbol_name.rsplit("_", 2)
    if len(parts) == 3 and parts[1].isdigit():
        return int(parts[1])
    return 0


def _rename_units(node, old_name, new_name):
    for unit_symbol in sexpr.find_all(node, "symbol"):
        current = str(unit_symbol[1])
        if current.startswith(old_name + "_"):
            unit_symbol[1] = sexpr.Quoted(
                new_name + current[len(old_name):])


def _set_property(node, new_property):
    key = str(new_property[1])
    for index, item in enumerate(node):
        if (isinstance(item, list) and item and item[0] == "property"
                and str(item[1]) == key):
            node[index] = copy.deepcopy(new_property)
            return
    insert_at = len(node)
    for index, item in enumerate(node):
        if isinstance(item, list) and item and item[0] == "symbol":
            insert_at = index
            break
    node.insert(insert_at, copy.deepcopy(new_property))
