# Human inspection checklist

The visual and hands-on checks for the ESP32 desiccant dryer controller that
replaces the original control board in an Azco VMD-08 dryer. Every `inspect`
row in `docs/failure-modes.md` appears here exactly once (the ID in bold is
the failure mode the check guards against), expanded into what to look at and
what "pass" means. A few bench and live rows (for example G-08, A-13,
A-01/A-19 and the buck preset) are included too, because a human does them
with a meter at the same visit; they are the commissioning subset, and the
automated verify suite still owns them. Adding an `inspect` row to the
catalogue means adding its item here in the same change.

Work the stages in order. Stages 1 to 5 are done with **mains disconnected
and the 24 V supply off**. Stage 6 is the first energised check. Stage 7 is
repeated at every service visit.

Item format, for people and for agents:
`- [ ] **ID** What to check. **Pass:** the condition. *(tool)*`

Sign off each stage at the bottom before moving to the next.

---

## Stage 1 · Board and header assembly (mains off, 24 V off)

Reference: `docs/hardware.md`, `docs/board-layout.svg`, `docs/pinout-verification.md`.

- [ ] **G-02** ESP32-S2 Thing Plus seated in its 16-pin and 12-pin sockets. **Pass:** USB-C end and antenna end match the silkscreen, no empty socket pin at either end, no pin bent under the module. *(eyes, torch)*
- [ ] **A-04** Both relay-driver transistors. **Pass:** marking reads `PN2222A` (pinout E-B-C, flat face toward you). A `P2N2222A` (C-B-E) is a reject; do not power the board. *(magnifier)*
- [ ] **F-13** Both 100 µF electrolytics. **Pass:** stripe (negative) on the GND side of the silkscreen on each board, can flat, no bulge or residue. *(eyes)*
- [ ] **F-19** ESP BAT pin and JST battery connector. **Pass:** nothing wired to BAT; 5 V from the buck lands only on the USB pin through the Schottky and JP-USB. *(eyes, continuity: BAT to 5 V bus open)*
- [ ] **G-15** MP1584 buck module fit. **Pass:** module sits flat on its own header holes with no forced or bent pins; if the vendor footprint differs from the drilled holes it is on flying leads, not sprung into place. *(eyes)*
- [ ] **G-15** Buck output preset. **Pass:** 5.00 to 5.10 V measured at the module OUT+ pad with 24 V applied to the module alone and JP-USB **removed**. *(meter)*
- [ ] **G-03** Display cable order. **Pass:** module header reads GND / VCC / SCL / SDA / RES / DC / CS / BLK in that order (LCDWIKI or QDtech MSP1541 style) and matches the board header 1:1. A Waveshare module (VCC GND DIN CLK CS DC RST BL) needs a re-pinned cable; straight-through is a reject. *(eyes, module silkscreen)*
- [ ] **G-04** Display backlight input. **Pass:** BLK to VCC measures about 10 kΩ unpowered, showing an on-module transistor. A near-zero or diode-like reading means BLK is a bare LED anode; do not connect GPIO17 to it. *(meter)*
- [ ] **G-05** SHT45 on the Qwiic cable. **Pass:** genuine Qwiic/STEMMA QT breakout on a 4-pin JST-SH cable, black to GND, red to 3.3 V. A breakout with a different 4-pin order is rewired before plugging in. *(eyes)*
- [ ] **G-08** Solder side of both boards under magnification. **Pass:** no bridge between adjacent pins on GPIO12/13 (heaters), GPIO10/11 (valves), or between any mains pad and its neighbours. *(magnifier, continuity)*
- [ ] **A-28** Blue LED on GPIO13. **Pass:** understood as "heater A relay commanded", nothing else connected to that net on the board. *(eyes)*

## Stage 2 · Mains heater path (mains off)

Reference: `docs/hardware.md` relay board section, `docs/datasheets/thermal-fuse/`.

- [ ] **A-11** Fuse F1. **Pass:** 5×20 mm, **T 3.15 A** (time-delay) marked on the cap, seated in a covered holder in the L lead. Any fast-blow, any other rating, or a bridged holder is a reject. *(eyes)*
- [ ] **A-12** Where the 24 V PSU takes its L. **Pass:** the PSU L terminal is fed from the **fused** side of F1 (continuity from the fuse's load end, none from the inlet L with the fuse pulled). *(continuity with F1 removed)*
- [ ] **A-10** L and N at the inlet terminal block. **Pass:** the conductor that goes through F1 and the relays is the one from the inlet **line** pin; neutral runs straight through, unswitched. Check with the plug's polarity, not wire colour alone. *(eyes, continuity to plug pins)*
- [ ] **A-09** Relay contact used. **Pass:** each heater's switched L leaves the relay's **NO** pin; the NC pin is empty. Identify NO/NC by continuity with the coil unpowered (COM to NC closed, COM to NO open). *(continuity)*
- [ ] **A-07** Thermal fuse present on each pack. **Pass:** one SF129E in series in each heater's switched-L lead, between relay NO and the heater, on the pack it protects. No jumper, no fuse on the shared side. *(eyes, continuity)*
- [ ] **A-08** Thermal fuse placement. **Pass:** clamped in metal-to-metal contact with the **pack body** next to that pack's DS18B20, not on the heater sheath and not in free air; clamp does not move by hand. *(hands)*
- [ ] **G-14** Thermal fuse and heater tail terminations. **Pass:** crimped with the correct die (no solder, no twisted-and-taped joints), pull test held, sleeved in fibreglass or silicone rated for 133 °C or more. *(hands, pull test)*
- [ ] **A-17** Mains conductors near the packs. **Pass:** 18 AWG stranded, 300 V, 105 °C or better; silicone with fibreglass sleeve on the last run to the pack; no PVC touching a pack surface. *(eyes, wire marking)*
- [ ] **G-13** Strain relief at the pack. **Pass:** heater tails and fuse leads are clamped so that tugging the loom does not move the conductor at the crimp. *(hands)*
- [ ] **A-13** Heater elements cold. **Pass:** about 123 Ω across each heater; more than 1 MΩ from each heater terminal to its sheath. *(meter)*
- [ ] **A-30** Heater current sensing. **Pass:** either a current sense is fitted in the switched-L lead and its reading reaches Home Assistant, or `docs/hardware.md` records the decision not to fit one, accepting that a welded contact (A-01) or an open element (A-22) is visible only as a temperature symptom. *(eyes, docs)*
- [ ] **A-31** Over-temperature backstop. **Pass:** either a self-resetting cutout is fitted in series ahead of the SF129E, or `docs/hardware.md` records that the one-shot fuse alone is accepted and the enclosure carries a label saying a trip means opening the pack to replace it. *(eyes, docs)*

## Stage 3 · Mains wiring, creepage and earthing (mains off)

- [ ] **G-09** Terminal block usage. **Pass:** every mains conductor lands in a **mains-rated** block (UL1059 300 V / 10 A or IEC 250 V class) on the relay board; no mains conductor in a 24 V or sensor block, and no 24 V conductor in a mains block. Label each block. *(eyes)*
- [ ] **A-16** Terminal torque and wire prep. **Pass:** stranded mains wire is ferruled, no loose strands, each conductor holds a firm pull; no conductor passes through a protoboard hole. *(hands, pull test)*
- [ ] **A-15** Creepage on the protoboard. **Pass:** at least two cleared rows (pads removed or slot cut) between any mains pad and any logic or 24 V pad, no plated pad left in the gap, board clean of flux. *(eyes, ruler)*
- [ ] **A-14** Protective earth. **Pass:** inlet PE to each heater sheath, to the chassis and to the PSU FG terminal each reads under 0.1 Ω, all bonded at one star point that is not on the protoboard. *(low-ohms meter)*
- [ ] **F-02** PSU FG. **Pass:** the LRS-35-24 FG screw has its own PE conductor, not shared through the chassis paint. *(eyes, meter)*
- [ ] **F-01** PSU mounting and guarding. **Pass:** open-frame PSU mains terminals are covered, PSU standoffs are metal to the earthed chassis, no mains terminal within finger reach when the lid is open. *(eyes)*
- [ ] **G-12** Enclosure. **Pass:** metal enclosure bonded to PE; every mains lead that passes an edge or a panel has a grommet or sleeve; lid closes without pinching a lead. *(eyes, meter)*
- [ ] **G-10** Routing. **Pass:** mains L/N run as a twisted or tightly paired loom, at least 25 mm from the 1-wire, I2C and SPI cables, crossing at right angles where they must cross. *(eyes)*
- [ ] **A-06** Relay-to-heater identity. **Pass:** relay A (GPIO13, harness pin 3) feeds the heater on pack A, relay B (GPIO12, pin 4) feeds pack B, matched to the DS18B20 and valve labelled for the same pack. *(continuity, labels)*
- [ ] **G-16** Labelling. **Pass:** each pack, its heater tail, its DS18B20 lead and its valve carry a permanent A or B label that agrees with the relay and GPIO map, so a later reassembly cannot cross a pair. No unlabelled member of a pair. *(eyes)*
- [ ] **A-24** Relay harness. **Pass:** JST-XH 4-way plugged home with the latch engaged; pin 1 = 5 V, 2 = GND, 3 = GPIO13, 4 = GPIO12 at both ends. *(eyes, continuity)*

## Stage 4 · Sensors and placement (mains off)

- [ ] **B-12** DS18B20 leads on the packs. **Pass:** probe cable rated for the pack temperature (silicone, 150 °C class) or the stock PVC lead is re-terminated short of the hot zone; no lead touches a heater sheath. *(eyes, wire marking)*
- [ ] **B-14** Probe position. **Pass:** each pack probe is clamped to the **pack body** beside its thermal fuse, not on the heater sheath, not on a fitting. *(eyes, hands)*
- [ ] **B-05 / J-05** Probe identity. **Pass:** with the board powered from USB only, warm the pack A probe by hand and `Pack A Temperature` rises while B does not; repeat for B and for the case probe. Addresses in `hw-real.yaml` were read from **this** unit's log, not copied. *(hands, ESPHome log)*
- [ ] **B-10** 1-wire pullup. **Pass:** 4.7 kΩ between DQ and 3.3 V; all three probes on VDD/GND/DQ (not parasitic, VDD not tied to GND). *(meter)*
- [ ] **G-06** Sensor screw terminals. **Pass:** each of the nine positions holds its conductor on a pull, no stray strand bridging to a neighbour. *(hands)*
- [ ] **C-03** SHT45 position. **Pass:** mounted in the outlet stream **downstream of both valves**, in moving air, not in a dead leg and not where condensate can reach it. *(eyes, air-path drawing)*
- [ ] **C-13** SHT45 config. **Pass:** the `sht4x` entry in `hw-real.yaml` has no `heater_*` options enabled. *(read config)*
- [ ] **D-07** Valve identity. **Pass:** valve A opens the air path through pack A; confirmed by blowing through with valve A energised from the 24 V bench supply. Labelled to match the heater and probe. *(hands, 24 V bench supply)*
- [ ] **E-03** Case probe position. **Pass:** the case DS18B20 sits in the warmest part of the enclosure air (above the relays and PSU), not on a cold wall or in the fan intake. *(eyes)*

## Stage 5 · Firmware and configuration pre-flight (before flashing)

Reference: `CLAUDE.md` invariants, `docs/releasing.md`.

- [ ] **J-02** Selector used. **Pass:** the real unit is flashed from `esphome/desiccant-dryer.yaml` (production) or `desiccant-dryer-hw-test.yaml`; never from the virtual or host selector. `esphome config` output for the chosen selector contains no `Sim ` entities and no `hw-virtual`. *(read config dump)*
- [ ] **H-18** Image identity. **Pass:** after flashing, the device log's project name and version match the selector, and no `Sim *` entity appears in Home Assistant. *(log, HA)*
- [ ] **J-03** Output restore modes. **Pass:** `heater_a`, `heater_b`, `valve_a`, `valve_b`, `case_fan` each have `restore_mode: ALWAYS_OFF` in the config dump. *(grep config dump)*
- [ ] **J-04** Interlocks. **Pass:** `heater_a` and `heater_b` list each other under `interlock`; `valve_a` and `valve_b` do the same; both pairs have `interlock_wait_time: 500ms`. *(grep config dump)*
- [ ] **J-05** DS18B20 addresses. **Pass:** the three `address:` values in `hw-real.yaml` match the three ROM codes in **this** board's first-boot log. *(log vs file)*
- [ ] **J-06** Sensor ids. **Pass:** `air_rh`, `air_temp`, `pack_a_temp`, `pack_b_temp`, `case_temp` all resolve in the config dump to real sensors, not to fallback templates. *(config dump)*
- [ ] **J-07** Tick interval. **Pass:** the control `interval` in `base.yaml` is 5 s, and the no-rise fault window is still 300 s and the probe timeout still 5 ticks. *(read base.yaml)*
- [ ] **H-20** Panic behaviour. **Pass:** nothing in the config or `sdkconfig_options` sets the ESP-IDF panic handler to halt or to the GDB stub; it stays at the reboot default, so a crash cannot leave the relays in their last state. *(grep config dump)*
- [ ] **J-11** Persisted state compatibility. **Pass:** the firmware being flashed uses the same `standby_state` and `active_pack` numbering and the same counter units as the one it replaces; otherwise the unit's globals are erased as part of the update. *(diff `base.yaml` globals, release notes)*
- [ ] **B-19 / B-20** Tunables on this unit. **Pass:** in Home Assistant, `Pack overtemp limit` reads 110 °C or lower (below the SF129E holding temperature of 118 °C); `regen_temp` is below `overtemp`; `cooldown_temp` is below `regen_temp`; `arm_rh` is below `swap_rh`. *(HA entities)*
- [ ] **K-10** Adoption selector. **Pass:** `desiccant-dryer-adopt.yaml` references the release tag that exists on GitHub and the same component version as the flashed image. *(read file, `git tag`)*
- [ ] **F-10** JP-USB discipline. **Pass:** the shunt is **removed** before any USB-C cable is connected to the board, and refitted before the lid goes on. Write this on the enclosure. *(eyes, label)*

## Stage 6 · First energised check (24 V on, mains on, heaters disconnected at their terminals)

- [ ] **F-07 / F-08** Rails. **Pass:** 24.0 ± 0.5 V at the PSU; 5.00 to 5.10 V at the buck OUT+; 3.3 V on the ESP 3V3 pin. *(meter)*
- [ ] **A-29 / F-15** Power-on behaviour. **Pass:** neither relay clicks and no valve pulls in during power-up, boot, or a pressed `Restart`; the blue LED stays off until heater A is genuinely commanded (watch `Heater A Relay`). *(ears, eyes, three power cycles)*
- [ ] **A-05 / D-01** Interlock at the terminals. **Pass:** on the hw-test build (the only one with the manual switches; the release makes them `internal`), with `Dryer Enabled` off, toggling `Heater A` on then `Heater B` on from HA never shows both relay NO contacts closed at once; same for the two valves. *(meter on relay NO, eyes on valves)*
- [ ] **L-12** Operator indicators. **Pass:** the front display, not the blue LED, is the status indicator; the LED meaning is written on the enclosure. *(eyes)*
- [ ] **A-01 / A-19** Relay contacts. **Pass:** each relay reads open across COM-NO when off and under 0.1 Ω when on, over ten cycles. *(meter)*

## Stage 7 · Periodic (every service visit, mains off)

- [ ] **G-07** Vibration. **Pass:** every header, socket, JST latch and terminal screw is still tight; the ESP has not walked out of its socket. *(hands)*
- [ ] **E-09** Contamination. **Pass:** no desiccant fines, dust or oxidation on the relay board, terminal blocks or PCB; no discolouration around relay contacts or the fuse holder. *(eyes)*
- [ ] **E-08** Condensation. **Pass:** no water marks or corrosion tracks on the boards or enclosure floor, especially across the mains creepage band. *(eyes)*
- [ ] **A-07 / A-27** Thermal fuses. **Pass:** continuity through each SF129E; an open fuse is replaced, and the cause (see failure modes A-01, A-02, B-02) is found before the heater is reconnected. *(continuity)*
- [ ] **A-11** Fuse F1. **Pass:** still T 3.15 A, no evidence of replacement with another type. *(eyes)*
- [ ] **A-14** PE bonds. **Pass:** under 0.1 Ω inlet PE to each sheath and to the chassis. *(low-ohms meter)*
- [ ] **B-13 / A-08** Probe and fuse clamps. **Pass:** each still tight to the pack body; thermal paste, if used, not dried out. *(hands)*
- [ ] **D-06** Valve coils. **Pass:** no discolouration or smell on the VDW22 coils; body temperature after a regen cycle noted against the 50 °C rating (open item in `docs/hardware.md`). *(eyes, IR thermometer)*
- [ ] **E-01** Fan. **Pass:** spins freely by hand, starts when `Case Fan` is toggled, blows in the intended direction. *(hands)*

---

## Sign-off

| Stage | Inspector | Date | Unit serial | Notes |
|---|---|---|---|---|
| 1 Board and headers | | | | |
| 2 Mains heater path | | | | |
| 3 Mains wiring and earthing | | | | |
| 4 Sensors | | | | |
| 5 Firmware pre-flight | | | | |
| 6 First energised check | | | | |
| 7 Periodic | | | | |

A stage passes only when every box in it is ticked. Any reject stops the
sequence; do not connect mains until it is cleared.
