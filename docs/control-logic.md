# Control logic

Runs every 5 s in the `interval:` lambda in `esphome/packages/base.yaml`.
All three builds share it unchanged; only the sensor sources differ. See
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
four persisted counters:

| Counter | Meaning | Reset by |
|---|---|---|
| `service_elapsed_s` | Time the active pack has been in service | swap, first start, Dryer Enabled off |
| `heat_elapsed_s` | Time the standby heater has run this regen | WET to HEATING, swap, first start, Dryer Enabled off, boot while HEATING, Clear Fault while HEATING |
| `hold_elapsed_s` | Time continuously at or above `regen_temp` | dropping below `regen_temp`, plus all of the above |
| `standby_elapsed_s` | Time in the standby pack's current phase | any change of `standby_state` (detected at the top of the tick), plus everything that resets `heat_elapsed_s` |

`time_scale` is 1.0 in production. The virtual build's "Sim Speed" sets it
so a full cycle runs in minutes. ESPHome flushes changed globals to flash about once a minute, one NVS key
per changed global (two to four keys per minute in production, about seven
on the virtual build because the plant temperatures keep moving), so a
power loss costs at most a minute of each counter.

## Standby state machine

| State | Enter when | Exit when |
|---|---|---|
| WET (0) | Just retired from service, or heater "not heating" fault (code 3) | outlet RH ≥ `arm_rh`, or service time ≥ `max_service_min − regen_max_min` → HEATING |
| HEATING (1) | — | Pack temp ≥ `regen_temp` continuously for `regen_hold_min` → COOLING. Or heater time ≥ `regen_max_min` → COOLING (warning logged). |
| COOLING (2) | — | Pack temp ≤ `cooldown_temp` → READY |
| READY (3) | — | outlet RH ≥ `swap_rh` or service time ≥ `max_service_min` → **swap** |

## Outputs

Outputs are a pure function of state, re-asserted at the end of every tick
by the `apply_outputs` script:

- Active pack: valve on, heater off.
- Standby pack: valve off. Heater on only while HEATING, with no fault, and
  with a pack temperature that was valid within the last 25 s (five ticks;
  the real probes publish every 10 s, so that rides out two missed readings
  and acts on the third). Longer than that turns the heater off; if that
  happens mid-regen the regen restarts when the probe returns, with a
  warning in the log. After a boot the heater stays off until the first
  valid reading.

Because this runs every tick, a reboot re-opens the active valve and
re-lights a heater on the first tick, and a heater cannot stay on while its
probe has been missing for more than 25 s. The tick skips itself while the swap script is running so
it never interferes with the both-valves-closed window.

Swap (`do_swap` script): standby heater off → both valves closed → 500 ms →
standby valve open → roles exchange → the retired pack becomes WET and all
counters reset. `Force Swap` runs the same script from any state; it makes
no readiness check, so it can put a wet pack into service.

## Boot and disable

`on_boot` forces all five outputs off. If the restored state is HEATING, the
heater and hold counters reset and the start temperature is cleared, so the
regen restarts from scratch: the first tick after boot only records the
pack's current temperature and re-lights the heater, and timing starts on
the tick after that. Resuming the old timers would risk a spurious "not
heating" fault after a long outage that let the pack cool. The cost is at
most one extra regen. Boot logs one `cycle` line with the restored state,
and `Force Swap` logs a warning so a manual swap is attributable.

`on_boot` runs at setup priority 700, after switches and restored globals
exist and before intervals start, and sets a `boot_done` flag that the
tick checks first. Without that, ESPHome would run the tick while setup
waits for WiFi, before the outputs were forced off or the counters reset.

`Dryer Enabled` off: all outputs off, `active_pack` cleared, state WET, all
counters zero. A latched fault is left alone. Turning it on again starts on
pack A.

## Faults (latched; `Clear Fault` button resets)

`fault_code` persists across reboots together with its message.

| Code | Message | Trigger | Effect |
|---|---|---|---|
| 1 | Active pack overtemp | active pack > `overtemp` | heaters off |
| 2 | Standby pack overtemp | standby pack > `overtemp` | heaters off, standby → COOLING |
| 3 | Standby heater not heating | heater on 5 min with pack < start + 5 °C and still below `regen_temp` | heaters off, standby → WET |

While a fault is latched the state machine does nothing. Valves stay as they
were, so air keeps flowing through the active pack, and service time keeps
counting. After clearing, what happens to the standby pack depends on the
fault. A pack retired to COOLING by fault 2 becomes READY once it cools; it
is treated as regenerated because it went past `overtemp`, above regen
temperature. A pack sent back to WET by fault 3 never reached regen
temperature, so it is not treated as regenerated: it re-arms by the normal
WET rule and must complete a full regen before it can be READY. If the
heater is still dead, fault 3 latches again 5 minutes after it turns on.
`Standby Heater Time` keeps the failed attempt's value until then.

Only one fault is recorded at a time: a second fault while one is latched is
not logged or shown, though a standby pack that overheats is still retired
to COOLING. Clearing a fault while the standby pack is HEATING restarts that
regen from scratch, exactly as a reboot does, because the pack cooled with
its heater off.

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
| `overtemp` | 110 °C | Hard heater cutoff |

All defaults are guesses. The old board used a fixed 20 min per pack, so
regeneration at this heater power is known to complete within 20 min.

`overtemp` dropped from 120 °C to 110 °C in 1.2.0. Each heater carries a
one-shot thermal fuse (SEFUSE SF129E, Tf 133 °C) clamped to the pack body as
the backstop for a welded relay contact, and a thermal fuse holds
continuously only some way below Tf. The firmware limit has to sit under
that holding temperature so the software always faults first: clearing a
fault is a button press, replacing a blown fuse means opening the pack.
Confirm the datasheet holding figure — if it is near 105 °C, this default
belongs at 100 °C instead. See the heater over-temp cutout notes in
[hardware.md](hardware.md).

These entities are `restore_value: true`, so a unit that has already run
keeps the value it stored. The new default only applies to a fresh install:
on an existing dryer, set `Pack overtemp limit` by hand in Home Assistant.

## Observability

`Dryer Status` ("Air via A, B heating (waiting)"), `Standby State`,
`Service Time`, `Standby Heater Time`, `Regen Hold Time`, `Standby Phase
Time`, `Fault`, `Fault Message`, and a `Restart` button. `Standby Heater
Time` and `Regen Hold Time` hold their final value through COOLING and READY
so a regen's duration stays visible in HA history; the swap resets them.
`Standby Phase Time` is what the display shows under the standby pack; it
resets on every phase change, so after a swap it restarts from zero as WET.
Transitions are logged under the `cycle` tag at INFO, faults at ERROR.

## Humidity override (all builds)

`Override Humidity` switch + `Override RH` number. `Control Humidity`
(`ctrl_rh`) is what the logic and display read; it mirrors the outlet sensor
unless the override is on, when it reads `Override RH` instead. The override
never persists across reboot and the display shows an "OVR" badge while it is
on. It replaces a reading rather than simulating one: on the virtual build it
overrides the plant model's rising RH. Pack temperatures have no override; on
the real unit heat the probes, on the virtual build use the plant knobs.

## Test sequence on the real unit

1. Dryer Enabled on, Override Humidity on at 2 % → expect "Air via A, B wet".
2. Slider to 6 % → heater B relay on ("B heating").
3. Warm probe B past `regen_temp` (lower it temporarily if needed), hold for
   `regen_hold_min` → heater off ("B cooling").
4. Let probe B fall below `cooldown_temp` → "B ready".
5. Slider to 12 % → valves swap, air via B. RH is still above `arm_rh`, so
   A skips WET on the next tick (it may show "A wet" for up to 5 s): expect
   "Air via B, A heating (waiting)" with the heater A relay on.
6. Slider back to 2 % ("(waiting)" clears), then repeat steps 3–5 with
   probe A.
