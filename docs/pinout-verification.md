# Pinout verification — SparkFun ESP32-S2 Thing Plus (WRL-17743)

Date: 2026-09-14. Re-checked 2026-09-15 by parsing the schematic's nets
(J2, J4, J7, D3/R4, GPIO18PU/R14) against the module's IO pins.

## Source of truth

`Hardware/ESP32-S2_Thing_Plus.sch` from SparkFun's GitHub hardware repo
(github.com/sparkfun/ESP32-S2_Thing_Plus). Nets were read directly from the
Eagle XML. J4 is the 16-pin header, J2 the 12-pin header, J3 the Qwiic
connector, J7 the back pads, J6 the JTAG footprint.

The Espressif ESP32-S2 Technical Reference Manual describes the chip only
and was used for chip-level constraints (USB pins, strapping pins,
SPI0/1 reservations), not header mapping.

## Result

All GPIO numbers in `esphome/packages/hw-real.yaml` (sensors), `base.yaml`
(outputs) and `display-st7789.yaml` (display), and in the wiring diagram
[breadboard.svg](breadboard.svg), are correct. No wiring changes.

### Headers, pin by pin (from the schematic)

16-pin header (J4):

| Pos | Net | GPIO | Our use |
|---|---|---|---|
| 1 | EN | — | |
| 2 | 3V3 | — | top 3.3 V rail |
| 3 | NC | — | |
| 4 | GND | — | top GND rail |
| 5 | A0 | 17 | display backlight (PWM) |
| 6 | A1 | 18 | — (optional pullup via solder jumper) |
| 7 | A2 | 14 | display RST |
| 8 | A3 | 9 | display DC |
| 9 | A4 | 7 | |
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
| 2 | EN | — | |
| 3 | USB | — | 5 V in from buck |
| 4 | 13 | 13 | heater A relay (also lights on-board LED) |
| 5 | 12 | 12 | heater B relay |
| 6 | 11 | 11 | valve A |
| 7 | 10 | 10 | valve B |
| 8 | 8 | 8 | |
| 9 | 6 | 6 | case fan |
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
   takes them from (display DC and CS). Don't wire "pin 9" from the 12-pin
   side expecting GPIO9.
4. **RX1/TX1 (GPIO33/34) are on the 16-pin header**, not back pads. Not
   used, but available.
5. **GPIO45/46 (strapping) and GPIO21/26/38/41 are on the back pads (J7)**
   only. Not used.

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
  `packages/platform-esp32.yaml` compiles in CI and runs on the bench board.
- If a status indicator is ever wanted, GPIO13 already drives the blue LED;
  it currently doubles as heater A's relay drive, so it will show heater A
  state without any extra config.
