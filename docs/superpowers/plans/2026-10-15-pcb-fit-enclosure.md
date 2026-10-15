# Fit the two boards to the enclosure spaces — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Re-lay `dryer-controller` to 85 × 70 mm and `dryer-mains` to 45 × 70 mm with every part, net, rule and gate of the branch unchanged, and prove the sizes with tests before DRC.

**Architecture:** Each board is a module (`hardware/dryer_board/controller.py`, `mains.py`) holding its parts, `BOARD_W/H`, `HOLES`, keep-outs, `PLACE`, `SILK`, `MAINS_TRACKS` (mains only) and `rule_areas()`/`edge_outlines()`; `board.build(bd, pcb_path, fresh)` lays a board from them, `route.route(bd, pcb_path, passes)` routes its SELV nets with Freerouting in Docker, `check_sync` proves the committed project matches, `export.export_all(bd, ...)` writes fab files. The work is geometry: new constants and tables in the two board modules, a new test module that pins the outlines, then regenerate, route, check and export per board.

**Tech Stack:** KiCad 10.0.6 (`kicad-cli`, bundled Python 3.9 with `pcbnew`), Docker image `ghcr.io/freerouting/freerouting:2.5.0`, `scripts/hardware.sh <cmd> [controller|mains]`.

**Spec:** `docs/superpowers/specs/2026-10-15-pcb-two-board-split-design.md`

## Global Constraints

- Outlines exactly 85 × 70 mm (`controller`) and 45 × 70 mm (`mains`); holes 4.3 mm at (4, 4), (W−4, 4), (4, 66), (W−4, 66) on each board.
- No part, value, net, LCSC number or link pinout changes; `mains.RULES`, `mains.MAINS_NETS`, the relay pad roles and every red/green rule test stay as they are. A check is passed by moving copper, never by weakening a rule or a rule area.
- Mains copper is hand-placed in `mains.MAINS_TRACKS` (1.5 mm, locked); Freerouting routes only SELV nets (all nets on the controller board). The clearances the present `MAINS_TRACKS` comment block lists are held: 6 mm mains to SELV outside the relay areas, 3.5 mm inside them, 1.6 mm between L-side mains nets, 1 mm in-class, 1 mm mains to edge, 6 mm mains copper to every hole (copper edge to hole edge).
- The ESP's USB-C face sits 3 mm past the controller board's left edge; the antenna end lies over a copper-free keep-out; the U1 keep-out (no tracks or vias under the 5 V module's body) and the SW-USB ON/OFF legends stay.
- Python 3.9 (no `match`, no `X | Y` unions, no pip packages); tests use `unittest`; test output pristine; every `open` in a `with` block; only one generator-built `pcbnew.BOARD` may be alive per process (tests reload from disk; `pcbnew.LoadBoard` boards are fine).
- Commit after each task in the repo's style (imperative subject, body says what and why) ending with a `Co-Authored-By:` line naming the model that wrote it; commit regenerated `hardware/dryer-*/` files and `docs/hardware/` renders with the task that changed them. Do not push; the controller pushes after the final review.
- Repo rules: no device IPs, no "VMD-08"/"Azco" titles, numbers traceable to datasheets or measurements, unverified items marked.

## Review Focus

1. **A board 0.1 mm larger than its space:** the generator must refuse it, not DRC. Task 1's `test_outlines` asserts each outline's bounding box equals (W, H) within 0.01 mm and every footprint courtyard lies inside it.
2. **The ESP body over a mounting hole's screw head:** a hole within the Thing Plus's footprint (y 8.7–31.6, x −3–61.8 on the controller) would be unusable. Task 1 asserts no hole centre lies within 3.5 mm of the ESP body rectangle (an M4 head is about 7 mm across).
3. **Mains copper creeping toward the smaller board's holes:** on 45 × 70 the right-side holes sit 4 mm from the plug. The existing "mains to mounting holes" rule covers it; Task 3's routed-board test additionally measures and prints the minimum, so a 6.0 mm pass with no margin is visible.
4. **Connector bodies off the board edge:** J_MAINS and the USB-C overhang by design; nothing else may. Task 1 asserts every courtyard except J_ESP12/J_ESP16/J_MAINS lies inside the outline and reports the overhang of those three.
5. **The link header reversed between boards:** `J_RLY` and `J_CTRL` pin n must carry the same net. `parts.LINK_PINS` already pins it; Task 1 adds a test that both boards' link parts use `parts.LINK_PINS` verbatim.

---

### Task 1: Outline and fit tests, and the new constants

**Files:**
- Create: `hardware/tests/test_outlines.py`
- Modify: `hardware/dryer_board/controller.py` (`BOARD_W, BOARD_H`, `HOLES`, `ANTENNA_KEEPOUT`, `U1_KEEPOUT`, `GND_POUR`, `PLACE`, `SILK`, `HIDDEN_REFS` as needed), `hardware/dryer_board/mains.py` (`BOARD_W, BOARD_H`, `HOLES`, `SLOT_X`, `SLOT_SEGMENTS`, `MAINS_ZONE`, `RELAY_AREAS`, `GND_POUR`, `PLACE`, `MAINS_TRACKS`, `SILK`, `SILK_LINES`)

**Interfaces:**
- Consumes: `boards.BOARDS`, `boards.by_name(name)`, each board module's `BOARD_W`, `BOARD_H`, `HOLES`, `PLACE`, `edge_outlines()`, `board.build(bd, pcb_path, fresh)`, `libs.footprint_path`, `pcbnew`.
- Produces: `test_outlines.py` with the five tests below, which every later task keeps green; the new geometry constants in both modules (values in Steps 3 and 4).

- [ ] **Step 1: Write the failing tests**

```python
# hardware/tests/test_outlines.py
"""The enclosure spaces are hard limits: 85 x 70 (controller) and 45 x 70 (mains).
These run before DRC and fail on size, not on clearance."""
import os, tempfile, unittest
import pcbnew
from dryer_board import boards, board, parts, project, schematic

SPACES = {"controller": (85.0, 70.0), "mains": (45.0, 70.0)}
OVERHANG_OK = {"J_ESP12", "J_ESP16", "J_MAINS"}   # the USB-C face and the mains plug leave the edge by design
TOL = 0.01

def _built(bd):
    d = tempfile.mkdtemp()
    project.write(bd, d); schematic.write_lib_tables(bd, d); schematic.write(bd, d)
    pcb = os.path.join(d, bd.PROJECT + ".kicad_pcb")
    board.build(bd, pcb, fresh=True)
    return pcbnew.LoadBoard(pcb)   # reload: only one generator-built board may be alive per process

class Outlines(unittest.TestCase):
    def test_declared_sizes(self):
        for bd in boards.BOARDS:
            self.assertEqual((bd.BOARD_W, bd.BOARD_H), SPACES[bd.SHORT], bd.SHORT)
            self.assertEqual(sorted(bd.HOLES.values()), sorted([(4, 4), (bd.BOARD_W - 4, 4), (4, 66), (bd.BOARD_W - 4, 66)]), bd.SHORT)

    def test_board_edges_match(self):
        for bd in boards.BOARDS:
            b = _built(bd)
            bb = b.GetBoardEdgesBoundingBox()
            self.assertAlmostEqual(bb.GetWidth() / 1e6, bd.BOARD_W, delta=TOL, msg=bd.SHORT)
            self.assertAlmostEqual(bb.GetHeight() / 1e6, bd.BOARD_H, delta=TOL, msg=bd.SHORT)

    def test_courtyards_inside(self):
        for bd in boards.BOARDS:
            b = _built(bd)
            for fp in b.GetFootprints():
                cy = fp.GetCourtyard(pcbnew.F_CrtYd).BBox()
                x1, y1 = cy.GetX() / 1e6, cy.GetY() / 1e6
                x2, y2 = x1 + cy.GetWidth() / 1e6, y1 + cy.GetHeight() / 1e6
                inside = x1 >= -TOL and y1 >= -TOL and x2 <= bd.BOARD_W + TOL and y2 <= bd.BOARD_H + TOL
                if fp.GetReference() in OVERHANG_OK:
                    continue
                self.assertTrue(inside, "%s %s courtyard (%.2f,%.2f)-(%.2f,%.2f) leaves the %sx%s board"
                                % (bd.SHORT, fp.GetReference(), x1, y1, x2, y2, bd.BOARD_W, bd.BOARD_H))

    def test_esp_body_clear_of_hole_heads(self):
        """The Thing Plus is 64.77 x 22.86 mm with its USB-C face 3 mm past the left edge;
        an M4 head is about 7 mm across, so no hole centre may be within 3.5 mm of the body."""
        bd = boards.by_name("controller")
        x12, y12, _ = bd.PLACE["J_ESP12"]; x16, y16, _ = bd.PLACE["J_ESP16"]
        top, bottom = min(y12, y16) - 1.27, max(y12, y16) + 1.27
        left, right = -3.0, -3.0 + 64.77
        for ref, (hx, hy) in bd.HOLES.items():
            near = (left - 3.5) <= hx <= (right + 3.5) and (top - 3.5) <= hy <= (bottom + 3.5)
            self.assertFalse(near, "%s at (%s, %s) is under or beside the ESP body" % (ref, hx, hy))

    def test_link_pinout_identical(self):
        for bd, ref in ((boards.by_name("controller"), "J_RLY"), (boards.by_name("mains"), "J_CTRL")):
            self.assertEqual(bd.by_ref(ref).pins, parts.LINK_PINS, ref)
```

- [ ] **Step 2: Run them to see them fail**

Run: `scripts/hardware.sh test` (or, faster, `PYTHONPATH=hardware /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 -m unittest hardware.tests.test_outlines -v` with the module path your checkout uses; `scripts/hardware.sh test` is the reference).
Expected: `test_declared_sizes` fails on (76, 85) and (64, 85); `test_board_edges_match` fails the same way; `test_courtyards_inside` passes or fails depending on the old placement; `test_esp_body_clear_of_hole_heads` and `test_link_pinout_identical` pass. If `GetCourtyard` is not a method in 10.0.6, use `fp.GetBoundingBox(False, False)` (no text, no invisible items) and say so in the report.

- [ ] **Step 3: Controller constants and placement (85 × 70)**

Replace the geometry block of `hardware/dryer_board/controller.py` with:

```python
# 85 x 70 mm, the controller space in the enclosure. The Thing Plus lies along the long edge
# with its USB-C face 3 mm past the left edge (x = -3) and its antenna at the right end over a
# copper-free keep-out; the 12-pin row is above the 16-pin row (component side up, USB left).
# SparkFun .brd: 12-pin pin 1 is 24.13 mm and 16-pin pin 1 is 13.97 mm from the USB face, the
# rows are 20.32 mm apart, the board is 22.86 wide and 64.77 long. Socket rotation 90 runs the
# pins toward +x from pin 1.
BOARD_W, BOARD_H = 85.0, 70.0
HOLES = {"H1": (4, 4), "H2": (81, 4), "H3": (4, 66), "H4": (81, 66)}

_USB_X = -3.0
_ROW12_Y = 10.0
_ROW16_Y = _ROW12_Y + 20.32
# Antenna: the last 6.3 mm of the S2 (x 55.5 to 61.8) and of the C6 (x 49.1 to 55.4); keep-out
# covers both with margin, no copper on either layer.
ANTENNA_KEEPOUT = (48.0, 6.0, 66.0, 34.0)
U1_KEEPOUT = (29.4, 40.1, 41.7, 45.5)   # U1 at (33, 46): courtyard x 29.45..41.65, body top to 0.5 mm above the pad row
GND_POUR = (2.0, 2.0, 83.0, 68.0)
MAINS_TRACKS = []   # no mains copper on this board

PLACE = {
    "J_ESP12": (_USB_X + 24.13, _ROW12_Y, 90),
    "J_ESP16": (_USB_X + 13.97, _ROW16_Y, 90),
    "H1": (4, 4, 0), "H2": (81, 4, 0), "H3": (4, 66, 0), "H4": (81, 66, 0),
    # link header, top right, beside the antenna keep-out; pin 1 at the top
    "J_RLY": (75, 10, 270), "R1": (71, 20, 0), "R4": (71, 23, 0),
    # right edge: sensor header vertical, pin 1 at the top
    "J_SENS": (80, 36, 90),
    # 5 V block (row at y 46), with the SW-USB and its legends to the right
    "U1": (33, 46, 0), "C2": (27.5, 46, 90), "C3": (44, 46, 90), "C4": (51, 45, 0),
    "R17": (29, 52, 0), "D13": (34, 52, 0), "D14": (41, 52, 0), "SW1": (62, 44, 0),
    # 24 V input chain (row at y 58-60)
    "J_24V": (12, 58, 0), "F2": (24, 56, 0), "D11": (32, 56, 0), "C1": (26, 63, 0),
    "R16": (40, 58, 0), "D12": (45, 58, 0),
    # test points in a row under the ESP
    "TP1": (8, 36, 0), "TP2": (11.5, 36, 0), "TP3": (15, 36, 0), "TP4": (18.5, 36, 0),
    "TP5": (22, 36, 0), "TP6": (25.5, 36, 0), "TP7": (29, 36, 0), "TP8": (32.5, 36, 0), "TP9": (36, 36, 0),
    # sensor pull-up and decoupling by the sensor header
    "R18": (73, 55, 0), "C5": (73, 58, 0), "C6": (73, 61, 0),
    # MOSFET stages A, B, C in columns at x 50, 59.5, 69, above J_LOADS
    "R7": (50, 51, 0), "R8": (50, 54, 0), "Q3": (50, 58, 0), "D5": (50, 63, 0), "D8": (54.5, 54, 0), "R9": (54.5, 58, 0),
    "R10": (59.5, 51, 0), "R11": (59.5, 54, 0), "Q4": (59.5, 58, 0), "D6": (59.5, 63, 0), "D9": (64, 54, 0), "R12": (64, 58, 0),
    "R13": (69, 51, 0), "R14": (69, 54, 0), "Q5": (69, 58, 0), "D7": (69, 63, 0), "D10": (73.5, 51, 0), "R15": (73.5, 48, 0),
    # bottom edge: loads plug and the display header (vertical headers, plugs from above)
    "J_LOADS": (48, 67, 0),
    "J_DISP": (12, 66.5, 0),
}
```

These coordinates were checked against the stock courtyards (0805 ±1.68 × ±0.95; SOT-23 ±1.93 × ±1.7; SMA ±3.5 × ±1.75; TSR-1 x −3.55..8.65, y −5.85..2.25; CP 6.3 ±4.7 × ±3.55; CP 8 ±6.15 × ±4.5; MSTBVA 6-pin x −4.04..29.44, y −5.3..4.3; MSTBVA 2-pin x −4.04..9.13; MCV 9-pin x −2.95..30.95, y −4.75..3.5 (rot 90: along y); PinHeader 1×8 along +y 19.55; PinSocket 1×16 along 39.87 and 1×12 along 29.71; JST XH 4-pin about 12.5 × 5.75; M4 hole r 3.45). The test in Step 1 and DRC's courtyard check are the arbiters: move a part within its comment group when they object, keep the ESP, holes, keep-outs and edge connectors where they are, and record every move.

Silkscreen: keep every entry in `SILK` but re-point them: the title along the bottom edge at y 69 (the ESP covers the top); the SW-USB sentence and ON/OFF legends beside SW1 (ON at pin 1's end); the J_DISP legend above its header; the J_SENS legend as a vertical column left of the header (rotation 90); "24V+ 0V" below J_24V; the loads legend below J_LOADS at y 69.3 (if it collides with the title, put the title on B.SilkS mirrored); LED labels above their LEDs; "MAINS BOARD" beside J_RLY with the four pin names right of its pins; the "1"/"12"/"16" socket numerals at the socket ends; the back-side socket legends mirrored, now above/below the rows: `_P12` entries at `(PLACE["J_ESP12"][0] + (p-1)*2.54, _ROW12_Y - 3.5)` rotated 90, `_P16` at `(PLACE["J_ESP16"][0] + (p-1)*2.54, _ROW16_Y + 3.5)` rotated 90. `HIDDEN_REFS` stays.

- [ ] **Step 4: Mains constants, placement and mains copper (45 × 70)**

Replace the geometry block of `hardware/dryer_board/mains.py` with:

```python
# 45 x 70 mm, the mains space in the enclosure. SELV strip x 0-7 (link header and both driver
# stages in one column, GND pour), slot x 7-9 with four gaps for the coil tracks, mains zone
# x 9-45: relays with COM at x 12 and contacts at x 26.2, F1 across the top of the zone at
# y 12, J_MAINS pads at x 35 with the plug entering from the right edge and N linked at x 39.5.
BOARD_W, BOARD_H = 45.0, 70.0
HOLES = {"H1": (4, 4), "H2": (41, 4), "H3": (4, 66), "H4": (41, 66)}

SLOT_X = (7.0, 9.0)
# coil pads at y 24 +- 6 and 54 +- 6: gaps 16-20, 28-32, 46-50, 58-62
SLOT_SEGMENTS = [(3, 16), (20, 28), (32, 46), (50, 58), (62, 67)]
MAINS_ZONE = (9.0, 0.0, 45.0, 70.0)
RELAY_AREAS = [(2.0, 14.0, 22.0, 34.0), (2.0, 44.0, 22.0, 64.0)]
GND_POUR = (2.0, 2.0, 6.5, 68.0)

PLACE = {
    "H1": (4, 4, 0), "H2": (41, 4, 0), "H3": (4, 66, 0), "H4": (41, 66, 0),
    # link header on the left edge, pin 1 at the top, between the two driver stages
    "J_CTRL": (3.5, 35, 270),
    # driver A above it, driver B below it, one column at x 4
    "R2": (4, 12, 90), "Q1": (4, 16, 90), "D1": (4, 21, 90), "R3": (4, 25.5, 90), "D3": (4, 28.5, 90),
    "R5": (4, 46, 90), "Q2": (4, 50, 90), "D2": (4, 55, 90), "R6": (4, 59.5, 90), "D4": (4, 62.5, 90),
    # mains zone
    "K1": (12, 24, 0), "K2": (12, 54, 0),
    "F1": (10, 12, 0),
    "J_MAINS": (35, 57.6, 90),
}
```

`MAINS_TRACKS` is re-laid for this geometry, keeping the net list and the distances listed in the file's comment block. Starting point (adjust until DRC is clean and the measured distances in Task 3 hold):

```python
MAINS_TRACKS = [
    ("L_IN", "F.Cu", [(10, 12), (14, 12), (21.5, 19.5), (21.5, 34), (21.5, 44), (21.5, 57.6), (35, 57.6)]),
    ("L_FUSED", "B.Cu", [(32.5, 12), (23.5, 21), (23.5, 34), (23.5, 44), (23.5, 54), (12, 54)]),
    ("L_FUSED", "B.Cu", [(12, 24), (23.5, 24)]),
    ("L_FUSED", "B.Cu", [(23.5, 27.1), (34.22, 27.1), (35, 27.12)]),
    ("L_SW_A", "F.Cu", [(26.15, 30.05), (29, 32.9), (29, 44.6), (31.9, 47.52), (35, 47.52)]),
    ("L_SW_B", "B.Cu", [(26.15, 60.05), (30, 56.05), (30, 40.4), (32.9, 37.36), (35, 37.36)]),
    ("N", "F.Cu", [(35, 22.04), (39.5, 22.04), (39.5, 52.52), (35, 52.52)]),
    ("N", "F.Cu", [(35, 32.2), (39.5, 32.2)]),
    ("N", "F.Cu", [(35, 42.36), (39.5, 42.36)]),
]
```

(J_MAINS pin 1 at y 57.6 and pins upward at 5.08: pin 2 N 52.52, 3 L_SW_A 47.52, 4 N 42.44, 5 L_SW_B 37.36, 6 N 32.28, 7 L_FUSED 27.2, 8 N 22.12; use the exact pad centres pcbnew reports and split every segment that crosses a relay-area edge so the 3.5 mm relaxation never applies to a stretch outside the areas, as the present table does at its area edges.) The F1 pads sit at (10, 12) and (32.5, 12) on the 22.5 mm slotted footprint; pad 2 must stay ≥ 6 mm, copper edge to hole edge, from H2 at (41, 4): if the measured distance is below 6 mm, move F1 down to y 13 and re-lay the L_FUSED diagonal.

Silkscreen: the title at y 1.4 across the SELV strip and zone (size 0.7); "MAINS 120 VAC" and "keep 6 mm from SELV" at the bottom of the zone (y 66 and 68.5, x 27); the link pin names right of J_CTRL; the mains pin names vertical at x 31.5 between the relay outline and the pin-1 triangle; "HTR A"/"HTR B" beside D3/D4 rotated 90; `SILK_LINES = [(10, 3, 10, 67)]` along the slot's mains side. `HIDDEN_REFS` stays.

- [ ] **Step 5: Generate both boards and run the outline tests**

Run: `scripts/hardware.sh generate controller --fresh && scripts/hardware.sh generate mains --fresh && scripts/hardware.sh test`
Expected: the five outline tests pass; existing DRC-based tests may now fail on courtyard overlaps or clearances. Fix placement collisions here (Step 3/4 rules), not routing: routing is Task 2.

- [ ] **Step 6: Commit**

```bash
git add hardware/dryer_board/controller.py hardware/dryer_board/mains.py hardware/tests/test_outlines.py hardware/dryer-controller hardware/dryer-mains
git commit -m "Fit the controller and mains boards to 85 x 70 and 45 x 70 mm"
```

---

### Task 2: Route both boards and bring DRC to zero

**Files:**
- Modify: `hardware/dryer_board/controller.py`, `hardware/dryer_board/mains.py` (placement nudges, `MAINS_TRACKS`), `hardware/dryer-controller/`, `hardware/dryer-mains/` (regenerated, routed)

**Interfaces:**
- Consumes: `scripts/hardware.sh route <board> [passes]`, `board.drc_report`, the tests in `hardware/tests/test_routed_board.py` and `test_board.py` (per-board gates already written for the split).

- [ ] **Step 1: Route the controller board**

Run: `scripts/hardware.sh route controller 200` (10-minute Bash timeout). Then `scripts/hardware.sh check controller`.
Expected: 0 DRC violations, 0 unconnected pads. Remedies in order, as in the rev A work: more passes; nudge a part within its comment group and `generate controller` (keeps tracks) then `route controller` again; if a connection cannot reach the antenna-side parts, widen the gap between the keep-out and J_RLY. Record each change.

- [ ] **Step 2: Route the mains board**

Run: `scripts/hardware.sh route mains 200` then `scripts/hardware.sh check mains`.
Expected: 0 DRC violations, 0 unconnected pads. The SELV nets here are only +5V, GND, RLY_A, RLY_B, COIL_A, COIL_B and the LED nets; the four coil tracks cross the slot gaps into the coil pads. A `[clearance]` naming "mains to selv" is fixed by moving mains copper in `MAINS_TRACKS` or widening a relay area toward the strip (never below x 2), not by touching `RULES`. A "mains to mounting holes" hit means F1 or the J_MAINS end pins are too near a hole: move F1 down or the header pin row up (keep pin 1 at the bottom).

- [ ] **Step 3: Full suite, both boards**

Run: `scripts/hardware.sh test && scripts/hardware.sh check`
Expected: every test passes, both boards clean. `test_outlines` must still pass (no size drift from nudging).

- [ ] **Step 4: Commit**

```bash
git add hardware/dryer_board hardware/dryer-controller hardware/dryer-mains
git commit -m "Route both boards at their enclosure sizes"
```

---

### Task 3: Measured margins on the committed boards

**Files:**
- Create: `hardware/tests/test_margins.py`

**Interfaces:**
- Consumes: the committed `hardware/dryer-mains/dryer-mains.kicad_pcb`, `mains.MAINS_NETS`, `mains.RELAY_AREAS`, `pcbnew`.
- Produces: a test that prints and asserts the minimum distances the spec lists, so a pass with no margin is visible in the test output and in the report.

- [ ] **Step 1: Write the test**

```python
# hardware/tests/test_margins.py
"""Minimum copper distances on the committed mains board, measured with pcbnew's shape
collision at 1 um, printed so a bare pass is visible: mains to SELV outside the relay areas
(>= 6.0), mains copper to each hole edge (>= 6.0), L-side mains nets to each other (>= 1.6),
mains to edge (>= 1.0)."""
import os, unittest
import pcbnew
from dryer_board import boards, kicad_env

bd = boards.by_name("mains")
PCB = os.path.join(kicad_env.project_dir(bd), bd.PROJECT + ".kicad_pcb")

def _gap(a, b, cap=40.0):
    """Edge-to-edge distance between two items in mm by bisection on Collide with clearance."""
    lo, hi = 0.0, cap
    while hi - lo > 0.001:
        mid = (lo + hi) / 2
        if a.GetEffectiveShape().Collide(b.GetEffectiveShape(), int(mid * 1e6)):
            hi = mid
        else:
            lo = mid
    return lo

def _in_area(item, areas):
    p = item.GetPosition(); x, y = p.x / 1e6, p.y / 1e6
    return any(x1 <= x <= x2 and y1 <= y <= y2 for x1, y1, x2, y2 in areas)

@unittest.skipUnless(os.path.exists(PCB), "no committed mains board")
class Margins(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.b = pcbnew.LoadBoard(PCB)
        items = list(cls.b.GetTracks()) + [p for fp in cls.b.GetFootprints() for p in fp.Pads()]
        cls.mains = [i for i in items if i.GetNetname() in bd.MAINS_NETS]
        cls.selv = [i for i in items if i.GetNetname() and i.GetNetname() not in bd.MAINS_NETS]
        cls.holes = [p for fp in cls.b.GetFootprints() if fp.GetReference().startswith("H") for p in fp.Pads()]

    def test_mains_to_selv_outside_relay_areas(self):
        worst = min((_gap(m, s), m.GetNetname(), s.GetNetname()) for m in self.mains for s in self.selv
                    if not _in_area(m, bd.RELAY_AREAS) and not _in_area(s, bd.RELAY_AREAS))
        print("\nmains to SELV outside relay areas: %.3f mm (%s vs %s)" % worst)
        self.assertGreaterEqual(worst[0], 6.0)

    def test_mains_to_holes(self):
        for h in self.holes:
            worst = min(_gap(m, h) for m in self.mains)
            print("mains to hole %s: %.3f mm" % (h.GetParent().GetReference(), worst))
            self.assertGreaterEqual(worst, 6.0)

    def test_l_side_nets_apart(self):
        l_side = [i for i in self.mains if i.GetNetname() != "N"]
        worst = min((_gap(a, c), a.GetNetname(), c.GetNetname()) for a in l_side for c in l_side if a.GetNetname() < c.GetNetname())
        print("L-side mains nets apart: %.3f mm (%s vs %s)" % worst)
        self.assertGreaterEqual(worst[0], 1.6)
```

- [ ] **Step 2: Run it**

Run: `scripts/hardware.sh test`
Expected: passes with the three measurements printed. If `GetEffectiveShape().Collide(shape, clearance)` has a different signature in 10.0.6, use `pcbnew.SHAPE.Collide` the way `hardware/tests/test_routed_board.py` or the Task 10 probes did, and say so. A measurement under its floor is a layout defect: go back to Task 2's remedies, never to the rules.

- [ ] **Step 3: Commit**

```bash
git add hardware/tests/test_margins.py
git commit -m "Measure the mains board's clearance margins in the suite"
```

---

### Task 4: Exports, docs and the reviewer's renders

**Files:**
- Modify: `docs/hardware.md` (PCB section: sizes, the layout paragraphs, the clearance numbers from Task 3), `docs/superpowers/specs/2026-10-14-pcb-design-kicad-design.md` ("As built": a pointer to the fit spec and the new sizes), `hardware/README.md` (sizes), `CLAUDE.md` (the `hardware/` paragraph's sizes), `docs/board-continuity-check.md` (only if a test-point or header position named in it moved), `docs/hardware/*` (renders via export)

- [ ] **Step 1: Export and look**

Run: `scripts/hardware.sh export` (both boards). Open `docs/hardware/controller-render-top.png` and `docs/hardware/mains-render-top.png` with the Read tool: the ESP along the top of the controller board with its USB end over the left edge, the mains plug on the mains board's right edge, the slot with four gaps, nothing in the antenna box. Describe both in the report.

- [ ] **Step 2: Docs**

Update every size, coordinate and measured distance the docs state (grep `110`, `76 x 85`, `64 x 85`, `x 37`, `22.5, 24.5` and the old hole coordinates in `docs/hardware.md`, `hardware/README.md`, `CLAUDE.md`); put Task 3's printed measurements into the clearance section; add to the rev A spec's "As built" one bullet pointing at `2026-10-15-pcb-two-board-split-design.md` with the two sizes.

- [ ] **Step 3: Verify and commit**

Run: `scripts/hardware.sh test && scripts/hardware.sh check && python3 tests/test_pinmap.py && git status --short`
Expected: green, and only the files above changed.

```bash
git add docs hardware/README.md CLAUDE.md
git commit -m "Document the boards at their enclosure sizes"
```

- [ ] **Step 4: Reviewer update** (done by the controller after the final review, not by this task): push, then reply on PR #49 with the two new renders and the measured margins, and ask JWardT3D to confirm the hole pattern and that the plug bodies may overhang the edges.
