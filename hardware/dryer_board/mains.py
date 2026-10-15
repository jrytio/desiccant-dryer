# hardware/dryer_board/mains.py
"""The mains board: the fuse, the two relays and their drivers, the 120 VAC plug, and the
keyed 4-way link from the controller board (controller.py), on a 45 x 70 mm board (the mains
space in the enclosure). The mains copper keeps the rev A single board's arrangement (a spine
between the relay coils and contacts, L_IN and L_FUSED on opposite layers, N linked beside
the plug) and the distances it held. Parts and nets first, then placement (mm, origin at the
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
# Placement. 45 x 70 mm, the mains space in the enclosure. SELV strip x 0-7 (link header and
# both driver stages, two narrow columns, GND pour), slot x 7-9 with four gaps for the coil
# tracks, mains zone x 9-45: relays with COM at x 12 and contacts at x 26.2, F1 across the top
# of the zone, J_MAINS pads at x 39.5 with the plug entering from the right edge and N linked
# at x 43.15 on the plug side.
#
# What fixes each position (courtyards measured from the KiCad 10.0.6 footprints):
# - J_MAINS at x 39.5: the N links run 1.1 mm right of the pads (x 43.15, 1.5 wide) and keep
#   1.1 mm from the board edge, so the pads cannot go further right; its courtyard (x 36.95 to
#   50.05, 43.7 tall) runs from y 13.86 to 57.58, between F1 and H4's courtyard (from y 61.4).
# - F1 at (12.4, 14): its courtyard (x 10.46 to 36.84) must end left of J_MAINS's, which puts
#   pad 1 at x 12.4 (its edge 1.4 mm from the slot), and that courtyard reaches H2's (x 36.4 up, to
#   y 8.6), so F1's top courtyard edge sits at y 8.65 (y 14). Pad 2 is then 7.8 mm from H2's
#   hole edge.
# - K1 at y 29: K1's top coil pad (SELV) keeps 6 mm from F1's pad 1 (6.27 measured); F1 is
#   not in a relay area. K2 at y 51.5: L_IN reaches J_MAINS pin 1 at y 53.5 between K2's NC
#   and NO pads, as on rev A (y COM + 2, 1.8 mm from NO).
# - The SELV strip: H1 and H3's courtyards leave y 8.6 to 61.4. Nothing SELV comes within
#   6 mm of F1's pad 1 (x 10.4 up, y 12.4 to 15.6): the column beside it (x 2) carries driver
#   A's flyback diode and transistor, the second column (x 5.4) starts at y 20.8. J_CTRL and
#   the second column also keep the plain 6 mm from the relay COM pads.

BOARD_W, BOARD_H = 45.0, 70.0
HOLES = {"H1": (4, 4), "H2": (41, 4), "H3": (4, 66), "H4": (41, 66)}

SLOT_X = (7.0, 9.0)
# coil pads at y 23.05 / 35.05 (K1) and 45.55 / 57.55 (K2): gaps 21-25, 33-37, 43.5-47.5, 55.5-59.5
SLOT_SEGMENTS = [(3, 21), (25, 33), (37, 43.5), (47.5, 55.5), (59.5, 67)]
MAINS_ZONE = (9.0, 0.0, 45.0, 70.0)
# COM +-10 mm in y, from the strip to just past the spine at x 21 (rev A: COM +-10 both ways)
RELAY_AREAS = [(2.0, 19.0, 22.0, 39.0), (2.0, 41.5, 22.0, 61.5)]
# The pour starts at y 21: the outline's corner (6.5, 21) is 6.66 mm from the corner of F1
# pad 1's bounding box (10.4, 15.6); the filled copper is 7.34 mm from the pad's copper. It
# has to hold that by its outline: board.build fills it before the project's DRC rules exist,
# so the saved fill would not pull back the 6 mm by itself.
GND_POUR = (2.0, 21.0, 6.5, 68.0)

PLACE = {
    "H1": (4, 4, 0), "H2": (41, 4, 0), "H3": (4, 66, 0), "H4": (41, 66, 0),
    # link header on the left edge, pin 1 at the top (rotation 270 runs the XH's pins down the
    # board), between the two driver stages; x 3.95 keeps its courtyard (x 0.01 to 6.84) on the
    # board. Pins y 33 to 40.5: the plain 6 mm from both COM pads (y 29 and 51.5), not the
    # relay-area 3.5, which is for the relay's own coil-to-COM geometry.
    "J_CTRL": (3.95, 33, 270),
    # relay driver A above it: diode, transistor, pulldown, LED down the edge column, the LED
    # resistor in the second column
    "D1": (2, 12.4, 90), "Q1": (2, 18.2, 90), "R2": (2, 22.2, 90), "D3": (2, 25.9, 90), "R3": (5.4, 22.5, 90),
    # relay driver B below it, down the edge column; the second column (x 5.4) stays 6 mm from
    # K2's COM (y 51.5), so only the LED resistor sits there, at the bottom
    "R5": (2, 45.3, 90), "Q2": (2, 49.1, 90), "D2": (2, 55, 90), "D4": (2, 59.6, 0), "R6": (5.4, 59.6, 90),
    # mains zone
    "K1": (12, 29, 0), "K2": (12, 51.5, 0),
    "F1": (12.4, 14, 0),
    "J_MAINS": (39.5, 53.5, 90),
}

# Mains copper, laid by board.add_mains_copper (locked; Freerouting never routes mains).
# (net, layer, polyline). Width is the MAINS netclass's 1.5 mm. Hand-placed because the
# custom rules in RULES are not visible to the router. Distances held (measured on the
# generated board, copper edge to copper edge):
# - 3.5 mm from the relay coil pads and the SELV coil corridors at y 23.05/35.05/45.55/57.55
#   inside the relay areas (the spine at x 21 is 5.05 mm from the coil pads, COM 3.5);
# - 6 mm from SELV copper outside the relay areas. F1's pad 1 (L_IN) is the mains copper
#   nearest the strip outside an area: 7.34 mm to the pour, 6.27 mm to K1's top coil
#   pad. The spine's short pieces between the areas are 6.5 mm from the coil pads;
# - 6 mm hole clearance from the M4 holes (H2 at (41, 4): F1's pad 2 at (34.9, 14) is the
#   closest mains copper, 7.8 mm from the hole's edge);
# - 1 mm between mains nets (the NC pads are mains). L to N 1.10 mm (the rule is 1.0; the
#   single board had 1.55; regaining it would put F1's pad 1 at the slot's 1 mm limit): the N
#   links beside the plug pins. 1.8 mm between the L-side nets (RULES holds them
#   to 1.6 mm): L_IN passes K2's NO pad at 1.8, L_SW_B passes K1's NO pad at 2.1 on B.Cu;
# - 1 mm to the board edge: the N links at x 43.15 are 1.1 mm from it;
# - the relay_pads relaxation (3.5 mm) applies to a whole segment if any of it touches a relay
#   area (insideArea tests the item, not the overlapping part), so every segment that would cross
#   an area edge is split there: the x 21 spines at y 18.2 and 39.8/40.7 (the pieces outside
#   end 0.75 mm, a cap, short of the areas, y 19-39 and 41.5-61.5), the L_IN feed to J_MAINS
#   at x 23.5, so no mains segment outside an area is relaxed.
# The spine at x 21 runs between the coil pads (x <= 13.95 + 1.25) and the NC/NO pads: L_IN
# on F.Cu, L_FUSED on B.Cu. F1 has its pins at x 12.4 and 34.9 on y 14; L_IN leaves pad 1 to
# the right and drops onto the spine, L_FUSED leaves pad 2 to the left on the other layer, and
# a second L_FUSED run drops from pad 2 to J_MAINS pin 7. N links the four N pins on the right
# of J_MAINS; the switched lines reach pins 3 and 5 from the left, L_SW_A on F.Cu, L_SW_B on
# B.Cu up the x 30.5 lane between the relay contacts and the plug.
MAINS_TRACKS = [
    ("L_IN", "F.Cu", [(12.4, 14), (18, 14), (21, 17), (21, 18.2), (21, 39.8), (21, 40.7), (21, 53.5), (23.5, 53.5), (39.5, 53.5)]),
    ("L_FUSED", "B.Cu", [(34.9, 14), (24, 14), (21, 17), (21, 18.2), (21, 39.8), (21, 40.7), (21, 51.5), (12, 51.5)]),
    ("L_FUSED", "B.Cu", [(12, 29), (21, 29)]),
    ("L_FUSED", "B.Cu", [(34.9, 14), (34.9, 23.02), (39.5, 23.02)]),
    ("L_SW_A", "F.Cu", [(26.15, 35.05), (34.44, 43.34), (39.5, 43.34)]),
    ("L_SW_B", "B.Cu", [(26.15, 57.55), (30.5, 53.2), (30.5, 33.18), (39.5, 33.18)]),
    ("N", "F.Cu", [(39.5, 17.94), (43.15, 17.94), (43.15, 48.42), (39.5, 48.42)]),
    ("N", "F.Cu", [(39.5, 28.1), (43.15, 28.1)]),
    ("N", "F.Cu", [(39.5, 38.26), (43.15, 38.26)]),
]

# References that would print over a label (J_MAINS's and J_CTRL's over their pin labels) or
# off the board (the holes', and the edge column's D1, Q1, D2, Q2, whose references fall left of
# the edge); board.py hides them on the silkscreen, they stay on F.Fab.
HIDDEN_REFS = ("J_MAINS", "J_CTRL", "H1", "H2", "H3", "H4", "D1", "Q1", "D2", "Q2")

# (text, x, y, size, rotation, layer, justify)
SILK = [
    # The title in two lines: at the 0.8 mm minimum text height one line is 45 mm long.
    ("dryer mains board  rev ${REVISION}  AGPL-3.0", 22.5, 1.1, 0.8, 0, "F.SilkS", "center"),
    ("github.com/jrytio/desiccant-dryer", 22.5, 3.0, 0.8, 0, "F.SilkS", "center"),
    ("MAINS 120 VAC", 25, 66, 2.0, 0, "F.SilkS", "center"),
    ("keep 6 mm from SELV", 25, 68.5, 1.0, 0, "F.SilkS", "center"),
    ("HTR A", 3.75, 25.9, 0.8, 90, "F.SilkS", "center"), ("HTR B", 5.4, 54.5, 0.8, 90, "F.SilkS", "center"),
    # On the back, mirrored by board.py: on the front J_CTRL's body covers the whole strip
    # width beside its pads.
    ("CONTROLLER", 6.0, 36.75, 0.8, 90, "B.SilkS", "center"),
]
# Link pins, pin 1 first, as one column reading down the header beside its pads (pin 1 at
# y 33, pitch 2.5 downward), on the back: on the front the header body covers the strip
# (right of it is the slot), and "HTR B" at the 0.8 mm minimum is wider than the room beside
# the pads, so the names cannot sit one per pin.
SILK += [("5V  GND  HTR A  HTR B", 1.05, 36.75, 0.8, 90, "B.SilkS", "center")]
# Mains header pins, left of the pads, one per position (pin 1 at y 53.5, pitch 5.08 upward).
# Vertical, centred at x 33.5 in the gap between the relay outline (x 30.55) and J_MAINS's
# pin-1 triangle (x 36.5): horizontal labels would run under the relay bodies.
SILK += [(name, 33.5, 53.5 - i * 5.08, 0.8, 90, "F.SilkS", "center")
         for i, name in enumerate(["L IN", "N IN", "HTR A", "N", "HTR B", "N", "PSU L", "PSU N"])]
# A line along the slot, mains side.
SILK_LINES = [(10, 3, 10, 67)]

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
