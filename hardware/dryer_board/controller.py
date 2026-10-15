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
# Placement. 85 x 70 mm, the controller space in the enclosure. The Thing Plus lies along the
# long edge with its USB-C face 3 mm past the left edge (x = -3) and its antenna at the right
# end over a copper-free keep-out; the 12-pin row is above the 16-pin row (component side up,
# USB left). SparkFun .brd: 12-pin pin 1 is 24.13 mm and 16-pin pin 1 is 13.97 mm from the USB
# face, the rows are 20.32 mm apart, the board is 22.86 wide and 64.77 long. Socket rotation 90
# runs the pins toward +x from pin 1.

BOARD_W, BOARD_H = 85.0, 70.0
HOLES = {"H1": (4, 4), "H2": (81, 4), "H3": (4, 66), "H4": (81, 66)}

_USB_X = -3.0
_ROW12_Y = 10.0
_ROW16_Y = _ROW12_Y + 20.32
# Antenna: the WROOM antenna is the last 6.3 mm of the S2 (x 55.5 to 61.8). No copper on
# either layer and no pads, so the keep-out starts past the last socket pins (x 49.07, pads to
# 49.92: the rows end 12.70 mm before the antenna end), at 53.5 mm from the USB face as on
# rev A. Where the C6's antenna sits on its board is not verified here.
ANTENNA_KEEPOUT = (50.5, 6.0, 66.0, 34.0)
# No tracks or vias under U1's body (TRACO TSR-1 datasheet: avoid routing under the
# converter). U1's courtyard in x, from its top down to 0.5 mm short of the pad row's centre
# line: with the area down to the pad row the router could not reach pads 1 and 3 (nine
# connections left unrouted on rev A). Pads and pours stay allowed. route.py's router copy
# keeps it as a keepout.
U1_KEEPOUT = (20.4, 40.1, 32.7, 45.5)   # U1 at (24, 46): courtyard x 20.41..32.70
GND_POUR = (2.0, 2.0, 83.0, 68.0)
MAINS_TRACKS = []   # no mains copper on this board

PLACE = {
    "J_ESP12": (_USB_X + 24.13, _ROW12_Y, 90),
    "J_ESP16": (_USB_X + 13.97, _ROW16_Y, 90),
    "H1": (4, 4, 0), "H2": (81, 4, 0), "H3": (4, 66, 0), "H4": (81, 66, 0),
    # link header, top right, beside the antenna keep-out; pin 1 at the top (rotation 270 runs
    # the XH's pins down the board, its body toward the keep-out). x 72.5 leaves J_SENS's
    # courtyard (from x 76.2) clear; the base series resistors sit below it.
    "J_RLY": (72.5, 10, 270), "R1": (71, 23, 0), "R4": (71, 26, 0),
    # right edge: sensor header vertical, pin 1 at the bottom of the run (rotation 90 runs the
    # pins up the board), clear of H2's and H4's M4 courtyards (y 8.6 and 61.4)
    "J_SENS": (81, 41, 90),
    # sensor pull-up and decoupling beside the sensor header
    "R18": (72, 29.5, 0), "C5": (72, 32.5, 0), "C6": (72, 35.5, 0),
    # 5 V block (row at y 46), with the SW-USB and its legends to the right below the keep-out
    "U1": (24, 46, 0), "C2": (18.5, 46, 90), "C3": (35, 46, 90), "C4": (41, 45, 0),
    "R17": (21, 51.5, 0), "D13": (25.5, 51.5, 0), "D14": (32.5, 51.5, 0), "SW1": (62, 37.5, 0),
    # 24 V input chain: plug bottom left above J_DISP, PPTC and Schottky in the gap to J_LOADS,
    # the bulk capacitor on the left edge below the USB end, the LED above the plug
    "J_24V": (12.7, 60.3, 0), "F2": (25.2, 59, 0), "D11": (32, 59, 0), "C1": (4.6, 46, 90),
    "R16": (12, 51, 0), "D12": (16.5, 51, 0),
    # test points in a row under the ESP
    "TP1": (8, 36, 0), "TP2": (11.5, 36, 0), "TP3": (15, 36, 0), "TP4": (18.5, 36, 0),
    "TP5": (22, 36, 0), "TP6": (25.5, 36, 0), "TP7": (29, 36, 0), "TP8": (32.5, 36, 0), "TP9": (36, 36, 0),
    # MOSFET stages A, B, C in columns at x 50, 59.5, 69, above J_LOADS
    "R7": (50, 45, 0), "R8": (50, 48, 0), "Q3": (50, 52, 0), "D5": (50, 57, 0), "D8": (54.5, 48, 0), "R9": (54.5, 52, 0),
    "R10": (59.5, 45, 0), "R11": (59.5, 48, 0), "Q4": (59.5, 52, 0), "D6": (59.5, 57, 0), "D9": (64, 48, 0), "R12": (64, 52, 0),
    "R13": (69, 45, 0), "R14": (69, 48, 0), "Q5": (69, 52, 0), "D7": (69, 57, 0), "D10": (73.5, 48, 0), "R15": (73.5, 51.5, 0),
    # bottom edge: loads plug, and the display header along the edge (rotation 90 runs its
    # pins toward +x); vertical headers, plugs from above
    "J_LOADS": (42, 65.5, 0),
    "J_DISP": (12, 66.5, 90),
}

# Footprints whose reference would print over a label: R18/C5/C6 over the J_SENS legend, the
# LEDs' (D8-D10, D12, D13) over "VLV A", "VLV B", "FAN", "24V", "5V". board.py hides them on
# the silkscreen; the names stay on F.Fab and in the assembly drawings. "FAN" sits above D10
# like "VLV A"/"VLV B", with R15 below it. The edge connectors' references (J_24V, J_LOADS,
# J_SENS, J_RLY) would print over their pin legends, which name them.
HIDDEN_REFS = ("R18", "C5", "C6", "D8", "D9", "D10", "D12", "D13", "H1", "H2", "H3", "H4",
               "J_24V", "J_LOADS", "J_SENS", "J_RLY")

# (text, x, y, size, rotation, layer, justify)
SILK = [
    # The front has no free strip long enough for the title (the ESP covers the top, the
    # connectors the bottom edge), so it runs along the bottom edge on the back.
    ("ESP32 desiccant dryer controller  rev ${REVISION}  AGPL-3.0  github.com/jrytio/desiccant-dryer", 42.5, 69.0, 0.9, 0, "B.SilkS", "center"),
    # SW-USB's sentence below it, ON and OFF at its ends (ON at pin 1): above it is its reference
    ("SW-USB: OFF before any USB-C cable", 63.5, 40.8, 0.8, 0, "F.SilkS", "center"),
    ("ON", 58.6, 37.5, 0.8, 0, "F.SilkS", "center"), ("OFF", 70.6, 37.5, 0.8, 0, "F.SilkS", "center"),
    # J_DISP's legend below its pins: above them is J_24V's body
    ("GND 3V3 SCL SDA RES DC CS BLK", 20.89, 68.9, 0.8, 0, "F.SilkS", "center"),
    ("3V3 DQ GND  3V3 DQ GND  3V3 DQ GND", 75.0, 27, 0.8, 90, "F.SilkS", "center"),
    # J_24V's legend above it: below it is J_DISP
    ("24V+  0V", 15.24, 54.0, 0.8, 0, "F.SilkS", "center"),
    # J_LOADS's legend above it: its body reaches the bottom edge
    ("VA+  VA-  VB+  VB-  F+  F-", 54.7, 59.5, 0.8, 0, "F.SilkS", "center"),
    ("24V", 16.5, 49.2, 0.8, 0, "F.SilkS", "center"), ("5V", 25.5, 49.7, 0.8, 0, "F.SilkS", "center"),
    ("VLV A", 54.5, 46.2, 0.8, 0, "F.SilkS", "center"), ("VLV B", 64, 46.2, 0.8, 0, "F.SilkS", "center"), ("FAN", 73.5, 46.2, 0.8, 0, "F.SilkS", "center"),
    ("MAINS BOARD", 70.5, 5.5, 0.8, 0, "F.SilkS", "center"),
    # socket numerals over the end pins, outside the rows (the references sit at the rows' ends)
    ("1", 21.13, 7.3, 0.8, 0, "F.SilkS", "center"), ("12", 49.07, 7.3, 0.8, 0, "F.SilkS", "center"),
    ("1", 10.97, 33.0, 0.8, 0, "F.SilkS", "center"), ("16", 49.07, 33.0, 0.8, 0, "F.SilkS", "center"),
    ("USB end", 1.5, 20.2, 0.8, 90, "B.SilkS", "center"),
]
# Link pins, left of the header's body, one per position (pin 1 at y 10, pitch 2.5 downward),
# in the protoboard harness's order. Right of the pins is J_SENS, 2.7 mm away.
SILK += [(name, 68.3, 10 + i * 2.5, 0.8, 0, "F.SilkS", "right") for i, name in enumerate(["5V", "GND", "HTR A", "HTR B"])]
# Socket functions on the back (readable with the board upside down), mirrored by board.py:
# the 12-pin row's above it, the 16-pin row's below it, each reading along its pin.
_P12 = {4: "HTR A", 5: "HTR B", 6: "VLV A", 7: "VLV B", 8: "FAN", 3: "USB 5V"}
_P16 = {2: "3V3", 4: "GND", 5: "BL", 8: "RST", 9: "DC", 10: "CS", 11: "SCK", 12: "MOSI", 13: "1-WIRE"}
SILK += [(n, PLACE["J_ESP12"][0] + (p - 1) * 2.54, _ROW12_Y - 3.5, 0.8, 90, "B.SilkS", "center") for p, n in _P12.items()]
SILK += [(n, PLACE["J_ESP16"][0] + (p - 1) * 2.54, _ROW16_Y + 3.5, 0.8, 90, "B.SilkS", "center") for p, n in _P16.items()]
# (x1, y1, x2, y2) silkscreen line segments, F.SilkS
SILK_LINES = []

def rule_areas():
    """The rule areas board.build lays: (name, (x1, y1, x2, y2), (no fills, no tracks, no vias, no pads))."""
    return [("antenna_keepout", ANTENNA_KEEPOUT, (True, True, True, True)),
            ("u1_keepout", U1_KEEPOUT, (False, True, True, False))]

def edge_outlines():
    """The Edge.Cuts shapes build draws, each as its corner points: the board rectangle only."""
    return [[(0, 0), (BOARD_W, 0), (BOARD_W, BOARD_H), (0, BOARD_H)]]
