# Hardware: the controller PCB

Generated from `dryer_board/` (see `docs/superpowers/specs/2026-10-14-pcb-design-kicad-design.md`).

    scripts/hardware.sh env       # where KiCad was found
    scripts/hardware.sh test      # unit tests (KiCad's Python)
    scripts/hardware.sh generate  # schematic, project, board (keeps existing tracks)
    scripts/hardware.sh route     # Freerouting in Docker, imports the result
    scripts/hardware.sh check     # committed files match the model; ERC; DRC
    scripts/hardware.sh export    # fab files to hardware/out/, renders to docs/hardware/

Needs KiCad 10 (`brew install --cask kicad`) and Docker for `route`. No Java.
