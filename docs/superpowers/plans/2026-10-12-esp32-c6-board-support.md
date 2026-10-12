# ESP32-C6 Thing Plus Board Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship one release that carries a firmware image for the SparkFun ESP32-S2 Thing Plus and one for the SparkFun Thing Plus ESP32-C6, so either board can sit in the same main-board socket and update itself from the same manifest.

**Architecture:** Everything that depends on the chip moves into one package per board (`packages/board-s2.yaml`, `packages/board-c6.yaml`): the `esp32:` block, the logger port and a table of `pin_*` substitutions. The shared controller, sensor and display packages take their pins from those substitutions and hold no GPIO numbers. The release workflow compiles one production selector per chip and `scripts/make-manifest.sh` writes both into one esp-web-tools manifest.

**Tech Stack:** ESPHome on ESP-IDF (CI and release pin 2026.9.0; the local Homebrew CLI is 2026.8.2), GitHub Actions, bash, Python 3 for the lint runner.

**Spec:** `docs/superpowers/specs/2026-10-12-esp32-c6-board-support-design.md`. Read it before starting; this plan argues from it.

## Global Constraints

- The ESP32-S2 builds must not change. For `desiccant-dryer`, `-virtual`, `-hw-test`, `-host` and `-scenarios`, the `esphome config` dump passed through `scripts/normalize-config.py` is byte-identical before and after Task 2, and differs only in the two `1.2.4` → `1.3.0` lines after Task 5.
- The shared packages `base.yaml`, `hw-real.yaml`, `display-st7789.yaml` and `platform-esp32.yaml` contain no GPIO number and no pin default. A selector with no board package must fail validation.
- C6 pin map, by header position: heater A GPIO18, heater B GPIO22, valve A GPIO11, valve B GPIO10, fan GPIO8, I2C SDA GPIO6 / SCL GPIO7, 1-wire GPIO21, SPI clock GPIO19 / data GPIO20, display CS GPIO5 / DC GPIO4 / RST GPIO3 / backlight GPIO0. S2 pin map: unchanged (13, 12, 11, 10, 8; 1/2; 37; 36/35; 5/7/9/17).
- Board IDs: `sparkfun_esp32s2_thing_plus` / `variant: esp32s2`; `sparkfun_esp32c6_thing_plus` / `variant: esp32c6`. Logger: `UART0` on the S2, `USB_SERIAL_JTAG` on the C6.
- The C6 production selector keeps the device name `desiccant-dryer` and builds in `build/desiccant-dryer-c6`. The C6 production build keeps `display_buffer_size: 50%` and the 10 s redraw.
- Manifest: `chipFamily` `ESP32-S2` and `ESP32-C6`; files `desiccant-dryer-<ver>-esp32s2.{ota,factory}.bin` and `desiccant-dryer-<ver>-esp32c6.{ota,factory}.bin`. Version `1.3.0`.
- CI matrix variant names for the C6 are `c6-production` and `c6-hw-test` (never `production-c6`: the existing `build-…-production-` cache restore prefix would match it).
- Nothing about the C6 has been run on hardware. Do not write "tested", "verified" or a measured number for the C6 anywhere; the bench steps in `docs/hardware-bringup.md` section 8 are how that gets done.
- No `Sim *` entity, secret, WiFi, OTA, SPI or LEDC key may be added to `base.yaml` or `display-draw.yaml`. No device IP addresses in tracked files. Do not title anything "VMD-08" or "Azco".
- `esphome/secrets.yaml` may be a symlink to real developer secrets in other checkouts. Never write to it; only create it when it does not exist at all.
- Write code and comments in the style of the files around them: these files explain *why* in full sentences.

## Review Focus

Conditions the spec implies that are most likely to hurt someone, and the test that pins each:

1. **A build directory handed to the wrong chip when packaging** (arguments swapped, or both production compiles sharing one directory). Expected: the release stops; no S2 unit is ever offered a C6 image. Pinned by Task 4: `make-manifest.sh` reads each image's chip id and `tests/make_manifest_test.sh` has "swapped build dirs refused". Task 5 runs the same check on real images in CI.
2. **A wrong GPIO in a board file**, most plausibly a heater and a valve transposed on the C6, where nothing is muscle memory. Expected: CI fails before anyone flashes. Pinned by Tasks 1 and 3: lint cases T-J12 (S2) and T-J12C (C6), each shown failing once on purpose.
3. **A selector that includes the shared packages but no board package** (a new test build copied from an old one). Expected: validation fails naming the missing `pin_*`, never a silent default. Pinned by Task 2, Step 6.
4. **An S2 unit already in the field reading the new two-build manifest**, with its own build listed second or first. Expected: it takes the `ESP32-S2` entry either way. Pinned by Task 4 ("chips in the other order" plus the md5 and path assertions) and by bench step 8.7 in Task 8, the only real proof.
5. **A C6 board fitted as delivered**: ALRT and SD_DET uncut, or a card in the µSD slot. Expected: a person is stopped by a checklist item with a meter reading, since firmware cannot detect it. Pinned by Task 9: inspection checklist items D-18 and G-17.

Also met while prototyping, and already handled in the files below: the setup access point's SSID is the friendly name plus " Setup" and may not exceed 32 characters, which is why the C6 bench build is "Desiccant Dryer (C6 Test)".

## Before you start

Run everything from the repository root. Three commands recur; they are written out in full in each step because shell functions do not survive between steps.

- **Config or lint with ESPHome 2026.9.0** (required for the two production selectors, whose `min_version` the Homebrew CLI does not meet):

  ```bash
  docker run --rm -v "$PWD:/config" -w /config --entrypoint esphome ghcr.io/esphome/esphome:2026.9.0 config esphome/desiccant-dryer.yaml
  docker run --rm -v "$PWD:/config" -w /config --entrypoint bash ghcr.io/esphome/esphome:2026.9.0 -c 'python3 tests/lint_config.py'
  ```

  `--entrypoint esphome` matters: the image's default entrypoint prints two lines to stdout that corrupt a config dump.
- **Config with the local CLI** for the bench and host selectors: `esphome config esphome/<selector>.yaml`. The host and scenarios selectors need SDL2 (`brew install sdl2`), which Docker would have to install on every run.
- **ESPHome's own Python**, which has PyYAML: `"$(dirname "$(readlink -f "$(which esphome)")")/python"`.

Scratch output goes under `.ci-cache/`, which is gitignored. Do not write scratch files anywhere else in the repository; in particular `scripts/failure-modes-report.py` writes `failure-modes.html` into the current directory unless given a path.

## File Structure

| File | Responsibility after this plan |
|---|---|
| `esphome/packages/board-s2.yaml` (new) | ESP32-S2 Thing Plus: `esp32:` block, logger port, pin table |
| `esphome/packages/board-c6.yaml` (new) | Thing Plus ESP32-C6: the same three things |
| `esphome/packages/platform-esp32.yaml` | Chip-independent: WiFi, setup AP, captive portal, web server |
| `esphome/packages/base.yaml`, `hw-real.yaml`, `display-st7789.yaml` | Unchanged roles; pins come from `${pin_*}` |
| `esphome/packages/platform-host.yaml` | Also supplies placeholder output pins for the host build |
| `esphome/desiccant-dryer.yaml`, `-virtual.yaml`, `-hw-test.yaml` | Each adds the S2 board package |
| `esphome/desiccant-dryer-c6.yaml` (new) | C6 production selector |
| `esphome/desiccant-dryer-hw-test-c6.yaml` (new) | C6 bench selector |
| `tests/lint_config.py` | Assertion keys may be dotted (`pin.number`) |
| `tests/cases/T-J12.yaml`, `T-J12C.yaml` (new) | The five output pins of each board, asserted in CI |
| `scripts/make-manifest.sh` | One manifest, one build per chip, chip id checked |
| `tests/make_manifest_test.sh` (new) | Tests that script with stand-in images |
| `.github/workflows/build.yml`, `release.yml` | Compile and package both chips |
| `docs/…`, `README.md`, `CLAUDE.md` | Two boards instead of one |

---

### Task 1: Pin the S2 output pins in CI before touching them

The refactor in Task 2 moves every GPIO number. This task first adds a CI check that the five output pins are what they are today, so Task 2 has something to break.

**Files:**
- Create: `tests/cases/T-J12.yaml`
- Modify: `tests/lint_config.py`, `docs/verification-plan.md`

**Interfaces:**
- Consumes: nothing.
- Produces: lint assertions accept a dotted key, `switch <id> has pin.number <n>`. Case `T-J12` (covers catalogue row `J-12`, which Task 9 adds).

- [ ] **Step 1: Make sure the tools are there**

```bash
[ -e esphome/secrets.yaml ] || [ -L esphome/secrets.yaml ] || cp esphome/secrets.ci.yaml esphome/secrets.yaml
docker pull -q ghcr.io/esphome/esphome:2026.9.0
esphome version
```

Expected: the image digest line, then `Version: 2026.8.2` or newer. The first line creates the dummy secrets only when no file and no symlink is there.

- [ ] **Step 2: Write the failing case**

Create `tests/cases/T-J12.yaml`:

```yaml
id: T-J12
covers: [J-12]
type: lint
status: green          # the S2 pin table: packages/board-s2.yaml
harness: ci-lint
selectors: [esphome/desiccant-dryer.yaml, esphome/desiccant-dryer-hw-test.yaml]
assert:
  - switch heater_a has pin.number 13 and switch heater_b has pin.number 12
  - switch valve_a has pin.number 11 and switch valve_b has pin.number 10
  - switch case_fan has pin.number 8
```

- [ ] **Step 3: Run it and watch it fail**

```bash
docker run --rm -v "$PWD:/config" -w /config --entrypoint bash ghcr.io/esphome/esphome:2026.9.0 -c 'python3 tests/lint_config.py T-J12'
```

Expected: exit 1 with `lint_config.py cannot parse the assertion: 'switch heater_a has pin.number 13'`. The runner's keys are `\w+` today, and a `pin:` is a mapping in the dump.

- [ ] **Step 4: Teach the runner dotted keys**

Apply to `tests/lint_config.py`:

```diff
--- a/tests/lint_config.py
+++ b/tests/lint_config.py
@@ -47,8 +47,9 @@
 # Three shapes cover every lint case in the plan. Values are matched against
 # the entity's own dict first, so `initial_value <= max_value` compares two
-# keys of the same entity; anything else is a literal.
+# keys of the same entity; anything else is a literal. A dotted key walks
+# into nested mappings: `pin.number` is the GPIO of a switch's `pin:`.
 
-EVERY = re.compile(r"^every (\w+) in \[([^\]]+)\] has (\w+) (<=|>=|<|>|is|) ?(.+)$")
-ONE = re.compile(r"^(\w+) (\w+) has (\w+) (<=|>=|<|>|is|) ?(.+)$")
+EVERY = re.compile(r"^every (\w+) in \[([^\]]+)\] has ([\w.]+) (<=|>=|<|>|is|) ?(.+)$")
+ONE = re.compile(r"^(\w+) (\w+) has ([\w.]+) (<=|>=|<|>|is|) ?(.+)$")
 INCLUDES = re.compile(r"^(\w+)\.(\w+) includes (\w+)$")
 
@@ -71,7 +72,9 @@
 
 def compare(ent, key, op, want, where):
-    if key not in ent:
-        raise AssertionError(f"{where}: no {key}")
-    got = ent[key]
+    got = ent
+    for part in key.split("."):
+        if not isinstance(got, dict) or part not in got:
+            raise AssertionError(f"{where}: no {key}")
+        got = got[part]
     want = ent[want] if want in ent else want
     if isinstance(got, bool):
```

- [ ] **Step 5: Run every lint case**

```bash
docker run --rm -v "$PWD:/config" -w /config --entrypoint bash ghcr.io/esphome/esphome:2026.9.0 -c 'python3 tests/lint_config.py'
```

Expected, exit 0:

```text
T-B20    green  pass ok
T-F15    green  pass ok
T-J04    green  pass ok
T-J12    green  pass ok
T-K01L   green  pass ok
```

- [ ] **Step 6: Prove the case can fail**

```bash
perl -pi -e 's/^    pin: GPIO13$/    pin: GPIO14/' esphome/packages/base.yaml
docker run --rm -v "$PWD:/config" -w /config --entrypoint bash ghcr.io/esphome/esphome:2026.9.0 -c 'python3 tests/lint_config.py T-J12'
git checkout esphome/packages/base.yaml
```

Expected from the middle command, exit 1: `T-J12    green  FAIL UNEXPECTED` followed by two lines ending `switch heater_a: pin.number is 14, expected == 13.0`. `git status --short esphome/packages/base.yaml` must print nothing afterwards.

- [ ] **Step 7: Document the new key shape**

In `docs/verification-plan.md`, replace

```text
`<op>` is `<=`, `>=`, `<`, `>` or omitted for equality. A `<value>` that
names another key of the same entity compares the two (`initial_value <=
max_value`).
```

with

```text
`<op>` is `<=`, `>=`, `<`, `>` or omitted for equality. A `<value>` that
names another key of the same entity compares the two (`initial_value <=
max_value`). A dotted `<key>` walks into a nested mapping: `switch heater_a
has pin.number 13` reads the GPIO of that switch's `pin:`.
```

- [ ] **Step 8: Commit**

```bash
git add tests/cases/T-J12.yaml tests/lint_config.py docs/verification-plan.md
git commit -m "Assert the five output pins in the config lint"
```

---

### Task 2: Move the S2's chip-specific config into a board package

**Files:**
- Create: `esphome/packages/board-s2.yaml`
- Modify: `esphome/packages/platform-esp32.yaml`, `esphome/packages/base.yaml`, `esphome/packages/hw-real.yaml`, `esphome/packages/display-st7789.yaml`, `esphome/packages/platform-host.yaml`, `esphome/desiccant-dryer.yaml`, `esphome/desiccant-dryer-virtual.yaml`, `esphome/desiccant-dryer-hw-test.yaml`

**Interfaces:**
- Consumes: case `T-J12` from Task 1.
- Produces: fourteen substitutions every board package must define: `pin_heater_a`, `pin_heater_b`, `pin_valve_a`, `pin_valve_b`, `pin_fan`, `pin_i2c_sda`, `pin_i2c_scl`, `pin_onewire`, `pin_spi_clk`, `pin_spi_mosi`, `pin_lcd_cs`, `pin_lcd_dc`, `pin_lcd_rst`, `pin_lcd_bl`. A value is a GPIO name (`GPIO13`) or a pin mapping (`number:` plus options). Each board package also owns the `esp32:` block and `logger: hardware_uart`.

- [ ] **Step 1: Capture the configs as they are now**

Do this before any edit in this task.

```bash
mkdir -p .ci-cache/dumps/before
for s in desiccant-dryer-virtual desiccant-dryer-hw-test desiccant-dryer-host desiccant-dryer-scenarios; do
  esphome config esphome/$s.yaml > .ci-cache/dumps/before/$s.txt 2>/dev/null || echo "FAILED $s"
done
docker run --rm -v "$PWD:/config" -w /config --entrypoint esphome ghcr.io/esphome/esphome:2026.9.0 \
  config esphome/desiccant-dryer.yaml > .ci-cache/dumps/before/desiccant-dryer.txt 2>/dev/null || echo "FAILED desiccant-dryer"
wc -l .ci-cache/dumps/before/*.txt
```

Expected: no `FAILED` line, and five files of about 1537, 1405, 481, 1756 and 1474 lines (host, hw-test, scenarios, virtual, production). Each must start with `substitutions:`; check with `head -1 .ci-cache/dumps/before/*.txt`.

- [ ] **Step 2: Create the S2 board package**

Create `esphome/packages/board-s2.yaml`. The `esp32:` and `logger:` blocks are the ones in `platform-esp32.yaml` today, moved with their comments:

```yaml
# SparkFun ESP32-S2 Thing Plus (WRL-17743): everything that depends on the
# chip. The board and framework block, the port the log goes out on, and the
# GPIO behind each header position. packages/board-c6.yaml is the same file
# for the ESP32-C6 Thing Plus. The main board is wired by header position
# and takes either board, so the two tables read row for row.
# Source: SparkFun's schematic, see docs/pinout-verification.md.
#
#   Position     Function             GPIO
#   16-pin  5    display backlight     17
#   16-pin  8    display RST            9
#   16-pin  9    display DC             7
#   16-pin 10    display CS             5
#   16-pin 11    SPI clock             36
#   16-pin 12    SPI data (MOSI)       35
#   16-pin 13    1-wire, 3x DS18B20    37
#   12-pin  4    heater A relay        13   also the on-board blue LED
#   12-pin  5    heater B relay        12
#   12-pin  6    valve A               11
#   12-pin  7    valve B               10
#   12-pin  8    case fan               8
#   12-pin 11    I2C SCL (and Qwiic)    2
#   12-pin 12    I2C SDA (and Qwiic)    1

substitutions:
  pin_heater_a: GPIO13
  pin_heater_b: GPIO12
  pin_valve_a: GPIO11
  pin_valve_b: GPIO10
  pin_fan: GPIO8
  pin_i2c_sda: GPIO1
  pin_i2c_scl: GPIO2
  pin_onewire: GPIO37
  pin_spi_clk: GPIO36
  pin_spi_mosi: GPIO35
  pin_lcd_cs: GPIO5
  pin_lcd_dc: GPIO7
  pin_lcd_rst: GPIO9
  pin_lcd_bl: GPIO17

esp32:
  board: sparkfun_esp32s2_thing_plus   # if rejected, esp32-s2-saola-1 works (same module)
  variant: esp32s2
  framework:
    type: esp-idf
    # A TLS session reserves ~16 KB per direction by default. With WiFi,
    # the API, the web server and the display up the S2 has ~35 KB free,
    # so 1.0.0's HTTPS manifest fetch failed with mbedtls_ssl_setup
    # -0x7F00 (alloc failed). Allocate the record buffers only while in
    # use and cap the outgoing one: requests to GitHub are small.
    # That alone got to the handshake, which then failed verifying
    # GitHub's certificate (alloc of 4437 B failed, largest free block
    # ~12 KB). So also free the TLS config and CA data as soon as the
    # handshake no longer needs them, and keep fewer permanent WiFi RX
    # buffers (10 x ~1.6 KB by default; the block-ack window must not
    # exceed them).
    sdkconfig_options:
      CONFIG_MBEDTLS_DYNAMIC_BUFFER: y
      CONFIG_MBEDTLS_DYNAMIC_FREE_CONFIG_DATA: y
      CONFIG_MBEDTLS_DYNAMIC_FREE_CA_CERT: y
      CONFIG_MBEDTLS_ASYMMETRIC_CONTENT_LEN: y
      CONFIG_MBEDTLS_SSL_OUT_CONTENT_LEN: "4096"
      CONFIG_ESP_WIFI_STATIC_RX_BUFFER_NUM: "6"
      CONFIG_ESP_WIFI_RX_BA_WIN: "4"

logger:
  # The S2 Thing Plus's USB port is a CP2102 on UART0. ESPHome's S2 default
  # is USB_CDC, which is the bare native-USB pins on this board, so nothing
  # would ever reach `esphome logs` over the cable. The log level is set in
  # base.yaml; ESPHome merges the logger blocks.
  hardware_uart: UART0
```

- [ ] **Step 3: Take the chip out of the platform package**

Apply to `esphome/packages/platform-esp32.yaml`. The whole `esp32:` block and the whole `logger:` block go; nothing below `# No network credentials here.` changes:

```diff
--- a/esphome/packages/platform-esp32.yaml
+++ b/esphome/packages/platform-esp32.yaml
@@ -1,38 +1,9 @@
-# ESP32-S2 platform: board, serial logging, OTA, WiFi, captive portal and
-# the web server. Shared by the production and virtual builds; the host
-# preview build uses packages/platform-host.yaml instead. No control logic
-# lives here.
-
-esp32:
-  board: sparkfun_esp32s2_thing_plus   # if rejected, esp32-s2-saola-1 works (same module)
-  variant: esp32s2
-  framework:
-    type: esp-idf
-    # A TLS session reserves ~16 KB per direction by default. With WiFi,
-    # the API, the web server and the display up the S2 has ~35 KB free,
-    # so 1.0.0's HTTPS manifest fetch failed with mbedtls_ssl_setup
-    # -0x7F00 (alloc failed). Allocate the record buffers only while in
-    # use and cap the outgoing one: requests to GitHub are small.
-    # That alone got to the handshake, which then failed verifying
-    # GitHub's certificate (alloc of 4437 B failed, largest free block
-    # ~12 KB). So also free the TLS config and CA data as soon as the
-    # handshake no longer needs them, and keep fewer permanent WiFi RX
-    # buffers (10 x ~1.6 KB by default; the block-ack window must not
-    # exceed them).
-    sdkconfig_options:
-      CONFIG_MBEDTLS_DYNAMIC_BUFFER: y
-      CONFIG_MBEDTLS_DYNAMIC_FREE_CONFIG_DATA: y
-      CONFIG_MBEDTLS_DYNAMIC_FREE_CA_CERT: y
-      CONFIG_MBEDTLS_ASYMMETRIC_CONTENT_LEN: y
-      CONFIG_MBEDTLS_SSL_OUT_CONTENT_LEN: "4096"
-      CONFIG_ESP_WIFI_STATIC_RX_BUFFER_NUM: "6"
-      CONFIG_ESP_WIFI_RX_BA_WIN: "4"
-
-logger:
-  # The S2 Thing Plus's USB port is a CP2102 on UART0. ESPHome's S2 default
-  # is USB_CDC, which is the bare native-USB pins on this board, so nothing
-  # would ever reach `esphome logs` over the cable. The log level is set in
-  # base.yaml; ESPHome merges the two logger blocks.
-  hardware_uart: UART0
+# Everything an ESP32 build needs that does not depend on which chip it is:
+# WiFi, the setup access point, the captive portal and the web server.
+# Shared by the production, virtual and hw-test builds; the host preview
+# build uses packages/platform-host.yaml instead. The board, the framework
+# and the pin map are in packages/board-s2.yaml or packages/board-c6.yaml,
+# which every selector that includes this file must also include. No
+# control logic lives here.
 
 # No network credentials here. The dev builds take theirs from
```

- [ ] **Step 4: Replace the GPIO numbers in the shared packages**

```diff
--- a/esphome/packages/base.yaml
+++ b/esphome/packages/base.yaml
@@ -7,10 +7,11 @@
 # package, not here.
 #
-# Outputs (12-pin header), identical on every build (the host build drives no pins):
-#   GPIO13  Heater A relay coil (5 V, low-side NPN)     interlocked with B
-#   GPIO12  Heater B relay coil                          interlocked with A
-#   GPIO11  Valve A  (24 V solenoid, low-side MOSFET)   interlocked with B
-#   GPIO10  Valve B                                      interlocked with A
-#   GPIO8   Case fan (24 V, low-side MOSFET)
+# Outputs (12-pin header positions 4 to 8): heater A and B relay coils
+# (5 V, low-side NPN, interlocked), valve A and B (24 V solenoids, low-side
+# MOSFETs, interlocked) and the case fan. The GPIO behind each one depends
+# on the board and comes from ${pin_heater_a}, ${pin_heater_b},
+# ${pin_valve_a}, ${pin_valve_b} and ${pin_fan} in packages/board-s2.yaml or
+# packages/board-c6.yaml (placeholders in platform-host.yaml: the host build
+# drives no pins).
 #
 # Cycle logic (control tick every 5 s):
@@ -302,5 +303,5 @@
     id: heater_a
     internal: ${outputs_internal}
-    pin: GPIO13
+    pin: ${pin_heater_a}
     restore_mode: ALWAYS_OFF
     interlock: [heater_b]
@@ -311,5 +312,5 @@
     id: heater_b
     internal: ${outputs_internal}
-    pin: GPIO12
+    pin: ${pin_heater_b}
     restore_mode: ALWAYS_OFF
     interlock: [heater_a]
@@ -320,5 +321,5 @@
     id: valve_a
     internal: ${outputs_internal}
-    pin: GPIO11
+    pin: ${pin_valve_a}
     restore_mode: ALWAYS_OFF
     interlock: [valve_b]
@@ -329,5 +330,5 @@
     id: valve_b
     internal: ${outputs_internal}
-    pin: GPIO10
+    pin: ${pin_valve_b}
     restore_mode: ALWAYS_OFF
     interlock: [valve_a]
@@ -337,5 +338,5 @@
     name: "Case Fan"
     id: case_fan
-    pin: GPIO8
+    pin: ${pin_fan}
     restore_mode: ALWAYS_OFF
     icon: mdi:fan
```

```diff
--- a/esphome/packages/hw-real.yaml
+++ b/esphome/packages/hw-real.yaml
@@ -1,16 +1,18 @@
 # Real hardware: sensor buses and sensors. Provides the sensor ids base.yaml
 # expects: air_rh, air_temp, pack_a_temp, pack_b_temp, case_temp.
-#   GPIO1/2 I2C (Qwiic) - SHT45 in the process-air stream after the valves
-#   GPIO37  1-wire (MISO header pin) - DS18B20 x3: pack A, pack B, case
+#   I2C (Qwiic connector) - SHT45 in the process-air stream after the valves
+#   1-wire (16-pin position 13) - DS18B20 x3: pack A, pack B, case
+# The GPIOs are ${pin_i2c_sda}, ${pin_i2c_scl} and ${pin_onewire} from
+# packages/board-s2.yaml or packages/board-c6.yaml.
 
 # ---------------------------------------------------------------- buses
 i2c:
-  sda: GPIO1
-  scl: GPIO2
+  sda: ${pin_i2c_sda}
+  scl: ${pin_i2c_scl}
   frequency: 100kHz
 
 one_wire:
   - platform: gpio
-    pin: GPIO37
+    pin: ${pin_onewire}
 
 sensor:
```

```diff
--- a/esphome/packages/display-st7789.yaml
+++ b/esphome/packages/display-st7789.yaml
@@ -3,5 +3,7 @@
 # runs so the frame buffer allocation on the S2 gets exercised. The drawing
 # itself is ${display_lambda} from packages/display-draw.yaml.
-#   GPIO36/35 SPI SCK/MOSI, GPIO5 CS, GPIO7 DC, GPIO9 RST, GPIO17 backlight
+# The pins (SPI clock and data, CS, DC, RST, backlight) are ${pin_spi_clk},
+# ${pin_spi_mosi} and ${pin_lcd_*} from packages/board-s2.yaml or
+# packages/board-c6.yaml.
 #
 # mipi_spi, not ili9xxx, because ili9xxx cannot buffer less than a full frame
@@ -47,10 +49,10 @@
 
 spi:
-  clk_pin: GPIO36
-  mosi_pin: GPIO35
+  clk_pin: ${pin_spi_clk}
+  mosi_pin: ${pin_spi_mosi}
 
 output:
   - platform: ledc
-    pin: GPIO17
+    pin: ${pin_lcd_bl}
     id: backlight_pwm
     frequency: 1000Hz
@@ -72,7 +74,7 @@
       offset_height: 0     # try 80 if the image is shifted / cropped
       offset_width: 0
-    cs_pin: GPIO5
-    dc_pin: GPIO7
-    reset_pin: GPIO9
+    cs_pin: ${pin_lcd_cs}
+    dc_pin: ${pin_lcd_dc}
+    reset_pin: ${pin_lcd_rst}
     invert_colors: true    # most 1.54" IPS modules need this
     # ili9xxx defaulted to 40MHz; mipi_spi defaults to 10MHz and the ST7789V
```

```diff
--- a/esphome/packages/platform-host.yaml
+++ b/esphome/packages/platform-host.yaml
@@ -3,4 +3,14 @@
 # the host block and the one entity the display reads that would otherwise
 # come from WiFi. Home Assistant reaches the process over the API.
+
+# base.yaml takes its five output pins from the board package. The host
+# build has no board and drives no pins, so these are placeholders; they are
+# the S2's numbers so that this build's config is the same as it always was.
+substitutions:
+  pin_heater_a: GPIO13
+  pin_heater_b: GPIO12
+  pin_valve_a: GPIO11
+  pin_valve_b: GPIO10
+  pin_fan: GPIO8
 
 host:
```

- [ ] **Step 5: Add the board package to the three S2 selectors**

```diff
--- a/esphome/desiccant-dryer.yaml
+++ b/esphome/desiccant-dryer.yaml
@@ -10,4 +10,5 @@
 packages:
   production: !include packages/production.yaml
+  board: !include packages/board-s2.yaml
   ui: !include packages/ui-code-local.yaml
   # Home Assistant provisions the API key at adoption time.
```

```diff
--- a/esphome/desiccant-dryer-virtual.yaml
+++ b/esphome/desiccant-dryer-virtual.yaml
@@ -21,4 +21,5 @@
   base: !include packages/base.yaml
   platform: !include packages/platform-esp32.yaml
+  board: !include packages/board-s2.yaml
   secrets: !include packages/dev-secrets.yaml
   hardware: !include packages/hw-virtual.yaml
```

```diff
--- a/esphome/desiccant-dryer-hw-test.yaml
+++ b/esphome/desiccant-dryer-hw-test.yaml
@@ -22,4 +22,5 @@
   base: !include packages/base.yaml
   platform: !include packages/platform-esp32.yaml
+  board: !include packages/board-s2.yaml
   secrets: !include packages/dev-secrets.yaml
   hardware: !include packages/hw-real.yaml
```

- [ ] **Step 6: A selector with no board package must fail**

```bash
sed '/board-s2.yaml/d' esphome/desiccant-dryer-hw-test.yaml > esphome/zz-noboard.yaml
esphome config esphome/zz-noboard.yaml > /dev/null 2> .ci-cache/noboard.err; echo "rc=$?"
grep -c "is undefined" .ci-cache/noboard.err
rm esphome/zz-noboard.yaml
```

Expected: `rc=2`, and a count above zero. The messages read `'pin_heater_a' is undefined`, and so on for the other pins. If `rc=0`, a default has crept into a shared package: find and remove it.

- [ ] **Step 7: No GPIO number left in the shared packages**

```bash
grep -n "GPIO[0-9]" esphome/packages/base.yaml esphome/packages/hw-real.yaml esphome/packages/display-st7789.yaml esphome/packages/platform-esp32.yaml
```

Expected: no output.

- [ ] **Step 8: The five configs are unchanged**

```bash
PY="$(dirname "$(readlink -f "$(which esphome)")")/python"
mkdir -p .ci-cache/dumps/after
for s in desiccant-dryer-virtual desiccant-dryer-hw-test desiccant-dryer-host desiccant-dryer-scenarios; do
  esphome config esphome/$s.yaml > .ci-cache/dumps/after/$s.txt 2>/dev/null || echo "FAILED $s"
done
docker run --rm -v "$PWD:/config" -w /config --entrypoint esphome ghcr.io/esphome/esphome:2026.9.0 \
  config esphome/desiccant-dryer.yaml > .ci-cache/dumps/after/desiccant-dryer.txt 2>/dev/null || echo "FAILED desiccant-dryer"
for s in desiccant-dryer desiccant-dryer-virtual desiccant-dryer-hw-test desiccant-dryer-host desiccant-dryer-scenarios; do
  "$PY" scripts/normalize-config.py .ci-cache/dumps/before/$s.txt > .ci-cache/dumps/before/$s.json
  "$PY" scripts/normalize-config.py .ci-cache/dumps/after/$s.txt > .ci-cache/dumps/after/$s.json
  cmp -s .ci-cache/dumps/before/$s.json .ci-cache/dumps/after/$s.json && echo "$s IDENTICAL" || echo "$s DIFFERS"
done
```

Expected: five `IDENTICAL` lines and nothing else. `normalize-config.py` drops the `substitutions:` block, which is the only place the new keys show. On a `DIFFERS`, `diff` the two `.json` files and fix the YAML; do not move on.

- [ ] **Step 9: Lint still green**

```bash
docker run --rm -v "$PWD:/config" -w /config --entrypoint bash ghcr.io/esphome/esphome:2026.9.0 -c 'python3 tests/lint_config.py'
```

Expected: the same five `pass ok` lines as Task 1, Step 5.

- [ ] **Step 10: Commit**

```bash
git add esphome/packages esphome/desiccant-dryer.yaml esphome/desiccant-dryer-virtual.yaml esphome/desiccant-dryer-hw-test.yaml
git commit -m "Move the ESP32-S2 board, logger port and pin map into a board package"
```

---

### Task 3: Add the ESP32-C6 board package and its two selectors

**Files:**
- Create: `esphome/packages/board-c6.yaml`, `esphome/desiccant-dryer-c6.yaml`, `esphome/desiccant-dryer-hw-test-c6.yaml`, `tests/cases/T-J12C.yaml`
- Modify: `tests/cases/T-F15.yaml`, `tests/cases/T-B20.yaml`, `tests/cases/T-J04.yaml`, `tests/cases/T-K01L.yaml`

**Interfaces:**
- Consumes: the fourteen `pin_*` substitutions and the board-package shape from Task 2; dotted lint keys from Task 1.
- Produces: selectors `esphome/desiccant-dryer-c6.yaml` (device name `desiccant-dryer`, build directory `esphome/.esphome/build/desiccant-dryer-c6`) and `esphome/desiccant-dryer-hw-test-c6.yaml` (device name `desiccant-dryer-hw-test-c6`). Case `T-J12C`.

- [ ] **Step 1: Write the failing cases**

Create `tests/cases/T-J12C.yaml`:

```yaml
id: T-J12C
covers: [J-12]
type: lint
status: green          # the C6 pin table: packages/board-c6.yaml
harness: ci-lint
selectors: [esphome/desiccant-dryer-c6.yaml, esphome/desiccant-dryer-hw-test-c6.yaml]
assert:
  - switch heater_a has pin.number 18 and switch heater_b has pin.number 22
  - switch valve_a has pin.number 11 and switch valve_b has pin.number 10
  - switch case_fan has pin.number 8
```

Widen the four production-invariant cases so they also read the C6 selectors:

```diff
--- a/tests/cases/T-F15.yaml
+++ b/tests/cases/T-F15.yaml
@@ -4,5 +4,5 @@
 status: green
 harness: ci-lint
-selectors: [esphome/desiccant-dryer.yaml, esphome/desiccant-dryer-hw-test.yaml]
+selectors: [esphome/desiccant-dryer.yaml, esphome/desiccant-dryer-c6.yaml, esphome/desiccant-dryer-hw-test.yaml, esphome/desiccant-dryer-hw-test-c6.yaml]
 assert:
   - every switch in [heater_a, heater_b, valve_a, valve_b, case_fan] has restore_mode ALWAYS_OFF
```

```diff
--- a/tests/cases/T-B20.yaml
+++ b/tests/cases/T-B20.yaml
@@ -4,5 +4,5 @@
 status: green          # max_value is 118, the SF129E holding temperature (issue #34)
 harness: ci-lint
-selectors: [esphome/desiccant-dryer.yaml, esphome/desiccant-dryer-hw-test.yaml]
+selectors: [esphome/desiccant-dryer.yaml, esphome/desiccant-dryer-c6.yaml, esphome/desiccant-dryer-hw-test.yaml, esphome/desiccant-dryer-hw-test-c6.yaml]
 assert:
   - number overtemp has max_value <= 118
```

```diff
--- a/tests/cases/T-J04.yaml
+++ b/tests/cases/T-J04.yaml
@@ -4,5 +4,5 @@
 status: green
 harness: ci-lint
-selectors: [esphome/desiccant-dryer.yaml, esphome/desiccant-dryer-hw-test.yaml]
+selectors: [esphome/desiccant-dryer.yaml, esphome/desiccant-dryer-c6.yaml, esphome/desiccant-dryer-hw-test.yaml, esphome/desiccant-dryer-hw-test-c6.yaml]
 assert:
   - heater_a.interlock includes heater_b and heater_b.interlock includes heater_a
```

```diff
--- a/tests/cases/T-K01L.yaml
+++ b/tests/cases/T-K01L.yaml
@@ -4,5 +4,5 @@
 status: green
 harness: ci-lint
-selectors: [esphome/desiccant-dryer.yaml]
+selectors: [esphome/desiccant-dryer.yaml, esphome/desiccant-dryer-c6.yaml]
 assert:
   - every switch in [heater_a, heater_b, valve_a, valve_b] has internal true
```

- [ ] **Step 2: Run and watch them fail**

```bash
docker run --rm -v "$PWD:/config" -w /config --entrypoint bash ghcr.io/esphome/esphome:2026.9.0 -c 'python3 tests/lint_config.py'
```

Expected: exit 1, `esphome config esphome/desiccant-dryer-c6.yaml failed:` (the file does not exist yet).

- [ ] **Step 3: Create the C6 board package**

Create `esphome/packages/board-c6.yaml`. The three strapping pins are written as mappings because `ignore_strapping_warning: true` cannot go in the shared files: ESPHome rejects it on a pin that is not a strapping pin, which is every one of these on the S2.

```yaml
# SparkFun Thing Plus ESP32-C6 (DEV-22924): everything that depends on the
# chip. The board and framework block, the port the log goes out on, and the
# GPIO behind each header position. packages/board-s2.yaml is the same file
# for the ESP32-S2 Thing Plus. The main board is wired by header position
# and takes either board, so the two tables read row for row.
# Source: SparkFun's schematic, see docs/pinout-verification.md.
#
#   Position     Function             GPIO
#   16-pin  5    display backlight      0
#   16-pin  8    display RST            3
#   16-pin  9    display DC             4   strapping
#   16-pin 10    display CS             5   strapping
#   16-pin 11    SPI clock             19   also the uSD slot's clock
#   16-pin 12    SPI data (MOSI)       20   also the uSD slot's CMD
#   16-pin 13    1-wire, 3x DS18B20    21   also the uSD slot's DAT0
#   12-pin  4    heater A relay        18   also the uSD slot's CS
#   12-pin  5    heater B relay        22   card detect unless SD_DET is cut
#   12-pin  6    valve A               11   gauge alert unless ALRT is cut
#   12-pin  7    valve B               10
#   12-pin  8    case fan               8   strapping, 100k pull-up on board
#   12-pin 11    I2C SCL (and Qwiic)    7
#   12-pin 12    I2C SDA (and Qwiic)    6
#
# Before this board goes in a socket: cut the ALRT and SD_DET jumpers on
# its back and keep the uSD slot empty. docs/hardware.md has the steps.
# The 12-pin silkscreen reads GPIO0..GPIO6; those are SparkFun's header
# labels, not chip GPIO numbers ("GPIO0" is IO18).

substitutions:
  pin_heater_a: GPIO18
  pin_heater_b: GPIO22
  pin_valve_a: GPIO11
  pin_valve_b: GPIO10
  # GPIO8 picks the boot mode together with GPIO9, and only when GPIO9 is
  # low (download mode). The fan's gate pulldown holds it low at reset,
  # which keeps the fan off; normal boot ignores it.
  pin_fan:
    number: GPIO8
    ignore_strapping_warning: true
  pin_i2c_sda: GPIO6
  pin_i2c_scl: GPIO7
  pin_onewire: GPIO21
  pin_spi_clk: GPIO19
  pin_spi_mosi: GPIO20
  # GPIO4 and GPIO5 only set SDIO timing at reset, and the panel's DC and
  # CS inputs do not drive them.
  pin_lcd_cs:
    number: GPIO5
    ignore_strapping_warning: true
  pin_lcd_dc:
    number: GPIO4
    ignore_strapping_warning: true
  pin_lcd_rst: GPIO3
  pin_lcd_bl: GPIO0

esp32:
  board: sparkfun_esp32c6_thing_plus
  variant: esp32c6
  framework:
    type: esp-idf
    # The same TLS and WiFi buffer settings as packages/board-s2.yaml,
    # where the reasons are written down. The C6 has the heap to do
    # without them; they are kept so the firmware update path runs the
    # same TLS configuration on both chips.
    sdkconfig_options:
      CONFIG_MBEDTLS_DYNAMIC_BUFFER: y
      CONFIG_MBEDTLS_DYNAMIC_FREE_CONFIG_DATA: y
      CONFIG_MBEDTLS_DYNAMIC_FREE_CA_CERT: y
      CONFIG_MBEDTLS_ASYMMETRIC_CONTENT_LEN: y
      CONFIG_MBEDTLS_SSL_OUT_CONTENT_LEN: "4096"
      CONFIG_ESP_WIFI_STATIC_RX_BUFFER_NUM: "6"
      CONFIG_ESP_WIFI_RX_BA_WIN: "4"

logger:
  # This board's USB-C port is the chip's own USB-Serial-JTAG; there is no
  # UART bridge. That is also ESPHome's default for the C6, stated here so
  # it does not depend on one. The log level is set in base.yaml.
  hardware_uart: USB_SERIAL_JTAG
```

- [ ] **Step 4: Create the two selectors**

Create `esphome/desiccant-dryer-c6.yaml`:

```yaml
# Production build for the SparkFun Thing Plus ESP32-C6: the same firmware
# as desiccant-dryer.yaml with the C6's board package. The device name is
# the same on purpose, so a replacement board looks like the same kind of
# unit to Home Assistant; the build directory is not, so the two production
# compiles never share one. CI compiles it and the release workflow builds
# the published C6 images from it.
# Contents: packages/production.yaml. See docs/releasing.md.
substitutions:
  name: desiccant-dryer
  friendly_name: Desiccant Dryer

esphome:
  build_path: build/desiccant-dryer-c6

packages:
  production: !include packages/production.yaml
  board: !include packages/board-c6.yaml
  ui: !include packages/ui-code-local.yaml
  # Home Assistant provisions the API key at adoption time.
  api: !include packages/api-provisioned.yaml
```

Create `esphome/desiccant-dryer-hw-test-c6.yaml`:

```yaml
# Hardware test build for the SparkFun Thing Plus ESP32-C6: the same build
# as desiccant-dryer-hw-test.yaml (production controller, real sensors and
# panel, developer credentials, password-protected OTA) with the C6's board
# package. Not a release. Appears in Home Assistant as its own device.
# Flash:  esphome run esphome/desiccant-dryer-hw-test-c6.yaml
#         (first time over USB with the board out of its socket, then
#         --device <board> over the network; docs/hardware-bringup.md §8)
substitutions:
  name: desiccant-dryer-hw-test-c6
  # "(C6 Test)", not "(HW Test C6)": the setup access point's SSID is this
  # name plus " Setup", and an SSID may not be longer than 32 characters.
  friendly_name: Desiccant Dryer (C6 Test)
  # No on-device updater here, so the panel keeps a full frame buffer and
  # the writer runs once per redraw.
  display_buffer_size: "100%"
  display_update_interval: 5s
  # Bench build: the four relay switches stay commandable from Home
  # Assistant so the relay and interlock steps in docs/hardware-bringup.md
  # can toggle them by hand, and the tick does not force them off while the
  # dryer is disabled. The production build has them internal (K-01/K-02).
  outputs_internal: "false"

packages:
  base: !include packages/base.yaml
  platform: !include packages/platform-esp32.yaml
  board: !include packages/board-c6.yaml
  secrets: !include packages/dev-secrets.yaml
  hardware: !include packages/hw-real.yaml
  draw: !include packages/display-draw.yaml
  ui: !include packages/ui-code-local.yaml
  display: !include packages/display-st7789.yaml

logger:
  level: DEBUG
```

- [ ] **Step 5: Both validate with no warning**

```bash
esphome config esphome/desiccant-dryer-hw-test-c6.yaml > .ci-cache/dumps/after/desiccant-dryer-hw-test-c6.txt 2> .ci-cache/c6-hw-test.err; echo "rc=$? warnings=$(grep -c WARNING .ci-cache/c6-hw-test.err)"
docker run --rm -v "$PWD:/config" -w /config --entrypoint esphome ghcr.io/esphome/esphome:2026.9.0 \
  config esphome/desiccant-dryer-c6.yaml > .ci-cache/dumps/after/desiccant-dryer-c6.txt 2> .ci-cache/c6-prod.err; echo "rc=$? warnings=$(grep -c WARNING .ci-cache/c6-prod.err)"
grep -n "build_path" .ci-cache/dumps/after/desiccant-dryer-c6.txt
```

Expected: `rc=0 warnings=0` twice, then `  build_path: build/desiccant-dryer-c6`. A strapping-pin warning means a mapping in `board-c6.yaml` lost its flag. `SSID can't be longer than 32 characters` means the friendly name was lengthened.

- [ ] **Step 6: Lint green on both chips**

```bash
docker run --rm -v "$PWD:/config" -w /config --entrypoint bash ghcr.io/esphome/esphome:2026.9.0 -c 'python3 tests/lint_config.py'
```

Expected, exit 0:

```text
T-B20    green  pass ok
T-F15    green  pass ok
T-J04    green  pass ok
T-J12    green  pass ok
T-J12C   green  pass ok
T-K01L   green  pass ok
```

- [ ] **Step 7: Prove T-J12C can fail**

GPIO2 is free on the C6, so validation passes and the assertion itself must catch it:

```bash
perl -pi -e 's/^  pin_heater_a: GPIO18$/  pin_heater_a: GPIO2/' esphome/packages/board-c6.yaml
docker run --rm -v "$PWD:/config" -w /config --entrypoint bash ghcr.io/esphome/esphome:2026.9.0 -c 'python3 tests/lint_config.py T-J12 T-J12C'
perl -pi -e 's/^  pin_heater_a: GPIO2$/  pin_heater_a: GPIO18/' esphome/packages/board-c6.yaml
grep -n "pin_heater_a" esphome/packages/board-c6.yaml
```

Expected from the lint run, exit 1:

```text
T-J12    green  pass ok
T-J12C   green  FAIL UNEXPECTED
           esphome/desiccant-dryer-c6.yaml: switch heater_a: pin.number is 2, expected == 18.0
           esphome/desiccant-dryer-hw-test-c6.yaml: switch heater_a: pin.number is 2, expected == 18.0
```

and from the last command `  pin_heater_a: GPIO18`.

- [ ] **Step 8: The two production configs differ only where the chip does**

```bash
PY="$(dirname "$(readlink -f "$(which esphome)")")/python"
"$PY" scripts/normalize-config.py .ci-cache/dumps/after/desiccant-dryer-c6.txt > .ci-cache/dumps/after/desiccant-dryer-c6.json
diff .ci-cache/dumps/after/desiccant-dryer.json .ci-cache/dumps/after/desiccant-dryer-c6.json \
  | grep '^[<>]' | sed -E 's/^[<>] *"([a-z_]+)".*/\1/' | sort | uniq -c
```

Expected, exactly these keys and counts (each differing line appears once per side):

```text
   2 board
   2 build_path
   2 cpu_frequency
   2 hardware_uart
   6 ignore_strapping_warning
  16 number
   2 scl
   2 sda
   2 variant
```

Any other key means the two production builds have drifted apart in something that is not the chip.

- [ ] **Step 9: Commit**

```bash
git add esphome/packages/board-c6.yaml esphome/desiccant-dryer-c6.yaml esphome/desiccant-dryer-hw-test-c6.yaml tests/cases
git commit -m "Add the ESP32-C6 Thing Plus board package and its selectors"
```

---

### Task 4: One manifest for both chips

**Files:**
- Create: `tests/make_manifest_test.sh`
- Modify: `scripts/make-manifest.sh` (rewritten; new argument order)

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `scripts/make-manifest.sh <version> <out-dir> <release-url> <chip>=<build-dir>...` with `<chip>` `esp32s2` or `esp32c6`; `<release-url>` may be `""`. Exit 0 and files `desiccant-dryer-<version>-<chip>.ota.bin`, `…factory.bin`, `manifest.json` in `<out-dir>`; exit 2 on a usage error, 1 on a missing or wrong-chip image. `bash tests/make_manifest_test.sh` exits 0 when the script behaves.

- [ ] **Step 1: Write the failing test**

Create `tests/make_manifest_test.sh`:

```bash
#!/usr/bin/env bash
# Exercises scripts/make-manifest.sh with stand-in images: twelve bytes of
# image header, the two chip-id bytes, then filler. Run from the repo root:
#   bash tests/make_manifest_test.sh
# It is not a tests/cases/ case: it tests the release packaging script, not
# the firmware. The lint-config job in .github/workflows/build.yml runs it.
set -u
t=$(mktemp -d); trap 'rm -rf "$t"' EXIT
mk() { # mk <dir> <chip id bytes, e.g. '\x02\x00'>
  mkdir -p "$1"
  { printf '\xe9\x05\x02\x20\x00\x00\x00\x00\xee\x00\x00\x00'; printf "$2"; printf 'payload-%s' "$1"; } > "$1/firmware.ota.bin"
  printf 'factory-%s' "$1" > "$1/firmware.factory.bin"
}
mk "$t/s2" '\x02\x00'; mk "$t/c6" '\x0d\x00'
fail=0
ok()   { if "$@" >/dev/null 2>&1; then echo "ok    $name"; else echo "FAIL  $name"; fail=1; fi; }
nok()  { if "$@" >/dev/null 2>&1; then echo "FAIL  $name (accepted)"; fail=1; else echo "ok    $name"; fi; }
name="both chips"; ok scripts/make-manifest.sh 9.9.9 "$t/out" https://example.test/r "esp32s2=$t/s2" "esp32c6=$t/c6"
name="manifest is JSON with two builds"; ok python3 -c "
import json,hashlib,sys,pathlib
o=pathlib.Path('$t/out'); m=json.loads((o/'manifest.json').read_text())
assert m['version']=='9.9.9' and [b['chipFamily'] for b in m['builds']]==['ESP32-S2','ESP32-C6'], m
for b,chip in zip(m['builds'],['esp32s2','esp32c6']):
    assert b['ota']['path']=='desiccant-dryer-9.9.9-%s.ota.bin'%chip, b
    assert b['parts']==[{'path':'desiccant-dryer-9.9.9-%s.factory.bin'%chip,'offset':0}], b
    assert b['ota']['md5']==hashlib.md5((o/b['ota']['path']).read_bytes()).hexdigest(), b
    assert b['ota']['release_url']=='https://example.test/r'
assert sorted(p.name for p in o.iterdir())==sorted(['manifest.json']+['desiccant-dryer-9.9.9-%s.%s.bin'%(c,k) for c in ['esp32s2','esp32c6'] for k in ['ota','factory']])
"
name="chips in the other order"; ok scripts/make-manifest.sh 9.9.9 "$t/rev" "" "esp32c6=$t/c6" "esp32s2=$t/s2"
name="other order still lists both"; ok python3 -c "
import json
m=json.load(open('$t/rev/manifest.json'))
assert sorted(b['chipFamily'] for b in m['builds'])==['ESP32-C6','ESP32-S2'], m
"
name="one chip alone"; ok scripts/make-manifest.sh 9.9.9 "$t/one" "" "esp32s2=$t/s2"
name="swapped build dirs refused"; nok scripts/make-manifest.sh 9.9.9 "$t/x1" "" "esp32s2=$t/c6" "esp32c6=$t/s2"
name="same chip twice refused"; nok scripts/make-manifest.sh 9.9.9 "$t/x2" "" "esp32s2=$t/s2" "esp32s2=$t/s2"
name="unknown chip refused"; nok scripts/make-manifest.sh 9.9.9 "$t/x3" "" "esp32=$t/s2"
name="missing image refused"; nok scripts/make-manifest.sh 9.9.9 "$t/x4" "" "esp32c6=$t/nope"
name="no chips refused"; nok scripts/make-manifest.sh 9.9.9 "$t/x5" ""
exit $fail
```

- [ ] **Step 2: Run it against today's script**

```bash
bash tests/make_manifest_test.sh; echo "exit=$?"
```

Expected: `exit=1`, with `FAIL` on the first five lines (`both chips` through `one chip alone`). The five `refused` lines read `ok` only because today's script rejects those arguments for the wrong reason.

- [ ] **Step 3: Rewrite the script**

Replace the whole of `scripts/make-manifest.sh` with:

```bash
#!/usr/bin/env bash
# Assemble the release files for one production release: an image pair per
# chip and one manifest listing them all.
#   scripts/make-manifest.sh <version> <out-dir> <release-url> <chip>=<build-dir>...
# <chip> is esp32s2 or esp32c6. <build-dir> is that chip's build directory
# after `esphome compile` of its selector:
#   esp32s2=esphome/.esphome/build/desiccant-dryer/build      (desiccant-dryer.yaml)
#   esp32c6=esphome/.esphome/build/desiccant-dryer-c6/build   (desiccant-dryer-c6.yaml)
# <release-url> may be "" for a dry run. Writes
# desiccant-dryer-<version>-<chip>.ota.bin and .factory.bin for each chip and
# manifest.json (esp-web-tools format: read by the device's
# `update: platform: http_request`, which takes the build whose chipFamily
# is its own chip, and by web.esphome.io) to <out-dir>.
set -euo pipefail
usage="usage: $0 <version> <out-dir> <release-url> <chip>=<build-dir>..."
[ $# -ge 4 ] || { echo "$usage" >&2; exit 2; }
version=$1 out=$2 release_url=$3
shift 3
mkdir -p "$out"
builds="" seen=""
for pair in "$@"; do
  chip=${pair%%=*} build=${pair#*=}
  # chipFamily is the name esp-web-tools and ESPHome's ESPHOME_VARIANT use.
  # id is esp_chip_id_t from ESP-IDF, as it appears little-endian in bytes
  # 12-13 of an application image.
  case $chip in
    esp32s2) family="ESP32-S2" id="0200" ;;
    esp32c6) family="ESP32-C6" id="0d00" ;;
    *) echo "unknown chip '$chip' in '$pair' (esp32s2 or esp32c6)" >&2; exit 2 ;;
  esac
  case " $seen " in
    *" $chip "*) echo "chip '$chip' given twice" >&2; exit 2 ;;
  esac
  seen="$seen $chip"
  for f in firmware.ota.bin firmware.factory.bin; do
    [ -f "$build/$f" ] || { echo "$build/$f is missing; compile that chip's selector first" >&2; exit 1; }
  done
  # A build directory handed to the wrong chip would publish that chip's
  # units an image they cannot run. Refuse it here, from the image itself.
  got=$(od -An -tx1 -j12 -N2 "$build/firmware.ota.bin" | tr -d ' \n')
  [ "$got" = "$id" ] || { echo "$build/firmware.ota.bin is not an $family image (chip id bytes $got, expected $id)" >&2; exit 1; }
  ota="desiccant-dryer-${version}-${chip}.ota.bin"
  factory="desiccant-dryer-${version}-${chip}.factory.bin"
  cp "$build/firmware.ota.bin" "$out/$ota"
  cp "$build/firmware.factory.bin" "$out/$factory"
  if command -v md5sum >/dev/null; then
    md5=$(md5sum "$out/$ota" | cut -d' ' -f1)
  else
    md5=$(md5 -q "$out/$ota")
  fi
  [ -z "$builds" ] || builds="$builds,"
  builds="$builds
    {
      \"chipFamily\": \"${family}\",
      \"ota\": {
        \"path\": \"${ota}\",
        \"md5\": \"${md5}\",
        \"summary\": \"Desiccant Dryer ${version}\",
        \"release_url\": \"${release_url}\"
      },
      \"parts\": [{ \"path\": \"${factory}\", \"offset\": 0 }]
    }"
  echo "$family: $ota md5 $md5"
done
cat > "$out/manifest.json" <<JSON
{
  "name": "Desiccant Dryer",
  "version": "${version}",
  "home_assistant_domain": "esphome",
  "new_install_prompt_erase": true,
  "builds": [${builds}
  ]
}
JSON
echo "wrote $out/manifest.json"
```

The chip id bytes are `esp_chip_id_t` from ESP-IDF, little-endian at offset 12 of an application image. `0200` was read from this project's own S2 images. `0d00` for the C6 is from ESP-IDF's header and is confirmed on a real image in Task 6.

- [ ] **Step 4: Run the test**

```bash
chmod +x scripts/make-manifest.sh
bash tests/make_manifest_test.sh; echo "exit=$?"
```

Expected:

```text
ok    both chips
ok    manifest is JSON with two builds
ok    chips in the other order
ok    other order still lists both
ok    one chip alone
ok    swapped build dirs refused
ok    same chip twice refused
ok    unknown chip refused
ok    missing image refused
ok    no chips refused
exit=0
```

- [ ] **Step 5: Commit**

```bash
git add scripts/make-manifest.sh tests/make_manifest_test.sh
git commit -m "Write one release manifest with a build per chip"
```

---

### Task 5: Compile and release both chips; version 1.3.0

**Files:**
- Modify: `.github/workflows/build.yml`, `.github/workflows/release.yml`, `esphome/version.yaml`

**Interfaces:**
- Consumes: the two C6 selectors and the build directory `esphome/.esphome/build/desiccant-dryer-c6/build` (Task 3); the `make-manifest.sh` arguments and `tests/make_manifest_test.sh` (Task 4).
- Produces: CI jobs `compile c6-production` and `compile c6-hw-test`; a release that publishes four `.bin` files and one manifest.

- [ ] **Step 1: build.yml**

In `.github/workflows/build.yml`, replace

```text
            -c 'python3 tests/lint_config.py'
```

with

```text
            -c 'python3 tests/lint_config.py'
      # Plain bash and python3 on the runner: the script only copies files
      # and writes JSON, so its test needs neither the image nor a compile.
      - name: Test the release manifest script
        run: bash tests/make_manifest_test.sh
```

In `.github/workflows/build.yml`, replace

```text
          - variant: production
            yaml: esphome/desiccant-dryer.yaml
            toolchain: esp32
          - variant: virtual
            yaml: esphome/desiccant-dryer-virtual.yaml
            toolchain: esp32
          - variant: hw-test
            yaml: esphome/desiccant-dryer-hw-test.yaml
            toolchain: esp32
```

with

```text
          # One toolchain cache per chip: ESPHome installs the ESP-IDF tools
          # for the target it is building (Xtensa for the S2, RISC-V for the
          # C6), so a cache saved by one chip's job lacks the other's
          # compiler. The C6 variants are named c6-<build>, not <build>-c6,
          # so the `build-...-production-` and `build-...-hw-test-` restore
          # prefixes below can never pick up a C6 build directory.
          # `package` runs the release packaging check on a production image.
          - variant: production
            yaml: esphome/desiccant-dryer.yaml
            toolchain: esp32s2
            package: esp32s2=esphome/.esphome/build/desiccant-dryer/build
          - variant: c6-production
            yaml: esphome/desiccant-dryer-c6.yaml
            toolchain: esp32c6
            package: esp32c6=esphome/.esphome/build/desiccant-dryer-c6/build
          - variant: virtual
            yaml: esphome/desiccant-dryer-virtual.yaml
            toolchain: esp32s2
          - variant: hw-test
            yaml: esphome/desiccant-dryer-hw-test.yaml
            toolchain: esp32s2
          - variant: c6-hw-test
            yaml: esphome/desiccant-dryer-hw-test-c6.yaml
            toolchain: esp32c6
```

In `.github/workflows/build.yml`, replace

```text
          key: toolchains-${{ env.ESPHOME_VERSION }}-${{ matrix.toolchain }}-${{ hashFiles('esphome/packages/platform-*.yaml') }}
```

with

```text
          key: toolchains-${{ env.ESPHOME_VERSION }}-${{ matrix.toolchain }}-${{ hashFiles('esphome/packages/platform-*.yaml', 'esphome/packages/board-*.yaml') }}
```

In `.github/workflows/build.yml`, replace

```text
      - name: Hand caches back to the runner user
        run: sudo chown -R "$(id -u):$(id -g)" "$TOOL_CACHE" esphome/.esphome
```

with

```text
      - name: Hand caches back to the runner user
        run: sudo chown -R "$(id -u):$(id -g)" "$TOOL_CACHE" esphome/.esphome
      # The packaging the release workflow does, on this job's own image:
      # proves the build directory is where release.yml looks for it and
      # that the image header names this chip.
      - name: Check the release packaging of this image
        if: matrix.package
        run: scripts/make-manifest.sh 0.0.0 "$RUNNER_TEMP/site" "" "${{ matrix.package }}"
```

- [ ] **Step 2: release.yml**

In `.github/workflows/release.yml`, replace

```text
# Builds the production firmware for a version tag, attaches the binaries
# and an esp-web-tools manifest to a GitHub Release, and copies them to the
```

with

```text
# Builds the production firmware for a version tag, one image per supported
# chip (ESP32-S2 and ESP32-C6), attaches the binaries and one esp-web-tools
# manifest listing both to a GitHub Release, and copies them to the
```

In `.github/workflows/release.yml`, replace

```text
      - name: Restore toolchains
        uses: actions/cache/restore@v6
        with:
          path: ${{ env.TOOL_CACHE }}
          key: toolchains-${{ env.ESPHOME_VERSION }}-esp32-${{ hashFiles('esphome/packages/platform-*.yaml') }}
          restore-keys: toolchains-${{ env.ESPHOME_VERSION }}-esp32-
      - name: Restore build directory
        uses: actions/cache/restore@v6
        with:
          path: esphome/.esphome
          key: build-${{ env.ESPHOME_VERSION }}-production-${{ hashFiles('esphome/**') }}
          restore-keys: build-${{ env.ESPHOME_VERSION }}-production-
```

with

```text
      # The S2's toolchain cache from build.yml. The C6 compile below adds
      # its own compiler to the same directory as it goes, which costs a few
      # minutes; releases are rare and this workflow never saves a cache.
      - name: Restore toolchains
        uses: actions/cache/restore@v6
        with:
          path: ${{ env.TOOL_CACHE }}
          key: toolchains-${{ env.ESPHOME_VERSION }}-esp32s2-${{ hashFiles('esphome/packages/platform-*.yaml', 'esphome/packages/board-*.yaml') }}
          restore-keys: toolchains-${{ env.ESPHOME_VERSION }}-esp32s2-
      # Two caches into one directory: each holds only its own build
      # subdirectory (build/desiccant-dryer, build/desiccant-dryer-c6).
      - name: Restore S2 build directory
        uses: actions/cache/restore@v6
        with:
          path: esphome/.esphome
          key: build-${{ env.ESPHOME_VERSION }}-production-${{ hashFiles('esphome/**') }}
          restore-keys: build-${{ env.ESPHOME_VERSION }}-production-
      - name: Restore C6 build directory
        uses: actions/cache/restore@v6
        with:
          path: esphome/.esphome
          key: build-${{ env.ESPHOME_VERSION }}-c6-production-${{ hashFiles('esphome/**') }}
          restore-keys: build-${{ env.ESPHOME_VERSION }}-c6-production-
```

In `.github/workflows/release.yml`, replace

```text
      - name: Compile
        run: |
          mkdir -p "$TOOL_CACHE"
          docker run --rm -v "$PWD:/config" -w /config \
            -v "$PWD/$TOOL_CACHE:/cache" \
            "ghcr.io/esphome/esphome:$ESPHOME_VERSION" compile esphome/desiccant-dryer.yaml
          sudo chown -R "$(id -u):$(id -g)" esphome/.esphome

      - name: Assemble manifest and binaries
        run: |
          scripts/make-manifest.sh "${{ steps.ver.outputs.version }}" \
            esphome/.esphome/build/desiccant-dryer/build \
            site "${{ github.server_url }}/${{ github.repository }}/releases/tag/${{ github.ref_name }}"
          cat site/manifest.json
```

with

```text
      - name: Compile both chips
        run: |
          mkdir -p "$TOOL_CACHE"
          for selector in desiccant-dryer desiccant-dryer-c6; do
            docker run --rm -v "$PWD:/config" -w /config \
              -v "$PWD/$TOOL_CACHE:/cache" \
              "ghcr.io/esphome/esphome:$ESPHOME_VERSION" compile "esphome/$selector.yaml"
          done
          sudo chown -R "$(id -u):$(id -g)" esphome/.esphome

      # make-manifest.sh reads each image's header and refuses one built for
      # the other chip, so a mixed-up build directory stops the release here.
      - name: Assemble manifest and binaries
        run: |
          scripts/make-manifest.sh "${{ steps.ver.outputs.version }}" site \
            "${{ github.server_url }}/${{ github.repository }}/releases/tag/${{ github.ref_name }}" \
            esp32s2=esphome/.esphome/build/desiccant-dryer/build \
            esp32c6=esphome/.esphome/build/desiccant-dryer-c6/build
          cat site/manifest.json
```

- [ ] **Step 3: Version**

In `esphome/version.yaml`, replace

```text
# Only esphome/desiccant-dryer.yaml includes this file.
substitutions:
  version: "1.2.4"
```

with

```text
# Only the production build includes this file (packages/production.yaml,
# wrapped by esphome/desiccant-dryer.yaml for the ESP32-S2 board and
# esphome/desiccant-dryer-c6.yaml for the ESP32-C6 board). Both chips share
# the one version number.
substitutions:
  version: "1.3.0"
```

- [ ] **Step 4: Check the workflows**

```bash
command -v actionlint >/dev/null && actionlint .github/workflows/build.yml .github/workflows/release.yml && echo "actionlint ok"
python3 -c "import yaml,sys; [yaml.safe_load(open(f)) for f in sys.argv[1:]]; print('yaml ok')" .github/workflows/build.yml .github/workflows/release.yml
grep -c "esp32c6" .github/workflows/build.yml .github/workflows/release.yml
```

Expected: `actionlint ok` (when it is installed; `brew install actionlint` otherwise), `yaml ok`, and counts of `3` for `build.yml` and `1` for `release.yml`. If the system `python3` has no PyYAML, use ESPHome's Python from "Before you start".

- [ ] **Step 5: Lint still green at 1.3.0**

```bash
docker run --rm -v "$PWD:/config" -w /config --entrypoint bash ghcr.io/esphome/esphome:2026.9.0 -c 'python3 tests/lint_config.py'
```

Expected: the six `pass ok` lines of Task 3, Step 6.

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/build.yml .github/workflows/release.yml esphome/version.yaml
git commit -m "Build and release an image per chip; version 1.3.0"
```

---

### Task 6: Prove the C6 image builds and packages

Nothing so far has compiled for a C6. CI will, but find out here first. This is slow the first time: ESP-IDF and the RISC-V toolchain are about 2 GB, and a Docker bind mount on macOS is slow. Start it in the background and expect 20 to 60 minutes.

**Files:**
- Modify (only if Step 2 says so): `esphome/packages/board-c6.yaml`, `scripts/make-manifest.sh`, `tests/make_manifest_test.sh`

**Interfaces:**
- Consumes: `esphome/desiccant-dryer-c6.yaml` (Task 3), `scripts/make-manifest.sh` (Task 4).
- Produces: evidence, and at most a one-line correction.

- [ ] **Step 1: Compile the C6 production image**

```bash
mkdir -p .ci-cache/tools
docker run --rm -v "$PWD:/config" -w /config -v "$PWD/.ci-cache/tools:/cache" \
  ghcr.io/esphome/esphome:2026.9.0 compile esphome/desiccant-dryer-c6.yaml 2>&1 | tee .ci-cache/c6-compile.log | tail -5
```

Expected: the log ends with `INFO Successfully compiled program.`

- [ ] **Step 2: If it failed, only these corrections are in scope**

- The log names one of the seven `CONFIG_…` options in `board-c6.yaml` as unknown or out of range for the ESP32-C6: delete that one line from `board-c6.yaml`, add one sentence to the comment above the block saying which option the C6 does not take, and rerun Step 1. Do not touch `board-s2.yaml`.
- Anything else (a component that does not build for the C6, an image too large for its partition, a board id the 2026.9.0 image does not know): stop and report the last 60 lines of `.ci-cache/c6-compile.log`. Do not work around it.

- [ ] **Step 3: Package the real image**

```bash
ls -la esphome/.esphome/build/desiccant-dryer-c6/build/firmware.ota.bin esphome/.esphome/build/desiccant-dryer-c6/build/firmware.factory.bin
od -An -tx1 -j12 -N2 esphome/.esphome/build/desiccant-dryer-c6/build/firmware.ota.bin
scripts/make-manifest.sh 0.0.0 .ci-cache/site "" esp32c6=esphome/.esphome/build/desiccant-dryer-c6/build
```

Expected: both files exist; `od` prints ` 0d 00`; the script prints `ESP32-C6: desiccant-dryer-0.0.0-esp32c6.ota.bin md5 …` and `wrote .ci-cache/site/manifest.json`.

If `od` prints other bytes, the constant in the script is wrong, not the image. Read `ESP_CHIP_ID_ESP32C6` in `esp_app_format.h` (`find .ci-cache/tools -name esp_app_format.h`), then change `id="0d00"` in `scripts/make-manifest.sh` and the `'\x0d\x00'` stand-in bytes in `tests/make_manifest_test.sh` together, rerun `bash tests/make_manifest_test.sh` and this step.

If the files are not in that directory, find them (`find esphome/.esphome/build/desiccant-dryer-c6 -name 'firmware.ota.bin'`) and stop: the path in `build.yml`, `release.yml` and `docs/releasing.md` has to match what the image really does, for both chips.

- [ ] **Step 4: Commit, if anything changed**

```bash
git status --short
git add -u && git commit -m "Correct the ESP32-C6 build settings found by the first compile"
```

Skip the commit when `git status --short` prints nothing.

---

### Task 7: C6 source documents and the pinout record

**Files:**
- Create: `docs/datasheets/mcu/sparkfun-esp32-c6-thing-plus.sch`, `docs/datasheets/mcu/sparkfun-esp32-c6-thing-plus.brd`, `docs/datasheets/mcu/espressif-esp32-c6-datasheet.pdf`, `docs/datasheets/mcu/espressif-esp32-c6-wroom-1-datasheet.pdf`
- Modify: `docs/datasheets/README.md`, `docs/pinout-verification.md`

**Interfaces:**
- Consumes: nothing.
- Produces: the anchor `docs/pinout-verification.md#thing-plus-esp32-c6-dev-22924`, which Tasks 8 to 10 link to.

- [ ] **Step 1: Fetch the four files at the pinned commit and check them**

```bash
C=fb7352f770b885fa9d5767bd25a168b90a11d4e5
B=https://raw.githubusercontent.com/sparkfun/SparkFun_Thing_Plus_ESP32_C6/$C
curl -fsSL -o docs/datasheets/mcu/sparkfun-esp32-c6-thing-plus.sch "$B/Hardware/Thing_Plus_ESP32_C6.sch"
curl -fsSL -o docs/datasheets/mcu/sparkfun-esp32-c6-thing-plus.brd "$B/Hardware/Thing_Plus_ESP32_C6.brd"
curl -fsSL -o docs/datasheets/mcu/espressif-esp32-c6-datasheet.pdf "$B/Documents/ESP32-C6-Datasheet.pdf"
curl -fsSL -o docs/datasheets/mcu/espressif-esp32-c6-wroom-1-datasheet.pdf "$B/Documents/ESP32-C6-WROOM-1-Datasheet.pdf"
shasum -a 256 docs/datasheets/mcu/*c6* | cut -c1-16,65-
```

Expected:

```text
1338481686672951  docs/datasheets/mcu/espressif-esp32-c6-datasheet.pdf
b0ae5c4c27f051bb  docs/datasheets/mcu/espressif-esp32-c6-wroom-1-datasheet.pdf
24b289329c3f9c98  docs/datasheets/mcu/sparkfun-esp32-c6-thing-plus.brd
aa89ff067b61ef02  docs/datasheets/mcu/sparkfun-esp32-c6-thing-plus.sch
```

A different hash means the wrong file: do not commit it.

- [ ] **Step 2: Index them**

The date in the text is the day these hashes were taken; leave it as written.

In `docs/datasheets/README.md`, replace

```text
retrieved on 2026-09-15 from the source in the table, except the SEFUSE
thermal-cutoff catalogue (2026-09-16); the SHA-256 prefix is there to tell
```

with

```text
retrieved on 2026-09-15 from the source in the table, except the SEFUSE
thermal-cutoff catalogue (2026-09-16) and the four ESP32-C6 files
(2026-10-12, SparkFun's repository at commit `fb7352f`, which has no
`LICENSE.md` of its own; its README calls the hardware open source and
SparkFun's standing hardware licence is the CC BY-SA 4.0 in
`mcu/SPARKFUN-LICENSE.md`); the SHA-256 prefix is there to tell
```

In `docs/datasheets/README.md`, directly after the one line that begins `| [mcu/espressif-esp32-s2-datasheet.pdf]`, insert

```text
| [mcu/sparkfun-esp32-c6-thing-plus.brd](mcu/sparkfun-esp32-c6-thing-plus.brd) | SparkFun Thing Plus ESP32-C6 (DEV-22924), the second supported controller board | Eagle board file (CC BY-SA 4.0, see SPARKFUN-LICENSE.md) | [link](https://github.com/sparkfun/SparkFun_Thing_Plus_ESP32_C6/blob/fb7352f770b885fa9d5767bd25a168b90a11d4e5/Hardware/Thing_Plus_ESP32_C6.brd) |  | `24b289329c3f9c98` | Outline is 22.86 × 58.42 mm; header pads at the same coordinates as the S2 board's (12-pin from 1.27, 24.13; 16-pin from 21.59, 13.97) |
| [mcu/sparkfun-esp32-c6-thing-plus.sch](mcu/sparkfun-esp32-c6-thing-plus.sch) | SparkFun Thing Plus ESP32-C6 | Eagle schematic (CC BY-SA 4.0) | [link](https://github.com/sparkfun/SparkFun_Thing_Plus_ESP32_C6/blob/fb7352f770b885fa9d5767bd25a168b90a11d4e5/Hardware/Thing_Plus_ESP32_C6.sch) |  | `aa89ff067b61ef02` | Nets behind pinout-verification.md: header J1; jumpers ALRT, SD_DET, LP, RGB, I2C; R1 100 kΩ on IO8; R11 100 kΩ on RESET; V_USB → D3 → RT9080 → 3.3V; USB D−/D+ straight to IO12/IO13 |
| [mcu/espressif-esp32-c6-wroom-1-datasheet.pdf](mcu/espressif-esp32-c6-wroom-1-datasheet.pdf) | ESP32-C6-WROOM-1 module on the C6 Thing Plus | Espressif datasheet, pre-release v0.6, SparkFun's copy | [link](https://github.com/sparkfun/SparkFun_Thing_Plus_ESP32_C6/blob/fb7352f770b885fa9d5767bd25a168b90a11d4e5/Documents/ESP32-C6-WROOM-1-Datasheet.pdf) | 37 | `b0ae5c4c27f051bb` | Module pin layout and pin descriptions |
| [mcu/espressif-esp32-c6-datasheet.pdf](mcu/espressif-esp32-c6-datasheet.pdf) | ESP32-C6 chip | Espressif datasheet, pre-release v0.5, SparkFun's copy | [link](https://github.com/sparkfun/SparkFun_Thing_Plus_ESP32_C6/blob/fb7352f770b885fa9d5767bd25a168b90a11d4e5/Documents/ESP32-C6-Datasheet.pdf) | 69 | `1338481686672951` | Section 2.6, strapping pins: Table 2-14 boot mode (GPIO8 low with GPIO9 low is invalid), Table 2-13 MTMS/MTDI |
```

- [ ] **Step 3: Record the C6 pinout**

In `docs/pinout-verification.md`, replace

```text
# Pinout verification — SparkFun ESP32-S2 Thing Plus (WRL-17743)
```

with

```text
# Pinout verification — SparkFun Thing Plus boards

Two boards fit the main board's sockets: the ESP32-S2 Thing Plus
(WRL-17743) and the Thing Plus ESP32-C6 (DEV-22924). The main board is
wired by header position. The GPIO behind each position differs between
the two and lives in `esphome/packages/board-s2.yaml` and
`esphome/packages/board-c6.yaml`. Everything down to "Action items for the
software side" is about the S2; the C6 has
[its own section](#thing-plus-esp32-c6-dev-22924) after that.

## ESP32-S2 Thing Plus (WRL-17743)
```

In `docs/pinout-verification.md`, replace

```text
All GPIO numbers in `esphome/packages/hw-real.yaml` (sensors), `base.yaml`
(outputs) and `display-st7789.yaml` (display), and in the wiring diagram
[breadboard.svg](breadboard.svg), are correct. No wiring changes.
```

with

```text
All GPIO numbers in `esphome/packages/board-s2.yaml` (the pin table the
sensor, output and display packages take theirs from), and in the wiring
diagram [breadboard.svg](breadboard.svg), are correct. No wiring changes.
```

In `docs/pinout-verification.md`, replace

```text
- Board ID: none. `board: sparkfun_esp32s2_thing_plus` in
  `packages/platform-esp32.yaml` compiles in CI and runs on the bench board.
```

with

```text
- Board ID: none. `board: sparkfun_esp32s2_thing_plus` in
  `packages/board-s2.yaml` compiles in CI and runs on the bench board.
```

Append to the end of `docs/pinout-verification.md` (keep one blank line before it)

```markdown
## Thing Plus ESP32-C6 (DEV-22924)

Date: 2026-10-08, by parsing the schematic's nets (J1, the jumpers, R1, R5,
R11, R14) against the module's IO pins, and the `.brd` for the header
positions. Nothing in this section has been checked on a physical board
yet; the bench items are in
[hardware-bringup.md](hardware-bringup.md#8-esp32-c6-board).

### Source of truth

`Hardware/Thing_Plus_ESP32_C6.sch` and `.brd` from SparkFun's GitHub
hardware repo (github.com/sparkfun/SparkFun_Thing_Plus_ESP32_C6, commit
`fb7352f`), kept in [datasheets/mcu/](datasheets/mcu/). J1 is both headers
in one part. Chip-level constraints are from Espressif's ESP32-C6 datasheet
(pre-release v0.5, same folder).

### Result

The C6 board fits the S2's sockets with no main-board change. In both
`.brd` files the 12-pin header runs from (1.27, 24.13) to (1.27, 52.07) mm
and the 16-pin header from (21.59, 13.97) to (21.59, 52.07) mm, with USB-C
at the y = 0 end. The C6 board is 58.42 mm long against 64.77 mm, shorter
at the antenna end. The power positions carry the same nets. The GPIO
behind each signal position is different and is in
`esphome/packages/board-c6.yaml`.

### Headers, pin by pin (from the schematic)

16-pin header:

| Pos | Silkscreen | GPIO | Our use | Also on the net |
|---|---|---|---|---|
| 1 | RESET | — | — | ESP EN: R11 100 kΩ to 3.3 V, C5 0.1 µF, RESET button |
| 2 | 3.3V | — | top 3.3 V rail | |
| 3 | AREF/NC | — | — | RGB LED data out, through jumper RGB (open as delivered) |
| 4 | GND | — | top GND rail | |
| 5 | A0 | 0 | display backlight (PWM) | |
| 6 | A1 | 1 | — | |
| 7 | A2 | 2 | — | |
| 8 | A3 | 3 | display RST | |
| 9 | A4 | 4 | display DC | strapping pin (MTMS) |
| 10 | A5 | 5 | display CS | strapping pin (MTDI) |
| 11 | SCK | 19 | SPI clock | µSD slot CLK |
| 12 | PICO | 20 | SPI data to display | µSD slot CMD |
| 13 | POCI | 21 | 1-wire bus (3× DS18B20) | µSD slot DAT0 |
| 14 | RX | 17 | — | UART0 RX |
| 15 | TX | 16 | — | UART0 TX; the ROM can print here at boot |
| 16 | FREEBIE | 9 | — | BOOT strap, BOOT button to GND |

12-pin header:

| Pos | Silkscreen | GPIO | Our use | Also on the net |
|---|---|---|---|---|
| 1 | V_BATT | — | — | LiPo connector, charger, gauge |
| 2 | EN | — | — | RT9080 regulator enable, R8 100 kΩ; not a reset |
| 3 | V_USB | — | 5 V in from buck | USB-C VBUS, the same net |
| 4 | GPIO0 | 18 | heater A relay | µSD slot DAT3/CS |
| 5 | GPIO1 | 22 | heater B relay | µSD card detect and R5 100 kΩ, through jumper SD_DET |
| 6 | GPIO2 | 11 | valve A | MAX17048 ALRT and R14 100 kΩ, through jumper ALRT |
| 7 | GPIO3 | 10 | valve B | |
| 8 | GPIO4 | 8 | case fan | strapping pin; R1 100 kΩ to 3.3 V |
| 9 | GPIO5 | 23 | — | WS2812 RGB LED data in |
| 10 | GPIO6 | 15 | — | strapping pin; one pad of jumper LP, not connected as delivered |
| 11 | SCL | 7 | I2C (also on Qwiic) | MAX17048, 2.2 kΩ pull-up |
| 12 | SDA | 6 | I2C (also on Qwiic) | MAX17048, 2.2 kΩ pull-up |

Qwiic (J4): GND, 3.3 V, SDA=GPIO6, SCL=GPIO7. SHT45 plugs in here; the
gauge on the same bus answers at 0x36, the SHT45 at 0x44.

### Things the schematic clears up

1. **The 12-pin silkscreen says GPIO0 to GPIO6, and those are not chip GPIO
   numbers.** They are SparkFun's labels for the header positions: "GPIO0"
   is IO18, "GPIO4" is IO8. Valve A, valve B and the fan keep the numbers
   they have on the S2 (11, 10, 8); nothing else does.
2. **Valve A's pin is also the battery gauge's alert.** IO11 reaches the
   MAX17048's open-drain ALRT pin and R14 (100 kΩ to 3.3 V) through jumper
   ALRT, closed as delivered. An asserted alert would short the pin to
   ground while the firmware drives valve A on. **Cut ALRT.**
3. **Heater B's pin is also the card-detect switch.** IO22 reaches the µSD
   socket's detect contact and R5 (100 kΩ to the switched 3.3 V rail) through
   jumper SD_DET, closed as delivered. **Cut SD_DET.**
4. **The µSD slot shares four of our lines**: heater A (IO18, the card's
   CS), SPI clock and data (IO19, IO20) and the 1-wire bus (IO21, the
   card's data out). No resistor sits on any of them. A card in the slot
   would be selected whenever heater A is off, see the display's SPI
   traffic, and could drive the 1-wire line. **The slot stays empty.**
5. **The fan's pin is a boot strap with a pull-up.** IO8 has R1, 100 kΩ to
   3.3 V. Against the fan channel's 100 Ω + 10 kΩ gate pulldown that is
   about 0.3 V at reset: the fan stays off, and the strap reads low. The
   constraints below say what that rules out.
6. **16-pin 16 is the BOOT strap** (IO9, BOOT button to ground), where the
   S2 has a spare GPIO3. Nothing may be wired to it. The same goes for
   16-pin 15 (UART0 TX), 12-pin 10 (IO15, a strap) and 12-pin 9 (the RGB
   LED's data). All four are unused in our wiring.
7. **RESET is pulled up by 100 kΩ**, ten times weaker than the S2's 10 kΩ,
   with the same 0.1 µF to ground: 1 µA of leakage on the pin drops 0.1 V.
   There is no auto-reset transistor; USB goes straight to the chip.
8. **There is no LED on any header pin.** The only LED the firmware could
   drive is the WS2812 on IO23, which is not used. Nothing on the board
   lights with heater A.
9. **The 12-pin USB pin is the USB-C connector's VBUS**, as on the S2 (net
   `V_USB`, then Schottky D3 towards the RT9080's input). The same rule
   holds: never the 5 V rail and a USB cable together.
10. **I2C pull-ups are on the board** (2.2 kΩ each through jumper I2C,
    closed as delivered); the S2 board has none.

### Chip-level constraints (datasheet)

- GPIO12/13 are USB D−/D+ and go straight to the USB-C connector: never
  assign. Flashing and the log use the chip's own USB-Serial-JTAG.
- GPIO24 to 30 belong to the module's flash.
- Strapping pins: GPIO8 and GPIO9 (boot mode), GPIO4 and GPIO5 (MTMS and
  MTDI: SDIO clock edges only), GPIO15 (JTAG source).
- Boot mode, datasheet Table 2-14: GPIO9 high boots from flash whatever
  GPIO8 is; GPIO9 low with GPIO8 high is download mode; **GPIO9 low with
  GPIO8 low is invalid** ("triggers unexpected behavior and should be
  avoided"). Seated in the main board, GPIO8 is held low by the fan's gate
  pulldown. A normal boot is unaffected, but download mode must not be
  entered there: flash the board out of its socket. Whether the
  USB-Serial-JTAG's own reset-to-download path runs into this is a bench
  item.
- The display's SPI pins (19, 20) reach the SPI peripheral through the GPIO
  matrix; on the S2, 35 and 36 are the peripheral's own pins. 40 MHz on
  real glass is a bench item.

### Action items for the software side

- Pin numbers: `esphome/packages/board-c6.yaml`, asserted in CI by the
  T-J12C lint case.
- Board ID: `board: sparkfun_esp32c6_thing_plus`, `variant: esp32c6`, in
  the same file.
- GPIO4, 5 and 8 carry `ignore_strapping_warning: true` there, each with
  its reason.
```

- [ ] **Step 4: Check the record against the schematic it cites**

```bash
python3 - <<'EOF'
import xml.etree.ElementTree as ET
r = ET.parse('docs/datasheets/mcu/sparkfun-esp32-c6-thing-plus.sch').getroot()
net = {pr.get('pin'): n.get('name') for n in r.iter('net') for pr in n.iter('pinref') if pr.get('part') == 'J1'}
want = {'GPIO0': 'IO18/!CS!', 'GPIO1': 'IO22/!SD_DET!', 'GPIO2': 'IO11/!ALRT!', 'GPIO3': 'IO10', 'GPIO4': 'IO8',
        'SDA': 'IO6/SDA', 'SCL': 'IO7/SCL', 'A0': 'IO0', 'A3': 'IO3', 'A4': 'IO4', 'A5': 'IO5',
        'SCK': 'IO19/SCK', 'PICO': 'IO20/PICO', 'POCI': 'IO21/POCI', 'FREEBIE': 'IO9/BOOT'}
bad = {k: (v, net.get(k)) for k, v in want.items() if net.get(k) != v}
print('schematic agrees with the pin table' if not bad else bad)
EOF
```

Expected: `schematic agrees with the pin table`. These are the nets behind every row of `board-c6.yaml`'s table and the 12-pin table just written.

- [ ] **Step 5: Commit**

```bash
git add docs/datasheets docs/pinout-verification.md
git commit -m "Record the ESP32-C6 Thing Plus pinout from SparkFun's schematic"
```

---

### Task 8: Hardware, bring-up and continuity docs

**Files:**
- Modify: `docs/hardware.md`, `docs/hardware-bringup.md`, `docs/board-continuity-check.md`

**Interfaces:**
- Consumes: the anchor `pinout-verification.md#thing-plus-esp32-c6-dev-22924` (Task 7).
- Produces: the anchors `hardware.md#fitting-an-esp32-c6-thing-plus` and `hardware-bringup.md#8-esp32-c6-board`, which Tasks 9 and 10 and the files above link to.

- [ ] **Step 1: hardware.md**

In `docs/hardware.md`, replace

```text
| MCU | SparkFun ESP32-S2 Thing Plus (WRL-17743) | Feather footprint, Qwiic, CP2102 |
```

with

```text
| MCU | SparkFun ESP32-S2 Thing Plus (WRL-17743), or SparkFun Thing Plus ESP32-C6 (DEV-22924) | Same sockets and wiring for either. The C6 needs two jumpers cut first: [Fitting an ESP32-C6 Thing Plus](#fitting-an-esp32-c6-thing-plus) |
```

In `docs/hardware.md`, replace

```text
## Board pinout used

From SparkFun's Eagle schematic (J4 = 16-pin, J2 = 12-pin); pin-by-pin
tables and sources in [pinout-verification.md](pinout-verification.md).
```

with

```text
## Board pinout used

The GPIO numbers in this document are the ESP32-S2 board's. The wiring is
by header position and is the same for the ESP32-C6 board, whose numbers
are in the table under
[Fitting an ESP32-C6 Thing Plus](#fitting-an-esp32-c6-thing-plus).

From SparkFun's Eagle schematic (J4 = 16-pin, J2 = 12-pin); pin-by-pin
tables and sources in [pinout-verification.md](pinout-verification.md).
```

In `docs/hardware.md`, replace

```text
## Driver stages
```

with

```text
## Fitting an ESP32-C6 Thing Plus

The SparkFun Thing Plus ESP32-C6 (DEV-22924) goes in the same two sockets
as the S2 board, with no change to either protoboard. It runs its own
firmware image (`esphome/desiccant-dryer-c6.yaml`); the published manifest
carries both images and each board takes its own. The source and the
reasoning for every line here are in
[pinout-verification.md](pinout-verification.md#thing-plus-esp32-c6-dev-22924).
None of it has been run on a C6 yet.

Before the board goes in a socket:

1. **Cut jumpers ALRT and SD_DET** on the back of the C6 board (a knife
   through the trace between the two pads; a solder blob restores it).
   ALRT ties valve A's pin to the battery gauge's alert output. SD_DET ties
   heater B's pin to the card-detect switch.
2. **Check both cuts with a meter, board unpowered:** no continuity across
   either jumper's two pads. For ALRT there is a second reading: 12-pin 6
   to 3V3 reads about 100 kΩ before the cut and open after.
3. **Leave the µSD slot empty** and tape over it. The slot shares the
   display's SPI lines, the 1-wire bus and heater A's line.
4. Leave the other jumpers (LP, I2C, RGB, CHG, PWR, SHLD, MEAS) as
   delivered, and solder the headers on as for the S2.
5. **Flash it before seating it**, over USB-C, from the published manifest
   (docs/releasing.md). Seated, the fan's gate pulldown holds the chip's
   GPIO8 boot strap low, and download mode with GPIO8 low is not a valid
   boot mode for the C6. The JP-USB rule is the same as for the S2: never
   a USB cable and the buck's 5 V together.

The same header positions, with each board's GPIO:

| Position | Function | S2 GPIO | C6 GPIO |
|---|---|---|---|
| 16-pin 5 | display backlight | 17 | 0 |
| 16-pin 8 | display RST | 9 | 3 |
| 16-pin 9 | display DC | 7 | 4 |
| 16-pin 10 | display CS | 5 | 5 |
| 16-pin 11 | SPI clock | 36 | 19 |
| 16-pin 12 | SPI data | 35 | 20 |
| 16-pin 13 | 1-wire | 37 | 21 |
| 12-pin 4 | heater A | 13 | 18 |
| 12-pin 5 | heater B | 12 | 22 |
| 12-pin 6 | valve A | 11 | 11 |
| 12-pin 7 | valve B | 10 | 10 |
| 12-pin 8 | case fan | 8 | 8 |
| 12-pin 11 / 12, Qwiic | I2C SCL / SDA | 2 / 1 | 7 / 6 |

Differences that show up in use:

- The C6 board's 12-pin silkscreen reads GPIO0 to GPIO6. Those are header
  labels, not the chip's GPIO numbers.
- No LED lights with heater A: the S2's blue LED on GPIO13 has no
  counterpart.
- The USB port is the chip's own (`/dev/cu.usbmodem*` on macOS), not a
  CP2102.
- RESET is pulled up by 100 kΩ where the S2 has 10 kΩ, so the pin
  tolerates a tenth of the leakage. Keep flux off that end of the socket.
- Four positions the wiring leaves empty must stay empty, because the C6
  gives them a job: 16-pin 16 (BOOT), 16-pin 15 (UART0 TX), 12-pin 10
  (a boot strap) and 12-pin 9 (the RGB LED).

## Driver stages
```

In `docs/hardware.md`, replace

```text
![Breadboard layout](breadboard.svg)
```

with

```text
![Breadboard layout](breadboard.svg)

GPIO labels in the drawing are the ESP32-S2 board's. The wiring is by
header position and is the same for the ESP32-C6 board
([table](#fitting-an-esp32-c6-thing-plus)).
```

In `docs/hardware.md`, replace

```text
![Protoboard layout](board-layout.svg)
```

with

```text
![Protoboard layout](board-layout.svg)

GPIO labels in the drawing are the ESP32-S2 board's. The wiring is by
header position and is the same for the ESP32-C6 board
([table](#fitting-an-esp32-c6-thing-plus)).
```

- [ ] **Step 2: hardware-bringup.md**

In `docs/hardware-bringup.md`, replace

```text
published manifest instead. It goes on last,
as its own step (section 7).
```

with

```text
published manifest instead. It goes on last,
as its own step (section 7).

An ESP32-C6 board uses `esphome/desiccant-dryer-hw-test-c6.yaml` wherever
this page says `desiccant-dryer-hw-test.yaml`, and has steps of its own in
[section 8](#8-esp32-c6-board). GPIO numbers on this page are the S2's.
```

Append to the end of `docs/hardware-bringup.md` (keep one blank line before it)

````markdown
## 8. ESP32-C6 board

For a SparkFun Thing Plus ESP32-C6 (DEV-22924). Nothing in this section had
been run on a C6 when it was written (2026-10-12). Record what you see
under each step, including a step that fails.

Preparation, before the board goes near a socket: cut ALRT and SD_DET,
check the cuts with a meter and keep the µSD slot empty
([hardware.md](hardware.md#fitting-an-esp32-c6-thing-plus)).

- [ ] **8.1 Flash the test build, board out of the socket.** Plug the
  USB-C cable straight into the board; the port is `/dev/cu.usbmodem*`.

  ```bash
  ls /dev/cu.usbmodem*
  esphome run --device /dev/cu.usbmodemXXXX esphome/desiccant-dryer-hw-test-c6.yaml
  ```

  Pass: it flashes without the BOOT button, the log appears on the same
  port, and the board joins WiFi as `desiccant-dryer-hw-test-c6`.
- [ ] **8.2 Seat it and power the main board** (JP-USB fitted, no USB
  cable). Pass: the panel shows the normal screen with no torn or shifted
  areas (40 MHz SPI through the C6's GPIO matrix is untested); the SHT45
  and all three DS18B20s read; no relay clicks, no valve pulls in and the
  fan stays off at power-up.
- [ ] **8.3 Sections 3 to 5 of this page**, on the C6 test build. Pass: as
  written there, except that no LED lights with heater A.
- [ ] **8.4 One USB flash attempt while seated.** Pull JP-USB first, plug
  in USB-C and run the 8.1 command again. Record whether it flashes: the
  fan's gate pulldown holds the GPIO8 boot strap low, which the datasheet
  calls an invalid combination with download mode. Either result is
  useful; write it into
  [pinout-verification.md](pinout-verification.md#thing-plus-esp32-c6-dev-22924)
  and hardware.md.
- [ ] **8.5 Release image.** After the first release that carries a C6
  image (1.3.0) is published: flash it from the manifest with
  web.esphome.io, board out of the socket; give it WiFi over Improv; reboot
  it once. Pass: `Firmware Version` reads the release, the `Firmware`
  update entity reads up to date, and Improv worked over the native USB
  port. Record `Free Heap`, `Largest Free Block` and, if the log shows a
  `display took a long time for an operation` warning, its figure.
- [ ] **8.6 The unit updates itself.** After the next release (a
  version-only one will do). Pass: the C6 unit installs it from the
  `Firmware` entity and comes back on the new version with reset reason
  "Reboot request from http_request.update".
- [ ] **8.7 An S2 unit still updates.** Pass: an S2 unit on 1.2.4 offers
  and installs 1.3.0 from the same manifest.
````

- [ ] **Step 3: board-continuity-check.md**

In `docs/board-continuity-check.md`, replace

```text
pulled low, it turns the whole 3.3 V rail off. 16-pin #8 "RES" is the
display's reset on GPIO9, not the ESP's.
```

with

```text
pulled low, it turns the whole 3.3 V rail off. 16-pin #8 "RES" is the
display's reset on GPIO9, not the ESP's.

The numbers in the map are the ESP32-S2 board's GPIOs. The checks on this
page go by socket position and hold for the ESP32-C6 board too; its
numbers are in [hardware.md](hardware.md#fitting-an-esp32-c6-thing-plus).
```

In `docs/board-continuity-check.md`, directly after the one line that begins `- [ ] BAT (12-pin #1) to anything: open`, insert

```text
- [ ] 16-pin #15 and #16, 12-pin #9 and #10, each to GND, 3V3, the 5 V bus and its neighbours: open. Nothing is wired to these four; on an ESP32-C6 board they are UART0 TX, the BOOT strap, the RGB LED's data and a boot strap
```

- [ ] **Step 4: Check the links land**

```bash
grep -c "^## Fitting an ESP32-C6 Thing Plus$" docs/hardware.md
grep -c "^## 8. ESP32-C6 board$" docs/hardware-bringup.md
grep -c "^## Thing Plus ESP32-C6 (DEV-22924)$" docs/pinout-verification.md
sed -n '/^## 8. ESP32-C6 board$/,$p' docs/hardware-bringup.md | grep -c "VMD-08\|Azco\|[0-9]\{1,3\}\.[0-9]\{1,3\}\.[0-9]\{1,3\}\.[0-9]\{1,3\}"
```

Expected: `1`, `1`, `1`, then `0` (no device address and no product branding in the new section).

- [ ] **Step 5: Commit**

```bash
git add docs/hardware.md docs/hardware-bringup.md docs/board-continuity-check.md
git commit -m "Document fitting and bringing up an ESP32-C6 board"
```

---

### Task 9: Failure modes, tests and the inspection checklist

The catalogue has rules that a script enforces: IDs are permanent and added at the end of a category, every row is in exactly one issue and one test, and the count tables must agree with the rows. Six rows are added.

**Files:**
- Modify: `docs/failure-modes.md`, `docs/verification-plan.md`, `docs/inspection-checklist.md`

**Interfaces:**
- Consumes: cases `T-J12` and `T-J12C` (Tasks 1 and 3); the doc anchors from Tasks 7 and 8.
- Produces: catalogue rows `D-18`, `F-21`, `G-17`, `H-21`, `H-22`, `J-12`; test rows `T-D18`, `T-F21`, `T-G17`, `T-H21`, `T-H22`, `T-J12`, `T-J12C`.

- [ ] **Step 1: See the script pass before the edit**

```bash
python3 scripts/failure-modes-report.py .ci-cache/failure-modes.html
```

Expected: `214 items, {'P0': 32, 'P1': 74, 'P2': 68, 'P3': 30, 'P4': 10}, 189 tests -> .ci-cache/failure-modes.html`

- [ ] **Step 2: failure-modes.md: intro, six rows, contents, issues, roll-up**

Each new row goes directly after the last row of its category. A row is one line and must end ` |  |`.

In `docs/failure-modes.md`, replace

```text
Azco VMD-08 dryer: an ESP32-S2, two 120 VAC pack heaters on Songle relays,
```

with

```text
Azco VMD-08 dryer: an ESP32-S2 or ESP32-C6 Thing Plus, two 120 VAC pack heaters on Songle relays,
```

In `docs/failure-modes.md`, replace

```text
and Prusa firmware.
```

with

```text
and Prusa firmware.

Rows that name GPIO numbers use the ESP32-S2 board's. On an ESP32-C6 board
the same header positions carry the numbers in
`docs/pinout-verification.md`. The rows that exist only because of the C6
board say so.
```

In `docs/failure-modes.md`, directly after the one line that begins `| D-17 |`, insert

```text
| D-18 | ESP32-C6 board fitted with its ALRT jumper still closed: the MAX17048 gauge's open-drain alert shares GPIO11 with valve A, so an asserted alert shorts the pin to ground while the firmware drives the valve on; valve A stays shut and the output is overloaded. Pass: no continuity across the ALRT jumper's pads | 🟠 P1 | WIRE | inspect |  |
```

In `docs/failure-modes.md`, directly after the one line that begins `| F-20 |`, insert

```text
| F-21 | The ESP32-C6 board pulls RESET up with 100 kΩ where the S2 has 10 kΩ, so a tenth of the leakage on the RESET pin (flux residue, a damp socket) holds the chip in reset or resets it at random; every output goes off and the dryer stops. Pass: RESET measures at the 3.3 V rail, not below it, with the board seated and powered | 🟡 P2 | HW | bench |  |
```

In `docs/failure-modes.md`, directly after the one line that begins `| G-16 |`, insert

```text
| G-17 | ESP32-C6 board with a µSD card in its slot, or its SD_DET jumper still closed: the slot shares the display's SPI lines, the 1-wire bus and heater A's line, and the detect switch shares heater B's, so a card can corrupt probe readings and load both heater pins. Pass: slot empty and taped over, no continuity across the SD_DET jumper's pads | 🟡 P2 | WIRE | inspect |  |
```

In `docs/failure-modes.md`, directly after the one line that begins `| H-20 |`, insert

```text
| H-21 | On an ESP32-C6 board the fan pin (GPIO8) is a boot strap and the fan's 10 kΩ gate pulldown holds it low, which the datasheet calls an invalid combination with download mode; a USB flash with the board seated may fail or misbehave. Pass: the result of one seated flash attempt is recorded and the docs say which way to flash | 🔵 P3 | HW | bench |  |
| H-22 | An image for the other chip is flashed by hand over USB during a recovery (the S2 file onto a C6 board or the reverse). Pass: esptool refuses the mismatch and the board still boots what it had | 🔵 P3 | OPS | bench |  |
```

In `docs/failure-modes.md`, directly after the one line that begins `| J-11 |`, insert

```text
| J-12 | A GPIO number in `board-s2.yaml` or `board-c6.yaml` is wrong for its chip, or a selector includes the other chip's board package; the firmware drives a different header position from the one wired, such as a heater relay where a valve is expected | 🔴 P0 | CFG | inspect |  |
```

In `docs/failure-modes.md`, replace

```text
| [D. Valves and airflow](#d-valves-and-airflow) |  | 10 | 5 | 2 |  | 17 |
```

with

```text
| [D. Valves and airflow](#d-valves-and-airflow) |  | 11 | 5 | 2 |  | 18 |
```

In `docs/failure-modes.md`, replace

```text
| [F. Power supplies and rails](#f-power-supplies-and-rails) | 2 | 9 | 8 | 1 |  | 20 |
```

with

```text
| [F. Power supplies and rails](#f-power-supplies-and-rails) | 2 | 9 | 9 | 1 |  | 21 |
```

In `docs/failure-modes.md`, replace

```text
| [G. Wiring, connectors, mechanical, environmental](#g-wiring-connectors-mechanical-environmental) | 4 | 7 | 4 | 1 |  | 16 |
```

with

```text
| [G. Wiring, connectors, mechanical, environmental](#g-wiring-connectors-mechanical-environmental) | 4 | 7 | 5 | 1 |  | 17 |
```

In `docs/failure-modes.md`, replace

```text
| [H. MCU and firmware runtime](#h-mcu-and-firmware-runtime) | 1 | 11 | 5 | 1 |  | 18 |
```

with

```text
| [H. MCU and firmware runtime](#h-mcu-and-firmware-runtime) | 1 | 11 | 5 | 3 |  | 20 |
```

In `docs/failure-modes.md`, replace

```text
| [J. Persistence and configuration](#j-persistence-and-configuration) | 4 | 1 | 4 | 1 |  | 10 |
```

with

```text
| [J. Persistence and configuration](#j-persistence-and-configuration) | 5 | 1 | 4 | 1 |  | 11 |
```

In `docs/failure-modes.md`, replace

```text
| G-01, G-06, G-08, G-11 | P0 |
```

with

```text
| G-01, G-06, G-08, G-11, H-21 | P0 |
```

In `docs/failure-modes.md`, replace

```text
| F-11, F-12, F-14, F-15, F-16 | P1 |
```

with

```text
| F-11, F-12, F-14, F-15, F-16, F-21 | P1 |
```

In `docs/failure-modes.md`, replace

```text
| H-02, H-07, H-08, H-12, H-16, H-19, H-20 | P1 |
```

with

```text
| H-02, H-07, H-08, H-12, H-16, H-19, H-20, H-22 | P1 |
```

In `docs/failure-modes.md`, replace

```text
| G-02, G-03, G-04, G-15, F-13, F-19 | P1 |
```

with

```text
| G-02, G-03, G-04, G-15, F-13, F-19, D-18, G-17 | P1 |
```

In `docs/failure-modes.md`, replace

```text
| J-02, J-03, J-04, J-05, J-06, J-07, J-11 | P0 |
```

with

```text
| J-02, J-03, J-04, J-05, J-06, J-07, J-11, J-12 | P0 |
```

In `docs/failure-modes.md`, replace

```text
| P0 | 32 |
```

with

```text
| P0 | 33 |
```

In `docs/failure-modes.md`, replace

```text
| P1 | 74 |
```

with

```text
| P1 | 75 |
```

In `docs/failure-modes.md`, replace

```text
| P2 | 68 |
```

with

```text
| P2 | 70 |
```

In `docs/failure-modes.md`, replace

```text
| P3 | 30 |
```

with

```text
| P3 | 32 |
```

- [ ] **Step 3: verification-plan.md: the rule, seven test rows, one widened row**

In `docs/verification-plan.md`, replace

```text
  never reused or renumbered. A trailing letter (`T-K01L`) is a second test
  of the same row under another harness — a `ci-lint` check beside a `host`
  case — and is the only way one row appears in two tests' Covers.
```

with

```text
  never reused or renumbered. A trailing letter marks a second test of the
  same row and is the only way one row appears in two tests' Covers:
  `T-K01L` is its row under another harness (a `ci-lint` check beside a
  `host` case), `T-J12C` is its row on the other board's selectors.
```

In `docs/verification-plan.md`, directly after the one line that begins `| T-D16 |`, insert

```text
| T-D18 | physical | D-18 | checklist | Stage 1 check, ESP32-C6 board only: meter across the two pads of the ALRT jumper on the back of the board, unpowered | no continuity; 12-pin 6 to 3V3 no longer reads about 100 kΩ | manual |
```

In `docs/verification-plan.md`, directly after the one line that begins `| T-F20 |`, insert

```text
| T-F21 | hil | F-21 | bench | Bench rig, ESP32-C6 board seated and powered: measure RESET (16-pin 1) to GND, and again after ten minutes | RESET reads the 3.3 V rail both times; a reading that sags is leakage the 100 kΩ pull-up cannot hold | later |
```

In `docs/verification-plan.md`, directly after the one line that begins `| T-G16 |`, insert

```text
| T-G17 | physical | G-17 | checklist | Stage 1 check, ESP32-C6 board only: look into the µSD slot and meter across the SD_DET jumper's pads | slot empty and taped over; no continuity across SD_DET | manual |
```

In `docs/verification-plan.md`, directly after the one line that begins `| T-H20 |`, insert

```text
| T-H21 | hil | H-21 | bench | ESP32-C6 board seated in the main board, JP-USB pulled: attempt one USB flash of the hw-test-c6 build | the outcome is recorded either way, and docs/hardware.md states whether a seated board can be flashed over USB | later |
| T-H22 | hil | H-22 | bench | Bench: with esptool, try to write the ESP32-S2 release image to an ESP32-C6 board, and the C6 image to an S2 board | esptool refuses both for the wrong chip and each board still boots its previous image | later |
```

In `docs/verification-plan.md`, directly after the one line that begins `| T-J11 |`, insert

```text
| T-J12 | lint | J-12 | ci-lint | Script dumps `esphome config` for `desiccant-dryer.yaml` and `desiccant-dryer-hw-test.yaml` and reads the five output switches' `pin.number` | heater A 13, heater B 12, valve A 11, valve B 10, fan 8: the ESP32-S2 table in `board-s2.yaml` | green |
| T-J12C | lint | J-12 | ci-lint | The same check on `desiccant-dryer-c6.yaml` and `desiccant-dryer-hw-test-c6.yaml` | heater A 18, heater B 22, valve A 11, valve B 10, fan 8: the ESP32-C6 table in `board-c6.yaml` | green |
```

In `docs/verification-plan.md`, replace

```text
for `desiccant-dryer.yaml` and checks the four output switches
```

with

```text
for `desiccant-dryer.yaml` and `desiccant-dryer-c6.yaml` and checks the four output switches
```

- [ ] **Step 4: inspection-checklist.md: three new items and two marks**

Every `inspect` row needs its item here: D-18 and G-17 in Stage 1, J-12 in Stage 5.

In `docs/inspection-checklist.md`, replace

```text
Sign off each stage at the bottom before moving to the next.
```

with

```text
Sign off each stage at the bottom before moving to the next.

GPIO numbers in the items are the ESP32-S2 board's. On an ESP32-C6 board
the same socket positions carry the numbers in
`docs/pinout-verification.md`. Items marked *C6 only* or *S2 only* apply to
that board alone.
```

In `docs/inspection-checklist.md`, replace

```text
- [ ] **G-02** ESP32-S2 Thing Plus seated in its 16-pin and 12-pin sockets.
```

with

```text
- [ ] **G-02** Thing Plus (ESP32-S2 or ESP32-C6) seated in its 16-pin and 12-pin sockets.
```

In `docs/inspection-checklist.md`, replace

```text
- [ ] **A-28** Blue LED on GPIO13.
```

with

```text
- [ ] **A-28** *S2 only.* Blue LED on GPIO13.
```

In `docs/inspection-checklist.md`, directly after the one line that begins `- [ ] **A-28**`, insert

```text
- [ ] **D-18** *C6 only.* ALRT jumper on the back of the ESP32-C6 board. **Pass:** cut; no continuity across its two pads, and 12-pin 6 to 3V3 reads open, not about 100 kΩ. *(meter, board unpowered and out of its socket)*
- [ ] **G-17** *C6 only.* µSD slot and SD_DET jumper on the ESP32-C6 board. **Pass:** slot empty and taped over; SD_DET cut, no continuity across its two pads. *(eyes, meter)*
```

In `docs/inspection-checklist.md`, directly after the one line that begins `- [ ] **J-02**`, insert

```text
- [ ] **J-12** Board package. **Pass:** the image is the one for the chip fitted: an ESP32-S2 board runs `desiccant-dryer.yaml` or `desiccant-dryer-hw-test.yaml` (`board-s2.yaml`), an ESP32-C6 board runs `desiccant-dryer-c6.yaml` or `desiccant-dryer-hw-test-c6.yaml` (`board-c6.yaml`); esptool or web.esphome.io names that chip before flashing, and the five output pins in the config dump match that chip's table in `docs/pinout-verification.md`. *(flasher output, config dump)*
```

- [ ] **Step 5: The script agrees**

```bash
python3 scripts/failure-modes-report.py .ci-cache/failure-modes.html
git status --short | grep -c "failure-modes.html" || true
```

Expected: `220 items, {'P0': 33, 'P1': 75, 'P2': 70, 'P3': 32, 'P4': 10}, 196 tests -> .ci-cache/failure-modes.html`, then `0`. Any other output from the script names the line that is wrong: a row that does not match the format, a row with no test, or a test citing an unknown row.

- [ ] **Step 6: Commit**

```bash
git add docs/failure-modes.md docs/verification-plan.md docs/inspection-checklist.md
git commit -m "Catalogue the ESP32-C6 failure modes and their checks"
```

---

### Task 10: Release docs, README and CLAUDE.md

**Files:**
- Modify: `docs/releasing.md`, `README.md`, `CLAUDE.md`

**Interfaces:**
- Consumes: the `make-manifest.sh` arguments (Task 4), the selector names (Task 3), the doc anchors (Tasks 7 and 8).
- Produces: nothing later tasks use.

- [ ] **Step 1: docs/releasing.md**

In `docs/releasing.md`, replace

```text
- `esphome/version.yaml` holds the semantic version. The production build
  (`packages/production.yaml`) includes it, and one selector wraps that
  build: `esphome/desiccant-dryer.yaml`, which takes the screen's drawing
  component (`components/dryer_ui`) and SVG art from this checkout. CI
  compiles it and the release workflow builds the published images from it.
```

with

```text
- `esphome/version.yaml` holds the semantic version. The production build
  (`packages/production.yaml`) includes it, and two selectors wrap that
  build, one per supported board: `esphome/desiccant-dryer.yaml` (SparkFun
  ESP32-S2 Thing Plus, `packages/board-s2.yaml`) and
  `esphome/desiccant-dryer-c6.yaml` (SparkFun Thing Plus ESP32-C6,
  `packages/board-c6.yaml`). They differ only in the board package: the
  chip, the port the log uses and the GPIO behind each header position.
  Both take the screen's drawing component (`components/dryer_ui`) and SVG
  art from this checkout. CI compiles both, and the release workflow builds
  the published images from them under one version number.
```

In `docs/releasing.md`, replace

```text
  the `.ota.bin` over HTTPS (relative path, resolved next to the manifest)
  and checks its md5.
```

with

```text
  the `.ota.bin` over HTTPS (relative path, resolved next to the manifest)
  and checks its md5. The manifest lists one build per chip (`chipFamily`
  `ESP32-S2` and `ESP32-C6`); a unit takes the one that names its own chip
  and ignores the other.
```

In `docs/releasing.md`, replace

```text
  refuses to build unless the tag equals the version in `version.yaml`,
  compiles `desiccant-dryer.yaml`, writes an esp-web-tools manifest with
  `scripts/make-manifest.sh`, attaches everything to a GitHub Release and
```

with

```text
  refuses to build unless the tag equals the version in `version.yaml`,
  compiles `desiccant-dryer.yaml` and `desiccant-dryer-c6.yaml`, writes one
  esp-web-tools manifest listing both with `scripts/make-manifest.sh`
  (which refuses an image whose header names the other chip), attaches
  everything to a GitHub Release and
```

In `docs/releasing.md`, replace

```text
1. Open https://web.esphome.io in Chrome or Edge, plug the board in over
   USB, and install the release's `.factory.bin` (from the GitHub Release)
   or point it at
   `https://jrytio.github.io/desiccant-dryer/firmware/manifest.json`.
```

with

```text
1. Open https://web.esphome.io in Chrome or Edge, plug the board in over
   USB, and point it at
   `https://jrytio.github.io/desiccant-dryer/firmware/manifest.json`, which
   picks the image for the chip it finds. To install a file from the GitHub
   Release by hand instead, take the `.factory.bin` named for the board:
   `-esp32s2` for the ESP32-S2 Thing Plus, `-esp32c6` for the Thing Plus
   ESP32-C6. An ESP32-C6 board is flashed out of its socket
   (docs/hardware.md, "Fitting an ESP32-C6 Thing Plus").
```

In `docs/releasing.md`, replace

```text
physical access, and on an installed unit it means opening the enclosure.
Weigh that before publishing a release.
```

with

```text
physical access, and on an installed unit it means opening the enclosure.
Weigh that before publishing a release.

A USB reflash needs the image for the chip that is fitted. web.esphome.io
chooses it from the manifest; by hand, use the `-esp32s2` or `-esp32c6`
factory file to match. An ESP32-C6 board comes out of its socket first.
```

In `docs/releasing.md`, replace

```text
  esphome compile esphome/desiccant-dryer.yaml && scripts/make-manifest.sh 1.2.0 esphome/.esphome/build/desiccant-dryer/build /tmp/site
```

with

```text
  esphome compile esphome/desiccant-dryer.yaml && esphome compile esphome/desiccant-dryer-c6.yaml && scripts/make-manifest.sh 1.3.0 /tmp/site "" esp32s2=esphome/.esphome/build/desiccant-dryer/build esp32c6=esphome/.esphome/build/desiccant-dryer-c6/build
```

In `docs/releasing.md`, replace

```text
- Production redraws the panel every 10 s and each redraw blocks for about
  699 ms, because the halved frame buffer makes `mipi_spi` run the writer
  twice (`packages/display-st7789.yaml` has the measurements). A fault or
```

with

```text
- Production redraws the panel every 10 s and each redraw blocks for about
  699 ms on the S2 (not yet measured on the C6), because the halved frame
  buffer makes `mipi_spi` run the writer twice
  (`packages/display-st7789.yaml` has the measurements). A fault or
```

In `docs/releasing.md`, replace

```text
  production selector includes, so override it on `desiccant-dryer.yaml`
  itself — the virtual, host, hw-test and scenarios builds have no updater
```

with

```text
  production selectors include, so override it on `desiccant-dryer.yaml`
  or `desiccant-dryer-c6.yaml` — the virtual, host, hw-test and scenarios builds have no updater
```

- [ ] **Step 2: README.md**

In `README.md`, replace

```text
ESPHome firmware for an ESP32-S2 replacement of the Azco VMD-08 desiccant
air dryer control board. Swaps packs on measured humidity and pack
```

with

```text
ESPHome firmware for an ESP32 replacement of the Azco VMD-08 desiccant
air dryer control board, on a SparkFun ESP32-S2 Thing Plus or a SparkFun
Thing Plus ESP32-C6 (same sockets and wiring, one image each). Swaps packs
on measured humidity and pack
```

In `README.md`, replace

```text
| Production | `esphome/desiccant-dryer.yaml` | SHT45 + 3× DS18B20 (`packages/hw-real.yaml`) | ESP32-S2 |
```

with

```text
| Production | `esphome/desiccant-dryer.yaml`, `esphome/desiccant-dryer-c6.yaml` | SHT45 + 3× DS18B20 (`packages/hw-real.yaml`) | ESP32-S2, ESP32-C6 |
```

In `README.md`, replace

```text
| Hardware test | `esphome/desiccant-dryer-hw-test.yaml` | Same real sensors, dev credentials and OTA | ESP32-S2 |
```

with

```text
| Hardware test | `esphome/desiccant-dryer-hw-test.yaml`, `esphome/desiccant-dryer-hw-test-c6.yaml` | Same real sensors, dev credentials and OTA | ESP32-S2, ESP32-C6 |
```

- [ ] **Step 3: CLAUDE.md**

In `CLAUDE.md`, replace

```text
- **Board: SparkFun ESP32-S2 Thing Plus (WRL-17743).** Single core, 320 KB RAM,
  no PSRAM, no Bluetooth, CP2102 UART for flashing. The full 16-bit 240x240
```

with

```text
- **Boards: SparkFun ESP32-S2 Thing Plus (WRL-17743) and SparkFun Thing
  Plus ESP32-C6 (DEV-22924)**, in the same sockets with the same wiring and
  one firmware image each (`packages/board-s2.yaml`, `packages/board-c6.yaml`).
- **The S2 board:** single core, 320 KB RAM,
  no PSRAM, no Bluetooth, CP2102 UART for flashing. The full 16-bit 240x240
```

In `CLAUDE.md`, replace

```text
  The logger must use `hardware_uart: UART0`;
  ESPHome's S2 default of USB_CDC is the unconnected native-USB pins.
```

with

```text
  The logger must use `hardware_uart: UART0`;
  ESPHome's S2 default of USB_CDC is the unconnected native-USB pins.
- **The C6 board** (ESP32-C6-WROOM-1-N16: single RISC-V core, 512 KB RAM,
  no PSRAM, the chip's own USB-Serial-JTAG, no CP2102) is supported from
  1.3.0. Before one goes in a socket its ALRT and SD_DET jumpers are cut
  and its µSD slot stays empty: the battery gauge's alert shares valve A's
  pin, card detect shares heater B's, and the slot shares the display SPI,
  1-wire and heater A lines. Its fan pin (GPIO8) is a boot strap that the
  gate pulldown holds low, so it is flashed out of its socket. It keeps
  the S2's 50% display buffer until its heap and redraw time are measured.
  Nothing about it is bench-verified: the open list is "Unverified" in
  `docs/superpowers/specs/2026-10-12-esp32-c6-board-support-design.md`
  and the steps are docs/hardware-bringup.md section 8.
```

In `CLAUDE.md`, replace

```text
entities). Platform: `packages/platform-esp32.yaml` (board, WiFi, OTA, web
server) or `packages/platform-host.yaml` (native build on the Mac). Hardware:
```

with

```text
entities). Platform: `packages/platform-esp32.yaml` (WiFi, setup AP, web
server) or `packages/platform-host.yaml` (native build on the Mac). Board:
`packages/board-s2.yaml` or `packages/board-c6.yaml` (that chip's `esp32:`
block, logger port and `pin_*` substitutions; every ESP32 selector includes
exactly one). Hardware:
```

In `CLAUDE.md`, replace

```text
`desiccant-dryer-hw-test.yaml` and `desiccant-dryer-host.yaml` are short
selectors; the production one wraps `packages/production.yaml`
(docs/releasing.md); `desiccant-dryer-scenarios.yaml`
```

with

```text
`desiccant-dryer-hw-test.yaml` and `desiccant-dryer-host.yaml` are short
selectors; the production one wraps `packages/production.yaml`
(docs/releasing.md); `desiccant-dryer-c6.yaml` and
`desiccant-dryer-hw-test-c6.yaml` are the production and hw-test builds
with the C6 board package; `desiccant-dryer-scenarios.yaml`
```

In `CLAUDE.md`, replace

```text
reads `ip_addr` from the platform package. `hw-real.yaml` is the pin-map source of truth for sensors,
`base.yaml` for outputs, `display-st7789.yaml` for the display.

Outputs on the 12-pin header: heater A 13, heater B 12, valve A 11,
valve B 10, fan 8. Sensors/display on the 16-pin header: I2C 1/2 (Qwiic),
SPI 36/35, display CS 5 / DC 7 / RST 9 / BL 17, 1-wire 37.
```

with

```text
reads `ip_addr` from the platform package. `board-s2.yaml` and `board-c6.yaml` are the pin-map source of truth,
one table per chip by header position; `base.yaml`, `hw-real.yaml` and
`display-st7789.yaml` hold no GPIO numbers.

The main board is wired by header position and takes either board. On the
C6, at the same positions: heater A 18, heater B 22, valve A 11, valve B 10,
fan 8; I2C 6/7 (Qwiic), SPI 19/20, display CS 5 / DC 4 / RST 3 / BL 0,
1-wire 21. Its 12-pin silkscreen reads GPIO0 to GPIO6, which are header
labels, not chip GPIOs. Checked against SparkFun's Eagle files only
(docs/pinout-verification.md). The rest of this section is the S2.

Outputs on the 12-pin header: heater A 13, heater B 12, valve A 11,
valve B 10, fan 8. Sensors/display on the 16-pin header: I2C 1/2 (Qwiic),
SPI 36/35, display CS 5 / DC 7 / RST 9 / BL 17, 1-wire 37.
```

In `CLAUDE.md`, replace

```text
- Outputs are applied from state by `apply_outputs` every tick. Never toggle
  a heater or valve from a state transition alone; change the state and let
  the apply step do it.
```

with

```text
- Outputs are applied from state by `apply_outputs` every tick. Never toggle
  a heater or valve from a state transition alone; change the state and let
  the apply step do it.
- Every ESP32 selector includes exactly one board package, and the shared
  packages contain no GPIO numbers. The T-J12 and T-J12C lint cases pin
  each board's five output pins; change a pin only together with its case
  and docs/pinout-verification.md.
```

In `CLAUDE.md`, replace

```text
- Flash with `esphome run esphome/desiccant-dryer.yaml` (real hardware) or
  `esphome run esphome/desiccant-dryer-virtual.yaml` (bare board). Bench
  testing on real hardware uses `esphome/desiccant-dryer-hw-test.yaml`
```

with

```text
- Flash with `esphome run esphome/desiccant-dryer.yaml` (real hardware) or
  `esphome run esphome/desiccant-dryer-virtual.yaml` (bare board). A C6
  board takes the `-c6` selector of the same build. Bench
  testing on real hardware uses `esphome/desiccant-dryer-hw-test.yaml`
```

In `CLAUDE.md`, replace

```text
- Only `packages/production.yaml` (wrapped by `desiccant-dryer.yaml`)
```

with

```text
- Only `packages/production.yaml` (wrapped by `desiccant-dryer.yaml` and
  `desiccant-dryer-c6.yaml`, one release image per chip in one manifest)
```

In `CLAUDE.md`, replace

```text
## Open items
```

with

```text
## Open items

- Bench-verify the ESP32-C6 board (docs/hardware-bringup.md section 8), then
  decide its display buffer size from measured heap and redraw time.
```

- [ ] **Step 4: Nothing still says the platform package holds the board**

```bash
grep -n "platform-esp32.yaml\` (board" CLAUDE.md README.md docs/*.md
grep -n "make-manifest.sh 1.2.0" docs/releasing.md
grep -c "desiccant-dryer-c6.yaml" CLAUDE.md README.md docs/releasing.md
```

Expected: no output from the first two commands, and a count of at least `1` for each of the three files.

- [ ] **Step 5: Commit**

```bash
git add docs/releasing.md README.md CLAUDE.md
git commit -m "Describe two boards and one release in the release docs, README and CLAUDE.md"
```

---

### Task 11: Whole-branch verification

**Files:** none modified, unless a check fails.

**Interfaces:**
- Consumes: everything above.
- Produces: the evidence the branch is ready for a pull request.

- [ ] **Step 1: Configs: the S2 moved only by the version**

```bash
PY="$(dirname "$(readlink -f "$(which esphome)")")/python"
mkdir -p .ci-cache/dumps/final
for s in desiccant-dryer-virtual desiccant-dryer-hw-test desiccant-dryer-host desiccant-dryer-scenarios; do
  esphome config esphome/$s.yaml > .ci-cache/dumps/final/$s.txt 2>/dev/null || echo "FAILED $s"
done
docker run --rm -v "$PWD:/config" -w /config --entrypoint esphome ghcr.io/esphome/esphome:2026.9.0 \
  config esphome/desiccant-dryer.yaml > .ci-cache/dumps/final/desiccant-dryer.txt 2>/dev/null || echo "FAILED desiccant-dryer"
for s in desiccant-dryer desiccant-dryer-virtual desiccant-dryer-hw-test desiccant-dryer-host desiccant-dryer-scenarios; do
  "$PY" scripts/normalize-config.py .ci-cache/dumps/final/$s.txt > .ci-cache/dumps/final/$s.json
  cmp -s .ci-cache/dumps/before/$s.json .ci-cache/dumps/final/$s.json && echo "$s IDENTICAL" || { echo "$s DIFFERS"; diff .ci-cache/dumps/before/$s.json .ci-cache/dumps/final/$s.json | grep '^[<>]'; }
done
```

Expected: four `IDENTICAL` lines and, for the production build only:

```text
desiccant-dryer DIFFERS
<    "version": "1.2.4"
>    "version": "1.3.0"
<     "v": "return {\"1.2.4\"};"
>     "v": "return {\"1.3.0\"};"
```

- [ ] **Step 2: Lint, manifest test, catalogue, workflows**

```bash
docker run --rm -v "$PWD:/config" -w /config --entrypoint bash ghcr.io/esphome/esphome:2026.9.0 -c 'python3 tests/lint_config.py'; echo "lint exit=$?"
bash tests/make_manifest_test.sh > /dev/null; echo "manifest test exit=$?"
python3 scripts/failure-modes-report.py .ci-cache/failure-modes.html
command -v actionlint >/dev/null && actionlint .github/workflows/*.yml && echo "actionlint ok"
```

Expected: six `pass ok` lines and `lint exit=0`; `manifest test exit=0`; `220 items, … 196 tests …`; `actionlint ok`.

- [ ] **Step 3: The host cases still pass**

The host build's config is byte-identical, so this is a regression check on the one file every build shares (`base.yaml`). It compiles the host build natively, which takes a few minutes.

```bash
tests/run_cases.py; echo "host cases exit=$?"
```

Expected: `host cases exit=0`, with every case reported as it is on `origin/main` (a `green` case passing, a `red` case failing as expected).

- [ ] **Step 4: Invariants by grep**

```bash
grep -n "GPIO[0-9]" esphome/packages/base.yaml esphome/packages/hw-real.yaml esphome/packages/display-st7789.yaml esphome/packages/platform-esp32.yaml
grep -L "board-s2.yaml\|board-c6.yaml" $(grep -l "platform-esp32.yaml\|production.yaml" esphome/desiccant-dryer*.yaml)
grep -rn "outputs_internal: \"false\"" esphome/desiccant-dryer.yaml esphome/desiccant-dryer-c6.yaml esphome/packages/production.yaml
git status --short
```

Expected: no output from any of the four. The second command lists any selector that takes the ESP32 platform package, directly or through `production.yaml`, without a board package. The third confirms no production selector exposes the relay switches. The fourth confirms nothing is left uncommitted and no scratch file escaped `.ci-cache/`.

- [ ] **Step 5: Hand over**

The screen drawing (`display-draw.yaml`, `components/dryer_ui`) is untouched, so `scripts/scenario-shots.sh` has nothing new to show and is not run.

Report: the commits (`git log --oneline origin/main..HEAD`), the outputs of Steps 1 to 4, the result of Task 6, and that the bench steps in `docs/hardware-bringup.md` section 8 are the remaining work and need a person with the board. Do not open a pull request or tag a release unless asked.
