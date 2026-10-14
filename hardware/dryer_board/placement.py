# hardware/dryer_board/placement.py
"""Where everything sits. mm, origin at the board's top-left corner, y down (KiCad's frame).
Rotation is KiCad's (degrees, counter-clockwise on screen). Sources: spec section
'Board layout and clearance'; ESP header positions from docs/pinout-verification.md."""

BOARD_W, BOARD_H = 110.0, 85.0
HOLES = {"H1": (4, 4), "H2": (106, 4), "H3": (4, 81), "H4": (106, 81)}

SLOT_X = (70.5, 72.5)
SLOT_SEGMENTS = [(3, 14), (18, 26), (30, 52), (56, 64), (68, 82)]
MAINS_ZONE = (72.5, 0.0, 110.0, 85.0)
ANTENNA_KEEPOUT = (5.0, 16.0, 36.0, 34.5)
RELAY_AREAS = [(66.0, 12.0, 86.0, 32.0), (66.0, 50.0, 86.0, 70.0)]
SELV_POUR = (2.0, 2.0, 69.5, 83.0)

# ESP sockets: pin 1 at the USB end (y = 88 is the USB-C face, 3 mm past the edge).
_USB_Y = 88.0
_ESP_X = 9.0

PLACE = {
    "J_ESP12": (_ESP_X + 1.27, _USB_Y - 24.13, 180),
    "J_ESP16": (_ESP_X + 21.59, _USB_Y - 13.97, 180),
    "H1": (4, 4, 0), "H2": (106, 4, 0), "H3": (4, 81, 0), "H4": (106, 81, 0),
    # mains zone
    "K1": (76, 22, 0), "K2": (76, 60, 0),
    "F1": (77.3, 7, 0),
    "J_MAINS": (99.5, 62, 90),
    # top strip: sensors, display
    "J_SENS": (37, 8, 0),
    "J_DISP": (38.3, 17, 90),
    "R18": (40, 21.5, 0), "C5": (44, 21.5, 0), "C6": (48, 21.5, 0),
    # 5 V block
    "U1": (44, 30, 0), "C2": (38.5, 30, 90), "C3": (55, 30, 90), "C4": (62, 29, 0),
    "R17": (40, 36, 0), "D13": (45, 36, 0),
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
    # relay driver A (beside relay A)
    "R1": (62, 14.5, 0), "R2": (62, 17.5, 0), "Q1": (67, 16, 0), "D1": (67, 21.5, 90), "R3": (62, 20.5, 0), "D3": (62, 23.5, 0),
    # relay driver B
    "R4": (64, 48.5, 0), "R5": (64, 51, 0), "D2": (63, 56, 90), "Q2": (67.5, 55, 0), "R6": (67.5, 59.5, 0), "D4": (67.5, 62.5, 0),
    # MOSFET stages A, B, C in columns x = 38, 47.5, 57
    "R7": (38, 58, 0), "R8": (38, 61, 0), "Q3": (38, 65, 0), "D5": (38, 70, 0), "D8": (42.5, 61, 0), "R9": (42.5, 65, 0),
    "R10": (47.5, 58, 0), "R11": (47.5, 61, 0), "Q4": (47.5, 65, 0), "D6": (47.5, 70, 0), "D9": (52, 61, 0), "R12": (52, 65, 0),
    "R13": (57, 58, 0), "R14": (57, 61, 0), "Q5": (57, 65, 0), "D7": (57, 70, 0), "D10": (61.5, 61, 0), "R15": (61.5, 65, 0),
    "J_LOADS": (38, 78, 0),
}

# Mains copper, laid by board.add_mains_copper (locked; Freerouting never routes mains).
# (net, layer, polyline). Width is the MAINS netclass's 1.5 mm. Hand-placed because the
# custom rules in project.RULES are not visible to the router. Distances held:
# - 3.5 mm from the relay coil pads and the SELV coil corridors at y 16.05/28.05/54.05/66.05
#   (5.5 mm centre to a coil pad);
# - 6 mm, copper edge to copper edge, from SELV copper outside the relay areas. The SELV pour
#   ends at x 69.5 (SELV_POUR), so mains copper edges stay at x >= 75.5: a 1.5 mm track's
#   centre at x >= 76.25, F1's 3 mm pad 1 centre at x >= 77.0 (it sits at 77.3);
# - 6 mm from the M3 holes (H2 at (106, 4): nothing mains within 8.35 mm of its centre);
# - 1 mm between mains nets (the NC pads are mains), at least 1.5 mm from L to N copper and
#   1.8 mm between the L-side nets (project.RULES holds them to 1.6 mm). The L_FUSED stub to
#   J_MAINS pin 7 runs at y 32.3, 2.0 mm clear of K1's NO pad (L_SW_A), and jogs up onto the pad;
# - the relay_pads relaxation (3.5 mm) applies to a whole segment if any of it touches a relay
#   area (insideArea tests the item, not the overlapping part), so every segment that would cross
#   an area edge is split there: the x 85 spines at y 11/33/49 (the middle piece's 0.75 mm end
#   caps stay outside both areas, y 12-32 and 50-70), the L_FUSED diagonal at (87, 12), and the
#   L_IN feed and the L_FUSED stub at x 87, so no mains segment outside an area is relaxed.
# The spine at x 85 runs between the coil pads (x <= 81.7 + 1.75) and the NC/NO pads: L_IN
# on F.Cu, L_FUSED on B.Cu. N links all four N pins on the right of J_MAINS; the switched
# lines reach pins 3 and 5 from the left. F1 (XFCN PTF-76-B) has its pins at x 77.3 and 92.3 on
# y 7, where the L_IN stub and the L_FUSED spine start.
MAINS_TRACKS = [
    ("L_IN", "F.Cu", [(82, 7), (77.3, 7)]),
    ("L_IN", "F.Cu", [(82, 7), (85, 10), (85, 11), (85, 33), (85, 49), (85, 62), (87, 62), (99.5, 62)]),
    ("L_FUSED", "B.Cu", [(92.3, 7), (87, 12), (85, 14), (85, 33), (85, 49), (85, 60), (76, 60)]),
    ("L_FUSED", "B.Cu", [(76, 22), (85, 22)]),
    ("L_FUSED", "B.Cu", [(85, 32.3), (87, 32.3), (98.72, 32.3), (99.5, 31.52)]),
    ("L_SW_A", "F.Cu", [(90.15, 28.05), (93.5, 31.4), (93.5, 48.5), (96.84, 51.84), (99.5, 51.84)]),
    ("L_SW_B", "B.Cu", [(90.15, 66.05), (95, 61.2), (95, 41.68), (99.5, 41.68)]),
    ("N", "F.Cu", [(99.5, 26.44), (103.6, 26.44), (103.6, 56.92), (99.5, 56.92)]),
    ("N", "F.Cu", [(99.5, 36.6), (103.6, 36.6)]),
    ("N", "F.Cu", [(99.5, 46.76), (103.6, 46.76)]),
]

# (text, x, y, size, rotation, layer, justify)
SILK = [
    ("ESP32 desiccant dryer controller  rev ${REVISION}  AGPL-3.0  github.com/jrytio/desiccant-dryer", 53, 1.4, 0.9, 0, "F.SilkS", "center"),
    ("MAINS 120 VAC", 91, 75, 2.0, 0, "F.SilkS", "center"),
    ("keep 6 mm from SELV", 91, 78, 1.0, 0, "F.SilkS", "center"),
    ("SW-USB: OFF before any USB-C cable", 57.0, 40.8, 0.8, 0, "F.SilkS", "center"),
    ("ON", 62.0, 34.6, 0.8, 0, "F.SilkS", "center"), ("OFF", 67.0, 34.6, 0.8, 0, "F.SilkS", "center"),
    ("GND 3V3 SCL SDA RES DC CS BLK", 46.5, 19.6, 0.8, 0, "F.SilkS", "center"),
    ("3V3 DQ GND  3V3 DQ GND  3V3 DQ GND", 51, 12.6, 0.8, 0, "F.SilkS", "center"),
    ("24V+  0V", 40.5, 52.3, 0.8, 0, "F.SilkS", "center"),
    ("VA+  VA-  VB+  VB-  F+  F-", 50.7, 84.0, 0.8, 0, "F.SilkS", "center"),
    ("24V", 45, 53.3, 0.8, 0, "F.SilkS", "center"), ("5V", 45, 33.8, 0.8, 0, "F.SilkS", "center"),
    ("HTR A", 57.5, 23.5, 0.8, 0, "F.SilkS", "center"), ("HTR B", 67.5, 64.7, 0.8, 0, "F.SilkS", "center"),
    ("VLV A", 42.5, 58.8, 0.8, 0, "F.SilkS", "center"), ("VLV B", 52, 58.8, 0.8, 0, "F.SilkS", "center"), ("FAN", 61.5, 63.0, 0.8, 0, "F.SilkS", "center"),
    ("1", 10.27, 66.5, 0.8, 0, "F.SilkS", "center"), ("12", 10.27, 33.3, 0.8, 0, "F.SilkS", "center"),
    ("1", 30.59, 76.7, 0.8, 0, "F.SilkS", "center"), ("16", 30.59, 33.3, 0.8, 0, "F.SilkS", "center"),
    ("USB end", 20, 83, 0.8, 0, "B.SilkS", "center"),
]
# Mains header pins, left of the pads, one per position (pin 1 at y 62, pitch 5.08 upward).
# Vertical, in the 2.4 mm channel between the relay and header courtyards: horizontal labels
# would run under the relay bodies.
SILK += [(name, 95.8, 62 - i * 5.08, 0.8, 90, "F.SilkS", "center")
         for i, name in enumerate(["L IN", "N IN", "HTR A", "N", "HTR B", "N", "PSU L", "PSU N"])]
# Socket functions on the back (readable with the board upside down), mirrored by board.py.
_P12 = {4: "HTR A", 5: "HTR B", 6: "VLV A", 7: "VLV B", 8: "FAN", 3: "USB 5V"}
_P16 = {2: "3V3", 4: "GND", 5: "BL", 8: "RST", 9: "DC", 10: "CS", 11: "SCK", 12: "MOSI", 13: "1-WIRE"}
SILK += [(n, PLACE["J_ESP12"][0] + 3.5, PLACE["J_ESP12"][1] - (p - 1) * 2.54, 0.8, 0, "B.SilkS", "left") for p, n in _P12.items()]
SILK += [(n, PLACE["J_ESP16"][0] - 3.5, PLACE["J_ESP16"][1] - (p - 1) * 2.54, 0.8, 0, "B.SilkS", "right") for p, n in _P16.items()]
