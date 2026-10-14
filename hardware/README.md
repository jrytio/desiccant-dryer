# Hardware: the controller PCB

Generated from `dryer_board/` (see `docs/superpowers/specs/2026-10-14-pcb-design-kicad-design.md`).

    scripts/hardware.sh env       # where KiCad was found
    scripts/hardware.sh test      # unit tests (KiCad's Python)
    scripts/hardware.sh generate  # schematic, project, board (keeps existing tracks)
    scripts/hardware.sh route [passes]  # Freerouting 2.5.0 in Docker (default 50) reroutes the SELV nets from scratch; mains copper is placement.MAINS_TRACKS
    scripts/hardware.sh check     # committed files match the model; ERC; DRC
    scripts/hardware.sh export    # fab files to hardware/out/, renders to docs/hardware/

Needs KiCad 10 (`brew install --cask kicad`) and Docker for `route`. No Java.

## Ordering (JLCPCB)

`scripts/hardware.sh export` writes `hardware/out/dryer-controller-rev<N>-gerbers.zip`, `-bom.csv` and `-cpl.csv`.

1. Upload the gerber zip, the BOM CSV and the CPL CSV to JLCPCB.
2. Options: 2 layers, 1.6 mm, 1 oz copper, HASL lead-free, assembly on the top side.
3. Run JLCPCB's DFM analysis on the uploaded gerbers before paying.
4. In JLCPCB's placement preview, check the rotation of the SOT-23 and SMA parts (their footprint zero differs from JLCPCB's) and correct any that are off.
5. The minimum order is five boards.
6. The Songle relay is an extended part, so JLCPCB charges a per-part loading fee for it.
7. The mating plugs for the four pluggable headers are ordered separately; their part numbers are filled in by a later task.
