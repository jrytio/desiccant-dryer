# Display UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the placeholder text screen on the dryer's 240×240 ST7789 with the process-schematic UI from `docs/superpowers/specs/2026-09-14-display-ui-design.md`, and add a desktop preview build that renders the same code in an SDL window for screenshots.

**Architecture:** The drawing is a pure function `draw_ui(Display&, UiState, UiAssets)` in a C++ header with no `id()` calls. A shared ESPHome package (`display-ui.yaml`) owns the fonts, the SVG-derived images and a `ui_draw` script that gathers ids into `UiState` and calls the function. The ST7789 package and the new host/SDL preview package each have a one-line display lambda that executes the script. Static art is SVG rasterised at compile time into flash; live data (fills, gauge, text) is drawn with primitives.

**Tech Stack:** ESPHome 2026.1.4 (ESP-IDF on the S2; `host` platform + `sdl` display on macOS), resvg (bundled with ESPHome) for SVG, Google Fonts Barlow and Inter, `mdi:fan` icon, macOS `screencapture`.

## Global Constraints

- Every colour drawn is on the RGB 3-3-2 grid: R and G in {0,36,73,109,146,182,219,255}, B in {0,85,170,255}. The palette is fixed in the header; SVG files use the same hex values (spec §5).
- Display `color_palette: 8BIT` and `update_interval: 2s` are unchanged. No animation.
- The header contains no `id()` calls; only the `ui_draw` script touches ids.
- All `CLAUDE.md` invariants hold; in particular "SIM" shows whenever `sim_enabled` is on, and `time_scale` is untouched.
- Geometry is the table in spec §2. Cylinder A centre column is 60 (art drawn at x + 0.5), B is 180. Interior columns are cx−25 … cx+25 (51 px), body rows 40 … 150, fill region to row 156.
- No unit-test framework exists for ESPHome lambdas. Each task's test cycle is: `esphome config` (validates YAML, fetches fonts/icons, rasterises SVGs) and/or `esphome compile`, plus, once the preview exists, a screenshot compared against `docs/display/mockup-states.html`.
- The worktree has no `esphome/secrets.yaml`. Compile-only work uses the CI dummy: `cp esphome/secrets.ci.yaml esphome/secrets.yaml` (gitignored). Never copy or print the real one from the main checkout in this plan.
- Run everything from the repo root of the worktree: `/Users/josh/GitHub/desiccant-dryer/.claude/worktrees/desiccant-packs-ui-design-fcac02`.
- Commit messages end with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.

---

## File map

| File | Responsibility |
|---|---|
| `esphome/packages/base.yaml` (modify) | + `standby_elapsed_s`, `standby_state_seen`, transition detection in the tick, reset in `reset_regen_counters`, "Standby Phase Time" sensor |
| `esphome/packages/display_ui.h` (create) | `UiState`, `UiAssets`, palette, helpers, `draw_ui()` |
| `esphome/packages/display-ui.yaml` (create) | `esphome.includes`, fonts, images, `ui_draw` script |
| `esphome/packages/display.yaml` (modify) | SPI, backlight, ST7789 block only; lambda calls the script |
| `esphome/packages/display-preview.yaml` (create) | Stub entities, scenario table, SDL display |
| `esphome/desiccant-dryer-preview.yaml` (create) | Host top-level selector |
| `esphome/desiccant-dryer.yaml`, `esphome/desiccant-dryer-virtual.yaml` (modify) | add the `ui` package |
| `esphome/assets/display/*.svg` (create) | schematic, valves, heaters, lit paths, fault ring, fill caps |
| `scripts/preview-shots.sh` (create) | build the preview once, capture the twelve scenarios |
| `docs/display/state-NN.png` (create) | screenshots |
| `docs/control-logic.md`, `docs/virtual-testing.md`, `CLAUDE.md` (modify) | documentation |

---

### Task 1: Standby phase counter in the controller

**Files:**
- Modify: `esphome/packages/base.yaml` (globals after line 131, `reset_regen_counters` at line 485, tick at line 558, sensors after line 405)
- Modify: `docs/control-logic.md` (counter table line 28, Observability line 127)

**Interfaces:**
- Produces: global `standby_elapsed_s` (float, seconds in the current standby phase, persisted), global `standby_state_seen` (int), sensor id `standby_phase_min`. Task 2's script reads `id(standby_elapsed_s)`.

- [ ] **Step 1: Dummy secrets and a baseline config dump**

```bash
cp esphome/secrets.ci.yaml esphome/secrets.yaml
SCRATCH=/private/tmp/claude-501/-Users-josh-GitHub-desiccant-dryer--claude-worktrees-desiccant-packs-ui-design-fcac02/c58373fd-106e-4183-a5f5-27fa9ecc4965/scratchpad
esphome config esphome/desiccant-dryer.yaml > $SCRATCH/before.txt 2>/dev/null; echo exit=$?
```
Expected: `exit=0` and `$SCRATCH/before.txt` non-empty.

- [ ] **Step 2: Add the two globals**

In `esphome/packages/base.yaml`, directly after the `hold_elapsed_s` global (the block ending `initial_value: "0"` at line 131), insert:

```yaml
  # Time in the current standby phase (WET, HEATING, COOLING or READY). Reset
  # whenever standby_state changes, wherever the change was made; the display
  # shows it under the standby pack.
  - id: standby_elapsed_s
    type: float
    restore_value: true
    initial_value: "0"
  # standby_state at the previous tick, to detect the change. -1 = never seen.
  - id: standby_state_seen
    type: int
    restore_value: true
    initial_value: "-1"
```

- [ ] **Step 3: Reset it with the regen counters**

In the `reset_regen_counters` script lambda, after `id(hold_elapsed_s) = 0;` add:

```cpp
          id(standby_elapsed_s) = 0;
```

so the script reads:

```yaml
  - id: reset_regen_counters
    mode: single
    then:
      - lambda: |-
          id(heat_elapsed_s) = 0;
          id(hold_elapsed_s) = 0;
          id(standby_elapsed_s) = 0;
          id(heat_start_temp) = NAN;
```

- [ ] **Step 4: Count it in the tick**

In the 5 s `interval` lambda, directly after the line `const float dt = dt_real * id(time_scale);` insert:

```cpp

          // --- standby phase timer: reset on any standby_state change, no
          // matter which path made it (tick, do_swap, faults, disable).
          if (id(standby_state) != id(standby_state_seen)) {
            id(standby_state_seen) = id(standby_state);
            id(standby_elapsed_s) = 0;
          } else {
            id(standby_elapsed_s) += dt;
          }
```

- [ ] **Step 5: Expose it**

After the `hold_min` sensor (the block ending `update_interval: 10s` at line 405) insert:

```yaml

  - platform: template
    name: "Standby Phase Time"
    id: standby_phase_min
    unit_of_measurement: "min"
    accuracy_decimals: 1
    entity_category: diagnostic
    lambda: |-
      return id(standby_elapsed_s) / 60.0f;
    update_interval: 10s
```

- [ ] **Step 6: Document it**

In `docs/control-logic.md`, after the `hold_elapsed_s` row of the counter table add:

```markdown
| `standby_elapsed_s` | Time in the standby pack's current phase | any change of `standby_state` (detected at the top of the tick), plus everything that resets `heat_elapsed_s` |
```

In the Observability section, change the first sentence's list to include `Standby Phase Time` after `Regen Hold Time`, and append this sentence to that paragraph:

```markdown
`Standby Phase Time` is what the display shows under the standby pack; it
resets on every phase change, so after a swap it restarts from zero as WET.
```

- [ ] **Step 7: Validate and diff**

```bash
esphome config esphome/desiccant-dryer.yaml > $SCRATCH/after.txt 2>/dev/null; echo exit=$?
PY="$(dirname "$(readlink -f "$(which esphome)")")/python"
$PY scripts/normalize-config.py $SCRATCH/before.txt > $SCRATCH/before.json
$PY scripts/normalize-config.py $SCRATCH/after.txt > $SCRATCH/after.json
diff $SCRATCH/before.json $SCRATCH/after.json | head -80
esphome config esphome/desiccant-dryer-virtual.yaml > /dev/null 2>&1; echo virtual_exit=$?
```
Expected: both exits 0. The diff shows only the two globals, the one script line, the tick block, and the new sensor. Anything else is a mistake; fix before committing.

- [ ] **Step 8: Commit**

```bash
git add esphome/packages/base.yaml docs/control-logic.md
git commit -m "Count time in the current standby phase

Persisted standby_elapsed_s resets on any standby_state change, detected
generically at the top of the control tick, and with the regen counters.
Exposed as the Standby Phase Time diagnostic sensor for the display.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: Shared UI package, drawing header, display package split

**Files:**
- Create: `esphome/packages/display_ui.h`
- Create: `esphome/packages/display-ui.yaml`
- Modify: `esphome/packages/display.yaml` (whole file)
- Modify: `esphome/desiccant-dryer.yaml`, `esphome/desiccant-dryer-virtual.yaml`

**Interfaces:**
- Consumes: ids from `base.yaml` and the hardware packages: `active_pack`, `standby_state`, `fault_code`, `dryer_enabled`, `sim_enabled`, `case_fan`, `heater_a`, `heater_b`, `valve_a`, `valve_b`, `pack_a_temp`, `pack_b_temp`, `case_temp`, `ctrl_rh`, `arm_rh`, `swap_rh`, `cooldown_temp`, `regen_temp`, `overtemp`, `service_elapsed_s`, `standby_elapsed_s`, `status_text`, `fault_message`, `ip_addr`.
- Produces: `dryer_ui::UiState`, `dryer_ui::UiAssets` (fonts only in this task; Task 4 appends image pointers), `dryer_ui::draw_ui(Display&, const UiState&, const UiAssets&)`, script id `ui_draw`, display id `lcd`, font ids `f_temp f_val f_cap f_label f_phase f_status f_status_b`. Task 3's preview provides the same ids as stubs and calls the same script.

This task draws everything that needs no images: text, gauge, unit row, strip. Images (Task 4) and fills (Task 5) slot into `draw_ui` later.

- [ ] **Step 1: Write the header**

Create `esphome/packages/display_ui.h`:

```cpp
#pragma once
// Dryer display: a pure function of UiState. No id() calls in here, so the
// same code draws the ST7789 (packages/display.yaml) and the SDL preview
// window (packages/display-preview.yaml). Geometry and rules follow
// docs/superpowers/specs/2026-09-14-display-ui-design.md sections 2, 4, 5.
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <string>

#include "esphome/components/display/display.h"

namespace dryer_ui {

using esphome::Color;
using esphome::display::BaseFont;
using esphome::display::BaseImage;
using esphome::display::Display;
using esphome::display::TextAlign;

struct UiState {
  int active = 0;         // 0 none, 1 A, 2 B
  int standby_state = 0;  // 0 WET, 1 HEATING, 2 COOLING, 3 READY
  int fault_code = 0;     // 0 none, 1 active overtemp, 2 standby overtemp, 3 not heating
  bool enabled = true, sim = false, fan = false;
  bool heater_a = false, heater_b = false, valve_a = false, valve_b = false;
  float t_a = NAN, t_b = NAN, t_case = NAN, rh = NAN;
  float arm_rh = 5, swap_rh = 10, cooldown = 40, regen = 90, overtemp = 120;
  float service_s = 0, standby_s = 0;
  std::string status, fault_msg, ip;
  uint32_t uptime_ms = 0;
};

// Aggregate-initialised by the ui_draw script; keep the member order in step.
struct UiAssets {
  BaseFont *f_temp, *f_val, *f_cap, *f_label, *f_phase, *f_status, *f_status_b;
};

// RGB 3-3-2 grid colours (spec section 5).
static const Color BLACK(0, 0, 0), WHITE(255, 255, 255);
static const Color GREEN(36, 219, 85), ORANGE(255, 146, 0), AMBER(255, 182, 0), ORANGE_MID(255, 109, 0);
static const Color DEEP(219, 73, 0), DARKOR(182, 73, 0), CYAN(0, 219, 255);
static const Color BLUE(36, 109, 255), BLUE_L(73, 146, 255), BLUE_D(0, 73, 170);
static const Color SHELL(73, 73, 85), DIM(146, 146, 170), STRIP_TXT(182, 182, 170);
static const Color RED_STRIP(219, 36, 36), RED(255, 36, 36);
static const Color DRY_DIM(36, 109, 36), AMBER_DIM(109, 73, 0), RED_DIM(109, 0, 0);

static const float HIGH_FRACTION = 1.0f / 3.0f;  // top third of the arm..swap band reads HIGH
static const uint32_t BOOT_IP_MS = 60000;        // the strip shows the IP this long after boot
static const int CX_A = 60, CX_B = 180;          // cylinder centre columns (art sits at cx + 0.5)

// What one cylinder shows, derived from UiState by pack_roles().
struct PackView {
  int cx = 0;
  float t = NAN;
  const char *phase = "";
  Color phase_color = DIM;
  bool show_timer = false;
  float timer_s = 0;
  bool faulted = false;
};

inline std::string fmt_timer(float seconds) {
  int m = (int) (seconds / 60.0f);
  if (m < 0) m = 0;
  char buf[16];
  if (m >= 60)
    snprintf(buf, sizeof buf, "%dh %02dm", m / 60, m % 60);
  else
    snprintf(buf, sizeof buf, "%dm", m);
  return buf;
}

inline void rounded_rect(Display &it, int x, int y, int w, int h, int r, Color c) {
  it.filled_rectangle(x + r, y, w - 2 * r, h, c);
  it.filled_rectangle(x, y + r, w, h - 2 * r, c);
  it.filled_circle(x + r, y + r, r, c);
  it.filled_circle(x + w - 1 - r, y + r, r, c);
  it.filled_circle(x + r, y + h - 1 - r, r, c);
  it.filled_circle(x + w - 1 - r, y + h - 1 - r, r, c);
}

// 2 px on, 3 px off, from x0 to x1 exclusive.
inline void dashes(Display &it, int x0, int x1, int y, Color c) {
  for (int x = x0; x < x1; x += 5) it.horizontal_line(x, y, 2, c);
}

// Row of the fill's top edge: 20 C .. overtemp maps onto the 110 px body.
inline int level_y(float t, float overtemp) {
  float f = (t - 20.0f) / (overtemp - 20.0f);
  if (f < 0) f = 0;
  if (f > 1) f = 1;
  return 150 - (int) lroundf(f * 110.0f);
}

inline void pack_roles(const UiState &s, PackView &a, PackView &b) {
  static const char *const SB_NAMES[] = {"WET", "HEATING", "COOLING", "READY"};
  static const Color SB_COLORS[] = {DIM, ORANGE, CYAN, BLUE};
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
  act.phase = "IN SERVICE";
  act.phase_color = GREEN;
  act.show_timer = true;
  act.timer_s = s.service_s;
  int st = s.standby_state;
  if (st < 0 || st > 3) st = 0;
  sb.phase = SB_NAMES[st];
  sb.phase_color = SB_COLORS[st];
  sb.show_timer = true;
  sb.timer_s = s.standby_s;
  PackView *faulted = s.fault_code == 1 ? &act : (s.fault_code == 2 || s.fault_code == 3) ? &sb : nullptr;
  if (faulted != nullptr) {
    faulted->phase = "FAULT";
    faulted->phase_color = RED;
    faulted->faulted = true;
  }
}

// Threshold dashes, the black plate, temperature, phase word and timer.
inline void draw_pack_text(Display &it, const UiAssets &a, const UiState &s, const PackView &p) {
  const int x0 = p.cx - 25, x1 = p.cx + 26;
  dashes(it, x0, x1, level_y(s.regen, s.overtemp), DARKOR);
  const bool cool = std::isnan(p.t) || p.t <= s.cooldown;
  dashes(it, x0, x1, level_y(s.cooldown, s.overtemp), cool ? BLUE_D : BLUE_L);
  rounded_rect(it, p.cx - 20, 78, 41, 52, 4, BLACK);
  if (std::isnan(p.t))
    it.print(p.cx, 100, a.f_temp, DIM, TextAlign::BASELINE_CENTER, "--°");
  else
    it.printf(p.cx, 100, a.f_temp, WHITE, TextAlign::BASELINE_CENTER, "%.0f°", p.t);
  if (p.phase[0] != '\0') it.print(p.cx, 112, a.f_phase, p.phase_color, TextAlign::BASELINE_CENTER, p.phase);
  if (p.show_timer) it.print(p.cx, 126, a.f_val, WHITE, TextAlign::BASELINE_CENTER, fmt_timer(p.timer_s).c_str());
}

// Outlet humidity: value, zone word, three-zone bar with a marker.
inline void draw_gauge(Display &it, const UiAssets &a, const UiState &s) {
  const float arm = s.arm_rh, swap = s.swap_rh, end = swap * 1.25f;
  const char *zone = "";
  Color zc = DIM;
  int z = -1;  // 0 DRY, 1 RISING/HIGH, 2 OVER
  if (!std::isnan(s.rh)) {
    if (s.rh < arm) {
      zone = "DRY"; zc = GREEN; z = 0;
    } else if (s.rh < swap - (swap - arm) * HIGH_FRACTION) {
      zone = "RISING"; zc = AMBER; z = 1;
    } else if (s.rh < swap) {
      zone = "HIGH"; zc = AMBER; z = 1;
    } else {
      zone = "OVER"; zc = RED; z = 2;
    }
  }
  if (std::isnan(s.rh))
    it.print(118, 204, a.f_val, DIM, TextAlign::BASELINE_RIGHT, "--% RH");
  else
    it.printf(118, 204, a.f_val, WHITE, TextAlign::BASELINE_RIGHT, "%.1f%% RH", s.rh);
  it.print(124, 204, a.f_phase, zc, TextAlign::BASELINE_LEFT, zone);
  const int x0 = 70, w = 100;
  int xa = x0 + (int) lroundf(w * arm / end);
  int xs = x0 + (int) lroundf(w * swap / end);
  if (xa > xs) xa = xs;  // arm above swap is a misconfiguration; keep the bar drawable
  it.filled_rectangle(x0, 208, xa - x0, 5, z == 0 ? GREEN : DRY_DIM);
  it.filled_rectangle(xa, 208, xs - xa, 5, z == 1 ? AMBER : AMBER_DIM);
  it.filled_rectangle(xs, 208, x0 + w - xs, 5, z == 2 ? RED : RED_DIM);
  if (!std::isnan(s.rh)) {
    float f = s.rh / end;
    if (f < 0) f = 0;
    if (f > 1) f = 1;
    it.filled_rectangle(x0 + (int) lroundf(w * f) - 1, 206, 2, 9, WHITE);
  }
}

// Labels, case temperature, fan label and the SIM badge. The fan icon itself
// is an image and is drawn by draw_ui.
inline void draw_unit(Display &it, const UiAssets &a, const UiState &s) {
  it.print(112, 11, a.f_label, DIM, TextAlign::BASELINE_RIGHT, "WET AIR");
  it.print(6, 196, a.f_label, DIM, TextAlign::BASELINE_LEFT, "CASE");
  if (std::isnan(s.t_case))
    it.print(6, 209, a.f_val, DIM, TextAlign::BASELINE_LEFT, "--°");
  else
    it.printf(6, 209, a.f_val, WHITE, TextAlign::BASELINE_LEFT, "%.0f°", s.t_case);
  it.print(216, 211, a.f_label, DIM, TextAlign::BASELINE_CENTER, "FAN");
  if (s.sim) {
    rounded_rect(it, 210, 4, 22, 12, 2, AMBER);
    it.print(221, 13, a.f_phase, BLACK, TextAlign::BASELINE_CENTER, "SIM", AMBER);
  }
}

// Bottom strip: fault (red), else the IP for the first minute, else status.
inline void draw_strip(Display &it, const UiAssets &a, const UiState &s) {
  if (s.fault_code != 0) {
    it.filled_rectangle(0, 214, 240, 26, RED_STRIP);
    std::string msg = "FAULT · " + s.fault_msg;
    it.print(120, 231, a.f_status_b, BLACK, TextAlign::BASELINE_CENTER, msg.c_str(), RED_STRIP);
    return;
  }
  it.horizontal_line(0, 214, 240, SHELL);
  const bool boot = s.uptime_ms < BOOT_IP_MS && !s.ip.empty();
  it.print(120, 231, a.f_status, STRIP_TXT, TextAlign::BASELINE_CENTER, boot ? s.ip.c_str() : s.status.c_str());
}

inline void draw_ui(Display &it, const UiState &s, const UiAssets &a) {
  it.fill(BLACK);
  PackView pa, pb;
  pack_roles(s, pa, pb);
  draw_pack_text(it, a, s, pa);
  draw_pack_text(it, a, s, pb);
  draw_gauge(it, a, s);
  draw_unit(it, a, s);
  draw_strip(it, a, s);
}

}  // namespace dryer_ui
```

- [ ] **Step 2: Write the shared UI package**

Create `esphome/packages/display-ui.yaml`:

```yaml
# Display UI shared by the ST7789 build (display.yaml) and the desktop
# preview (display-preview.yaml): fonts, image assets and the ui_draw script.
# The script is the only place that reads ids; it fills a UiState and hands it
# to draw_ui() in display_ui.h, which draws into whichever display has id
# `lcd`. Both display blocks' lambdas are just `id(ui_draw).execute();`.
#
# Assets under assets/display are SVG, rasterised at compile time by ESPHome
# (resvg) into flash. Fonts come from Google Fonts at compile time. Every
# colour used here and in the header is on the display's RGB 3-3-2 grid.

esphome:
  includes:
    - packages/display_ui.h

font:
  - file: "gfonts://Barlow@700"
    id: f_temp
    size: 24
    bpp: 4
    glyphs: "0123456789-°"
  - file: "gfonts://Barlow@600"
    id: f_val
    size: 12
    bpp: 4
    glyphs: "0123456789.%-°hm RH"
  - file: "gfonts://Barlow@700"
    id: f_cap
    size: 11
    bpp: 4
    glyphs: "AB"
  - file: "gfonts://Inter@600"
    id: f_label
    size: 8
    bpp: 4
    glyphs: " ABCDEFGHIJKLMNOPQRSTUVWXYZ"
  - file: "gfonts://Inter@700"
    id: f_phase
    size: 8
    bpp: 4
    glyphs: " ABCDEFGHIJKLMNOPQRSTUVWXYZ"
  - file: "gfonts://Inter@500"
    id: f_status
    size: 10
    bpp: 4
    glyphs: " !\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~°·"
  - file: "gfonts://Inter@700"
    id: f_status_b
    size: 10
    bpp: 4
    glyphs: " !\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~°·"

script:
  - id: ui_draw
    mode: single
    then:
      - lambda: |-
          dryer_ui::UiState s;
          s.active = id(active_pack);
          s.standby_state = id(standby_state);
          s.fault_code = id(fault_code);
          s.enabled = id(dryer_enabled).state;
          s.sim = id(sim_enabled).state;
          s.fan = id(case_fan).state;
          s.heater_a = id(heater_a).state;
          s.heater_b = id(heater_b).state;
          s.valve_a = id(valve_a).state;
          s.valve_b = id(valve_b).state;
          s.t_a = id(pack_a_temp).state;
          s.t_b = id(pack_b_temp).state;
          s.t_case = id(case_temp).state;
          s.rh = id(ctrl_rh).state;
          s.arm_rh = id(arm_rh).state;
          s.swap_rh = id(swap_rh).state;
          s.cooldown = id(cooldown_temp).state;
          s.regen = id(regen_temp).state;
          s.overtemp = id(overtemp).state;
          s.service_s = id(service_elapsed_s);
          s.standby_s = id(standby_elapsed_s);
          s.status = id(status_text).state;
          s.fault_msg = id(fault_message).state;
          s.ip = id(ip_addr).state;
          s.uptime_ms = millis();
          dryer_ui::UiAssets a{id(f_temp), id(f_val), id(f_cap), id(f_label), id(f_phase),
                               id(f_status), id(f_status_b)};
          dryer_ui::draw_ui(*id(lcd), s, a);
```

- [ ] **Step 3: Trim the hardware display package**

Replace the whole of `esphome/packages/display.yaml` with:

```yaml
# ST7789 1.54" 240x240 display on SPI: the hardware half of the display. The
# drawing itself lives in display-ui.yaml + display_ui.h so the same code also
# runs in the desktop preview (desiccant-dryer-preview.yaml). On the virtual
# build nothing is attached; the driver still runs so the frame buffer
# allocation on the S2 gets exercised.
#   GPIO36/35 SPI SCK/MOSI, GPIO5 CS, GPIO9 DC, GPIO14 RST, GPIO17 backlight

spi:
  clk_pin: GPIO36
  mosi_pin: GPIO35

output:
  - platform: ledc
    pin: GPIO17
    id: backlight_pwm
    frequency: 1000Hz

light:
  - platform: monochromatic
    name: "Display Backlight"
    output: backlight_pwm
    restore_mode: RESTORE_DEFAULT_ON
    default_transition_length: 0s

display:
  - platform: ili9xxx
    id: lcd
    model: ST7789V
    dimensions:
      height: 240
      width: 240
      offset_height: 0     # try 80 if the image is shifted / cropped
      offset_width: 0
    cs_pin: GPIO5
    dc_pin: GPIO9
    reset_pin: GPIO14
    invert_colors: true    # most 1.54" IPS modules need this
    # 8-bit palette halves the frame buffer to ~58 KB. The full 16-bit buffer
    # (~115 KB) failed to allocate on the S2 with WiFi, API and web server up
    # (seen on the first virtual-build flash: "Could not allocate buffer").
    color_palette: 8BIT
    update_interval: 2s
    auto_clear_enabled: false   # draw_ui() fills the frame itself
    lambda: |-
      id(ui_draw).execute();
```

- [ ] **Step 4: Add the package to both selectors**

In `esphome/desiccant-dryer.yaml` and `esphome/desiccant-dryer-virtual.yaml`, add a line to the `packages:` map after `display:`:

```yaml
  ui: !include packages/display-ui.yaml
```

Also update the comment in `esphome/desiccant-dryer.yaml` so the header reads:

```yaml
# Production build: real sensors on the SparkFun ESP32-S2 Thing Plus.
# Flash:  esphome run esphome/desiccant-dryer.yaml
# Logic:  packages/base.yaml       (shared with the virtual build)
# Wiring: packages/hw-real.yaml    (the only file the hardware side needs)
# Screen: packages/display.yaml    (ST7789 wiring) + display-ui.yaml (drawing)
```

- [ ] **Step 5: Validate both ESP builds**

```bash
esphome config esphome/desiccant-dryer.yaml > /dev/null; echo prod_exit=$?
esphome config esphome/desiccant-dryer-virtual.yaml > /dev/null; echo virt_exit=$?
```
Expected: both `0`. Font downloads happen here; a network failure shows as `Could not download font`; retry.

- [ ] **Step 6: Compile the virtual build**

```bash
esphome compile esphome/desiccant-dryer-virtual.yaml 2>&1 | tail -15
```
Expected: ends with `Successfully created esp32 image` (or the RAM/Flash summary and `[SUCCESS]`). Takes 2–5 min with the cached toolchain. A compile error in `display_ui.h` shows the line; fix and re-run.

- [ ] **Step 7: Commit**

```bash
git add esphome/packages/display_ui.h esphome/packages/display-ui.yaml esphome/packages/display.yaml esphome/desiccant-dryer.yaml esphome/desiccant-dryer-virtual.yaml
git commit -m "Split the display into hardware and drawing packages

display.yaml keeps the ST7789 wiring; display-ui.yaml owns fonts and a
ui_draw script that gathers ids into a UiState and calls draw_ui() in
display_ui.h, which has no id() calls so it can also run on the host.
Draws the text, gauge, unit row and status strip of the new schematic;
art and fills follow.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: Desktop preview build

**Files:**
- Create: `esphome/desiccant-dryer-preview.yaml`
- Create: `esphome/packages/display-preview.yaml`
- Create: `scripts/preview-shots.sh`

**Interfaces:**
- Consumes: script `ui_draw` and fonts from `display-ui.yaml`; the id list from Task 2.
- Produces: display id `lcd` on the host; the twelve-row scenario table (spec §7) selected by `SCENARIO=n`; PNGs at `docs/display/state-NN.png`.

- [ ] **Step 1: Check the host toolchain**

```bash
sdl2-config --version && xcode-select -p
```
Expected: an SDL version (2.32.x) and `/Library/Developer/CommandLineTools` (or an Xcode path). If `sdl2-config` is missing: `brew install sdl2`.

- [ ] **Step 2: Write the top-level preview file**

Create `esphome/desiccant-dryer-preview.yaml`:

```yaml
# Desktop preview of the display: runs display_ui.h in an SDL window on the
# Mac with stub entities instead of the controller, so every screen state can
# be checked and screenshotted without a board.
#   esphome compile esphome/desiccant-dryer-preview.yaml
#   SCENARIO=3 esphome/.esphome/build/desiccant-dryer-preview/.pioenvs/desiccant-dryer-preview/program
# Or all twelve at once: scripts/preview-shots.sh. Needs `brew install sdl2`.
substitutions:
  name: desiccant-dryer-preview
  friendly_name: Desiccant Dryer Preview

esphome:
  name: ${name}
  friendly_name: ${friendly_name}

host:

logger:
  level: INFO

packages:
  ui: !include packages/display-ui.yaml
  preview: !include packages/display-preview.yaml
```

- [ ] **Step 3: Write the stub package**

Create `esphome/packages/display-preview.yaml`:

```yaml
# Host-only stand-ins for everything the ui_draw script reads, under the same
# ids as base.yaml and the hardware packages, plus an SDL window in place of
# the ST7789. No state machine runs here: on boot a scenario table sets every
# input directly. Pick one with SCENARIO=n (1..12, default 3) in the
# environment of the built binary. Rows match docs/display/mockup-states.html.

globals:
  - id: active_pack
    type: int
    initial_value: "0"
  - id: standby_state
    type: int
    initial_value: "0"
  - id: fault_code
    type: int
    initial_value: "0"
  - id: service_elapsed_s
    type: float
    initial_value: "0"
  - id: standby_elapsed_s
    type: float
    initial_value: "0"

switch:
  - platform: template
    name: "Dryer Enabled"
    id: dryer_enabled
    optimistic: true
    restore_mode: ALWAYS_OFF
  - platform: template
    name: "Simulate Humidity"
    id: sim_enabled
    optimistic: true
    restore_mode: ALWAYS_OFF
  - platform: template
    name: "Case Fan"
    id: case_fan
    optimistic: true
    restore_mode: ALWAYS_OFF
  - platform: template
    name: "Heater A"
    id: heater_a
    optimistic: true
    restore_mode: ALWAYS_OFF
  - platform: template
    name: "Heater B"
    id: heater_b
    optimistic: true
    restore_mode: ALWAYS_OFF
  - platform: template
    name: "Valve A"
    id: valve_a
    optimistic: true
    restore_mode: ALWAYS_OFF
  - platform: template
    name: "Valve B"
    id: valve_b
    optimistic: true
    restore_mode: ALWAYS_OFF

number:
  - platform: template
    name: "Arm RH"
    id: arm_rh
    min_value: 0.5
    max_value: 50
    step: 0.5
    initial_value: 5
    optimistic: true
  - platform: template
    name: "Swap RH"
    id: swap_rh
    min_value: 1
    max_value: 60
    step: 0.5
    initial_value: 10
    optimistic: true
  - platform: template
    name: "Cooldown temp"
    id: cooldown_temp
    min_value: 20
    max_value: 80
    step: 1
    initial_value: 40
    optimistic: true
  - platform: template
    name: "Regen temp"
    id: regen_temp
    min_value: 40
    max_value: 120
    step: 1
    initial_value: 90
    optimistic: true
  - platform: template
    name: "Pack overtemp limit"
    id: overtemp
    min_value: 60
    max_value: 125
    step: 1
    initial_value: 120
    optimistic: true

sensor:
  - platform: template
    name: "Control Humidity"
    id: ctrl_rh
    update_interval: never
  - platform: template
    name: "Pack A Temperature"
    id: pack_a_temp
    update_interval: never
  - platform: template
    name: "Pack B Temperature"
    id: pack_b_temp
    update_interval: never
  - platform: template
    name: "Case Temperature"
    id: case_temp
    update_interval: never

text_sensor:
  - platform: template
    name: "Dryer Status"
    id: status_text
    update_interval: never
  - platform: template
    name: "Fault Message"
    id: fault_message
    update_interval: never
  - platform: template
    name: "IP Address"
    id: ip_addr
    update_interval: never

esphome:
  on_boot:
    # After every component above exists; the numbers have published their
    # initial values by then.
    priority: -100
    then:
      - lambda: |-
          struct Sc {
            int active, sb, fault;
            bool enabled, sim, fan, ha, hb, va, vb;
            float ta, tb, tc, rh, service_s, standby_s;
            const char *status, *fault_msg, *ip;
          };
          // Same twelve rows as docs/display/mockup-states.html.
          static const Sc SC[12] = {
            {0, 0, 0, true,  false, false, false, false, false, false, 24,  24,  24, 1.1f,     0,    0, "Starting", "", ""},
            {1, 0, 0, true,  false, false, false, false, true,  false, 26,  25,  27, 2.4f,  3720, 3720, "Air via A, B wet", "", ""},
            {1, 1, 0, true,  false, true,  false, true,  true,  false, 31,  87,  31, 6.8f,  8040,  720, "Air via A, B heating", "", ""},
            {1, 2, 0, true,  false, true,  false, false, true,  false, 33,  62,  33, 7.9f,  9660,  540, "Air via A, B cooling", "", ""},
            {1, 3, 0, true,  false, true,  false, false, true,  false, 34,  38,  32, 8.6f, 10680,  360, "Air via A, B ready", "", ""},
            {1, 1, 0, true,  false, true,  false, true,  true,  false, 35,  71,  32, 11.2f, 11100,  480, "Air via A, B heating (waiting)", "", ""},
            {1, 2, 0, true,  false, true,  false, false, true,  false, 35,  48,  32, 9.1f, 11100,  840, "Air via A, B cooling", "", ""},
            {2, 1, 0, true,  false, true,  true,  false, false, true,  94,  29,  30, 5.6f,  6000,  900, "Air via B, A heating", "", ""},
            {1, 2, 2, true,  false, true,  false, false, true,  false, 33, 124,  36, 6.1f,  8400, 1080, "Air via A, B cooling", "Standby pack overtemp", ""},
            {0, 0, 0, false, false, false, false, false, false, false, 28,  45,  26, 3.0f,     0,    0, "Disabled", "", ""},
            {1, 0, 0, true,  false, false, false, false, true,  false, 25,  25,  25, 2.0f,     0,    0, "Air via A, B wet", "", "198.51.100.200"},
            {1, 1, 0, true,  true,  false, false, false, true,  false, 30, NAN,  29, 6.0f,  2640,  180, "Air via A, B heating", "", ""},
          };
          int n = 3;
          if (const char *e = std::getenv("SCENARIO")) n = atoi(e);
          if (n < 1 || n > 12) n = 3;
          const Sc &c = SC[n - 1];
          ESP_LOGI("preview", "Scenario %d: %s", n, c.status);
          id(active_pack) = c.active;
          id(standby_state) = c.sb;
          id(fault_code) = c.fault;
          id(service_elapsed_s) = c.service_s;
          id(standby_elapsed_s) = c.standby_s;
          auto set = [](esphome::switch_::Switch *sw, bool on) { if (on) sw->turn_on(); else sw->turn_off(); };
          set(id(dryer_enabled), c.enabled);
          set(id(sim_enabled), c.sim);
          set(id(case_fan), c.fan);
          set(id(heater_a), c.ha);
          set(id(heater_b), c.hb);
          set(id(valve_a), c.va);
          set(id(valve_b), c.vb);
          id(pack_a_temp).publish_state(c.ta);
          id(pack_b_temp).publish_state(c.tb);
          id(case_temp).publish_state(c.tc);
          id(ctrl_rh).publish_state(c.rh);
          id(status_text).publish_state(c.status);
          id(fault_message).publish_state(c.fault_msg);
          id(ip_addr).publish_state(c.ip);

display:
  - platform: sdl
    id: lcd
    dimensions:
      width: 240
      height: 240
    update_interval: 1s
    auto_clear_enabled: false
    window_options:
      position:
        x: 100
        y: 100
      borderless: true
      always_on_top: true
    lambda: |-
      id(ui_draw).execute();
```

- [ ] **Step 4: Validate and compile the preview**

```bash
esphome config esphome/desiccant-dryer-preview.yaml > /dev/null; echo exit=$?
esphome compile esphome/desiccant-dryer-preview.yaml 2>&1 | tail -12
ls -la esphome/.esphome/build/desiccant-dryer-preview/.pioenvs/desiccant-dryer-preview/program
```
Expected: exit 0, compile ends in `[SUCCESS]`, and the `program` binary exists. If the binary is elsewhere, find it with `find esphome/.esphome/build/desiccant-dryer-preview -name program -type f` and use that path in Step 6. If `std::getenv` fails to compile, add `#include <cstdlib>` at the top of the lambda.

- [ ] **Step 5: Run one scenario by hand**

```bash
SCENARIO=3 esphome/.esphome/build/desiccant-dryer-preview/.pioenvs/desiccant-dryer-preview/program & pid=$!
sleep 4; screencapture -x -R 100,100,240,240 $SCRATCH/preview-3.png; kill $pid
```
(`$SCRATCH` is the scratchpad directory named in Task 1 Step 1.)
Expected: a borderless 240×240 window appeared at (100,100) with text and the gauge on black (no art yet), and `$SCRATCH/preview-3.png` shows it. If macOS asks for Screen Recording permission for the terminal, grant it and rerun. If the capture shows the desktop instead of the window, the window position differs; check with a full-screen `screencapture -x /tmp/full.png` and adjust `position` in the yaml.

- [ ] **Step 6: Write the screenshot script**

Create `scripts/preview-shots.sh` (then `chmod +x`):

```bash
#!/usr/bin/env bash
# Build the desktop display preview once, then capture every scenario into
# docs/display/state-NN.png. macOS only (screencapture); needs brew sdl2.
# Usage: scripts/preview-shots.sh [first] [last]     (default 1 12)
set -euo pipefail
cd "$(dirname "$0")/.."
first=${1:-1}
last=${2:-12}
X=100; Y=100   # must match window_options.position in packages/display-preview.yaml

esphome compile esphome/desiccant-dryer-preview.yaml > /dev/null
BIN=esphome/.esphome/build/desiccant-dryer-preview/.pioenvs/desiccant-dryer-preview/program
[ -x "$BIN" ] || { echo "preview binary not found at $BIN" >&2; exit 1; }
mkdir -p docs/display

for n in $(seq "$first" "$last"); do
  out=docs/display/state-$(printf %02d "$n").png
  SCENARIO=$n "$BIN" > /dev/null 2>&1 &
  pid=$!
  sleep 4
  screencapture -x -R "$X,$Y,240,240" "$out"
  kill "$pid" 2>/dev/null || true
  wait "$pid" 2>/dev/null || true
  echo "wrote $out"
done
```

- [ ] **Step 7: Run it for two scenarios and check**

```bash
chmod +x scripts/preview-shots.sh
scripts/preview-shots.sh 3 3 && scripts/preview-shots.sh 9 9
```
Expected: `wrote docs/display/state-03.png` and `state-09.png`. Open both (Read tool). Scenario 3 shows `31°` / `87°`, IN SERVICE and HEATING words, `6.8% RH RISING`, the gauge and the status line. Scenario 9 shows a red strip reading `FAULT · Standby pack overtemp` and FAULT under pack B.

- [ ] **Step 8: Commit (no PNGs yet)**

```bash
git add esphome/desiccant-dryer-preview.yaml esphome/packages/display-preview.yaml scripts/preview-shots.sh
git commit -m "Add a host/SDL preview build for the display

Stub entities under the controller's ids, a twelve-row scenario table
picked by SCENARIO=n, and scripts/preview-shots.sh to capture them all.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 4: SVG art and sprites

**Files:**
- Create: `esphome/assets/display/schematic.svg`, `valve-open.svg`, `valve-closed.svg`, `heater-on-a.svg`, `heater-on-b.svg`, `lit-a.svg`, `lit-b.svg`, `fault-ring.svg`, `cap-blue.svg`, `cap-amber.svg`, `cap-gold.svg`
- Modify: `esphome/packages/display-ui.yaml` (add `image:`, extend the script's `UiAssets`)
- Modify: `esphome/packages/display_ui.h` (`UiAssets`, `draw_ui`)

**Interfaces:**
- Consumes: `draw_ui`, `UiAssets` from Task 2.
- Produces: image ids `img_bg img_valve_open img_valve_closed img_heater_on_a img_heater_on_b img_lit_a img_lit_b img_fault_ring img_cap_blue img_cap_amber img_cap_gold img_fan`; `UiAssets` gains members `bg, valve_open, valve_closed, heater_on_a, heater_on_b, lit_a, lit_b, fault_ring, cap_blue, cap_amber, cap_gold, fan` in that order after the fonts. Task 5 uses `cap_*`.

Coordinates in the SVGs are screen coordinates for `schematic.svg`; sprites are in their own box and the header draws them at the offsets listed in spec §3.

- [ ] **Step 1: The background**

Create `esphome/assets/display/schematic.svg`:

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="240" height="240" viewBox="0 0 240 240">
  <!-- Opaque black everywhere except the two cylinder interiors (columns
       35..85 and 155..205, rows 40 down to the bottom cap curve), which stay
       transparent so the temperature fill drawn underneath shows through. -->
  <path fill="#000000" fill-rule="evenodd"
        d="M0 0H240V240H0Z M35 40H86V150A25.5 6 0 0 1 35 150Z M155 40H206V150A25.5 6 0 0 1 155 150Z"/>
  <!-- pipes: inlet stub and manifold, inlet branches, outlet branches and manifold -->
  <path d="M120.5 2V24 M59 22.5H182 M60.5 22.5V40 M180.5 22.5V40 M60.5 156V178 M180.5 156V178 M59 176.5H182"
        stroke="#494955" stroke-width="3" fill="none"/>
  <path d="M116.5 14L120.5 19L124.5 14" stroke="#9292AA" stroke-width="1.5" fill="none"/>
  <!-- cylinder shells: sides, lower arc of the bottom cap, filled top cap -->
  <g stroke="#494955" fill="none">
    <path d="M34.5 40V150 M86.5 40V150 M154.5 40V150 M206.5 40V150"/>
    <path d="M34.5 150A26 6 0 0 0 86.5 150 M154.5 150A26 6 0 0 0 206.5 150"/>
  </g>
  <ellipse cx="60.5" cy="40" rx="26" ry="6" fill="#494955"/>
  <ellipse cx="180.5" cy="40" rx="26" ry="6" fill="#494955"/>
  <!-- heater elements in the off state, B the mirror of A -->
  <path d="M22 70L30 78L22 86L30 94L22 102L30 110L22 118 M218 70L210 78L218 86L210 94L218 102L210 110L218 118"
        stroke="#494955" stroke-width="2" fill="none" stroke-linejoin="round"/>
  <!-- sensor node on the outlet manifold, stem and arrow -->
  <circle cx="120.5" cy="176.5" r="6" fill="#000000" stroke="#494955" stroke-width="1.5"/>
  <path d="M120.5 182V190" stroke="#494955" stroke-width="3" fill="none"/>
  <path d="M116.5 187L120.5 192L124.5 187" stroke="#494955" stroke-width="1.5" fill="none"/>
</svg>
```

- [ ] **Step 2: Valve sprites** (19×17, drawn at (cx−9, 158); the pipe through the sprite is at x 9.5)

`esphome/assets/display/valve-open.svg`:

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="19" height="17" viewBox="0 0 19 17">
  <path d="M9.5 0V17" stroke="#24DB55" stroke-width="3" fill="none"/>
  <path d="M2 2.5L9.5 8.5L2 14.5Z M17 2.5L9.5 8.5L17 14.5Z" fill="#24DB55"/>
</svg>
```

`esphome/assets/display/valve-closed.svg`:

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="19" height="17" viewBox="0 0 19 17">
  <path d="M9.5 0V17" stroke="#494955" stroke-width="3" fill="none"/>
  <path d="M2 2.5L9.5 8.5L2 14.5Z M17 2.5L9.5 8.5L17 14.5Z" fill="#000000" stroke="#9292AA" stroke-width="1.2" stroke-linejoin="round"/>
</svg>
```

- [ ] **Step 3: Heater glow sprites** (16×56, drawn at (17,65) and (207,65))

`esphome/assets/display/heater-on-a.svg`:

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="16" height="56" viewBox="0 0 16 56">
  <path d="M5 5L13 13L5 21L13 29L5 37L13 45L5 53" stroke="#B64900" stroke-width="5" fill="none" stroke-linejoin="round" stroke-linecap="round"/>
  <path d="M5 5L13 13L5 21L13 29L5 37L13 45L5 53" stroke="#FFB600" stroke-width="2" fill="none" stroke-linejoin="round"/>
</svg>
```

`esphome/assets/display/heater-on-b.svg`:

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="16" height="56" viewBox="0 0 16 56">
  <path d="M11 5L3 13L11 21L3 29L11 37L3 45L11 53" stroke="#B64900" stroke-width="5" fill="none" stroke-linejoin="round" stroke-linecap="round"/>
  <path d="M11 5L3 13L11 21L3 29L11 37L3 45L11 53" stroke="#FFB600" stroke-width="2" fill="none" stroke-linejoin="round"/>
</svg>
```

- [ ] **Step 4: Lit path sprites** (76×42, drawn at (55,154) and (109,154))

`esphome/assets/display/lit-a.svg`:

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="76" height="42" viewBox="0 0 76 42">
  <path d="M5.5 2V24 M4 22.5H66" stroke="#24DB55" stroke-width="3" fill="none"/>
  <circle cx="65.5" cy="22.5" r="6" fill="#000000" stroke="#24DB55" stroke-width="1.5"/>
  <path d="M65.5 28V36" stroke="#24DB55" stroke-width="3" fill="none"/>
  <path d="M61.5 33L65.5 38L69.5 33" stroke="#24DB55" stroke-width="1.5" fill="none"/>
</svg>
```

`esphome/assets/display/lit-b.svg`:

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="76" height="42" viewBox="0 0 76 42">
  <path d="M71.5 2V24 M11 22.5H73" stroke="#24DB55" stroke-width="3" fill="none"/>
  <circle cx="11.5" cy="22.5" r="6" fill="#000000" stroke="#24DB55" stroke-width="1.5"/>
  <path d="M11.5 28V36" stroke="#24DB55" stroke-width="3" fill="none"/>
  <path d="M7.5 33L11.5 38L15.5 33" stroke="#24DB55" stroke-width="1.5" fill="none"/>
</svg>
```

- [ ] **Step 5: Fault ring** (57×122, drawn at (cx−28, 34))

`esphome/assets/display/fault-ring.svg`:

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="57" height="122" viewBox="0 0 57 122">
  <g stroke="#FF2424" stroke-width="1.5" fill="none">
    <path d="M2.5 6V116 M54.5 6V116"/>
    <ellipse cx="28.5" cy="6" rx="26" ry="6"/>
    <path d="M2.5 116A26 6 0 0 0 54.5 116"/>
  </g>
</svg>
```

- [ ] **Step 6: Fill caps** (51×12, drawn at (cx−25, level−6))

`esphome/assets/display/cap-blue.svg`:

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="51" height="12" viewBox="0 0 51 12">
  <ellipse cx="25.5" cy="6" rx="25.5" ry="6" fill="#4992FF"/>
</svg>
```

`esphome/assets/display/cap-amber.svg`:

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="51" height="12" viewBox="0 0 51 12">
  <ellipse cx="25.5" cy="6" rx="25.5" ry="6" fill="#FFB600"/>
</svg>
```

`esphome/assets/display/cap-gold.svg`:

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="51" height="12" viewBox="0 0 51 12">
  <ellipse cx="25.5" cy="6" rx="25.5" ry="6" fill="#FFDB55"/>
</svg>
```

- [ ] **Step 7: Register the images**

In `esphome/packages/display-ui.yaml`, after the `font:` section and before `script:`, add:

```yaml
image:
  - file: assets/display/schematic.svg
    id: img_bg
    type: RGB565
    transparency: alpha_channel
    resize: 240x240
  - file: assets/display/valve-open.svg
    id: img_valve_open
    type: RGB565
    transparency: alpha_channel
    resize: 19x17
  - file: assets/display/valve-closed.svg
    id: img_valve_closed
    type: RGB565
    transparency: alpha_channel
    resize: 19x17
  - file: assets/display/heater-on-a.svg
    id: img_heater_on_a
    type: RGB565
    transparency: alpha_channel
    resize: 16x56
  - file: assets/display/heater-on-b.svg
    id: img_heater_on_b
    type: RGB565
    transparency: alpha_channel
    resize: 16x56
  - file: assets/display/lit-a.svg
    id: img_lit_a
    type: RGB565
    transparency: alpha_channel
    resize: 76x42
  - file: assets/display/lit-b.svg
    id: img_lit_b
    type: RGB565
    transparency: alpha_channel
    resize: 76x42
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
  # Tinted at draw time: green when the fan runs, shell grey otherwise.
  - file: mdi:fan
    id: img_fan
    type: BINARY
    transparency: chroma_key
    resize: 14x14
```

And replace the two `UiAssets` lines in the script with:

```cpp
          dryer_ui::UiAssets a{id(f_temp), id(f_val), id(f_cap), id(f_label), id(f_phase),
                               id(f_status), id(f_status_b),
                               id(img_bg), id(img_valve_open), id(img_valve_closed),
                               id(img_heater_on_a), id(img_heater_on_b), id(img_lit_a), id(img_lit_b),
                               id(img_fault_ring), id(img_cap_blue), id(img_cap_amber), id(img_cap_gold),
                               id(img_fan)};
```

- [ ] **Step 8: Extend the header**

In `esphome/packages/display_ui.h`, replace the `UiAssets` struct with:

```cpp
// Aggregate-initialised by the ui_draw script; keep the member order in step.
struct UiAssets {
  BaseFont *f_temp, *f_val, *f_cap, *f_label, *f_phase, *f_status, *f_status_b;
  BaseImage *bg, *valve_open, *valve_closed, *heater_on_a, *heater_on_b, *lit_a, *lit_b, *fault_ring,
      *cap_blue, *cap_amber, *cap_gold, *fan;
};
```

and replace `draw_ui` with (fills are still absent; Task 5 adds them where the comment says):

```cpp
inline void draw_ui(Display &it, const UiState &s, const UiAssets &a) {
  it.fill(BLACK);
  PackView pa, pb;
  pack_roles(s, pa, pb);
  // Task 5: fills go here, under the background.
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
  if (pa.faulted) it.image(CX_A - 28, 34, a.fault_ring);
  if (pb.faulted) it.image(CX_B - 28, 34, a.fault_ring);
  it.print(CX_A, 44, a.f_cap, WHITE, TextAlign::BASELINE_CENTER, "A", SHELL);
  it.print(CX_B, 44, a.f_cap, WHITE, TextAlign::BASELINE_CENTER, "B", SHELL);
  draw_pack_text(it, a, s, pa);
  draw_pack_text(it, a, s, pb);
  draw_gauge(it, a, s);
  draw_unit(it, a, s);
  it.image(209, 189, a.fan, s.fan ? GREEN : SHELL);
  draw_strip(it, a, s);
}
```

- [ ] **Step 9: Validate, compile the preview, look**

```bash
esphome config esphome/desiccant-dryer-preview.yaml > /dev/null; echo exit=$?
scripts/preview-shots.sh 3 3 && scripts/preview-shots.sh 8 8 && scripts/preview-shots.sh 9 9
```
Expected: exit 0 (the `mdi:fan` download and the SVG rasterisation happen here). Open the three PNGs. Scenario 3: grey pipes and shells, green lit path down the A branch to the node and out the bottom, green open valve on A, grey closed valve on B, amber glowing zigzag beside B, green fan. Scenario 8: the mirror (B lit, A glowing). Scenario 9: red ring around B, red strip. If a sprite is offset from the pipe by a pixel, adjust its draw coordinate in `draw_ui`, not the SVG.

- [ ] **Step 10: Validate and compile an ESP build**

```bash
esphome config esphome/desiccant-dryer.yaml > /dev/null; echo exit=$?
esphome compile esphome/desiccant-dryer-virtual.yaml 2>&1 | grep -E "RAM|Flash|SUCCESS|error" | tail -5
```
Expected: exit 0, `[SUCCESS]`, Flash usage up by roughly 230 KB versus Task 2 (background 173 KB plus sprites), RAM unchanged.

- [ ] **Step 11: Commit**

```bash
git add esphome/assets/display esphome/packages/display-ui.yaml esphome/packages/display_ui.h
git commit -m "Draw the schematic from SVG sprites

Background with pipes and shells, valve, heater-glow, lit-path and
fault-ring sprites rasterised at compile time, plus the mdi fan icon.
Symbols follow the real output switches.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 5: Temperature fills

**Files:**
- Modify: `esphome/packages/display_ui.h` (add `draw_fill`, call it from `draw_ui`)

**Interfaces:**
- Consumes: `UiAssets.cap_blue/cap_amber/cap_gold`, `level_y`, `PackView` from Tasks 2 and 4.
- Produces: `draw_fill(Display&, const UiAssets&, const UiState&, const PackView&)`.

- [ ] **Step 1: Add draw_fill**

In `esphome/packages/display_ui.h`, insert this function directly before `draw_pack_text`:

```cpp
// Stacked colour bands from the level down to row 156, then the cap sprite
// on the level. Drawn before the background, whose opaque corners mask the
// bands outside the bottom cap curve. Blue family at or below cooldown,
// orange above, with an amber top band and gold cap at or above regen.
inline void draw_fill(Display &it, const UiAssets &a, const UiState &s, const PackView &p) {
  if (std::isnan(p.t)) return;
  const int x0 = p.cx - 25;
  const int top = level_y(p.t, s.overtemp);
  Color bands[4];
  int n = 0;
  BaseImage *cap;
  if (p.t <= s.cooldown) {
    bands[n++] = BLUE;
    bands[n++] = BLUE_D;
    cap = a.cap_blue;
  } else {
    if (p.t >= s.regen) bands[n++] = AMBER;
    bands[n++] = ORANGE;
    bands[n++] = ORANGE_MID;
    bands[n++] = DEEP;
    cap = p.t >= s.regen ? a.cap_gold : a.cap_amber;
  }
  int h = (156 - top) / n;
  if (h < 6) h = 6;
  int y = top;
  for (int i = 0; i < n; i++) {
    const int hh = (i == n - 1) ? 156 - y : h;
    if (hh > 0) it.filled_rectangle(x0, y, 51, hh, bands[i]);
    y += h;
  }
  it.image(x0, top - 6, cap);
}
```

- [ ] **Step 2: Call it**

In `draw_ui`, replace the line `// Task 5: fills go here, under the background.` with:

```cpp
  draw_fill(it, a, s, pa);
  draw_fill(it, a, s, pb);
```

- [ ] **Step 3: Look at the cool, hot, ready and NaN cases**

```bash
scripts/preview-shots.sh 2 5 && scripts/preview-shots.sh 12 12
```
Expected, comparing with `docs/display/mockup-states.html`: scenario 2 shows a low blue fill with a light-blue top ellipse in both cylinders; 3 shows B filled orange to just below the regen dash with a gold cap; 4 orange lower; 5 both blue with READY in blue; 12 pack B empty with `--°`. The fill must stop exactly at the shell walls and follow the bottom cap curve; if a band shows outside the shell, the hole path in `schematic.svg` and `x0`/width 51 disagree.

- [ ] **Step 4: Compile an ESP build and commit**

```bash
esphome compile esphome/desiccant-dryer-virtual.yaml 2>&1 | grep -E "SUCCESS|error" | tail -3
git add esphome/packages/display_ui.h
git commit -m "Fill the cylinders with pack temperature

Banded fill from 20 C to the overtemp limit, blue at or below cooldown,
orange above, amber band and gold cap at or above regen temperature.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 6: All twelve screenshots, docs, final checks

**Files:**
- Create: `docs/display/state-01.png` … `state-12.png`
- Modify: `CLAUDE.md`, `docs/virtual-testing.md`

**Interfaces:**
- Consumes: everything above.

- [ ] **Step 1: Capture the full set and compare**

```bash
scripts/preview-shots.sh
ls -la docs/display/*.png | wc -l
```
Expected: 12 files. Open each and compare against the matching tile in `docs/display/mockup-states.html`. Check specifically: 1 has no roles, timers or lit path; 6 shows OVER in red with the red zone bright; 7 shows HIGH; 10 shows OFF on both packs, both valves closed, no fan; 11's strip reads `198.51.100.200`; 12 shows the SIM badge. Fix any mismatch in the header or SVGs, re-run the affected scenario, and repeat until they match.

- [ ] **Step 2: Compile both ESP builds one last time**

```bash
esphome compile esphome/desiccant-dryer.yaml 2>&1 | grep -E "RAM|Flash|SUCCESS|error" | tail -4
esphome compile esphome/desiccant-dryer-virtual.yaml 2>&1 | grep -E "RAM|Flash|SUCCESS|error" | tail -4
```
Expected: both `[SUCCESS]`. Note the Flash figures for the PR description.

- [ ] **Step 3: CLAUDE.md**

In `CLAUDE.md`, "Layout and pin map" section, replace the sentence that starts `Two builds share one logic file via ESPHome packages:` through `are ten-line selectors.` with:

```markdown
Two builds share one logic file via ESPHome packages: `esphome/packages/base.yaml`
(platform, globals, tunables, GPIO outputs, state machine, derived entities),
`packages/hw-real.yaml` (buses and real sensors; the hardware side edits only
this), `packages/hw-virtual.yaml` (plant model and sim knobs),
`packages/display.yaml` (ST7789 wiring) and `packages/display-ui.yaml` (fonts,
SVG sprites from `esphome/assets/display/`, and the `ui_draw` script that
feeds `packages/display_ui.h`, where all drawing lives with no `id()` calls).
`desiccant-dryer.yaml` and `desiccant-dryer-virtual.yaml` are ten-line
selectors. A third, `desiccant-dryer-preview.yaml`, runs only the display
code on the Mac (ESPHome `host` platform, SDL window, stub entities in
`packages/display-preview.yaml`); `scripts/preview-shots.sh` captures its
twelve scenarios into `docs/display/`. The screen design is in
`docs/superpowers/specs/2026-09-14-display-ui-design.md`.
```

In "Working conventions", add a bullet after the `esphome config` diff bullet:

```markdown
- Any display change: run `scripts/preview-shots.sh` (needs `brew install sdl2`)
  and check the PNGs in `docs/display/` before flashing. The preview renders
  true colour; the real panel snaps to the RGB 3-3-2 grid, which every
  designed colour already sits on.
```

- [ ] **Step 4: virtual-testing.md**

Append to `docs/virtual-testing.md`:

```markdown

## Desktop display preview

`esphome/desiccant-dryer-preview.yaml` runs the display drawing code on the
Mac in a 240×240 SDL window, with stub entities in place of the controller.
It needs `brew install sdl2` and the Xcode command line tools.

```bash
scripts/preview-shots.sh          # build once, capture scenarios 1..12 to docs/display/
scripts/preview-shots.sh 6 6      # just one
```

To watch a scenario live:

```bash
esphome compile esphome/desiccant-dryer-preview.yaml
SCENARIO=6 esphome/.esphome/build/desiccant-dryer-preview/.pioenvs/desiccant-dryer-preview/program
```

The scenario table is in `packages/display-preview.yaml` and matches the
tiles in `docs/display/mockup-states.html`. The first `screencapture` may
prompt for Screen Recording permission for your terminal. The preview is
not validated in CI: the `sdl` component needs `sdl2-config` at config time,
which the ESPHome Docker image lacks.
```

- [ ] **Step 5: Normalised config diff against the merge base**

```bash
SCRATCH=/private/tmp/claude-501/-Users-josh-GitHub-desiccant-dryer--claude-worktrees-desiccant-packs-ui-design-fcac02/c58373fd-106e-4183-a5f5-27fa9ecc4965/scratchpad
PY="$(dirname "$(readlink -f "$(which esphome)")")/python"
git fetch origin
git worktree add $SCRATCH/main-wt origin/main > /dev/null 2>&1   # never stash in this repo
cp esphome/secrets.ci.yaml $SCRATCH/main-wt/esphome/secrets.yaml
(cd $SCRATCH/main-wt && esphome config esphome/desiccant-dryer.yaml > $SCRATCH/main.txt 2>/dev/null)
esphome config esphome/desiccant-dryer.yaml > $SCRATCH/head.txt 2>/dev/null
$PY scripts/normalize-config.py $SCRATCH/main.txt > $SCRATCH/main.json
$PY scripts/normalize-config.py $SCRATCH/head.txt > $SCRATCH/head.json
diff $SCRATCH/main.json $SCRATCH/head.json | grep -v '"display"\|font\|image\|ui_draw\|f_\|img_' | head -60
git worktree remove --force $SCRATCH/main-wt
```
Expected: outside the display, font, image and script sections, only the Task 1 additions.

- [ ] **Step 6: Commit**

```bash
git add docs/display/*.png CLAUDE.md docs/virtual-testing.md
git commit -m "Display preview screenshots and docs

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

- [ ] **Step 7: Report**

Summarise for the user: the twelve screenshots, the Flash delta, and the one step still waiting on their go-ahead: flashing the virtual build to the bench board to confirm the frame buffer still allocates and to read the display component's loop-time warnings (the board is running the overnight soak).

---

## Execution notes (2026-09-14)

Two deviations from the plan as written, both in Task 3:

- **Capture is in-process, not `screencapture`.** The terminal had no Screen
  Recording permission, so `screencapture` failed for every region. Instead
  `packages/preview_capture.h` provides a `CaptureDisplay` that snaps each
  pixel to the RGB 3-3-2 palette and writes a PPM; `display-preview.yaml`
  renders into it when `SHOT=<file>` is set and exits. The `ui_draw` script
  keeps the last state and asset table in `dryer_ui::last_state()` /
  `last_assets()` (function-local statics; custom-typed `globals` did not
  work because the include is emitted after the globals in main.cpp).
  `scripts/preview-shots.sh` converts the PPM to a 2x nearest-neighbour PNG
  with ESPHome's bundled Pillow. The window position options are now
  irrelevant to the script but harmless.
- **Boot-IP uptime is measured from the first frame.** Host `millis()` counts
  from machine boot, so `UiState.uptime_ms` is now
  `dryer_ui::uptime_since_first_frame(millis())`, about 2 s after boot on
  the device.

Also: the temperature plate was widened from 41 to 47 px in Task 4 so
three-digit readings such as `124°` stay on it.

## Rebased onto PRs #4 and #5 (2026-09-15)

Those PRs landed first with their own package layout, so this branch was
rebuilt on top of it. File mapping from the plan's names:

| Plan | Landed |
|---|---|
| `packages/display-ui.yaml` | `packages/display-draw.yaml` (their file; `display_lambda` now runs `ui_draw`) |
| `packages/display.yaml` edits | `packages/display-st7789.yaml` (`auto_clear_enabled: false`; display id is `panel`) and `packages/display-sdl.yaml` (`id: panel`, same flag) |
| `desiccant-dryer-preview.yaml`, `packages/display-preview.yaml` | `desiccant-dryer-scenarios.yaml`, `packages/display-scenarios.yaml` (reuses `display-sdl.yaml`) |
| `scripts/preview-shots.sh` | `scripts/scenario-shots.sh` |
| selector edits | none needed: the selectors already include `display-draw.yaml` |

The full-firmware host build from PR #4 shows the new screen live; the
screen mirror from PR #5 serves it from the ST7789 buffer unchanged.
