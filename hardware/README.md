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
4. In JLCPCB's placement preview, check the rotation of the SOT-23 and SMA parts (their footprint zero differs from JLCPCB's) and correct any that are off.
5. The minimum order is five boards of each.
6. Every fab-fitted part carries its LCSC number in the BOM (`hardware/dryer_board/controller.py` and `mains.py`; each part's description says basic or extended). JLCPCB charges a per-part loading fee for each extended part: the relays, the MOSFETs, the electrolytics, the PPTC, the headers and sockets, the two XH link headers and the switch.
7. **U1 (the 5 V module, controller board) is hand-fitted.** It is in the BOM with no LCSC number, so deselect it in JLCPCB's BOM check. The footprint is drawn for the TRACO TSR 1-2450 (Mouser 495-TSR-1-2450). The Amazon-listed "AOTUPASION TSR 1-2450" (B0GTTJ4PNX) fits it mechanically: 11.5 × 7.5 × 10 mm body inside the footprint's 11.7 × 7.6 outline, three SIP pins on the 2.54 mm pitch, and the pin-1 dot at the same end as TRACO's drawing. The listing does not state its pinout and the label carries no TRACO logo, so **before soldering one, power it on the bench: current-limited 12 V on pin 1 (+) and pin 2 (GND), expect 5 V on pin 3** (docs/board-continuity-check.md, PCB item 0). A MornSun K7805-1000R3 from another distributor also fits (same pinout).
8. **F1 (the fuse holder, mains board) is hand-fitted** from the covered 5 × 20 mm holders on hand (Amazon B0FCS5MK1Y, 10 A 250 V), and is in the BOM with no LCSC number. Its footprint has slotted holes on a 12.5 mm pitch that take any pin spacing from 11.5 to 13.5 mm, drawn to the reviewer's measurement of 2026-10-15: pins about 12.5 mm apart, body 25.7 × 10 mm (the body is drawn centred on the pins, an assumption). That body is the BLX-A moulding, whose datasheet (`docs/datasheets/fuses/jksemi-blx-a.pdf`) puts the pins 22.3 ± 1.0 mm apart, so the measurement and the drawing disagree. **Confirm the pin positions against the body ends before ordering boards.** If the pins are 22.3 mm apart after all, switch F1 back to `Fuseholder_5x20mm_Covered_P22.50mm_Slot` (still in `lib/dryer.pretty`); that is not a one-line change, because the 25.8 mm body and the vertical plug share 26.2 mm between the slot and the edge, so F1 and the L_IN/L_FUSED copper in `mains.py` need re-laying as in commit 1ad4129, then `generate mains`, `check`. The 15 mm `..._XFCN_PTF-76-B_P15.00mm` footprint is there too. To have JLCPCB fit a holder instead, the XFCN PTF-77 (LCSC C717030) is a 22.5 mm part on the 22.5 mm pads. The 5 × 20 mm fuse itself (T 3.15 A) is bought separately.
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

## CI

`.github/workflows/hardware.yml` runs `test`, `check` and `export --no-docs` in the `kicad/kicad:10.0.6` image (pinned to the patch release the TP2 placement was checked against; amd64 only; on Apple silicon use `docker run --platform linux/amd64 -u $(id -u):$(id -g) -e HOME=/tmp`). It never routes. `hardware/out/` is uploaded as an artifact and the review copies in `docs/hardware/` (`controller-*`, `mains-*`) are not touched, so they change only when someone runs `export` locally. A `pcb-*` tag attaches both boards' gerber zips, BOMs, CPLs and schematic PDFs to a GitHub release.
