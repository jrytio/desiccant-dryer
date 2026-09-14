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
  no PSRAM, no Bluetooth, CP2102 UART for flashing. The 240x240 display buffer
  (~115 KB) fits but is tight; `color_palette: 8BIT` is the fallback.
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

## Pin map (esphome/desiccant-dryer.yaml is the source of truth)

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
All thresholds are HA `number` entities. Overtemp and "heater on but no
temperature rise" latch a fault that stops everything until cleared.

Defaults (arm 5 %, swap 10 %, regen 90 °C / 15 min, cooldown 40 °C, max
service 180 min) are untested guesses meant to get first cycles logging.

## Invariants — keep these true in any change

- Heater A and heater B are interlocked; valve A and valve B are interlocked.
- The active (in-service) pack's heater is never on.
- All outputs use `restore_mode: ALWAYS_OFF` and are forced off in `on_boot`.
- `Dryer Enabled` off → everything off, state reset.
- Humidity simulation (`sim_enabled` / `sim_rh`) must never survive a reboot,
  and the display must show "SIM" whenever it is active.

## Working conventions

- Flash with `esphome run esphome/desiccant-dryer.yaml` (copy
  `secrets.yaml.example` to `secrets.yaml` first).
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
