# Cylinder State Colours Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the temperature fill in the display's two cylinders with a solid body colour per pack state.

**Architecture:** `esphome/packages/display_ui.h` draws the whole screen from a `UiState`. Today `draw_fill()` paints stacked colour bands up to a temperature level plus a cap sprite, underneath `schematic.svg`, whose cylinder interiors are transparent. The new `draw_fill()` paints one rectangle in the state colour in the same place. The fill-only inputs (`cooldown`, `regen`, `overtemp`), threshold dashes, cap sprites and fault-ring sprite are removed end to end (header, `display-draw.yaml`, `display-scenarios.yaml`, SVG assets).

**Tech Stack:** ESPHome 2026.1.4 (ESP-IDF on ESP32-S2, plus `host` platform builds with SDL2), C++ header included via `esphome: includes:`, SVG images rasterised at compile time, Python/Pillow scenario renders.

**Spec:** `docs/superpowers/specs/2026-09-14-cylinder-state-colours-design.md`. Reference sheet: `docs/display/mockup-states.html`.

## Global Constraints

- Colours (RGB 3-3-2 grid): IN USE `#24DB55` (`GREEN`), WET `#FF92AA` (`PINK`, new), HEATING `#FF9200` (`ORANGE`), COOLING `#00DBFF` (`CYAN`), READY `#246DFF` (`BLUE`), FAULT `#FF2424` (`RED`).
- Words: active pack `IN USE` (was `IN SERVICE`); faulted pack `FAULT` (unchanged); disabled `OFF` in `DIM`; `active_pack == 0` shows no word.
- Disabled and Starting (`active_pack == 0`): body not filled (stays black).
- NaN temperature: body colour stays; temperature text `--°` in `DIM` (unchanged).
- Fault: only the faulted pack is red (code 1 active pack, codes 2/3 standby); the other pack keeps its colour. No fault ring.
- No change to layout, plate, heater glow, valves, lit path, gauge, strip, SIM badge, fan, timers, fonts, `base.yaml` or any HA entity.
- CLAUDE.md rules: nothing WiFi/OTA/SPI/LEDC in `display-draw.yaml`; no `id()` calls in `display_ui.h`; every display change is checked with `scripts/scenario-shots.sh` before commit.
- Commit messages end with `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`.
- Work only inside the worktree `/Users/josh/GitHub/desiccant-dryer/.claude/worktrees/cylinder-state-colors-343ff1`. Never use bare `git stash`.

---

### Task 1: Solid state-colour cylinder bodies

The header, `display-draw.yaml` and `display-scenarios.yaml` must change together: `UiAssets` is aggregate-initialised in the `ui_draw` script in member order, and the script reads `UiState` fields. There is no unit-test harness for the display; the test is the palette-accurate scenario renders plus `esphome config` / `esphome compile`.

**Files:**
- Modify: `esphome/packages/display_ui.h`
- Modify: `esphome/packages/display-draw.yaml` (image list lines 97–116, script lines 146–148 and 155–160)
- Modify: `esphome/packages/display-scenarios.yaml` (numbers lines 82–105)
- Modify: `esphome/assets/display/schematic.svg` (comment lines 2–4 only)
- Delete: `esphome/assets/display/fault-ring.svg`, `cap-blue.svg`, `cap-amber.svg`, `cap-gold.svg`
- Regenerate: `docs/display/state-01.png` … `state-12.png`

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: `dryer_ui::PINK`; `PackView::filled`; `draw_fill(Display &, const PackView &)`; `draw_pack_text(Display &, const UiAssets &, const PackView &)`; `UiState` without `cooldown/regen/overtemp`; `UiAssets{f_temp, f_val, f_cap, f_label, f_phase, f_status, f_status_b, bg, valve_open, valve_closed, heater_on_a, heater_on_b, lit_a, lit_b, fan}`.

- [ ] **Step 1: Capture the before-config baseline**

Run from the worktree root, before editing anything:

```bash
SCRATCH=/private/tmp/claude-501/-Users-josh-GitHub-desiccant-dryer--claude-worktrees-cylinder-state-colors-343ff1/166ee361-d09d-40a9-aed5-c0ead9321440/scratchpad/cfg
mkdir -p $SCRATCH
cp esphome/secrets.ci.yaml esphome/secrets.yaml
esphome config esphome/desiccant-dryer.yaml > $SCRATCH/prod-before.txt 2>/dev/null; echo prod=$?
esphome config esphome/desiccant-dryer-scenarios.yaml > $SCRATCH/scen-before.txt 2>/dev/null; echo scen=$?
```

Expected: `prod=0`, `scen=0`. (`esphome/secrets.yaml` is gitignored; never commit it.) The first run downloads fonts and may take a minute.

- [ ] **Step 2: Edit `display_ui.h` — header comment, state, assets, colours**

Replace lines 6–7 of the header comment:

```cpp
// packages/display-draw.yaml gathers the state. Geometry and rules follow
// docs/superpowers/specs/2026-09-14-display-ui-design.md sections 2, 4, 5,
// with the cylinder colours of 2026-09-14-cylinder-state-colours-design.md.
```

In `struct UiState`, replace the line
`  float arm_rh = 5, swap_rh = 10, cooldown = 40, regen = 90, overtemp = 120;` with:

```cpp
  float arm_rh = 5, swap_rh = 10;
```

Replace `struct UiAssets` (keep the comment above it):

```cpp
struct UiAssets {
  BaseFont *f_temp, *f_val, *f_cap, *f_label, *f_phase, *f_status, *f_status_b;
  BaseImage *bg, *valve_open, *valve_closed, *heater_on_a, *heater_on_b, *lit_a, *lit_b, *fan;
};
```

Replace the colour block (the comment line `// RGB 3-3-2 grid colours (spec section 5).` and the seven `static const Color` lines after it) with:

```cpp
// RGB 3-3-2 grid colours (display UI spec section 5; cylinder colours spec
// section 1).
static const Color BLACK(0, 0, 0), WHITE(255, 255, 255);
static const Color GREEN(36, 219, 85), ORANGE(255, 146, 0), AMBER(255, 182, 0), CYAN(0, 219, 255);
static const Color BLUE(36, 109, 255), PINK(255, 146, 170);
static const Color SHELL(73, 73, 85), DIM(146, 146, 170), STRIP_TXT(182, 182, 170);
static const Color RED_STRIP(219, 36, 36), RED(255, 36, 36);
static const Color DRY_DIM(36, 109, 36), AMBER_DIM(109, 73, 0), RED_DIM(109, 0, 0);
```

- [ ] **Step 3: Edit `display_ui.h` — `PackView`, remove `dashes`/`level_y`, `pack_roles`**

Replace `struct PackView` (keep its comment line):

```cpp
struct PackView {
  int cx = 0;
  float t = NAN;
  const char *phase = "";
  Color phase_color = DIM;  // also the body colour when filled
  bool filled = false;      // body painted in phase_color; false when off or starting
  bool show_timer = false;
  float timer_s = 0;
};
```

Delete the `dashes()` function with its `// 2 px on, 3 px off...` comment, and the `level_y()` function with its `// Row of the fill's top edge...` comment.

Replace `pack_roles()` with:

```cpp
inline void pack_roles(const UiState &s, PackView &a, PackView &b) {
  static const char *const SB_NAMES[] = {"WET", "HEATING", "COOLING", "READY"};
  static const Color SB_COLORS[] = {PINK, ORANGE, CYAN, BLUE};
  a = PackView{};
  b = PackView{};
  a.cx = CX_A;
  a.t = s.t_a;
  b.cx = CX_B;
  b.t = s.t_b;
  if (!s.enabled) {
    a.phase = b.phase = "OFF";
    return;
  }
  if (s.active != 1 && s.active != 2) return;  // starting: no roles yet
  PackView &act = s.active == 1 ? a : b;
  PackView &sb = s.active == 1 ? b : a;
  act.phase = "IN USE";
  act.phase_color = GREEN;
  act.filled = true;
  act.show_timer = true;
  act.timer_s = s.service_s;
  int st = s.standby_state;
  if (st < 0 || st > 3) st = 0;
  sb.phase = SB_NAMES[st];
  sb.phase_color = SB_COLORS[st];
  sb.filled = true;
  sb.show_timer = true;
  sb.timer_s = s.standby_s;
  PackView *faulted = s.fault_code == 1 ? &act : (s.fault_code == 2 || s.fault_code == 3) ? &sb : nullptr;
  if (faulted != nullptr) {
    faulted->phase = "FAULT";
    faulted->phase_color = RED;
  }
}
```

- [ ] **Step 4: Edit `display_ui.h` — `draw_fill`, `draw_pack_text`, `draw_ui`**

Replace `draw_fill()` and the comment block above it with:

```cpp
// The body in its state colour: one rectangle over the cylinder interior,
// drawn before the background, which keeps its grey top cap over row 40 and
// masks everything outside the bottom cap curve down to row 156.
inline void draw_fill(Display &it, const PackView &p) {
  if (p.filled) it.filled_rectangle(p.cx - 25, 40, 51, 116, p.phase_color);
}
```

Replace `draw_pack_text()` and its comment with:

```cpp
// The black plate, temperature, phase word and timer.
inline void draw_pack_text(Display &it, const UiAssets &a, const PackView &p) {
  rounded_rect(it, p.cx - 23, 78, 47, 52, 4, BLACK);
  if (std::isnan(p.t))
    it.print(p.cx, 100, a.f_temp, DIM, TextAlign::BASELINE_CENTER, "--°");
  else
    it.printf(p.cx, 100, a.f_temp, WHITE, TextAlign::BASELINE_CENTER, "%.0f°", p.t);
  if (p.phase[0] != '\0') it.print(p.cx, 112, a.f_phase, p.phase_color, TextAlign::BASELINE_CENTER, p.phase);
  if (p.show_timer) it.print(p.cx, 126, a.f_val, WHITE, TextAlign::BASELINE_CENTER, fmt_timer(p.timer_s).c_str());
}
```

Replace `draw_ui()` with:

```cpp
inline void draw_ui(Display &it, const UiState &s, const UiAssets &a) {
  it.fill(BLACK);
  PackView pa, pb;
  pack_roles(s, pa, pb);
  draw_fill(it, pa);
  draw_fill(it, pb);
  it.image(0, 0, a.bg);
  // Symbols follow the real output switches, not the state machine.
  if (s.valve_a)
    it.image(55, 154, a.lit_a);
  else if (s.valve_b)
    it.image(109, 154, a.lit_b);
  it.image(CX_A - 9, 158, s.valve_a ? a.valve_open : a.valve_closed);
  it.image(CX_B - 9, 158, s.valve_b ? a.valve_open : a.valve_closed);
  if (s.heater_a) it.image(17, 65, a.heater_on_a);
  if (s.heater_b) it.image(207, 65, a.heater_on_b);
  it.print(CX_A, 44, a.f_cap, WHITE, TextAlign::BASELINE_CENTER, "A", SHELL);
  it.print(CX_B, 44, a.f_cap, WHITE, TextAlign::BASELINE_CENTER, "B", SHELL);
  draw_pack_text(it, a, pa);
  draw_pack_text(it, a, pb);
  draw_gauge(it, a, s);
  draw_unit(it, a, s);
  it.image(209, 189, a.fan, s.fan ? GREEN : SHELL);
  draw_strip(it, a, s);
}
```

Then confirm nothing references removed names:

```bash
grep -n -E "cooldown|regen|overtemp|level_y|dashes|cap_blue|cap_amber|cap_gold|fault_ring|faulted\b|ORANGE_MID|DEEP|DARKOR|BLUE_L|BLUE_D|IN SERVICE" esphome/packages/display_ui.h
```

Expected: only the `fault_code` comment in `UiState` mentioning "overtemp" (`// 0 none, 1 active overtemp, 2 standby overtemp, 3 not heating`) and the local `faulted` pointer in `pack_roles`. Nothing else.

- [ ] **Step 5: Edit `display-draw.yaml`**

Delete these four entries from `image:` (everything from `- file: assets/display/fault-ring.svg` through the `img_cap_gold` entry's `resize: 51x12`), leaving `img_lit_b` followed directly by the `# Tinted at draw time...` comment and `mdi:fan` entry:

```yaml
  - file: assets/display/fault-ring.svg
    id: img_fault_ring
    type: RGB565
    transparency: alpha_channel
    resize: 57x122
  - file: assets/display/cap-blue.svg
    id: img_cap_blue
    type: RGB565
    transparency: alpha_channel
    resize: 51x12
  - file: assets/display/cap-amber.svg
    id: img_cap_amber
    type: RGB565
    transparency: alpha_channel
    resize: 51x12
  - file: assets/display/cap-gold.svg
    id: img_cap_gold
    type: RGB565
    transparency: alpha_channel
    resize: 51x12
```

In the `ui_draw` lambda delete the three lines:

```yaml
          s.cooldown = id(cooldown_temp).state;
          s.regen = id(regen_temp).state;
          s.overtemp = id(overtemp).state;
```

and replace the `dryer_ui::last_assets() = ...` statement (4 lines) with:

```yaml
          dryer_ui::last_assets() = dryer_ui::UiAssets{id(f_temp), id(f_val), id(f_cap), id(f_label), id(f_phase),
                                                       id(f_status), id(f_status_b),
                                                       id(img_bg), id(img_valve_open), id(img_valve_closed),
                                                       id(img_heater_on_a), id(img_heater_on_b), id(img_lit_a), id(img_lit_b),
                                                       id(img_fan)};
```

- [ ] **Step 6: Edit `display-scenarios.yaml`, `schematic.svg`; delete sprites**

In `esphome/packages/display-scenarios.yaml` delete the three template numbers `cooldown_temp`, `regen_temp` and `overtemp` (the blocks starting `- platform: template` / `name: "Cooldown temp"`, `name: "Regen temp"`, `name: "Pack overtemp limit"`). `arm_rh` and `swap_rh` stay. Do not touch the scenario table.

In `esphome/assets/display/schematic.svg` replace the comment on lines 2–4 with:

```xml
  <!-- Opaque black everywhere except the two cylinder interiors (columns
       35..85 and 155..205, rows 40 down to the bottom cap curve), which stay
       transparent so the state colour drawn underneath shows through. -->
```

Delete the sprites:

```bash
git rm esphome/assets/display/fault-ring.svg esphome/assets/display/cap-blue.svg esphome/assets/display/cap-amber.svg esphome/assets/display/cap-gold.svg
git grep -n -E "fault-ring|fault_ring|cap-blue|cap_blue|cap-amber|cap_amber|cap-gold|cap_gold" -- esphome
```

Expected: the grep prints nothing.

- [ ] **Step 7: Validate configs and diff against the baseline**

```bash
SCRATCH=/private/tmp/claude-501/-Users-josh-GitHub-desiccant-dryer--claude-worktrees-cylinder-state-colors-343ff1/166ee361-d09d-40a9-aed5-c0ead9321440/scratchpad/cfg
for y in desiccant-dryer desiccant-dryer-virtual desiccant-dryer-host desiccant-dryer-scenarios; do
  esphome config esphome/$y.yaml > $SCRATCH/$y-after.txt 2>$SCRATCH/$y-after.err; echo $y=$?
done
PY="$(dirname "$(readlink -f "$(which esphome)")")/python"
$PY scripts/normalize-config.py $SCRATCH/prod-before.txt > $SCRATCH/prod-before.json
$PY scripts/normalize-config.py $SCRATCH/desiccant-dryer-after.txt > $SCRATCH/prod-after.json
diff $SCRATCH/prod-before.json $SCRATCH/prod-after.json
$PY scripts/normalize-config.py $SCRATCH/scen-before.txt > $SCRATCH/scen-before.json
$PY scripts/normalize-config.py $SCRATCH/desiccant-dryer-scenarios-after.txt > $SCRATCH/scen-after.json
diff $SCRATCH/scen-before.json $SCRATCH/scen-after.json
```

Expected: all four exits `0` (if one fails, read its `.err`). The production diff shows only the four removed `image:` entries and the `ui_draw` lambda text. The scenarios diff shows the same plus the three removed `number:` entries. Anything else is a mistake; fix it before going on.

- [ ] **Step 8: Render the scenarios (the test)**

```bash
scripts/scenario-shots.sh
```

Expected: `wrote docs/display/state-01.png` … `state-12.png`, exit 0. This compiles the scenarios host build natively, so it also proves the header compiles (needs `brew install sdl2`, already present on this Mac).

Open every PNG with the Read tool and check against the spec and `docs/display/mockup-states.html`:

| # | Must show |
|---|---|
| 1 | Both bodies black (grey shell only), no phase words, no timers |
| 2 | A solid green `IN USE` `1h 02m`; B solid pink `WET` `1h 02m` |
| 3 | A green; B solid orange `HEATING` `12m`, heater glow right of B |
| 4 | B solid cyan `COOLING` |
| 5 | B solid blue `READY` |
| 6 | B orange `HEATING`, gauge `OVER`, strip ends `(waiting)` |
| 7 | B cyan `COOLING`, gauge `HIGH` |
| 8 | A solid orange `HEATING` with heater glow left of A; B green `IN USE`; path lit down B |
| 9 | A green `IN USE`; B solid red `FAULT` `124°`; red strip; no red ring |
| 10 | Both bodies black, `OFF` in dim on both, no timers |
| 11 | A green, B pink, strip `10.42.14.100` |
| 12 | A green; B solid orange with `--°` in dim; SIM badge |

In every filled cylinder also check: no fill colour above the grey top cap or outside the bottom cap curve; no leftover dashed lines; the black plate is intact. If anything is off, fix the header and re-run this step.

- [ ] **Step 9: Compile the live host build**

```bash
esphome compile esphome/desiccant-dryer-host.yaml > /private/tmp/claude-501/-Users-josh-GitHub-desiccant-dryer--claude-worktrees-cylinder-state-colors-343ff1/166ee361-d09d-40a9-aed5-c0ead9321440/scratchpad/cfg/host-compile.log 2>&1; echo host=$?
```

Expected: `host=0`. The ESP32 production and virtual builds are compiled by CI on the PR; do not flash any board.

- [ ] **Step 10: Commit**

```bash
git add esphome/packages/display_ui.h esphome/packages/display-draw.yaml esphome/packages/display-scenarios.yaml esphome/assets/display/schematic.svg docs/display/state-*.png
git status --short
git commit -m "Colour the display cylinders by pack state

Each cylinder body is one solid colour for its state: IN USE green,
WET pink, HEATING orange, COOLING cyan, READY blue, FAULT red; unfilled
when off or starting. Removes the temperature fill, threshold dashes,
cap sprites and fault ring, and the three thresholds only they read.
Scenario captures regenerated.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

Expected: `git status --short` before the commit lists only the files above plus the four deleted SVGs (already staged by `git rm`); `esphome/secrets.yaml` must not appear.

---

### Task 2: Docs follow the new cylinder design

**Files:**
- Modify: `docs/superpowers/specs/2026-09-14-display-ui-design.md` (after line 4)
- Modify: `docs/host-preview.md` (table rows at lines 50–55)
- Modify: `CLAUDE.md` (lines 51–52)

**Interfaces:**
- Consumes: the behaviour delivered by Task 1 (words `IN USE`/`FAULT`, colours, no fault ring).
- Produces: nothing code depends on.

- [ ] **Step 1: Mark the superseded parts of the display UI spec**

In `docs/superpowers/specs/2026-09-14-display-ui-design.md`, directly after the line `Status: approved in conversation; awaiting spec review`, insert:

```markdown
Amended by: `2026-09-14-cylinder-state-colours-design.md`. The cylinder
temperature fill, threshold dashes, cap sprites (`img_cap_*`), fault ring
(`img_fault_ring`), the `cooldown`/`regen`/`overtemp` inputs, and the phase
colours and words below are superseded: each cylinder body is now one solid
colour for its state (IN USE green, WET pink, HEATING orange, COOLING cyan,
READY blue, FAULT red). The rest of this document stands.
```

Leave the rest of that file unchanged.

- [ ] **Step 2: Update the host-preview screen-state table**

In `docs/host-preview.md`, replace these table rows:

```markdown
| A IN SERVICE (green), B WET, air path lit down the A branch | Fresh start |
| B HEATING in orange, heater glow beside B, fill rising | Sim Speed 60, wait about a minute |
| B COOLING (cyan), then READY (blue), then the path moves to B | Keep waiting |
```

with:

```markdown
| A IN USE (solid green), B WET (solid pink), air path lit down the A branch | Fresh start |
| B turns solid orange, HEATING, heater glow beside B | Sim Speed 60, wait about a minute |
| B turns cyan (COOLING), then blue (READY), then the path moves to B | Keep waiting |
```

and replace:

```markdown
| Red strip "FAULT · ...", red ring around the pack | Sim Heater Max Temp 130, wait for heating |
```

with:

```markdown
| Red strip "FAULT · ...", the faulted pack solid red | Sim Heater Max Temp 130, wait for heating |
```

- [ ] **Step 3: Point CLAUDE.md at both specs**

In `CLAUDE.md`, replace:

```markdown
into `docs/display/`. The screen design is in
`docs/superpowers/specs/2026-09-14-display-ui-design.md`. Base must only reference
```

with:

```markdown
into `docs/display/`. The screen design is in
`docs/superpowers/specs/2026-09-14-display-ui-design.md`, with the cylinders
coloured by state per `docs/superpowers/specs/2026-09-14-cylinder-state-colours-design.md`.
Base must only reference
```

- [ ] **Step 4: Check for stale wording and commit**

```bash
git grep -n -E "IN SERVICE|fill rising|red ring" -- CLAUDE.md docs/host-preview.md docs/virtual-testing.md docs/screen-in-ha.md README.md
```

Expected: no output. (Plans under `docs/superpowers/plans/` and the body of the old spec are historical and intentionally keep the old wording.)

```bash
git add docs/superpowers/specs/2026-09-14-display-ui-design.md docs/host-preview.md CLAUDE.md
git commit -m "Docs: cylinders are coloured by state

Marks the superseded parts of the display UI spec, updates the host
preview screen-state table, and points CLAUDE.md at the new spec.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```
