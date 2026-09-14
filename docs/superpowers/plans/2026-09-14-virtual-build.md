# Virtual Build and Elapsed-Time Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the ESPHome config into a shared base plus real and virtual hardware packages, replace `millis()` timestamps with persisted scaled elapsed counters so reboots resume correctly and time can be accelerated, add an on-device plant model so the whole control loop can be exercised on a bare ESP32-S2 through Home Assistant, and put both builds under CI.

**Architecture:** ESPHome packages. `packages/base.yaml` owns platform blocks, globals, tunables, GPIO outputs, the state machine and derived entities. `packages/hw-real.yaml` and `packages/hw-virtual.yaml` each provide the same five sensor ids (`air_rh`, `air_temp`, `pack_a_temp`, `pack_b_temp`, `case_temp`), the virtual one from a first-order plant model driven by the real GPIO switch states. `packages/display.yaml` is shared. Two ten-line top-level files select the combination. Outputs are re-asserted from state every tick by an `apply_outputs` script.

**Tech Stack:** ESPHome 2026.1.4 on ESP-IDF, SparkFun ESP32-S2 Thing Plus (`sparkfun_esp32s2_thing_plus`), Home Assistant native API, GitHub Actions with `esphome/build-action@v8.1.0`.

**Spec:** `docs/superpowers/specs/2026-09-14-virtual-build-design.md`

## Global Constraints

- ESPHome version: 2026.1.4 locally and in CI (`version: 2026.1.4`).
- Board: `sparkfun_esp32s2_thing_plus`, `variant: esp32s2`, `framework: type: esp-idf`. Never change.
- Pin map unchanged: heater A 13, heater B 12, valve A 11, valve B 10, fan 6, I2C 1/2, SPI 36/35, display CS 5 / DC 9 / RST 14 / BL 17, 1-wire 37.
- Every output switch keeps `restore_mode: ALWAYS_OFF` and is forced off in `on_boot`.
- Heater A/B interlocked; valve A/B interlocked; the active pack's heater is never on.
- `Simulate Humidity` / `Simulated RH` (base) must never survive a reboot; the display shows "SIM" whenever it is active.
- `time_scale` global is 1.0 in production and is only written by the virtual package.
- Entity names that already exist keep their exact names (HA history).
- Device names: production `desiccant-dryer` / `Desiccant Dryer`; virtual `desiccant-dryer-virtual` / `Desiccant Dryer (Virtual)`.
- Keep C++ in lambdas small; prefer ESPHome components/automations when they exist.
- All commits on branch `virtual-build`, message trailer `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- Work from repo root `/Users/josh/GitHub/desiccant-dryer`. `esphome` is on PATH. macOS has no `timeout` command.
- Local compiles need `esphome/secrets.yaml` (gitignored). Until real secrets exist, copy `esphome/secrets.ci.yaml` there.

## File map

| Path | Responsibility | Task |
|---|---|---|
| `esphome/desiccant-dryer.yaml` | Production top-level: substitutions + packages | 1 |
| `esphome/desiccant-dryer-virtual.yaml` | Virtual top-level: substitutions + packages | 3 |
| `esphome/packages/base.yaml` | Platform blocks, globals, tunables, outputs, state machine, derived entities, fan thermostat | 1 (move), 2 (refactor) |
| `esphome/packages/hw-real.yaml` | I2C, 1-wire, SHT45, three DS18B20s | 1 |
| `esphome/packages/hw-virtual.yaml` | Plant model, template sensors, sim knobs | 3 |
| `esphome/packages/display.yaml` | SPI, backlight, fonts, colors, ST7789 lambda | 1 (move), 2 (fault line) |
| `esphome/secrets.ci.yaml` | Dummy secrets for CI and local compile checks | 1 |
| `scripts/normalize-config.py` | Canonicalises `esphome config` output for equivalence diffs | 1 |
| `.github/workflows/build.yml` | Compiles both variants | 4 |
| `docs/control-logic.md` | Updated state machine, time, boot, faults | 5 |
| `docs/virtual-testing.md` | Bench setup and test checklist | 5 |
| `README.md`, `CLAUDE.md` | Layout and conventions | 5 |

---

### Task 1: Split the config into packages with no behaviour change

**Files:**
- Create: `esphome/packages/base.yaml`, `esphome/packages/hw-real.yaml`, `esphome/packages/display.yaml`, `esphome/secrets.ci.yaml`, `scripts/normalize-config.py`
- Modify: `esphome/desiccant-dryer.yaml` (replace entire file)

**Interfaces:**
- Consumes: the baseline `esphome/desiccant-dryer.yaml` at commit `bdc149c` (629 lines; line numbers below refer to it and must not have shifted — verify with the `git show` step).
- Produces: package files whose merged config is byte-for-byte equivalent (after normalisation) to the baseline. Sensor ids `air_rh`, `air_temp`, `pack_a_temp`, `pack_b_temp`, `case_temp` live in `hw-real.yaml`; everything else the display and base reference lives in `base.yaml`. `secrets.ci.yaml` provides valid dummy values for every `!secret` key.

- [ ] **Step 1: Confirm the baseline line numbers are intact**

Run:
```bash
cd /Users/josh/GitHub/desiccant-dryer && git status --short && git rev-parse --short HEAD && sed -n '31p;71p;87p;304p;351p;376p;378p;429p;431p;552p;73p;77p;83p;85p;321p;349p;79p;81p;306p;317p;554p;629p' esphome/desiccant-dryer.yaml
```
Expected: clean tree on `virtual-build`, and the printed lines are, in order: `esphome:`, `  port: 80`, `# ---------------------------------------------------------------- globals`, `      - script.execute: do_swap`, `  # The humidity the controller actually acts on: real or simulated.`, `    name: "Uptime"`, `binary_sensor:`, `      temperature_step: 1`, `# ---------------------------------------------------------------- cycle logic`, `          id(waiting_for_standby) = (id(standby_state) != 3 && rh >= id(swap_rh).state);`, `# ---------------------------------------------------------------- buses`, `  frequency: 100kHz`, `one_wire:`, `    pin: GPIO37`, `  - platform: sht4x`, `    update_interval: 10s`, `spi:`, `  mosi_pin: GPIO35`, `output:`, `    default_transition_length: 0s`, `# ---------------------------------------------------------------- display`, and the last `it.print(...ip_addr...)` line. (Ranges 73, 87 and 554 start on the section-divider comment on purpose, so it becomes the header of the moved section.) If any line differs, stop: the ranges below are wrong.

- [ ] **Step 2: Capture the baseline's generated config for the equivalence test**

Run:
```bash
cd /Users/josh/GitHub/desiccant-dryer && mkdir -p /tmp/dd-baseline && cp esphome/desiccant-dryer.yaml /tmp/dd-baseline/ && cat > /tmp/dd-baseline/secrets.yaml <<'EOF'
wifi_ssid: "ci-placeholder"
wifi_password: "ci-placeholder"
ap_password: "ci-placeholder"
api_key: "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
ota_password: "ci-placeholder"
EOF
(cd /tmp/dd-baseline && esphome config desiccant-dryer.yaml > baseline-config.txt 2>&1); tail -1 /tmp/dd-baseline/baseline-config.txt
```
Expected: `INFO Configuration is valid!`

- [ ] **Step 3: Write the normaliser script**

Create `scripts/normalize-config.py`:
```python
#!/usr/bin/env python3
"""Canonicalise `esphome config` output so two configs can be diffed
regardless of section order or list order.

Usage: normalize-config.py CONFIG_DUMP.txt > canonical.json
Run with ESPHome's own Python so PyYAML is available, e.g.
  "$(dirname "$(readlink -f "$(which esphome)")")/python" scripts/normalize-config.py dump.txt
"""
import json
import sys

import yaml


class AnyTag(yaml.SafeLoader):
    """SafeLoader that keeps unknown tags such as !lambda as data."""


def _any_ctor(loader, tag_suffix, node):
    if isinstance(node, yaml.ScalarNode):
        return {"__tag__": tag_suffix, "v": loader.construct_scalar(node)}
    if isinstance(node, yaml.SequenceNode):
        return {"__tag__": tag_suffix, "v": loader.construct_sequence(node)}
    return {"__tag__": tag_suffix, "v": loader.construct_mapping(node)}


AnyTag.add_multi_constructor("!", _any_ctor)


def canon(x):
    if isinstance(x, dict):
        return {k: canon(v) for k, v in sorted(x.items())}
    if isinstance(x, list):
        return sorted((canon(v) for v in x), key=lambda v: json.dumps(v, sort_keys=True))
    return x


def main(path):
    with open(path) as f:
        text = "".join(l for l in f if not l.startswith(("INFO", "WARNING")))
    print(json.dumps(canon(yaml.load(text, Loader=AnyTag)), indent=1, sort_keys=True))


if __name__ == "__main__":
    main(sys.argv[1])
```

- [ ] **Step 4: Write the dummy CI secrets**

Create `esphome/secrets.ci.yaml`:
```yaml
# Dummy secrets for CI compiles and local config checks only.
# The API key is 32 zero bytes in base64. Never flash a build made with these.
wifi_ssid: "ci-placeholder"
wifi_password: "ci-placeholder"
ap_password: "ci-placeholder"
api_key: "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
ota_password: "ci-placeholder"
```

- [ ] **Step 5: Extract the three packages from the baseline by line range**

Run this exactly (it reads the committed baseline, not the working file):
```bash
cd /Users/josh/GitHub/desiccant-dryer && mkdir -p esphome/packages && git show bdc149c:esphome/desiccant-dryer.yaml > /tmp/dd-baseline/src.yaml && SRC=/tmp/dd-baseline/src.yaml && {
  echo "# Shared base for both builds. The top-level file supplies \${name} and"
  echo "# \${friendly_name} and picks a hardware package (hw-real or hw-virtual)"
  echo "# plus display. This file must only reference these sensor ids from the"
  echo "# hardware package: air_rh, air_temp, pack_a_temp, pack_b_temp, case_temp."
  echo
  sed -n '31,71p' $SRC
  sed -n '87,304p' $SRC
  echo "sensor:"
  sed -n '351,376p' $SRC
  echo
  sed -n '378,429p' $SRC
  echo
  sed -n '431,552p' $SRC
} > esphome/packages/base.yaml && {
  echo "# Real hardware: sensor buses and sensors. Provides the sensor ids base.yaml"
  echo "# expects: air_rh, air_temp, pack_a_temp, pack_b_temp, case_temp."
  echo "#   GPIO1/2 I2C (Qwiic) - SHT45 in the process-air stream after the valves"
  echo "#   GPIO37  1-wire (MISO header pin) - DS18B20 x3: pack A, pack B, case"
  echo
  sed -n '73,77p' $SRC
  echo
  sed -n '83,85p' $SRC
  echo
  echo "sensor:"
  sed -n '321,349p' $SRC
} > esphome/packages/hw-real.yaml && {
  echo "# ST7789 1.54\" 240x240 display on SPI, shared by both builds. On the virtual"
  echo "# build nothing is attached; the driver still runs so the frame buffer"
  echo "# allocation on the S2 gets exercised."
  echo "#   GPIO36/35 SPI SCK/MOSI, GPIO5 CS, GPIO9 DC, GPIO14 RST, GPIO17 backlight"
  echo
  sed -n '79,81p' $SRC
  echo
  sed -n '306,317p' $SRC
  echo
  sed -n '554,629p' $SRC
} > esphome/packages/display.yaml && wc -l esphome/packages/*.yaml
```
Expected line counts: base ~467, hw-real ~45, display ~98.

- [ ] **Step 6: Replace the top-level production file**

Overwrite `esphome/desiccant-dryer.yaml` with exactly:
```yaml
# Production build: real sensors on the SparkFun ESP32-S2 Thing Plus.
# Flash:  esphome run esphome/desiccant-dryer.yaml
# Logic:  packages/base.yaml      (shared with the virtual build)
# Wiring: packages/hw-real.yaml   (the only file the hardware side needs)
substitutions:
  name: desiccant-dryer
  friendly_name: Desiccant Dryer

packages:
  base: !include packages/base.yaml
  hardware: !include packages/hw-real.yaml
  display: !include packages/display.yaml
```

- [ ] **Step 7: Validate and prove equivalence**

Run:
```bash
cd /Users/josh/GitHub/desiccant-dryer && cp esphome/secrets.ci.yaml esphome/secrets.yaml && esphome config esphome/desiccant-dryer.yaml > /tmp/dd-baseline/split-config.txt 2>&1; tail -1 /tmp/dd-baseline/split-config.txt && PY="$(dirname "$(readlink -f "$(which esphome)")")/python" && $PY scripts/normalize-config.py /tmp/dd-baseline/baseline-config.txt > /tmp/dd-baseline/a.json && $PY scripts/normalize-config.py /tmp/dd-baseline/split-config.txt > /tmp/dd-baseline/b.json && diff /tmp/dd-baseline/a.json /tmp/dd-baseline/b.json && echo EQUIVALENT
```
Expected: `INFO Configuration is valid!` then `EQUIVALENT` with no diff lines. Note `esphome/secrets.yaml` is gitignored; leave it in place for later compiles.

- [ ] **Step 8: Commit**

```bash
cd /Users/josh/GitHub/desiccant-dryer && git add esphome/desiccant-dryer.yaml esphome/packages esphome/secrets.ci.yaml scripts/normalize-config.py && git commit -m "Split config into base, hw-real and display packages

No behaviour change: the merged config normalises identically to the
single-file baseline. Adds dummy CI secrets and the normaliser script
used for that check.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: Elapsed-time refactor and output re-assertion in base.yaml

**Files:**
- Modify: `esphome/packages/base.yaml` (replace entire file)
- Modify: `esphome/packages/display.yaml` (fault lines in the display lambda)

**Interfaces:**
- Consumes: sensor ids `air_rh`, `air_temp`, `pack_a_temp`, `pack_b_temp`, `case_temp` from the hardware package; `ip_addr` text sensor and switches from base itself.
- Produces (used by Task 3 and the display): globals `active_pack` (int), `standby_state` (int), `service_elapsed_s` (float), `heat_elapsed_s` (float), `hold_elapsed_s` (float), `heat_start_temp` (float), `fault_code` (int), `waiting_for_standby` (bool), `time_scale` (float), `last_tick_ms` (uint32_t); scripts `apply_outputs` and `do_swap`; text sensor `fault_message`; switches `heater_a`, `heater_b`, `valve_a`, `valve_b`, `case_fan`, `sim_enabled`, `dryer_enabled`; sensor `ctrl_rh`.

- [ ] **Step 1: Replace base.yaml with the refactored version**

Overwrite `esphome/packages/base.yaml` with exactly:
```yaml
# Shared base for both builds. The top-level file supplies ${name} and
# ${friendly_name} and picks a hardware package (hw-real or hw-virtual)
# plus display. This file must only reference these sensor ids from the
# hardware package: air_rh, air_temp, pack_a_temp, pack_b_temp, case_temp.
#
# Outputs (12-pin header), identical on both builds:
#   GPIO13  Heater A relay coil (5 V, low-side NPN)     interlocked with B
#   GPIO12  Heater B relay coil                          interlocked with A
#   GPIO11  Valve A  (24 V solenoid, low-side MOSFET)   interlocked with B
#   GPIO10  Valve B                                      interlocked with A
#   GPIO6   Case fan (24 V, low-side MOSFET)
#
# Cycle logic (control tick every 5 s):
#   One pack is "active" (valve open, heater off). The other is "standby" and
#   moves through: WET -> HEATING -> COOLING -> READY.
#     WET      -> HEATING  when outlet RH >= arm_rh (or service time nears max)
#     HEATING  -> COOLING  when pack temp has been >= regen_temp for regen_hold min
#                          (or heater has run regen_max min - logged as a warning)
#     COOLING  -> READY    when pack temp <= cooldown_temp
#     READY    -> swap     when outlet RH >= swap_rh, or service time >= max_service
#   Time: elapsed-second counters advanced by each tick and scaled by
#   time_scale (1.0 in production; the virtual build accelerates it). The
#   counters persist, so a reboot resumes the cycle. Outputs are re-asserted
#   from state every tick (apply_outputs), so a reboot re-opens the active
#   valve and re-lights a heater.
#   Safety: any pack above overtemp -> heaters off + fault. Heater on 5 min
#   with no temperature rise -> fault. Faults latch until cleared in HA.

esphome:
  name: ${name}
  friendly_name: ${friendly_name}
  on_boot:
    priority: -100
    then:
      - lambda: |-
          // Everything off until the state machine has run once.
          id(heater_a).turn_off();
          id(heater_b).turn_off();
          id(valve_a).turn_off();
          id(valve_b).turn_off();
          id(case_fan).turn_off();
          id(last_tick_ms) = millis();
          // A regen interrupted by a reboot restarts from scratch: the pack may
          // have cooled during the outage, and resuming the old timer would
          // trip the "not heating" check.
          if (id(standby_state) == 1) {
            id(heat_elapsed_s) = 0;
            id(hold_elapsed_s) = 0;
            id(heat_start_temp) = NAN;
          }

esp32:
  board: sparkfun_esp32s2_thing_plus   # if rejected, esp32-s2-saola-1 works (same module)
  variant: esp32s2
  framework:
    type: esp-idf

logger:
  level: INFO

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

# ---------------------------------------------------------------- globals
globals:
  # 0 = none, 1 = A, 2 = B
  - id: active_pack
    type: int
    restore_value: true
    initial_value: "0"
  # standby pack state: 0 WET, 1 HEATING, 2 COOLING, 3 READY
  - id: standby_state
    type: int
    restore_value: true
    initial_value: "0"
  # Elapsed counters in scaled seconds. Persisted so a reboot resumes mid-cycle
  # (ESPHome batches flash writes about once a minute).
  - id: service_elapsed_s
    type: float
    restore_value: true
    initial_value: "0"
  - id: heat_elapsed_s
    type: float
    restore_value: true
    initial_value: "0"
  - id: hold_elapsed_s
    type: float
    restore_value: true
    initial_value: "0"
  # Standby temp when heating began. NAN = capture on the next valid tick.
  - id: heat_start_temp
    type: float
    restore_value: true
    initial_value: "NAN"
  # 0 none, 1 active pack overtemp, 2 standby pack overtemp,
  # 3 standby heater not heating. Text lives in the Fault Message sensor.
  - id: fault_code
    type: int
    restore_value: true
    initial_value: "0"
  - id: waiting_for_standby
    type: bool
    initial_value: "false"
  # Multiplier on real elapsed time. Production leaves this at 1.0; only the
  # virtual package's "Sim Speed" writes it.
  - id: time_scale
    type: float
    initial_value: "1.0"
  - id: last_tick_ms
    type: uint32_t
    initial_value: "0"

# ---------------------------------------------------------------- tunables
number:
  - platform: template
    name: "Arm RH (start heating standby)"
    id: arm_rh
    unit_of_measurement: "%"
    min_value: 0.5
    max_value: 50
    step: 0.5
    initial_value: 5
    restore_value: true
    optimistic: true
    entity_category: config
  - platform: template
    name: "Swap RH"
    id: swap_rh
    unit_of_measurement: "%"
    min_value: 1
    max_value: 60
    step: 0.5
    initial_value: 10
    restore_value: true
    optimistic: true
    entity_category: config
  - platform: template
    name: "Regen temp"
    id: regen_temp
    unit_of_measurement: "°C"
    min_value: 40
    max_value: 120
    step: 1
    initial_value: 90
    restore_value: true
    optimistic: true
    entity_category: config
  - platform: template
    name: "Regen hold time"
    id: regen_hold_min
    unit_of_measurement: "min"
    min_value: 1
    max_value: 120
    step: 1
    initial_value: 15
    restore_value: true
    optimistic: true
    entity_category: config
  - platform: template
    name: "Regen max heater time"
    id: regen_max_min
    unit_of_measurement: "min"
    min_value: 5
    max_value: 240
    step: 5
    initial_value: 60
    restore_value: true
    optimistic: true
    entity_category: config
  - platform: template
    name: "Cooldown temp"
    id: cooldown_temp
    unit_of_measurement: "°C"
    min_value: 20
    max_value: 80
    step: 1
    initial_value: 40
    restore_value: true
    optimistic: true
    entity_category: config
  - platform: template
    name: "Max service time"
    id: max_service_min
    unit_of_measurement: "min"
    min_value: 10
    max_value: 600
    step: 5
    initial_value: 180
    restore_value: true
    optimistic: true
    entity_category: config
  - platform: template
    name: "Pack overtemp limit"
    id: overtemp
    unit_of_measurement: "°C"
    min_value: 60
    max_value: 125
    step: 1
    initial_value: 120
    restore_value: true
    optimistic: true
    entity_category: config

  # Simulation: when "Simulate Humidity" is on, this value replaces the outlet
  # humidity everywhere the control logic and display use it. Never persisted.
  - platform: template
    name: "Simulated RH"
    id: sim_rh
    unit_of_measurement: "%"
    min_value: 0
    max_value: 100
    step: 0.5
    initial_value: 2
    restore_value: false
    optimistic: true
    entity_category: config
    icon: mdi:test-tube

# ---------------------------------------------------------------- outputs
switch:
  - platform: gpio
    name: "Heater A"
    id: heater_a
    pin: GPIO13
    restore_mode: ALWAYS_OFF
    interlock: [heater_b]
    interlock_wait_time: 500ms
    icon: mdi:radiator
  - platform: gpio
    name: "Heater B"
    id: heater_b
    pin: GPIO12
    restore_mode: ALWAYS_OFF
    interlock: [heater_a]
    interlock_wait_time: 500ms
    icon: mdi:radiator
  - platform: gpio
    name: "Valve A"
    id: valve_a
    pin: GPIO11
    restore_mode: ALWAYS_OFF
    interlock: [valve_b]
    interlock_wait_time: 500ms
    icon: mdi:valve
  - platform: gpio
    name: "Valve B"
    id: valve_b
    pin: GPIO10
    restore_mode: ALWAYS_OFF
    interlock: [valve_a]
    interlock_wait_time: 500ms
    icon: mdi:valve
  - platform: gpio
    name: "Case Fan"
    id: case_fan
    pin: GPIO6
    restore_mode: ALWAYS_OFF
    icon: mdi:fan

  - platform: template
    name: "Simulate Humidity"
    id: sim_enabled
    optimistic: true
    restore_mode: ALWAYS_OFF
    icon: mdi:test-tube
    entity_category: config

  - platform: template
    name: "Dryer Enabled"
    id: dryer_enabled
    optimistic: true
    restore_mode: RESTORE_DEFAULT_ON
    icon: mdi:power
    on_turn_off:
      - lambda: |-
          id(heater_a).turn_off();
          id(heater_b).turn_off();
          id(valve_a).turn_off();
          id(valve_b).turn_off();
          id(active_pack) = 0;
          id(standby_state) = 0;
          id(service_elapsed_s) = 0;
          id(heat_elapsed_s) = 0;
          id(hold_elapsed_s) = 0;
          id(heat_start_temp) = NAN;
          id(waiting_for_standby) = false;

button:
  - platform: template
    name: "Clear Fault"
    icon: mdi:alert-remove
    on_press:
      - lambda: |-
          id(fault_code) = 0;
  - platform: template
    name: "Force Swap"
    icon: mdi:swap-horizontal
    on_press:
      - script.execute: do_swap
  - platform: restart
    name: "Restart"
    entity_category: diagnostic

# ---------------------------------------------------------------- derived sensors
sensor:
  # The humidity the controller actually acts on: real or simulated.
  - platform: template
    name: "Control Humidity"
    id: ctrl_rh
    unit_of_measurement: "%"
    accuracy_decimals: 1
    lambda: |-
      if (id(sim_enabled).state) return id(sim_rh).state;
      return id(air_rh).state;
    update_interval: 5s

  - platform: template
    name: "Service Time"
    id: service_min
    unit_of_measurement: "min"
    accuracy_decimals: 0
    lambda: |-
      if (id(active_pack) == 0) return 0;
      return id(service_elapsed_s) / 60.0f;
    update_interval: 10s

  - platform: template
    name: "Standby Heater Time"
    id: heat_min
    unit_of_measurement: "min"
    accuracy_decimals: 1
    entity_category: diagnostic
    lambda: |-
      if (id(standby_state) != 1) return 0;
      return id(heat_elapsed_s) / 60.0f;
    update_interval: 10s

  - platform: template
    name: "Regen Hold Time"
    id: hold_min
    unit_of_measurement: "min"
    accuracy_decimals: 1
    entity_category: diagnostic
    lambda: |-
      if (id(standby_state) != 1) return 0;
      return id(hold_elapsed_s) / 60.0f;
    update_interval: 10s

  - platform: wifi_signal
    name: "WiFi Signal"
    update_interval: 60s
  - platform: uptime
    name: "Uptime"

binary_sensor:
  - platform: template
    name: "Fault"
    device_class: problem
    lambda: return id(fault_code) != 0;

text_sensor:
  - platform: wifi_info
    ip_address:
      name: "IP Address"
      id: ip_addr
  # Single place the fault code becomes text; the display reads this too.
  - platform: template
    name: "Fault Message"
    id: fault_message
    update_interval: 5s
    lambda: |-
      switch (id(fault_code)) {
        case 1: return std::string("Active pack overtemp");
        case 2: return std::string("Standby pack overtemp");
        case 3: return std::string("Standby heater not heating");
        default: return std::string("");
      }
  - platform: template
    name: "Standby State"
    id: standby_state_text
    entity_category: diagnostic
    update_interval: 5s
    lambda: |-
      const char* st[] = {"wet", "heating", "cooling", "ready"};
      return std::string(st[id(standby_state)]);
  - platform: template
    name: "Dryer Status"
    id: status_text
    update_interval: 5s
    lambda: |-
      if (!id(dryer_enabled).state) return std::string("Disabled");
      if (id(active_pack) == 0) return std::string("Starting");
      std::string act = id(active_pack) == 1 ? "A" : "B";
      std::string sb  = id(active_pack) == 1 ? "B" : "A";
      const char* st[] = {"wet", "heating", "cooling", "ready"};
      std::string s = "Air via " + act + ", " + sb + " " + st[id(standby_state)];
      if (id(waiting_for_standby)) s += " (waiting)";
      return s;

# ---------------------------------------------------------------- fan thermostat
climate:
  - platform: thermostat
    name: "Case Fan Thermostat"
    sensor: case_temp
    min_cooling_off_time: 60s
    min_cooling_run_time: 60s
    min_idle_time: 30s
    cool_action:
      - switch.turn_on: case_fan
    idle_action:
      - switch.turn_off: case_fan
    default_preset: Normal
    preset:
      - name: Normal
        default_target_temperature_high: 35
        mode: cool
    cool_deadband: 1.5
    cool_overrun: 1.5
    visual:
      min_temperature: 20
      max_temperature: 60
      temperature_step: 1

# ---------------------------------------------------------------- cycle logic
script:
  # Outputs are a pure function of state. Runs at the end of every control
  # tick, so a reboot or a missed transition can never leave the active valve
  # closed or a heater in the wrong state. ESPHome ignores turn_on/turn_off on
  # a switch already in that state, so this is silent when nothing changes.
  - id: apply_outputs
    mode: single
    then:
      - lambda: |-
          if (id(active_pack) == 0) return;
          const bool a_active = (id(active_pack) == 1);
          const float t_sb = a_active ? id(pack_b_temp).state : id(pack_a_temp).state;
          const bool sb_heat = id(standby_state) == 1 && id(fault_code) == 0 && !isnan(t_sb);
          if (a_active) {
            id(valve_b).turn_off();
            id(valve_a).turn_on();
            id(heater_a).turn_off();
            if (sb_heat) id(heater_b).turn_on(); else id(heater_b).turn_off();
          } else {
            id(valve_a).turn_off();
            id(valve_b).turn_on();
            id(heater_b).turn_off();
            if (sb_heat) id(heater_a).turn_on(); else id(heater_a).turn_off();
          }

  - id: do_swap
    mode: single
    then:
      - lambda: |-
          if (id(active_pack) == 0) return;
          int next = (id(active_pack) == 1) ? 2 : 1;
          ESP_LOGI("cycle", "Swapping air to pack %s", next == 1 ? "A" : "B");
          // heater off on the pack about to go into service
          if (next == 1) id(heater_a).turn_off(); else id(heater_b).turn_off();
          id(valve_a).turn_off();
          id(valve_b).turn_off();
      - delay: 500ms
      - lambda: |-
          if (id(active_pack) == 0) return;   // disabled during the delay
          int next = (id(active_pack) == 1) ? 2 : 1;
          if (next == 1) id(valve_a).turn_on(); else id(valve_b).turn_on();
          id(active_pack) = next;
          id(standby_state) = 0;          // the pack just retired is WET
          id(service_elapsed_s) = 0;
          id(heat_elapsed_s) = 0;
          id(hold_elapsed_s) = 0;
          id(heat_start_temp) = NAN;
          id(waiting_for_standby) = false;

interval:
  - interval: 5s
    then:
      - lambda: |-
          if (!id(dryer_enabled).state) return;
          if (id(do_swap).is_running()) return;   // never fight the both-closed window

          // --- scaled time step
          const uint32_t now = millis();
          float dt_real = (now - id(last_tick_ms)) / 1000.0f;
          id(last_tick_ms) = now;
          if (dt_real > 60.0f) dt_real = 60.0f;   // stalled-loop guard (OTA, long block)
          const float dt = dt_real * id(time_scale);

          // --- first run / after a disable: start on pack A
          if (id(active_pack) == 0) {
            id(active_pack) = 1;
            id(standby_state) = 0;
            id(service_elapsed_s) = 0;
            id(heat_elapsed_s) = 0;
            id(hold_elapsed_s) = 0;
            id(heat_start_temp) = NAN;
            ESP_LOGI("cycle", "Starting on pack A");
            id(apply_outputs).execute();
            return;
          }

          const bool a_active = (id(active_pack) == 1);
          const float t_sb  = a_active ? id(pack_b_temp).state : id(pack_a_temp).state;
          const float t_act = a_active ? id(pack_a_temp).state : id(pack_b_temp).state;
          const float rh    = id(ctrl_rh).state;

          // Service time counts whenever a pack is in service, faults included:
          // air is still flowing through it.
          id(service_elapsed_s) += dt;
          const float service_m = id(service_elapsed_s) / 60.0f;

          // --- safety: overtemp on either pack, checked every tick
          if (!isnan(t_act) && t_act > id(overtemp).state) {
            id(fault_code) = 1;
            ESP_LOGE("cycle", "FAULT: active pack overtemp (%.1f C)", t_act);
          }
          if (!isnan(t_sb) && t_sb > id(overtemp).state) {
            id(fault_code) = 2;
            id(standby_state) = 2;
            ESP_LOGE("cycle", "FAULT: standby pack overtemp (%.1f C)", t_sb);
          }
          if (id(fault_code) != 0) { id(apply_outputs).execute(); return; }   // hold until cleared
          if (isnan(rh) || isnan(t_sb)) { id(apply_outputs).execute(); return; }   // sensors not ready

          switch (id(standby_state)) {
            case 0: { // WET - wait for breakthrough to begin, or run out of runway
              const bool near_max = service_m >= id(max_service_min).state - id(regen_max_min).state;
              if (rh >= id(arm_rh).state || near_max) {
                id(standby_state) = 1;
                id(heat_elapsed_s) = 0;
                id(hold_elapsed_s) = 0;
                id(heat_start_temp) = t_sb;
                ESP_LOGI("cycle", "Standby heater on (RH %.1f%%, service %.0f min)", rh, service_m);
              }
              break;
            }
            case 1: { // HEATING
              if (isnan(id(heat_start_temp))) id(heat_start_temp) = t_sb;   // after a reboot
              id(heat_elapsed_s) += dt;
              const float heat_m = id(heat_elapsed_s) / 60.0f;
              // "Not heating": 5 min on with under 5 C of rise, judged only while
              // still below regen temp. A pack already at regen temp is heating
              // fine even if it can't rise another 5 C (matters after a reboot,
              // when the start temp is captured from an already-hot pack).
              if (id(heat_elapsed_s) >= 300.0f && t_sb < id(heat_start_temp) + 5.0f
                  && t_sb < id(regen_temp).state) {
                id(fault_code) = 3;
                id(standby_state) = 2;
                ESP_LOGE("cycle", "FAULT: standby heater not heating (%.1f C after %.0f min)", t_sb, heat_m);
                break;
              }
              if (t_sb >= id(regen_temp).state) id(hold_elapsed_s) += dt; else id(hold_elapsed_s) = 0;
              if (id(hold_elapsed_s) >= id(regen_hold_min).state * 60.0f) {
                id(standby_state) = 2;
                ESP_LOGI("cycle", "Regen complete after %.0f min", heat_m);
              } else if (id(heat_elapsed_s) >= id(regen_max_min).state * 60.0f) {
                id(standby_state) = 2;
                ESP_LOGW("cycle", "Regen hit max heater time (%.0f min)", heat_m);
              }
              break;
            }
            case 2: { // COOLING
              if (t_sb <= id(cooldown_temp).state) {
                id(standby_state) = 3;
                ESP_LOGI("cycle", "Standby pack ready");
              }
              break;
            }
            case 3: { // READY
              if (rh >= id(swap_rh).state || service_m >= id(max_service_min).state) {
                id(do_swap).execute();
                return;   // outputs are re-asserted on the next tick, after the swap
              }
              break;
            }
          }

          // note when we'd like to swap but the standby pack isn't ready
          id(waiting_for_standby) = (id(standby_state) != 3 && rh >= id(swap_rh).state);
          id(apply_outputs).execute();
```

- [ ] **Step 2: Point the display's fault lines at the new fault code and text sensor**

In `esphome/packages/display.yaml`, the display lambda currently contains:
```
      if (id(fault)) {
        it.print(120, 8, id(f_med), id(c_red), TextAlign::TOP_CENTER, "FAULT");
        it.print(120, 40, id(f_small), id(c_red), TextAlign::TOP_CENTER, id(fault_msg).c_str());
```
Replace those three lines with:
```
      if (id(fault_code) != 0) {
        it.print(120, 8, id(f_med), id(c_red), TextAlign::TOP_CENTER, "FAULT");
        it.print(120, 40, id(f_small), id(c_red), TextAlign::TOP_CENTER, id(fault_message).state.c_str());
```
Run to apply and confirm no stale references remain:
```bash
cd /Users/josh/GitHub/desiccant-dryer && sed -i '' -e 's/if (id(fault)) {/if (id(fault_code) != 0) {/' -e 's/id(fault_msg).c_str()/id(fault_message).state.c_str()/' esphome/packages/display.yaml && grep -rnE 'id\(fault\)|fault_msg|service_start_ms|heat_start_ms|above_regen_since_ms|millis\(\)' esphome/packages/ ; echo "grep exit=$? (1 means no stale refs except the two millis() in base tick/on_boot)"
```
Expected: the grep prints only the two `millis()` lines in `base.yaml` (`on_boot` and the tick's `const uint32_t now = millis();`). Nothing from `display.yaml`.

- [ ] **Step 3: Validate and compile the production build**

Run:
```bash
cd /Users/josh/GitHub/desiccant-dryer && esphome config esphome/desiccant-dryer.yaml > /tmp/dd-baseline/prod-config.txt 2>&1; tail -1 /tmp/dd-baseline/prod-config.txt && esphome compile esphome/desiccant-dryer.yaml > /tmp/dd-baseline/prod-compile.txt 2>&1; tail -3 /tmp/dd-baseline/prod-compile.txt; grep -E "^RAM:|^Flash:" /tmp/dd-baseline/prod-compile.txt
```
Expected: `INFO Configuration is valid!`, then `INFO Successfully compiled program.` with RAM around 11 % and Flash around 55 %. The first compile on a fresh machine downloads the ESP-IDF toolchain and takes 10 to 15 minutes; subsequent ones take 1 to 3 minutes. If the compile fails, fix the YAML and rerun; do not change the board or framework.

- [ ] **Step 4: Commit**

```bash
cd /Users/josh/GitHub/desiccant-dryer && git add esphome/packages/base.yaml esphome/packages/display.yaml && git commit -m "Replace millis timestamps with persisted scaled elapsed counters

Outputs are now re-asserted from state every tick by apply_outputs, which
fixes the active valve staying closed after a reboot and a mid-HEATING
heater never re-lighting. Service, heater and hold times persist across
reboot. A time_scale global (1.0 in production) lets the virtual build
accelerate the whole cycle. Fault state is a restored code with the text
derived in one place. Adds Standby Heater Time, Regen Hold Time, Standby
State and a Restart button as diagnostics.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: Virtual hardware package and virtual top-level build

**Files:**
- Create: `esphome/packages/hw-virtual.yaml`, `esphome/desiccant-dryer-virtual.yaml`

**Interfaces:**
- Consumes from base: globals `time_scale`, `active_pack`, `service_elapsed_s`; switches `heater_a`, `heater_b`.
- Produces: sensors `air_rh`, `air_temp`, `pack_a_temp`, `pack_b_temp`, `case_temp` with the same names as `hw-real.yaml`; globals `plant_t_a`, `plant_t_b`, `plant_t_case`, `plant_rh`, `plant_last_ms`; numbers `sim_speed`, `sim_ambient`, `sim_heater_max`, `sim_tau_min`, `sim_breakthrough_min`, `sim_rh_rate`, `sim_pack_a_temp`, `sim_pack_b_temp`; switches `sim_heater_fault`, `sim_manual_temps`.

- [ ] **Step 1: Write the virtual hardware package**

Create `esphome/packages/hw-virtual.yaml`:
```yaml
# Virtual hardware: nothing attached. A small plant model produces the five
# sensor ids base.yaml expects (air_rh, air_temp, pack_a_temp, pack_b_temp,
# case_temp) from the real GPIO output states, in time scaled by "Sim Speed".
#
# Model (first-order, integrated every second in scaled time):
#   pack temp  -> heater max while its heater switch is on, else -> ambient,
#                 with one thermal time constant for both directions
#   case temp  -> ambient + 8 C while any heater is on, 10 min time constant
#   outlet RH  =  1 % until the active pack's service time passes the
#                 breakthrough point, then rises linearly; resets on swap
#
# Everything here is a test-bench control and persists across reboots so the
# reboot tests keep their settings. That is deliberately different from the
# base "Simulate Humidity" override, which never persists.

globals:
  - id: plant_t_a
    type: float
    restore_value: true
    initial_value: "25.0"
  - id: plant_t_b
    type: float
    restore_value: true
    initial_value: "25.0"
  - id: plant_t_case
    type: float
    restore_value: true
    initial_value: "25.0"
  - id: plant_rh
    type: float
    restore_value: true
    initial_value: "1.0"
  - id: plant_last_ms
    type: uint32_t
    initial_value: "0"

number:
  - platform: template
    name: "Sim Speed"
    id: sim_speed
    unit_of_measurement: "x"
    min_value: 1
    max_value: 60
    step: 1
    initial_value: 1
    restore_value: true
    optimistic: true
    entity_category: config
    icon: mdi:test-tube
  - platform: template
    name: "Sim Ambient Temp"
    id: sim_ambient
    unit_of_measurement: "°C"
    min_value: 0
    max_value: 60
    step: 1
    initial_value: 25
    restore_value: true
    optimistic: true
    entity_category: config
    icon: mdi:test-tube
  - platform: template
    name: "Sim Heater Max Temp"
    id: sim_heater_max
    unit_of_measurement: "°C"
    min_value: 40
    max_value: 150
    step: 1
    initial_value: 110
    restore_value: true
    optimistic: true
    entity_category: config
    icon: mdi:test-tube
  - platform: template
    name: "Sim Thermal Time Constant"
    id: sim_tau_min
    unit_of_measurement: "min"
    min_value: 1
    max_value: 30
    step: 1
    initial_value: 5
    restore_value: true
    optimistic: true
    entity_category: config
    icon: mdi:test-tube
  - platform: template
    name: "Sim Breakthrough Time"
    id: sim_breakthrough_min
    unit_of_measurement: "min"
    min_value: 0
    max_value: 600
    step: 5
    initial_value: 60
    restore_value: true
    optimistic: true
    entity_category: config
    icon: mdi:test-tube
  - platform: template
    name: "Sim RH Rise Rate"
    id: sim_rh_rate
    unit_of_measurement: "%/min"
    min_value: 0.01
    max_value: 10
    step: 0.01
    initial_value: 0.1
    restore_value: true
    optimistic: true
    entity_category: config
    icon: mdi:test-tube
  - platform: template
    name: "Sim Pack A Temp"
    id: sim_pack_a_temp
    unit_of_measurement: "°C"
    min_value: 0
    max_value: 150
    step: 1
    initial_value: 25
    restore_value: true
    optimistic: true
    entity_category: config
    icon: mdi:test-tube
  - platform: template
    name: "Sim Pack B Temp"
    id: sim_pack_b_temp
    unit_of_measurement: "°C"
    min_value: 0
    max_value: 150
    step: 1
    initial_value: 25
    restore_value: true
    optimistic: true
    entity_category: config
    icon: mdi:test-tube

switch:
  # Heater on produces no heat: exercises the "not heating" fault.
  - platform: template
    name: "Sim Heater Fault"
    id: sim_heater_fault
    optimistic: true
    restore_mode: RESTORE_DEFAULT_OFF
    entity_category: config
    icon: mdi:test-tube
  # Pin both pack temps to the two Sim Pack temp numbers.
  - platform: template
    name: "Sim Manual Temps"
    id: sim_manual_temps
    optimistic: true
    restore_mode: RESTORE_DEFAULT_OFF
    entity_category: config
    icon: mdi:test-tube

interval:
  - interval: 1s
    then:
      - lambda: |-
          float speed = id(sim_speed).state;
          if (isnan(speed) || speed < 1.0f) speed = 1.0f;
          id(time_scale) = speed;

          const uint32_t now = millis();
          float dt_real = (now - id(plant_last_ms)) / 1000.0f;
          id(plant_last_ms) = now;
          if (dt_real > 5.0f) dt_real = 5.0f;
          const float dt = dt_real * speed;

          const float ambient = id(sim_ambient).state;
          const float tau = id(sim_tau_min).state * 60.0f;
          const float k = 1.0f - expf(-dt / tau);          // exact first-order step

          const bool heat_a = id(heater_a).state && !id(sim_heater_fault).state;
          const bool heat_b = id(heater_b).state && !id(sim_heater_fault).state;
          const float target_a = heat_a ? id(sim_heater_max).state : ambient;
          const float target_b = heat_b ? id(sim_heater_max).state : ambient;
          id(plant_t_a) += (target_a - id(plant_t_a)) * k;
          id(plant_t_b) += (target_b - id(plant_t_b)) * k;
          if (id(sim_manual_temps).state) {
            id(plant_t_a) = id(sim_pack_a_temp).state;
            id(plant_t_b) = id(sim_pack_b_temp).state;
          }

          const bool any_heat = id(heater_a).state || id(heater_b).state;
          const float target_case = ambient + (any_heat ? 8.0f : 0.0f);
          const float k_case = 1.0f - expf(-dt / 600.0f);
          id(plant_t_case) += (target_case - id(plant_t_case)) * k_case;

          const float service_min = id(active_pack) == 0 ? 0.0f : id(service_elapsed_s) / 60.0f;
          float rh = 1.0f + fmaxf(0.0f, service_min - id(sim_breakthrough_min).state) * id(sim_rh_rate).state;
          if (rh > 100.0f) rh = 100.0f;
          id(plant_rh) = rh;

sensor:
  - platform: template
    name: "Outlet Air Humidity"
    id: air_rh
    unit_of_measurement: "%"
    accuracy_decimals: 1
    device_class: humidity
    state_class: measurement
    lambda: return id(plant_rh);
    update_interval: 2s
  - platform: template
    name: "Outlet Air Temperature"
    id: air_temp
    unit_of_measurement: "°C"
    accuracy_decimals: 1
    device_class: temperature
    state_class: measurement
    lambda: return id(sim_ambient).state + 2.0f;
    update_interval: 2s
  - platform: template
    name: "Pack A Temperature"
    id: pack_a_temp
    unit_of_measurement: "°C"
    accuracy_decimals: 1
    device_class: temperature
    state_class: measurement
    lambda: return id(plant_t_a);
    update_interval: 2s
  - platform: template
    name: "Pack B Temperature"
    id: pack_b_temp
    unit_of_measurement: "°C"
    accuracy_decimals: 1
    device_class: temperature
    state_class: measurement
    lambda: return id(plant_t_b);
    update_interval: 2s
  - platform: template
    name: "Case Temperature"
    id: case_temp
    unit_of_measurement: "°C"
    accuracy_decimals: 1
    device_class: temperature
    state_class: measurement
    lambda: return id(plant_t_case);
    update_interval: 2s
```

- [ ] **Step 2: Write the virtual top-level file**

Create `esphome/desiccant-dryer-virtual.yaml`:
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
  hardware: !include packages/hw-virtual.yaml
  display: !include packages/display.yaml
```

- [ ] **Step 3: Validate both builds, check the virtual one has no hardware sensor components, and compile it**

Run:
```bash
cd /Users/josh/GitHub/desiccant-dryer && esphome config esphome/desiccant-dryer-virtual.yaml > /tmp/dd-baseline/virt-config.txt 2>&1; tail -1 /tmp/dd-baseline/virt-config.txt && grep -cE "platform: (sht4x|dallas_temp)" /tmp/dd-baseline/virt-config.txt; grep -E "^  name: |^  friendly_name: " /tmp/dd-baseline/virt-config.txt | head -2 && esphome config esphome/desiccant-dryer.yaml > /dev/null 2>&1 && echo "prod still valid" && esphome compile esphome/desiccant-dryer-virtual.yaml > /tmp/dd-baseline/virt-compile.txt 2>&1; tail -2 /tmp/dd-baseline/virt-compile.txt; grep -E "^RAM:|^Flash:" /tmp/dd-baseline/virt-compile.txt
```
Expected: `INFO Configuration is valid!`, the count of sht4x/dallas platforms is `0`, name `desiccant-dryer-virtual` and friendly name `Desiccant Dryer (Virtual)`, `prod still valid`, then `INFO Successfully compiled program.`.

- [ ] **Step 4: Commit**

```bash
cd /Users/josh/GitHub/desiccant-dryer && git add esphome/packages/hw-virtual.yaml esphome/desiccant-dryer-virtual.yaml && git commit -m "Add virtual build with on-device plant model

desiccant-dryer-virtual.yaml runs the production logic, outputs and
display on a bare S2 Thing Plus. hw-virtual.yaml integrates a first-order
thermal model per pack from the real heater switch states and a
breakthrough RH curve from service time, in time scaled by Sim Speed.
Knobs cover ambient, heater max, time constant, breakthrough, rise rate,
a heater fault and manual pack temps.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 4: CI that compiles both variants

> Executed as written, then changed in Task 7: `esphome/build-action@v8.1.0` refuses ESPHome older than 2026.7.0, so the shipped workflow runs `ghcr.io/esphome/esphome:2026.1.4` with `docker run` instead. The step below is the original text.

**Files:**
- Create: `.github/workflows/build.yml`

**Interfaces:**
- Consumes: `esphome/secrets.ci.yaml` (Task 1), both top-level YAMLs.
- Produces: a required check named `compile production` and `compile virtual` on every PR.

- [ ] **Step 1: Write the workflow**

Create `.github/workflows/build.yml`:
```yaml
name: build

on:
  push:
    branches: [main]
  pull_request:

jobs:
  compile:
    name: compile ${{ matrix.variant }}
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        include:
          - variant: production
            yaml: esphome/desiccant-dryer.yaml
          - variant: virtual
            yaml: esphome/desiccant-dryer-virtual.yaml
    steps:
      - uses: actions/checkout@v7
      - name: Provide dummy secrets
        run: cp esphome/secrets.ci.yaml esphome/secrets.yaml
      - name: Compile ${{ matrix.variant }}
        uses: esphome/build-action@v8.1.0
        with:
          yaml-file: ${{ matrix.yaml }}
          version: 2026.1.4
```

- [ ] **Step 2: Sanity-check the workflow file parses and the dummy secrets validate from a clean copy**

Run:
```bash
cd /Users/josh/GitHub/desiccant-dryer && "$(dirname "$(readlink -f "$(which esphome)")")/python" -c "import yaml,sys; d=yaml.safe_load(open('.github/workflows/build.yml')); print(sorted(d['jobs']['compile']['strategy']['matrix']['include'][0].keys()))" && rm -rf /tmp/dd-ci && mkdir /tmp/dd-ci && cp -R esphome /tmp/dd-ci/ && rm -f /tmp/dd-ci/esphome/secrets.yaml && rm -rf /tmp/dd-ci/esphome/.esphome && cp /tmp/dd-ci/esphome/secrets.ci.yaml /tmp/dd-ci/esphome/secrets.yaml && (cd /tmp/dd-ci && esphome config esphome/desiccant-dryer.yaml 2>&1 | tail -1 && esphome config esphome/desiccant-dryer-virtual.yaml 2>&1 | tail -1)
```
Expected: `['variant', 'yaml']` and two lines of `INFO Configuration is valid!`. The real CI run is verified in Task 7 when the PR opens.

- [ ] **Step 3: Commit**

```bash
cd /Users/josh/GitHub/desiccant-dryer && git add .github/workflows/build.yml && git commit -m "Add CI that compiles the production and virtual builds

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 5: Documentation

**Files:**
- Modify: `docs/control-logic.md` (replace entire file), `README.md` (replace entire file), `CLAUDE.md` (three sections)
- Create: `docs/virtual-testing.md`

**Interfaces:**
- Consumes: entity names and knob defaults from Tasks 2 and 3. If any name in the docs does not match the YAML, the YAML wins and the doc is wrong.

- [ ] **Step 1: Rewrite docs/control-logic.md**

Overwrite `docs/control-logic.md` with:
```markdown
# Control logic

Runs every 5 s in the `interval:` lambda in `esphome/packages/base.yaml`.
Both builds share it unchanged; only the sensor sources differ. See
`docs/virtual-testing.md` for exercising it with no hardware attached.

## Roles

- **Active pack**: valve open, heater off. Air flows through it to the ozone
  generator.
- **Standby pack**: valve closed. Cycles through the states below.

`active_pack` (1 = A, 2 = B, 0 = none) and `standby_state` persist across
reboots so a power blip resumes mid-cycle. On first boot (no state) the
controller starts on pack A with B as WET standby.

## Time

The logic never reads a clock for durations. Each tick measures the real
seconds since the previous tick (clamped to 60 s so a stall cannot jump
anything), multiplies by the `time_scale` global, and adds the result to
three persisted counters:

| Counter | Meaning | Reset by |
|---|---|---|
| `service_elapsed_s` | Time the active pack has been in service | swap, first start, Dryer Enabled off |
| `heat_elapsed_s` | Time the standby heater has run this regen | WET to HEATING, swap, boot while HEATING |
| `hold_elapsed_s` | Time continuously at or above `regen_temp` | dropping below `regen_temp`, plus all of the above |

`time_scale` is 1.0 in production. The virtual build's "Sim Speed" sets it
so a full cycle runs in minutes. ESPHome writes changed globals to flash
about once a minute, so a power loss costs at most a minute of each counter.

## Standby state machine

| State | Enter when | Exit when |
|---|---|---|
| WET (0) | Just retired from service | outlet RH ≥ `arm_rh`, or service time ≥ `max_service_min − regen_max_min` → HEATING |
| HEATING (1) | — | Pack temp ≥ `regen_temp` continuously for `regen_hold_min` → COOLING. Or heater time ≥ `regen_max_min` → COOLING (warning logged). |
| COOLING (2) | — | Pack temp ≤ `cooldown_temp` → READY |
| READY (3) | — | outlet RH ≥ `swap_rh` or service time ≥ `max_service_min` → **swap** |

## Outputs

Outputs are a pure function of state, re-asserted at the end of every tick
by the `apply_outputs` script:

- Active pack: valve on, heater off.
- Standby pack: valve off. Heater on only while HEATING, with no fault, and
  with a valid pack temperature.

Because this runs every tick, a reboot re-opens the active valve and
re-lights a heater on the first tick, and a heater cannot stay on while its
probe reads NaN. The tick skips itself while the swap script is running so
it never interferes with the both-valves-closed window.

Swap (`do_swap` script): standby heater off → both valves closed → 500 ms →
standby valve open → roles exchange → the retired pack becomes WET and all
counters reset. `Force Swap` runs the same script from any state; it makes
no readiness check, so it can put a wet pack into service.

## Boot and disable

`on_boot` forces all five outputs off. If the restored state is HEATING, the
heater and hold counters reset and the start temperature is cleared, so the
regen restarts from scratch on the first tick. Resuming the old timers would
risk a spurious "not heating" fault after a long outage that let the pack
cool. The cost is at most one extra regen.

`Dryer Enabled` off: all outputs off, `active_pack` cleared, state WET, all
counters zero. A latched fault is left alone. Turning it on again starts on
pack A.

## Faults (latched; `Clear Fault` button resets)

`fault_code` persists across reboots together with its message.

| Code | Message | Trigger | Effect |
|---|---|---|---|
| 1 | Active pack overtemp | active pack > `overtemp` | heaters off |
| 2 | Standby pack overtemp | standby pack > `overtemp` | heaters off, standby → COOLING |
| 3 | Standby heater not heating | heater on 5 min with pack < start + 5 °C and still below `regen_temp` | heaters off, standby → COOLING |

While a fault is latched the state machine does nothing. Valves stay as they
were, so air keeps flowing through the active pack, and service time keeps
counting. After clearing, a pack left in COOLING becomes READY once it
cools; it is treated as regenerated because it reached at least regen
temperature. This is a judgment call and is easy to change in the tick.

## Tunables (HA `number` entities, persisted)

| Entity | Default | Meaning |
|---|---|---|
| `arm_rh` | 5 % | Outlet RH that starts standby regeneration |
| `swap_rh` | 10 % | Outlet RH that triggers the swap (if standby READY) |
| `regen_temp` | 90 °C | Pack temp considered "regenerating" |
| `regen_hold_min` | 15 min | Time above `regen_temp` to call regen complete |
| `regen_max_min` | 60 min | Heater safety timeout |
| `cooldown_temp` | 40 °C | Pack temp below which it may take air |
| `max_service_min` | 180 min | Fallback swap timer (sensor-drift guard) |
| `overtemp` | 120 °C | Hard heater cutoff |

All defaults are guesses. The old board used a fixed 20 min per pack, so
regeneration at this heater power is known to complete within 20 min.

## Observability

`Dryer Status` ("Air via A, B heating (waiting)"), `Standby State`,
`Service Time`, `Standby Heater Time`, `Regen Hold Time`, `Fault`,
`Fault Message`, and a `Restart` button. Transitions are logged under the
`cycle` tag at INFO, faults at ERROR.

## Humidity simulation (both builds)

`Simulate Humidity` switch + `Simulated RH` number. `Control Humidity`
(`ctrl_rh`) is what the logic and display read; it mirrors the outlet sensor
unless simulation is on. Simulation never persists across reboot and the
display tags the reading "SIM". Pack temperatures are not simulated here; on
the real unit heat the probes, on the virtual build use the plant knobs.

## Test sequence on the real unit

1. Dryer Enabled on, Simulate on at 2 % → expect "Air via A, B wet".
2. Slider to 6 % → heater B relay on ("B heating").
3. Warm probe B past `regen_temp` (lower it temporarily if needed), hold for
   `regen_hold_min` → heater off ("B cooling").
4. Let probe B fall below `cooldown_temp` → "B ready".
5. Slider to 12 % → valves swap, "Air via B, A wet".
6. Slider back to 2 %, repeat toward A.
```

- [ ] **Step 2: Write docs/virtual-testing.md**

Create `docs/virtual-testing.md`:
```markdown
# Virtual build: bench setup and test checklist

The virtual build runs the production logic, outputs, interlocks and display
on a bare SparkFun ESP32-S2 Thing Plus with nothing attached. Sensors come
from an on-device plant model driven by the real heater switch states, in
time scaled by "Sim Speed". It appears in Home Assistant as
**Desiccant Dryer (Virtual)**, a separate device from the real unit.

## One-time setup

1. Secrets (gitignored). From the repo root:

   ```bash
   cp esphome/secrets.yaml.example esphome/secrets.yaml
   ```

   Fill `wifi_ssid` and `wifi_password`. Generate the others:

   ```bash
   openssl rand -base64 32     # api_key
   openssl rand -hex 16        # ota_password
   openssl rand -hex 8         # ap_password
   ```

2. First flash over USB. Plug the board in, find the port, flash:

   ```bash
   ls /dev/cu.usbserial* /dev/cu.SLAB* 2>/dev/null
   esphome run esphome/desiccant-dryer-virtual.yaml
   ```

   `esphome run` lists the serial port to pick. The CP2102 auto-resets the
   board; if the upload does not start, hold BOOT, tap RESET, release BOOT,
   and retry. Leave the log streaming.

3. Home Assistant: Settings → Devices & services. The device is discovered
   by mDNS as `desiccant-dryer-virtual`; click Configure and paste the
   `api_key`. Later flashes go over the air:

   ```bash
   esphome run esphome/desiccant-dryer-virtual.yaml --device desiccant-dryer-virtual.local
   ```

4. Log tail without reflashing:

   ```bash
   esphome logs esphome/desiccant-dryer-virtual.yaml --device desiccant-dryer-virtual.local
   ```

## Plant knobs (Configuration section of the HA device page)

All persist across reboots. Defaults are arbitrary and chosen so the happy
path completes on its own.

| Entity | Default | Purpose |
|---|---|---|
| Sim Speed | 1x | Time multiplier for the plant and the control counters. 60x makes one control tick worth 5 sim-minutes |
| Sim Ambient Temp | 25 °C | Where packs cool to; raise above 35 °C to see the fan |
| Sim Heater Max Temp | 110 °C | Where a heated pack settles; set 130 °C to trigger overtemp |
| Sim Thermal Time Constant | 5 min | Heating and cooling pace |
| Sim Breakthrough Time | 60 min | Service minutes before outlet RH starts rising |
| Sim RH Rise Rate | 0.1 %/min | Set about 1 to make RH outrun regen and see "(waiting)" |
| Sim Heater Fault | off | Heater on produces no heat; triggers "not heating" |
| Sim Manual Temps | off | Pin both pack temps to Sim Pack A/B Temp |
| Sim Pack A Temp, Sim Pack B Temp | 25 °C | Used while Sim Manual Temps is on |

With the defaults: RH reaches 5 % at 100 min of service and 10 % at 150 min.
Heating to 90 °C takes about 7 min, the hold 15 min, cooling to 40 °C about
9 min, so standby is READY around 131 min and the swap fires at 150 min.
At 60x that is 2.5 real minutes per half cycle.

## Checklist

Watch `Dryer Status`, `Standby State`, the five output switches, the
sensors, and the log. "Outputs" below lists what must be on; everything
else must be off. Reset between scenarios by pressing `Dryer Enabled` off
then on, and returning any knob you changed.

| # | Scenario | Action | Expected |
|---|---|---|---|
| 1 | Fresh boot | Flash, wait 10 s | Status "Air via A, B wet". Outputs: Valve A. Log "Starting on pack A". No display allocation error in the boot log |
| 2 | Hands-free cycle | Sim Speed 60. Wait | RH climbs after 60 sim-min. At 5 %: Heater B on, status "B heating", Standby Heater Time and Pack B Temperature climb. Regen Hold Time climbs once B ≥ 90 °C. After 15 sim-min hold: heater off, "B cooling". At ≤ 40 °C: "B ready". At 10 % RH: log "Swapping air to pack B", Valve B on, Valve A off, status "Air via B, A wet", RH drops to 1 %, Service Time restarts from 0 |
| 3 | Second half | Keep waiting | Same sequence mirrored: Heater A on, then swap back to A |
| 4 | Waiting state | Sim RH Rise Rate 1, reset | RH passes 10 % while B is still heating. Status ends "(waiting)". Swap happens the tick after "B ready" |
| 5 | Force Swap | Press during "B heating" | Heater B off first, valves swap, status "Air via B, A wet". No fault |
| 6 | Standby overtemp | Sim Heater Max 130, reset, wait for heating | Fault on, Fault Message "Standby pack overtemp", both heaters off, Valve A still on, Standby State "cooling", Service Time keeps counting. Press Clear Fault: pack cools, "ready", cycle continues |
| 7 | Not heating | Sim Heater Fault on, reset, wait for arm | 5 sim-min after Heater B turns on: Fault "Standby heater not heating", heater off, state "cooling". Clear Fault → "ready" |
| 8 | Active overtemp | Sim Manual Temps on, Sim Pack A Temp 125 | Fault "Active pack overtemp" within one tick, heaters off, Valve A still on. Set 25, Clear Fault → continues |
| 9 | Disable / enable | Dryer Enabled off, then on | Off: all outputs off, status "Disabled". On: within 5 s "Air via A, B wet", Valve A on |
| 10 | Reboot mid-service | At ~30 sim-min of service press Restart | Same active pack after boot, its valve on within one tick, Service Time within a minute of where it was, standby "wet" |
| 11 | Reboot mid-HEATING | Press Restart during "B heating" | After boot: still "B heating", Heater B on within one tick, Standby Heater Time and Regen Hold Time restart from 0, Pack B Temperature continues from where it was (plant state persisted) |
| 12 | Base humidity override | Simulate Humidity on, Simulated RH 12 | Control Humidity reads 12. Swap as soon as standby is ready. Press Restart: Simulate Humidity is off again |
| 13 | Fan thermostat | Sim Ambient Temp 40 | Case Temperature rises past 36.5 °C, Case Fan on. Back to 25: fan off after the 60 s minimum run time |
| 14 | Sim speed mid-cycle | Change Sim Speed between 1 and 60 during heating | Counters and temperatures stay continuous; nothing resets |

Record anything unexpected with the log excerpt and the knob values.
```

- [ ] **Step 3: Rewrite README.md**

Overwrite `README.md` with:
```markdown
# desiccant-dryer

ESPHome firmware for an ESP32-S2 replacement of the Azco VMD-08 desiccant
air dryer control board. Swaps packs on measured humidity and pack
temperature instead of a fixed timer. See `CLAUDE.md` for decisions,
`docs/hardware.md` for wiring and BOM, `docs/control-logic.md` for the
state machine, `docs/virtual-testing.md` for testing without hardware.

Two builds share `esphome/packages/base.yaml`:

| Build | File | Sensors |
|---|---|---|
| Production | `esphome/desiccant-dryer.yaml` | SHT45 + 3× DS18B20 (`packages/hw-real.yaml`) |
| Virtual | `esphome/desiccant-dryer-virtual.yaml` | On-device plant model (`packages/hw-virtual.yaml`) |

```
cp esphome/secrets.yaml.example esphome/secrets.yaml   # fill in
esphome run esphome/desiccant-dryer-virtual.yaml       # bare board
esphome run esphome/desiccant-dryer.yaml               # real hardware
```

CI compiles both on every pull request.
```

- [ ] **Step 4: Update CLAUDE.md**

Apply these three edits to `CLAUDE.md`.

(a) Replace the "## Pin map" section heading and its first sentence:
```
## Pin map (esphome/desiccant-dryer.yaml is the source of truth)
```
with:
```
## Layout and pin map

Two builds share one logic file via ESPHome packages: `esphome/packages/base.yaml`
(platform, globals, tunables, GPIO outputs, state machine, derived entities),
`packages/hw-real.yaml` (buses and real sensors; the hardware side edits only
this), `packages/hw-virtual.yaml` (plant model and sim knobs), and
`packages/display.yaml`. `desiccant-dryer.yaml` and `desiccant-dryer-virtual.yaml`
are ten-line selectors. Base must only reference the five sensor ids
`air_rh`, `air_temp`, `pack_a_temp`, `pack_b_temp`, `case_temp` from the
hardware package. `hw-real.yaml` is the pin-map source of truth for sensors;
`base.yaml` for outputs.
```

(b) Replace the "## Control logic" paragraph that begins `Standby pack moves WET → HEATING → COOLING → READY.` and ends `...latch a fault that stops everything until cleared.` with:
```
Standby pack moves WET → HEATING → COOLING → READY. Heater starts when outlet
RH crosses `arm_rh`; regen is judged complete by pack temperature held above
`regen_temp` for `regen_hold_min`; the pack is READY once it cools below
`cooldown_temp`; swap happens when RH crosses `swap_rh` (or `max_service_min`).
All thresholds are HA `number` entities. Durations are persisted elapsed
counters scaled by a `time_scale` global (1.0 in production); outputs are
re-asserted from state every tick by the `apply_outputs` script. Overtemp and
"heater on but no temperature rise" latch a fault code that stops everything
until cleared.
```

(c) In "## Invariants", append these bullets after the `sim_enabled` bullet:
```
- `time_scale` is only ever written by `packages/hw-virtual.yaml`. Production
  runs at 1.0.
- Virtual plant knobs (`Sim *`) persist across reboot by design; the base
  `Simulate Humidity` override does not. Don't merge the two mechanisms.
- Outputs are applied from state by `apply_outputs` every tick. Never toggle
  a heater or valve from a state transition alone; change the state and let
  the apply step do it.
```

(d) In "## Working conventions", replace the first bullet (`Flash with ...`) with:
```
- Flash with `esphome run esphome/desiccant-dryer.yaml` (real hardware) or
  `esphome run esphome/desiccant-dryer-virtual.yaml` (bare board). Copy
  `secrets.yaml.example` to `secrets.yaml` first; for a compile-only check,
  `cp esphome/secrets.ci.yaml esphome/secrets.yaml` works.
- To prove a refactor changed nothing, dump `esphome config` before and
  after and diff through `scripts/normalize-config.py`.
```

Run to apply (a) to (d) with a script rather than by hand:
```bash
cd /Users/josh/GitHub/desiccant-dryer && python3 - <<'PY'
import pathlib, re
p = pathlib.Path("CLAUDE.md"); s = p.read_text()

a_old = "## Pin map (esphome/desiccant-dryer.yaml is the source of truth)\n"
a_new = """## Layout and pin map

Two builds share one logic file via ESPHome packages: `esphome/packages/base.yaml`
(platform, globals, tunables, GPIO outputs, state machine, derived entities),
`packages/hw-real.yaml` (buses and real sensors; the hardware side edits only
this), `packages/hw-virtual.yaml` (plant model and sim knobs), and
`packages/display.yaml`. `desiccant-dryer.yaml` and `desiccant-dryer-virtual.yaml`
are ten-line selectors. Base must only reference the five sensor ids
`air_rh`, `air_temp`, `pack_a_temp`, `pack_b_temp`, `case_temp` from the
hardware package. `hw-real.yaml` is the pin-map source of truth for sensors;
`base.yaml` for outputs.

"""
assert a_old in s; s = s.replace(a_old, a_new)

b_old_start = "Standby pack moves WET → HEATING → COOLING → READY."
b_old_end = "latch a fault that stops everything until cleared.\n"
i = s.index(b_old_start); j = s.index(b_old_end, i) + len(b_old_end)
b_new = """Standby pack moves WET → HEATING → COOLING → READY. Heater starts when outlet
RH crosses `arm_rh`; regen is judged complete by pack temperature held above
`regen_temp` for `regen_hold_min`; the pack is READY once it cools below
`cooldown_temp`; swap happens when RH crosses `swap_rh` (or `max_service_min`).
All thresholds are HA `number` entities. Durations are persisted elapsed
counters scaled by a `time_scale` global (1.0 in production); outputs are
re-asserted from state every tick by the `apply_outputs` script. Overtemp and
"heater on but no temperature rise" latch a fault code that stops everything
until cleared.
"""
s = s[:i] + b_new + s[j:]

c_anchor = "  and the display must show \"SIM\" whenever it is active.\n"
c_new = c_anchor + """- `time_scale` is only ever written by `packages/hw-virtual.yaml`. Production
  runs at 1.0.
- Virtual plant knobs (`Sim *`) persist across reboot by design; the base
  `Simulate Humidity` override does not. Don't merge the two mechanisms.
- Outputs are applied from state by `apply_outputs` every tick. Never toggle
  a heater or valve from a state transition alone; change the state and let
  the apply step do it.
"""
assert c_anchor in s; s = s.replace(c_anchor, c_new)

d_old = """- Flash with `esphome run esphome/desiccant-dryer.yaml` (copy
  `secrets.yaml.example` to `secrets.yaml` first).
"""
d_new = """- Flash with `esphome run esphome/desiccant-dryer.yaml` (real hardware) or
  `esphome run esphome/desiccant-dryer-virtual.yaml` (bare board). Copy
  `secrets.yaml.example` to `secrets.yaml` first; for a compile-only check,
  `cp esphome/secrets.ci.yaml esphome/secrets.yaml` works.
- To prove a refactor changed nothing, dump `esphome config` before and
  after and diff through `scripts/normalize-config.py`.
"""
assert d_old in s; s = s.replace(d_old, d_new)
p.write_text(s); print("CLAUDE.md updated")
PY
grep -n "Layout and pin map\|time_scale\|normalize-config" CLAUDE.md
```
Expected: `CLAUDE.md updated` and three matching lines.

- [ ] **Step 5: Cross-check every entity name in the docs against the YAML**

Run:
```bash
cd /Users/josh/GitHub/desiccant-dryer && for n in "Sim Speed" "Sim Ambient Temp" "Sim Heater Max Temp" "Sim Thermal Time Constant" "Sim Breakthrough Time" "Sim RH Rise Rate" "Sim Heater Fault" "Sim Manual Temps" "Sim Pack A Temp" "Sim Pack B Temp" "Standby Heater Time" "Regen Hold Time" "Standby State" "Fault Message" "Dryer Status" "Service Time" "Control Humidity" "Simulate Humidity" "Simulated RH" "Clear Fault" "Force Swap" "Restart" "Dryer Enabled" "Case Fan" "Pack A Temperature" "Pack B Temperature" "Case Temperature"; do grep -q "name: \"$n\"" esphome/packages/*.yaml || echo "MISSING IN YAML: $n"; done; echo "name check done"
```
Expected: only `name check done`.

- [ ] **Step 6: Commit**

```bash
cd /Users/josh/GitHub/desiccant-dryer && git add docs/control-logic.md docs/virtual-testing.md README.md CLAUDE.md && git commit -m "Document the package layout, elapsed-time logic and virtual test bench

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 6: Bench bring-up on the S2 Thing Plus and Home Assistant

This task needs the user for WiFi credentials, plugging in the board, and the HA pairing dialog. Do every other step yourself.

**Files:**
- Create (gitignored): `esphome/secrets.yaml`

**Interfaces:**
- Consumes: the virtual build from Task 3, the checklist from Task 5.
- Produces: a flashed, HA-paired virtual device and a filled-in checklist result reported to the user.

- [ ] **Step 1: Generate secrets, leaving WiFi for the user**

Run:
```bash
cd /Users/josh/GitHub/desiccant-dryer && [ -f esphome/secrets.yaml ] && grep -q ci-placeholder esphome/secrets.yaml && rm esphome/secrets.yaml; [ -f esphome/secrets.yaml ] && echo "real secrets already present, leaving them" || { printf 'wifi_ssid: "FILL-ME-IN"\nwifi_password: "FILL-ME-IN"\nap_password: "%s"\napi_key: "%s"\nota_password: "%s"\n' "$(openssl rand -hex 8)" "$(openssl rand -base64 32)" "$(openssl rand -hex 16)" > esphome/secrets.yaml && echo "secrets written"; }; grep -c FILL-ME-IN esphome/secrets.yaml
```
Expected: `secrets written` and `2`. Then tell the user: "Please fill `wifi_ssid` and `wifi_password` in `esphome/secrets.yaml`, plug the S2 Thing Plus into USB, and say when ready." Stop until they confirm.

- [ ] **Step 2: Flash over USB and watch the boot log**

Run (the port prompt is interactive; pass `--device` once known):
```bash
cd /Users/josh/GitHub/desiccant-dryer && ls /dev/cu.usbserial* /dev/cu.SLAB* 2>/dev/null; grep -c FILL-ME-IN esphome/secrets.yaml
```
Expected: one serial device and `0`. Then:
```bash
cd /Users/josh/GitHub/desiccant-dryer && esphome run esphome/desiccant-dryer-virtual.yaml --device "$(ls /dev/cu.usbserial* /dev/cu.SLAB* 2>/dev/null | head -1)" 2>&1 | tee /tmp/dd-baseline/flash.log
```
Expected in the log within 30 s of boot: WiFi connected with an IP, `[cycle] Starting on pack A`, no line containing `Could not allocate` or `display` errors. If the upload does not start, ask the user to hold BOOT, tap RESET, release BOOT, and rerun.

- [ ] **Step 3: Pair with Home Assistant**

Tell the user: "In HA go to Settings → Devices & services. `desiccant-dryer-virtual` should be listed as discovered. Click Configure and paste this API key: `<api_key from esphome/secrets.yaml>`." Wait for confirmation. Then verify from the device side:
```bash
cd /Users/josh/GitHub/desiccant-dryer && esphome logs esphome/desiccant-dryer-virtual.yaml --device desiccant-dryer-virtual.local 2>&1 | head -40
```
Expected: `[api]` lines showing a client connected from the HA host's IP.

- [ ] **Step 4: Run the checklist**

Walk `docs/virtual-testing.md` scenarios 1 to 14 in order, driving knobs through HA (ask the user to operate HA if you cannot, and read results from `esphome logs` and the web server at `http://desiccant-dryer-virtual.local/`). For each scenario record pass or fail with the observed status text and any log line. Scenario 2 at 60x takes about 3 real minutes; scenarios 10 and 11 need the Restart button.

- [ ] **Step 5: Fix anything that failed**

Any failure is a logic bug or a doc error. Fix it in `base.yaml` or `hw-virtual.yaml`, reflash OTA with `esphome run esphome/desiccant-dryer-virtual.yaml --device desiccant-dryer-virtual.local`, rerun the failed scenario, and commit the fix with a message that names the scenario number. Do not weaken a check to make a scenario pass.

- [ ] **Step 6: Report**

Send the user a pass/fail table for the 14 scenarios plus the RAM/Flash figures and whether the display buffer allocated. Nothing to commit.

---

### Task 7: Pull request per the global workflow

**Files:** none.

- [ ] **Step 1: Rebase on a fresh origin/main and push**

```bash
cd /Users/josh/GitHub/desiccant-dryer && git fetch origin && git rebase origin/main && git push -u origin virtual-build --force-with-lease
```
Expected: rebase reports up to date or replays cleanly; push succeeds.

- [ ] **Step 2: Open the PR**

```bash
cd /Users/josh/GitHub/desiccant-dryer && gh pr create --base main --head virtual-build --title "Virtual build, elapsed-time refactor and CI" --body "$(cat <<'EOF'
## Summary
- Split the config into `packages/base.yaml` (shared logic), `hw-real.yaml`, `hw-virtual.yaml`, `display.yaml`; two ten-line top-level selectors.
- Replace `millis()` timestamps with persisted, `time_scale`-scaled elapsed counters and re-assert outputs from state every tick. Fixes: active valve closed after reboot; mid-HEATING heater never re-lit; service time reset on reboot; fault message lost on reboot.
- Add `desiccant-dryer-virtual.yaml`: production logic on a bare S2 Thing Plus with an on-device plant model and time acceleration, for end-to-end testing through Home Assistant.
- CI compiles both builds.
- Docs: control logic updated, bench checklist in `docs/virtual-testing.md`.

Design: `docs/superpowers/specs/2026-09-14-virtual-build-design.md`.

## Test plan
- [x] `esphome config` and `esphome compile` pass for both builds locally
- [ ] CI green
- [ ] Bench checklist in `docs/virtual-testing.md` run on the S2 Thing Plus (results in the PR comments)

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 3: Watch CI and fix failures**

Bind the PR with the desktop app's PR tools and read the check status there; otherwise:
```bash
cd /Users/josh/GitHub/desiccant-dryer && gh pr checks --watch
```
If a check fails, read the failing job log with `gh run view <id> --log-failed`, fix the root cause, commit, push, and watch again until green. Surface each failure to the user with the log excerpt.

- [ ] **Step 4: Wait for the Copilot review and address it**

Poll every couple of minutes until a review by Copilot appears:
```bash
cd /Users/josh/GitHub/desiccant-dryer && gh pr view --json reviews,comments --jq '.reviews[] | select(.author.login | test("copilot"; "i")) | .state' ; gh api repos/jrytio/desiccant-dryer/pulls/$(gh pr view --json number --jq .number)/comments --jq '.[] | select(.user.login | test("copilot"; "i")) | "\(.path):\(.line) \(.body)"'
```
Address every comment: fix it and push, or reply on the thread explaining why not. Report the list of comments and what was done for each to the user. The PR task is not done until the Copilot review has landed and been handled.

---

## Self-review notes

- Spec coverage: layout (T1, T3), globals and tick (T2), apply_outputs and swap (T2), boot and disable (T2), fault code and message (T2), diagnostics (T2), hw-real move (T1), display fault line (T2), plant model, sensors and knobs (T3), HA workflow (T5 docs, T6 execution), CI (T4), verification checklist (T5, T6), edge cases (T2 code comments), follow-ups (spec only, intentionally no task).
- Names used across tasks match: `apply_outputs`, `do_swap`, `fault_message`, `fault_code`, `time_scale`, `service_elapsed_s`, `heat_elapsed_s`, `hold_elapsed_s`, `heat_start_temp`, `last_tick_ms`, `plant_*`, `sim_*`.
- Line ranges in Task 1 were verified against commit `bdc149c` and the normalised diff was confirmed empty before this plan was written.
