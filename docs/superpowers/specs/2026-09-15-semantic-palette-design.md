# Semantic palette — design

Date: 2026-09-15
Status: chosen by the customer from three options
Amends: `2026-09-14-cylinder-state-colours-design.md` §1 (colours only; the
mapping of states to cylinders is unchanged)

## Goal

The customer wanted a modern, muted palette for a technical audience, with
no pink. Of the three options offered (Indicator, Semantic, Aurora) they
chose Semantic: GitHub's own status hues, which that audience already reads
without thinking. The cycle now reads as a status board rather than a
thermometer.

## Colours

All on the panel's RGB 3-3-2 grid.

| State | Meaning borrowed | Colour | Constant |
|---|---|---|---|
| IN USE | success | `#49B655` (73,182,85) | `GREEN` |
| WET | attention: needs regeneration | `#DBB600` (219,182,0) | `YELLOW` |
| HEATING | severe: heater energised | `#DB6D55` (219,109,85) | `ORANGE` |
| COOLING | informational: nothing to do | `#49B6FF` (73,182,255) | `CYAN` |
| READY | done, like a merged PR | `#926DFF` (146,109,255) | `PURPLE` |
| FAULT | danger | `#FF4955` (255,73,85) | `RED` |

Everything that shared a colour with a state follows it: chevrons, lit
air path, open valve and fan-on take `GREEN`; heat waves take `ORANGE`;
the gauge's RISING/HIGH zones and the OVR badge take `YELLOW` (`AMBER` is
now an alias for it); the fault strip is a darker `RED_STRIP` (219,73,85).
`PINK` and `BLUE` are gone. Sprites with baked-in colours (`flow-in`,
`flow-out`, `lit-a`, `lit-b`, `valve-open`) were re-tinted to match.
