# hardware/dryer_board/controller.py
"""The controller board: the socketed ESP, 24 V in, the 5 V module, the USB-pin feed, the
three MOSFET stages, the sensor and display headers, and the keyed 4-way link that drives
the relays on the mains board (mains.py). Parts and nets first, then where everything sits:
mm, origin at the board's top-left corner, y down (KiCad's frame), rotation in degrees
counter-clockwise on screen. Sources: spec section 'Board layout and clearance'; ESP header
positions from docs/pinout-verification.md."""
from typing import List
from . import parts, pinmap
from .parts import Part, NC

PROJECT = "dryer-controller"
SHORT = "controller"
TITLE = "ESP32 desiccant dryer controller"
REVISION = "A"
MAINS_NETS: List[str] = []   # nothing on this board is mains; the mains nets live on dryer-mains

# name -> (track width mm, clearance mm, via diameter mm, via drill mm, net name patterns)
NETCLASSES = {
    "Default": (0.3, 0.2, 0.6, 0.3, []),
    "P24":     (0.8, 0.2, 0.8, 0.4, ["+24V*", "SW_VA", "SW_VB", "SW_FAN"]),
    "P5":      (0.8, 0.2, 0.8, 0.4, ["+5V", "V5_D", "VBUS"]),
}
RULES = "(version 1)\n"   # no custom DRC rules: the mains rules are the mains board's (mains.RULES)

def _socket_pins(header):
    """Net for every position of the 16- or 12-pin socket from pinmap."""
    net_for = {"usb_5v": "VBUS", "heater_a": "HTR_A", "heater_b": "HTR_B", "valve_a": "VLV_A",
               "valve_b": "VLV_B", "fan": "FAN", "3v3": "+3V3", "gnd": "GND", "lcd_bl": "LCD_BL",
               "lcd_rst": "LCD_RST", "lcd_dc": "LCD_DC", "lcd_cs": "LCD_CS", "spi_clk": "SPI_CLK",
               "spi_mosi": "SPI_MOSI", "onewire": "OW_DQ"}
    pins = {str(i): NC for i in range(1, header + 1)}
    for fn, (hdr, pos) in pinmap.FUNCTIONS.items():
        if hdr == header and fn in net_for:
            pins[str(pos)] = net_for[fn]
    return pins

PARTS: List[Part] = [
    # ESP sockets (female headers). Rotated 180 on the board so pin 1 is at the USB end.
    Part("J_ESP16", "Thing Plus 16-pin", "Connector_Generic:Conn_01x16",
         "Connector_PinSocket_2.54mm:PinSocket_1x16_P2.54mm_Vertical", _socket_pins(16), "C2905421",
         description="ESP socket, 16-pin row; Kinghelm KH-2.54FH-1X16P-H8.5, 8.5 mm; JLCPCB extended"),
    Part("J_ESP12", "Thing Plus 12-pin", "Connector_Generic:Conn_01x12",
         "Connector_PinSocket_2.54mm:PinSocket_1x12_P2.54mm_Vertical", _socket_pins(12), "C2905419",
         description="ESP socket, 12-pin row; Kinghelm KH-2.54FH-1X12P-H8.5, 8.5 mm; JLCPCB extended"),

    # 24 V input: plug -> PPTC -> Schottky -> bulk -> LED
    Part("J_24V", "24 V in", "Connector_Generic:Conn_01x02",
         "dryer:PhoenixContact_MSTBVA_2,5_2-G-5,08_1x02_P5.08mm_Vertical_Drill1.7mm", {"1": "+24V_RAW", "2": "GND"}, "C395734",
         description="24 V supply, 2-pin 5.08 mm pluggable header; DORABO DB2EVC-5.08-2P-GN, 300 V 15 A (UL); "
                     "plug DB2EK-5.08-2P-GN-S C395732, loose; JLCPCB extended"),
    Part("F2", "PPTC 1.1 A 30 V", "Device:Polyfuse", "Fuse:Fuse_1812_4532Metric", {"1": "+24V_RAW", "2": "+24V_F"}, "C142747",
         description="resettable fuse on the 24 V input (F-03, G-11); Littelfuse 1812L110/33MR, 1.1 A hold, 33 V; JLCPCB extended"),
    Part("D11", "SS34", "Device:D_Schottky", "Diode_SMD:D_SMA", {"1": "+24V", "2": "+24V_F"}, "C8678",
         description="reverse-polarity series Schottky; MDD SS34; JLCPCB basic"),
    Part("C1", "100u 50V", "Device:C_Polarized", "Capacitor_SMD:CP_Elec_8x10.5", {"1": "+24V", "2": "GND"}, "C294509",
         description="24 V bulk; Lelon VZH101M1HTR-0810, 8 x 10 mm (terminals 3.1 mm apart, inside the 8x10.5 pads); JLCPCB extended"),
    parts.r("R16", "10k", "+24V", "LED_24V_R"),
    parts.led("D12", "green", "GND", "LED_24V_R"),

    # 5 V: fixed module in the TSR-1 / 78xx footprint
    Part("U1", "TSR 1-2450", "Converter_DCDC:TSR_1-2450", "Converter_DCDC:Converter_DCDC_TRACO_TSR-1_THT",
         {"1": "+24V", "2": "GND", "3": "+5V"}, hand_fit=True,
         description="fixed 5 V 1 A switching module, 78xx pinout (1 Vin, 2 GND, 3 Vout); TRACO TSR 1-2450, the part "
                     "this footprint is drawn for, hand-fitted (Mouser 495-TSR-1-2450, or the Amazon-sourced "
                     "'TSR 1-2450' the owner holds: same body and pitch, pin order bench-checked before soldering, "
                     "hardware/README.md); not at LCSC/JLCPCB. MornSun K7805-1000R3 (same pinout) is the alternative, "
                     "not stocked by LCSC/JLCPCB or Mouser (2026-10-14)"),
    parts.c("C2", "10u 50V", "+24V", "GND", d="module input, per datasheet"),
    parts.c("C3", "22u 10V", "+5V", "GND", d="module output, per datasheet"),
    Part("C4", "100u 16V", "Device:C_Polarized", "Capacitor_SMD:CP_Elec_6.3x7.7", {"1": "+5V", "2": "GND"}, "C231174",
         description="5 V bulk, feeds the relay coils over the link; Lelon VZH101M1CTR-0607, 6.3 x 7.7 mm; JLCPCB extended"),
    parts.r("R17", "2.2k", "+5V", "LED_5V_R"),
    parts.led("D13", "green", "GND", "LED_5V_R"),

    # USB pin feed: 5 V -> Schottky -> slide switch -> ESP 12-pin 3
    Part("D14", "SS34", "Device:D_Schottky", "Diode_SMD:D_SMA", {"1": "V5_D", "2": "+5V"}, "C8678",
         description="blocks a USB host back-feeding the 5 V bus; MDD SS34; JLCPCB basic"),
    Part("SW1", "SW-USB", "Switch:SW_SPDT", "dryer:SW_Slide_SPDT_SOFNG_SS-12D00_P2.50mm",
         {"1": "VBUS", "2": "V5_D", "3": NC}, "C22355741",
         description="OFF before any USB-C cable; SOFNG SS-12D00-G3, 0.5 A 24 V DC, pin 2 common; JLCPCB extended"),

    # Relay drive: the 1k base series resistor stays at this end of the link (as on the
    # protoboard harness), so a link fault puts at most 5 V through 1k onto the GPIO. The
    # pulldown, transistor, flyback, LED and relay are on the mains board.
    parts.r("R1", "1k", "HTR_A", "RLY_A", d="heater A base series; the link carries RLY_A to the mains board"),
    parts.r("R4", "1k", "HTR_B", "RLY_B", d="heater B base series; the link carries RLY_B to the mains board"),
    parts.link("J_RLY", "to mains board"),

    # MOSFET stages: valve A, valve B, fan (100 R gate, 10k pulldown, S1M flyback, LED from 24 V)
    parts.r("R7", "100", "VLV_A", "GATE_A"), parts.r("R8", "10k", "GATE_A", "GND"),
    parts.nfet("Q3", "GATE_A", "GND", "SW_VA"), parts.s1m("D5", "+24V", "SW_VA"),
    parts.r("R9", "10k", "+24V", "LED_VA_R"), parts.led("D8", "yellow", "SW_VA", "LED_VA_R"),
    parts.r("R10", "100", "VLV_B", "GATE_B"), parts.r("R11", "10k", "GATE_B", "GND"),
    parts.nfet("Q4", "GATE_B", "GND", "SW_VB"), parts.s1m("D6", "+24V", "SW_VB"),
    parts.r("R12", "10k", "+24V", "LED_VB_R"), parts.led("D9", "yellow", "SW_VB", "LED_VB_R"),
    parts.r("R13", "100", "FAN", "GATE_C"), parts.r("R14", "10k", "GATE_C", "GND"),
    parts.nfet("Q5", "GATE_C", "GND", "SW_FAN"), parts.s1m("D7", "+24V", "SW_FAN"),
    parts.r("R15", "10k", "+24V", "LED_FAN_R"), parts.led("D10", "yellow", "SW_FAN", "LED_FAN_R"),

    # 24 V loads and sensors
    Part("J_LOADS", "valves + fan", "Connector_Generic:Conn_01x06",
         "dryer:PhoenixContact_MSTBVA_2,5_6-G-5,08_1x06_P5.08mm_Vertical_Drill1.7mm",
         {"1": "+24V", "2": "SW_VA", "3": "+24V", "4": "SW_VB", "5": "+24V", "6": "SW_FAN"}, "C395768",
         description="valve A, valve B, fan: 24+ and SW each; DORABO DB2EVC-5.08-6P-GN, 300 V 15 A (UL); "
                     "plug DB2EK-5.08-6P-GN-S C395774, loose; JLCPCB extended"),
    Part("J_SENS", "DS18B20 x3", "Connector_Generic:Conn_01x09",
         "dryer:PhoenixContact_MCV_1,5_9-G-3.5_1x09_P3.50mm_Vertical_Drill1.4mm",
         {"1": "+3V3", "2": "OW_DQ", "3": "GND", "4": "+3V3", "5": "OW_DQ", "6": "GND", "7": "+3V3", "8": "OW_DQ", "9": "GND"},
         "C430559",
         description="three 3V3/DQ/GND triples, 3.5 mm pluggable; DORABO DB2EVC-3.5-9P-GN; "
                     "plug DB2EK-3.5-9P-GN-S C430561, loose; JLCPCB extended"),
    parts.r("R18", "5.1k", "+3V3", "OW_DQ", d="1-wire pullup"),
    parts.c("C5", "100n", "+3V3", "GND", d="3V3 at the sensor header"),
    parts.c("C6", "10u 10V", "+3V3", "GND", d="3V3 at the sensor header"),
    Part("J_DISP", "ST7789 240x240", "Connector_Generic:Conn_01x08",
         "Connector_PinHeader_2.54mm:PinHeader_1x08_P2.54mm_Vertical",
         {"1": "GND", "2": "+3V3", "3": "SPI_CLK", "4": "SPI_MOSI", "5": "LCD_RST", "6": "LCD_DC", "7": "LCD_CS", "8": "LCD_BL"},
         "C492407", description="GND 3V3 SCL SDA RES DC CS BLK; XFCN PZ254V-11-08P; JLCPCB extended"),

    # Test points, mounting holes, power flags. The SHT45 is not on this board: it plugs into
    # the Thing Plus's own Qwiic connector (docs/hardware.md "Header pinouts").
    parts.tp("TP1", "GND", "GND"), parts.tp("TP2", "3V3", "+3V3"), parts.tp("TP3", "5V", "+5V"), parts.tp("TP4", "24V", "+24V"),
    parts.tp("TP5", "HTR_A", "HTR_A"), parts.tp("TP6", "HTR_B", "HTR_B"), parts.tp("TP7", "VLV_A", "VLV_A"),
    parts.tp("TP8", "VLV_B", "VLV_B"), parts.tp("TP9", "FAN", "FAN"),
    parts.hole("H1"), parts.hole("H2"), parts.hole("H3"), parts.hole("H4"),
    parts.flag("#FLG1", "+24V"), parts.flag("#FLG2", "GND"), parts.flag("#FLG3", "+3V3"),
]

def by_ref(ref):
    return parts.by_ref(PARTS, ref)

def nets():
    return parts.nets(PARTS)

def board_parts():
    return parts.board_parts(PARTS)

def check():
    """Invariants the table must satisfy. Returns a list of violations."""
    errs = parts.check_nets(PARTS)
    for hdr, pos in pinmap.RESERVED:
        ref = "J_ESP16" if hdr == 16 else "J_ESP12"
        if by_ref(ref).pins[str(pos)] != NC:
            errs.append("%s position %d is reserved (%s)" % (ref, pos, pinmap.RESERVED[(hdr, pos)]))
    for hdr, ref in ((16, "J_ESP16"), (12, "J_ESP12")):
        want = _socket_pins(hdr)
        got = by_ref(ref).pins
        for pos in sorted(want, key=int):
            if got.get(pos) != want[pos]:
                errs.append("%s position %s is %s, pinmap says %s" % (ref, pos, got.get(pos), want[pos]))
    if by_ref("J_RLY").pins != parts.LINK_PINS:
        errs.append("J_RLY pins %s, the link is %s" % (by_ref("J_RLY").pins, parts.LINK_PINS))
    for net in ("L_IN", "L_FUSED", "L_SW_A", "L_SW_B", "N"):
        if net in nets():
            errs.append("mains net %s on the controller board" % net)
    return errs

# ---------------------------------------------------------------------------------------
# Placement. 76 x 85 mm: the SELV side of the rev A single board, minus the relay drivers,
# with the link header where they were. Height is set by the ESP (USB-C face 3 mm past the
# bottom edge) and J_LOADS; width by SW1 and the M4 holes to its right.

BOARD_W, BOARD_H = 76.0, 85.0
HOLES = {"H1": (4, 4), "H2": (72, 4), "H3": (4, 81), "H4": (72, 81)}

ANTENNA_KEEPOUT = (5.0, 16.0, 36.0, 34.5)
# No tracks or vias under U1's body (TRACO TSR-1 datasheet: avoid routing under the
# converter). U1's courtyard in x, from its top down to y 29.5, 0.5 mm short of the pad row's
# centre line: with the area down to y 30 the router could not reach pads 1 and 3 (nine
# connections left unrouted). Pads and pours stay allowed. route.py's router copy keeps it as
# a keepout.
U1_KEEPOUT = (40.4, 24.1, 52.7, 29.5)
GND_POUR = (2.0, 2.0, 74.0, 83.0)
MAINS_TRACKS = []   # no mains copper on this board

# ESP sockets: pin 1 at the USB end (y = 88 is the USB-C face, 3 mm past the edge).
_USB_Y = 88.0
_ESP_X = 9.0

PLACE = {
    "J_ESP12": (_ESP_X + 1.27, _USB_Y - 24.13, 180),
    "J_ESP16": (_ESP_X + 21.59, _USB_Y - 13.97, 180),
    "H1": (4, 4, 0), "H2": (72, 4, 0), "H3": (4, 81, 0), "H4": (72, 81, 0),
    # top strip: sensors, display
    # J_SENS 4 mm left of where the single board had it: H2's M4 courtyard reaches x 67.5
    "J_SENS": (33, 8, 0),
    "J_DISP": (38.3, 17, 90),
    "R18": (40, 21.5, 0), "C5": (44, 21.5, 0), "C6": (48, 21.5, 0),
    # 5 V block
    "U1": (44, 30, 0), "C2": (38.5, 30, 90), "C3": (55, 30, 90), "C4": (62, 29, 0),
    # R17 sits 0.5 mm below D13: at y 36 the router, kept out from under U1, necks a GND
    # track to 0.18 mm (under the 0.2 mm minimum) to pass its pad.
    "R17": (40, 36.5, 0), "D13": (45, 36, 0),
    "D14": (52, 35.5, 0), "SW1": (62, 37, 0),
    # test points. TP2 sits 0.1 mm left of the 3.5 mm grid: at x 37.5 the routed board trips a
    # KiCad 10 DRC false positive (GND fill reported on TP2 and its via with 0 mm clearance, while
    # the saved fill keeps 0.3 mm). 37.4 is the nearest position that routes clean; 37.3 and 37.6 put
    # LCD_CS across the antenna keep-out bounding-box test, 37.7 trips the same DRC fault.
    "TP1": (34, 39.3, 0), "TP2": (37.4, 39.3, 0), "TP3": (41, 39.3, 0), "TP4": (44.5, 39.3, 0),
    "TP5": (48, 39.3, 0), "TP6": (51.5, 39.3, 0), "TP7": (55, 39.3, 0), "TP8": (34, 55, 0), "TP9": (34, 58.5, 0),
    # 24 V input
    "J_24V": (38, 47, 0), "F2": (52, 44, 0), "D11": (60, 44, 0), "C1": (54, 51, 0),
    "R16": (40, 55.5, 0), "D12": (45, 55.5, 0),
    # relay drive: the base series resistors and the link header on the right edge, pin 1 at the
    # top (rotation 270 runs the XH's pins down the board; its latch faces inboard)
    "R1": (62, 14.5, 0), "R4": (64, 48.5, 0),
    "J_RLY": (71, 20, 270),
    # MOSFET stages A, B, C in columns x = 38, 47.5, 57
    "R7": (38, 58, 0), "R8": (38, 61, 0), "Q3": (38, 65, 0), "D5": (38, 70, 0), "D8": (42.5, 61, 0), "R9": (42.5, 65, 0),
    "R10": (47.5, 58, 0), "R11": (47.5, 61, 0), "Q4": (47.5, 65, 0), "D6": (47.5, 70, 0), "D9": (52, 61, 0), "R12": (52, 65, 0),
    "R13": (57, 58, 0), "R14": (57, 61, 0), "Q5": (57, 65, 0), "D7": (57, 70, 0), "D10": (61.5, 61, 0), "R15": (61.5, 65, 0),
    "J_LOADS": (38, 78, 0),
}

# Footprints whose reference would print over a label: R18/C5/C6 over the J_DISP legend, the
# LEDs' (D8-D10, D12, D13) over "VLV A", "VLV B", "FAN", "24V", "5V". board.py hides them on
# the silkscreen; the names stay on F.Fab and in the assembly drawings. "FAN" sits above D10
# like "VLV A"/"VLV B" (below it, R15's reference covered it).
HIDDEN_REFS = ("R18", "C5", "C6", "D8", "D9", "D10", "D12", "D13", "H1", "H2", "H3", "H4")

# (text, x, y, size, rotation, layer, justify)
SILK = [
    ("ESP32 desiccant dryer controller  rev ${REVISION}  AGPL-3.0  github.com/jrytio/desiccant-dryer", 38, 1.4, 0.9, 0, "F.SilkS", "center"),
    ("SW-USB: OFF before any USB-C cable", 57.0, 40.8, 0.8, 0, "F.SilkS", "center"),
    ("ON", 62.0, 34.6, 0.8, 0, "F.SilkS", "center"), ("OFF", 67.0, 34.6, 0.8, 0, "F.SilkS", "center"),
    ("GND 3V3 SCL SDA RES DC CS BLK", 46.5, 19.6, 0.8, 0, "F.SilkS", "center"),
    ("3V3 DQ GND  3V3 DQ GND  3V3 DQ GND", 47, 12.6, 0.8, 0, "F.SilkS", "center"),
    ("24V+  0V", 40.5, 52.3, 0.8, 0, "F.SilkS", "center"),
    ("VA+  VA-  VB+  VB-  F+  F-", 50.7, 84.0, 0.8, 0, "F.SilkS", "center"),
    ("24V", 45, 53.3, 0.8, 0, "F.SilkS", "center"), ("5V", 45, 33.8, 0.8, 0, "F.SilkS", "center"),
    ("VLV A", 42.5, 58.8, 0.8, 0, "F.SilkS", "center"), ("VLV B", 52, 58.8, 0.8, 0, "F.SilkS", "center"), ("FAN", 61.0, 58.8, 0.8, 0, "F.SilkS", "center"),
    ("MAINS BOARD", 70.5, 15.8, 0.8, 0, "F.SilkS", "center"),
    ("1", 10.27, 66.5, 0.8, 0, "F.SilkS", "center"), ("12", 10.27, 33.3, 0.8, 0, "F.SilkS", "center"),
    ("1", 30.59, 76.7, 0.8, 0, "F.SilkS", "center"), ("16", 30.59, 33.3, 0.8, 0, "F.SilkS", "center"),
    ("USB end", 20, 83, 0.8, 0, "B.SilkS", "center"),
]
# Link pins, left of the header, one per position (pin 1 at y 20, pitch 2.5 downward), in the
# protoboard harness's order.
SILK += [(name, 66.8, 20 + i * 2.5, 0.8, 0, "F.SilkS", "right") for i, name in enumerate(["5V", "GND", "HTR A", "HTR B"])]
# Socket functions on the back (readable with the board upside down), mirrored by board.py.
_P12 = {4: "HTR A", 5: "HTR B", 6: "VLV A", 7: "VLV B", 8: "FAN", 3: "USB 5V"}
_P16 = {2: "3V3", 4: "GND", 5: "BL", 8: "RST", 9: "DC", 10: "CS", 11: "SCK", 12: "MOSI", 13: "1-WIRE"}
SILK += [(n, PLACE["J_ESP12"][0] + 3.5, PLACE["J_ESP12"][1] - (p - 1) * 2.54, 0.8, 0, "B.SilkS", "left") for p, n in _P12.items()]
SILK += [(n, PLACE["J_ESP16"][0] - 3.5, PLACE["J_ESP16"][1] - (p - 1) * 2.54, 0.8, 0, "B.SilkS", "right") for p, n in _P16.items()]
# (x1, y1, x2, y2) silkscreen line segments, F.SilkS
SILK_LINES = []

def rule_areas():
    """The rule areas board.build lays: (name, (x1, y1, x2, y2), (no fills, no tracks, no vias, no pads))."""
    return [("antenna_keepout", ANTENNA_KEEPOUT, (True, True, True, True)),
            ("u1_keepout", U1_KEEPOUT, (False, True, True, False))]

def edge_outlines():
    """The Edge.Cuts shapes build draws, each as its corner points: the board rectangle only."""
    return [[(0, 0), (BOARD_W, 0), (BOARD_W, BOARD_H), (0, BOARD_H)]]
