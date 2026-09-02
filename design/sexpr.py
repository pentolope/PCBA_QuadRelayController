from __future__ import annotations


class Atom(str):
    __slots__ = ()


class Quoted(str):
    __slots__ = ()


def parse(text):
    pos = 0
    length = len(text)

    def skip():
        nonlocal pos
        while pos < length and text[pos] in " \t\r\n":
            pos += 1

    def read_quoted():
        nonlocal pos
        pos += 1
        out = []
        while True:
            ch = text[pos]
            if ch == "\\":
                out.append(text[pos:pos + 2])
                pos += 2
                continue
            if ch == '"':
                pos += 1
                return Quoted("".join(out))
            out.append(ch)
            pos += 1

    def read_atom():
        nonlocal pos
        start = pos
        while pos < length and text[pos] not in ' \t\r\n()"':
            pos += 1
        return Atom(text[start:pos])

    def read_list():
        nonlocal pos
        pos += 1
        items = []
        while True:
            skip()
            ch = text[pos]
            if ch == ")":
                pos += 1
                return items
            if ch == "(":
                items.append(read_list())
            elif ch == '"':
                items.append(read_quoted())
            else:
                items.append(read_atom())

    skip()
    return read_list()


def _escape(value):
    return value.replace("\\", "\\\\").replace('"', '\\"')


def dump(node, indent=0):
    pad = "\t" * indent
    if isinstance(node, Quoted):
        return '"' + _escape(str(node)) + '"'
    if isinstance(node, str):
        return str(node)
    if not node:
        return "()"
    head = node[0]
    rendered = [dump(item, indent + 1) for item in node[1:]]
    if all("\n" not in item for item in rendered) and sum(
            len(item) for item in rendered) < 70 and not any(
            isinstance(item, list) for item in node[1:]):
        return "(" + " ".join([dump(head, indent)] + rendered) + ")"
    body = "".join("\n" + "\t" * (indent + 1) + item for item in rendered)
    return "(" + dump(head, indent) + body + "\n" + pad + ")"


def find(node, key):
    for item in node:
        if isinstance(item, list) and item and item[0] == key:
            return item
    return None


def find_all(node, key):
    return [item for item in node
            if isinstance(item, list) and item and item[0] == key]
