# Fitting the two controller boards to the enclosure spaces

**Goal.** Re-lay the two boards of PR #49, `dryer-controller` and
`dryer-mains`, so they fit the dryer's enclosure spaces: the controller
board 85 × 70 mm, the mains board 45 × 70 mm. Every circuit, part, rule and
tool of the current branch stays as it is; only the outlines, the
placements and the hand-placed mains copper change.

**What was asked, and what is assumed.** The hardware reviewer on PR #49
(2026-10-14/15) asked for a separate mains board with header connectors,
the SHT45 connection made explicit, fit for a TSR 1-2450-compatible 5 V
module and the fuse holders on hand, 4 mm mounting hardware, and advice on
PCBWay. Commit `63e7ad3` (another session, 2026-10-15) did all of that:
the split into `dryer-controller` (76 × 85 mm) and `dryer-mains`
(64 × 85 mm) linked by a keyed JST-XH 4-way cable (`J_RLY` on the
controller, `J_CTRL` on the mains board; 5 V, GND, `RLY_A`, `RLY_B`), 4.3 mm
M4 holes, F1 on a 22.5 mm slotted footprint for the BLX-A holders on hand,
U1 as the Amazon TSR 1-2450 with a pin-order bench check, the SHT45
documented on the Thing Plus's Qwiic jack, and a PCBWay note. The reviewer
then gave the sizes of his two spaces, 85 × 70 mm and 45 × 70 mm, which
neither board meets. Decided with the owner (2026-10-15): fit the boards
to those spaces rather than put one board in an external box. Assumed:
both spaces are flat rectangles with the 70 mm sides parallel and cables
free to leave any edge; the corner-hole pattern (4 mm in from each edge)
stands until the reviewer gives another; the on-hand fuse holder's pin
pitch (21.5 to 23.5 mm, slotted) and the TSR clone's pin order are
confirmed at first article as commit `63e7ad3` arranged.

Nothing here has been laid out yet. The two outlines are hard limits and
the first thing the generator asserts.

## Decisions

| Decision | Choice | Why |
|---|---|---|
| Outlines | `dryer-controller` 85 × 70 mm; `dryer-mains` 45 × 70 mm | The enclosure spaces |
| Names, nets, link | Unchanged from `63e7ad3`: `J_RLY`/`J_CTRL`, nets `RLY_A`/`RLY_B`, revision A on both boards | Nothing fabricated yet; no churn in docs and tests |
| Controller orientation | The Thing Plus lies along the long edge, USB-C face 3 mm past the left edge (x = −3), 12-pin row above the 16-pin row, antenna at the right end over a copper-free keep-out | 64.77 mm of ESP does not fit a 70 mm side with the overhang and the holes; it fits the 85 mm side |
| Controller edges | Bottom edge: J_LOADS, J_24V, J_DISP (vertical headers, plugs from above); right edge: J_SENS vertical along y, J_RLY at the top right beside the antenna keep-out; left edge: the USB-C overhang only | 85 mm of bottom edge takes the three; the 70 mm right edge takes the 31 mm sensor header; the keyed link sits nearest the mains board |
| Mains board | SELV strip x 0–7 (J_CTRL and the two driver stages in one column), slot x 7–9, mains zone x 9–45: relays with COM at x 12 and contacts toward the plug, J_MAINS pads at x 35 with the plug entering from the right, F1 across the top of the mains zone at y ≈ 12 with its pads kept 6 mm from the top holes | The relays and plug need about 36 mm; the fuse only fits horizontally; the hole rule fixes its height |
| Rules | The seven mains rules, the 6 mm hole rule, the antenna and U1 keep-outs are unchanged; mains copper stays hand-placed in `mains.MAINS_TRACKS` | The safety design is rev A's |
| Gate | New tests assert each board's outline is exactly its space, every courtyard lies inside its outline, and the holes sit 4 mm from the edges, before DRC runs | A board that passes DRC but is 1 mm too wide is useless |

## Controller board, 85 × 70 mm

Holes at (4, 4), (81, 4), (4, 66), (81, 66), 4.3 mm. ESP socket rows with
pin 1 at the USB end: 12-pin pin 1 at (21.13, 10), 16-pin pin 1 at
(10.97, 30.32), both rotated so the pins run toward +x (SparkFun: 12-pin
pin 1 is 24.13 mm and 16-pin pin 1 is 13.97 mm from the USB face; the rows
are 20.32 mm apart; the Thing Plus is 22.86 mm wide, so its body spans
y 8.7 to 31.6 and clears the top holes' M4 heads). Antenna keep-out
(54, 6)–(66, 34), no copper on either layer. Everything else lives in
y 34–70 and in x 66–85 above that: the 5 V module with its U1 keep-out,
SW-USB and its legend, the 24 V input chain, the three MOSFET stages, the
test points and LEDs, with the GND pour over the whole board outside the
keep-outs. The silkscreen keeps every label and the back-side socket
legends, repositioned.

## Mains board, 45 × 70 mm

Holes at (4, 4), (41, 4), (4, 66), (41, 66). SELV strip x 0–7 with the
GND pour, J_CTRL vertical near the middle of the left edge, driver A above
it and driver B below it in a single column. Slot x 7–9 in segments with
gaps for the four coil tracks. Mains zone x 9–45: K1 with COM at (12, 24),
K2 at (12, 54), contacts at x 26.2; F1 across the top at y 12 with pads at
x ≈ 10 and 32.5 (both ≥ 6 mm, copper edge to hole edge, from the top
holes); J_MAINS pads at x 35, pin 1 at the bottom, pins from y ≈ 57.6
upward to 22; N linked on the right of the header at x ≈ 39.5. Relay
areas (3.5 mm rule) around each relay's pads; mains copper re-laid in
`MAINS_TRACKS` holding every distance the present table's comment block
lists (6 mm to SELV outside the areas, 3.5 inside, 1.6 mm L to L, 1 mm
in-class, 1 mm to the edge, 6 mm to the holes).

## As built (2026-10-15)

Where the boards differ from the layout above, each with its reason.
Figures are from the `PLACE`, `HOLES`, `RELAY_AREAS` and `GND_POUR`
tables and the comments in `hardware/dryer_board/mains.py`.

- **K1 COM at (12, 29) and K2 COM at (12, 51.5)**, not y 24 and 54, so the
  coil corridors clear F1 and H3.
- **F1 at (12.4, 14), pads at x 12.4 and 34.9**, not x 10 and 32.5 at
  y 12: its courtyard must end left of J_MAINS's, and its pad 2 keeps
  7.76 mm from H2's hole edge.
- **J_MAINS at (39.5, 53.5), rotated 90°, pads at x 39.5**, not x 35; the
  N links run at x 43.15. The housing overhangs the right edge by 5.05 mm
  (bounded at 5.1 mm by `test_outlines`); open with the reviewer.
- **J_CTRL at (3.95, 33), pins y 33 to 40.5, held to the plain 6 mm from
  the COM pads (6.32 mm measured) rather than the relay-area 3.5 mm**, with the driver parts
  in two columns (x 2 and x 5.4), not one.
- **Antenna keep-out from x 50.5** (to 66, y 6 to 34), not from 54.
- **Relay areas** (2, 19) to (22, 39) and (2, 41.5) to (22, 61.5).
- **GND pour outline from y 21** on the mains board, (2, 21) to (6.5, 68).
- **A rules-aware refill** joined the pipeline (`board.refill_with_rules`),
  and two test files, `test_outlines.py` and `test_margins.py`, hold the
  outlines, overhangs and clearance margins.
- **L to N is 1.10 mm**, down from 1.55 mm on the single board.
- **Parked rule gap**: the DRC rules hold the netless relay NC pads to
  SELV at 6 mm but to L-side mains copper only at the 1.0 mm netclass
  clearance; `test_margins.py` holds them at 1.6 mm. A rev B rule, NC to
  L-side 1.6 mm, is the fix.

## Not in this work

Any part, value or net change; the link pinout; moving the SHT45; the
enclosure.

## Unverified — confirm, do not assume

- That both outlines hold their parts with the rev A clearances; the
  tests and DRC decide, and a board that will not route at these sizes is
  reported, not forced.
- The reviewer's hole pattern (corners assumed) and whether the spaces
  allow the connector bodies to overhang the board edge (J_MAINS and the
  USB-C do).
- The on-hand fuse holder's pin pitch and the TSR clone's pin order
  (first-article checks exist).
