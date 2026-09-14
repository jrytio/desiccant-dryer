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
   `api_key`. Later flashes go over the air. The boot log prints
   `IP x.x.x.x` two seconds after WiFi connects; use that address if
   `.local` names do not resolve from your machine (common across VLANs):

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
| Sim Manual Temps | off | Pin both pack temps to Sim Pack A/B Temp. The heaters then have no effect, so raise the pinned value yourself or expect the "not heating" fault |
| Sim Pack A Temp, Sim Pack B Temp | 25 °C | Used while Sim Manual Temps is on |
| Sim Probe A Fault, Sim Probe B Fault | off | That pack's probe reads NaN while on; the plant keeps running underneath |

With the defaults: RH reaches 5 % at 100 min of service and 10 % at 150 min.
Heating to 90 °C takes about 7 min, the hold 15 min, cooling to 40 °C about
9 min, so standby is READY around 131 min and the swap fires at 150 min.
At 60x that is 2.5 real minutes per half cycle.

Two things to know about the model. Pack and case temperatures are published from the plant tick, so the controller's view of them is never more than one plant tick (1 s real) old at any speed; outlet RH reaches the controller through the `Control Humidity` template sensor, which polls every 5 s, so RH can be up to 5 s real (5 simulated minutes at 60x) behind the plant. And the controller's "not heating" check needs the
standby pack to rise 5 °C within 5 simulated minutes; with the thermal time
constant at its 30 min maximum that requires `Sim Heater Max Temp` roughly 33 °C above `Sim Ambient Temp` at 1x, rising to about 40 °C at
60x because the controller then sees the pack up to one plant tick (one
simulated minute) late. Extreme knob settings can therefore trip that
fault legitimately.

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
| 13 | Fan thermostat | Sim Ambient Temp 40 | Case Temperature rises past 36.5 °C, Case Fan on. Back to 25: fan off once the case falls below 33.5 °C (about 6 simulated minutes, so 6 s real at 60x) and the 60 s minimum run time has passed |
| 14 | Sim speed mid-cycle | Change Sim Speed between 1 and 60 during heating | Counters and temperatures stay continuous; nothing resets |
| 15 | Short probe dropout | During "B heating", Sim Probe B Fault on for about 15 s (three control ticks), then off | Pack B Temperature shows unknown; Heater B stays on throughout; Standby State stays "heating"; no log warning; regen completes normally |
| 16 | Long probe dropout | During "B heating", Sim Probe B Fault on for 40 s, then off | After 25 s: log "Standby probe lost", Heater B off, state still "heating", no fault. On recovery: Heater B on within one tick, Standby Heater Time restarts from 0, no fault, regen completes |

Record anything unexpected with the log excerpt and the knob values.
