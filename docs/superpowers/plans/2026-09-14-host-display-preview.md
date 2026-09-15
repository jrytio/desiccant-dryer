# Host Display Preview Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a third ESPHome build that compiles the dryer firmware natively for the Mac and renders the display into an SDL window, so the screen can be iterated without flashing a board, while leaving the two device builds byte-for-byte equivalent.

**Architecture:** ESPHome packages. Platform-specific blocks (board, WiFi, OTA, web server, WiFi sensors) move out of `base.yaml` into `platform-esp32.yaml`, with a `platform-host.yaml` counterpart. `display.yaml` splits into `display-draw.yaml` (fonts, colours, and the drawing lambda held in a substitution named `display_lambda`) and `display-st7789.yaml` (the panel driver); a new `display-sdl.yaml` draws the same substitution into a window. A new selector `desiccant-dryer-host.yaml` combines base, platform-host, hw-virtual, display-draw and display-sdl.

**Tech Stack:** ESPHome 2026.1.4 (host platform, `sdl` display), SDL2 2.32.8 from Homebrew, Home Assistant native API, GitHub Actions running the `ghcr.io/esphome/esphome:2026.1.4` image.

**Spec:** `docs/superpowers/specs/2026-09-14-host-display-preview-design.md`

## Global Constraints

- Work in the worktree `/Users/josh/GitHub/desiccant-dryer/.claude/worktrees/display-mirroring-laptop-c13ab1` on branch `claude/display-mirroring-laptop-c13ab1`. Never `cd` to the main checkout. Never use bare `git stash`.
- ESPHome version: 2026.1.4 locally (`esphome` is on PATH) and in CI. SDL2 is installed by Homebrew; `sdl2-config` is on PATH.
- The two device builds (`esphome/desiccant-dryer.yaml`, `esphome/desiccant-dryer-virtual.yaml`) must produce normalised `esphome config` dumps identical to the baseline captured in Task 1. That is the acceptance test for Tasks 2 and 3.
- Board block, pin map, entity names, control logic, plant model and every invariant in `CLAUDE.md` are unchanged. Text moved between files is moved verbatim, comments included.
- Device names: production `desiccant-dryer` / `Desiccant Dryer`; virtual `desiccant-dryer-virtual` / `Desiccant Dryer (Virtual)`; host `desiccant-dryer-host` / `Desiccant Dryer (Host)`.
- The substitution holding the drawing lambda is named `display_lambda`. Ids `f_big`, `f_med`, `f_small`, `c_white`, `c_grey`, `c_green`, `c_orange`, `c_red`, `c_blue`, `ip_addr` keep their names.
- On the host platform `wifi`, `captive_portal`, `web_server`, `wifi_signal`, `wifi_info`, `ota`, `ledc`, `spi`, `ili9xxx` and `logger.hardware_uart` are unavailable; none of them may appear in the host build.
- Baseline and scratch files go in `.superpowers/baseline/` inside the worktree (gitignored). macOS has no `timeout` command.
- The host binary block-buffers stdout when it is not a terminal, so a timed run must go through a pseudo-terminal (the Python snippet in Task 4). Run it with the sandbox disabled so SDL can reach the window server.
- `esphome/secrets.yaml` is gitignored. Copy it from the main checkout if present (it holds the real API key Home Assistant already knows); never print or commit it. Otherwise copy `esphome/secrets.ci.yaml`.
- Commit messages end with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`. The PR description ends with `🤖 Generated with [Claude Code](https://claude.com/claude-code)`.

## File map

| Path | Responsibility | Task |
|---|---|---|
| `.superpowers/baseline/` | Baseline config dumps and normalised JSON for the equivalence test | 1 |
| `esphome/packages/platform-esp32.yaml` | Board, logger UART, OTA, WiFi + AP, captive portal, web server, WiFi Signal, IP Address | 2 |
| `esphome/packages/base.yaml` | Controller only after Task 2: on_boot, api, log level, globals, tunables, outputs, buttons, derived entities, thermostat, scripts, tick | 2 |
| `esphome/desiccant-dryer.yaml`, `esphome/desiccant-dryer-virtual.yaml` | Selectors; gain the platform package (2) and the two display packages (3) | 2, 3 |
| `esphome/packages/display-draw.yaml` | Fonts, colours, `display_lambda` substitution | 3 |
| `esphome/packages/display-st7789.yaml` | SPI, backlight, ili9xxx panel using `${display_lambda}` | 3 |
| `esphome/packages/display.yaml` | Deleted | 3 |
| `esphome/packages/platform-host.yaml` | `host:` block, internal `ip_addr` template | 4 |
| `esphome/packages/display-sdl.yaml` | SDL window using `${display_lambda}` | 4 |
| `esphome/desiccant-dryer-host.yaml` | Host selector | 4 |
| `docs/host-preview.md` | How to run, pair, reset, and what the preview cannot show | 5 |
| `CLAUDE.md`, `README.md`, `docs/hardware-bringup.md`, `docs/virtual-testing.md` | Layout, commands, renamed file references | 5 |
| `.github/workflows/build.yml` | Adds the `compile-host` job | 6 |

---

### Task 1: Secrets and baseline capture

**Files:**
- Create: `esphome/secrets.yaml` (gitignored, copied)
- Create: `.superpowers/baseline/baseline-prod.txt`, `baseline-virt.txt`, `baseline-prod.json`, `baseline-virt.json` (gitignored)

**Interfaces:**
- Consumes: the committed device selectors as of commit `509b7d1`.
- Produces: `.superpowers/baseline/baseline-prod.json` and `baseline-virt.json`, which Tasks 2 and 3 diff against.

- [ ] **Step 1: Put a secrets file in place**

```bash
cd /Users/josh/GitHub/desiccant-dryer/.claude/worktrees/display-mirroring-laptop-c13ab1 && if [ -f /Users/josh/GitHub/desiccant-dryer/esphome/secrets.yaml ]; then cp /Users/josh/GitHub/desiccant-dryer/esphome/secrets.yaml esphome/secrets.yaml && echo "copied real secrets"; else cp esphome/secrets.ci.yaml esphome/secrets.yaml && echo "copied CI dummy secrets"; fi; git status --short esphome/secrets.yaml; echo "(empty status line above = gitignored, good)"
```

Expected: one of the two "copied" lines, and no `??` entry for the secrets file.

- [ ] **Step 2: Dump both device configs**

```bash
cd /Users/josh/GitHub/desiccant-dryer/.claude/worktrees/display-mirroring-laptop-c13ab1 && mkdir -p .superpowers/baseline && B=.superpowers/baseline && esphome config esphome/desiccant-dryer.yaml > $B/baseline-prod.txt 2>&1 && esphome config esphome/desiccant-dryer-virtual.yaml > $B/baseline-virt.txt 2>&1 && echo DUMPED && grep -c "platform: ili9xxx" $B/baseline-prod.txt $B/baseline-virt.txt
```

Expected: `DUMPED`, then `1` for each file. If `esphome config` fails, the tail of the `.txt` file has the reason; the most likely one is a missing secret key.

- [ ] **Step 3: Normalise the baselines**

```bash
cd /Users/josh/GitHub/desiccant-dryer/.claude/worktrees/display-mirroring-laptop-c13ab1 && B=.superpowers/baseline && PY="$(dirname "$(readlink -f "$(which esphome)")")/python" && $PY scripts/normalize-config.py $B/baseline-prod.txt > $B/baseline-prod.json && $PY scripts/normalize-config.py $B/baseline-virt.txt > $B/baseline-virt.json && wc -l $B/baseline-prod.json $B/baseline-virt.json
```

Expected: two line counts in the thousands, no traceback. Nothing to commit.

---

### Task 2: Move the platform blocks out of base.yaml

**Files:**
- Create: `esphome/packages/platform-esp32.yaml`
- Modify: `esphome/packages/base.yaml` (header comment lines 1-4; platform blocks lines 62-93; `wifi_signal` sensor lines 392-394; `wifi_info` text sensor lines 405-408)
- Modify: `esphome/desiccant-dryer.yaml`, `esphome/desiccant-dryer-virtual.yaml`

**Interfaces:**
- Consumes: the baseline JSON from Task 1.
- Produces: `platform-esp32.yaml` providing `esp32`, `logger.hardware_uart`, `ota`, `wifi`, `captive_portal`, `web_server`, the `WiFi Signal` sensor and the `ip_addr` text sensor. `base.yaml` no longer defines any of them but still reads `id(ip_addr)` nowhere itself (only the display does). Selectors list `platform:` between `base:` and `hardware:`.

- [ ] **Step 1: Create `esphome/packages/platform-esp32.yaml`**

```yaml
# ESP32-S2 platform: board, serial logging, OTA, WiFi, captive portal and
# the web server. Shared by the production and virtual builds; the host
# preview build uses packages/platform-host.yaml instead. No control logic
# lives here.

esp32:
  board: sparkfun_esp32s2_thing_plus   # if rejected, esp32-s2-saola-1 works (same module)
  variant: esp32s2
  framework:
    type: esp-idf

logger:
  # The S2 Thing Plus's USB port is a CP2102 on UART0. ESPHome's S2 default
  # is USB_CDC, which is the bare native-USB pins on this board, so nothing
  # would ever reach `esphome logs` over the cable. The log level is set in
  # base.yaml; ESPHome merges the two logger blocks.
  hardware_uart: UART0

ota:
  - platform: esphome
    password: !secret ota_password

wifi:
  ssid: !secret wifi_ssid
  password: !secret wifi_password
  ap:
    ssid: "${friendly_name} Setup"
    password: !secret ap_password

captive_portal:

web_server:
  port: 80

sensor:
  - platform: wifi_signal
    name: "WiFi Signal"
    update_interval: 60s

text_sensor:
  - platform: wifi_info
    ip_address:
      name: "IP Address"
      id: ip_addr
```

- [ ] **Step 2: Update the header comment of `esphome/packages/base.yaml`**

Replace the first four lines:

```
# Shared base for both builds. The top-level file supplies ${name} and
# ${friendly_name} and picks a hardware package (hw-real or hw-virtual)
# plus display. This file must only reference these sensor ids from the
# hardware package: air_rh, air_temp, pack_a_temp, pack_b_temp, case_temp.
```

with:

```
# Shared controller for every build. The top-level file supplies ${name}
# and ${friendly_name} and picks a platform package (platform-esp32 or
# platform-host), a hardware package (hw-real or hw-virtual) and the
# display packages. This file must only reference these sensor ids from
# the hardware package: air_rh, air_temp, pack_a_temp, pack_b_temp,
# case_temp. Board, WiFi, OTA and the web server live in the platform
# package, not here.
```

- [ ] **Step 3: Remove the platform blocks from `esphome/packages/base.yaml`**

Replace this block (it starts right after the `on_boot` lambda and ends before `# ---------------------------------------------------------------- globals`):

```yaml
esp32:
  board: sparkfun_esp32s2_thing_plus   # if rejected, esp32-s2-saola-1 works (same module)
  variant: esp32s2
  framework:
    type: esp-idf

logger:
  level: INFO
  # The S2 Thing Plus's USB port is a CP2102 on UART0. ESPHome's S2 default
  # is USB_CDC, which is the bare native-USB pins on this board, so nothing
  # would ever reach `esphome logs` over the cable.
  hardware_uart: UART0

api:
  encryption:
    key: !secret api_key

ota:
  - platform: esphome
    password: !secret ota_password

wifi:
  ssid: !secret wifi_ssid
  password: !secret wifi_password
  ap:
    ssid: "${friendly_name} Setup"
    password: !secret ap_password

captive_portal:

web_server:
  port: 80
```

with:

```yaml
logger:
  level: INFO

api:
  encryption:
    key: !secret api_key
```

- [ ] **Step 4: Remove the WiFi entities from `esphome/packages/base.yaml`**

In the `sensor:` list, delete these three lines (the `uptime` sensor after them stays):

```yaml
  - platform: wifi_signal
    name: "WiFi Signal"
    update_interval: 60s
```

In the `text_sensor:` list, delete these four lines (the `# Single place the fault code becomes text` comment and the `Fault Message` sensor after them stay):

```yaml
  - platform: wifi_info
    ip_address:
      name: "IP Address"
      id: ip_addr
```

- [ ] **Step 5: Add the platform package to both selectors**

`esphome/desiccant-dryer.yaml` becomes:

```yaml
# Production build: real sensors on the SparkFun ESP32-S2 Thing Plus.
# Flash:  esphome run esphome/desiccant-dryer.yaml
# Logic:  packages/base.yaml           (shared with the virtual and host builds)
# Board:  packages/platform-esp32.yaml (board, WiFi, OTA, web server)
# Wiring: packages/hw-real.yaml        (the only file the hardware side needs)
substitutions:
  name: desiccant-dryer
  friendly_name: Desiccant Dryer

packages:
  base: !include packages/base.yaml
  platform: !include packages/platform-esp32.yaml
  hardware: !include packages/hw-real.yaml
  display: !include packages/display.yaml
```

`esphome/desiccant-dryer-virtual.yaml` becomes:

```yaml
# Virtual build: same board, nothing attached. Sensors come from the plant
# model in packages/hw-virtual.yaml; outputs, interlocks, display and all
# control logic are the production ones. Appears in Home Assistant as a
# separate device so it can never be mistaken for the real unit.
# Flash:  esphome run esphome/desiccant-dryer-virtual.yaml
# Tests:  docs/virtual-testing.md
substitutions:
  name: desiccant-dryer-virtual
  friendly_name: Desiccant Dryer (Virtual)

packages:
  base: !include packages/base.yaml
  platform: !include packages/platform-esp32.yaml
  hardware: !include packages/hw-virtual.yaml
  display: !include packages/display.yaml
```

- [ ] **Step 6: Prove both device builds are unchanged**

```bash
cd /Users/josh/GitHub/desiccant-dryer/.claude/worktrees/display-mirroring-laptop-c13ab1 && B=.superpowers/baseline && PY="$(dirname "$(readlink -f "$(which esphome)")")/python" && for v in prod:desiccant-dryer virt:desiccant-dryer-virtual; do tag=${v%%:*}; yaml=${v#*:}; if esphome config esphome/$yaml.yaml > $B/after-$tag.txt 2>&1; then $PY scripts/normalize-config.py $B/after-$tag.txt > $B/after-$tag.json && if diff -q $B/baseline-$tag.json $B/after-$tag.json > /dev/null; then echo "EQUIVALENT $tag"; else echo "DIFFERENT $tag"; diff $B/baseline-$tag.json $B/after-$tag.json | head -40; fi; else echo "CONFIG FAILED $tag"; tail -20 $B/after-$tag.txt; fi; done
```

Expected: `EQUIVALENT prod` and `EQUIVALENT virt`. Anything else means text was not moved verbatim; fix the file, do not adjust the baseline.

- [ ] **Step 7: Commit**

```bash
cd /Users/josh/GitHub/desiccant-dryer/.claude/worktrees/display-mirroring-laptop-c13ab1 && git add esphome/packages/platform-esp32.yaml esphome/packages/base.yaml esphome/desiccant-dryer.yaml esphome/desiccant-dryer-virtual.yaml && git commit -m "Move board, WiFi, OTA and web server into a platform package

base.yaml is now the controller only. platform-esp32.yaml holds the
blocks that only make sense on the S2, so a host build can swap in a
different platform package. Normalised config dumps of both device
builds are identical to before.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" && git log --oneline -1
```

---

### Task 3: Split display.yaml into drawing and panel driver

**Files:**
- Create: `esphome/packages/display-draw.yaml`
- Create: `esphome/packages/display-st7789.yaml`
- Delete: `esphome/packages/display.yaml`
- Modify: `esphome/desiccant-dryer.yaml`, `esphome/desiccant-dryer-virtual.yaml`

**Interfaces:**
- Consumes: the baseline JSON from Task 1; the selectors as left by Task 2.
- Produces: substitution `display_lambda` (the full drawing lambda body), fonts `f_big`/`f_med`/`f_small`, colours `c_white`/`c_grey`/`c_green`/`c_orange`/`c_red`/`c_blue`, all in `display-draw.yaml`. Any display package can use `lambda: ${display_lambda}`. Selectors list `draw:` before `display:`.

- [ ] **Step 1: Create `esphome/packages/display-draw.yaml`**

The lambda body below is today's `display.yaml` lambda moved verbatim; only its indentation changes because it now sits under `substitutions:`.

```yaml
# What the 240x240 screen shows, independent of the panel that draws it.
# Edit this file when working on the display, and run the host preview
# build to see it without a board:  esphome run esphome/desiccant-dryer-host.yaml
# packages/display-st7789.yaml (real panel) and packages/display-sdl.yaml
# (host window) both render ${display_lambda}.

substitutions:
  display_lambda: |-
    it.fill(Color::BLACK);

    if (id(fault_code) != 0) {
      it.print(120, 8, id(f_med), id(c_red), TextAlign::TOP_CENTER, "FAULT");
      it.print(120, 40, id(f_small), id(c_red), TextAlign::TOP_CENTER, id(fault_message).state.c_str());
    } else if (!id(dryer_enabled).state) {
      it.print(120, 8, id(f_med), id(c_grey), TextAlign::TOP_CENTER, "DISABLED");
    } else if (id(active_pack) != 0) {
      const char* act = id(active_pack) == 1 ? "A" : "B";
      const char* sb  = id(active_pack) == 1 ? "B" : "A";
      it.printf(120, 4, id(f_big), id(c_blue), TextAlign::TOP_CENTER, "AIR: %s", act);
      const char* st[] = {"wet", "heating", "cooling", "ready"};
      Color sc = id(standby_state) == 1 ? id(c_orange)
               : id(standby_state) == 3 ? id(c_green) : id(c_grey);
      it.printf(120, 44, id(f_small), sc, TextAlign::TOP_CENTER, "pack %s %s", sb, st[id(standby_state)]);
    }

    // sensors
    it.printf(8, 74, id(f_med), id(sim_enabled).state ? id(c_orange) : id(c_white), "%.1f %%RH%s",
              id(ctrl_rh).state, id(sim_enabled).state ? " SIM" : "");
    it.printf(8, 100, id(f_med), id(c_white), "%.1f °C air", id(air_temp).state);

    Color ca = id(heater_a).state ? id(c_orange) : id(c_grey);
    Color cb = id(heater_b).state ? id(c_orange) : id(c_grey);
    it.printf(8, 134, id(f_small), ca, "A %.0f° %s", id(pack_a_temp).state, id(heater_a).state ? "HEAT" : "");
    it.printf(8, 154, id(f_small), cb, "B %.0f° %s", id(pack_b_temp).state, id(heater_b).state ? "HEAT" : "");
    it.printf(8, 174, id(f_small), id(c_grey), "case %.0f° fan %s", id(case_temp).state, id(case_fan).state ? "on" : "off");

    // humidity bar: 0 .. swap threshold
    float frac = id(ctrl_rh).state / id(swap_rh).state;
    if (frac < 0) frac = 0; if (frac > 1) frac = 1;
    it.rectangle(8, 200, 224, 12, id(c_grey));
    it.filled_rectangle(8, 200, (int)(224 * frac), 12, frac > 0.8 ? id(c_orange) : id(c_green));

    it.print(120, 222, id(f_small), id(c_grey), TextAlign::TOP_CENTER, id(ip_addr).state.c_str());

font:
  - file: "gfonts://Roboto"
    id: f_big
    size: 34
  - file: "gfonts://Roboto"
    id: f_med
    size: 22
  - file: "gfonts://Roboto"
    id: f_small
    size: 16

color:
  - id: c_white
    hex: FFFFFF
  - id: c_grey
    hex: 909090
  - id: c_green
    hex: 40D060
  - id: c_orange
    hex: FFA030
  - id: c_red
    hex: FF4040
  - id: c_blue
    hex: 50A0FF
```

- [ ] **Step 2: Create `esphome/packages/display-st7789.yaml`**

```yaml
# ST7789 1.54" 240x240 display on SPI, shared by both device builds. On the
# virtual build nothing is attached; the driver still runs so the frame
# buffer allocation on the S2 gets exercised. The drawing itself is
# ${display_lambda} from packages/display-draw.yaml.
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
    lambda: ${display_lambda}
```

- [ ] **Step 3: Delete the old file and point both selectors at the new pair**

```bash
cd /Users/josh/GitHub/desiccant-dryer/.claude/worktrees/display-mirroring-laptop-c13ab1 && git rm -q esphome/packages/display.yaml && ls esphome/packages
```

Expected listing: `base.yaml display-draw.yaml display-st7789.yaml hw-real.yaml hw-virtual.yaml platform-esp32.yaml`.

In both `esphome/desiccant-dryer.yaml` and `esphome/desiccant-dryer-virtual.yaml`, replace the single line

```yaml
  display: !include packages/display.yaml
```

with

```yaml
  draw: !include packages/display-draw.yaml
  display: !include packages/display-st7789.yaml
```

- [ ] **Step 4: Prove both device builds are unchanged**

Same command as Task 2 Step 6:

```bash
cd /Users/josh/GitHub/desiccant-dryer/.claude/worktrees/display-mirroring-laptop-c13ab1 && B=.superpowers/baseline && PY="$(dirname "$(readlink -f "$(which esphome)")")/python" && for v in prod:desiccant-dryer virt:desiccant-dryer-virtual; do tag=${v%%:*}; yaml=${v#*:}; if esphome config esphome/$yaml.yaml > $B/after-$tag.txt 2>&1; then $PY scripts/normalize-config.py $B/after-$tag.txt > $B/after-$tag.json && if diff -q $B/baseline-$tag.json $B/after-$tag.json > /dev/null; then echo "EQUIVALENT $tag"; else echo "DIFFERENT $tag"; diff $B/baseline-$tag.json $B/after-$tag.json | head -40; fi; else echo "CONFIG FAILED $tag"; tail -20 $B/after-$tag.txt; fi; done
```

Expected: `EQUIVALENT prod` and `EQUIVALENT virt`. If the diff shows the lambda text altered (for example braces or `%` sequences changed), ESPHome's substitution expander mangled the body; stop and report rather than editing the lambda to fit.

**Deviation recorded during execution:** `esphome config` echoes the `substitutions:` block it expanded, so the new `display_lambda` key appeared as one extra key in the normalised dump while every expanded value was identical. `scripts/normalize-config.py` now drops the top-level `substitutions` key (they are inputs already expanded into every other key), the raw Task 1 `.txt` dumps were re-normalised with the new script, and the check then printed EQUIVALENT for both builds. The script change is part of this task's commit.

- [ ] **Step 5: Commit**

```bash
cd /Users/josh/GitHub/desiccant-dryer/.claude/worktrees/display-mirroring-laptop-c13ab1 && git add esphome/packages/display-draw.yaml esphome/packages/display-st7789.yaml esphome/desiccant-dryer.yaml esphome/desiccant-dryer-virtual.yaml && git commit -m "Split the display into drawing and panel-driver packages

display-draw.yaml holds fonts, colours and the drawing lambda as the
display_lambda substitution; display-st7789.yaml is the SPI panel and
backlight. Both device builds are unchanged (normalised config diff is
empty). A second driver package can now render the same drawing.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" && git log --oneline -1
```

---

### Task 4: The host preview build

**Files:**
- Create: `esphome/packages/platform-host.yaml`
- Create: `esphome/packages/display-sdl.yaml`
- Create: `esphome/desiccant-dryer-host.yaml`

**Interfaces:**
- Consumes: `display_lambda`, fonts and colours from `display-draw.yaml`; the five sensor ids from `hw-virtual.yaml`; everything else from `base.yaml`.
- Produces: `ip_addr` (internal template text sensor reading `host`) so the last line of the display compiles; a runnable native binary printed by `esphome run`.

- [ ] **Step 1: Show that the host selector does not exist yet**

```bash
cd /Users/josh/GitHub/desiccant-dryer/.claude/worktrees/display-mirroring-laptop-c13ab1 && esphome config esphome/desiccant-dryer-host.yaml 2>&1 | tail -2
```

Expected: an error that the file could not be read.

- [ ] **Step 2: Create `esphome/packages/platform-host.yaml`**

```yaml
# Host platform: the firmware compiled natively for the Mac. No WiFi, OTA,
# captive portal or web server exist on host, so this file only provides
# the host block and the one entity the display reads that would otherwise
# come from WiFi. Home Assistant reaches the process over the API.

host:

text_sensor:
  # The display's bottom line prints ip_addr. On host it just says so.
  # Internal: Home Assistant does not need a fixed-string entity.
  - platform: template
    name: "IP Address"
    id: ip_addr
    internal: true
    update_interval: 60s
    lambda: return std::string("host");
```

- [ ] **Step 3: Create `esphome/packages/display-sdl.yaml`**

```yaml
# The screen as an SDL window on the Mac, for the host preview build. Same
# size and refresh as the ST7789 and the same ${display_lambda} from
# packages/display-draw.yaml. Resizable so it can be scaled up on a
# Retina screen; SDL scales the 240x240 logical frame to the window.
# Not reproduced here: the 8-bit palette, invert_colors, the panel offset
# and the backlight.

display:
  - platform: sdl
    dimensions:
      width: 240
      height: 240
    update_interval: 2s
    window_options:
      resizable: true
    lambda: ${display_lambda}
```

- [ ] **Step 4: Create `esphome/desiccant-dryer-host.yaml`**

```yaml
# Host preview build: the firmware compiled natively for the Mac, with the
# display rendered into an SDL window. Same controller and plant model as
# the virtual build; no WiFi, OTA or web server. Home Assistant connects
# over the API like any other ESPHome device. Needs SDL2: brew install sdl2
# Run:    esphome run esphome/desiccant-dryer-host.yaml
# Guide:  docs/host-preview.md
substitutions:
  name: desiccant-dryer-host
  friendly_name: Desiccant Dryer (Host)

packages:
  base: !include packages/base.yaml
  platform: !include packages/platform-host.yaml
  hardware: !include packages/hw-virtual.yaml
  draw: !include packages/display-draw.yaml
  display: !include packages/display-sdl.yaml
```

- [ ] **Step 5: Validate the host config**

```bash
cd /Users/josh/GitHub/desiccant-dryer/.claude/worktrees/display-mirroring-laptop-c13ab1 && B=.superpowers/baseline && if esphome config esphome/desiccant-dryer-host.yaml > $B/host-config.txt 2>&1; then echo VALID; else echo INVALID; tail -30 $B/host-config.txt; fi; echo "sdl displays: $(grep -c 'platform: sdl' $B/host-config.txt)"; echo "ili9xxx displays: $(grep -c 'platform: ili9xxx' $B/host-config.txt)"; echo "wifi/ota/web_server keys: $(grep -cE '^(wifi|ota|web_server|captive_portal|esp32):' $B/host-config.txt)"; echo "gpio switches: $(grep -c 'platform: gpio' $B/host-config.txt)"; grep -A1 "^esphome:" $B/host-config.txt | head -3
```

Expected: `VALID`, `sdl displays: 1`, `ili9xxx displays: 0`, `wifi/ota/web_server keys: 0`, `gpio switches: 5`, and the `esphome:` block naming `desiccant-dryer-host`.

- [ ] **Step 6: Compile natively**

```bash
cd /Users/josh/GitHub/desiccant-dryer/.claude/worktrees/display-mirroring-laptop-c13ab1 && B=.superpowers/baseline && esphome compile esphome/desiccant-dryer-host.yaml > $B/host-compile.txt 2>&1; tail -3 $B/host-compile.txt
```

Expected: `[SUCCESS]` and `INFO Successfully compiled program to path '<...>/esphome/.esphome/build/desiccant-dryer-host/.pioenvs/desiccant-dryer-host/program'`. First compile fetches the `platformio/native` platform and takes about a minute; later ones take seconds.

- [ ] **Step 7: Run it for twelve seconds through a pseudo-terminal and read the log**

Run this with the sandbox disabled (SDL must open a window). A window titled `desiccant-dryer-host` appears and closes when the run ends.

```bash
cd /Users/josh/GitHub/desiccant-dryer/.claude/worktrees/display-mirroring-laptop-c13ab1 && python3 - <<'EOF'
import os, pty, re, select, signal, time
prog = "esphome/.esphome/build/desiccant-dryer-host/.pioenvs/desiccant-dryer-host/program"
pid, fd = pty.fork()
if pid == 0:
    os.execv(prog, [prog])
end = time.time() + 12
data = b""
while time.time() < end:
    r, _, _ = select.select([fd], [], [], 0.5)
    if r:
        try:
            chunk = os.read(fd, 65536)
        except OSError:
            break
        if not chunk:
            break
        data += chunk
os.kill(pid, signal.SIGKILL)
txt = re.sub(r"\x1b\[[0-9;]*m", "", data.decode(errors="replace")).replace("\r", "")
for line in txt.splitlines():
    if any(k in line for k in ("setup()", "Boot:", "Starting on pack", "cycle", "display", "[E]", "api")):
        print(line)
EOF
```

Expected lines, in order:
- `[I][cycle:...]: Boot: active pack 0, standby state 0, fault 0` (or the restored pack on a later run)
- `[I][app:...]: setup() finished successfully!`
- one `display took a long time` warning (SDL window creation, once)
- `[I][cycle:...]: Starting on pack A` within about 5 s

No `[E]` lines. If `Boot:` appears but no `Starting on pack`, the control tick did not run; check that `Dryer Enabled` is on (it defaults on).

- [ ] **Step 8: Commit**

```bash
cd /Users/josh/GitHub/desiccant-dryer/.claude/worktrees/display-mirroring-laptop-c13ab1 && git add esphome/packages/platform-host.yaml esphome/packages/display-sdl.yaml esphome/desiccant-dryer-host.yaml && git commit -m "Add the host preview build: native compile with an SDL display window

desiccant-dryer-host.yaml combines the controller, the virtual plant
model and the shared drawing lambda with ESPHome's host platform and
an SDL window, so the screen can be worked on without flashing a board.
Home Assistant connects over the API; there is no WiFi, OTA or web
server on host.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" && git log --oneline -1
```

---

### Task 5: Documentation

**Files:**
- Create: `docs/host-preview.md`
- Modify: `CLAUDE.md` (layout paragraph lines 35-43; working conventions lines 84-89)
- Modify: `README.md`
- Modify: `docs/hardware-bringup.md` (lines 63 and 66)
- Modify: `docs/virtual-testing.md` (after the first paragraph)

**Interfaces:**
- Consumes: file names and commands from Tasks 2-4.
- Produces: nothing code-facing.

- [ ] **Step 1: Create `docs/host-preview.md`**

````markdown
# Host preview: the display on your Mac

The host build compiles the firmware natively for the Mac and draws the
display into a window. It runs the production controller, the virtual
plant model from `packages/hw-virtual.yaml`, and the exact drawing lambda
the ST7789 uses, so layout, text and positions match the real screen
pixel for pixel. Use it to work on `packages/display-draw.yaml` without
flashing a board.

## One-time setup

```bash
brew install sdl2
```

`esphome/secrets.yaml` must exist (see `docs/virtual-testing.md`); only
`api_key` is used on host.

## Run

```bash
esphome run esphome/desiccant-dryer-host.yaml
```

ESPHome compiles natively (about a minute the first time, seconds after),
opens a 240x240 window titled `desiccant-dryer-host`, and streams the log
in the terminal. Drag the window corner to scale it up. Ctrl-C stops it.
The edit loop is: change `display-draw.yaml`, Ctrl-C, run again.

macOS may ask once whether the program may accept incoming connections;
allow it so Home Assistant can reach the API.

## Drive it from Home Assistant

The process behaves like any other ESPHome device, **Desiccant Dryer
(Host)**. Home Assistant may discover it by mDNS on the same subnet;
otherwise add the ESPHome integration manually with the Mac's LAN address,
port 6053, and the `api_key` from `secrets.yaml`. Every Sim knob and
threshold from `docs/virtual-testing.md` works the same way, so the
checklist there can be run on the Mac with the screen in view. The five
output switches toggle and interlock normally; they drive no pins.

Useful screen states and how to reach them:

| Screen | How |
|---|---|
| "AIR: A" with "pack B wet" | Fresh start |
| "pack B heating", "B ... HEAT" in orange | Sim Speed 60, wait about a minute |
| "pack B ready" in green, then "AIR: B" | Keep waiting |
| RH line orange with "SIM" | Simulate Humidity on, Simulated RH 12 |
| "DISABLED" | Dryer Enabled off |
| "FAULT" with the message in red | Sim Heater Max Temp 130, wait for heating |

## Persisted state

Everything the board would keep in flash (active pack, counters, Sim
knobs, plant temperatures) is kept in
`~/.esphome/prefs/desiccant-dryer-host.prefs`. Delete that file for a
fresh boot. The Restart button exits the process; run it again to
"reboot", and the state resumes from the file exactly as on the board.

## What the preview cannot show

The window renders the drawing, not the panel. These only show on the
real screen:

- 8-bit palette rounding (`color_palette: 8BIT`), so colours are slightly
  richer in the window.
- `invert_colors`, `offset_height` and `offset_width`.
- Backlight level; there is no `Display Backlight` entity on host.

There is no web server on host, so the entity-name REST URLs from the
bench notes do not apply; use Home Assistant.
````

- [ ] **Step 2: Update the layout paragraph in `CLAUDE.md`**

Replace:

```
Two builds share one logic file via ESPHome packages: `esphome/packages/base.yaml`
(platform, globals, tunables, GPIO outputs, state machine, derived entities),
`packages/hw-real.yaml` (buses and real sensors; the hardware side edits only
this), `packages/hw-virtual.yaml` (plant model and sim knobs), and
`packages/display.yaml`. `desiccant-dryer.yaml` and `desiccant-dryer-virtual.yaml`
are ten-line selectors. Base must only reference the five sensor ids
`air_rh`, `air_temp`, `pack_a_temp`, `pack_b_temp`, `case_temp` from the
hardware package. `hw-real.yaml` is the pin-map source of truth for sensors,
`base.yaml` for outputs, `display.yaml` for the display.
```

with:

```
Three builds share one logic file via ESPHome packages. `esphome/packages/base.yaml`
is the controller (globals, tunables, GPIO outputs, state machine, derived
entities). Platform: `packages/platform-esp32.yaml` (board, WiFi, OTA, web
server) or `packages/platform-host.yaml` (native build on the Mac). Hardware:
`packages/hw-real.yaml` (buses and real sensors; the hardware side edits only
this) or `packages/hw-virtual.yaml` (plant model and sim knobs). Display:
`packages/display-draw.yaml` (fonts, colours and the drawing lambda as the
`display_lambda` substitution; edit this to change the screen) plus a driver,
`packages/display-st7789.yaml` (real panel) or `packages/display-sdl.yaml`
(window on the Mac). `desiccant-dryer.yaml`, `desiccant-dryer-virtual.yaml`
and `desiccant-dryer-host.yaml` are short selectors. Base must only reference
the five sensor ids `air_rh`, `air_temp`, `pack_a_temp`, `pack_b_temp`,
`case_temp` from the hardware package and `ip_addr` from the platform
package. `hw-real.yaml` is the pin-map source of truth for sensors,
`base.yaml` for outputs, `display-st7789.yaml` for the display.
```

- [ ] **Step 3: Update the working conventions in `CLAUDE.md`**

Replace:

```
- Flash with `esphome run esphome/desiccant-dryer.yaml` (real hardware) or
  `esphome run esphome/desiccant-dryer-virtual.yaml` (bare board). Copy
  `secrets.yaml.example` to `secrets.yaml` first; for a compile-only check,
  `cp esphome/secrets.ci.yaml esphome/secrets.yaml` works.
```

with:

```
- Flash with `esphome run esphome/desiccant-dryer.yaml` (real hardware) or
  `esphome run esphome/desiccant-dryer-virtual.yaml` (bare board). Copy
  `secrets.yaml.example` to `secrets.yaml` first; for a compile-only check,
  `cp esphome/secrets.ci.yaml esphome/secrets.yaml` works.
- To see the screen without a board, `esphome run esphome/desiccant-dryer-host.yaml`
  compiles natively and opens an SDL window (needs `brew install sdl2`); see
  docs/host-preview.md. Nothing WiFi, OTA, SPI or LEDC related may be added
  to `base.yaml` or `display-draw.yaml`, because the host build has none of
  those; it goes in the platform or driver package.
```

- [ ] **Step 4: Update `README.md`**

Replace the whole file with:

````markdown
# desiccant-dryer

ESPHome firmware for an ESP32-S2 replacement of the Azco VMD-08 desiccant
air dryer control board. Swaps packs on measured humidity and pack
temperature instead of a fixed timer. See `CLAUDE.md` for decisions,
`docs/hardware.md` for wiring and BOM, `docs/control-logic.md` for the
state machine, `docs/virtual-testing.md` for testing without hardware,
`docs/host-preview.md` for the display on your Mac.

Three builds share `esphome/packages/base.yaml`:

| Build | File | Sensors | Runs on |
|---|---|---|---|
| Production | `esphome/desiccant-dryer.yaml` | SHT45 + 3× DS18B20 (`packages/hw-real.yaml`) | ESP32-S2 |
| Virtual | `esphome/desiccant-dryer-virtual.yaml` | On-device plant model (`packages/hw-virtual.yaml`) | ESP32-S2, nothing attached |
| Host | `esphome/desiccant-dryer-host.yaml` | Same plant model | Your Mac, display in an SDL window |

```
cp esphome/secrets.yaml.example esphome/secrets.yaml   # fill in
esphome run esphome/desiccant-dryer-virtual.yaml       # bare board
esphome run esphome/desiccant-dryer.yaml               # real hardware
esphome run esphome/desiccant-dryer-host.yaml          # no board; brew install sdl2 first
```

CI compiles all three on every pull request.
````

- [ ] **Step 5: Fix the renamed references in `docs/hardware-bringup.md`**

Replace:

```
Confirm the layout matches `display.yaml`: "AIR: A" at the top, the
```

with:

```
Confirm the layout matches `display-draw.yaml`: "AIR: A" at the top, the
```

and replace:

```
cropped, try `offset_height: 80` as the comment in `display.yaml` says. Note
```

with:

```
cropped, try `offset_height: 80` as the comment in `display-st7789.yaml` says. Note
```

- [ ] **Step 6: Point `docs/virtual-testing.md` at the host preview**

After the first paragraph (which ends with `a separate device from the real unit.`), insert a blank line and:

```
The same checklist runs on the Mac with no board at all through the host
preview build, with the display visible in a window; see
`docs/host-preview.md`.
```

- [ ] **Step 7: Check that no stale file names remain**

```bash
cd /Users/josh/GitHub/desiccant-dryer/.claude/worktrees/display-mirroring-laptop-c13ab1 && grep -rn 'packages/display\.yaml\|`display\.yaml`' CLAUDE.md README.md docs/*.md esphome/*.yaml esphome/packages/*.yaml; echo "exit=$? (1 means no matches, which is what we want)"
```

Expected: no matches, `exit=1`.

- [ ] **Step 8: Commit**

```bash
cd /Users/josh/GitHub/desiccant-dryer/.claude/worktrees/display-mirroring-laptop-c13ab1 && git add docs/host-preview.md CLAUDE.md README.md docs/hardware-bringup.md docs/virtual-testing.md && git commit -m "Document the host preview build and the new package layout

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" && git log --oneline -1
```

---

### Task 6: CI job for the host build

**Files:**
- Modify: `.github/workflows/build.yml`

**Interfaces:**
- Consumes: `esphome/desiccant-dryer-host.yaml` from Task 4.
- Produces: a `compile host` check on the PR.

- [ ] **Step 1: Add the job**

Append to `.github/workflows/build.yml` (after the existing `compile` job, at the same indentation as `compile:`):

```yaml

  # The host preview build compiles natively inside the same image. The
  # sdl display validates by running sdl2-config, so SDL2 must be installed
  # before even `esphome config` would pass.
  compile-host:
    name: compile host
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - name: Provide dummy secrets
        run: cp esphome/secrets.ci.yaml esphome/secrets.yaml
      - name: Compile host preview
        run: >
          docker run --rm -v "$PWD:/config" -w /config --entrypoint bash
          ghcr.io/esphome/esphome:2026.1.4
          -c "apt-get update -qq && apt-get install -y -qq --no-install-recommends libsdl2-dev g++ > /dev/null && esphome compile esphome/desiccant-dryer-host.yaml"
```

- [ ] **Step 2: Check the workflow still parses**

```bash
cd /Users/josh/GitHub/desiccant-dryer/.claude/worktrees/display-mirroring-laptop-c13ab1 && "$(dirname "$(readlink -f "$(which esphome)")")/python" -c "import yaml,sys; d=yaml.safe_load(open('.github/workflows/build.yml')); print(sorted(d['jobs']))"
```

Expected: `['compile', 'compile-host']`.

- [ ] **Step 3: Commit**

```bash
cd /Users/josh/GitHub/desiccant-dryer/.claude/worktrees/display-mirroring-laptop-c13ab1 && git add .github/workflows/build.yml && git commit -m "CI: compile the host preview build

Installs SDL2 and g++ inside the ESPHome image and compiles
desiccant-dryer-host.yaml natively alongside the two device builds.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" && git log --oneline -1
```

If this job fails on the PR because the image cannot build natively (missing compiler headers, apt unavailable), remove the job in a follow-up commit and say so in the PR description; the device jobs are unaffected.

---

### Task 7: Open the pull request

Follow the user's global PR workflow: rebase onto a fresh `origin/main`, open the PR, watch CI and fix failures, then wait for and address the Copilot review. Never touch local `main`.

**Files:**
- None new. Possible conflict resolution in `esphome/packages/base.yaml` if PR #2 (`bench-polish`) has merged.

- [ ] **Step 1: Rebase onto origin/main**

```bash
cd /Users/josh/GitHub/desiccant-dryer/.claude/worktrees/display-mirroring-laptop-c13ab1 && git fetch origin && git log --oneline HEAD..origin/main && git rebase origin/main && git log --oneline -8
```

If `HEAD..origin/main` is empty there is nothing to rebase. If the rebase conflicts in `base.yaml`: keep every logic change from `origin/main` inside `base.yaml`, keep the platform blocks removed (they live in `platform-esp32.yaml`), and if `origin/main` changed any of the moved blocks, apply that change inside `platform-esp32.yaml` instead. Then `git add` and `git rebase --continue`.

- [ ] **Step 2: After any rebase that touched esphome files, re-prove equivalence against origin/main**

Build a fresh baseline from `origin/main` and diff the rebased tree against it:

```bash
cd /Users/josh/GitHub/desiccant-dryer/.claude/worktrees/display-mirroring-laptop-c13ab1 && M=.superpowers/main-baseline && rm -rf $M && mkdir -p $M && git archive origin/main esphome scripts | tar -x -C $M && cp esphome/secrets.yaml $M/esphome/secrets.yaml && PY="$(dirname "$(readlink -f "$(which esphome)")")/python" && for v in prod:desiccant-dryer virt:desiccant-dryer-virtual; do tag=${v%%:*}; yaml=${v#*:}; (cd $M && esphome config esphome/$yaml.yaml > main-$tag.txt 2>&1) && $PY scripts/normalize-config.py $M/main-$tag.txt > $M/main-$tag.json && esphome config esphome/$yaml.yaml > $M/head-$tag.txt 2>&1 && $PY scripts/normalize-config.py $M/head-$tag.txt > $M/head-$tag.json && (diff -q $M/main-$tag.json $M/head-$tag.json > /dev/null && echo "EQUIVALENT $tag" || { echo "DIFFERENT $tag"; diff $M/main-$tag.json $M/head-$tag.json | head -40; }); done
```

Expected: `EQUIVALENT prod` and `EQUIVALENT virt`. Skip this step only if Step 1 had nothing to rebase.

- [ ] **Step 3: Push and open the PR**

```bash
cd /Users/josh/GitHub/desiccant-dryer/.claude/worktrees/display-mirroring-laptop-c13ab1 && git push --force-with-lease -u origin claude/display-mirroring-laptop-c13ab1 && gh pr create --base main --title "Host preview build: the display in an SDL window on the Mac" --body "$(cat <<'EOF'
## Summary

- Adds `esphome/desiccant-dryer-host.yaml`, which compiles the firmware natively for the Mac with ESPHome's host platform and renders the display into an SDL window, so the screen can be iterated without flashing a board. It runs the production controller and the virtual plant model; Home Assistant connects over the API.
- Moves the board, WiFi, OTA, captive portal, web server and WiFi sensors out of `base.yaml` into `packages/platform-esp32.yaml`, with `packages/platform-host.yaml` as the host counterpart.
- Splits `display.yaml` into `display-draw.yaml` (fonts, colours, drawing lambda as the `display_lambda` substitution) and `display-st7789.yaml` (panel driver); `display-sdl.yaml` renders the same lambda in a window.
- Docs: new `docs/host-preview.md`; CLAUDE.md, README and the bring-up guide updated for the new file names.
- CI: a third job compiles the host build after installing SDL2 in the ESPHome image.

## Verification

- Normalised `esphome config` dumps of the production and virtual builds are identical before and after the package split (`scripts/normalize-config.py`).
- All three builds compile locally with ESPHome 2026.1.4.
- The host binary runs, finishes setup, opens the window and starts the cycle on pack A.
- Bench checklist with Home Assistant on the host build: see `docs/host-preview.md` (run after merge review if not yet done; noted in the conversation).

Spec: `docs/superpowers/specs/2026-09-14-host-display-preview-design.md`
Plan: `docs/superpowers/plans/2026-09-14-host-display-preview.md`

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Expected: a PR URL. Bind it with the desktop app's PR tools if available, or watch checks with `gh pr checks <number> --watch` in the background.

- [ ] **Step 4: Watch CI and fix failures**

```bash
cd /Users/josh/GitHub/desiccant-dryer/.claude/worktrees/display-mirroring-laptop-c13ab1 && gh pr checks --watch --interval 30
```

Expected: `compile production`, `compile virtual` and `compile host` all pass. On a failure, read the log with `gh run view <run-id> --log-failed`, fix the root cause, commit, push, and watch again. If only `compile host` fails for an environment reason (apt or compiler missing in the image), remove the job as described at the end of Task 6.

- [ ] **Step 5: Wait for the Copilot review and address every comment**

Poll until a review from Copilot exists, then read its comments:

```bash
cd /Users/josh/GitHub/desiccant-dryer/.claude/worktrees/display-mirroring-laptop-c13ab1 && N=$(gh pr view --json number -q .number) && gh api repos/{owner}/{repo}/pulls/$N/reviews --jq '.[] | select(.user.login | test("copilot"; "i")) | {state, submitted_at}' && gh api repos/{owner}/{repo}/pulls/$N/comments --jq '.[] | select(.user.login | test("copilot"; "i")) | "\(.path):\(.line // .original_line): \(.body)"'
```

Repeat every few minutes until the first command prints a review (Copilot's review arrives a little after the PR opens). For each comment: fix it and push, or reply on the thread explaining why not. Do not call the PR done until every Copilot comment has been handled and CI is green on the final push.

---

### Task 8: Bench verification of the preview with Home Assistant

This is the spec's section 7, items 3-6. It needs the user at Home Assistant to pair the host device and turn knobs; the agent runs the process and reads the log, the user reports what the window shows. Record outcomes in the conversation and in the PR if anything differs from the expected column.

**Files:**
- None.

- [ ] **Step 1: Start with a clean state**

```bash
rm -f ~/.esphome/prefs/desiccant-dryer-host.prefs && cd /Users/josh/GitHub/desiccant-dryer/.claude/worktrees/display-mirroring-laptop-c13ab1 && esphome run esphome/desiccant-dryer-host.yaml
```

Run this in the user's terminal (it keeps the window open until Ctrl-C). Expected window: "AIR: A" in blue, "pack B wet" in grey, "1.0 %RH" in white after the first 5 s (until then "nan %RH"), "27.0 °C air", "A 25°", "B 25°", "case 25° fan off", an empty grey bar, "host" at the bottom.

- [ ] **Step 2: Pair Home Assistant**

Settings, Devices & services, Add integration, ESPHome. Host: the Mac's LAN address, port 6053, encryption key: `api_key` from `esphome/secrets.yaml`. The device appears as **Desiccant Dryer (Host)**. If macOS asks whether the program may accept incoming connections, allow it.

- [ ] **Step 3: Half cycle at 60x**

| Action | Expected on the window |
|---|---|
| Sim Speed 60 | After about a minute the RH line climbs and the bar fills green |
| RH reaches 5 % | "pack B heating" in orange; "B ... HEAT" in orange; B temperature rising |
| B holds 90 °C for 15 sim-min | "pack B cooling" in grey, "HEAT" gone |
| B below 40 °C | "pack B ready" in green |
| Bar past 80 % of the swap threshold | Bar turns orange |
| RH reaches 10 % | "AIR: B", "pack A wet", RH back to 1.0, bar empty |

- [ ] **Step 4: Overrides and faults**

| Action | Expected on the window |
|---|---|
| Simulate Humidity on, Simulated RH 12 | RH line orange, reads "12.0 %RH SIM"; swap once standby is ready |
| Simulate Humidity off, Dryer Enabled off | "DISABLED" in grey at the top; sensor lines still shown |
| Dryer Enabled on | "AIR: A" and "pack B wet" within 5 s |
| Sim Heater Max Temp 130, wait for heating | "FAULT" and "Standby pack overtemp" in red; "HEAT" gone |
| Clear Fault, Sim Heater Max Temp 110 | Normal header returns, standby cools to "ready" |

- [ ] **Step 5: Restart**

Press Restart in Home Assistant. Expected: the process exits and the window closes; the terminal returns to the prompt. Run the command from Step 1 again without the `rm`. Expected: the boot log line `Boot: active pack <same as before>` and the window shows the same active pack within one tick.

- [ ] **Step 6: Record**

Note anything that differed from the expected column, with the log excerpt, in the conversation and as a PR comment. Then Ctrl-C the process.
