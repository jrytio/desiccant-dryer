# Cylinder state colours — design

Date: 2026-09-14
Status: approved in conversation
Amends: `2026-09-14-display-ui-design.md` (the display UI spec)

## Goal

Replace the temperature fill in the two cylinders (a coloured level rising
from 20 °C to the overtemp limit, with threshold dashes and a cap sprite on
top) with a solid body colour that says which state the pack is in. On the
real screen, the fill level and dashes did not read as progress. Colour by
state reads at a glance.

Reference sheet: `docs/display/mockup-states.html` (all twelve scenarios in
the new design; open in a browser).

## Decisions made during brainstorming

| Question | Decision |
|---|---|
| Treatment | Whole cylinder body filled with the state colour; the black text plate stays, white temperature and timer, phase word in the state colour (option "A" of three) |
| WET colour | Pink `#FF92AA`, matching the colour of wet indicator desiccant; READY blue matches dry desiccant |
| Words | IN SERVICE becomes IN USE. FAULT stays, matching the HA `Fault` / `Clear Fault` entities and the status strip |
| Off and Starting | No colour: body stays black, shell grey |
| Probe reading missing | Colour stays (the state is still known); temperature shows `--°` in dim, as today |
| Fault | Faulted pack solid red with FAULT; the other pack keeps its colour, because air still flows through the active pack while a fault is latched. The red fault-ring sprite is dropped |
| Rendering | One filled rectangle per pack under the existing background, which already leaves the cylinder interiors transparent and masks the bottom corners |

## Non-goals

- Any change to layout, plate, heater glow, valves, lit air path, gauge,
  status strip, SIM badge, fan, timers or fonts.
- Any change to the controller (`base.yaml`), HA entities, or thresholds.
- Partial redraw (still the follow-up in the display UI spec §9).

## 1. Colours

All on the panel's RGB 3-3-2 grid (R and G in steps of 255/7, B in steps of
255/3).

| Body state | Word | Colour | Constant |
|---|---|---|---|
| Active pack | IN USE | `#24DB55` | `GREEN` (existing) |
| Standby 0 | WET | `#FF92AA` | `PINK` (new) |
| Standby 1 | HEATING | `#FF9200` | `ORANGE` (existing) |
| Standby 2 | COOLING | `#00DBFF` | `CYAN` (existing) |
| Standby 3 | READY | `#246DFF` | `BLUE` (existing) |
| Faulted pack | FAULT | `#FF2424` | `RED` (existing) |
| Disabled | OFF | none (black body), word `DIM` | — |
| Enabled, `active_pack == 0` | (no word) | none (black body) | — |

The word on the plate is always the same colour as the body. Faulted-pack
selection is unchanged: code 1 is the active pack, codes 2 and 3 the standby
pack.

Constants that become unused and are removed: `ORANGE_MID`, `DEEP`,
`DARKOR`, `BLUE_L`, `BLUE_D`.

## 2. Drawing (`esphome/packages/display_ui.h`)

- `PackView` gains `bool filled` (default false). `pack_roles()` sets it true
  for the active pack, the standby pack and a faulted pack; it stays false
  when disabled and when `active_pack` is 0. The body colour is
  `phase_color`. WET's entry in the standby colour table changes from `DIM`
  to `PINK`; the active pack's word changes from `"IN SERVICE"` to
  `"IN USE"`.
- `draw_fill()` becomes: if `filled`, one `filled_rectangle(cx − 25, 40, 51,
  116, phase_color)`. That covers the transparent interior of
  `schematic.svg` (columns cx−25…cx+25, rows 40 to the bottom cap curve);
  the background, drawn next, keeps the grey top cap over row 40 and masks
  everything outside the bottom cap curve down to row 156. It no longer
  depends on the temperature, so a NaN reading still gets its colour.
- `draw_pack_text()` loses the two threshold dash lines; the plate,
  temperature, phase word and timer are unchanged.
- Removed: `level_y()`, `dashes()`, the cap sprite choice, and the two
  `fault_ring` image draws in `draw_ui()`.
- `UiState` loses `cooldown`, `regen` and `overtemp` (only the fill used
  them). `UiAssets` loses `fault_ring`, `cap_blue`, `cap_amber`, `cap_gold`;
  the remaining member order is `f_temp, f_val, f_cap, f_label, f_phase,
  f_status, f_status_b, bg, valve_open, valve_closed, heater_on_a,
  heater_on_b, lit_a, lit_b, fan`.
- The header comment points at this spec as well as the display UI spec.

Draw order per frame becomes: `fill(BLACK)`; body rectangles; `img_bg`;
lit path, valve and heater sprites; pack letters; plates and text; gauge;
case, fan label, SIM badge; fan icon; status strip.

## 3. YAML and assets

- `esphome/packages/display-draw.yaml`: remove the `img_fault_ring`,
  `img_cap_blue`, `img_cap_amber`, `img_cap_gold` image entries; the
  `ui_draw` script stops reading `cooldown_temp`, `regen_temp`, `overtemp`
  and builds `UiAssets` in the new member order.
- `esphome/packages/display-scenarios.yaml`: remove the `cooldown_temp`,
  `regen_temp` and `overtemp` template numbers (the screen no longer reads
  them). The scenario table itself is unchanged.
- Delete `esphome/assets/display/fault-ring.svg`, `cap-blue.svg`,
  `cap-amber.svg`, `cap-gold.svg`.
- `esphome/assets/display/schematic.svg`: comment only — the interiors are
  transparent so the state colour drawn underneath shows through. No
  geometry change.

Flash saving is roughly 26 KB (the four RGB565+alpha sprites at 3 bytes per
pixel); estimated, not measured.

## 4. Docs

- `docs/display/mockup-states.html`: replaced by the new twelve-scenario
  sheet (already done with this spec).
- `docs/display/state-01.png` … `state-12.png`: regenerated with
  `scripts/scenario-shots.sh`.
- `docs/superpowers/specs/2026-09-14-display-ui-design.md`: a note under the
  status line saying the cylinder fill, threshold dashes, cap sprites, fault
  ring and phase colours/words are superseded by this spec. The rest of that
  document is left as written.
- `docs/host-preview.md`: the "Useful screen states" table uses IN USE,
  describes the cylinder turning orange/cyan/blue/pink instead of a rising
  fill, and the fault row says the faulted pack turns solid red instead of
  a red ring.
- `CLAUDE.md`: where the layout section names the screen design spec, add
  this spec alongside it.
- Plans under `docs/superpowers/plans/` are historical and are not edited.

## 5. Verification

1. `cp esphome/secrets.ci.yaml esphome/secrets.yaml`, then `esphome config`
   on `desiccant-dryer.yaml`, `desiccant-dryer-virtual.yaml`,
   `desiccant-dryer-host.yaml` and `desiccant-dryer-scenarios.yaml`.
2. Normalised config diff (`scripts/normalize-config.py`) of
   `desiccant-dryer.yaml` before and after: only the `image:` list and the
   `ui_draw` script lambda change. For the scenarios build, additionally the
   three removed numbers.
3. `scripts/scenario-shots.sh`; read all twelve PNGs and check each against
   the reference sheet: body colours, words, OFF/Starting unfilled, scenario
   9 red B with A still green, scenario 12 orange B with `--°`. No stray
   pixels at the top cap or bottom cap curve.
4. `esphome compile` of the host build locally. The production and virtual
   ESP32 builds compile in CI (`.github/workflows/build.yml`), along with
   both host builds.
5. Not part of this change: flashing the bench board. That waits for the
   user.
