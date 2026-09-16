# Hardware bring-up checklist

Bring-up of a board wired into real hardware. Bench state for the first run
(2026-09-15): three DS18B20s, both valves, the fan and the display
connected; 2N2222 heater driver stages wired but no relays; no SHT45.
Everything here is safe with mains disconnected, and nothing switches mains
until the relays exist.

What to expect with the gaps: the SHT45 logs a read failure every 10 s and
`Outlet Air Humidity` stays unknown, which holds the state machine safely
until `Override Humidity` is on. The heater switches drive the transistor
bases only; GPIO13 also lights the on-board blue LED.

The testing runs on the **hardware test build**,
`esphome/desiccant-dryer-hw-test.yaml`: the production controller and real
hardware plus the developer credentials from `secrets.yaml`, so it takes
OTA updates as often as needed and USB is only used once. The released
production image (`esphome/desiccant-dryer.yaml`) has no OTA server, no
WiFi credentials (it has WiFi and a setup access point, and is provisioned
through Improv or that access point) and no `/screen.png`; it goes on last,
as its own step (section 7).

## 1. Flash the test build (USB, once)

1. First pull the wire from the board's USB pin to the breadboard 5 V rail.
   That pin is the same net as the USB-C connector's VBUS, with no diode, so
   leaving it in ties the buck to the computer's USB port. Then plug the
   board in. macOS lists one CP2102N twice (`cu.SLAB_USBtoUART` and
   `cu.usbserial-NNN`); either works:

   ```bash
   ls /dev/cu.usbserial* /dev/cu.SLAB*
   ```

2. Copy the real `secrets.yaml` into `esphome/` (the CI copy has dummy
   WiFi) and flash:

   ```bash
   esphome run --device /dev/cu.usbserial-XXXX --no-logs esphome/desiccant-dryer-hw-test.yaml
   ```

3. Unplug, wire the board into the hardware, power it. It joins WiFi as
   `desiccant-dryer-hw-test`; find the IP from mDNS or the router. From here
   every reflash is over the network:

   ```bash
   esphome run --device <board> esphome/desiccant-dryer-hw-test.yaml
   ```

4. Add it in Home Assistant: Settings → Devices & services → Add
   integration → ESPHome, host `<board>`, port 6053, the `api_key` from
   `secrets.yaml`. Home Assistant is on another site with no mDNS across the
   VPN, so it is not discovered by itself. The entity unit settings
   default to °F on a new entry; set them to °C if you want to match the
   thresholds.

Logs without USB: `esphome logs --device <board>
esphome/desiccant-dryer-hw-test.yaml` (the dump on connect lists the 1-wire
devices), or the web server's event stream at `http://<board>/events`.

## 2. Identify the DS18B20 probes

`dallas_temp` has no `index:` option, so the probes need their addresses
before they read at all.

1. Copy the three addresses from the `[gpio.one_wire] Found devices` lines
   into `hw-real.yaml`, any order, and reflash over the network.
2. Warm one probe at a time (fingers give 2 to 5 °C within a minute) and
   note which of `Pack A Temperature`, `Pack B Temperature`, `Case
   Temperature` rose.
3. Either reassign the addresses in `hw-real.yaml` and reflash, or label
   the probes to match the file. Commit the addresses on their own.

First unit (2026-09-15), probes labelled to match:

| Entity | Address |
|---|---|
| Pack A Temperature | `0x8b00000071633028` |
| Pack B Temperature | `0xc300000070605d28` (confirmed by warming) |
| Case Temperature | `0xdb0000006f9c0328` |

## 3. Outputs, one at a time, from HA

Turn `Dryer Enabled` off first: the control tick re-asserts outputs every
5 s while it is on and would undo your toggles.

The heater stages have no load until the relays are fitted, so an open
collector floats near 0 V whether the transistor is on or off. Put a pull-up
(about 1 kΩ to 5 V, or an LED and resistor) on each collector in place of
the coil to see it switch.

| Output | Action | Expect | First unit |
|---|---|---|---|
| Valve A | switch on, then off | audible click each way; Valve B stays off | pass |
| Valve B | switch on while A is on | A drops out first, B clicks on 500 ms later (interlock) | pass, ~650 ms seen from HA |
| Case Fan | set Case Fan Thermostat target below case temp | fan runs once 30 s minimum idle has passed; back above: stops after 60 s minimum run | pass, ~60 s run |
| Heater A | switch on | blue LED lights; A collector under 0.2 V, B collector ~5 V | pass, 9 mV / 5 V |
| Heater B | switch on while A is on | A drops out first, B on 500 ms later; B collector under 0.2 V, A ~5 V | pass, ~600 ms, 13 mV / 5 V |

Turn every output off afterwards, then `Dryer Enabled` on: within 5 s the
tick should open Valve A and leave everything else off.

## 4. Display

Compare the panel with `http://<board>/screen.png` (the frame buffer the
panel is drawn from) and with the reference states in `docs/display/`. With
no SHT45 the humidity reads `--% RH`. If the image is shifted or cropped,
try `offset_height: 80` as the comment in `display-st7789.yaml` says; red
and blue swapped means the colour order, a negative image means
`invert_colors`. First unit: offset 0, colours and backlight correct.

## 5. Cycle with the humidity override and real probes

Follow "Test sequence on the real unit" in `docs/control-logic.md`, setting
the override slider from HA. For the bench:

- `Regen temp` cannot go below 40 °C, which fingers do not reach. Set it to
  40 °C and use a heat gun on low (or hot water) on the standby probe; aim
  for 45 to 60 °C, far below the 110 °C overtemp latch.
- `Regen hold time` 1 min, `Cooldown temp` about 33 °C so COOLING has a
  threshold to fall through once the heat is removed.
- Start heating within 5 min of the heater switch turning on, or the "not
  heating" fault latches; that is the check working.

First unit: B heating → cooling → ready, swap to B (with "A heating
(waiting)" at 12 %), A heating → cooling → ready, swap back to A, no faults.

Afterwards: `Dryer Enabled` off, `Override Humidity` off, and the tunables
back to their defaults (regen 90 °C / 15 min, cooldown 40 °C).

## 6. Record

Note anything that differed from the tables above, and the addresses and
display offset of each unit, in this file.

## 7. Production image

Needs USB access to the board. Follow "Installing a release on a dryer" in
docs/releasing.md: flash the release, give it WiFi, adopt it in ESPHome
Device Builder, and install the adopted YAML over USB once. After that,
Device Builder installs updates over WiFi. Expect `Firmware Version` to
match the release. Remove the HW Test entry from HA first if it uses the
same host.

The test board (2026-09-15) ran this path with an adopted-style YAML built
from a branch: USB install of 1.1.0, then a Device Builder-equivalent
native OTA push (`esphome run --device <board>`) to a relabelled build,
which rebooted into it with the controller running and no fault.
