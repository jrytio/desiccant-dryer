# Desiccant air dryer controller

ESP32 replacement for the control board in an Azco VMD-08 desiccant air dryer.
The dryer feeds dry air to a separate ozone generator (not controlled here).
Two desiccant packs, each with a 120 VAC heater. One pack is in service (air
flows through it) while the other regenerates (heater on, vents to atmosphere).

The original board swapped packs on a fixed 20-minute timer. This firmware swaps
based on measured outlet humidity and measured pack temperatures instead.

## Platform decisions (settled — don't relitigate without a reason)

- **ESPHome on ESP-IDF**, not MicroPython/Arduino/Tasmota. All control logic
  runs on-device; Home Assistant is for tuning and observation only. The unit
  must keep working with WiFi or HA down.
- **Board: SparkFun ESP32-S2 Thing Plus (WRL-17743).** Single core, 320 KB RAM,
  no PSRAM, no Bluetooth, CP2102 UART for flashing. The full 16-bit 240x240
  display buffer (~115 KB) does not allocate once WiFi, API and the web server
  are up (seen on the first bench flash), so the display runs
  `color_palette: 8BIT` (~58 KB). The logger must use `hardware_uart: UART0`;
  ESPHome's S2 default of USB_CDC is the unconnected native-USB pins.
- **Heaters are 120 VAC (~117 W, 123 Ω each)**, switched by Songle SRD-05VDC
  relays driven by 2N2222 low-side stages. Mains stays off the ESP board.
- **Valves are two SMC VDW22 2-port NC solenoids (24 VDC, 3 W)**, one per pack,
  driven by IRLZ44N low-side MOSFETs. Both closed = safe/idle state.
- **Case fan is 24 V on/off** (not PWM), thermostat-controlled from a DS18B20.
- **Outlet humidity sensor is an SHT45** on the Qwiic connector. A DHT11 was
  rejected: its 20–80 % RH range is blind to the 0–10 % region the control
  logic depends on. Cheap RH sensors can't measure true dew point; the SHT45
  is used as a *breakthrough detector* (rise off baseline), not a dryness gauge.
- **Three DS18B20s share one 1-wire bus** on GPIO37: pack A, pack B, case.

## Layout and pin map

Three builds share one logic file via ESPHome packages. `esphome/packages/base.yaml`
is the controller (globals, tunables, GPIO outputs, state machine, derived
entities). Platform: `packages/platform-esp32.yaml` (board, WiFi, OTA, web
server) or `packages/platform-host.yaml` (native build on the Mac). Hardware:
`packages/hw-real.yaml` (buses and real sensors; the hardware side edits only
this) or `packages/hw-virtual.yaml` (plant model and sim knobs). Display:
`packages/display-draw.yaml` (fonts, SVG sprites from `esphome/assets/display/`,
and the `ui_draw` script that gathers ids into a `UiState` for
`packages/display_ui.h`, where all drawing lives with no `id()` calls; the
`display_lambda` substitution just runs that script) plus a driver,
`packages/display-st7789.yaml` (real panel) or `packages/display-sdl.yaml`
(window on the Mac); both give the display id `panel`. `packages/screen-mirror.yaml` (device builds only) serves the panel's frame buffer as `/screen.png` through the local component `esphome/components/screen_mirror`. `desiccant-dryer.yaml`, `desiccant-dryer-virtual.yaml`
and `desiccant-dryer-host.yaml` are short selectors; `desiccant-dryer-scenarios.yaml`
is a fourth, host-only build that swaps the controller for a fixed table of
twelve screen states (`packages/display-scenarios.yaml`) so
`scripts/scenario-shots.sh` can render them all through the panel's palette
into `docs/display/`. The screen design is in
`docs/superpowers/specs/2026-09-14-display-ui-design.md`, with the cylinders
coloured by state per `docs/superpowers/specs/2026-09-14-cylinder-state-colours-design.md`
and airflow in/out of the pack tops per `docs/superpowers/specs/2026-09-15-airflow-indicators-design.md`.
Base must only reference the five sensor ids `air_rh`, `air_temp`, `pack_a_temp`, `pack_b_temp`,
`case_temp` from the hardware package; `display-draw.yaml` additionally
reads `ip_addr` from the platform package. `hw-real.yaml` is the pin-map source of truth for sensors,
`base.yaml` for outputs, `display-st7789.yaml` for the display.

Outputs on the 12-pin header: heater A 13, heater B 12, valve A 11,
valve B 10, fan 6. Sensors/display on the 16-pin header: I2C 1/2 (Qwiic),
SPI 36/35, display CS 5 / DC 9 / RST 14 / BL 17, 1-wire 37.
GPIO18 has a hardware pullup — never use it for a low-side driver.
GPIO13 also drives the on-board blue LED (acceptable: shows heater A relay).

## Control logic (see docs/control-logic.md for the full state machine)

Standby pack moves WET → HEATING → COOLING → READY. Heater starts when outlet
RH crosses `arm_rh`; regen is judged complete by pack temperature held above
`regen_temp` for `regen_hold_min`; the pack is READY once it cools below
`cooldown_temp`; swap happens when RH crosses `swap_rh` (or `max_service_min`).
All thresholds are HA `number` entities. Durations are persisted elapsed
counters scaled by a `time_scale` global (1.0 in production); outputs are
re-asserted from state every tick by the `apply_outputs` script. Overtemp and
"heater on but no temperature rise" latch a fault code that stops everything
until cleared.

Defaults (arm 5 %, swap 10 %, regen 90 °C / 15 min, cooldown 40 °C, max
service 180 min) are untested guesses meant to get first cycles logging.

## Invariants — keep these true in any change

- Heater A and heater B are interlocked; valve A and valve B are interlocked.
- The active (in-service) pack's heater is never on.
- All outputs use `restore_mode: ALWAYS_OFF` and are forced off in `on_boot`.
- `Dryer Enabled` off → everything off, state reset.
- Humidity simulation (`sim_enabled` / `sim_rh`) must never survive a reboot,
  and the display must show "SIM" whenever it is active.
- `time_scale` is only ever written by `packages/hw-virtual.yaml`. Production
  runs at 1.0.
- Virtual plant knobs (`Sim *`) persist across reboot by design; the base
  `Simulate Humidity` override does not. Don't merge the two mechanisms.
- Outputs are applied from state by `apply_outputs` every tick. Never toggle
  a heater or valve from a state transition alone; change the state and let
  the apply step do it.

## Working conventions

- Flash with `esphome run esphome/desiccant-dryer.yaml` (real hardware) or
  `esphome run esphome/desiccant-dryer-virtual.yaml` (bare board). Copy
  `secrets.yaml.example` to `secrets.yaml` first; for a compile-only check,
  `cp esphome/secrets.ci.yaml esphome/secrets.yaml` works.
- To see the screen without a board, `esphome run esphome/desiccant-dryer-host.yaml`
  compiles natively and opens an SDL window (needs `brew install sdl2`); see
  docs/host-preview.md. Nothing WiFi, OTA, SPI or LEDC related may be added
  to `base.yaml` or `display-draw.yaml`, because the host build has none of
  those; it goes in the platform or driver package.
- Any display change: run `scripts/scenario-shots.sh` and check the PNGs in
  `docs/display/` before flashing. They are rendered through the same RGB
  3-3-2 palette the panel uses (every designed colour already sits on that
  grid); the host build shows the same drawing live but in full colour.
- The device builds serve the live screen at `http://<board>/screen.png`
  for Home Assistant's Generic Camera (docs/screen-in-ha.md). It streams
  from the ST7789's 8-bit buffer; keep `color_palette: 8BIT` and rotation
  0 or the endpoint returns 500.
- The bench Home Assistant dashboard (virtual board) is
  `docs/ha/dryer-bench-dashboard.yaml`; its header lists what it needs on
  the HA side (HACS Tabdeck Card, °C display units on the temperature
  sensors, the camera at 0.5 Hz). Keep it in step with the dashboard
  published on the dev instance, and keep its help text in step with the
  control logic when either changes.
- To prove a refactor changed nothing, dump `esphome config` before and
  after and diff through `scripts/normalize-config.py`.
- First boot: read the three DS18B20 addresses from the log and fill in the
  `address:` placeholders; identify probes by warming them one at a time.
- Don't invent sensor addresses, thresholds, or "tested" values. Mark anything
  unverified as such.
- Keep the C++ in lambdas small; prefer ESPHome components/automations when
  they exist.

## Open items

- Confirm real breakthrough curve and regen time; retune defaults.
- Decide whether a proper dew-point transmitter (4–20 mA / Modbus) is needed
  once real data is in.
- PCB design is a separate effort; the breadboard wiring is in docs/hardware.md.
- Before wiring real heaters: make the four heater/valve switches
  `internal: true` with read-only binary_sensor mirrors. A manual toggle from
  HA can currently turn on the active pack's heater for up to one 5 s tick.
- The max-service fallback only fires from READY. A standby stuck in COOLING
  (cooldown below ambient, probe reading high) never swaps and only shows
  "(waiting)" if RH is also high. Decide whether `max_service_min` should
  force a swap from any state with a warning.
