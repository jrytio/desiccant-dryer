# Host display preview — design

Date: 2026-09-14
Status: approved in conversation; spec written for review

## Goal

Let the display logic and layout be iterated on the Mac without flashing a
board. A third build compiles the firmware natively for the host with
ESPHome's `host` platform and renders the display into an SDL window,
running the same drawing lambda, fonts and colours as the ST7789 build
and the same control logic and plant model as the virtual build.

## Context and constraints

- ESPHome 2026.1.4 is installed on the Mac; SDL2 2.32.8 is installed via
  Homebrew and `sdl2-config` is on PATH. A throwaway host + SDL config with
  a Google font and a multi-line lambda held in a substitution compiled
  and linked in about 7 s, ran, finished setup and drew its first frame
  (the display's first update took 329 ms, which is SDL window creation).
- ESPHome's host platform in 2026.1.4 auto-loads `network` and
  `preferences`, supports `api`, `logger`, `font`, `template`, `gpio`
  switches (pins are no-ops and accept the same `GPIO13` spelling),
  `thermostat`, `restart` (which calls `exit(0)`), `uptime` and `sdl`
  displays. It does not support `wifi`, `captive_portal`, `web_server`,
  `wifi_signal`, `wifi_info`, `ota` (validates with a warning and does
  nothing), `ledc`, `spi` or `ili9xxx`, and `logger.hardware_uart` is
  rejected on host.
- Substitutions declared inside a package are merged into the main
  substitutions before expansion, so a package can own the lambda text and
  other packages can reference it as `${display_lambda}`.
- Host preferences are a file: `~/.esphome/prefs/<device name>.prefs`.
- The `sdl` display validator runs `sdl2-config` at config time, so even
  `esphome config` on the host build needs SDL2 installed.
- All platform decisions in `CLAUDE.md` stand. The two device builds must
  be unchanged by this work; the repo's normalise-and-diff convention is
  the proof.
- PR #2 (`bench-polish`) is open against `main` and touches `base.yaml`.
  This work branches from `main`; the rebase before the PR resolves any
  overlap.

## Decisions made during brainstorming

| Question | Decision |
|---|---|
| Preview mechanism | Native host build with an SDL window, not a frame-buffer stream from the device or an HTML re-implementation |
| Data source for the preview | The existing virtual plant model (`hw-virtual.yaml`), driven from Home Assistant like the virtual board |
| Sharing the drawing lambda | One package holds it as a substitution; both display driver packages reference it |
| Platform-specific config | Moves out of `base.yaml` into `platform-esp32.yaml`; a `platform-host.yaml` counterpart exists |
| Home Assistant on the host build | Kept (`api` stays in base); it is the only way to turn knobs on host since `web_server` is unavailable |
| Window size | 240x240 logical, resizable so it can be scaled up on a Retina screen |
| CI | Third job compiles the host build after installing SDL2 and a C++ compiler in the container; dropped with a note if the image cannot do native builds |

## Non-goals

- Mirroring the real unit's screen over the network.
- Any change to what the display shows. This work only makes it viewable.
- Touch, keyboard or mouse input to the preview.
- Reproducing panel-level effects: 8-bit palette rounding, `invert_colors`,
  `offset_height`, backlight level.
- Changes to the control logic, plant model, pin map or entity names.

## 1. Repo layout

```
esphome/
  desiccant-dryer.yaml            # production: base, platform-esp32, hw-real, display-draw, display-st7789
  desiccant-dryer-virtual.yaml    # virtual:    base, platform-esp32, hw-virtual, display-draw, display-st7789
  desiccant-dryer-host.yaml       # host:       base, platform-host,  hw-virtual, display-draw, display-sdl
  packages/
    base.yaml            # controller only: on_boot, api, log level, globals, tunables,
                         # GPIO outputs, buttons, derived entities, fan thermostat, scripts, tick
    platform-esp32.yaml  # esp32 board, logger UART, ota, wifi + AP, captive portal,
                         # web server, WiFi Signal, IP Address (wifi_info)
    platform-host.yaml   # host block, internal IP Address template reading "host"
    hw-real.yaml         # unchanged
    hw-virtual.yaml      # unchanged
    display-draw.yaml    # fonts, colours, the drawing lambda as substitution display_lambda
    display-st7789.yaml  # spi, backlight output + light, ili9xxx panel using ${display_lambda}
    display-sdl.yaml     # sdl display using ${display_lambda}
docs/
  host-preview.md        # how to run, pair, reset and what the preview cannot show
  superpowers/specs/2026-09-14-host-display-preview-design.md   # this file
.github/workflows/build.yml   # adds the host compile job
```

`display.yaml` is deleted; its two halves are the new `display-draw.yaml`
and `display-st7789.yaml`. Selectors stay short: substitutions for `name`
and `friendly_name` plus a five-entry `packages:` block. The host build is
named `desiccant-dryer-host` / `Desiccant Dryer (Host)` so it appears in
Home Assistant as its own device.

## 2. Package contents

### base.yaml

Loses these keys, which move verbatim to `platform-esp32.yaml`:
`esp32:`, `logger.hardware_uart`, `ota:`, `wifi:`, `captive_portal:`,
`web_server:`, the `wifi_signal` sensor and the `wifi_info` text sensor
(`ip_addr`). Keeps `logger: level: INFO`; the platform package adds
`hardware_uart` and ESPHome merges the two dicts. Keeps `api:` with its
encrypted key. Everything else is untouched, including the five `gpio`
switches with their pin names and interlocks. The header comment is
updated to say platform blocks live in the platform packages.

### platform-esp32.yaml

Exactly the keys removed from `base.yaml`, with their existing comments
(the UART0 note especially). Nothing new.

### platform-host.yaml

```yaml
host:

text_sensor:
  - platform: template
    name: "IP Address"
    id: ip_addr
    internal: true
    update_interval: 60s
    lambda: return std::string("host");
```

`ip_addr` exists only so the last line of the display compiles. It is
internal so Home Assistant does not get a meaningless entity.

### display-draw.yaml

```yaml
substitutions:
  display_lambda: |-
    it.fill(Color::BLACK);
    ... (today's lambda body, unchanged) ...

font:    # f_big, f_med, f_small, unchanged
color:   # c_white .. c_blue, unchanged
```

This is the file to edit when working on the screen. The lambda is the
current one moved without modification; ids `f_*`, `c_*` and every
`id(...)` it reads stay the same.

### display-st7789.yaml

Today's `display.yaml` minus fonts, colours and the lambda body: the SPI
bus, the LEDC backlight output and its light, and the ili9xxx display with
all its current options (`color_palette: 8BIT`, `invert_colors`, offsets,
`update_interval: 2s`) and `lambda: ${display_lambda}`. Comments about the
S2 frame-buffer budget and the offset hint move with it.

### display-sdl.yaml

```yaml
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

No backlight, no palette. The window title is the device name.

## 3. Host build behaviour

- Run with `esphome run esphome/desiccant-dryer-host.yaml`. ESPHome
  compiles natively, prints the binary path, executes it and streams the
  log in the terminal. Ctrl-C stops it. The edit loop is: change
  `display-draw.yaml`, Ctrl-C, re-run; a rebuild takes seconds.
- The same `secrets.yaml` is used because `api` keeps its encryption key;
  WiFi and OTA secrets are ignored on host.
- Home Assistant pairs with the process at the Mac's LAN address on port
  6053 with the `api_key`. mDNS is compiled in and may discover it on the
  same subnet; otherwise add it manually. macOS may ask once to allow
  incoming connections for the binary.
- All Sim knobs, thresholds, `Simulate Humidity`, `Dryer Enabled`, `Force
  Swap`, `Clear Fault` work exactly as on the virtual board. The GPIO
  switches still toggle and interlock; they just drive no pins.
- Persisted state (`active_pack`, counters, Sim knobs, plant temperatures)
  lives in `~/.esphome/prefs/desiccant-dryer-host.prefs`. Deleting it gives
  a fresh boot.
- The Restart button exits the process; re-run to "reboot". The reboot
  scenarios from the virtual checklist therefore still work.

## 4. What does not change

Control logic, plant model, pin map, entity names, interlocks,
`restore_mode: ALWAYS_OFF`, the `on_boot` force-off, the `Simulate
Humidity` non-persistence, `time_scale` ownership and every other
invariant in `CLAUDE.md`. The device builds' normalised config dumps must
be identical before and after.

## 5. Docs

- `CLAUDE.md`: the layout paragraph lists the eight packages and the three
  selectors; working conventions add the host run command and the note
  that the display is edited in `display-draw.yaml`.
- `README.md`: the builds table gains a Host row; the command block gains
  the host run line; "CI compiles both" becomes "all three".
- `docs/hardware-bringup.md`: the two `display.yaml` references become
  `display-draw.yaml` (layout) and `display-st7789.yaml` (offset hint).
- `docs/virtual-testing.md`: one sentence pointing at `docs/host-preview.md`
  for running the same checklist without a board.
- `docs/host-preview.md` (new, short): prerequisites (`brew install sdl2`),
  the run command, HA pairing, the prefs file, the Restart behaviour, the
  edit loop, and the list of things the preview cannot show.

## 6. CI

`build.yml` gains a `compile-host` job alongside the existing matrix. It
runs the same Docker image with `--entrypoint bash` and a one-liner that
installs `libsdl2-dev` and `g++` with apt, then runs
`esphome compile esphome/desiccant-dryer-host.yaml`. Dummy secrets are
copied in as for the other jobs. If the image turns out unable to build
natively, the job is removed and the PR description says so; the two
device jobs are unaffected either way.

## 7. Verification

1. Before touching anything, dump `esphome config` for both device builds
   and normalise them with `scripts/normalize-config.py`. After the split,
   dump and normalise again; both diffs must be empty.
2. `esphome compile` passes for all three selectors locally.
3. `esphome run` on the host build opens a window showing "AIR: A",
   "pack B wet" in grey, "1.0 %RH", the air and three temperature lines,
   the humidity bar and "host" at the bottom.
4. Pair Home Assistant, set Sim Speed to 60, and watch the screen through
   one half cycle: "pack B heating" in orange with "B ... HEAT" lit, then
   "pack B cooling", "pack B ready" in green, the bar turning orange past
   80 % of the swap threshold, then "AIR: B" and "pack A wet".
5. Simulate Humidity on at 12 %: the RH line turns orange and reads "SIM".
   Dryer Enabled off: "DISABLED". Sim Heater Max Temp 130 °C: "FAULT" and
   "Standby pack overtemp" in red. Clear Fault recovers.
6. Restart from HA: process exits; re-run resumes on the same active pack.
7. CI green on all jobs, or the host job dropped with a note.

Flashing a board is not required; the empty config diff is the repo's
accepted proof that the device builds did not change.

## 8. Edge cases

- The first display update logs "display took a long time (329 ms)". That
  is SDL creating the window; it does not recur and is harmless.
- Google Fonts are fetched into the config directory's `.esphome` cache on
  the first build; the device builds already populate it.
- ESPHome's host platform uses a fixed default MAC address. Home Assistant
  keys ESPHome devices by MAC, so only one host build should be paired at
  a time. Not a problem here.
- The host build has no `web_server`, so entity-name REST URLs from the
  bench notes do not apply to it; use Home Assistant.
- `ota:` is deliberately absent from the host build rather than left to
  ESPHome's "disabled on host" warning.

## 9. Follow-ups (not in this work)

- Stream the real unit's frame buffer to the laptop for bench mirroring,
  if that is ever wanted.
- Host-side unit tests for the state machine, which the host build now
  makes practical.
- A scripted demo that walks the preview through every screen state
  without waiting on the plant model.
