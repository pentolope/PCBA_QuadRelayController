from __future__ import annotations

import os

CHANNEL_COUNT = 4

PROJECT_NAME = "quad_relay_controller"

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SYMBOL_LIBRARY_PATHS = (
    os.path.join(_REPO_ROOT, "library"),
    "/usr/share/kicad/symbols",
)

LIBRARY_NAME = "QuadRelayController"

#: The MCU pin each channel's command signal leaves on, in channel order.
CHANNEL_COMMAND_PINS = ("3", "4", "5", "6")

#: Contact function -> relay symbol pin. IEC 60617 relay numbering, confirmed
#: against the Omron drawing: the SPST-NO member of the same family drops the
#: pin pair that this map calls normally-closed.
CONTACT_PINS = {"NC": "12", "COM": "11", "NO": "14"}

#: Terminal positions left to right. Fixed by the layout, not by taste: the
#: relay's three contact rows reach three in-line terminals without a crossing
#: or a layer change only in this order.
TERMINAL_FUNCTIONS = ("NO", "COM", "NC")


def _part(lib_id, footprint, value, mpn=None, manufacturer=None, lcsc=None,
          datasheet="", in_bom=True, on_board=True):
    return {
        "lib_id": lib_id,
        "footprint": footprint,
        "value": value,
        "mpn": mpn,
        "manufacturer": manufacturer,
        "lcsc": lcsc,
        "datasheet": datasheet,
        "in_bom": in_bom,
        "on_board": on_board,
    }


def _resistor(value, lcsc, mpn):
    return _part("Device:R", "Resistor_SMD:R_0603_1608Metric", value,
                 mpn, "UNI-ROYAL(Uniroyal Elec)", lcsc)


def _capacitor(value, footprint, lcsc, mpn, manufacturer):
    return _part("Device:C", footprint, value, mpn, manufacturer, lcsc)


def _parts():
    parts = {
        "U1": _part(
            "%s:PY32F003F1xPx" % LIBRARY_NAME,
            "Package_SO:TSSOP-20_4.4x6.5mm_P0.65mm",
            "PY32F003F18P6TU", "PY32F003F18P6TU", "PUYA", "C5379864"),
        "Q5": _part(
            "Transistor_FET:AO3401A", "Package_TO_SOT_SMD:SOT-23",
            "AO3401A", "AO3401A", "Alpha & Omega Semiconductor", "C15127"),
        "J1": _part(
            "%s:ScrewTerminal_1x02" % LIBRARY_NAME,
            "%s:TerminalBlock_KF128-5.08_1x02_P5.08mm" % LIBRARY_NAME,
            "KF128-5.08-2P-AA", "KF128-5.08-2P-AA", "Cixi Kefa Elec",
            "C474952"),
        "J6": _part(
            "Connector_Generic:Conn_01x05",
            "Connector_PinHeader_2.54mm:PinHeader_1x05_P2.54mm_Vertical",
            "KH-2.54PH180-1X5P-L11.5", "KH-2.54PH180-1X5P-L11.5",
            "Shenzhen Kinghelm Elec", "C2932699"),
        "J7": _part(
            "Connector_Generic:Conn_01x04",
            "Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical",
            "KH-2.54PH180-1X4P-L11.5", "KH-2.54PH180-1X4P-L11.5",
            "Shenzhen Kinghelm Elec", "C2905435"),
        "R14": _resistor("100k", "C25803", "0603WAF1003T5E"),
        "R15": _resistor("10k", "C25804", "0603WAF1002T5E"),
        "R16": _resistor("4R7", "C23164", "0603WAF470KT5E"),
        "C3": _capacitor("10uF", "Capacitor_SMD:C_0805_2012Metric", "C15850",
                         "CL21A106KAYNNNE", "Samsung Electro-Mechanics"),
    }
    for index in (1, 2):
        parts["C%d" % index] = _capacitor(
            "10uF", "Capacitor_SMD:C_0805_2012Metric", "C15850",
            "CL21A106KAYNNNE", "Samsung Electro-Mechanics")
    for index in (4, 5, 6):
        parts["C%d" % index] = _capacitor(
            "100nF", "Capacitor_SMD:C_0603_1608Metric", "C14663",
            "CC0603KRX7R9BB104", "YAGEO")
    for channel in range(1, CHANNEL_COUNT + 1):
        parts["K%d" % channel] = _part(
            "Relay:G2RL-1-E", "Relay_THT:Relay_SPDT_Omron_G2RL-1-E",
            "G2RL-1-E DC5", "G2RL-1-E DC5", "Omron Electronics", "C1524515")
        parts["Q%d" % channel] = _part(
            "Transistor_FET:AO3400A", "Package_TO_SOT_SMD:SOT-23",
            "AO3400A", "AO3400A", "Alpha & Omega Semiconductor", "C20917")
        parts["D%d" % channel] = _part(
            "Device:D", "Diode_SMD:D_SOD-123",
            "1N4148W", "1N4148W", "ST(Semtech)", "C81598")
        parts["D%d" % (channel + 4)] = _part(
            "Device:LED", "LED_SMD:LED_0603_1608Metric",
            "KT-0603R", "KT-0603R", "Hubei KENTO Elec", "C2286")
        parts["J%d" % (channel + 1)] = _part(
            "%s:ContactTerminal_1x03" % LIBRARY_NAME,
            "TerminalBlock_Ningbo-Kagnex:"
            "TerminalBlock_Ningbo-Kagnex_HB9500M_1x03_P9.5mm",
            "HB9500M-9.5-03P-13-00A", "HB9500M-9.5-03P-13-00A",
            "Ningbo Kangnex Elec", "C162697")
        parts["R%d" % channel] = _resistor("100R", "C22775", "0603WAF1000T5E")
        parts["R%d" % (channel + 4)] = _resistor(
            "2.2k", "C4190", "0603WAF2201T5E")
        parts["R%d" % (channel + 8)] = _resistor(
            "1.5k", "C22843", "0603WAF1501T5E")
    parts["D9"] = _part(
        "Device:LED", "LED_SMD:LED_0603_1608Metric",
        "KT-0603R", "KT-0603R", "Hubei KENTO Elec", "C2286")
    parts["R13"] = _resistor("1.5k", "C22843", "0603WAF1501T5E")
    for index in range(10, 17):
        parts["D%d" % index] = _part(
            "%s:TPD1E10B06" % LIBRARY_NAME,
            "%s:TI_X1SON-2_1.0x0.6mm_P0.65mm" % LIBRARY_NAME,
            "TPD1E10B06DPYR", "TPD1E10B06DPYR", "Texas Instruments", "C48260")
    for index in range(1, 13):
        parts["TP%d" % index] = _part(
            "Connector:TestPoint", "TestPoint:TestPoint_Pad_D1.0mm",
            "TestPoint", in_bom=False)
    for index in range(1, 5):
        parts["H%d" % index] = _part(
            "Mechanical:MountingHole",
            "MountingHole:MountingHole_3.2mm_M3",
            "MountingHole_M3", in_bom=False)
    for index in range(1, 5):
        parts["#FLG%d" % index] = _part(
            "power:PWR_FLAG", "", "PWR_FLAG", in_bom=False, on_board=False)
    return parts


PARTS = _parts()


def _nets():
    ground = [
        "J1.2", "U1.7", "R14.2", "R15.2",
        "C1.2", "C2.2", "C3.2", "C4.2", "C5.2", "C6.2",
        "J6.5", "J7.4", "TP4.1", "#FLG4.1", "D9.1",
    ]
    coil_supply = [
        "Q5.2", "C1.1", "C2.1", "R16.1", "R13.1", "TP2.1", "#FLG2.1",
    ]
    logic_rail = [
        "R16.2", "C3.1", "C4.1", "C5.1", "U1.9", "J6.1", "J7.1",
        "D11.2", "TP3.1", "#FLG3.1",
    ]
    for index in range(10, 17):
        ground.append("D%d.1" % index)
    for channel in range(1, CHANNEL_COUNT + 1):
        ground.append("Q%d.2" % channel)
        ground.append("R%d.2" % (channel + 4))
        ground.append("D%d.1" % (channel + 4))
        coil_supply.append("K%d.A1" % channel)
        coil_supply.append("D%d.1" % channel)

    nets = {
        "GND": ground,
        "V5IN": ["J1.1", "Q5.3", "D10.2", "TP1.1", "#FLG1.1"],
        "VCOIL": coil_supply,
        "+5V": logic_rail,
        "PFET_G": ["Q5.1", "R14.1"],
        "BOOT0": ["U1.15", "R15.1"],
        "NRST": ["U1.18", "C6.1", "J6.4", "D12.2"],
        "SWDIO": ["U1.10", "J6.2", "D13.2"],
        "SWCLK": ["U1.11", "J6.3", "D14.2"],
        "UART_TX": ["U1.1", "J7.2", "D15.2"],
        "UART_RX": ["U1.2", "J7.3", "D16.2"],
    }
    for channel in range(1, CHANNEL_COUNT + 1):
        nets["RLY%d_CMD" % channel] = [
            "U1.%s" % CHANNEL_COMMAND_PINS[channel - 1],
            "R%d.1" % channel, "R%d.1" % (channel + 8)]
        nets["RLY%d_G" % channel] = [
            "R%d.2" % channel, "R%d.1" % (channel + 4),
            "Q%d.1" % channel, "TP%d.1" % (channel + 4)]
        nets["RLY%d_C" % channel] = [
            "Q%d.3" % channel, "K%d.A2" % channel, "D%d.2" % channel,
            "TP%d.1" % (channel + 8)]
        nets["LED%d_A" % channel] = [
            "R%d.2" % (channel + 8), "D%d.2" % (channel + 4)]
        for position, function in enumerate(TERMINAL_FUNCTIONS):
            nets["CH%d_%s" % (channel, function)] = [
                "K%d.%s" % (channel, CONTACT_PINS[function]),
                "J%d.%d" % (channel + 1, position + 1)]
    nets["PWR_LED_A"] = ["R13.2", "D9.2"]
    return nets


NETS = _nets()

NO_CONNECT = tuple(
    "U1.%d" % pin for pin in (8, 12, 13, 14, 16, 17, 19, 20))


#: The 5 V logic input the board declares on its silkscreen, and the range
#: every rail claim is evaluated over.
INPUT_SUPPLY = {"min_v": 4.75, "max_v": 5.25}

RAILS = {
    "V5IN": dict(INPUT_SUPPLY),
    "VCOIL": dict(INPUT_SUPPLY),
    "+5V": dict(INPUT_SUPPLY),
    "GND": {"min_v": 0.0, "max_v": 0.0},
}

NODE_VOLTAGE_RANGES = {
    "PFET_G": {"min_v": 0.0, "max_v": 0.0},
    "BOOT0": {"min_v": 0.0, "max_v": INPUT_SUPPLY["max_v"]},
}

#: The switched side is a separate galvanic system: no rail on this board
#: reaches it, and its declared rating is what the board is marked with.
SWITCHED_RATING = {
    "voltage_rms_v": 250.0,
    "current_a": 4.0,
    "insulation_to_logic": "reinforced",
    "insulation_between_channels": "reinforced",
    "insulation_within_channel": "functional",
}

#: Which side of the isolation boundary each net belongs to. Every net must
#: appear exactly once; the layout and the clearance rules are derived from
#: this, not from a hand-maintained coordinate list.
def _switched_nets():
    names = []
    for channel in range(1, CHANNEL_COUNT + 1):
        for function in ("NC", "COM", "NO"):
            names.append("CH%d_%s" % (channel, function))
    return tuple(names)


SWITCHED_NETS = _switched_nets()

LOGIC_NETS = tuple(sorted(set(NETS) - set(SWITCHED_NETS)))

#: Reference designators whose pads sit on the switched side of the boundary.
SWITCHED_REFERENCES = tuple(
    ["J%d" % (channel + 1) for channel in range(1, CHANNEL_COUNT + 1)])

#: What the assembler has to do beyond one reflow of the front side. Only
#: what a check reads is declared here: the placement side and the
#: through-hole population are both measured off the board.
ASSEMBLY_POLICY = {
    "placement_sides": 1,
    # one relay and one switched terminal per channel, the supply input
    # terminal, and the two logic-side headers
    "through_hole_soldered_parts": 2 * CHANNEL_COUNT + 1 + 2,
}

CONNECTOR_FUNCTION_NETS = {
    "J1": {"V5IN": "V5IN", "GND": "GND"},
    "J6": {"+5V": "+5V", "SWDIO": "SWDIO", "SWCLK": "SWCLK", "NRST": "NRST",
           "GND": "GND"},
    "J7": {"+5V": "+5V", "UART_TX": "UART_TX", "UART_RX": "UART_RX",
           "GND": "GND"},
}

#: Series element between the coil supply and the logic rail, and the bulk
#: it works against. Named here so the simulation and the rules agree.
LOGIC_RAIL_SERIES_REFERENCE = "R16"
LOGIC_RAIL_BULK_REFERENCES = ("C3", "C4", "C5")
COIL_SUPPLY_BULK_REFERENCES = ("C1", "C2")

#: A budget, not a measurement: the resistance of the field wiring and the
#: source feeding the 5 V input terminal.
INPUT_PATH_BUDGET_OHM = 0.5

#: A conservative design target, not a substantiated limit: the brief asks
#: for a small turn-off loop and states no figure, so the board declares one
#: and is checked against it. The seed places the flyback diode directly above
#: its coil pins, which is comfortably inside this.
FLYBACK_LOOP_AREA_TARGET_MM2 = 60.0

#: The build this board is costed and supplied for. A stock reading below
#: this is a finding, not a footnote.
PLANNED_BUILD_QUANTITY = 50

#: The maximum ambient the board is designed to operate at. The brief
#: conditions its dissipation requirement on "maximum ambient" and states no
#: figure, so the board declares one: every package rating is derated to it,
#: every part's stated ambient range is checked against it, and the coil drive
#: margin is evaluated from it.
MAX_AMBIENT_C = 40.0

#: The BOR option-byte setting the board's rail claim is evaluated against.
#: VBOR8 is the highest threshold the part offers, so a rail that stays above
#: it stays above every other selectable setting.
BROWN_OUT_OPTION = "VBOR8"


def pin_to_net():
    mapping = {}
    for net_name, pin_refs in NETS.items():
        for pin_ref in pin_refs:
            if pin_ref in mapping:
                raise ValueError(
                    "pin %s assigned to both %s and %s"
                    % (pin_ref, mapping[pin_ref], net_name))
            mapping[pin_ref] = net_name
    for pin_ref in NO_CONNECT:
        if pin_ref in mapping:
            raise ValueError(
                "pin %s is both no-connect and on net %s"
                % (pin_ref, mapping[pin_ref]))
    return mapping
