# Hardware: the controller and mains PCBs

Two boards, generated from `dryer_board/` (see `docs/superpowers/specs/2026-10-14-pcb-design-kicad-design.md`, and its "As built" section for where the boards differ from it):

- **`dryer-controller`** (85 × 70 mm, the controller space in the enclosure): the socketed Thing Plus, 24 V in, the 5 V module, the USB-pin switch, the three MOSFET stages, the sensor and display headers, and J_RLY, the link to the mains board.
- **`dryer-mains`** (45 × 70 mm, the mains space): the fuse, the two relays with their driver stages, the 120 VAC plug, and J_CTRL, the other end of the link. The mains zone sits behind a 2 mm routed slot with four gaps for the coil tracks. Both outlines are the reviewer's enclosure sizes; the corner mounting holes (4 mm in from each edge) and the USB-C overhang (3 mm past the controller's left edge) are assumptions awaiting his confirmation; the mains plug is a vertical header inside the outline since he reported a wall beside the mains space (docs/superpowers/specs/2026-10-15-pcb-two-board-split-design.md).

The link is a JST-XH 4-way, the protoboard harness's connector and pin order: **1 = 5 V, 2 = GND, 3 = heater A, 4 = heater B**, labelled beside both headers. Pin 1 is at the top of each header with the boards side by side (controller left, mains right). The cable is 1:1, XHP-4 housing to XHP-4 housing (a pre-made "XH 2.54" 4-pin female-female lead is the same thing: XH is 2.50 mm); keep it under 30 cm. The link's 2.5 mm pitch means no other plug on either board fits it. The SHT45 is not on either board: it plugs into the Thing Plus's own Qwiic connector with a Qwiic/STEMMA QT cable (docs/hardware.md "Header pinouts").

BOM, header pinouts, LEDs, clearances and the USB-pin budget are in `docs/hardware.md` ("Printed circuit board (rev A)"); revisions and the `pcb-*` release tag in `docs/releasing.md`.

    scripts/hardware.sh env       # where KiCad was found
    scripts/hardware.sh test      # unit tests (KiCad's Python)
    scripts/hardware.sh generate [--fresh] [board]   # schematic, project, board (keeps existing tracks)
    scripts/hardware.sh route [board] [passes]       # Freerouting 2.5.0 in Docker (default 50) reroutes the SELV nets from scratch; mains copper is mains.MAINS_TRACKS
    scripts/hardware.sh check [board]                # committed files match the model; ERC; DRC
    scripts/hardware.sh export [--no-docs] [board]   # fab files and renders to hardware/out/, review copies to docs/hardware/ (--no-docs skips the copy)

Every command runs over both boards unless one is named (`controller` or `mains`). Needs KiCad 10 (`brew install --cask kicad`) and Docker for `route`. No Java.

Do not use the KiCad GUI's "Update PCB from Schematic" on these boards: the footprints carry no schematic
path, so KiCad would treat every part as new or orphaned. The generator is the update path: change
`dryer_board/`, then `generate` (and `route` if the SELV connectivity changed). The local footprints
(`dryer:*`) live in `lib/dryer.pretty` and are copied into each project's `lib/` by `generate`; edit the
copy in `lib/`, not a project's.

## Ordering (JLCPCB)

`scripts/hardware.sh export` writes, for each board, `hardware/out/dryer-<board>-rev<N>-gerbers.zip`, `-bom.csv` and `-cpl.csv`. Order the two boards as two JLCPCB orders (or one order with two files if JLCPCB offers it); each has its own BOM and CPL.

1. Upload each board's gerber zip, BOM CSV and CPL CSV to JLCPCB.
2. Options: 2 layers, 1.6 mm, 1 oz copper, HASL lead-free, assembly on the top side.
3. Run JLCPCB's DFM analysis on the uploaded gerbers before paying.
4. In JLCPCB's placement preview, check every polarised and keyed part before paying. The CPL is already written for JLCPCB: each part's position is the centre of its pads (KiCad's own position file gives the footprint anchor, which is pin 1 on the connectors, sockets, relays, fuse holder, switch and U1, so those appeared shifted by half a body in the first upload on 2026-10-16), and the rotations carry the per-package corrections in `JLC_ROTATIONS` in `hardware/dryer_board/export.py` (pluggable headers and the XH links 180°, 1×N pin sockets and headers −90°, SOT-23 180°, electrolytics 180°, SMA diodes 180°, 0805 LEDs 180°; resistors, ceramics and the PPTC unchanged). The connector, socket, SOT-23 and electrolytic values match that preview; the SMA diodes, the LEDs, the direction of the pin-socket turn (pin 1 at the USB end), the relays, the fuse holder and the slide switch are set by analogy or left at KiCad's angle and must be confirmed in the preview. If one is off, change its entry in `JLC_ROTATIONS`, run `scripts/hardware.sh export`, re-upload the CPL and look again; do not fix it only in the browser, or the next export loses it. The flyback diodes D5 to D7 and the 24 V diodes D11 and D14 matter most: reversed, a flyback shorts its output when it switches on.
5. The minimum order is five boards of each.
6. Every fab-fitted part carries its LCSC number in the BOM (`hardware/dryer_board/controller.py` and `mains.py`; each part's description says basic or extended). JLCPCB charges a per-part loading fee for each extended part: the relays, the MOSFETs, the electrolytics, the PPTC, the fuse holder, the headers and sockets, the two XH link headers and the switch.
7. **U1 (the 5 V module, controller board) is hand-fitted.** It is in the BOM with no LCSC number, so deselect it in JLCPCB's BOM check. The footprint is drawn for the TRACO TSR 1-2450 (Mouser 495-TSR-1-2450). The Amazon-listed "AOTUPASION TSR 1-2450" (B0GTTJ4PNX) fits it mechanically: 11.5 × 7.5 × 10 mm body inside the footprint's 11.7 × 7.6 outline, three SIP pins on the 2.54 mm pitch, and the pin-1 dot at the same end as TRACO's drawing. The listing does not state its pinout and the label carries no TRACO logo, so **before soldering one, power it on the bench: current-limited 12 V on pin 1 (+) and pin 2 (GND), expect 5 V on pin 3** (docs/board-continuity-check.md, PCB item 0). A MornSun K7805-1000R3 from another distributor also fits (same pinout).
8. **F1 (the fuse holder, mains board) is fab-fitted**: the XFCN PTF-76-B covered holder (LCSC C48603682, 15 mm pitch, UL 250 VAC 20 A), the single-board rev A's choice. The covered 5 × 20 mm holders on hand (Amazon B0FCS5MK1Y, the BLX-A moulding; the reviewer confirmed their pitch at about 22 mm on 2026-10-15, after a first reading of 12.5 mm from the listing's picture) are **not fitted**: with mains copper 1 mm from the slot, their 25.8 mm body would run from x 10.35 to 36.15 and into the vertical plug (strip, slot, clearance, holder and the plug's body add up to 45.6 mm across the 45 mm board; 1 mm over against the plug's courtyard). The `Fuseholder_5x20mm_Covered_P22.50mm_Slot` footprint stays in `lib/dryer.pretty` for a right-angle-plug layout, where they fit. The 5 × 20 mm fuse itself (T 3.15 A) is bought separately. First-article note: the plug's pin-1 wires leave 2 to 4 mm from the holder's lift-off cap, so changing the fuse may need the plug pulled first (unverified until a board is built).
9. The mating plugs for the pluggable headers, and the link cable, are not on the boards. Order them as loose parts (LCSC numbers; DORABO screw plugs, green):

   | Header | Plug | LCSC |
   |---|---|---|
   | J_MAINS (8-pin 5.08 mm, mains board; the header is the vertical DB2EV-5.08-8P-GN, C395787, since the reviewer reported a wall beside the mains space) | DB2EK-5.08-8P-GN-S | C395791 |
   | J_LOADS (6-pin 5.08 mm, controller) | DB2EK-5.08-6P-GN-S | C395774 |
   | J_24V (2-pin 5.08 mm, controller) | DB2EK-5.08-2P-GN-S | C395732 |
   | J_SENS (9-pin 3.5 mm, controller) | DB2EK-3.5-9P-GN-S | C430561 |
   | J_RLY and J_CTRL (JST XH 4-way, one each board) | 2 × XHP-4 housing + 8 × SXH-001T-P0.6 crimps and a 4-core lead, or a pre-made 4-pin XH female-female cable | JST, any distributor |

   The mounting holes on both boards are 4.3 mm, for M4 hardware.

### PCBWay instead of JLCPCB

Both boards can be fabricated and assembled by PCBWay with no design change: the gerbers, drill files and footprints are standard, and PCBWay assembles through-hole parts and accepts DNP lines (U1 and F1). What changes is the paperwork and the sourcing, not the boards:

- PCBWay wants its own BOM columns (line, quantity, designators, manufacturer, MPN, description, package, SMT/PTH, and a distributor part number) rather than JLCPCB's four; the LCSC numbers go in the distributor column. Their centroid file is the same designator / X / Y / rotation / side list as the CPL.
- PCBWay sources from Digi-Key, Mouser, Farnell, Arrow, Avnet and "local suppliers", and will buy from a supplier or link you name in the BOM, with substitutes only on your approval. Whether they buy from LCSC was not confirmed on their pages. The parts at risk are the LCSC-only Chinese brands: the DORABO pluggable headers and plugs, the Kinghelm sockets, the SOFNG slide switch, the XFCN display header, and the Songle relays (not at Digi-Key; a TE equivalent would need its pin pattern checked). The passives, LEDs, diodes, transistors and electrolytics are generic and have Western-distributor equivalents in the same footprints.
- Practical route if PCBWay is chosen: order it as a kitted or combo job, buy the LCSC-only parts yourself (with spares, PCBWay asks for extra passives) and ship them, or put the LCSC links in the BOM and get the all-in quote in writing before paying. PCBWay's MOQ is 1 (the quote form starts at 5); the online price excludes parts and the exact quote follows a manual review in one to two days.

#### Quote packet (2026-10-16)

Everything PCBWay's quote form asks for, so the request takes a few minutes. The request itself needs a PCBWay account and contact details, so a person files it (the hardware reviewer asked for an estimate on PR #49).

Files: the `hardware-outputs` artifact of the latest green [hardware workflow run](https://github.com/jrytio/desiccant-dryer/actions/workflows/hardware.yml) on the PR branch (or `scripts/hardware.sh export` locally, into `hardware/out/`): `dryer-controller-revA-gerbers.zip` and `dryer-mains-revA-gerbers.zip` (gerbers and drill files, one zip per board), `dryer-*-revA-bom.csv` (JLCPCB columns: comment, designators, footprint, LCSC number; PCBWay accepts it, the LCSC number is the distributor part number), `dryer-*-revA-cpl.csv` (centroids, top side; positions are the pad centres and the rotations follow JLCPCB's library orientations per item 4 above, so PCBWay's reviewers must check orientation in their own preview) and `dryer-*-revA-schematic.pdf`.

| | Controller board | Mains board |
|---|---|---|
| Size | 85 × 70 mm | 45 × 70 mm |
| Layers, material, thickness, copper | 2, FR-4, 1.6 mm, 1 oz | same |
| Surface finish | lead-free HASL (ENIG if preferred; nothing in the design needs it) | same |
| Min track / clearance | 0.2 / 0.2 mm (0.225 mm is the narrowest track routed) | same |
| Min hole | 0.3 mm via drill; smallest part hole 0.95 mm | same; 1.6 mm fuse-holder holes |
| Cutouts | none | one 2 mm wide routed slot in five segments (internal cutouts, in the Edge.Cuts layer) |
| Mounting holes | 4 × 4.3 mm non-plated | same |
| Quantity | 5 (the form's minimum; 2 to 5 are wanted) | 5 |
| Assembly | top side only, SMD and through-hole: 26 BOM lines, 43 placements (34 SMD, 9 through-hole: the two ESP sockets, five pluggable headers, the slide switch, U1). U1 (the 5 V module) is hand-fitted: mark it DNP / "do not source" | top side only: 9 BOM lines, 15 placements (10 SMD, 5 through-hole: fuse holder, two relays, two headers). Nothing excluded |
| Parts to confirm sourcing | the LCSC-only brands (see above); the DORABO headers (J_LOADS C395768, J_24V C395734, J_SENS C430559, J_RLY JST C144395 is generic) | DORABO DB2EV-5.08-8P-GN C395787, XFCN PTF-76-B C48603682, Songle SRD-05VDC-SL-C C35449, JST C144395 |

Steps on pcbway.com: PCB Instant Quote → enter the table (one quote per board, or both in one order as two parts) → tick "Assembly" and give the placement counts → upload the two zips, the BOMs and the CPLs → "Request a quote". Expect the manual review to ask about the mains board's slot (it is intentional, an isolation slot) and about sourcing the Chinese-brand parts.

## CI

`.github/workflows/hardware.yml` runs `test`, `check` and `export --no-docs` in the `kicad/kicad:10.0.6` image (pinned to the patch release the TP2 placement was checked against; amd64 only; on Apple silicon use `docker run --platform linux/amd64 -u $(id -u):$(id -g) -e HOME=/tmp`). It never routes. `hardware/out/` is uploaded as an artifact and the review copies in `docs/hardware/` (`controller-*`, `mains-*`) are not touched, so they change only when someone runs `export` locally. A `pcb-*` tag attaches both boards' gerber zips, BOMs, CPLs and schematic PDFs to a GitHub release.
