# Hardware bring-up checklist

First flash of the production build onto a board with real hardware. Written
for the bench state on 2026-09-14: three DS18B20s, both valves, the fan and
the display connected; 2N2222 heater driver stages wired but no relays; no
SHT45. Everything here is safe with mains disconnected, and nothing switches
mains until the relays exist.

What to expect with the gaps: the SHT45 logs a read failure every 10 s and
`Outlet Air Humidity` stays unknown, which holds the state machine safely
until `Simulate Humidity` is on. The heater switches drive the transistor
bases only; GPIO13 also lights the on-board blue LED.

## 1. Flash

1. Plug the hardware board in. Two boards on USB show two ports; pick the new
   one:

   ```bash
   ls /dev/cu.usbserial* /dev/cu.SLAB*
   ```

2. Flash the production build over USB and keep the log open:

   ```bash
   esphome run --device /dev/cu.usbserial-XXXX esphome/desiccant-dryer.yaml
   ```

   Expected in the boot log: a `Boot: active pack N, standby state N, fault N`
   line first (all zero on a fresh device; a reflash keeps the persisted
   values), `[wifi] Connected` then `IP x.x.x.x` (use that address if `.local`
   does not resolve), `[one_wire]` listing three found addresses, `[ili9xxx]` without "Failed to init", `[sht4x]` warning
   about communication (expected), `[cycle] Starting on pack A`, Valve A on.

3. Pair in Home Assistant as a second device (Desiccant Dryer, port 6053,
   same API key).

## 2. Identify the DS18B20 probes

1. Copy the three addresses from the boot log into `hw-real.yaml`, any
   order, and reflash over the air (`--device desiccant-dryer.local` or its
   IP).
2. Warm one probe at a time (fingers are enough, 2 to 3 °C rise within a
   minute). Watch `Pack A Temperature`, `Pack B Temperature`, `Case
   Temperature` in HA and note which entity rose.
3. Reassign the addresses in `hw-real.yaml` so the probe clamped to pack A
   is `pack_a_temp`, and so on. Reflash. Commit that change on its own.

## 3. Outputs, one at a time, from HA

Turn `Dryer Enabled` off first: the control tick re-asserts outputs every
5 s while it is on and would undo your toggles. Turn it back on when done.

| Output | Action | Expect |
|---|---|---|
| Valve A | switch on, then off | audible click each way; Valve B stays off |
| Valve B | switch on while A is on | A drops out first, B clicks on 500 ms later (interlock) |
| Case Fan | set Case Fan Thermostat target below case temp | fan runs after the 30 s minimum idle time; back above: stops after 60 s minimum run |
| Heater A | switch on | blue LED on GPIO13 lights; collector of the A stage reads near 0 V |
| Heater B | switch on while A is on | A drops out first, B on 500 ms later; collector of the B stage near 0 V |

Turn every output off afterwards, then `Dryer Enabled` on: within 5 s the
tick should open Valve A and leave everything else off. That correction is
itself worth watching once.

## 4. Display

Confirm the layout matches `display-draw.yaml`: "AIR: A" at the top, the
humidity line reads "nan %RH" until simulation is on, the three temperature
lines, the humidity bar, the IP at the bottom. If the image is shifted or
cropped, try `offset_height: 80` as the comment in `display-st7789.yaml` says. Note
the backlight level and colours.

## 5. Cycle with simulated humidity and real probes

Follow "Test sequence on the real unit" in `docs/control-logic.md`. Lower
`Regen temp` to something a hand can reach (about 30 °C) and `Regen hold
time` to 1 min for the bench so the HEATING state can be completed by
warming probe B. Expect the "not heating" fault if a probe is not warmed
within 5 min of the heater switch turning on; that is the check working.

## 6. Record

Note the three addresses, which port each board uses, anything that
differed from the table above, and the display offset that worked, as a PR
comment or in this file.
