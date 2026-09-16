# Verification plan

How each failure mode in `docs/failure-modes.md` (the threat assessment) is
verified, and how much of that verification can run without a human. The
catalogue says *what can go wrong*; this document says *how we prove the
firmware or the design handles it*. Every one of the catalogue's rows is
covered by exactly one test below.

## Test types

The type is decided by what the test can control and observe. That decides
the harness, so it also decides how automated the test can be.

| Type | What it proves | Harness | Automated? |
|---|---|---|---|
| **logic** | Given sensor values and time, the state machine does the right thing (arms, regens, swaps, faults, boots safe). | `host`: the host or virtual build, driven over the native API with the `Sim *` knobs and simulated time | Yes, in CI |
| **detect** | A sensor directly reports a fault (NaN, 85 °C, frozen, pinned RH) and the firmware acts on it. | `host` | Yes, in CI |
| **infer** | Nothing reports the fault, but other sensors betray it (temperature still rising with the heater off, the wrong pack warming). The plant model carries the fault; the firmware must notice within a bound. | `host` | Yes, in CI. Most are ✱ gaps today, so these tests start red and the firmware check turns them green |
| **lint** | A design invariant is present in the built configuration: interlocks, `restore_mode: ALWAYS_OFF`, no `Sim` entities in production, tunable ranges under the fuse limit, watchdog and panic handler set. | `ci-lint`: a script over `esphome config` output and the YAML | Yes, in CI, on every PR |
| **physical** | Something a person must look at or measure: fuse fitted, creepage, earth bonds, probe placement. | `checklist`: a stage of `docs/inspection-checklist.md` | No. The signed-off stage is the pass |
| **hil** | Needs the real board or an energised rig: the watchdog really drops the relays, the buck really holds 5 V, a relay really welds. | `bench` (mains off) or `live` (energised, instrumented) | Later, with a small observer rig |

## Status vocabulary

| Status | Meaning |
|---|---|
| `green` | Expected to pass on today's firmware. A failure is a regression. |
| `red` | Expected to fail today: the catalogue row is a ✱ gap, or the test needs a plant-model knob that does not exist yet. The test is written first; the fix turns it green. |
| `manual` | Physical. Passes when the checklist stage is signed off. |
| `later` | Hardware in the loop. Defined now, run when the rig exists. |

## Harness

**Host runner.** `tests/run_cases.py` starts the host build headless,
connects over the ESPHome native API, and executes each case in
`tests/cases/` that is not `harness: ci-lint`: set knobs, advance simulated
time via `Sim Speed`, assert entity states. Cases are data, not code, so a
coding agent can add one without touching the runner. The runner exits
non-zero if any `green` case fails or any `red` case unexpectedly passes
(that means a gap closed and the case status must be updated to `green`).
It runs in the `host-cases` job in `build.yml`, beside the compile jobs,
inside the same ESPHome image.

Locally (needs `brew install sdl2` and an `esphome/secrets.yaml`, as
`docs/host-preview.md` describes):

```bash
tests/run_cases.py                  # every host case; compiles the host build first
tests/run_cases.py T-B01 --no-build # one case, reusing the compiled binary
```

Each case gets its own process and its own prefs directory, so persisted
globals and `Sim` knobs never leak from one case into the next; `restart`
presses the Restart button and runs the binary again against the same
prefs, which is what the board does on a reboot. `SDL_VIDEODRIVER=dummy`
keeps the display compiled in but windowless, so no headless build variant
is needed. The plant model's clock only runs while the process does, so a
case's wall-clock cost is its simulated minutes divided by `Sim Speed`
(maximum 60, i.e. one real second per simulated minute).

A case that references a `Sim *` knob the plant model does not have yet is
skipped with that knob named, not failed. The knobs under "New Sim knobs"
below are all still missing, so the cases needing them are skipped.

**Config lint.** `tests/lint_config.py` runs `esphome config` for each
case's `selectors` and evaluates its `assert` lines against the dump. It
runs every case file with `harness: ci-lint`, and exits non-zero if a
`green` case fails or a `red` case passes. It runs in the `lint-config` job
in `build.yml`, beside the compile jobs, inside the same ESPHome image.

A `lint` case adds `selectors` and `assert` instead of `setup`/`steps`:

```yaml
# tests/cases/T-B20.yaml
id: T-B20
covers: [B-20, J-09]
type: lint
status: green
harness: ci-lint
selectors: [esphome/desiccant-dryer.yaml, esphome/desiccant-dryer-hw-test.yaml]
assert:
  - number overtemp has max_value <= 118
  - number overtemp has initial_value <= max_value
```

Assertion lines are joined with ` and ` and take one of three shapes, all
resolved against the `id:` in the config dump:

| Shape | Example |
|---|---|
| `<domain> <id> has <key> [<op>] <value>` | `number overtemp has max_value <= 118` |
| `every <domain> in [<ids>] has <key> [<op>] <value>` | `every switch in [heater_a, heater_b] has restore_mode ALWAYS_OFF` |
| `<id>.<key> includes <id>` | `heater_a.interlock includes heater_b` |

`<op>` is `<=`, `>=`, `<`, `>` or omitted for equality. A `<value>` that
names another key of the same entity compares the two (`initial_value <=
max_value`).

**Still needed**: the plant-model knobs listed under "New Sim knobs"
below. Until they exist the cases using them are skipped, not run.

## Case format

One YAML file per automated test, named after the test ID:

```yaml
# tests/cases/T-B02.yaml
id: T-B02
covers: [B-02, A-01]
type: infer
status: red            # needs Sim Relay Stuck On A, and the firmware check
setup:                 # entity name: value, applied before steps
  Sim Speed: 60        # 1 real second = 1 simulated minute
  Sim Breakthrough Time: 5
  Dryer Enabled: on
steps:
  - wait_until: {Standby State: heating}
    timeout_sim_min: 30
  - set: {Sim Relay Stuck On A: on}
  - wait_until: {Standby State: cooling}
    timeout_sim_min: 60
  - wait_sim_min: 10
  - expect:
      Heater A: off
      Fault Code: {not: 0}
```

Step verbs: `set`, `wait_sim_min`, `wait_until` (with `timeout_sim_min`),
`expect`, `press` (a button entity), `restart` (reboot the host build and
reconnect; persisted globals survive, `rh_override` must not). Expectation
values are literals or `{not: v}`, `{min: v}`, `{max: v}`,
`{within_ticks: n, ...}`.

## Rules

- Test IDs are `T-` plus the primary catalogue ID without its dash. A test
  that covers several rows is named after the highest-priority one. IDs are
  never reused or renumbered.
- Every catalogue row is in exactly one test's Covers. Adding a catalogue
  row means adding it to an existing test's Covers or adding a new test in
  the same change; `scripts/failure-modes-report.py` fails if a row is
  uncovered.
- A `red` test that passes is a signal, not a success: change its status to
  `green` in the same PR that closed the gap.
- `physical` tests point at a checklist stage and are never marked green
  by software.

## Tests

| Test | Type | Covers | Harness | Inject | Expect | Status |
|---|---|---|---|---|---|---|
| T-B02 | infer | B-02, A-01 | host | `Sim Relay Stuck On A` on while standby A is HEATING; wait until `Standby State` leaves HEATING; then 10 sim min more | heater A commanded off and pack A still rising ⇒ `Fault Code` set, both heaters off within 2 ticks | red |
| T-A02 | hil | A-02 | bench | On the bench rig (mains off), fault the PN2222A driver stage for heater A to hold collector-emitter shorted, command `Heater A` off | relay A stays engaged despite GPIO/coil off ⇒ confirms no software detects a shorted driver | later |
| T-A03 | hil | A-03, H-02, H-19 | bench | Flash a build with a lambda that spins in the interval script past the watchdog period; power up normally | ESP-IDF task watchdog reboots the board and both heater relays de-energise within one watchdog period | later |
| T-A04 | physical | A-04 | checklist | Stage 1 board assembly check: inspect both relay-driver transistor markings and pinout under magnification | both read `PN2222A` (E-B-C); a `P2N2222A` (C-B-E) is rejected before power-up | manual |
| T-A05 | lint | A-05 | ci-lint | Dump `esphome config` for `desiccant-dryer.yaml`; grep the heater_a/heater_b switch blocks | both list the other as `interlock:` with `interlock_wait_time: 500ms` set | green |
| T-A07 | physical | A-07 | checklist | Stage 2 mains heater path check: trace each heater's switched-L lead from relay NO pin to element | one SF129E thermal fuse in series per pack, on the pack it protects, no jumper | manual |
| T-A08 | physical | A-08 | checklist | Stage 2 check: inspect SF129E clamp on each pack body next to its DS18B20 | clamped metal-to-metal on the pack body, not the heater sheath, does not move by hand | manual |
| T-A09 | physical | A-09 | checklist | Stage 2 check: continuity-test each relay's COM/NO/NC with coil unpowered | switched L leaves the relay's NO pin; NC pin is empty | manual |
| T-A10 | physical | A-10 | checklist | Stage 2 check: trace inlet L/N against plug polarity through F1 and the relays | the switched conductor is line; neutral runs straight through unswitched | manual |
| T-A11 | physical | A-11 | checklist | Stage 2 check: inspect fuse F1's markings and holder | 5x20mm T3.15A time-delay fitted in a covered holder, not bridged or fast-blow | manual |
| T-A12 | physical | A-12 | checklist | Stage 2 check: continuity-test the 24V PSU's L feed with F1 removed | no continuity from inlet L with F1 pulled; PSU L comes from the fused side only | manual |
| T-A13 | hil | A-13 | live | Live rig: short a heater element to its sheath, or partially short it, with the sheath bonded to earth via a GFCI-protected feed | over-current trips upstream protection, or the sheath is confirmed live, showing why the PE bond (A-14) is required | later |
| T-A14 | physical | A-14 | checklist | Stage 2/3 check: verify heater sheath-to-chassis PE bond continuity | low-resistance bond present from each heater sheath to chassis PE | manual |
| T-A15 | physical | A-15 | checklist | Stage 3 enclosure check: measure pad-to-pad creepage between mains and logic rows on the protoboard | at least 5.6mm creepage maintained everywhere, less only on plated pads with acceptance noted | manual |
| T-A16 | physical | A-16 | checklist | Stage 3 check: inspect every mains screw terminal for ferrule use and torque | all stranded mains conductors ferruled and torqued to spec, none pulls free by hand | manual |
| T-A17 | physical | A-17 | checklist | Stage 3 check: inspect mains conductor insulation rating near each pack | rated for 90 to 133C continuous, no chafing against the pack body | manual |
| T-A18 | hil | A-18 | bench | Bench rig, mains off: omit or reverse the flyback diode across a relay coil, cycle the relay 50 times | PN2222A survives or fails predictably, confirming the diode is required and correctly oriented in production | later |
| T-A19 | hil | A-19, A-20 | live | Live rig: cycle a heater relay several thousand times under its 1A load, monitor contact resistance and arcing | contact resistance rise or visible pitting flags approaching open/weld failure before it happens in the field | later |
| T-A21 | hil | A-21 | bench | Bench rig, mains off: open-circuit a relay coil, command that heater on | relay never engages; `Heater A/B` switch state and pack temperature disagree, confirming no coil-continuity check exists | later |
| T-A22 | hil | A-22 | live | Live rig: open-circuit a heater element, command it on for a full regen | no heat produced; existing "not heating" fault (B-01/I-04) is the only thing that notices | later |
| T-A23 | hil | A-23 | bench | Bench rig, mains off: open the PN2222A base resistor or 10k pulldown, toggle the heater switch | relay floats or chatters instead of switching cleanly | later |
| T-A24 | hil | A-24 | bench | Bench rig, mains off: unplug the 4-way JST-XH relay harness, or open one conductor | both heaters dead, or one dead depending on which conductor opened | later |
| T-A25 | hil | A-25 | bench | Bench rig: load both relay coils plus a WiFi TX burst simultaneously, monitor the 5V rail under the buck | rail sag causes audible relay chatter if margin is insufficient | later |
| T-A26 | logic | A-26 | host | `Sim Heater Max Temp` set to 95 (near `regen_temp` 90), `Sim Thermal Time Constant` 20; run a full regen | heater runs to `regen_max_min` without reaching hold, standby goes to COOLING via the logged timeout warning | green |
| T-A27 | hil | A-27 | live | Live rig: trip a pack's SF129E once (over-temperature event), then command that pack's heater on again | heater stays commanded but pack never heats; dryer appears "not heating" (fault 3) with no distinct fuse-blown indication | later |
| T-A28 | physical | A-28 | checklist | Stage 1 check: inspect the on-board blue LED wired to GPIO13 | LED only reflects heater A relay command, nothing else shares that net | manual |
| T-A29 | hil | A-29 | bench | Bench rig: reboot the board repeatedly while probing GPIO13 with a scope | no millisecond-scale pulse on GPIO13 during the boot/strapping window | later |
| T-A30 | physical | A-30 | checklist | Design review item: confirm whether a heater current sense is fitted or the decision against one is recorded | current sense fitted, or `docs/hardware.md` records the reasoned decision not to fit one | manual |
| T-A31 | physical | A-31 | checklist | Design review item: confirm a self-resetting cutout ahead of the SF129E, or a recorded rationale for relying on the one-shot fuse alone | resettable cutout fitted, or `docs/hardware.md` records why the one-shot fuse alone is accepted | manual |
| T-B01 | logic | B-01 | host | `Sim Heater Fault` on for standby A; wait 5 sim min, then continue watching a second run where temp rises 3C then flatlines | both cases latch fault 3 (not heating) within one tick of the 5 min mark, heater off, standby to WET | green |
| T-I02 | infer | I-02, B-03 | host | `Sim Heater Max Temp` 150, `Sim Thermal Time Constant` 1 (near-instant rise) on standby A; watch pack A temp approach `overtemp` | a rate-of-rise or thermal-model check trips before pack temperature reaches `overtemp`: `Fault` on, both heaters off | red |
| T-B04 | detect | B-04 | host | `Sim Manual Temps` on, `Sim Pack A Temp` 130 with pack A active, then `Sim Probe A Fault` on so `pack_a_temp` publishes NaN | active-pack probe NaN beyond the probe timeout while any heater is on: both heaters off and `Fault` on within 2 ticks | red |
| T-B05 | hil | B-05 | bench | Bench rig, mains off: swap the two DS18B20 leads (or their `address:` mapping) between packs A and B, warm pack A with a heat gun | `pack_b_temp` moves instead of `pack_a_temp`, confirming the mis-mapping and that nothing in firmware catches it | later |
| T-B06 | detect | B-06 | host | `Sim Probe 85C` on for pack A while pack A is standby HEATING | an exact 85.0 from a cold pack is rejected as the power-on sentinel: reading treated as unavailable, `Regen Hold Time` stays 0 | red |
| T-B07 | detect | B-07 | host | `Sim Probe Garbage A` on for pack A (publishes -127C) while pack A is standby | -127 (or any value outside -20 to 150) is rejected: reading treated as unavailable, no COOLING to READY transition on it | red |
| T-B08 | infer | B-08, I-25 | host | `Sim Manual Temps` on, `Sim Pack A Temp` pinned at 95C (above `regen_temp`) through a full HEATING and overtemp window | a reading unchanged to the bit for longer than the staleness window while a heater is on is treated as unavailable: heater off, `Fault` on | red |
| T-B09 | logic | B-09, I-17 | host | `Sim Probe A Fault` toggled on for 3 ticks then off while standby A is HEATING near `regen_temp` | heater A stays commanded through the gap (`sb_nan_ticks` tolerance), regen continues uninterrupted once the probe returns | green |
| T-B10 | logic | B-10, B-11 | host | `Sim Probe A Fault`, `Sim Probe B Fault` and `Sim Case Probe Fault` all on simultaneously for 30 sim min | standby heater drops after the tolerance window, no crash, state machine holds safely with all three probes NaN | green |
| T-B12 | physical | B-12 | checklist | Stage 2/4 check: inspect probe lead insulation rating near each pack body | rated 100C or higher, no chafing against the heater sheath or pack | manual |
| T-B13 | hil | B-13 | live | Live rig: loosen a probe's thermal clamp so it reads air temperature instead of the pack body, run a regen | heater over-runs to `regen_max_min` or overtemp instead of a clean regen-complete | later |
| T-B14 | physical | B-14 | checklist | Stage 4 sensor placement check: verify each DS18B20 is clamped to the pack body, not the heater sheath | probe contacts the pack body directly; sheath-mounted probes are rejected | manual |
| T-B15 | hil | B-15 | live | Live rig: run a regen and watch for probe self-heating or radiant pickup from the heater artificially extending the apparent hold | reported hold time exceeds the pack's true thermal hold, a false "regen complete" risk | later |
| T-B16 | detect | B-16 | host | `Sim Case Probe Fault` on (case_temp NaN) while ambient is warm enough that cooling would normally be called for | `case_temp` NaN forces the fan on within 2 ticks (fail-safe) and logs a warning | red |
| T-B17 | hil | B-17 | bench | Bench rig: substitute a counterfeit DS18B20 above 85C and compare its reading against a reference thermometer | accuracy degrades enough to misjudge the regen hold as complete early or late | later |
| T-B18 | infer | B-18, I-08 | host | `Sim Ambient Temp` set to 45 (above `cooldown_temp` 40) for the full test; let standby complete HEATING and enter COOLING | standby stuck below READY with service past `max_service_min` forces a swap with a warning or raises `Fault`; the active pack never runs indefinitely | red |
| T-B19 | logic | B-19 | host | Write a stored `Pack overtemp limit` above the 118C maximum (a unit commissioned under the 125C range), then reboot | the second `on_boot` block re-clamps the restored value to 118C and logs a warning; a stored value inside the range (say 115C) still survives the reboot unchanged. `tests/cases/T-B19.yaml` covers only the in-range half: seeding a stored value above the maximum needs an NVS write no harness can do yet | green |
| T-B20 | lint | B-20, J-09 | ci-lint | Script parses `overtemp` number's `min_value`/`max_value` from `esphome config` output | `Pack overtemp limit` `max_value` is at or below 118 in the config dump, so a value above the SF129E holding temperature cannot be set | green |
| T-B21 | logic | B-21 | host | Set `Regen temp` to 115 (above `overtemp` 110) via the API, run standby A into HEATING | fault 1 (active-pack unrelated) does not apply; standby's own overtemp path is not separately checked here, so it heats until `overtemp` trips fault 2 instead of ever reaching a "regen complete" hold | green |
| T-B22 | logic | B-22 | host | `Sim Probe A Fault` and `Sim Probe B Fault` both on while pack A is standby HEATING; wait 30s | heater A cut after the tolerance window elapses; `Fault Code` remains 0, no fault latched despite the stall | green |
| T-B23 | infer | B-23 | host | `Sim Manual Temps` on, raise `Sim Pack A Temp` while pack A is active (heater off) and pack B is standby HEATING | active pack rising more than 5 C over 5 sim min with its heater commanded off raises `Fault` and turns both heaters off | red |
| T-B24 | infer | B-24 | host | `Sim Manual Temps` on, jump `Sim Pack A Temp` by 40C between two consecutive 10s samples | a step larger than 20 C between consecutive samples is discarded and logged; no state transition or fault is taken on it | red |
| T-B25 | infer | B-25 | host | Cold boot with `Sim Manual Temps` on and `Sim Pack A Temp` at 60C while B and case sit at 25C ambient | a spread above 10 C between the three probes at cold boot raises `Fault` before any heater starts | red |
| T-B26 | infer | B-26 | host | `Sim Probes Swapped` on (pack B's sensor mirrors pack A's plant value) while heating pack B | `pack_b_temp` tracking `pack_a_temp` within 1 C while only heater A is on raises `Fault` and turns both heaters off | red |
| T-C01 | detect | C-01 | host | `Sim RH Fault` on (air_rh NaN) for 20 sim min while the dryer is running normally | RH NaN beyond a timeout (default 5 min) raises `Fault` or a warning entity and `Dryer Status` names the sensor loss | red |
| T-C02 | detect | C-02 | host | `Sim RH Frozen` on while service time passes the point breakthrough should occur | RH unchanged to the resolution beyond a timeout while air flows is treated as unavailable, with the same handling as T-C01 | red |
| T-C03 | physical | C-03 | checklist | Stage 4 check: verify SHT45 mounting position relative to the valves and airflow path | sensor sits downstream of both valves in moving outlet air, not upstream or in a stagnant pocket | manual |
| T-C04 | hil | C-04 | live | Live rig: expose the SHT45 to condensation or simulated ozone-generator backflow | reading saturates high; dryer shows endless "(waiting)" or swaps prematurely | later |
| T-C05 | hil | C-05 | live | Live rig: run extended ozone/contaminant exposure on the SHT45 and track baseline drift over weeks | baseline RH creeps upward past `arm_rh`, heater runs near-continuously | later |
| T-C06 | hil | C-06 | bench | Bench rig: offset the SHT45's own temperature reading and compare RH compensation against a reference | RH compensation shifts with the temperature error, moving the effective baseline | later |
| T-C07 | logic | C-07, C-08, L-03 | host | Turn `Override Humidity` on with `Override RH` set to 8%, then press `Restart` | display shows the "OVR" badge immediately while on; after reboot `Override Humidity` is off (`ALWAYS_OFF`) and the badge is gone until re-enabled | green |
| T-C09 | lint | C-09 | ci-lint | Script reads `hw-real.yaml` and asserts `sliding_window_moving_average` window size on the RH sensor | window is 3 samples, consistent with the documented 20 to 30s worst-case breakthrough delay | green |
| T-C10 | logic | C-10 | host | `Sim Breakthrough Time` 1 min, `Sim RH Rise Rate` 5%/min, run standby from WET | RH sits near the noisy 0 to 10% floor then rises sharply past `arm_rh` in under a minute once breakthrough starts | green |
| T-C11 | logic | C-11, I-16 | host | Set `Arm RH` to 15% and `Swap RH` to 10% via the API (also test `Cooldown temp` above `Regen temp`, and `Regen hold time` above `Regen max heater time`) | a write that breaks `arm_rh` < `swap_rh`, `cooldown_temp` < `regen_temp` or `regen_hold_min` <= `regen_max_min` is clamped or rejected and logged | red |
| T-C12 | hil | C-12 | bench | Bench rig: run the I2C bus at 100kHz over the full Qwiic cable length with only the breakout's own pullups | bus errors appear under marginal conditions, confirming no board-side pullups exist | later |
| T-C13 | lint | C-13 | ci-lint | Script parses `hw-real.yaml`'s `sht4x` sensor block for `heater_max_duration`/enable flags | SHT45 heater feature is not enabled | green |
| T-C14 | detect | C-14 | host | `Override Humidity` on, `Override RH` set to 100% for 20 sim min | an exact 0 or 100 % held for 3 samples is treated as unavailable; no arm or swap is taken on it | red |
| T-D01 | infer | D-01, D-04, D-17 | host | `Sim Valve Stuck A` turned on while valve A is open and a swap is commanded (valve B told to open) | both valves are never commanded open together in any state, swap, fault or manual toggle; with `Sim Valve Stuck A` latched open, the no-improvement check (T-I22) raises `Fault` after the next swap | red |
| T-D02 | infer | D-02, D-05 | host | `Sim Valve Stuck A` turned on while valve A is closed, then standby A heater is commanded on | with `Sim Valve Stuck A` closed and heater A on, the rate-of-rise check (T-I02) trips before `overtemp`; heater off, `Fault` on | red |
| T-D03 | logic | D-03, F-17, I-19 | host | Press `Force Swap`, then power-cycle the host build mid-way through the 500ms both-valves-closed window | after boot, the retiring pack's valve reopens within 5s and no half-swapped or stuck-both-closed state persists, even if `service_elapsed_s` is already above `Max service time` | green |
| T-D06 | hil | D-06 | live | Live rig: run a valve coil (rated 50C) mounted on a 90C pack for an extended regen | coil insulation is stressed toward failure at sustained pack-body temperature | later |
| T-D07 | hil | D-07 | bench | Bench rig: swap valve A/B terminal wiring, run a normal cycle | air flows through the pack currently being heated instead of the active pack | later |
| T-D08 | hil | D-08 | bench | Bench rig, mains off equivalent (24V only): open a valve MOSFET's gate pulldown, power up | valve floats partially open during boot/reset instead of staying closed | later |
| T-D09 | hil | D-09 | bench | Bench rig: short a valve coil and observe the IRLZ44N at 3.3V gate drive | MOSFET heats with no current limiting on the 24V rail | later |
| T-D10 | hil | D-10 | bench | Bench rig: omit or reverse a valve's flyback diode, cycle it repeatedly | MOSFET shows avalanche stress, trending toward a short (D-01/D-04 symptom) | later |
| T-D11 | hil | D-11 | bench | Bench rig: open-circuit a valve coil, command that pack into service | pack can never take air; a swap leaves the outlet effectively closed | later |
| T-D12 | hil | D-12 | live | Live rig: block a pack's purge vent during regen | regen exhaust cannot escape; pack overheats or the desiccant stays wet | later |
| T-D13 | hil | D-13 | live | Live rig: block inlet air or stop the upstream compressor | dryer keeps cycling on humidity readings even though no air is moving | later |
| T-D14 | hil | D-14 | live | Live rig: introduce a small leak between the two pack manifolds | wet air bypasses the active pack into the outlet | later |
| T-D15 | logic | D-15 | host | Press `Force Swap` while the standby pack is WET, then again while HEATING | swap proceeds immediately in both cases; no readiness check blocks putting a wet or hot pack into service | green |
| T-D16 | logic | D-16 | host | Trigger a normal READY-to-swap transition; log heater and valve switch timestamps during `do_swap` | the retiring pack's heater is commanded off strictly before its valve closes, in that order | green |
| T-E01 | hil | E-01, E-02 | bench | Bench rig: open-circuit the fan (bearing/coil) for one run, then short its MOSFET for a second run | run 1: enclosure temp climbs unchecked; run 2: fan runs continuously, masking a later real stall | later |
| T-E03 | hil | E-03 | live | Live rig: detach the case DS18B20 from its mount so it reads ambient instead of the hot zone, heat the enclosure | `case_temp` stays low while the enclosure is genuinely hot; fan thermostat never starts | later |
| T-E05 | logic | E-05 | host | Toggle `Dryer Enabled` off then on while a fault is separately latched | thermostat mode goes to `OFF` then back to `COOL`; the latched fault never touches the thermostat and cooling resumes | green |
| T-E06 | hil | E-06 | live | Live rig: block enclosure vents or reverse the fan's mounting direction | airflow through the enclosure drops despite the fan running | later |
| T-E07 | hil | E-07 | live | Live rig: run the enclosure above the relay's rated ambient for an extended period | relay contact resistance measurably increases, raising weld risk | later |
| T-E08 | physical | E-08 | checklist | Stage 3 check: assess condensation risk for a cold start in a humid room across mains creepage | enclosure design or siting avoids condensation forming across mains-rated spacing | manual |
| T-E09 | physical | E-09 | checklist | Stage 7 service-visit check: inspect for dust, desiccant fines or ozone residue on relay contacts and traces | no visible corrosion or debris accumulation since the last visit | manual |
| T-E10 | hil | E-10 | bench | Bench rig: wire a substitute 24V fan reverse-polarity | fan fails to spin or is damaged if the substitute part lacks polarity protection | later |
| T-E11 | infer | E-11 | host | `Sim Fan Stalled` on (case thermal model ignores fan/cooling) while ambient is warm enough to call for cooling, for 30 sim min | `case_temp` rising for 10 sim min while the thermostat calls COOL raises `Fault` (fan failure) and turns both heaters off | red |
| T-F01 | physical | F-01 | checklist | Design review item: confirm the LRS-35-24 is Class I with FG bonded as the sole mains-fault protection | FG/PE bonding is the documented protection against an internal short to mains | manual |
| T-F02 | physical | F-02 | checklist | Stage 3 check: continuity-test PSU FG to chassis PE | low-resistance bond present; chassis cannot float on a primary-side fault | manual |
| T-F03 | hil | F-03 | bench | Bench rig, 24V only: reverse the 24V input polarity briefly | confirms whether protection exists or the buck/MOSFETs are destroyed | later |
| T-F04 | hil | F-04 | bench | Bench rig: raise the PSU trimmer above 24V rated output | buck input rating is approached or exceeded | later |
| T-F05 | hil | F-05 | bench | Bench rig: short a valve or fan output momentarily | PSU enters hiccup mode, controller reboots repeatedly | later |
| T-F06 | hil | F-06 | live | Live rig: cold-start the dryer and measure inrush current at F1 | the specified time-delay fuse rides through the ~45A inrush without opening | later |
| T-F07 | hil | F-07, F-08 | bench | Bench rig: adjust the MP1584 trimmer to both extremes and measure output | high: exceeds AP2112K/relay coil ratings; low: relay coils drop out or ESP browns out | later |
| T-F09 | hil | F-09 | bench | Bench rig: scope the MP1584 output into the ESP's USB power net under load | ripple/oscillation levels correlate with random resets or WiFi drops | later |
| T-F10 | hil | F-10 | bench | Bench rig: connect a USB-C host cable with JP-USB fitted | buck attempts to feed the host port at up to 4 to 4.7A | later |
| T-F11 | hil | F-11 | bench | Bench rig: pull JP-USB while powered from USB for programming | relay coils lose 5V; outputs appear commanded on but relays stay dead | later |
| T-F12 | hil | F-12 | bench | Bench rig: fit the 5V net Schottky reversed | ESP is unpowered, or a connected host back-feeds the coil rail | later |
| T-F13 | physical | F-13 | checklist | Stage 1 check: inspect both 100uF electrolytic capacitors' polarity marking against the board silkscreen | stripe (negative) matches the GND side on each board, no bulge or vent residue | manual |
| T-F14 | hil | F-14 | bench | Bench rig: load the 3.3V LDO with WiFi TX bursts plus backlight plus 1-wire simultaneously | current approaches the 310mA peak, risking brownout | later |
| T-F15 | lint | F-15, J-03 | ci-lint | Script dumps `esphome config` and greps every GPIO output switch (heater_a/b, valve_a/b, case_fan) | all five list `restore_mode: ALWAYS_OFF`, matching the GPIO reset-default-low invariant | green |
| T-F16 | hil | F-16 | live | Live rig: induce a mains dip long enough to reboot the ESP but not drop relay coil magnetism | brief mismatch window between relay's physical state and firmware's assumed state | later |
| T-F18 | hil | F-18 | bench | Bench rig: measure noise on 1-wire/I2C with PSU 0V, PE, USB host ground and the display cable all bonded | ground loop coupling visible as noise on sensor buses | later |
| T-F19 | physical | F-19 | checklist | Stage 1 check: verify nothing is wired to the ESP's BAT/LiPo charger pin | BAT pin isolated; no path from the 5V bus other than through the Schottky and JP-USB | manual |
| T-F20 | infer | F-20 | host | `Sim Valve Stuck A` on (valve never actually moves) representing a dead 24V rail, run a normal swap | loss of the 24 V rail is detected, either by a rail-sense input or because valves not moving fails the T-I22 no-improvement check within one service period | red |
| T-G01 | hil | G-01 | bench | Bench rig: seat the board one pin off on the 12-pin header (GPIO8/GPIO4 vs Feather "9"/"5" positions) | wrong physical outputs are driven relative to the intended pin map | later |
| T-G02 | physical | G-02 | checklist | Stage 1 check: verify ESP32-S2 module seating in both sockets | USB-C and antenna ends match silkscreen, no empty end pin, no bent pin | manual |
| T-G03 | physical | G-03 | checklist | Stage 1 check: verify display cable pinout against module type (Waveshare vs LCDWIKI) | header order matches board 1:1; a straight-through cable on the wrong module type is rejected | manual |
| T-G04 | physical | G-04 | checklist | Stage 1 check: measure BLK-to-VCC resistance on the display backlight input | about 10k ohm, confirming an on-module transistor rather than a bare LED on GPIO17 | manual |
| T-G05 | physical | G-05 | checklist | Stage 1 check: verify the SHT45 Qwiic cable pinout and wiring colours | genuine Qwiic 4-pin JST-SH, black to GND, red to 3.3V | manual |
| T-G06 | hil | G-06 | bench | Bench rig: loosen a sensor's screw terminal deliberately | intermittent probe readings appear, distinct from bus-level CRC noise (B-09) | later |
| T-G07 | physical | G-07 | checklist | Stage 7 service-visit check: check header and terminal seating for vibration-induced loosening | all headers and terminals remain firmly seated | manual |
| T-G08 | physical | G-08 | checklist | Stage 1 check: inspect solder side under magnification around GPIO12/13 and GPIO10/11 | no bridge between adjacent heater or valve pins, or to any mains pad | manual |
| T-G09 | physical | G-09 | checklist | Stage 2/3 check: verify no mains-rated wire lands in a 24V-rated terminal block or vice versa | terminal families are not cross-populated despite matching 5.08mm pitch | manual |
| T-G10 | physical | G-10 | checklist | Stage 3 check: verify mains wiring routing relative to 1-wire and SPI runs | mains kept clear of signal wiring; no induced-noise routing | manual |
| T-G11 | hil | G-11 | bench | Bench rig: stress-test the 24V bus trace/wire under a wiring-error scenario (no 24V fuse present) | trace or wire heats under an overcurrent condition with nothing to interrupt it | later |
| T-G12 | physical | G-12 | checklist | Stage 3 check: verify enclosure earthing and mains lead routing away from sharp edges | enclosure bonded to earth; no chafe point on the mains lead | manual |
| T-G13 | physical | G-13 | checklist | Stage 3 check: verify strain relief on heater tails at each pack | strain relief present; no conductor flex fatigue point at 90C | manual |
| T-G14 | physical | G-14 | checklist | Stage 2 check: pull-test thermal fuse and heater tail crimps | correctly crimped (no solder/twist-tape), sleeved for 133C+, holds under pull | manual |
| T-G15 | physical | G-15 | checklist | Stage 1 check: verify MP1584 buck module fit and measure its output preset | sits flat on its own header, no forced pins; output 5.00 to 5.10V with JP-USB removed | manual |
| T-G16 | physical | G-16 | checklist | Stage 3/7 check: verify packs, heater tails, probe leads and valves are permanently labelled A/B | every A/B pair is labelled and matches the wiring diagram at reassembly | manual |
| T-H03 | hil | H-03, K-08, K-09 | bench | Bench rig: load the web server, TLS/OTA and API client connections simultaneously while forcing WiFi reconnect storms | heap pressure and loop time rise; the 60s `dt` clamp hides how long a heater actually ran uncontrolled during the stall | later |
| T-H04 | hil | H-04 | bench | Bench rig: deliberately deepen recursion in a display-draw lambda to provoke a stack overflow | reset occurs with outputs held at their last state until reboot completes | later |
| T-H05 | lint | H-05 | ci-lint | Script inspects the interval lambda's `dt_real`/`dt` computation for unsigned-subtraction wraparound safety | `dt_real` is computed and clamped so a `millis()` wrap cannot produce a negative or huge `dt` | green |
| T-H06 | hil | H-06 | bench | Bench rig: trigger a long OTA or slow `/screen.png` fetch during active regen timing | interval tick is blocked long enough that heater timers under-count real elapsed time | later |
| T-H07 | hil | H-07 | bench | Bench rig: force repeated boot failures until ESP-IDF safe mode is entered | controller runs in safe mode with no control logic and no explicit output assertion | later |
| T-H08 | hil | H-08 | bench | Bench rig: OTA a deliberately broken image and observe relay pin state during the bootloader/partition switch | relay pins hold whatever state existed at flash time through the switch | later |
| T-H09 | hil | H-09 | bench | Bench rig: cut power mid-OTA | device falls back to the previous partition or enters safe mode (H-07) | later |
| T-H10 | hil | H-10 | bench | Bench rig: corrupt the NVS region backing `heat_start_temp` or an elapsed-second counter, then boot | `on_boot` only clamps `active_pack`, `standby_state` and `fault_code`; a garbage `heat_start_temp` or negative counter drives regen timing wrong | later |
| T-H12 | hil | H-12 | bench | Bench rig: enter UART0 download mode / deep reset while probing relay/valve GPIOs | pins glitch briefly during the mode transition | later |
| T-H13 | logic | H-13 | host | Trigger two rapid state changes that both call `apply_outputs` within one tick (e.g. overtemp fault plus a manual switch write) | `mode: single` drops the overlapping call cleanly; final output state matches the latest state, nothing left half-applied | green |
| T-H14 | logic | H-14 | host | Force an overtemp fault transition and poll `Heater A`/`Heater B` switch state every 100ms across the next tick | heater may stay commanded on for up to one 5s tick during the 500ms interlock window before both go off | green |
| T-H15 | hil | H-15 | bench | Bench rig: trigger a fault storm (repeated latch/clear) with the logger at DEBUG over UART0 | log volume measurably delays the loop under sustained fault churn | later |
| T-H16 | hil | H-16 | bench | Bench rig: lower the effective brown-out detector threshold and sag the supply | MCU runs erratically before resetting instead of resetting cleanly at a safe margin | later |
| T-H17 | lint | H-17 | ci-lint | Script dumps `esphome config` for `desiccant-dryer.yaml` and searches for any reference to `hw-virtual.yaml` or `time_scale` writers | production selector includes only `hw-real.yaml`; `time_scale` is written only from `packages/hw-virtual.yaml` | green |
| T-H18 | physical | H-18 | checklist | Deployment check: verify the flashed image matches the target build (production vs virtual) before install | binary/manifest identifies `desiccant-dryer.yaml`, not a virtual or host build, for a real unit | manual |
| T-H20 | lint | H-20 | ci-lint | Script inspects the ESP-IDF sdkconfig/panic handler setting used by the build | panic handler is set to reboot, not halt or the GDB stub | green |
| T-I03 | infer | I-03, A-06 | host | `Sim Manual Temps` on, slowly raise `Sim Pack A Temp` while pack A is active (heater nominally off), simulating a mis-wired relay | active pack rising more than 5 C above case temperature with its heater off raises `Fault` and turns both heaters off (same check as T-B23) | red |
| T-I04 | logic | I-04, I-23 | host | `Sim Heater Fault` on for standby A but delayed 6 min after HEATING starts (probe shows a small early bump then flatlines exactly at minute 6) | heater failing after the 5 min check still produces `Fault Message` Standby heater not heating within 10 sim min of the failure; a probe that never moves is caught by the same continuous check | red |
| T-I05 | logic | I-05 | host | Force fault 1 (active pack overtemp) while the active pack keeps supplying air; wait 20 sim min | a fault latched for longer than 30 sim min closes both valves or raises a distinct alarm entity, and `Service Time` stops counting | red |
| T-I06 | logic | I-06 | host | With `Sim Heater Fault` on for standby A, let fault 3 latch, press `Clear Fault`, wait 5 more min | fault 3 re-latches on schedule since the heater is still dead; the heater visibly cycles on for 5 min each clear | green |
| T-I07 | logic | I-07 | host | Latch fault 1 (active overtemp), then also drive the standby pack's temperature above `overtemp` | standby is forced to COOLING regardless; only fault 1 remains recorded, the second fault is not logged | green |
| T-I09 | logic | I-09 | host | Hold `Override RH` well below `arm_rh` for the entire max-service window with `near_max` never reached | standby remains WET indefinitely; nothing else forces it into HEATING | green |
| T-I10 | logic | I-10 | host | Repeatedly press `Restart` while standby is HEATING, 5 times in a row | each reboot resets heat/hold counters and restarts the regen from scratch, with no cap on how many times this can repeat | green |
| T-I11 | logic | I-11 | host | Set `Regen temp` unreachably high (119C, just under `overtemp`), run standby through `regen_max_min` | standby transitions to COOLING on the max-heater-time timeout, logged as a warning, and is treated as if regen completed | green |
| T-I12 | physical | I-12 | checklist | Design/process note: regen completeness is judged by pack surface temperature, not desiccant core moisture | documented in `docs/control-logic.md` as a known limitation pending real breakthrough-curve data | manual |
| T-I13 | physical | I-13 | checklist | Design/process note: a swap can occur while the standby pack's purge vent is still warm | documented as an accepted brief hot-air exposure at swap time | manual |
| T-I14 | logic | I-14 | host | Latch fault 2 on pack B, toggle `Dryer Enabled` off then on | `Fault Code` remains set after re-enable (fault is not cleared by disable); dryer restarts on pack A regardless of which pack was actually dry | green |
| T-I15 | logic | I-15 | host | Fresh install (globals at defaults), power up for the first time | pack A goes into service WET with no distinct "both packs unverified" warning | green |
| T-I18 | logic | I-18 | host | `Sim RH Fault` on (air_rh NaN) while standby B is mid-HEATING with a valid pack temperature | overtemp checks (independent of RH) keep running; the WET/HEATING/COOLING/READY switch is frozen on the `isnan(rh)` early return, heater state holds at its last value | green |
| T-I20 | logic | I-20 | host | `Override RH` held above `Swap RH` continuously while both packs alternate between marginal READY states | swap fires on nearly every tick that finds a READY standby, producing rapid valve alternation | green |
| T-I21 | logic | I-21 | host | `Override RH` pinned just above `arm_rh` for several hours of sim time, forcing back-to-back regens | heater duty accumulates with no per-hour or per-day cap anywhere in the logic | green |
| T-I22 | infer | I-22 | host | `Override Humidity` on, keep `Override RH` above `swap_rh` through a swap and into the new active pack's service | outlet RH not falling below `arm_rh` within 30 sim min of a swap raises `Fault` (pack not drying) | red |
| T-I24 | infer | I-24 | host | `Sim Fan Stalled` on with `Sim Ambient Temp` high (case genuinely hot) while standby is HEATING | `case_temp` above a limit, or a fan fault, holds the standby heater off and shows a warning in `Dryer Status` | red |
| T-I26 | infer | I-26 | host | `Sim Heater Fault` on for both packs across three consecutive swap cycles | two consecutive failed regens (fault 3 or `regen_max_min` timeout on both packs) enter a terminal fault: heaters off, `Dryer Status` reads cannot dry, no retry until `Clear Fault` | red |
| T-J02 | lint | J-02 | ci-lint | Script dumps `esphome config` for `desiccant-dryer.yaml` and `desiccant-dryer-adopt.yaml` | neither includes `hw-virtual.yaml`, `platform-host.yaml`, or `packages/dev-secrets.yaml` | green |
| T-J04 | lint | J-04 | ci-lint | Script dumps `esphome config` and checks every heater/valve switch for a correctly spelled `interlock:` entry naming its partner | all four outputs show a valid partner interlock; a removed or misspelled key would be silently accepted otherwise, so the script also confirms it would flag that | green |
| T-J05 | physical | J-05 | checklist | Firmware pre-flight check: compare `hw-real.yaml`'s three `address:` values against this board's own first-boot log on paper | all three addresses match the board's own log, not a copied value from another unit | manual |
| T-J06 | lint | J-06 | ci-lint | Script parses `hw-real.yaml` and `hw-virtual.yaml` sensor ids against the five names `base.yaml` may reference | `air_rh`, `air_temp`, `pack_a_temp`, `pack_b_temp`, `case_temp` all exist and are spelled identically in both hardware packages | green |
| T-J07 | lint | J-07 | ci-lint | Script dumps `esphome config` and checks the `interval:` block's period | interval is 5s, matching the 300s/5-tick constants documented in `docs/control-logic.md` | green |
| T-J08 | hil | J-08 | bench | Bench rig: fill or erase NVS during a flash update | all tunables revert to firmware defaults mid-run with no notification to the operator | later |
| T-J10 | hil | J-10 | bench | Bench rig: flash two boards with the same hostname and API encryption key on one network | Home Assistant writes a tunable change to the wrong unit | later |
| T-J11 | lint | J-11 | ci-lint | Script inspects the `globals:` block for any schema-version marker alongside `standby_state` or the elapsed counters | a persisted schema-version global exists and a mismatch at boot resets the persisted state to defaults with one log line | red |
| T-K01 | logic | K-01, K-02 | host | `Dryer Enabled` off; then `switch.turn_on` on `Heater A` and `Valve A` via the API; wait 3 ticks (15s) | a heater or valve switched on while disabled is turned back off within 1 tick; the active pack's heater switched on while enabled is off within 1 tick | red |
| T-K03 | logic | K-03 | host | Script toggles `Valve A` on/off via the API 10 times within one 5s tick interval | each optimistic switch state change is applied immediately with no debounce, confirming automation-driven chatter is possible | green |
| T-K04 | lint | K-04 | ci-lint | Script dumps `esphome config`'s `web_server:` block | no `auth:` is configured; port 80 is reachable by anyone on the LAN, as documented | green |
| T-K05 | lint | K-05 | ci-lint | Script dumps `esphome config` for `packages/release.yaml` and checks Improv/captive-portal settings | Improv serial and captive portal are present as documented provisioning paths, not accidentally left permanently open beyond intended use | green |
| T-K06 | logic | K-06 | host | While standby A is HEATING at a real 50C, set `Regen temp` to 30 via the API | `hold_elapsed_s` starts accumulating immediately since 50 &gt;= 30; regen is declared complete after `regen_hold_min` with no protection against the bad write | green |
| T-K07 | logic | K-07 | host | Press `Restart` while standby is HEATING | regen restarts from scratch after boot (per `on_boot`), costing one extra full regen cycle for that button press | green |
| T-K10 | lint | K-10 | ci-lint | `scripts/normalize-config.py` diffs `esphome config` for `desiccant-dryer.yaml` against `desiccant-dryer-adopt.yaml` | board, pin map and output config match between the flashed selector and the adopt selector | green |
| T-K11 | logic | K-11 | host | Latch any fault via the API, read the `Fault` binary_sensor | `device_class: problem` is true; no HA-side alerting automation exists to notify anyone, which is an HA-configuration gap rather than a firmware one | green |
| T-K12 | logic | K-12 | host | Disconnect the API client while the state machine keeps running onboard | HA-side entities show `unavailable` while the device continues its cycle correctly using its own internal values | green |
| T-K13 | physical | K-13 | checklist | Ops runbook check: after a site move, confirm the ESPHome entry's IP and `image.dryer_screen` URL are updated | HA controls the board's current address; the reconfiguration step in `docs/screen-in-ha.md` was followed | manual |
| T-K14 | logic | K-14 | host | Turn `Dryer Enabled` off via the API (simulating an HA scene or restored snapshot) | dryer stops drying silently; only `Dryer Status` ("Disabled") on the display communicates it | green |
| T-K15 | logic | K-15 | host | Write `Regen hold time` to 20 via the API, then immediately write it back to 5 (simulating a stale HA snapshot restore) | firmware accepts whichever value arrives last with no protection against an overwrite from a stale snapshot | green |
| T-L01 | hil | L-01 | bench | Bench rig: swap the SPI CS/DC lines or set the wrong `data_rate` | display shows blank or garbage output | later |
| T-L02 | hil | L-02 | bench | Bench rig: force a redraw stall (blocked lambda) while the display holds its last frame | screen looks healthy while the controller is actually hung, matching the A-03 symptom | later |
| T-L04 | logic | L-04 | host | Force each of fault codes 1, 2 and 3 in turn via the appropriate sim/API injection | `Fault` code and `Fault Message` text always update together for every code, including the 0/"" cleared state | green |
| T-L05 | infer | L-05 | host | Force a swap and immediately read the display's `UiState` gather point relative to `apply_outputs` execution order | any pack-colour/airflow-arrow lag behind the true valve/heater state is bounded to at most one tick, matching the documented ordering | green |
| T-L06 | lint | L-06 | ci-lint | Script inspects `display_ui.h`'s formatting calls for temperature and RH against each sensor's declared unit/precision | °C and one-decimal RH formatting in the display match the sensor definitions in `base.yaml`/`hw-real.yaml` | green |
| T-L07 | lint | L-07 | ci-lint | Script dumps `esphome config` for the display package and checks `color_palette` and `rotation` | `color_palette: 8BIT` and `rotation: 0` are set, the combination `/screen.png` requires to avoid a 500 | green |
| T-L08 | infer | L-08 | host | Repeatedly fetch `/screen.png` from the host/virtual build via `preview_start` while the display redraws every tick | frames come back whole with no visible tearing, matching the PR #15 regression fix | green |
| T-L09 | hil | L-09 | bench | Bench rig: disconnect and reconnect WiFi on a real board, compare the `IP Address` text sensor to the actual DHCP lease | sensor updates to the new address promptly rather than showing the pre-reconnect value | later |
| T-L10 | hil | L-10 | bench | Bench rig: verify the LEDC backlight channel initialises on a real panel | backlight comes on with the panel drawing correctly; a missing LEDC init leaves it stuck off | later |
| T-L11 | lint | L-11 | ci-lint | Script dumps `esphome config` for `packages/release.yaml` and checks the debug sensors (free heap, largest block, loop time) are present with an `update_interval` | all three debug sensors exist and update, so memory problems would not go unnoticed | green |
| T-L12 | physical | L-12 | checklist | Stage 1 check (paired with A-28): confirm the commissioning note that the GPIO13 blue LED is not a general "status OK" indicator | checklist/documentation explicitly states the LED reflects heater A relay state only | manual |

## New Sim knobs

| Knob | Used by tests | What it does in the plant model |
|---|---|---|
| `Sim Relay Stuck On A` | T-B02 | Heater A's plant effect (heat toward `Sim Heater Max Temp`) stays applied to pack A regardless of the `Heater A` switch command, simulating a welded relay contact |
| `Sim Valve Stuck A` | T-D01, T-D02, T-F20 | Valve A's simulated real-world position latches to whatever it was when this switch turns on and ignores all further commands, modelling a mechanically stuck valve with no position feedback |
| `Sim RH Fault` | T-C01, T-C14 (via Override) | Forces `air_rh` to publish NaN regardless of the plant model, simulating a dead or disconnected SHT45 |
| `Sim RH Frozen` | T-C02 | `air_rh` stops updating and republishes its last value every tick regardless of the plant model, simulating a hung I2C bus |
| `Sim Probe 85C` | T-B06 | Forces `pack_a_temp` to publish exactly 85.0C regardless of the plant model, simulating the DS18B20 power-on sentinel value |
| `Sim Probe Garbage A` | T-B07 | Forces `pack_a_temp` to publish -127C regardless of the plant model, simulating an out-of-range DS18B20 fault code |
| `Sim Case Probe Fault` | T-B16, T-B1011 | Forces `case_temp` to publish NaN regardless of the plant model, simulating a dead case DS18B20 |
| `Sim Probes Swapped` | T-B26 | `pack_b_temp` republishes pack A's plant temperature instead of its own, simulating duplicated or crossed DS18B20 addresses |
| `Sim Fan Stalled` | T-E11, T-I24 | The case thermal model stops responding to fan/thermostat state, so the enclosure keeps heating as if the fan were absent, simulating a stalled fan with no tachometer feedback |

Each knob is a `switch` in `packages/hw-virtual.yaml` acting on the plant model only; none exists in the real hardware package.
