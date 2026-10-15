# hardware/dryer_board/mains.py
"""The mains board: the fuse, the two relays and their drivers, the 120 VAC plug, and the
keyed 4-way link from the controller board (controller.py). It is the rev A single board's
mains strip, plus the relay driver stages, on its own 64 x 85 mm board; the mains copper is
the same geometry moved 48 mm left and 6 mm down. Parts and nets first, then placement (mm, origin at the
board's top-left corner, y down, rotation counter-clockwise on screen), then the DRC rules."""
from typing import List
from . import parts
from .parts import Part, NC

PROJECT = "dryer-mains"
SHORT = "mains"
TITLE = "ESP32 desiccant dryer mains board"
REVISION = "A"

MAINS_NETS = ["L_IN", "L_FUSED", "L_SW_A", "L_SW_B", "N"]
MAINS_PARTS = ("J_MAINS", "F1", "K1", "K2")   # the only parts a mains net may reach

# name -> (track width mm, clearance mm, via diameter mm, via drill mm, net name patterns)
NETCLASSES = {
    "Default": (0.3, 0.2, 0.6, 0.3, []),
    "MAINS":   (1.5, 1.0, 1.2, 0.6, MAINS_NETS),
    "P5":      (0.8, 0.2, 0.8, 0.4, ["+5V", "COIL_A", "COIL_B"]),
}

PARTS: List[Part] = [
    # The link from the controller: 5 V for the coils, GND, and the two base drives, each
    # already through its 1k series resistor on the controller board.
    parts.link("J_CTRL", "from controller"),

    # Relay stage A (heater A): 1k pulldown, MMBT2222A, S1M flyback, LED, Songle relay
    parts.r("R2", "1k", "RLY_A", "GND", d="heater A base pulldown, holds the relay off with the link unplugged"),
    parts.npn("Q1", "RLY_A", "GND", "COIL_A"),
    parts.s1m("D1", "+5V", "COIL_A"),
    parts.r("R3", "2.2k", "+5V", "LED_HA_R"), parts.led("D3", "red", "COIL_A", "LED_HA_R"),
    Part("K1", "SRD-05VDC-SL-C", "Relay:SANYOU_SRD_Form_C", "Relay_THT:Relay_SPDT_SANYOU_SRD_Series_Form_C",
         {"1": "L_FUSED", "2": "+5V", "5": "COIL_A", "3": "L_SW_A", "4": NC}, "C35449", False,
         "heater A relay; Songle SRD-05VDC-SL-C; JLCPCB extended"),
    # Relay stage B (heater B)
    parts.r("R5", "1k", "RLY_B", "GND", d="heater B base pulldown"),
    parts.npn("Q2", "RLY_B", "GND", "COIL_B"),
    parts.s1m("D2", "+5V", "COIL_B"),
    parts.r("R6", "2.2k", "+5V", "LED_HB_R"), parts.led("D4", "red", "COIL_B", "LED_HB_R"),
    Part("K2", "SRD-05VDC-SL-C", "Relay:SANYOU_SRD_Form_C", "Relay_THT:Relay_SPDT_SANYOU_SRD_Series_Form_C",
         {"1": "L_FUSED", "2": "+5V", "5": "COIL_B", "3": "L_SW_B", "4": NC}, "C35449", False,
         "heater B relay; Songle SRD-05VDC-SL-C; JLCPCB extended"),

    # Mains: fuse and the single 8-pin plug
    Part("F1", "T 3.15 A 5x20", "Device:Fuse", "dryer:Fuseholder_5x20mm_Covered_P22.50mm_Slot",
         {"1": "L_IN", "2": "L_FUSED"}, hand_fit=True,
         description="covered 5 x 20 mm holder on 22.5 mm pitch, slotted holes for 21.5 to 23.5 mm: hand-fitted from "
                     "the BLX-A style holders on hand (Amazon B0FCS5MK1Y, 10 A 250 V, pitch 22.3 +-1.0 mm by the "
                     "moulding's datasheet, not stated by the seller: measure one, hardware/README.md); the "
                     "fab-fitted alternative is XFCN PTF-77 C717030 (22.50 mm, UL 250 VAC 20 A, same body as the "
                     "PTF-76-B), JLCPCB extended. The T 3.15 A fuse itself is fitted by hand"),
    Part("J_MAINS", "120 VAC", "Connector_Generic:Conn_01x08",
         "dryer:PhoenixContact_MSTBA_2,5_8-G-5,08_1x08_P5.08mm_Horizontal_Drill1.7mm",
         {"1": "L_IN", "2": "N", "3": "L_SW_A", "4": "N", "5": "L_SW_B", "6": "N", "7": "L_FUSED", "8": "N"}, "C395786",
         description="L in, N in, heater A L-sw/N, heater B L-sw/N, PSU L (fused)/N; DORABO DB2ERC-5.08-8P-GN, "
                     "right angle, 300 V 15 A (UL); plug DB2EK-5.08-8P-GN-S C395791, loose; JLCPCB extended"),

    # Mounting holes, power flags
    parts.hole("H1"), parts.hole("H2"), parts.hole("H3"), parts.hole("H4"),
    parts.flag("#FLG1", "+5V"), parts.flag("#FLG2", "GND"),
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
    n = nets()
    for k in ("K1", "K2"):
        if by_ref(k).pins["4"] != NC:
            errs.append("%s NC contact must stay unconnected" % k)
    for net in MAINS_NETS:
        for ref, _ in n.get(net, []):
            if ref not in MAINS_PARTS:
                errs.append("mains net %s reaches %s" % (net, ref))
    # The reverse: every connected pin on the mains parts' mains side is on a mains net, so
    # it gets the MAINS netclass and the 6 mm rules. (K1/K2 pads 2 and 5 are the SELV coil;
    # pad 4, NC, is checked above.)
    mains_pins = [("J_MAINS", pin) for pin in by_ref("J_MAINS").pins] + [("F1", pin) for pin in by_ref("F1").pins]
    mains_pins += [(k, pad) for k in ("K1", "K2") for pad in ("1", "3")]
    for ref, pin in mains_pins:
        net = by_ref(ref).pins.get(pin, NC)
        if net != NC and net not in MAINS_NETS:
            errs.append("%s pin %s is on %s, which is not a mains net" % (ref, pin, net))
    if by_ref("J_CTRL").pins != parts.LINK_PINS:
        errs.append("J_CTRL pins %s, the link is %s" % (by_ref("J_CTRL").pins, parts.LINK_PINS))
    return errs

# ---------------------------------------------------------------------------------------
# Placement. The SELV strip (x < 22.5) holds the link header and the two driver stages; the
# mains zone (x >= 24.5) behind the 2 mm slot holds the relays and J_MAINS as the rev A single
# board had them, moved 48 mm left and 6 mm down (x_new = x_old - 48, y_new = y_old + 6; J_MAINS
# and the N copper 2 mm further right on the 2 mm wider board), so the clearances measured in
# docs/hardware.md "Mains layout and clearance" are unchanged. The 6 mm drop and the 2 mm of
# width make room for F1 on its 22.5 mm pitch: its L_FUSED pad must keep 6 mm hole clearance
# from H2 while its L_IN pad keeps 6 mm from the SELV pour.

BOARD_W, BOARD_H = 64.0, 85.0
HOLES = {"H1": (4, 4), "H2": (60, 4), "H3": (4, 81), "H4": (60, 81)}

SLOT_X = (22.5, 24.5)
SLOT_SEGMENTS = [(3, 20), (24, 32), (36, 58), (62, 70), (74, 82)]
MAINS_ZONE = (24.5, 0.0, 64.0, 85.0)
RELAY_AREAS = [(18.0, 18.0, 38.0, 38.0), (18.0, 56.0, 38.0, 76.0)]
GND_POUR = (2.0, 2.0, 21.5, 83.0)

PLACE = {
    "H1": (4, 4, 0), "H2": (60, 4, 0), "H3": (4, 81, 0), "H4": (60, 81, 0),
    # link header on the left edge, pin 1 at the top (rotation 270 runs the XH's pins down the
    # board), between the two driver stages
    "J_CTRL": (6, 42, 270),
    # mains zone
    "K1": (28, 28, 0), "K2": (28, 66, 0),
    "F1": (29.8, 13, 0),
    "J_MAINS": (53.5, 68, 90),
    # relay driver A (beside relay A)
    "R2": (14, 23.5, 0), "Q1": (19, 22, 0), "D1": (19, 27.5, 90), "R3": (14, 26.5, 0), "D3": (14, 29.5, 0),
    # relay driver B
    "R5": (16, 57, 0), "D2": (15, 62, 90), "Q2": (19.5, 61, 0), "R6": (19.5, 65.5, 0), "D4": (19.5, 68.5, 0),
}

# Mains copper, laid by board.add_mains_copper (locked; Freerouting never routes mains).
# (net, layer, polyline). Width is the MAINS netclass's 1.5 mm. Hand-placed because the
# custom rules in RULES are not visible to the router. Distances held:
# - 3.5 mm from the relay coil pads and the SELV coil corridors at y 22.05/34.05/60.05/72.05
#   (5.5 mm centre to a coil pad);
# - 6 mm, copper edge to copper edge, from SELV copper outside the relay areas. The SELV pour
#   ends at x 21.5 (GND_POUR), so mains copper edges stay at x >= 27.5: a 1.5 mm track's
#   centre at x >= 28.25, F1's 4 mm wide pad 1 centre at x >= 29.5 (it sits at 29.8);
# - 6 mm hole clearance from the M4 holes (H2 at (60, 4): F1's pad 2 at (52.3, 13) is the
#   closest mains copper, about 7.9 mm from the hole's edge);
# - 1 mm between mains nets (the NC pads are mains), at least 1.5 mm from L to N copper and
#   1.8 mm between the L-side nets (RULES holds them to 1.6 mm). The L_FUSED stub to J_MAINS
#   pin 7 runs at y 38.3, 2.0 mm clear of K1's NO pad (L_SW_A), and jogs up onto the pad;
# - the relay_pads relaxation (3.5 mm) applies to a whole segment if any of it touches a relay
#   area (insideArea tests the item, not the overlapping part), so every segment that would cross
#   an area edge is split there: the x 37 spines at y 17/39/55 (the middle piece's 0.75 mm end
#   caps stay outside both areas, y 18-38 and 56-76), the L_FUSED diagonal at (39, 18), and the
#   L_IN feed and the L_FUSED stub at x 39, so no mains segment outside an area is relaxed.
# The spine at x 37 runs between the coil pads (x <= 33.7 + 1.75) and the NC/NO pads: L_IN
# on F.Cu, L_FUSED on B.Cu. N links all four N pins on the right of J_MAINS; the switched
# lines reach pins 3 and 5 from the left. F1 has its pins at x 29.8 and 52.3 on y 13, where the
# L_IN stub starts and the L_FUSED diagonal comes down to the spine; the diagonal passes K1's
# netless NC pad at 2.9 mm, which is mains to mains (the in-class 1 mm applies).
MAINS_TRACKS = [
    ("L_IN", "F.Cu", [(34, 13), (29.8, 13)]),
    ("L_IN", "F.Cu", [(34, 13), (37, 16), (37, 17), (37, 39), (37, 55), (37, 68), (39, 68), (53.5, 68)]),
    ("L_FUSED", "B.Cu", [(52.3, 13), (39, 18), (37, 20), (37, 39), (37, 55), (37, 66), (28, 66)]),
    ("L_FUSED", "B.Cu", [(28, 28), (37, 28)]),
    ("L_FUSED", "B.Cu", [(37, 38.3), (39, 38.3), (52.72, 38.3), (53.5, 37.52)]),
    ("L_SW_A", "F.Cu", [(42.15, 34.05), (45.5, 37.4), (45.5, 54.5), (48.84, 57.84), (53.5, 57.84)]),
    ("L_SW_B", "B.Cu", [(42.15, 72.05), (47, 67.2), (47, 47.68), (53.5, 47.68)]),
    ("N", "F.Cu", [(53.5, 32.44), (57.6, 32.44), (57.6, 62.92), (53.5, 62.92)]),
    ("N", "F.Cu", [(53.5, 42.6), (57.6, 42.6)]),
    ("N", "F.Cu", [(53.5, 52.76), (57.6, 52.76)]),
]

# References that would print over a label (J_MAINS's and J_CTRL's over their pin labels) or
# off the board (the holes'); board.py hides them on the silkscreen, they stay on F.Fab.
HIDDEN_REFS = ("J_MAINS", "J_CTRL", "H1", "H2", "H3", "H4")

# (text, x, y, size, rotation, layer, justify)
SILK = [
    ("dryer mains board  rev ${REVISION}  AGPL-3.0  github.com/jrytio/desiccant-dryer", 30, 1.4, 0.8, 0, "F.SilkS", "center"),
    ("MAINS 120 VAC", 44, 78, 2.0, 0, "F.SilkS", "center"),
    ("keep 6 mm from SELV", 44, 81, 1.0, 0, "F.SilkS", "center"),
    ("HTR A", 9.5, 29.5, 0.8, 0, "F.SilkS", "center"), ("HTR B", 19.5, 70.7, 0.8, 0, "F.SilkS", "center"),
    ("CONTROLLER", 6, 37.8, 0.8, 0, "F.SilkS", "center"),
]
# Link pins, right of the header, one per position (pin 1 at y 42, pitch 2.5 downward).
SILK += [(name, 9.3, 42 + i * 2.5, 0.8, 0, "F.SilkS", "left") for i, name in enumerate(["5V", "GND", "HTR A", "HTR B"])]
# Mains header pins, left of the pads, one per position (pin 1 at y 68, pitch 5.08 upward).
# Vertical, centred at x 49.5 in the gap between the relay outline (x 46.55) and J_MAINS's
# pin-1 triangle (x 50.53): horizontal labels would run under the relay bodies.
SILK += [(name, 49.5, 68 - i * 5.08, 0.8, 90, "F.SilkS", "center")
         for i, name in enumerate(["L IN", "N IN", "HTR A", "N", "HTR B", "N", "PSU L", "PSU N"])]
# A line along the slot, mains side.
SILK_LINES = [(25.5, 3, 25.5, 82)]

def rule_areas():
    """The rule areas board.build lays: (name, (x1, y1, x2, y2), (no fills, no tracks, no vias, no pads))."""
    out = [("mains_nopour", MAINS_ZONE, (True, False, False, False))]
    out += [("relay_pads", r, (False, False, False, False)) for r in RELAY_AREAS]
    return out

def edge_outlines():
    """The Edge.Cuts shapes build draws, each as its corner points: the board rectangle, then
    one rectangle per slot segment."""
    def corners(x1, y1, x2, y2):
        return [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]
    x1, x2 = SLOT_X
    return [corners(0, 0, BOARD_W, BOARD_H)] + [corners(x1, y1, x2, y2) for y1, y2 in SLOT_SEGMENTS]

# The relay NC pad (4) carries no net, so no copper ever reaches it, but COM connects to it
# whenever the coil is off: it is live mains that the netclass rules cannot see. The last
# rule names it directly; it comes after the relay_pads relaxation so that cannot override it.
# memberOfFootprint('K*') does not match in KiCad 10.0.6, so both relays are named.
# The NC pad is netless, so the two "mains to selv" rules would also see it as SELV on the B
# side; it is at mains potential, so they exclude it and mains copper passes it at the MAINS
# in-class clearance. An M4 head or washer bears on the area round each mounting hole, so
# mains copper keeps 6 mm from every non-plated hole (spec, "Stackup and fab").
# The MAINS netclass clearance (1 mm) covers L to N; the L-side nets (L_IN, L_FUSED, L_SW_A,
# L_SW_B) keep 1.6 mm from each other: a bridge between two of them bypasses the fuse or turns
# a heater on with its relay open, so they get more margin than the netclass gives.
# The net name is A.NetName: A.Net != 'N' parses in 10.0.6 but does not exclude N.
RULES = """(version 1)
(rule "mains track width"
  (condition "A.NetClass == 'MAINS'")
  (constraint track_width (min 1.5mm)))
(rule "mains to board edge"
  (condition "A.NetClass == 'MAINS'")
  (constraint edge_clearance (min 1mm)))
(rule "mains to selv"
  (condition "A.NetClass == 'MAINS' && B.NetClass != 'MAINS' && !(B.Pad_Number == '4' && (B.memberOfFootprint('K1') || B.memberOfFootprint('K2')))")
  (constraint clearance (min 6mm)))
(rule "mains L to L"
  (condition "A.NetClass == 'MAINS' && B.NetClass == 'MAINS' && A.NetName != 'N' && B.NetName != 'N'")
  (constraint clearance (min 1.6mm)))
(rule "mains to selv at relay pads"
  (condition "A.NetClass == 'MAINS' && B.NetClass != 'MAINS' && A.insideArea('relay_pads') && !(B.Pad_Number == '4' && (B.memberOfFootprint('K1') || B.memberOfFootprint('K2')))")
  (constraint clearance (min 3.5mm)))
(rule "relay NC contact is live"
  (condition "(A.memberOfFootprint('K1') || A.memberOfFootprint('K2')) && A.Pad_Number == '4' && B.NetClass != 'MAINS'")
  (constraint clearance (min 6mm)))
(rule "mains to mounting holes"
  (condition "A.NetClass == 'MAINS' && B.Pad_Type == 'NPTH, mechanical'")
  (constraint hole_clearance (min 6mm)))
"""
