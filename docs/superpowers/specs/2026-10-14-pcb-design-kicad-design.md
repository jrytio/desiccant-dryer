# Printed circuit board for the dryer controller

**Goal.** Replace the two hand-wired 7 × 9 cm protoboards (logic + 24 V
board, mains relay board, JST-XH harness) with one fabricated and
fab-assembled PCB that carries the same circuit, takes the same socketed
SparkFun Thing Plus (ESP32-S2 or ESP32-C6) in the same header positions,
and needs no hand soldering beyond seating the ESP. The design is
generated from code in this repository with KiCad 10, checked by ERC and
DRC in CI, and exported to fab files by script.

**What was asked, and what is assumed.** Asked (2026-10-14): a PCB that
mimics the current board so units can be produced faster and more
reliably, designed in KiCad because it can be driven from the command
line and from Python. The owner's framing: only two to five boards, built
to make up for a lack of time and soldering skill, so worry about time and
reliability, not volume; anything the factory fits is more reliable than a
hand-soldered joint. Assumed: no firmware change and no pin-map change; the
power supply, display, SHT45, DS18B20 probes, valves, fan, heaters and
thermal fuses stay off the board as they are now; the mains scheme stays as
on the protoboard (L switched by relay, N passed through, one fuse covers
the heaters and the supply, protective earth bonded off the board).

Nothing in this document has been fabricated. Every part named as a
candidate is checked against the fab's catalogue during planning, and the
numbers that need a bench are listed under
[Unverified](#unverified--confirm-do-not-assume).

## Decisions made in the design conversation (2026-10-14)

| Decision | Choice | Why |
|---|---|---|
| Topology | One board, mains zone and SELV zone separated by a routed slot and a DRC-enforced clearance | The two-board split only existed to get creepage on protoboard; a PCB solves that directly, drops the harness (a failure point) and halves the terminals |
| ESP | Socketed Thing Plus, female headers at SparkFun's geometry | Keeps both firmware images, the board packages, the pin-map docs and the swap-a-board repair path |
| Assembly | JLCPCB fabrication and assembly, SMD and through-hole, all parts top side; every part chosen from the LCSC catalogue | Zero hand soldering. Any part the catalogue lacks falls back to hand-fit, listed as such in the BOM |
| 5 V | Fixed 5 V switching module in a 78xx three-pin footprint (candidate MornSun K7805-1000R3) | No trimmer to set; retires the G-15 preset check |
| Scope beyond mimicking | 24 V input protection, seven status LEDs, a slide switch in place of the JP-USB shunt. Not the 24 V rail monitor | The three are cheap, fab-fitted and remove a bring-up or safety step; the monitor needs firmware and has no ADC-capable header position that is clean on both chips |
| Outline | Sized to the parts, about 100 × 80 mm, M3 corner holes | No enclosure constraint was given |
| Field wiring | Pluggable keyed headers, one per function group | The loom unplugs for a board swap; no plug fits another header (G-09) |
| Authoring | Generated from code; the generator owns everything but track geometry | Every change is a reviewable diff and nothing depends on GUI time |
| Routing | Freerouting 2.5.0 headless in Docker (`ghcr.io/freerouting/freerouting:2.5.0`), local only | No Java on the Mac (owner's requirement); Docker is already used for ESPHome. The committed board is a normal KiCad board, so a GUI tidy-up stays available |
| Licence | AGPL-3.0, the repository's licence, for `hardware/` too | One licence to maintain; the socket footprint derived from SparkFun's CC BY-SA 4.0 board file keeps its attribution note as `docs/datasheets/mcu/` does |

## The circuit

Same nets as the protoboard net lists in `docs/hardware.md` unless a row
below says otherwise. Component values that the protoboard settled (1 kΩ
base series and 1 kΩ base pulldown, 100 Ω gate and 10 kΩ gate pulldown,
5.1 kΩ 1-wire pullup) are kept with their recorded reasoning.

| Block | Design | Change from the protoboard |
|---|---|---|
| ESP sockets | 16-pin and 12-pin 2.54 mm female headers at the positions read from SparkFun's `.brd` (rows 20.32 mm apart, 16-pin pin 1 at 13.97 mm and 12-pin pin 1 at 24.13 mm from the USB end). The USB-C end overhangs the board edge so an S2 can be flashed seated; the antenna end sits over a copper-free zone. Unused positions get a pad and no copper. 12-pin 9 and 10 and 16-pin 15 and 16 stay free (C6 straps, UART0 TX, RGB data). Qwiic stays on the ESP | Same |
| 24 V in | 2-pin 5.08 mm pluggable header → PPTC 1.1 A hold, rated 30 V or more → series Schottky SS34 (reverse polarity) → 100 µF / 50 V bulk → green "24 V" LED through 10 kΩ | New (F-03, G-11). The loads see about 23.6 V, inside the valves' tolerance |
| 5 V | Fixed 5 V module, 78xx pinout, input and output capacitors per its datasheet, 100 µF / 16 V bulk for the relay coils, green "5 V" LED through 2.2 kΩ | Replaces the MP1584 module and the trim step |
| USB pin feed | 5 V → Schottky (SS34) → SPDT slide switch SW-USB (one side used) → ESP 12-pin 3 | The switch replaces the JP-USB shunt. Same rule: off before any USB-C cable; printed beside the switch. The Schottky keeps its protoboard role of blocking a host from back-feeding the 5 V bus |
| Relay stages ×2 | MMBT2222A (SOT-23), 1 kΩ base series, 1 kΩ base pulldown, SMD flyback S1M across the coil (cathode to 5 V), Songle SRD-05VDC-SL-C (LCSC C35449). NO contact switches L; NC pin gets a pad and no copper. Red LED from 5 V through 2.2 kΩ to the collector lights when the stage is driven | Harness gone; both resistors on one board |
| MOSFET stages ×3 | SOT-23 logic-level N-MOSFET rated 60 V (candidate SI2308; fully enhanced at 3.3 V, unlike the IRLZ44N), 100 Ω gate series, 10 kΩ gate pulldown, S1M flyback across the load (cathode to 24 V), yellow LED from 24 V through 10 kΩ to the drain lights when the stage is driven | SMD part; same values |
| Mains | F1 T 3.15 A 5 × 20 in a covered through-hole holder, in L between the inlet pin and both relay COM pins and the PSU feed; N straight through, never switched or fused. One 8-pin 5.08 mm pluggable header rated 300 V: 1 L in, 2 N in, 3 heater A switched L, 4 heater A N, 5 heater B switched L, 6 heater B N, 7 PSU L (fused), 8 PSU N | One plug instead of four blocks |
| 24 V loads | One 6-pin 5.08 mm pluggable header: valve A 24+ / SW, valve B 24+ / SW, fan 24+ / SW | Pluggable |
| Sensors | One 9-pin 3.5 mm pluggable header: three 3V3 / DQ / GND triples; 5.1 kΩ DQ pullup to 3V3; 10 µF and 100 nF on 3V3 at the header | Pluggable |
| Display | 8-pin 2.54 mm pin header, order GND 3V3 SCL SDA RES DC CS BLK | Same |
| Keying | Mains 8-pin 5.08, loads 6-pin 5.08, 24 V in 2-pin 5.08, sensors 9-pin 3.5, display 8-pin 2.54: every plug has a unique pitch and pin count | New (G-09) |
| Test points | GND, 3V3, 5 V, 24 V, and the five output drive nets at the ESP side of their series resistors | New |
| Protective earth | Not on the board; the star point stays in the enclosure | Same |

The schematic is one generated sheet: a block per row of the table, stock
KiCad symbols, every pin joined by net labels, power symbols for GND, 3V3,
5V and 24V, no-connect markers on every unused socket position and on the
relay NC pins, and `PWR_FLAG` where ERC needs one. It is a readable
record of the netlist, not a hand-drawn sheet.

## Board layout and clearance

**Stackup and fab.** Two layers, 1.6 mm FR-4, 1 oz copper, lead-free HASL,
all parts on the top side so the fab assembles SMD and through-hole in one
pass. Four 3.2 mm non-plated M3 holes in the corners, each at least 6 mm
from mains copper. Outline about 100 × 80 mm; the generator sets it.

**Three zones, left to right.**

1. **Sensor and display edge.** The 9-pin sensor header and the 8-pin
   display header on the edge that faces the enclosure front, beside the
   ESP's 16-pin side where those signals originate.
2. **ESP and 24 V.** The ESP with its USB-C overhanging the board edge and
   its antenna over a copper-free zone, as in the protoboard drawing. Below
   it the 24 V input and protection, the 5 V module, the three MOSFET
   stages and the 6-pin load header.
3. **Mains zone** along the far short edge: the 8-pin mains header on the
   edge, F1, and the two relays straddling the boundary with COM, NO and NC
   inside the zone and the coil pins outside. A 2 mm routed slot runs the
   length of the boundary except under each relay body. Under a relay the
   Songle pin pattern fixes the COM-to-coil pad gap at about 3.8 mm
   (6.3 mm centre to centre, 1.3 mm holes with their annular rings), which
   exceeds reinforced creepage at 120 V for pollution degree 2 and is the
   gap every Songle relay module has.

**Copper rules**, in a committed `.kicad_dru` so DRC fails in CI when they
are broken:

- `MAINS` netclass (L in, fused L, N, switched L A and B): 1.5 mm tracks,
  no pours, 1.0 mm clearance within the class.
- `MAINS` to any other net: 6 mm clearance everywhere, relaxed to 3.5 mm
  only inside a named rule area drawn around each relay's pads.
- Copper to board edge and to the slot: 0.5 mm; mains copper to edge 1 mm.
- `P24` (24 V, the three SW nets) and `P5` classes: 0.8 mm tracks.
- Everything else: 0.3 mm tracks, 0.2 mm clearance, 0.6 / 0.3 mm vias.
- GND pour on both layers in the SELV area only, stitched; none under the
  antenna zone, none in the mains zone.

**Silkscreen.** Hatched "MAINS 120 VAC" band over the mains zone, every
header pin labelled by function, socket positions numbered 1 to 16 and 1
to 12 with the function at each used position (no GPIO numbers, they
differ per chip), "SW-USB OFF before USB-C" beside the switch, the board
name "ESP32 desiccant dryer controller", the revision, the licence and the
repository URL.

## Tooling

**Where it lives.** A new top-level `hardware/` directory:

- `hardware/dryer_board/`: a Python package that runs under KiCad's bundled
  Python (3.9 in KiCad 10.0.6; the official `kicad/kicad:10.0` image in CI)
  with no pip dependencies.
  - `circuit.py`: the single table of parts (reference, value, symbol,
    footprint, LCSC number, hand-fit flag) and pin-to-net assignments, plus
    the board revision. The netlist, BOM and position file derive from it.
  - `pinmap.py`: header position to function.
  - `schematic.py`: writes the `.kicad_sch`.
  - `board.py`: builds the `.kicad_pcb` through `pcbnew`: outline, slot,
    holes, keep-outs, rule areas, pours, footprints, placement table,
    netclasses; exports the Specctra DSN.
  - `route.py`: runs Freerouting in Docker on the DSN and imports the SES.
  - a `.kicad_jobset` that runs ERC, DRC, gerbers, drill, position file,
    BOM, schematic PDF, top-view SVG and two rendered PNGs.
- `hardware/dryer-controller/`: the committed, generated KiCad project:
  `.kicad_pro`, `.kicad_sch`, `.kicad_pcb`, `.kicad_dru`, library tables,
  and a local library for any symbol or footprint the stock libraries lack.
  These open normally in the KiCad GUI.
- `scripts/hardware.sh` with `generate`, `route`, `check` and `export`
  subcommands, finding `kicad-cli` and KiCad's Python in the app bundle on
  macOS or on the path in the CI image. Fab outputs go to a gitignored
  `hardware/out/`.

**Stock libraries used.** `Relay_THT:Relay_SPDT_SANYOU_SRD_Series_Form_C`
and `Relay:SANYOU_SRD_Form_C` (the Songle SRD pattern; the generator
asserts its pad positions against the Songle numbers recorded in
`docs/hardware.md`), `Converter_DCDC` TRACO TSR-1 (the K78 module is
pin-compatible), `Fuse` 5 × 20 covered holders, `TerminalBlock_Phoenix`
for the pluggable headers, `Connector_PinSocket_2.54mm`,
`Connector_PinHeader_2.54mm`, `Package_TO_SOT_SMD`, `Diode_SMD`,
`LED_SMD`, `Resistor_SMD`, `Capacitor_SMD`, `TestPoint`, `MountingHole`.
Exact footprint names and LCSC numbers are pinned in the implementation
plan.

**Who owns what.** The generator owns everything except track geometry.
`board.py` updates a committed board in place the way KiCad's
update-from-schematic does: footprints, nets, rules, outline and rule
areas follow the model; tracks on unchanged nets survive; tracks on nets
whose connectivity changed are dropped. `--fresh` discards all tracks.
Generated files are deterministic (UUIDs derived from reference and pin
names, sorted output) so a PR diff is readable.

**Routing** is not deterministic, so CI never routes. `scripts/hardware.sh
route` runs locally, and the routed board is committed. The DSN carries
the netclass widths and clearances and the slot; DRC afterwards is the
backstop for anything the router ignored.

## CI and release flow

- A new `.github/workflows/hardware.yml`, triggered by changes under
  `hardware/` and by tags `pcb-*`, in the `kicad/kicad:10.0` image:
  regenerate, assert the committed schematic and board match the model
  (footprints, nets, rules; not tracks), ERC and DRC with
  `--exit-code-violations`, export, upload `hardware/out/` as a workflow
  artifact. On a `pcb-*` tag it also creates a GitHub Release with the fab
  zip attached, so the files sent to the fab are recoverable.
- `build.yml` adds `hardware/**` to its `paths-ignore` so a board change
  does not rebuild firmware. The pin-map test below runs in both
  workflows.
- `circuit.py` holds the revision (rev A, B, ...); it feeds the silkscreen,
  the title block and the fab zip name.
- Ordering: upload the gerber zip, the BOM CSV and the position CSV to
  JLCPCB. Minimum order is five bare boards; the Songle relay is an
  "extended" part with a small per-part loading fee.

## Pin-map guard

`tests/test_pinmap.py` holds the position-to-GPIO tables for both boards
(from `docs/pinout-verification.md`) and the position-to-function table
from `hardware/dryer_board/pinmap.py`, and asserts that each `pin_*`
substitution in `esphome/packages/board-s2.yaml` and `board-c6.yaml` names
the GPIO at the position carrying that function. It runs in the
`lint-config` job and in `hardware.yml`. Hardware and firmware cannot
drift; a pin change is a change to `pinmap.py`, both board packages, the
T-J12 cases and `docs/pinout-verification.md` together.

## Verification

**On every PR, in CI.**

- Generator-to-board sync, ERC clean, DRC clean including the custom rules.
- One deliberately bad board (a mains track 4 mm from a logic track,
  built by the test from the same generator) must fail DRC. This proves
  the rules file is loaded, the red-case idea from `tests/cases`.
- The pin-map test.
- Footprint assertions against the pin geometry recorded in
  `docs/hardware.md` for the Songle relay, and against the module
  datasheet for the 5 V regulator.

**Before ordering a revision, by hand.**

- Review the renders in `docs/hardware/` (schematic PDF, top-view SVG, two
  PNGs), regenerated by `scripts/hardware.sh export` the way
  `scripts/scenario-shots.sh` keeps `docs/display/` current.
- Print the top-view SVG 1:1 and lay the real relay, plugs and a Thing
  Plus on it, as the repo already does for `docs/board-layout.svg`.
- Run JLCPCB's DFM check on the gerbers.
- Confirm every LCSC number in the BOM is in stock and assembly-eligible.

**First article.** `docs/board-continuity-check.md` gains a PCB version:
shorts, mains isolation reading open to every SELV net, plug keying,
SW-USB both ways, the 5 V module's output with no trim, and an LED table
saying which LED shows which output. Then `docs/hardware-bringup.md`
applies unchanged from its section 1.

## Docs that change

- `docs/hardware.md`: a "Printed circuit board" section (BOM with LCSC
  numbers, header pinouts, what differs from the protoboard) and the
  protoboard section marked as the previous build.
- `docs/board-continuity-check.md`: the PCB version above.
- `docs/failure-modes.md`: rows A-15, F-03, G-09 and G-11 record the PCB
  mitigation; new rows for the PPTC and for SW-USB left on.
- `docs/inspection-checklist.md`: items retired or reworded for the PCB.
- `docs/datasheets/`: the new parts (5 V module, MMBT2222A, the MOSFET,
  SS34, S1M, the PPTC, the pluggable headers, the fuse holder, the slide
  switch).
- `CLAUDE.md`: `hardware/` in the layout section; the invariant that the
  pin map by header position is asserted by `tests/test_pinmap.py`.
- `README.md`: one paragraph and a link.

## Not in this work

- Firmware changes of any kind, including the 24 V rail monitor.
- The enclosure, the PSU mounting, the display and sensor cables.
- Any change to the pin map or to the mains scheme.
- A power path that would make the USB port safe with SW-USB on.
- Routing in CI.

## Unverified — confirm, do not assume

- That MornSun K7805-1000R3 (or an equivalent fixed 5 V, 78xx-pinout
  module rated for 24 V in) is in the LCSC catalogue and assembly-eligible.
  Fallback: hand-fit from Mouser, flagged in the BOM.
- LCSC part numbers and assembly eligibility for the pluggable headers
  (300 V rated for the mains 8-pin), the covered fuse holder, the slide
  switch, the PPTC and the SOT-23 MOSFET.
- That the stock SANYOU SRD footprint's pad positions equal the Songle
  numbers in `docs/hardware.md`; the generator asserts this.
- The 3.8 mm COM-to-coil pad gap and the 6 mm rule against the creepage
  table actually applied at review (IEC 62368-1, 150 V working, pollution
  degree 2).
- The 5 V module's output tolerance against the AP2112 dropout budget in
  `docs/hardware.md` after the SS34 drop (the protoboard budget assumed
  5.00 to 5.10 V).
- How KiCad's DSN export represents the slot and the rule areas, and that
  Freerouting 2.5.0 honours them; DRC is the backstop either way.
- That the `kicad/kicad:10.0` image's Python has `pcbnew`.
- The final outline and that the USB-C overhang leaves room for a plug
  with the board on standoffs.
- That the K78 module fits the stock TRACO TSR-1 footprint (both are SIP-3,
  2.54 mm pitch, In-GND-Out); the generator asserts the pin pitch and the
  plan compares the body outlines.
- Board thermal: the 5 V module at about 0.4 A, the SS34 at about 0.2 W.

## As built (2026-10-14)

The sections above are the approved design and are left as approved. Rev A
as generated differs from them as follows; each line gives the reason.
`docs/hardware.md` ("Printed circuit board (rev A)") describes the board
as built.

- **Outline 110 × 85 mm**, not about 100 × 80: fixed in the implementation
  plan's placement table, which needed the room for the mains strip, the
  relay areas and the 6 mm clearances; the spec left the size to the
  generator.
- **Mains zone is x ≥ 72.5 mm behind a 2 mm slot (x 70.5 to 72.5) with
  four gaps**, one per relay coil track, rather than a slot broken only
  under each relay body.
- **Both relays sit wholly inside the mains zone, their coil pads SELV
  islands**, instead of straddling the boundary with the coil pins
  outside. The Songle pattern puts COM outboard of the coil column, so no
  straight boundary separates COM from the coil pins. The coil nets stay
  SELV and reach the islands through the slot gaps under the 3.5 mm
  `relay_pads` rule.
- **The COM-to-coil pad gap is 3.51 mm (3.61 mm to the +5V coil pad), not
  about 3.8 mm**: measured on the committed board, with the stock
  footprint's Ø3.0 mm COM pad and Ø2.5 mm coil pads. It is the relay's own
  geometry and still exceeds the 3.2 mm reinforced creepage of the desk
  review (unverified, see docs/hardware.md).
- **Mains copper is hand-placed, not autorouted**: 1.5 mm tracks, fixed
  geometry in `placement.MAINS_TRACKS`, laid locked by the generator. The
  first routed board had 31 unconnected pads because KiCad's DSN export
  turns every rule area into a full keep-out (walling off the mains and
  coil pads) and Freerouting cannot see the custom rules. Five short mains
  nets are better defined as fixed geometry.
- **Freerouting routes only the low-voltage nets, from scratch on every
  `route`**, on a copy of the board with the mains side blocked (except a
  corridor to each coil pad) and the GND pours removed; the SES is imported
  onto a bare board and the mains copper laid again. Freerouting keeps any
  wiring it is given, so a bad route would otherwise survive every rerun.
- **"Tracks on unchanged nets survive" now describes `generate` only.**
  `generate` (update mode) keeps existing tracks; `route` replaces every
  SELV track.
- **`check` also compares the committed mains copper with
  `placement.MAINS_TRACKS`** (segments, layer, 1.5 mm width, locked),
  since the generator owns it. SELV tracks are never compared.
- **Three DRC rules beyond the spec's two** (`project.RULES`):
  "relay NC contact is live" (K1/K2 pad 4, netless but at mains potential
  whenever the coil is off, 6 mm from every non-mains item, after the
  3.5 mm relaxation so it cannot be overridden); "mains to mounting
  holes" (6 mm hole clearance to every NPTH hole, so the spec's "each at
  least 6 mm from mains copper" is checked, not assumed; a review found
  L_IN 1.19 mm from H2 before it existed); and the **NC-pad exclusion** on
  both mains-to-SELV rules, so the netless NC pad is not treated as SELV
  and mains tracks may pass it at the mains in-class clearance.
- **CJ2310 MOSFET, not SI2308**: in the JLCPCB catalogue; 60 V,
  V<sub>GS(th)</sub> 2 V max, R<sub>DS(on)</sub> 125 mΩ max at 4.5 V. Its
  datasheet draws the 3 V output curve on top of the 4 V and 5 V curves at
  low V<sub>DS</sub>, so 3.3 V drive at 125 mA is comfortable (not
  measured).
- **Flybacks are MDD M7** (the S1M rating: 1 A, 1000 V, SMA); the BOM value
  field still reads "S1M".
- **U1 is hand-fitted, a TRACO TSR 1-2450 from Mouser**: MornSun's
  K7805-1000R3 is not stocked at LCSC/JLCPCB or Mouser. The TSR 1-2450 is
  the part the stock footprint is drawn for, same pinout. It stays in the
  BOM with no LCSC number; deselect it at JLCPCB.
- **F1 is an XFCN PTF-76-B covered holder with 15 mm pin pitch** (UL
  250 VAC 20 A, VDE 6.3 A), on a local footprint, at (77.3, 7) so its body
  clears the slot and its L_IN pad keeps 6 mm from the SELV pour. A
  22.3 to 22.6 mm holder cannot sit there: with pad 1 6 mm from SELV, pad 2
  lands within 6 mm of mounting hole H2.
- **SW1 is a SOFNG SS-12D00 on a 2.5 mm pitch** (not 2.54), on a local
  footprint.
- **The four pluggable headers are DORABO parts on local footprints**
  copied from the stock Phoenix ones and drilled to the DORABO drawings
  (Ø1.7 mm for the 5.08 mm headers, Ø1.4 mm for the 3.5 mm one, 0.3 mm
  annular ring); the stock drills were too small for their pins.
- **TP2 sits at x 37.4**, off the 3.5 mm grid, to avoid a KiCad 10 DRC
  false positive (GND fill reported touching TP2 with 0 mm clearance while
  the saved fill keeps 0.3 mm).
- **`export.py` instead of a `.kicad_jobset`**: the exports run as
  kicad-cli calls from Python, which also post-processes the BOM (KiCad's
  trailing "?" on references such as J_24V stripped, plain comma lists)
  and writes JLCPCB's CPL from KiCad's position file.
- **`export --no-docs`** in CI: the renders are not pixel-stable, so CI
  uploads them as an artifact and never rewrites the committed review
  files in `docs/hardware/`; a local `export` refreshes them.
- **Silkscreen**: a "MAINS 120 VAC / keep 6 mm from SELV" legend and a
  line along the slot rather than a hatched band; socket positions
  numbered at the ends on the front, with the function at each used
  position on the back.
- **No GND stitching vias** are placed by the generator; the pours connect
  through pads and the vias the router places (DRC reports nothing
  unconnected).
