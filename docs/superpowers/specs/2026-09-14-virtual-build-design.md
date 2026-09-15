# Virtual build and time-model refactor — design

Date: 2026-09-14
Status: approved in conversation; awaiting spec review

Amended 2026-09-15 (PR #9): fault 3 ("Standby heater not heating") now
sends the standby pack to WET, not COOLING, because that pack never reached
regen temperature and would otherwise become READY as soon as the fault was
cleared. The `standby_state = COOLING` on the fault 3 line of the tick
pseudocode below is superseded; `docs/control-logic.md` is current. The
rest of this document stands.

## Goal

Make the dryer control logic testable end to end on a bare SparkFun
ESP32-S2 Thing Plus with no sensors, relays, valves, or display attached,
driven and observed through Home Assistant, before the hardware exists.
Keep a production build that expects the real hardware. Fix the
reboot-resume bugs in the shared logic along the way, because the virtual
build is where they can be proven fixed.

## Context and constraints

- Board on hand for the virtual build: SparkFun ESP32-S2 Thing Plus, the
  same board as production. GPIO outputs and their interlocks therefore
  stay real in the virtual build; only sensors are mocked.
- Home Assistant runs on the LAN. Flashing is done from the Mac with the
  esphome CLI (2026.1.4 installed) over USB the first time, OTA after.
- The hardware is being built by someone else in parallel. The hardware
  person should only need to touch one file.
- All platform decisions in `CLAUDE.md` stand (ESPHome on ESP-IDF, logic
  on-device, must work with WiFi/HA down).

## Decisions made during brainstorming

| Question | Decision |
|---|---|
| Sensor source in the virtual build | On-device plant model with HA knobs; sliders as overrides |
| Sharing code between builds | ESPHome packages with a shared base (option 1A) |
| Time keeping | Tick-accumulated elapsed counters scaled by `time_scale` (option 2A) |
| Reboot into HEATING | Restart HEATING from scratch rather than resume timers |
| Standby overtemp during HEATING | Keep current behaviour: fault, state to COOLING, READY after clear |
| Repo hosting | Private repo `jrytio/desiccant-dryer`, work on branch `virtual-build`, PR workflow |
| Display in virtual build | Included, to exercise the RAM budget on the S2 |

## Non-goals

- Automated scenario runner driving the device from the Mac (follow-up).
- A READY-idle timeout that sends a long-idle pack back to WET (follow-up).
- Retuning control defaults; they remain untested guesses.
- Any change to the electrical design or pin map.

## 1. Repo layout

```
esphome/
  desiccant-dryer.yaml            # production: substitutions + packages base, hw-real, display
  desiccant-dryer-virtual.yaml    # virtual: substitutions + packages base, hw-virtual, display
  secrets.yaml.example            # unchanged
  secrets.ci.yaml                 # committed dummy secrets, copied into place by CI only
  packages/
    base.yaml        # platform blocks, globals, tunables, GPIO outputs, state machine,
                     # status and diagnostic entities, Simulate Humidity override, fan thermostat
    hw-real.yaml     # i2c and 1-wire buses, SHT45, three DS18B20s
    hw-virtual.yaml  # plant model, template sensors under the same ids, sim knobs
    display.yaml     # spi bus, ST7789, fonts, colors, backlight output and light
docs/
  control-logic.md     # updated for elapsed counters, boot behaviour, diagnostics
  virtual-testing.md   # setup steps and the on-device test checklist
  superpowers/specs/2026-09-14-virtual-build-design.md   # this file
.github/workflows/build.yml   # compiles both variants
README.md                     # mentions both builds
```

Top-level files carry only `substitutions` (`name`, `friendly_name`) and a
`packages:` block. The virtual build uses `name: desiccant-dryer-virtual`
and `friendly_name: Desiccant Dryer (Virtual)` so it appears in HA as a
separate device and a wrong flash onto the real unit is obvious.

Package responsibilities:

- `base.yaml` owns `esphome:` (including `on_boot`), `esp32:`, `logger:`,
  `api:`, `ota:`, `wifi:`, `captive_portal:`, `web_server:`, all globals,
  all tunable numbers, the five GPIO switches with interlocks, the
  `sim_enabled`/`sim_rh` override, `dryer_enabled`, buttons, the state
  machine `interval:` and scripts, `ctrl_rh` and the other derived
  sensors, text and binary sensors, and the case fan thermostat.
- `hw-real.yaml` owns `i2c:`, `one_wire:`, the `sht4x` sensor
  (`air_temp`, `air_rh`) and three `dallas_temp` sensors (`pack_a_temp`,
  `pack_b_temp`, `case_temp`) with placeholder addresses.
- `hw-virtual.yaml` provides the same five sensor ids as template sensors
  fed by the plant model, plus the plant globals, knobs, and plant tick.
- `display.yaml` owns `spi:`, the backlight `output:` and `light:`,
  `font:`, `color:`, and `display:`. It only reads ids that base and both
  hardware packages guarantee.

ESPHome merges packages before validation, so cross-package id references
are fine. The GPIO switches stay in base because the board and pins are
identical in both builds and the interlocks are part of the logic under
test.

## 2. Base package: control logic

### 2.1 Globals

| id | type | restore | initial | meaning |
|---|---|---|---|---|
| `active_pack` | int | yes | 0 | 0 none, 1 A, 2 B |
| `standby_state` | int | yes | 0 | 0 WET, 1 HEATING, 2 COOLING, 3 READY |
| `service_elapsed_s` | float | yes | 0 | scaled seconds since the active pack went into service |
| `heat_elapsed_s` | float | yes | 0 | scaled seconds the standby heater has run this regen |
| `hold_elapsed_s` | float | yes | 0 | scaled seconds the standby pack has been continuously at or above `regen_temp` |
| `heat_start_temp` | float | yes | NAN | standby temp when heating began; NAN means capture on the next valid tick |
| `fault_code` | int | yes | 0 | 0 none, 1 active pack overtemp, 2 standby pack overtemp, 3 standby heater not heating |
| `waiting_for_standby` | bool | no | false | RH wants a swap but standby is not READY |
| `time_scale` | float | no | 1.0 | multiplier applied to real elapsed time; production never changes it |
| `last_tick_ms` | uint32_t | no | 0 | millis at the previous control tick |

`fault_code` replaces the `fault` bool and the unrestorable `fault_msg`
string. The Fault binary sensor is `fault_code != 0`; the Fault Message
text sensor (id `fault_message`) maps the code to text and is the single
place that mapping lives; the display reads it. Both entity names are
unchanged. This
also fixes the message being blank after a reboot with a latched fault.

`millis()` timestamps are gone from the logic. Every duration is a counter
advanced by the tick.

### 2.2 Control tick (every 5 s)

```
if not dryer_enabled: return
if do_swap is running: return              # never fight the 500 ms both-closed window
dt_real = (millis - last_tick_ms) / 1000; last_tick_ms = millis
clamp dt_real to 60 s                      # stalled-loop guard (OTA, long block)
dt = dt_real * time_scale                  # scaled seconds

if active_pack == 0:                       # first run
    active_pack = 1; standby_state = WET
    service/heat/hold counters = 0; heat_start_temp = NAN
    log "Starting on pack A"; apply_outputs(); return

t_sb, t_act, rh = standby temp, active temp, ctrl_rh
service_elapsed_s += dt
service_min = service_elapsed_s / 60

# safety, evaluated every tick regardless of state
if t_act valid and t_act > overtemp: fault_code = 1
if t_sb  valid and t_sb  > overtemp: fault_code = 2; standby_state = COOLING
if fault_code != 0: apply_outputs(); return
if rh or t_sb is NaN: apply_outputs(); return

switch standby_state:
  WET:
    near_max = service_min >= max_service_min - regen_max_min
    if rh >= arm_rh or near_max:
        standby_state = HEATING; heat/hold = 0; heat_start_temp = t_sb; log
  HEATING:
    if heat_start_temp is NaN: heat_start_temp = t_sb        # post-reboot capture
    heat_elapsed_s += dt
    if heat_elapsed_s >= 300 and t_sb < heat_start_temp + 5 and t_sb < regen_temp:
        fault_code = 3; standby_state = COOLING; break
    if t_sb >= regen_temp: hold_elapsed_s += dt  else hold_elapsed_s = 0
    if hold_elapsed_s >= regen_hold_min * 60: standby_state = COOLING; log
    elif heat_elapsed_s >= regen_max_min * 60: standby_state = COOLING; warn
  COOLING:
    if t_sb <= cooldown_temp: standby_state = READY; log
  READY:
    if rh >= swap_rh or service_min >= max_service_min:
        do_swap.execute(); return          # outputs re-asserted on the next tick

waiting_for_standby = standby_state != READY and rh >= swap_rh
apply_outputs()
```

The "not heating" check keeps its hardcoded 5 °C in 5 min; the 5 min is
now 300 scaled seconds so it accelerates with everything else. It only
applies while the pack is still below `regen_temp`: a pack already at regen
temperature is heating fine even if it cannot rise another 5 °C, which
matters after a reboot when the start temperature is captured from an
already-hot pack.

### 2.3 apply_outputs script

A `script:` with no delays, so it runs synchronously when executed from
the tick. Outputs become a pure function of state:

```
a_active = active_pack == 1
sb_heat  = standby_state == HEATING and fault_code == 0 and standby temp is valid
if a_active: valve_b off; valve_a on;  heater_a off; heater_b = sb_heat
else:        valve_a off; valve_b on;  heater_b off; heater_a = sb_heat
```

Calling `turn_on` on a switch that is already on is a no-op in ESPHome,
so re-asserting every tick costs nothing and produces no log noise. This
one step fixes both reboot bugs (closed valves, unlit heater) and adds a
guard the old code lacked: a heater cannot stay on while its pack probe
reads NaN.

### 2.4 Swap script

Unchanged in behaviour: standby heater off, both valves closed, 500 ms,
next valve open, roles exchange, retired pack becomes WET,
`service_elapsed_s`, `heat_elapsed_s`, `hold_elapsed_s` reset,
`heat_start_temp = NAN`, `waiting_for_standby = false`. `mode: single`
still makes a second Force Swap during the window a no-op.

### 2.5 Boot and disable

`on_boot` (priority -100): all five outputs off; `last_tick_ms = millis()`;
if the restored `standby_state` is HEATING then `heat_elapsed_s = 0`,
`hold_elapsed_s = 0`, `heat_start_temp = NAN`. The first tick re-asserts
outputs from the restored state, so the active valve opens and, if
HEATING, the heater lights and the regen restarts from scratch. A resumed
regen would risk a spurious "not heating" fault after a long outage that
let the pack cool.

`Dryer Enabled` off: all outputs off, `active_pack = 0`,
`standby_state = WET`, all counters zero, `heat_start_temp = NAN`,
`waiting_for_standby = false`. `fault_code` is left alone; faults are only
cleared by the button.

`Clear Fault`: `fault_code = 0`.

### 2.6 Entities in base

Unchanged names: the eight tunable numbers, `Simulated RH`, the five
output switches, `Simulate Humidity`, `Dryer Enabled`, `Clear Fault`,
`Force Swap`, `Control Humidity`, `Service Time`, `WiFi Signal`, `Uptime`,
`Fault`, `IP Address`, `Fault Message`, `Dryer Status`, `Case Fan
Thermostat`, `Display Backlight` (in display.yaml).

Added, all `entity_category: diagnostic`:

- `Standby Heater Time` (min) = `heat_elapsed_s / 60` while HEATING, else 0
- `Regen Hold Time` (min) = `hold_elapsed_s / 60` while HEATING, else 0
- `Standby State` text sensor: `wet`, `heating`, `cooling`, `ready`
- `Restart` button (`platform: restart`) for reboot tests

`Service Time` now reads `service_elapsed_s / 60`.

The `Simulate Humidity` / `Simulated RH` override keeps its current
semantics and its invariants (never restored, display shows SIM). In the
virtual build it layers on top of the plant's RH exactly as it layers on
top of the SHT45 in production.

## 3. Real hardware package

`hw-real.yaml` is the current bus and sensor blocks moved verbatim:
`i2c` on GPIO1/2 at 100 kHz, `one_wire` on GPIO37, `sht4x` at 10 s with
the 3-sample moving average on humidity, three `dallas_temp` sensors with
placeholder addresses and the same ids and names. No behaviour change.

## 4. Display package

`display.yaml` is the current `spi`, `output`, `light`, `font`, `color`
and `display` blocks moved verbatim. The only lambda change is that the
fault line reads the `Fault Message` text sensor's state instead of the
removed `fault_msg` global, so the code-to-text mapping lives in one
place. It is included by both builds. On the bare virtual board nothing is attached; the driver
writes to nothing and the 240x240 buffer allocation is exercised for
real. If allocation fails the log says so and the control logic is
unaffected.

## 5. Virtual hardware package

### 5.1 Plant model

Globals, all `restore_value: true` so a reboot test sees a hot pack, not a
cold one:

| id | meaning | initial |
|---|---|---|
| `plant_t_a`, `plant_t_b` | pack temperatures, °C | 25 |
| `plant_t_case` | case temperature, °C | 25 |
| `plant_rh` | outlet RH, % | 1.0 |
| `plant_last_ms` | millis at the previous plant tick | 0 (not restored) |

Plant tick, `interval: 1s`:

```
time_scale = sim_speed                         # copied every tick; no on_value plumbing
dt = min(real elapsed, 5 s) * time_scale
ambient = sim_ambient
for each pack X:
    heating = heater_X switch is on and not sim_heater_fault
    target  = heating ? sim_heater_max : ambient
    tau     = sim_tau_min * 60
    T_X    += (target - T_X) * (1 - exp(-dt / tau))       # exact first-order step
if sim_manual_temps: T_A = sim_pack_a_temp; T_B = sim_pack_b_temp
any_heat = heater_a on or heater_b on
case target = ambient + (any_heat ? 8 : 0), tau 600 s, same update
service_min = service_elapsed_s / 60 (0 when active_pack == 0)
plant_rh = 1.0 + max(0, service_min - sim_breakthrough_min) * sim_rh_rate, clamped 0..100
```

The model reads the real GPIO switch states, so the output path is part
of what is tested. Manual temps write into the plant state, so the model
continues smoothly from the pinned values when the switch is released.

### 5.2 Template sensors

Same ids and names as `hw-real.yaml`, `update_interval: 2s`:
`air_rh` = `plant_rh`, `air_temp` = ambient + 2, `pack_a_temp`,
`pack_b_temp`, `case_temp` from the plant globals.

### 5.3 Knobs

All `entity_category: config`, icon `mdi:test-tube`, names prefixed
"Sim ", `restore_value: true` so a bench setup survives the reboot tests.
This is a different thing from the base `Simulate Humidity` override,
which stays non-persistent by invariant; the docs say so.

| Entity | Range | Default | Purpose |
|---|---|---|---|
| Sim Speed | 1–60 x, step 1 | 1 | Sets `time_scale`. Capped at 60 so one control tick is at most 5 sim-minutes |
| Sim Ambient Temp | 0–60 °C | 25 | Cooldown and fan tests |
| Sim Heater Max Temp | 40–150 °C | 110 | Set above the 120 °C overtemp limit to trigger the fault |
| Sim Thermal Time Constant | 1–30 min | 5 | Regen and cooldown pace |
| Sim Breakthrough Time | 0–600 min | 60 | Service minutes before RH starts rising |
| Sim RH Rise Rate | 0.01–10 %/min | 0.1 | Raise to about 1 to see the "waiting" state |
| Sim Heater Fault | switch | off | Heater on produces no heat; triggers "not heating" |
| Sim Manual Temps | switch | off | Pin both pack temps to the two numbers below |
| Sim Pack A Temp, Sim Pack B Temp | 0–150 °C | 25 | Used while Sim Manual Temps is on |

With the defaults and the base tunables: RH reaches 5 % at 100 min of
service and 10 % at 150 min; heating to 90 °C takes about 7 min, the hold
15 min, cooling to 40 °C about 9 min, so the standby pack is READY around
131 min and the swap fires at 150 min. At 60x that is 2.5 real minutes per
half cycle. These numbers are arbitrary and are documented as such.

## 6. Home Assistant workflow

1. `esphome/secrets.yaml` is created from the example with a generated
   `api_key` (`openssl rand -base64 32`), `ota_password`, and
   `ap_password`; the two WiFi fields are left for the user to fill.
2. First flash: board on USB, `esphome run esphome/desiccant-dryer-virtual.yaml`.
   Later flashes go OTA to `desiccant-dryer-virtual.local`.
3. HA discovers the device by mDNS under Settings, Devices and services.
   The user pastes the API key into HA's dialog.
4. All tuning and testing happen through the device's HA entities.
   `esphome logs esphome/desiccant-dryer-virtual.yaml` shows the
   state-transition log lines alongside.

The production build follows the same steps with the other YAML once the
hardware exists; it shows up as a second HA device.

## 7. CI

`.github/workflows/build.yml` runs on pushes to `main` and on pull
requests. A matrix over the two top-level YAMLs copies
`esphome/secrets.ci.yaml` to `esphome/secrets.yaml` and compiles by running
the official Docker image `ghcr.io/esphome/esphome:2026.1.4` directly, so
the version pin matches the Mac. (`esphome/build-action` was the first
choice, but its v8 release refuses ESPHome older than 2026.7.) The dummy secrets are obviously fake but syntactically valid (the API
key must be 32 base64 bytes). Font download from Google Fonts needs
network, which the hosted runner has.

## 8. Verification

There is no host-side unit test for ESPHome lambdas. Verification is:

1. `esphome config` and `esphome compile` pass for both YAMLs locally and
   in CI.
2. The virtual build is flashed to the S2 Thing Plus, joins HA, and passes
   the checklist in `docs/virtual-testing.md`. Each step names the action,
   the expected `Dryer Status` text, and the expected output switch
   states:
   - Fresh boot: "Air via A, B wet", valve A on, everything else off.
   - Hands-free cycle at 60x: heater B on at 5 % RH, "B heating";
     Standby Heater Time and Regen Hold Time climb; "B cooling"; "B ready";
     at 10 % RH valves swap, "Air via B, A wet", RH drops to baseline,
     Service Time restarts.
   - Waiting state: rise rate 1 %/min, RH passes 10 % before READY,
     status shows "(waiting)", swap follows as soon as READY.
   - Force Swap from any state: heater off first, swap happens.
   - Overtemp: heater max 130 °C, fault latches with "Standby pack
     overtemp", both heaters off, valves untouched; Clear Fault, pack
     cools, becomes READY.
   - Not heating: Sim Heater Fault on, arm, fault after 5 sim-minutes
     with "Standby heater not heating".
   - Active pack overtemp via Manual Temps.
   - Dryer Enabled off: all outputs off, "Disabled"; on: restarts on A.
   - Restart mid-service: same active pack, valve re-opens within one
     tick, Service Time continues within a minute of where it was.
   - Restart mid-HEATING: heater re-lights within one tick, heater and
     hold times restart at 0.
   - Simulate Humidity on at 12 %: swap when READY; status reflects it;
     switch is off again after a restart.
   - Fan: ambient 40 °C, Case Fan turns on; 25 °C, turns off after the
     thermostat's minimum run time.
   - Log shows no display allocation error on boot.

## 9. Error handling and edge cases

- NaN sensors: state holds, standby heater is forced off by
  `apply_outputs`, valves keep airflow. This matches the current "sensors
  not ready" behaviour and adds the heater guard.
- Fault latched: state machine stops, heaters off, valves keep airflow.
  Heater and hold counters stop advancing. Service time keeps counting,
  because air is still flowing through the active pack and the
  max-service fallback must stay meaningful after the fault is cleared.
  Cleared only by the button; survives reboot with its message.
- `millis()` wrap: unsigned subtraction is wrap-safe; the 60 s clamp
  bounds any single step.
- Flash wear: ESPHome batches preference writes (default 1 min on ESP32),
  so counters changing every 5 s cause one NVS write per minute. A power
  loss loses at most one minute of counters. `flash_write_interval` is left
  at the default.
- Sim Speed changed mid-cycle: counters and plant both use the same
  scaled dt, so the cycle stays consistent.
- Reboot mid-swap (both valves closed): `active_pack` still names the old
  pack, the first tick re-opens its valve, and the next READY tick swaps
  again. Safe.
- Tick landing during the 500 ms swap window: impossible from the tick's
  own swap (5 s spacing) and guarded by the `is_running` check for the
  Force Swap button.

## 10. Follow-ups (not in this work)

- Automated scenario runner on the Mac using `aioesphomeapi` that sets
  knobs, watches entities, and asserts transitions.
- Extract the state machine into a C++ header included from the lambda,
  with host-side unit tests using a fake clock. Would replace most of the
  manual checklist.
- READY-idle timeout back to WET, since open packs reabsorb moisture.
- Retune all defaults from real breakthrough and regen data.
