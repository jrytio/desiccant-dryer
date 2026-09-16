# Failure modes — catalogue for the test and verification suite

A list of every hardware and software failure we could think of for the
ESP32 desiccant dryer controller, the replacement for the original control board in an Azco VMD-08 dryer (ESP32-S2, two 120 VAC heaters on Songle relays,
two 24 V SMC valves, DS18B20 pack/case probes, SHT45 outlet sensor,
SF129E thermal fuses, Mean Well LRS-35-24 and an MP1584 buck).

Nothing here is verified against the running firmware. It is the starting
inventory for a test/verify suite, in the spirit of the thermal-runaway and
"heating but no temperature rise" protection in Marlin and Prusa firmware.

## Priority scale

| Priority | Meaning |
|---|---|
| **P0** | Fire, electrocution, or mains energy where it must never be |
| **P1** | Damages the dryer, packs, valves or controller, or removes a safety layer so that a second fault becomes P0 |
| **P2** | Process failure: wet air reaches the ozone generator, or the dryer silently stops drying |
| **P3** | Degraded or wasted operation: extra regens, wasted heat, nuisance faults, needs a manual reset |
| **P4** | Status, display or telemetry is wrong; the plant itself is fine |

Item IDs are `<category letter>-<number>`. Numbers are stable once assigned;
add new items at the end of a category rather than renumbering. Some IDs
have been retired by merging into another row — see "Retired IDs" near the
end of this file; their numbers are not reused.

## Column key

| Column | Values |
|---|---|
| **Pri** | 🔴 P0 · 🟠 P1 · 🟡 P2 · 🔵 P3 · ⚪ P4 (scale above) |
| **Kind** | `HW` component fault · `WIRE` assembly or wiring error · `FW` firmware logic · `CFG` YAML or tunable · `OPS` operator or Home Assistant action |
| **Verify** | `virtual` provable in the host or virtual build · `bench` needs the real board, mains off · `live` needs energised heaters with instrumentation · `inspect` a build or config review item, not a runtime test |
| **Gap** | ✱ the firmware has no detection for this today; a test would fail until a check is added |

For agents: each row matches `^\| ([A-L]-\d\d) \| (.+) \| [🔴🟠🟡🔵⚪] (P[0-4]) \| (HW|WIRE|FW|CFG|OPS) \| (virtual|bench|live|inspect) \| (✱?) \|$`.
`scripts/failure-modes-report.py` renders this file as a filterable HTML page.

## Contents

| Category | 🔴 | 🟠 | 🟡 | 🔵 | ⚪ | Total |
|---|---|---|---|---|---|---|
| [A. Heater mains path (relays, drivers, fuses, wiring)](#a-heater-mains-path-relays-drivers-fuses-wiring) | 17 | 6 | 4 | 2 |  | 29 |
| [B. Pack temperature sensing and thermal control](#b-pack-temperature-sensing-and-thermal-control) | 2 | 12 | 7 | 3 |  | 24 |
| [C. Outlet humidity sensing (SHT45)](#c-outlet-humidity-sensing-sht45) |  |  | 9 | 4 |  | 13 |
| [D. Valves and airflow](#d-valves-and-airflow) |  | 10 | 4 | 2 |  | 16 |
| [E. Case cooling, enclosure and fan](#e-case-cooling-enclosure-and-fan) | 1 | 4 | 2 | 1 | 1 | 9 |
| [F. Power supplies and rails](#f-power-supplies-and-rails) | 2 | 9 | 7 | 1 |  | 19 |
| [G. Wiring, connectors, mechanical, environmental](#g-wiring-connectors-mechanical-environmental) | 4 | 6 | 4 | 1 |  | 15 |
| [H. MCU and firmware runtime](#h-mcu-and-firmware-runtime) | 1 | 9 | 5 | 1 |  | 16 |
| [I. Control logic and state machine](#i-control-logic-and-state-machine) |  | 6 | 11 | 7 |  | 24 |
| [J. Persistence and configuration](#j-persistence-and-configuration) | 4 | 1 | 3 | 1 |  | 9 |
| [K. Remote control, Home Assistant and network](#k-remote-control-home-assistant-and-network) |  | 5 | 5 | 3 |  | 13 |
| [L. Display and telemetry](#l-display-and-telemetry) |  |  |  | 3 | 9 | 12 |

---

## A. Heater mains path (relays, drivers, fuses, wiring)

| ID | Failure | Pri | Kind | Verify | Gap |
|---|---|---|---|---|---|
| A-01 | Relay contact welds closed; heater stays on with the coil de-energised. Hardware failure of the contact itself, found by exercising the relay live; the matching "no software check catches this" gap is B-02 | 🔴 P0 | HW | live |  |
| A-02 | PN2222A driver shorts collector-emitter; relay held on permanently | 🔴 P0 | HW | bench |  |
| A-03 | A heater GPIO (12 or 13) is stuck driving its relay on — firmware crash/hang leaving outputs in their last state, a pin latch-up, or a solder bridge — and the state survives a reboot. The ESP-IDF task watchdog must reboot a hung loop and `on_boot` (priority 700, `base.yaml`) must force both heater outputs off before the state machine runs; verify the relay actually de-energises within one watchdog period | 🔴 P0 | FW | bench |  |
| A-04 | P2N2222A fitted instead of PN2222A (mirrored pinout); stage misbehaves or B-E junction breaks down | 🔴 P0 | WIRE | inspect |  |
| A-05 | Both heater relays on at once (interlock defeated by hardware fault or firmware bug); 2 A through fuse and double heat load | 🔴 P0 | FW | bench |  |
| A-06 | Heater on the in-service pack (wrong relay wired, swapped harness pins 3/4, or logic error); hot air and heat into the ozone feed | 🔴 P0 | WIRE | bench |  |
| A-07 | SF129E thermal fuse not fitted, bypassed, or fitted on the wrong pack | 🔴 P0 | WIRE | inspect |  |
| A-08 | SF129E clamped where it does not track pack temperature (loose clamp, wrong position); backstop never opens | 🔴 P0 | WIRE | inspect |  |
| A-09 | Relay NC pin wired by mistake; heater live whenever the relay is *off* | 🔴 P0 | WIRE | inspect |  |
| A-10 | Neutral switched instead of line (inlet L/N reversed at terminal); heater energised while "off" | 🔴 P0 | WIRE | inspect |  |
| A-11 | Mains fuse F1 is bypassed, fitted at the wrong rating, or replaced with a fast-blow type that nuisance-trips and gets bridged by a frustrated technician; an inspection of the installed fuse's type and rating. F-06 is the live inrush event that provokes the nuisance trip | 🔴 P0 | WIRE | inspect |  |
| A-12 | 24 V PSU L spur taken before F1 instead of after; unfused PSU fault path | 🔴 P0 | WIRE | inspect |  |
| A-13 | Heater element shorted to sheath or partially shorted; over-current or sheath live | 🔴 P0 | HW | live |  |
| A-14 | Heater sheath / chassis PE bond missing or broken; sheath live on insulation failure | 🔴 P0 | WIRE | inspect |  |
| A-15 | Creepage between mains and logic rows on the protoboard (5.6 mm pad-to-pad, less on plated pads) arcs over in humidity or dust | 🔴 P0 | WIRE | inspect |  |
| A-16 | Mains wire pulls out of a screw terminal (stranded not ferruled, under-torqued) and touches logic or chassis | 🔴 P0 | WIRE | inspect |  |
| A-17 | Mains conductor of wrong insulation or temperature rating chafes on pack at 90 to 133 °C | 🔴 P0 | WIRE | inspect |  |
| A-18 | Relay coil flyback diode missing or reversed; PN2222A destroyed, possible stuck-on failure later | 🟠 P1 | WIRE | bench |  |
| A-19 | Relay contact fails open or high-resistance; heater never heats, or contact heats itself | 🟠 P1 | HW | live |  |
| A-20 | Relay contact arcs and pits from switching the 1 A inductive-ish load every regen; life ends with a weld | 🟠 P1 | HW | live |  |
| A-21 | Relay coil open; heater cannot be commanded on | 🟡 P2 | HW | bench |  |
| A-22 | Heater element open circuit; no heat | 🟡 P2 | HW | live |  |
| A-23 | PN2222A base resistor or 10 kΩ pulldown open; relay floats or chatters | 🟠 P1 | HW | bench |  |
| A-24 | Relay harness (JST-XH 4-way) unplugged or one conductor open; both heaters dead, or one dead | 🟡 P2 | WIRE | bench |  |
| A-25 | Relay chatter from marginal 5 V coil supply (buck sag under two coils plus WiFi peak) | 🟠 P1 | HW | bench |  |
| A-26 | Heater partially failed (higher resistance); heats too slowly, trips the no-rise fault or never reaches regen temperature | 🔵 P3 | HW | virtual |  |
| A-27 | SF129E has opened once (one-shot); pack permanently unheatable until replaced, dryer appears "not heating" | 🟡 P2 | HW | live |  |
| A-28 | On-board blue LED on GPIO13 shorted or LED failure pulling GPIO13; heater A relay affected | 🟠 P1 | HW | bench |  |
| A-29 | GPIO13 boot-time glitch (strapping / reset) pulses relay A on for milliseconds at every reboot | 🔵 P3 | FW | bench |  |

## B. Pack temperature sensing and thermal control

| ID | Failure | Pri | Kind | Verify | Gap |
|---|---|---|---|---|---|
| B-01 | Heater on, standby pack temperature does not rise (dead heater, probe not on pack, probe swapped); firmware must cut power (existing 5 min / +5 °C check; verify it also covers a rise that stalls mid-way) | 🟠 P1 | FW | virtual |  |
| B-02 | Pack temperature keeps rising for several ticks after its heater is commanded off (welded relay contact, or a driver stuck on); `base.yaml` has no check comparing heater command state to the temperature trend, so this is caught only by the SF129E thermal fuse or by an operator noticing. A-01 is the hardware weld this detects | 🔴 P0 | FW | virtual | ✱ |
| B-03 | Pack temperature runs away above `regen_temp` toward `overtemp` faster than expected (undersized pack, blocked vent); only the fixed 110 °C limit catches it — there is no rate-of-rise check in the interval lambda | 🟠 P1 | FW | virtual | ✱ |
| B-04 | Active pack overtemp with its probe reading NaN; the fault-1 check (`!isnan(t_act) && t_act > overtemp`) is skipped, no fallback | 🟠 P1 | FW | virtual | ✱ |
| B-05 | DS18B20 pack A and pack B are physically installed on the wrong packs, or their addresses are entered swapped when a board is first wired; the heater then heats one pack while the firmware watches the other's temperature. Verify by warming pack A and confirming `pack_a_temp`, not `pack_b_temp`, responds. J-05 is the same wrong-mapping fault caused by copying addresses from another unit instead of a physical swap | 🔴 P0 | WIRE | bench | ✱ |
| B-06 | DS18B20 returns the 85 °C power-on value; no filter in `hw-real.yaml` rejects it, so it is treated as a real reading (looks like a hot pack, or a regen "hold") | 🟠 P1 | FW | virtual | ✱ |
| B-07 | DS18B20 returns −127 °C or another out-of-range numeric value; no range filter exists, so it is not rejected and drives cooldown and READY logic | 🟠 P1 | FW | virtual | ✱ |
| B-08 | DS18B20 frozen at last good value (bus stuck, driver not publishing NaN); no stale-value timeout exists for the pack probes | 🟠 P1 | FW | virtual | ✱ |
| B-09 | DS18B20 CRC errors on the shared 1-wire bus; intermittent NaN, standby heater allowed on for up to 5 missed ticks (`sb_nan_ticks`) | 🟡 P2 | HW | bench |  |
| B-10 | 1-wire pullup open or wrong value; all three probes drop out together | 🟡 P2 | HW | bench |  |
| B-11 | 1-wire bus shorted or GPIO37 damaged; all temperature data lost, heater held off, dryer stalls | 🟡 P2 | HW | bench |  |
| B-12 | Probe lead insulation (rated under 100 °C) melts on a 90 to 133 °C pack; short or open, or lead shorts to the heater sheath | 🟠 P1 | HW | inspect |  |
| B-13 | Probe detaches from the pack body (thermal paste dries, clamp loosens); reads air temperature, heater over-runs until `regen_max_min` or overtemp | 🟠 P1 | HW | live |  |
| B-14 | Probe mounted on the heater sheath instead of the pack body; reads high, regen judged complete before the desiccant is dry | 🟡 P2 | WIRE | inspect |  |
| B-15 | Probe self-heating or radiant pickup from the heater; false "regen hold" | 🔵 P3 | HW | live |  |
| B-16 | Case DS18B20 (`case_temp`) fails and reports NaN; the `Case Fan Thermostat` climate component's behaviour on an unavailable sensor is undefined in `base.yaml` — no fallback (e.g. forcing the fan on) exists, and the fan may never start. E-03 is the same probe reading a plausible-but-wrong low value instead of NaN | 🟠 P1 | FW | virtual | ✱ |
| B-17 | DS18B20 counterfeit with poor accuracy above 85 °C; regen hold judged wrongly | 🔵 P3 | HW | bench |  |
| B-18 | Ambient above `cooldown_temp` (40 °C); standby never becomes READY, max-service fallback never fires (documented open item, see I-08) | 🟡 P2 | FW | virtual |  |
| B-19 | `restore_value: true` tunables (e.g. `Pack overtemp limit`) persisted in NVS survive a firmware upgrade that lowers a default for safety: a unit already running keeps its old 120 °C `overtemp` value after 1.2.0 drops the shipped default to 110 °C, still above the SF129E's 118 °C holding temperature. The fix is a manual re-entry in Home Assistant (docs/control-logic.md), not automatic; this is a general risk for any tunable default change, not only `overtemp` | 🟠 P1 | CFG | bench |  |
| B-20 | `overtemp` set by hand up to its 125 °C maximum, above the fuse holding temperature | 🟠 P1 | CFG | virtual |  |
| B-21 | `regen_temp` set at or above `overtemp`; every regen faults, or overtemp check races the hold timer | 🔵 P3 | CFG | virtual |  |
| B-22 | Both packs' probes fail while one is HEATING; heater cut after 25 s but no fault latched, silent stall | 🟡 P2 | FW | virtual |  |
| B-23 | Temperature rises on the *active* pack while the standby heater is on (cross-talk, wrong valve routing hot purge air); no plausibility check compares the two packs | 🟠 P1 | FW | virtual | ✱ |
| B-24 | Temperature reading jumps by tens of degrees between 10 s samples (electrical noise on the 1-wire line from the relay board); accepted as-is, no rate-of-change filter | 🟡 P2 | FW | virtual | ✱ |

## C. Outlet humidity sensing (SHT45)

| ID | Failure | Pri | Kind | Verify | Gap |
|---|---|---|---|---|---|
| C-01 | SHT45 unplugged or I2C bus dead; `ctrl_rh` reads NaN, the state machine holds forever (`isnan(rh)` early-returns before any state change) with no timeout or fault for a prolonged loss of the outlet sensor | 🟡 P2 | FW | bench | ✱ |
| C-02 | SHT45 reads a frozen value (I2C hung after a glitch, no reset); breakthrough never seen, wet air delivered | 🟡 P2 | FW | virtual | ✱ |
| C-03 | SHT45 placed upstream of the valves or in stagnant air; measures the wrong air | 🟡 P2 | WIRE | inspect |  |
| C-04 | SHT45 saturated or wetted by condensation or ozone-generator backflow; reads high, endless "waiting" or premature swaps | 🟡 P2 | HW | live |  |
| C-05 | SHT45 drifts with ozone or contaminant exposure; baseline creeps past `arm_rh`, heater runs continuously | 🔵 P3 | HW | live |  |
| C-06 | SHT45 temperature reading wrong; RH compensation off, baseline shifts | 🔵 P3 | HW | bench |  |
| C-07 | Humidity override left on (`rh_override_on`) during production; control runs on a fake number | 🟡 P2 | OPS | virtual |  |
| C-08 | Override survives a reboot (invariant regression check: `rh_override_on` is `restore_mode: ALWAYS_OFF` today, so this must stay false) | 🟡 P2 | FW | bench |  |
| C-09 | RH moving-average filter (`sliding_window_moving_average`, window 3) hides a sharp breakthrough spike for 20 to 30 s | 🔵 P3 | FW | virtual |  |
| C-10 | RH below `arm_rh` at all times because the sensor floor (0 to 10 %) is noisy; regen never arms, then breakthrough is sudden | 🟡 P2 | FW | virtual |  |
| C-11 | `arm_rh` set above `swap_rh` in Home Assistant; pack swaps to a pack that never started regenerating, with no cross-validation between the two tunables | 🟡 P2 | CFG | virtual | ✱ |
| C-12 | I2C pullups absent (none on the ESP board, relying on the breakout); marginal bus at 100 kHz over the Qwiic cable | 🟡 P2 | HW | bench |  |
| C-13 | SHT45 heater feature accidentally enabled in config; reads low and warm | 🔵 P3 | CFG | inspect |  |

## D. Valves and airflow

| ID | Failure | Pri | Kind | Verify | Gap |
|---|---|---|---|---|---|
| D-01 | Both valves open at once through an electrical or firmware fault (MOSFET shorted, or the `interlock: [valve_b]`/`[valve_a]` pair removed by a config error) rather than a mechanical failure; regenerating pack vents wet purge air into the outlet, hot air to the ozone feed. Bench-test that the interlock config actually blocks this; there is no runtime cross-check that would catch it if it did occur. D-04 is the mechanical equivalent (valve physically stuck open) | 🟠 P1 | FW | bench | ✱ |
| D-02 | Both valves closed while heater on through an electrical or firmware fault (valve MOSFET open, coil open, 24 V lost) rather than a mechanical failure; pack heats with no purge airflow, hot spot, and nothing cross-checks valve state against heater state. D-05 is the mechanical equivalent | 🟠 P1 | FW | virtual | ✱ |
| D-03 | `do_swap` is interrupted while the dryer stays enabled (reset, brownout or watchdog reboot inside the 500 ms both-valves-closed window), so step 2 never runs: `active_pack` still names the retiring pack and `standby_state` is unchanged. After boot `on_boot` forces outputs off and the first tick re-derives them, so the retiring pack's valve should reopen within one 5 s tick; verify that, and that no half-swapped state (both closed, or wrong pack open) persists. Turning `Dryer Enabled` off during the window is the intended safe state, not this fault | 🔵 P3 | FW | virtual |  |
| D-04 | Valve solenoid mechanically sticks open (debris, coil energised too long against a 90 °C pack) even though only one is commanded on; same visible symptom as D-01 (wet purge air, hot air to the outlet) but caused by hardware wear, found by exercising the valve live rather than by a config or interlock review | 🟠 P1 | HW | live |  |
| D-05 | Valve stuck closed mechanically (debris, seized coil); same symptom as D-02, or no service flow if it is the active valve — found by exercising the valve live, not by a config review | 🟡 P2 | HW | live |  |
| D-06 | Valve coil overheats (rated 50 °C, mounted on a 90 °C pack); insulation failure, short on the 24 V rail | 🟠 P1 | HW | live |  |
| D-07 | Valve wired to the wrong pack (A/B swapped at terminals); air flows through the pack being heated | 🟠 P1 | WIRE | bench |  |
| D-08 | IRLZ44N gate pulldown open; valve floats on at boot or during reset | 🟠 P1 | HW | bench |  |
| D-09 | IRLZ44N partially enhanced at 3.3 V heats under a shorted coil; no current limit on the 24 V rail | 🟠 P1 | HW | bench |  |
| D-10 | Flyback diode across valve missing or reversed; MOSFET avalanche, eventual short (becomes D-01/D-04) | 🟠 P1 | WIRE | bench |  |
| D-11 | Valve coil open; pack can never be brought into service, swap leaves the outlet closed | 🟡 P2 | HW | bench |  |
| D-12 | Purge vent blocked; regen exhaust cannot leave, pack overheats or stays wet | 🟠 P1 | HW | live |  |
| D-13 | Inlet air blocked or compressor off; dryer cycles on humidity that is not moving | 🔵 P3 | HW | live |  |
| D-14 | Leak between the two pack circuits (cracked manifold); wet air bypasses the in-service pack | 🟡 P2 | HW | live |  |
| D-15 | Force Swap pressed with the standby pack WET or HEATING; wet pack into service, hot pack retired mid-heat | 🟡 P2 | OPS | virtual |  |
| D-16 | Swap while the retiring pack's heater is still commanded (`do_swap` already turns the retiring heater off before closing valves; verify this order holds under future edits) | 🟠 P1 | FW | virtual |  |

## E. Case cooling, enclosure and fan

| ID | Failure | Pri | Kind | Verify | Gap |
|---|---|---|---|---|---|
| E-01 | Fan fails (bearing, open coil, MOSFET open); enclosure temperature climbs, relays and buck derate, ESP brownout | 🟠 P1 | HW | bench |  |
| E-02 | Fan runs continuously (MOSFET short); no hazard but hides E-01 | ⚪ P4 | HW | bench |  |
| E-03 | Case DS18B20 reads persistently low because it fell off its mount or is placed away from the actual hot zone (a working, connected probe, unlike B-16's NaN case); the fan thermostat sees a plausible but wrong low temperature and the fan never runs. Verify by heating the enclosure and confirming the probe, not just the fan output, tracks it | 🟠 P1 | HW | live |  |
| E-05 | Fan thermostat mode after `Dryer Enabled` is toggled off then on: `on_turn_off` sets the thermostat to `OFF`, and `on_turn_on` sets it back to `COOL` (base.yaml); verify this reset actually restarts cooling and that a latched fault (which does not touch the thermostat) never leaves it parked | 🟡 P2 | FW | virtual |  |
| E-06 | Enclosure vents blocked or fan direction reversed | 🟡 P2 | HW | live |  |
| E-07 | Enclosure interior above the relay's rated ambient; contact resistance rises, weld risk increases | 🟠 P1 | HW | live |  |
| E-08 | Condensation inside the enclosure (cold start in a humid room) across mains creepage | 🔴 P0 | HW | inspect |  |
| E-09 | Dust, desiccant fines or ozone ingress corroding relay contacts and PCB traces | 🟠 P1 | HW | inspect |  |
| E-10 | Fan wired reverse polarity (polarity protected on the example part, not guaranteed on a substitute) | 🔵 P3 | WIRE | bench |  |

## F. Power supplies and rails

| ID | Failure | Pri | Kind | Verify | Gap |
|---|---|---|---|---|---|
| F-01 | LRS-35-24 fails with output shorted to mains (rare, Class I supply); FG/PE bond is the only protection | 🔴 P0 | HW | inspect |  |
| F-02 | PSU FG not bonded to PE; chassis floats on a primary fault | 🔴 P0 | WIRE | inspect |  |
| F-03 | 24 V rail reverse-polarity on the logic board (no protection, open item); buck and MOSFETs destroyed, possible stuck-on outputs | 🟠 P1 | WIRE | bench |  |
| F-04 | 24 V rail over-voltage (PSU trimmer, PSU fault); buck input above rating | 🟠 P1 | HW | bench |  |
| F-05 | PSU hiccup mode from a shorted valve or fan; whole controller reboots repeatedly, outputs cycle | 🟠 P1 | HW | bench |  |
| F-06 | Cold-start inrush (~45 A) opens F1 if a fast-blow fuse is fitted instead of the specified slow-blow/time-delay type, leaving the dryer dead; the live-test risk is that someone then bridges or upgrades the fuse rating to silence the nuisance trips, creating A-11's unsafe state. Verify the specified fuse rides through inrush without opening | 🟠 P1 | HW | live |  |
| F-07 | MP1584 output set too high (trimmer drift, mis-set); ESP AP2112K over 6.5 V absolute max, relay coils over-driven | 🟠 P1 | HW | bench |  |
| F-08 | MP1584 output too low; relay coils drop out intermittently, ESP brownout resets | 🟠 P1 | HW | bench |  |
| F-09 | MP1584 output ripple or oscillation into the ESP's USB net; random resets, WiFi drop | 🟡 P2 | HW | bench |  |
| F-10 | Buck feeds a host's USB port when a USB-C cable is connected with JP-USB fitted (up to 4 to 4.7 A) | 🟠 P1 | HW | bench |  |
| F-11 | JP-USB pulled during operation for programming; relay coils lose 5 V but ESP stays powered from USB; outputs appear commanded but relays are dead | 🟡 P2 | OPS | bench |  |
| F-12 | Schottky on the 5 V net reversed; ESP unpowered or host back-feeds coils | 🟡 P2 | WIRE | bench |  |
| F-13 | 5 V bulk capacitor fitted reversed or vented; rail noise, relay chatter | 🟠 P1 | WIRE | inspect |  |
| F-14 | 3.3 V LDO over-current (310 mA ESP peak plus display backlight plus 1-wire); brownout during WiFi bursts | 🟡 P2 | HW | bench |  |
| F-15 | Brownout during boot leaves the ESP in a partial state with GPIOs at their reset default (verify the relay/valve pins default low) | 🟠 P1 | FW | bench |  |
| F-16 | Mains power dip long enough to reboot the ESP but not to drop the relays' magnetic state (relay held by residual coil energy); short-lived mismatch | 🟡 P2 | HW | live |  |
| F-17 | Power loss mid-swap (both valves closed) and restore; boot forces outputs off then reasserts from persisted state (verify no stuck both-closed) | 🟡 P2 | FW | virtual |  |
| F-18 | Ground loop between PSU 0 V, PE, USB host ground and the display cable; noise on 1-wire and I2C | 🟡 P2 | HW | bench |  |
| F-19 | LiPo charger / BAT pin accidentally fed 5 V; DMG2307L or MCP73831 damage | 🔵 P3 | WIRE | inspect |  |

## G. Wiring, connectors, mechanical, environmental

| ID | Failure | Pri | Kind | Verify | Gap |
|---|---|---|---|---|---|
| G-01 | 12-pin header off by one (GPIO8/GPIO4 vs Feather "9"/"5" positions); wrong outputs driven | 🟠 P1 | WIRE | bench |  |
| G-02 | ESP inserted into its socket shifted by one pin or rotated | 🟠 P1 | WIRE | inspect |  |
| G-03 | Display cable order mismatch (Waveshare vs LCDWIKI pinout); VCC and GND swapped onto the display or SPI pins | 🟠 P1 | WIRE | inspect |  |
| G-04 | Display backlight pin driving a bare LED instead of a transistor; GPIO17 overloaded | 🟡 P2 | HW | inspect |  |
| G-05 | Qwiic cable pinout mismatch with a non-Qwiic breakout; 3.3 V on SDA | 🟡 P2 | WIRE | inspect |  |
| G-06 | Screw terminal on a sensor triple loose; intermittent probe. Symptom looks like B-09's 1-wire CRC errors but the cause here is a loose mechanical joint, not bus noise | 🟡 P2 | WIRE | bench |  |
| G-07 | Vibration from the compressor loosens headers and terminals over months | 🟠 P1 | HW | inspect |  |
| G-08 | Solder bridge between adjacent heater and valve GPIO pins (12 and 13, 10 and 11) | 🔴 P0 | WIRE | bench |  |
| G-09 | Wrong wire in a mains-rated terminal (24 V and mains blocks are the same 5.08 mm family) | 🔴 P0 | WIRE | inspect |  |
| G-10 | Mains wiring routed next to the 1-wire and SPI lines; induced noise, false readings | 🟡 P2 | WIRE | inspect |  |
| G-11 | Protoboard trace or bus wire overheats from a wiring error on the 24 V bus (no 24 V fuse) | 🟠 P1 | WIRE | bench |  |
| G-12 | Enclosure not earthed or metal enclosure with a chafed mains lead | 🔴 P0 | WIRE | inspect |  |
| G-13 | Strain relief missing on the heater tails at the pack; conductor fatigue at 90 °C | 🔴 P0 | WIRE | inspect |  |
| G-14 | Thermal fuse leads crimped badly; high-resistance joint heats and opens the fuse spuriously, or melts | 🟠 P1 | WIRE | inspect |  |
| G-15 | Buck module footprint different from the drilled holes; forced fit, cracked joints | 🔵 P3 | HW | inspect |  |

## H. MCU and firmware runtime

| ID | Failure | Pri | Kind | Verify | Gap |
|---|---|---|---|---|---|
| H-02 | Watchdog reboot loop; heater pulses on for one tick each boot (verify boot priority 700 forces off before any tick) | 🟠 P1 | FW | bench |  |
| H-03 | Heap exhaustion (display buffer, TLS, web server, log clients) stalls the 5 s interval; `dt` clamp at 60 s hides how long the heater ran uncontrolled | 🟠 P1 | FW | bench |  |
| H-04 | Stack overflow in a lambda or the display draw; reset with outputs at their last state until reboot completes | 🟠 P1 | FW | bench |  |
| H-05 | `millis()` wrap or `last_tick_ms` restore garbage; `dt` negative or huge (clamped, but verify sign) | 🟡 P2 | FW | virtual |  |
| H-06 | Interval tick blocked by a long OTA, a slow `/screen.png` fetch, or an SPI display redraw; heater timers under-count | 🟡 P2 | FW | bench |  |
| H-07 | Safe mode entered after repeated boot failures; controller runs with no control logic and no explicit output assertion | 🟠 P1 | FW | bench |  |
| H-08 | OTA of a broken image; relay pins default state during the bootloader and partition switch | 🟠 P1 | FW | bench |  |
| H-09 | OTA interrupted by power loss; falls back to previous partition or safe mode (see H-07) | 🟡 P2 | FW | bench |  |
| H-10 | NVS wear from per-minute counter writes over years can corrupt persisted globals on restore; `on_boot` only clamps `active_pack`, `standby_state` and `fault_code` to valid ranges (base.yaml), so a garbage `heat_start_temp` or garbage elapsed-second counters (NaN or negative) are not caught and drive the regen timing wrong | 🟡 P2 | FW | virtual | ✱ |
| H-12 | GPIO output glitch during deep reset or flashing (UART0 download mode) toggles relay pins | 🟠 P1 | FW | bench |  |
| H-13 | `apply_outputs` script mode `single` skipped because a previous call is still running | 🟠 P1 | FW | virtual |  |
| H-14 | Interlock `wait_time` 500 ms plus `apply_outputs` ordering leaves a heater on for one tick during a fault transition | 🟠 P1 | FW | virtual |  |
| H-15 | Logger at DEBUG floods UART0 and delays the loop under a log-heavy fault storm | 🔵 P3 | FW | bench |  |
| H-16 | Brown-out detector threshold too low; MCU runs erratically before resetting | 🟠 P1 | HW | bench |  |
| H-17 | Clock drift or `time_scale` accidentally not 1.0 in production (invariant); all durations wrong | 🟡 P2 | CFG | virtual |  |
| H-18 | Flash image mismatch (virtual build flashed to the real unit); plant model drives real relays | 🔴 P0 | OPS | inspect |  |

## I. Control logic and state machine

| ID | Failure | Pri | Kind | Verify | Gap |
|---|---|---|---|---|---|
| I-02 | No thermal model: no expected rate of rise, no upper bound on heating time per degree, no comparison to case or ambient | 🟠 P1 | FW | virtual | ✱ |
| I-03 | Active pack temperature is only checked against `overtemp`; a slow rise on the in-service pack (wrong relay wired, see A-06) is not flagged until 110 °C | 🟠 P1 | FW | virtual | ✱ |
| I-04 | Fault 3 (no rise) only checks at exactly 5 min; a heater that dies after minute 6 is not detected until `regen_max_min` | 🟠 P1 | FW | virtual | ✱ |
| I-05 | Fault latched but valves keep running and service time keeps counting; wet air delivered indefinitely with no escalation | 🟡 P2 | FW | virtual | ✱ |
| I-06 | Clearing a fault re-arms heating immediately even if the cause is a dead heater; fault re-latches every 5 min (heater cycles on for 5 min each clear) | 🔵 P3 | FW | virtual |  |
| I-07 | Fault 2 forces standby to COOLING even if another fault was already latched; state inconsistency | 🔵 P3 | FW | virtual |  |
| I-08 | Max-service fallback only fires from READY; stuck standby never swaps | 🟡 P2 | FW | virtual | ✱ |
| I-09 | Standby stuck WET because RH never crosses `arm_rh` and near-max window never reached | 🟡 P2 | FW | virtual |  |
| I-10 | HEATING resumed after reboot with counters reset; a pack can be heated for `regen_max_min` again and again across power cycles (thermal fatigue of the pack, desiccant degradation) | 🔵 P3 | FW | virtual |  |
| I-11 | `regen_max_min` timeout treated as regen complete (goes to COOLING then READY); wet pack put into service | 🟡 P2 | FW | virtual |  |
| I-12 | Regen hold measured by pack surface temperature, desiccant core still wet; premature READY | 🟡 P2 | FW | virtual |  |
| I-13 | Swap happens while the standby is READY but its purge vent is still hot; brief hot air to the outlet | 🔵 P3 | FW | virtual |  |
| I-14 | `Dryer Enabled` off clears state but not the fault; on re-enable the dryer starts on pack A regardless of which was dry | 🔵 P3 | FW | virtual |  |
| I-15 | Both packs WET at first start (fresh install); pack A is put into service wet with no warning | 🟡 P2 | FW | virtual |  |
| I-16 | Tunables mutually inconsistent (`cooldown_temp` > `regen_temp`, `arm_rh` > `swap_rh`, `regen_hold_min` > `regen_max_min`); no cross-validation | 🟡 P2 | FW | virtual | ✱ |
| I-17 | `sb_nan_ticks` allows the heater on for 25 s after the probe vanishes; probe loss during a fast rise | 🟡 P2 | FW | virtual |  |
| I-18 | NaN RH with a valid standby temperature; fault checks run but the state machine is frozen, heater state preserved from the last decision | 🟡 P2 | FW | virtual |  |
| I-19 | Swap interrupted by a reset before step 2 of `do_swap` (see D-03) leaves `service_elapsed_s` above `max_service_min`, so the retry fires on the first tick after boot while the standby may have cooled below READY conditions; verify the retried swap still goes to a READY pack, or that the retry is deferred | 🔵 P3 | FW | virtual |  |
| I-20 | Swap triggered every tick when RH stays above `swap_rh` and both packs are marginal; rapid alternation, valves cycling | 🟡 P2 | FW | virtual |  |
| I-21 | Heater duty not bounded per hour or per day; a broken humidity baseline can run the heater near-continuously (energy, pack life) | 🔵 P3 | FW | virtual |  |
| I-22 | No detection that regen produced no drop in outlet RH after the swap (pack exhausted, desiccant dead) | 🟡 P2 | FW | virtual | ✱ |
| I-23 | No detection of a probe that never moves at all across a full regen (probe on the wrong pack or in air) beyond the 5 min check | 🟠 P1 | FW | virtual | ✱ |
| I-24 | Heater allowed on with the case temperature already high or the fan faulted; `sb_heat` does not read `case_temp` or the fan thermostat state | 🟠 P1 | FW | virtual | ✱ |
| I-25 | Overtemp fault relies on the same probe that the regen logic trusts; a single stuck probe defeats both (only SF129E remains) | 🟠 P1 | FW | virtual | ✱ |

## J. Persistence and configuration

| ID | Failure | Pri | Kind | Verify | Gap |
|---|---|---|---|---|---|
| J-02 | Production build accidentally includes `hw-virtual.yaml` or dev secrets (wrong selector) | 🔴 P0 | CFG | inspect |  |
| J-03 | `restore_mode` on an output changed from `ALWAYS_OFF` by a future edit; relay restores on at boot | 🔴 P0 | CFG | inspect |  |
| J-04 | `interlock` removed or misspelt on a heater or valve pair; silently accepted by config | 🔴 P0 | CFG | inspect |  |
| J-05 | DS18B20 `address:` values in `hw-real.yaml` are copied from a different physical unit during commissioning, producing the same wrong-probe-mapping fault as B-05 but via a config/documentation mistake rather than a wiring swap; caught by comparing the logged first-boot addresses against what is committed, not by warming a pack | 🔴 P0 | CFG | inspect |  |
| J-06 | Sensor id renamed in `hw-real.yaml` without base.yaml following; config fails, or falls back to a template with NaN | 🟡 P2 | CFG | inspect |  |
| J-07 | Interval changed from 5 s; fault timing constants (300 s, 5 ticks) no longer mean what the docs say | 🟡 P2 | CFG | inspect |  |
| J-08 | NVS full or erased on a flash update; all tunables back to defaults mid-run, no notification | 🔵 P3 | FW | bench |  |
| J-09 | `number` entity min/max allow physically unsafe values (`overtemp` up to 125 °C — above the SF129E's 118 °C holding temperature — `regen_hold_min` down to 0); no firmware validation narrows these ranges below what the datasheet allows | 🟠 P1 | CFG | virtual | ✱ |
| J-10 | Two controllers with the same hostname/API key on one network; HA writes tunables to the wrong unit | 🟡 P2 | OPS | bench |  |

## K. Remote control, Home Assistant and network

| ID | Failure | Pri | Kind | Verify | Gap |
|---|---|---|---|---|---|
| K-01 | Manual `Heater A/B` switch toggled from HA or the web server turns on the in-service pack's heater for up to one 5 s tick, because `apply_outputs` only re-asserts state once per control tick (documented open item) | 🟠 P1 | FW | virtual | ✱ |
| K-02 | Manual `Valve A/B` switch toggled from HA opens or closes both valves for one tick for the same reason as K-01 — `apply_outputs` has not run again yet | 🟠 P1 | FW | virtual | ✱ |
| K-03 | HA automation or script spamming outputs faster than the tick; relay chatter | 🟠 P1 | OPS | virtual |  |
| K-04 | Unauthenticated web server on port 80 lets anyone on the LAN toggle heaters and valves | 🟠 P1 | OPS | bench |  |
| K-05 | Improv or captive-portal AP left active; anyone can rejoin the device to their own network and control it | 🟡 P2 | OPS | bench |  |
| K-06 | HA sends a tunable write with a bad value while a regen is in progress (e.g. `regen_temp` 30 °C); regen declared complete instantly | 🟡 P2 | FW | virtual |  |
| K-07 | HA `Restart` button pressed while HEATING; one extra regen cycle per press | 🔵 P3 | OPS | virtual |  |
| K-08 | WiFi reconnect storms consuming heap and loop time (see H-03) | 🟡 P2 | FW | bench |  |
| K-09 | API client count or web client count growth starves the loop | 🟡 P2 | FW | bench |  |
| K-10 | Device Builder OTA pushes a config for the wrong board variant (adopt selector drift) | 🟠 P1 | CFG | inspect |  |
| K-11 | A latched fault has no active push notification to the operator; the `Fault` binary_sensor (`device_class: problem`, base.yaml) does surface it to Home Assistant, so the gap is an HA-side alerting automation, not a missing firmware entity — nobody notices the existing entity for days without one | 🟡 P2 | OPS | virtual |  |
| K-12 | Sensor entities go `unavailable` in HA while the device keeps running on stale internal values; operator misreads the situation | 🔵 P3 | OPS | virtual |  |
| K-13 | mDNS/IP change after a site move; HA controls a stale address, writes lost silently | 🔵 P3 | OPS | bench |  |

## L. Display and telemetry

| ID | Failure | Pri | Kind | Verify | Gap |
|---|---|---|---|---|---|
| L-01 | Display blank or garbage (SPI cable, CS/DC swap, wrong `data_rate`); operator cannot see state or faults | 🔵 P3 | HW | bench |  |
| L-02 | Display shows a stale frame after a redraw stall; appears healthy while the controller is hung (see A-03) | 🔵 P3 | FW | bench |  |
| L-03 | "OVR" badge missing while override is active (invariant) | 🔵 P3 | FW | virtual |  |
| L-04 | Fault code shown but not the fault message, or vice versa | ⚪ P4 | FW | virtual |  |
| L-05 | Pack colours or airflow arrows disagree with actual valve/heater state (UiState gathered before `apply_outputs`) | ⚪ P4 | FW | virtual |  |
| L-06 | Temperature or RH displayed with the wrong unit or rounding | ⚪ P4 | FW | virtual |  |
| L-07 | `/screen.png` returns 500 (rotation or palette changed) | ⚪ P4 | FW | virtual |  |
| L-08 | Screen mirror fetch tears the frame or delays redraws | ⚪ P4 | FW | virtual |  |
| L-09 | IP address shown stale after reconnect | ⚪ P4 | FW | bench |  |
| L-10 | Backlight stuck off (LEDC channel not initialised) with the panel drawing correctly | ⚪ P4 | HW | bench |  |
| L-11 | Debug sensors (free heap, largest block, loop time) not updating; memory problems go unnoticed | ⚪ P4 | FW | bench |  |
| L-12 | Heater A LED on GPIO13 read as a "status OK" light by an operator | ⚪ P4 | OPS | inspect |  |

---

## Issue grouping

Proposed GitHub issues for turning this catalogue into work. Each issue is
scoped so one coding agent can close it in one PR: a firmware/config change
plus the matching virtual or bench test, or — for `inspect`-only rows — one
written checklist. "Highest Pri" is the highest priority among the rows the
issue covers, using the scale above.

| # | Issue title | IDs | Highest Pri |
|---|---|---|---|
| 1 | Verify relay contact and heater-element failure behaviour on the bench and live rig | A-01, A-13, A-19, A-20, A-21, A-22 | P0 |
| 2 | Add firmware detection for a stuck-on heater path (driver, GPIO, interlock, wrong relay) | A-02, A-03, A-05, A-06 | P0 |
| 3 | Verify PN2222A driver-stage support components (flyback diode, base/pulldown resistors, coil supply, LED coupling) | A-18, A-23, A-25, A-28 | P1 |
| 4 | Verify heater harness, partial-failure detection and boot-time relay glitch | A-24, A-26, A-27, A-29 | P2 |
| 5 | Extend heater fault detection to rate-of-rise and NaN-skipped overtemp cases | B-01, B-02, B-03, B-04 | P0 |
| 6 | Reject implausible DS18B20 readings (85 °C sentinel, out-of-range, noise spikes) | B-06, B-07, B-08, B-24 | P1 |
| 7 | Verify DS18B20 probe-mapping, bus wiring and CRC-error tolerance | B-05, B-09, B-10, B-11 | P0 |
| 8 | Verify pack-probe mounting failure modes and cross-talk plausibility | B-13, B-15, B-17, B-23 | P1 |
| 9 | Guard overtemp/cooldown tunables against unsafe or inconsistent limits | B-16, B-18, B-19, B-20, B-21, B-22 | P1 |
| 10 | Detect SHT45 dropout, freeze and saturation | C-01, C-02, C-04, C-12 | P2 |
| 11 | Guard against humidity baseline drift and override misuse | C-05, C-06, C-07, C-08, C-09, C-10 | P2 |
| 12 | Cross-validate `arm_rh` against `swap_rh` | C-11 | P2 |
| 13 | Detect both-valves-open/closed faults and stalled swaps in firmware | D-01, D-02, D-03, D-16 | P1 |
| 14 | Verify valve solenoid and MOSFET driver failure modes on the bench and live rig | D-04, D-05, D-06, D-08, D-09, D-10 | P1 |
| 15 | Verify valve wiring, airflow path obstructions and Force Swap misuse | D-07, D-11, D-12, D-13, D-14, D-15 | P1 |
| 16 | Verify case fan failure, fan-stuck-on and thermostat reset behaviour | E-01, E-02, E-03, E-05 | P1 |
| 17 | Verify enclosure airflow, ambient derating and fan wiring polarity | E-06, E-07, E-10 | P1 |
| 18 | Verify PSU FG/PE bonding and output-to-mains short protection | F-01, F-02 | P0 |
| 19 | Verify 24 V rail fault tolerance (reverse polarity, overvoltage, hiccup, inrush) | F-03, F-04, F-05, F-06 | P1 |
| 20 | Verify MP1584 buck regulation, ripple and USB back-feed paths | F-07, F-08, F-09, F-10 | P1 |
| 21 | Verify 5 V rail protection, brownout margin and mains-dip relay state | F-11, F-12, F-14, F-15, F-16 | P1 |
| 22 | Verify power-loss-mid-swap recovery and ground-loop noise | F-17, F-18 | P2 |
| 23 | Verify header pin-map, socket seating and solder-bridge risks | G-01, G-06, G-08, G-11 | P0 |
| 24 | Verify watchdog reboot-loop and boot-priority output safety | H-02, H-07, H-08, H-12, H-16 | P1 |
| 25 | Verify loop-stall, heap and stack exhaustion effects on fault timers | H-03, H-04, H-06, H-15 | P1 |
| 26 | Harden persisted counters against NVS wear, corruption and `millis()` wrap | H-05, H-09, H-10 | P2 |
| 27 | Verify `apply_outputs`/interlock ordering races and the `time_scale` invariant | H-13, H-14, H-17 | P1 |
| 28 | Add a thermal plausibility model beyond fixed overtemp/no-rise thresholds | I-02, I-03, I-04, I-23, I-25 | P1 |
| 29 | Escalate latched faults instead of letting valves and service time run on | I-05, I-06, I-07, I-24 | P1 |
| 30 | Fix standby state-machine dead ends (stuck WET, stuck COOLING, rapid alternation) | I-08, I-09, I-13, I-19, I-20 | P2 |
| 31 | Verify regen-completion correctness across reboots and cold starts | I-10, I-11, I-12, I-15, I-21 | P2 |
| 32 | Add tunable cross-validation and detect a regen with no RH improvement | I-14, I-16, I-17, I-18, I-22 | P2 |
| 33 | Guard tunable persistence against unsafe ranges, NVS loss and hostname/API collisions | J-08, J-09, J-10 | P1 |
| 34 | Guard manual switch toggles and automations against racing the control tick | K-01, K-02, K-03 | P1 |
| 35 | Harden network exposure (unauthenticated web server, captive portal left open) | K-04, K-05 | P1 |
| 36 | Verify HA tunable-write and Restart button edge cases mid-cycle | K-06, K-07 | P2 |
| 37 | Verify control loop resilience under WiFi/API/web-client load | K-08, K-09 | P2 |
| 38 | Surface latched faults and stale entities to the operator | K-11, K-12, K-13 | P2 |
| 39 | Fix display staleness and hang-masking during redraw stalls | L-01, L-02, L-07, L-08, L-10 | P3 |
| 40 | Fix fault, state and unit accuracy on the display and telemetry | L-03, L-04, L-05, L-06, L-09, L-11 | P3 |
| 41 | Write mains heater-path pre-power inspection checklist | A-04, A-07, A-08, A-09, A-10, A-11 | P0 |
| 42 | Write mains wiring, creepage and earthing inspection checklist | A-12, A-14, A-15, A-16, A-17, G-09 | P0 |
| 43 | Write enclosure and mechanical assembly inspection checklist | G-07, G-12, G-13, G-14, E-08, E-09 | P0 |
| 44 | Write sensor wiring and placement inspection checklist | B-12, B-14, C-03, C-13, G-05, G-10 | P1 |
| 45 | Write board, header and display assembly inspection checklist | G-02, G-03, G-04, G-15, F-13, F-19 | P1 |
| 46 | Write firmware build and config pre-flight inspection checklist | J-02, J-03, J-04, J-05, J-06, J-07 | P0 |
| 47 | Write deployment and adoption-selector inspection checklist | H-18, K-10, L-12 | P0 |

## Priority roll-up

| Priority | Count | Themes |
|---|---|---|
| P0 | 31 | Welded or stuck-on heater path, missing thermal fuse, probe/valve/relay mapping errors, mains wiring and creepage, firmware hang with heater on, no software detection of "heater off but still heating" |
| P1 | 68 | Single-layer protection losses, sensor plausibility gaps, 24 V and 5 V rail faults, valves stuck, manual HA toggles |
| P2 | 61 | Wet air delivered, silent stalls, NaN and frozen sensors, state machine dead ends |
| P3 | 29 | Wasted regens, nuisance faults, manual resets |
| P4 | 10 | Display and telemetry only |

Suggested first targets for the verify suite, in order: A-01/B-02 (welded
relay detection), B-01/I-04/I-23 (heater with no rise, continuously not
just at 5 min), B-05/J-05 (probe mapping), B-06/B-07/B-08 (85 °C,
out-of-range and frozen probe values), A-03/H-02 (hang and reboot-loop
behaviour of the outputs), K-01/K-02 (manual toggles), I-05/K-11 (latched
fault escalation).

## Retired IDs

Rows merged into another ID during the 2026-09-16 consolidation pass. The
number is not reused; do not renumber the survivors.

| Retired | Merged into | Reason |
|---|---|---|
| I-01 | B-02 | Same test: no firmware check for a pack temperature rising with its heater commanded off (welded relay/driver). |
| H-01 | A-03 | Same test: a stuck-high heater GPIO from a firmware crash/hang, recovered by the watchdog and `on_boot` forcing outputs off. |
| E-04 | B-16 | Same test: the case DS18B20 reporting NaN leaves the fan thermostat's behaviour undefined. |
| H-11 | H-10 | Same test: a persisted counter or `heat_start_temp` restored as garbage after NVS corruption; `on_boot` only clamps three of the integer globals. |
| J-01 | B-19 | Same test: a `restore_value: true` tunable keeps an old, less-safe value across a firmware upgrade — the running example in both rows was `overtemp` 120 → 110 °C. |
