# Airflow indicators — design

Date: 2026-09-15
Status: approved in conversation
Amends: `2026-09-14-display-ui-design.md` and
`2026-09-14-cylinder-state-colours-design.md`

## Goal

The top of the screen showed a shared "WET AIR" inlet piped into both
cylinders, which doesn't match what happens: ambient air enters the top of
the pack in use, and warm air leaves the top of the pack being heated. The
heater zigzag beside a cylinder repeated what its orange colour already says.
Replace both with an airflow indicator above each pack.

Reference sheet: `docs/display/mockup-states.html`.

## Design

- **Removed:** the "WET AIR" label, the inlet stub, top manifold and branches,
  the inlet arrowhead, both heater zigzags in `schematic.svg`, and the
  `heater-on-a.svg` / `heater-on-b.svg` glow sprites.
- **Air in:** `flow-in.svg` (17×26), three green (`#24DB55`) chevrons pointing
  down, drawn at (cx − 8, 3) when that pack's valve is on.
- **Air out:** `flow-out.svg` (27×31), three amber (`#FFB600`) heat waves
  rising, drawn at (cx − 13, 1) when that pack's heater is on.
- Both follow the real output switches, like the valves and lit path: a
  HEATING pack whose heater is held off shows no waves; on a fault the heaters
  are off (no waves) and the active valve stays open (chevrons stay). COOLING,
  READY, WET, OFF and Starting show nothing at the top.
- `UiAssets` members `heater_on_a, heater_on_b` become `flow_in, flow_out`;
  `display-draw.yaml` image ids `img_heater_on_a/b` become
  `img_flow_in/out`.
- Unchanged: cylinder geometry and colours, plate, bottom plumbing, valves,
  gauge, strip, SIM badge (x 210–232 stays clear of B's waves at x 167–193),
  fan.

## Verification

`esphome config` on all four builds; `scripts/scenario-shots.sh` and check
the twelve captures against the reference sheet; CI compiles all four builds.
