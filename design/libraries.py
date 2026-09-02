from __future__ import annotations

import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIBRARY_NAME = "QuadRelayController"
SYMBOL_LIB_PATH = os.path.join(REPO_ROOT, "library",
                               LIBRARY_NAME + ".kicad_sym")
FOOTPRINT_DIR = os.path.join(REPO_ROOT, "library", LIBRARY_NAME + ".pretty")
SYM_LIB_TABLE = os.path.join(REPO_ROOT, "sym-lib-table")
FP_LIB_TABLE = os.path.join(REPO_ROOT, "fp-lib-table")

SYMBOL_LIB_VERSION = "20251024"
FOOTPRINT_VERSION = "20260206"
GENERATOR = "quad-relay-controller-design-source"

# PY32F003 Datasheet Rev1.7, figure 3-3 "TSSOP20 Pinout1 PY32F003F1xPx".
PY32F003F1XPX_PINS = [
    ("1", "PA2", "bidirectional"),
    ("2", "PA3", "bidirectional"),
    ("3", "PA4", "bidirectional"),
    ("4", "PA5", "bidirectional"),
    ("5", "PA6", "bidirectional"),
    ("6", "PA7", "bidirectional"),
    ("7", "VSS", "power_in"),
    ("8", "PA12", "bidirectional"),
    ("9", "VCC", "power_in"),
    ("10", "PA13-SWD", "bidirectional"),
    ("11", "PA14-SWC", "bidirectional"),
    ("12", "PB5", "bidirectional"),
    ("13", "PB6", "bidirectional"),
    ("14", "PB7", "bidirectional"),
    ("15", "PF4-BOOT0", "bidirectional"),
    ("16", "PF0", "bidirectional"),
    ("17", "PF1", "bidirectional"),
    ("18", "PF2-NRST", "bidirectional"),
    ("19", "PA0", "bidirectional"),
    ("20", "PA1", "bidirectional"),
]

PY32_SYMBOL_NAME = "PY32F003F1xPx"
PY32_DEFAULT_FOOTPRINT = "Package_SO:TSSOP-20_4.4x6.5mm_P0.65mm"
PY32_DATASHEET = ("https://download.py32.org/Datasheet/en/"
                  "PY32F003_Datasheet_Rev1.7.pdf")

TVS_SYMBOL_NAME = "TPD1E10B06"
TVS_DATASHEET = "https://www.ti.com/lit/ds/symlink/tpd1e10b06.pdf"

# TI DPY0002A, drawing 4224561/C (SLLSEB1G): land pattern 2x (0.3) wide by
# 2x (0.5) tall on (0.7) centres; package outline 1.1/0.9 by 0.7/0.5.
X1SON_FOOTPRINT_NAME = "TI_X1SON-2_1.0x0.6mm_P0.65mm"
X1SON_PAD_SIZE_MM = (0.30, 0.50)
X1SON_PAD_PITCH_MM = 0.70
X1SON_BODY_MM = (1.10, 0.70)
X1SON_COURTYARD_MARGIN_MM = 0.15

# Cixi Kefa KF128-5.08 drawing rev A (2021-03-13): PCB layout is two
# 1.40 +0.10/-0.00 holes on 5.08 +/-0.03 centres; body 10.70 deep with the
# pin row 5.40 from the wire-entry face; height 14.10.
KF128_FOOTPRINT_NAME = "TerminalBlock_KF128-5.08_1x02_P5.08mm"
KF128_PITCH_MM = 5.08
KF128_DRILL_MM = 1.40
KF128_PAD_DIAMETER_MM = 2.60
KF128_BODY_DEPTH_MM = 10.70
KF128_PIN_TO_ENTRY_FACE_MM = 5.40
KF128_COURTYARD_MARGIN_MM = 0.25


def _effects():
    return ("\n\t\t\t\t(effects\n\t\t\t\t\t(font\n"
            "\t\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t\t)\n\t\t\t\t)")


def _symbol_property(key, value, index, hide):
    hidden = "\n\t\t\t(hide yes)" if hide else ""
    return ('\t\t(property "%s" "%s"\n\t\t\t(at 0 %.2f 0)%s\n'
            '\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n'
            '\t\t\t\t)\n\t\t\t)\n\t\t)\n'
            % (key, value, 17.78 - 2.54 * index, hidden))


def _pin_text(kind, x, y, angle, name, number):
    return ('\t\t\t(pin %s line\n\t\t\t\t(at %.2f %.2f %d)\n'
            '\t\t\t\t(length 2.54)\n'
            '\t\t\t\t(name "%s"%s\n\t\t\t\t)\n'
            '\t\t\t\t(number "%s"%s\n\t\t\t\t)\n\t\t\t)'
            % (kind, x, y, angle, name, _effects(), number, _effects()))


def py32_symbol_text():
    left = PY32F003F1XPX_PINS[:10]
    right = PY32F003F1XPX_PINS[10:]
    half = 2.54 * (len(left) - 1) / 2.0
    lines = ['\t(symbol "%s"' % PY32_SYMBOL_NAME,
             '\t\t(pin_names\n\t\t\t(offset 1.016)\n\t\t)',
             '\t\t(exclude_from_sim no)',
             '\t\t(in_bom yes)',
             '\t\t(on_board yes)']
    lines.append(_symbol_property("Reference", "U", 0, False).rstrip("\n"))
    lines.append(_symbol_property("Value", PY32_SYMBOL_NAME, 1,
                                  False).rstrip("\n"))
    lines.append(_symbol_property("Footprint", PY32_DEFAULT_FOOTPRINT, 2,
                                  True).rstrip("\n"))
    lines.append(_symbol_property("Datasheet", PY32_DATASHEET, 3,
                                  True).rstrip("\n"))
    lines.append('\t\t(symbol "%s_0_1"' % PY32_SYMBOL_NAME)
    lines.append('\t\t\t(rectangle')
    lines.append('\t\t\t\t(start -10.16 %.2f)' % (half + 2.54))
    lines.append('\t\t\t\t(end 10.16 %.2f)' % (-half - 2.54))
    lines.append('\t\t\t\t(stroke\n\t\t\t\t\t(width 0.254)\n'
                 '\t\t\t\t\t(type default)\n\t\t\t\t)')
    lines.append('\t\t\t\t(fill\n\t\t\t\t\t(type background)\n\t\t\t\t)')
    lines.append('\t\t\t)')
    lines.append('\t\t)')
    lines.append('\t\t(symbol "%s_1_1"' % PY32_SYMBOL_NAME)
    for index, (number, name, kind) in enumerate(left):
        y = half - 2.54 * index
        lines.append(_pin_text(kind, -12.7, y, 0, name, number))
    for index, (number, name, kind) in enumerate(reversed(right)):
        y = half - 2.54 * index
        lines.append(_pin_text(kind, 12.7, y, 180, name, number))
    lines.append('\t\t)')
    lines.append('\t)')
    return "\n".join(lines)


def tvs_symbol_text():
    return "\n".join([
        '\t(symbol "%s"' % TVS_SYMBOL_NAME,
        '\t\t(pin_numbers\n\t\t\t(hide yes)\n\t\t)',
        '\t\t(pin_names\n\t\t\t(offset 1.016)\n\t\t\t(hide yes)\n\t\t)',
        '\t\t(exclude_from_sim no)',
        '\t\t(in_bom yes)',
        '\t\t(on_board yes)',
        _symbol_property("Reference", "D", 0, False).rstrip("\n"),
        _symbol_property("Value", TVS_SYMBOL_NAME, 1, False).rstrip("\n"),
        _symbol_property("Footprint", "%s:%s" % (LIBRARY_NAME,
                                                 X1SON_FOOTPRINT_NAME),
                         2, True).rstrip("\n"),
        _symbol_property("Datasheet", TVS_DATASHEET, 3, True).rstrip("\n"),
        _symbol_property("ki_fp_filters", X1SON_FOOTPRINT_NAME, 4,
                         True).rstrip("\n"),
        '\t\t(symbol "%s_0_1"' % TVS_SYMBOL_NAME,
        '\t\t\t(rectangle',
        '\t\t\t\t(start -1.27 1.27)',
        '\t\t\t\t(end 1.27 -1.27)',
        '\t\t\t\t(stroke\n\t\t\t\t\t(width 0.254)\n'
        '\t\t\t\t\t(type default)\n\t\t\t\t)',
        '\t\t\t\t(fill\n\t\t\t\t\t(type background)\n\t\t\t\t)',
        '\t\t\t)',
        '\t\t)',
        '\t\t(symbol "%s_1_1"' % TVS_SYMBOL_NAME,
        _pin_text("passive", 0.0, -3.81, 90, "A1", "1"),
        _pin_text("passive", 0.0, 3.81, 270, "A2", "2"),
        '\t\t)',
        '\t)',
    ])


#: Terminal-block symbols. The stock generic connector symbols carry a
#: footprint filter that only accepts pin-header land patterns, so assigning a
#: terminal block to one is an ERC violation rather than a silent mismatch.
#: These carry a filter that describes what they are actually for.
TERMINAL_SYMBOLS = {
    "ScrewTerminal_1x02": ["1", "2"],
    "ContactTerminal_1x03": ["NO", "COM", "NC"],
}
TERMINAL_FOOTPRINT_FILTER = "TerminalBlock*"


def terminal_symbol_text(name, pin_names):
    half = 2.54 * (len(pin_names) - 1) / 2.0
    lines = ['\t(symbol "%s"' % name,
             '\t\t(pin_names\n\t\t\t(offset 1.016)\n\t\t)',
             '\t\t(exclude_from_sim yes)',
             '\t\t(in_bom yes)',
             '\t\t(on_board yes)',
             _symbol_property("Reference", "J", 0, False).rstrip("\n"),
             _symbol_property("Value", name, 1, False).rstrip("\n"),
             _symbol_property("Footprint", "", 2, True).rstrip("\n"),
             _symbol_property("Datasheet", "", 3, True).rstrip("\n"),
             _symbol_property("ki_fp_filters", TERMINAL_FOOTPRINT_FILTER, 4,
                              True).rstrip("\n"),
             '\t\t(symbol "%s_0_1"' % name,
             '\t\t\t(rectangle',
             '\t\t\t\t(start -2.54 %.2f)' % (half + 2.54),
             '\t\t\t\t(end 2.54 %.2f)' % (-half - 2.54),
             '\t\t\t\t(stroke\n\t\t\t\t\t(width 0.254)\n'
             '\t\t\t\t\t(type default)\n\t\t\t\t)',
             '\t\t\t\t(fill\n\t\t\t\t\t(type background)\n\t\t\t\t)',
             '\t\t\t)',
             '\t\t)',
             '\t\t(symbol "%s_1_1"' % name]
    for index, pin_name in enumerate(pin_names):
        y = half - 2.54 * index
        lines.append(_pin_text("passive", -5.08, y, 0, pin_name,
                               str(index + 1)))
    lines.append('\t\t)')
    lines.append('\t)')
    return "\n".join(lines)


def symbol_library_text():
    body = [py32_symbol_text(), tvs_symbol_text()]
    for name in sorted(TERMINAL_SYMBOLS):
        body.append(terminal_symbol_text(name, TERMINAL_SYMBOLS[name]))
    return "\n".join([
        '(kicad_symbol_lib',
        '\t(version %s)' % SYMBOL_LIB_VERSION,
        '\t(generator "%s")' % GENERATOR,
        '\t(generator_version "10.0")',
    ] + body + [')']) + "\n"


def x1son_footprint_text():
    width, height = X1SON_PAD_SIZE_MM
    offset = X1SON_PAD_PITCH_MM / 2.0
    body_x, body_y = (value / 2.0 for value in X1SON_BODY_MM)
    court_x = body_x + X1SON_COURTYARD_MARGIN_MM
    court_y = body_y + X1SON_COURTYARD_MARGIN_MM
    pads = []
    for number, sign in (("1", -1.0), ("2", 1.0)):
        pads.append(
            '\t(pad "%s" smd roundrect\n\t\t(at %.3f 0)\n'
            '\t\t(size %.3f %.3f)\n\t\t(layers "F.Cu" "F.Paste" "F.Mask")\n'
            '\t\t(roundrect_rratio 0.1667)\n\t)'
            % (number, sign * offset, width, height))
    outline = []
    for layer, half_x, half_y, thickness in (
            ("F.CrtYd", court_x, court_y, 0.05),
            ("F.Fab", body_x, body_y, 0.1)):
        outline.append(
            '\t(fp_rect\n\t\t(start %.3f %.3f)\n\t\t(end %.3f %.3f)\n'
            '\t\t(stroke\n\t\t\t(width %.2f)\n\t\t\t(type default)\n\t\t)\n'
            '\t\t(fill none)\n\t\t(layer "%s")\n\t)'
            % (-half_x, -half_y, half_x, half_y, thickness, layer))
    return "\n".join([
        '(footprint "%s"' % X1SON_FOOTPRINT_NAME,
        '\t(version %s)' % FOOTPRINT_VERSION,
        '\t(generator "%s")' % GENERATOR,
        '\t(generator_version "10.0")',
        '\t(layer "F.Cu")',
        '\t(descr "TI DPY0002A land pattern, SLLSEB1G drawing 4224561/C")',
        '\t(tags "X1SON DPY TVS")',
        '\t(attr smd)',
        '\t(property "Reference" "REF**"\n\t\t(at 0 -1.2 0)\n'
        '\t\t(layer "F.SilkS")\n\t\t(uuid "00000000-0000-0000-0000-'
        '000000000001")\n\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 0.6 0.6)\n'
        '\t\t\t\t(thickness 0.1)\n\t\t\t)\n\t\t)\n\t)',
        '\t(property "Value" "%s"\n\t\t(at 0 1.2 0)\n'
        '\t\t(layer "F.Fab")\n\t\t(uuid "00000000-0000-0000-0000-'
        '000000000002")\n\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 0.6 0.6)\n'
        '\t\t\t\t(thickness 0.1)\n\t\t\t)\n\t\t)\n\t)' % X1SON_FOOTPRINT_NAME,
    ] + outline + pads + [')']) + "\n"


def kf128_footprint_text():
    """Land pattern for the 5 V input terminal.

    The drawing dimensions the hole diameter and the pitch, so those are
    datasheet values; the annulus is this board's choice. The body is drawn
    with the wire-entry face toward -Y, which is how the layout places it so
    that field wiring leaves the board rather than crossing it.
    """
    half_pitch = KF128_PITCH_MM / 2.0
    front = -KF128_PIN_TO_ENTRY_FACE_MM
    back = KF128_BODY_DEPTH_MM - KF128_PIN_TO_ENTRY_FACE_MM
    half_width = KF128_PITCH_MM  # (P x 5.08) overall for two poles
    margin = KF128_COURTYARD_MARGIN_MM
    pads = []
    for number, sign in (("1", -1.0), ("2", 1.0)):
        pads.append(
            '\t(pad "%s" thru_hole %s\n\t\t(at %.3f 0)\n'
            '\t\t(size %.3f %.3f)\n\t\t(drill %.3f)\n'
            '\t\t(layers "*.Cu" "*.Mask")\n\t)'
            % (number, "rect" if number == "1" else "circle",
               sign * half_pitch, KF128_PAD_DIAMETER_MM,
               KF128_PAD_DIAMETER_MM, KF128_DRILL_MM))
    outline = [
        '\t(fp_rect\n\t\t(start %.3f %.3f)\n\t\t(end %.3f %.3f)\n'
        '\t\t(stroke\n\t\t\t(width 0.05)\n\t\t\t(type default)\n\t\t)\n'
        '\t\t(fill none)\n\t\t(layer "F.CrtYd")\n\t)'
        % (-half_width - margin, front - margin,
           half_width + margin, back + margin),
        '\t(fp_rect\n\t\t(start %.3f %.3f)\n\t\t(end %.3f %.3f)\n'
        '\t\t(stroke\n\t\t\t(width 0.1)\n\t\t\t(type default)\n\t\t)\n'
        '\t\t(fill none)\n\t\t(layer "F.Fab")\n\t)'
        % (-half_width, front, half_width, back),
    ]
    return "\n".join([
        '(footprint "%s"' % KF128_FOOTPRINT_NAME,
        '\t(version %s)' % FOOTPRINT_VERSION,
        '\t(generator "%s")' % GENERATOR,
        '\t(generator_version "10.0")',
        '\t(layer "F.Cu")',
        '\t(descr "Cixi Kefa KF128-5.08 2-pole screw terminal, PCB layout '
        'from drawing KF128-5.08 rev A")',
        '\t(tags "terminal block screw 5.08mm")',
        '\t(attr through_hole)',
        '\t(property "Reference" "REF**"\n\t\t(at 0 %.2f 0)\n'
        '\t\t(layer "F.SilkS")\n\t\t(uuid "00000000-0000-0000-0000-'
        '000000000011")\n\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1 1)\n'
        '\t\t\t\t(thickness 0.15)\n\t\t\t)\n\t\t)\n\t)' % (front - 1.2),
        '\t(property "Value" "%s"\n\t\t(at 0 %.2f 0)\n'
        '\t\t(layer "F.Fab")\n\t\t(uuid "00000000-0000-0000-0000-'
        '000000000012")\n\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1 1)\n'
        '\t\t\t\t(thickness 0.15)\n\t\t\t)\n\t\t)\n\t)'
        % (KF128_FOOTPRINT_NAME, back + 1.2),
    ] + outline + pads + [')']) + "\n"


def sym_lib_table_text():
    return ('(sym_lib_table\n\t(version 7)\n'
            '\t(lib (name "%s")(type "KiCad")'
            '(uri "${KIPRJMOD}/library/%s.kicad_sym")(options "")(descr ""))\n)\n'
            % (LIBRARY_NAME, LIBRARY_NAME))


def fp_lib_table_text():
    return ('(fp_lib_table\n\t(version 7)\n'
            '\t(lib (name "%s")(type "KiCad")'
            '(uri "${KIPRJMOD}/library/%s.pretty")(options "")(descr ""))\n)\n'
            % (LIBRARY_NAME, LIBRARY_NAME))


def artifacts():
    return {
        SYMBOL_LIB_PATH: symbol_library_text(),
        os.path.join(FOOTPRINT_DIR, X1SON_FOOTPRINT_NAME + ".kicad_mod"):
            x1son_footprint_text(),
        os.path.join(FOOTPRINT_DIR, KF128_FOOTPRINT_NAME + ".kicad_mod"):
            kf128_footprint_text(),
        SYM_LIB_TABLE: sym_lib_table_text(),
        FP_LIB_TABLE: fp_lib_table_text(),
    }


def write():
    os.makedirs(FOOTPRINT_DIR, exist_ok=True)
    written = []
    for path, text in artifacts().items():
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        written.append(path)
    return sorted(written)


if __name__ == "__main__":
    for path in write():
        sys.stdout.write(path + "\n")
