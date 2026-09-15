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
(Host)**, but Home Assistant will not discover it on its own (the host
platform has no real mDNS). Add the ESPHome integration manually with the
Mac's LAN address, port 6053, and the `api_key` from `secrets.yaml`. Every Sim knob and
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
