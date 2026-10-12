# ESP32-C6 Thing Plus as a second supported board

**Goal.** Let a SparkFun Thing Plus ESP32-C6 (DEV-22924) take the place of the
ESP32-S2 Thing Plus in the same main-board socket, with no main-board
changes, running the same controller and updating itself from the same
release manifest. The S2 stays supported: every release ships one image per
chip.

**What was asked, and what is assumed.** Asked: support a newer SparkFun
board with an ESP32-C6-WROOM-1 as a replacement for the S2 board. Decided
in the design conversation (2026-10-08): both chips side by side; the C6
goes in the existing socket with two solder jumpers cut on the C6; per-chip
board packages with pin substitutions. Assumed: the control logic, sensors,
display drawing and Home Assistant entities do not change.

Nothing in this document has been run on a C6. Everything about the board
comes from SparkFun's Eagle files and ESPHome's source; the bench items are
listed under [Unverified](#unverified--measure-do-not-assume).

## The board

Read 2026-10-08 from `Hardware/Thing_Plus_ESP32_C6.sch` and `.brd` in
github.com/sparkfun/SparkFun_Thing_Plus_ESP32_C6 (Eagle XML, nets parsed
the same way as for the S2 in `docs/pinout-verification.md`).

- Module ESP32-C6-WROOM-1-N16: single RISC-V core, 512 KB SRAM (S2: 320 KB),
  16 MB flash, no PSRAM, WiFi 6, Bluetooth, 802.15.4.
- USB-C goes to the chip's own USB-Serial-JTAG (GPIO12/13). There is no
  CP2102 and no auto-reset transistor pair.
- Regulator RT9080-33GJ5 (S2: AP2112). MAX17048 battery gauge on the Qwiic
  I2C bus (address 0x36; the SHT45 is 0x44). MCP73831 charger. µSD slot.
  WS2812 RGB LED on IO23; no plain LED on any header pin.
- ESPHome 2026.8.2 has the board as `sparkfun_esp32c6_thing_plus`
  (`variant: esp32c6`), and its logger default for the C6 is
  `USB_SERIAL_JTAG`.

**It is a mechanical drop-in.** In both `.brd` files the 12-pin header runs
from (1.27, 24.13) to (1.27, 52.07) mm and the 16-pin header from
(21.59, 13.97) to (21.59, 52.07) mm, with USB-C at the y = 0 end. The C6
board is 58.42 mm long against the S2's 64.77 mm; the difference is at the
antenna end. Power positions match: 16-pin 1 RESET, 2 3V3, 4 GND; 12-pin
1 BAT, 2 LDO EN, 3 USB. As on the S2, 12-pin 3 is the same net as USB-C
VBUS, so the rule "never the 5 V rail and a USB cable together" carries
over.

## Header map by position

The main board is wired by position, so the C6's pin numbers follow from
where each wire already lands.

16-pin header:

| Pos | S2 net / GPIO | C6 silkscreen / GPIO | Our use | C6 note |
|---|---|---|---|---|
| 1 | CHIP_PU | RESET / EN | — | pull-up R11 is 100 kΩ (S2: 10 kΩ) |
| 2 | 3V3 | 3.3V | 3.3 V rail | |
| 3 | NC | AREF/NC | — | WS2812 data out through jumper RGB, open by default |
| 4 | GND | GND | GND rail | |
| 5 | A0 / 17 | A0 / 0 | backlight PWM | |
| 6 | A1 / 18 | A1 / 1 | — | |
| 7 | A2 / 14 | A2 / 2 | — | |
| 8 | A3 / 9 | A3 / 3 | display RST | |
| 9 | A4 / 7 | A4 / 4 | display DC | strapping (MTMS) |
| 10 | A5 / 5 | A5 / 5 | display CS | strapping (MTDI) |
| 11 | SCK / 36 | SCK / 19 | SPI clock | also µSD CLK |
| 12 | COPI / 35 | PICO / 20 | SPI data | also µSD CMD |
| 13 | CIPO / 37 | POCI / 21 | 1-wire | also µSD DAT0 |
| 14 | RX1 / 33 | RX / 17 | — | UART0 RX |
| 15 | TX1 / 34 | TX / 16 | — | UART0 TX: the ROM prints here at boot |
| 16 | 3 / 3 | FREEBIE / 9 | — | **BOOT strap**, BOOT button to GND |

12-pin header:

| Pos | S2 net / GPIO | C6 silkscreen / GPIO | Our use | C6 note |
|---|---|---|---|---|
| 1 | BAT | V_BATT | — | |
| 2 | EN (LDO) | EN (LDO) | — | regulator enable, R8 100 kΩ |
| 3 | USB | V_USB | 5 V in | same net as USB-C VBUS |
| 4 | 13 | "GPIO0" / 18 | heater A | also µSD DAT3/CS |
| 5 | 12 | "GPIO1" / 22 | heater B | card detect + R5 100 kΩ, through jumper SD_DET |
| 6 | 11 | "GPIO2" / 11 | valve A | MAX17048 ALRT + R14 100 kΩ, through jumper ALRT |
| 7 | 10 | "GPIO3" / 10 | valve B | nothing else on the net |
| 8 | 8 | "GPIO4" / 8 | case fan | **strapping**, R1 100 kΩ to 3.3 V |
| 9 | 6 | "GPIO5" / 23 | — | WS2812 data in |
| 10 | 4 | "GPIO6" / 15 | — | strapping; jumper LP pad, not connected by default |
| 11 | SCL / 2 | SCL / 7 | I2C | Qwiic, gauge, 2.2 kΩ pull-up |
| 12 | SDA / 1 | SDA / 6 | I2C | Qwiic, gauge, 2.2 kΩ pull-up |

The C6's 12-pin silkscreen says GPIO0–GPIO6. Those are SparkFun's header
labels, not chip GPIO numbers: "GPIO0" is IO18. Valve A, valve B and the fan
happen to keep their numbers (11, 10, 8); nothing else does.

## Shared nets on the C6, and the decision for each

| Net | Shared with | At boot (pin floating) | Decision |
|---|---|---|---|
| Valve A, IO11 | MAX17048 alert, open-drain, 100 kΩ pull-up | 100 kΩ against our 10.1 kΩ gate path: ~0.3 V, valve shut | **Cut jumper ALRT.** If the gauge pulled its alert low while the firmware drove valve A on, an output would be driving into a short. |
| Heater B, IO22 | µSD card-detect switch, 100 kΩ pull-up to the switched 3.3 V rail | 100 kΩ against 1 kΩ + 1 kΩ: ~0.03 V at the base, relay off | **Cut jumper SD_DET.** Makes the net ours alone. |
| Heater A IO18, SPI IO19/20, 1-wire IO21 | µSD slot signals, no pull resistors on the board | nothing to pull them | **The µSD slot stays empty.** A card would be selected whenever heater A is off, see the display's SPI traffic, and could drive the 1-wire line. |
| Fan, IO8 | boot strap, 100 kΩ pull-up | ~0.3 V: fan off, but the strap reads low | Keep. GPIO8 only matters together with GPIO9 low (download mode); see Unverified 1. |
| Display DC IO4, CS IO5 | SDIO-timing straps | driven only by us; the panel's inputs do not drive them | Keep. |
| RESET | — | 100 kΩ pull-up, ten times weaker than the S2's | Keep. The main board's measured RESET leakage paths are megohms (1 µA or less), so at most about 0.1 V of drop across the pull-up. |

Positions the main board must leave unconnected because the C6 gives them
a job: 16-pin 16 (BOOT strap), 16-pin 15 (UART0 TX, an output at boot),
12-pin 10 (IO15 strap), 12-pin 9 (RGB LED data). All four are unused on the
S2 wiring.

## Firmware structure

Two new packages carry everything that depends on the chip.

`packages/board-s2.yaml`
- the `esp32:` block moved verbatim from `platform-esp32.yaml` (board,
  variant, ESP-IDF, the TLS and WiFi `sdkconfig_options` and their comment);
- `logger: hardware_uart: UART0`, with its comment;
- the S2 pin table as substitutions.

`packages/board-c6.yaml`
- `esp32:` with `board: sparkfun_esp32c6_thing_plus`, `variant: esp32c6`,
  `framework: type: esp-idf`, and the same `sdkconfig_options`, so the
  update path's TLS configuration is the same on both chips. The C6 does
  not need the heap trims; if one of the options does not exist for the C6
  the compile will say so and that one is dropped there. Default 4 MB
  partition layout, the same as the S2.
- `logger: hardware_uart: USB_SERIAL_JTAG`, stated rather than left to the
  default.
- the C6 pin table. GPIO4, 5 and 8 are written as mappings with
  `ignore_strapping_warning: true` and a one-line reason each. (Checked: a
  substitution can hold a mapping and `pin: ${pin_fan}` expands it. The flag
  cannot live in the shared files, because ESPHome rejects it on a pin that
  is not a strapping pin, which is every one of them on the S2.)

Both files open with the same position → function → GPIO table so they read
row for row against each other and against the sockets. They become the
pin-map source of truth, replacing the split across `hw-real.yaml`,
`base.yaml` and `display-st7789.yaml`.

Substitutions, identical keys in both files:

| Key | S2 | C6 |
|---|---|---|
| `pin_heater_a` | GPIO13 | GPIO18 |
| `pin_heater_b` | GPIO12 | GPIO22 |
| `pin_valve_a` | GPIO11 | GPIO11 |
| `pin_valve_b` | GPIO10 | GPIO10 |
| `pin_fan` | GPIO8 | GPIO8 (strapping) |
| `pin_i2c_sda` | GPIO1 | GPIO6 |
| `pin_i2c_scl` | GPIO2 | GPIO7 |
| `pin_onewire` | GPIO37 | GPIO21 |
| `pin_spi_clk` | GPIO36 | GPIO19 |
| `pin_spi_mosi` | GPIO35 | GPIO20 |
| `pin_lcd_cs` | GPIO5 | GPIO5 (strapping) |
| `pin_lcd_dc` | GPIO7 | GPIO4 (strapping) |
| `pin_lcd_rst` | GPIO9 | GPIO3 |
| `pin_lcd_bl` | GPIO17 | GPIO0 |

Shared files:
- `base.yaml`, `hw-real.yaml`, `display-st7789.yaml` use `${pin_*}` and hold
  no GPIO numbers and no defaults: a selector without a board package fails
  validation instead of silently taking one chip's pins. Their header
  comments point at the board files.
- `platform-esp32.yaml` keeps WiFi, the setup AP, the captive portal, the
  web server and the WiFi sensors.
- `platform-host.yaml` supplies the five output keys with today's numbers,
  as placeholders: the host build drives no pins, and keeping the numbers
  keeps its config dump unchanged.
- `production.yaml` stays chip-neutral.

Selectors:
- `desiccant-dryer.yaml`, `-virtual.yaml`, `-hw-test.yaml` each add
  `board: !include packages/board-s2.yaml`.
- New `desiccant-dryer-c6.yaml`: `production.yaml` + `board-c6.yaml`, the
  same `name: desiccant-dryer` and project name, so a replacement board
  shows up as the same kind of device. It sets its own build directory so
  the two production compiles do not share one.
- New `desiccant-dryer-hw-test-c6.yaml`: the bench build, name
  `desiccant-dryer-hw-test-c6`.
- The virtual build stays S2-only.

The C6 production build keeps the S2's `display_buffer_size: 50%` and 10 s
redraw. Whether it can afford 100% is a later change, made from measured
numbers.

## Release, updates and CI

- `release.yml` compiles both production selectors for a tag.
- `scripts/make-manifest.sh <version> <out-dir> <release-url>
  <chip>=<build-dir>...` writes
  `desiccant-dryer-<ver>-esp32s2.{ota,factory}.bin`,
  `desiccant-dryer-<ver>-esp32c6.{ota,factory}.bin` and one `manifest.json`
  with two builds, `chipFamily` `ESP32-S2` and `ESP32-C6`, each with its own
  md5. The release carries all five files; Pages `firmware/` still holds
  only the latest release.
- Units in the field: `http_request`'s update component (read in 2026.8.2)
  walks `builds`, skips entries whose `chipFamily` is not its own
  `ESPHOME_VARIANT`, and resolves the `.bin` path relative to the manifest.
  An S2 unit on 1.2.4 therefore takes the S2 build of the next release, and
  renaming the files is safe. The manifest grows to about 1 KB.
- web.esphome.io chooses the factory image by the chip it detects.
- Version **1.3.0**, bumped in the PR. One version number for both chips.
- `build.yml`: the compile matrix gains `production-c6` and `hw-test-c6`.
  The toolchain cache key gains the chip, since the C6 needs the RISC-V
  compiler and a shared key would be saved by whichever job finished first.
  The repository's Actions cache was empty when checked (2026-10-12), so the
  sizes against the 10 GB quota are unknown until the new matrix has run.
- ci-lint: T-K01L, T-F15, T-B20 and T-J04 add `desiccant-dryer-c6.yaml`
  (and `-hw-test-c6.yaml` where they list hw-test) to `selectors`. A new
  case asserts the five output pins of each production selector against
  the table above, so a wrong number in a board file fails CI rather than
  energising the wrong relay.

## Hardware prep and docs

Before a C6 goes into a socket:
1. Cut jumpers **ALRT** and **SD_DET** on the back (both are closed-trace
   jumpers; a solder blob restores them).
2. Check with a meter, unpowered: no continuity across either jumper's two
   pads. For ALRT there is a second reading: 12-pin 6 to 3V3 is about
   100 kΩ before the cut and open after. (SD_DET's pull-up goes to the
   switched rail, so it has no equivalent reading to 3V3.)
3. Leave the µSD slot empty; tape over it.
4. Leave LP, I2C, RGB, CHG, PWR, SHLD and MEAS as delivered.

Flashing: the port is `/dev/cu.usbmodem*`. First flash off the main board,
from the Pages manifest through web.esphome.io, as for any field board.

Docs:
- `docs/pinout-verification.md`: a C6 section in the S2 section's form
  (header tables, shared nets, chip constraints: USB 12/13, strapping
  4/5/8/9/15, flash 24–30).
- `docs/datasheets/mcu/`: the C6 `.sch` and `.brd` under the existing
  SparkFun licence note, and Espressif's ESP32-C6 and ESP32-C6-WROOM-1
  datasheets; `docs/datasheets/README.md` updated.
- `docs/hardware.md`: "Fitting an ESP32-C6 Thing Plus" with the steps above.
- `docs/hardware-bringup.md`: C6 flashing and the bench steps below.
- `docs/board-continuity-check.md`: the four positions that must be
  unconnected.
- `docs/breadboard.svg`, `docs/board-layout.svg`: unchanged, with a caption
  line that the GPIO labels are the S2's and the wiring is by position.
- `docs/failure-modes.md` and `docs/verification-plan.md`: ALRT left
  uncut; a card in the slot; GPIO8 strap and USB flashing in the socket;
  the weaker RESET pull-up; an image for the wrong chip.
- `docs/releasing.md`: two images per tag, how each consumer picks one, and
  that a USB recovery flash needs the image for the chip fitted.
- `CLAUDE.md`, `README.md`: one board becomes two; pin map and layout
  sections follow the new files.

## Verification

In the PR:
1. **S2 unchanged.** `esphome config` for `desiccant-dryer`, `-virtual`,
   `-hw-test`, `-host` and `-scenarios` on `origin/main` and on the branch,
   through `scripts/normalize-config.py`, diffed. Only the `substitutions`
   block may differ.
2. The new pin lint case and the extended invariant cases pass.
3. All seven builds compile in CI.
4. `make-manifest.sh` run locally on both build directories: two builds,
   the right `chipFamily` strings, md5s that match the files.

On the bench, as a checklist in `docs/hardware-bringup.md`:
5. `hw-test-c6` over USB, board off the main board: boots, logs on the
   native USB port, joins WiFi.
6. Seated: panel draws cleanly, SHT45 and the three DS18B20s read, then
   bring-up steps 3 to 5 (relays, interlocks, valves, fan).
7. One USB flash attempt while seated; record the result.
8. After 1.3.0 is released: flash from the Pages manifest, provision by
   Improv, reboot once, record Free Heap, Largest Free Block and the logged
   redraw time. Then a version-only 1.3.1, installed by the unit itself,
   before it goes to its site.

Done: CI green on seven builds, the config diff empty, the C6 through
bring-up 3 to 5 on the main board, and a C6 unit having installed 1.3.1 by
itself.

## Not in this work

- The RGB LED as a status light. Thread, Zigbee, Bluetooth.
- A 16 MB partition layout.
- A 100% display buffer on the C6.
- A C6 virtual build.
- Any change to the main board, the control logic or the screen.

## Unverified — measure, do not assume

1. **USB download mode while seated.** The fan's 10 kΩ gate pulldown holds
   GPIO8 low. From memory of Espressif's datasheet, GPIO8 low with GPIO9 low
   is not a valid boot combination; confirm against the PDF when it is added
   to `docs/datasheets/`, and by bench step 7. The docs then say what was
   seen.
2. **40 MHz SPI on glass.** The S2's 35/36 are its dedicated SPI pins; the
   C6's 19/20 go through the GPIO matrix. If the image shows artefacts,
   `data_rate` becomes a per-board substitution.
3. **Redraw time and heap on the C6.** 160 MHz RISC-V against the S2's
   240 MHz Xtensa; the S2's 377 ms and 699 ms figures do not transfer.
4. **Improv over USB-Serial-JTAG.** ESPHome's validation accepts it; not
   seen working on this board.
5. **The on-device HTTPS install on the C6.** Proven only by step 8.
6. **Whether the gauge asserts ALRT with no battery.** Not needed once the
   jumper is cut; recorded because it is the reason for the cut.
7. **`sparkfun_esp32c6_thing_plus` and the sdkconfig options under ESPHome
   2026.9.0.** Read in 2026.8.2; CI compiles with 2026.9.0.
