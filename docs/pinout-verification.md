# Pinout verification — SparkFun Thing Plus boards

Two boards fit the main board's sockets: the ESP32-S2 Thing Plus
(WRL-17743) and the Thing Plus ESP32-C6 (DEV-22924). The main board is
wired by header position. The GPIO behind each position differs between
the two and lives in `esphome/packages/board-s2.yaml` and
`esphome/packages/board-c6.yaml`. Everything down to "Action items for the
software side" is about the S2; the C6 has
[its own section](#thing-plus-esp32-c6-dev-22924) after that.

## ESP32-S2 Thing Plus (WRL-17743)

Date: 2026-09-14. Re-checked 2026-09-15 by parsing the schematic's nets
(J2, J4, J7, D3/R4, GPIO18PU/R14) against the module's IO pins, and
2026-10-08 for the two EN pins (J4 pin 1, J2 pin 2) against the `.sch`
and `.brd` in [datasheets/mcu/](datasheets/mcu/).

## Source of truth

`Hardware/ESP32-S2_Thing_Plus.sch` from SparkFun's GitHub hardware repo
(github.com/sparkfun/ESP32-S2_Thing_Plus). Nets were read directly from the
Eagle XML. J4 is the 16-pin header, J2 the 12-pin header, J3 the Qwiic
connector, J7 the back pads, J6 the JTAG footprint.

The Espressif ESP32-S2 Technical Reference Manual describes the chip only
and was used for chip-level constraints (USB pins, strapping pins,
SPI0/1 reservations), not header mapping.

## Result

All GPIO numbers in `esphome/packages/board-s2.yaml` (the pin table the
sensor, output and display packages take theirs from), and in the wiring
diagram [breadboard.svg](breadboard.svg), are correct. No wiring changes.

### Headers, pin by pin (from the schematic)

16-pin header (J4):

| Pos | Net | GPIO | Our use |
|---|---|---|---|
| 1 | CHIP_PU | — | — (ESP reset, silkscreen RST; see 7 below) |
| 2 | 3V3 | — | top 3.3 V rail |
| 3 | NC | — | |
| 4 | GND | — | top GND rail |
| 5 | A0 | 17 | display backlight (PWM) |
| 6 | A1 | 18 | — (optional pullup via solder jumper) |
| 7 | A2 | 14 | |
| 8 | A3 | 9 | display RST |
| 9 | A4 | 7 | display DC |
| 10 | A5 | 5 | display CS |
| 11 | SCK | 36 | SPI clock |
| 12 | COPI (MOSI) | 35 | SPI data to display |
| 13 | CIPO (MISO) | 37 | 1-wire bus (3× DS18B20) |
| 14 | RX1 | 33 | |
| 15 | TX1 | 34 | |
| 16 | 3 | 3 | |

12-pin header (J2):

| Pos | Net | GPIO | Our use |
|---|---|---|---|
| 1 | BAT | — | |
| 2 | EN | — | — (3.3 V regulator enable, not a reset; see 7 below) |
| 3 | USB | — | 5 V in from buck (same net as USB-C VBUS) |
| 4 | 13 | 13 | heater A relay (also lights on-board LED) |
| 5 | 12 | 12 | heater B relay |
| 6 | 11 | 11 | valve A |
| 7 | 10 | 10 | valve B |
| 8 | 8 | 8 | case fan |
| 9 | 6 | 6 | |
| 10 | 4 | 4 | |
| 11 | SCL | 2 | I2C (also on Qwiic) |
| 12 | SDA | 1 | I2C (also on Qwiic) |

Qwiic (J3): GND, 3.3 V, SDA=GPIO1, SCL=GPIO2. SHT45 plugs in here.

### Things the schematic clears up

1. **On-board blue LED is on GPIO13**, via R4 (1 kΩ) to D3, cathode to GND
   — active high. Consequence: the LED lights whenever heater A's relay is
   driven. Fine.
2. **GPIO18 (A1) pullup is optional.** It goes through solder jumper
   `GPIO18PU` (normally open) to R14 10 kΩ. By default there is no pullup.
   We don't use GPIO18 either way.
3. **The 12-pin header does not carry GPIO9 or GPIO5.** Where a standard
   Feather has "9" and "5", this board has GPIO8 and GPIO4. GPIO9 and GPIO5
   exist only as A3 and A5 on the 16-pin header — which is where the design
   takes them from (display RST and CS). Don't wire "pin 9" from the 12-pin
   side expecting GPIO9.
4. **RX1/TX1 (GPIO33/34) are on the 16-pin header**, not back pads. Not
   used, but available.
5. **GPIO45/46 (strapping) and GPIO21/26/38/41 are on the back pads (J7)**
   only. Not used.
6. **The 12-pin USB pin is the USB-C connector's VBUS.** J2 pin 3 and J5
   VBUS are one net, `V_USB`. The Schottky D2 sits after it (V_USB to VIN),
   so nothing separates the two sources. Never connect the breadboard 5 V
   rail to the USB pin and a USB-C cable at the same time: pull the USB-pin
   wire before flashing over USB, or flash over the air.
7. **The two "EN" pins are different nets.** J4 pin 1 is `CHIP_PU`, the
   module's EN pin: the ESP reset, with R10 10 kΩ to 3.3 V, C8 0.1 µF,
   the RESET button S1, the JTAG !RESET pin and the collector of Q2,
   the DTR/RTS auto-reset transistor. Its silkscreen is RST on the
   component side and RESET on the back. J2 pin 2 is net `EN`: the
   AP2112 LDO's enable, R8 100 kΩ to VIN, silkscreened EN. Pulling it
   low turns the 3.3 V rail off rather than resetting the ESP. Neither
   is used.

## Chip-level constraints (TRM)

- GPIO19/20 are USB D−/D+: never assign.
- Strapping pins: GPIO0 (boot button), 45, 46.
- GPIO33–37 are reserved only for 8-line SPI flash/PSRAM; this module is
  quad-SPI, so 35/36/37 are free for the display and 1-wire.
- USB-C data lines go to the CP2102 UART bridge by default (USB solder
  jumper on the back), so flashing is plain serial.

## Action items for the software side

- Pin numbers: none.
- Board ID: none. `board: sparkfun_esp32s2_thing_plus` in
  `packages/board-s2.yaml` compiles in CI and runs on the bench board.
- If a status indicator is ever wanted, GPIO13 already drives the blue LED;
  it currently doubles as heater A's relay drive, so it will show heater A
  state without any extra config.

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
