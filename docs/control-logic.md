# Control logic

Runs every 5 s in the `interval:` lambda in `esphome/desiccant-dryer.yaml`.

## Roles

- **Active pack**: valve open, heater off. Air flows through it to the ozone
  generator.
- **Standby pack**: valve closed. Cycles through the states below.

`active_pack` (1 = A, 2 = B, 0 = none) and `standby_state` persist across
reboots so a power blip resumes mid-cycle. On first boot (no state) the
controller starts on pack A with B as WET standby.

## Standby state machine

| State | Enter when | Action | Exit when |
|---|---|---|---|
| WET (0) | Just retired from service | Nothing | outlet RH ≥ `arm_rh`, or service time ≥ `max_service_min − regen_max_min` → HEATING |
| HEATING (1) | — | Standby heater on; record start temp/time | Pack temp ≥ `regen_temp` continuously for `regen_hold_min` → COOLING. Or heater time ≥ `regen_max_min` → COOLING (warning logged). |
| COOLING (2) | — | Heater off | Pack temp ≤ `cooldown_temp` → READY |
| READY (3) | — | Nothing | outlet RH ≥ `swap_rh` or service time ≥ `max_service_min` → **swap** |

Swap (`do_swap` script): standby heater off → both valves closed → 500 ms →
standby valve open → roles exchange → the retired pack becomes WET.

## Faults (latched; `Clear Fault` button resets)

- Either pack above `overtemp` → all heaters off.
- Standby heater on for 5 min with pack temp < start + 5 °C → heater off.
While a fault is latched the state machine does nothing; valves stay as they
were (air keeps flowing through the active pack).

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

All defaults are guesses. Old board used a fixed 20 min per pack, so
regeneration at this heater power is known to complete within 20 min.

## Simulation

`Simulate Humidity` switch + `Simulated RH` number. `Control Humidity`
(`ctrl_rh`) is what the logic and display read; it mirrors the SHT45 unless
simulation is on. Simulation never persists across reboot and the display
tags the reading "SIM". Pack temperatures are not simulated — heat the probes.

## Test sequence

1. Dryer Enabled on, Simulate on at 2 % → expect "Air via A, B wet".
2. Slider to 6 % → heater B relay on ("B heating").
3. Warm probe B past `regen_temp` (lower it temporarily if needed), hold for
   `regen_hold_min` → heater off ("B cooling").
4. Let probe B fall below `cooldown_temp` → "B ready".
5. Slider to 12 % → valves swap, "Air via B, A wet".
6. Slider back to 2 %, repeat toward A.
