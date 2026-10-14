# Hardware: the controller PCB

Generated from `dryer_board/` (see `docs/superpowers/specs/2026-10-14-pcb-design-kicad-design.md`, and its "As built" section for where the board differs from it). BOM, header pinouts, LEDs, clearances and the USB-pin budget are in `docs/hardware.md` ("Printed circuit board (rev A)"); revisions and the `pcb-*` release tag in `docs/releasing.md`.

    scripts/hardware.sh env       # where KiCad was found
    scripts/hardware.sh test      # unit tests (KiCad's Python)
    scripts/hardware.sh generate  # schematic, project, board (keeps existing tracks)
    scripts/hardware.sh route [passes]  # Freerouting 2.5.0 in Docker (default 50) reroutes the SELV nets from scratch; mains copper is placement.MAINS_TRACKS
    scripts/hardware.sh check     # committed files match the model; ERC; DRC
    scripts/hardware.sh export    # fab files and renders to hardware/out/, review copies to docs/hardware/ (--no-docs skips the copy)

Needs KiCad 10 (`brew install --cask kicad`) and Docker for `route`. No Java.

Do not use the KiCad GUI's "Update PCB from Schematic" on this board: the footprints carry no schematic
path, so KiCad would treat every part as new or orphaned. The generator is the update path: change
`dryer_board/`, then `generate` (and `route` if the SELV connectivity changed).

## Ordering (JLCPCB)

`scripts/hardware.sh export` writes `hardware/out/dryer-controller-rev<N>-gerbers.zip`, `-bom.csv` and `-cpl.csv`.

1. Upload the gerber zip, the BOM CSV and the CPL CSV to JLCPCB.
2. Options: 2 layers, 1.6 mm, 1 oz copper, HASL lead-free, assembly on the top side.
3. Run JLCPCB's DFM analysis on the uploaded gerbers before paying.
4. In JLCPCB's placement preview, check the rotation of the SOT-23 and SMA parts (their footprint zero differs from JLCPCB's) and correct any that are off.
5. The minimum order is five boards.
6. Every part carries its LCSC number in the BOM (`hardware/dryer_board/circuit.py`, each part's description says basic or extended). JLCPCB charges a per-part loading fee for each extended part: the relays, the MOSFETs, the electrolytics, the PPTC, the headers and sockets, the switch and the fuse holder.
7. U1 (the 5 V module) is hand-fitted: MornSun's K7805-1000R3 is not stocked at LCSC/JLCPCB or Mouser. It is in the BOM with no LCSC number, so deselect it in JLCPCB's BOM check. Buy the TRACO TSR 1-2450 (Mouser 495-TSR-1-2450), the part the footprint is drawn for, with the same pinout, or a MornSun K7805-1000R3 from another distributor. The 5 × 20 mm fuse (T 3.15 A) for F1's holder is also bought separately.
8. The mating plugs for the four pluggable headers are not on the board. Order them as loose parts (LCSC numbers, DORABO screw plugs, green):

   | Header | Plug | LCSC |
   |---|---|---|
   | J_MAINS (8-pin 5.08 mm) | DB2EK-5.08-8P-GN-S | C395791 |
   | J_LOADS (6-pin 5.08 mm) | DB2EK-5.08-6P-GN-S | C395774 |
   | J_24V (2-pin 5.08 mm) | DB2EK-5.08-2P-GN-S | C395732 |
   | J_SENS (9-pin 3.5 mm) | DB2EK-3.5-9P-GN-S | C430561 |

## CI

`.github/workflows/hardware.yml` runs `test`, `check` and `export --no-docs` in the `kicad/kicad:10.0.6` image (pinned to the patch release the TP2 placement was checked against; amd64 only; on Apple silicon use `docker run --platform linux/amd64 -u $(id -u):$(id -g) -e HOME=/tmp`). It never routes. `hardware/out/` is uploaded as an artifact and the review copies in `docs/hardware/` are not touched, so they change only when someone runs `export` locally. A `pcb-*` tag attaches the gerber zip, BOM, CPL and schematic PDF to a GitHub release.
