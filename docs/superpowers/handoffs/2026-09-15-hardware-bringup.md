# Handoff: hardware bring-up session (paste this as the first message of a fresh session)

You are continuing work on `/Users/josh/GitHub/desiccant-dryer`, an ESPHome (2026.1.4,
ESP-IDF) controller for a twin-tower desiccant air dryer on a SparkFun ESP32-S2
Thing Plus. Today's job: flash the production build onto the board once the real
hardware is wired to it, verify the wiring end to end, fill in the DS18B20
addresses, and leave the results in a PR. Work autonomously; ask the user only
for the bench steps that need hands (warming probes, listening for valve clicks,
metering).

## Read first, in this order

1. `CLAUDE.md` (project rules and invariants; the Open items list is current)
2. `docs/hardware-bringup.md` (the procedure you are executing)
3. `docs/control-logic.md` (what the controller does; "Test sequence on the real unit")
4. `docs/hardware.md` (pin map and wiring the hardware person followed)
5. `.superpowers/sdd/progress.md` (gitignored ledger of everything done so far)

Do not re-brainstorm or re-plan the bring-up; the plan is `docs/hardware-bringup.md`.

## State of the repo and bench (as of 2026-09-14 evening)

- `main` holds everything: package split (`esphome/packages/base.yaml`,
  `hw-real.yaml`, `hw-virtual.yaml`, `display.yaml`), persisted elapsed-time
  logic, `apply_outputs`, boot ordering fix, 25 s probe-dropout tolerance, CI
  (`.github/workflows/build.yml`, Docker image `ghcr.io/esphome/esphome:2026.1.4`).
  PRs #1 and #2 are merged. Both builds compile; the toolchain is cached.
- One board only. It currently runs the **virtual** build
  (`esphome/desiccant-dryer-virtual.yaml`) as an overnight soak at Sim Speed 60.
  Serial port `/dev/cu.usbserial-210` (macOS names it by USB location; if the
  board moves ports the name changes; `ls /dev/cu.usbserial*`). Its MAC is
  `7c:df:a1:55:b1:02`. `esphome/secrets.yaml` is gitignored and the user's to
  edit (never print it or edit its passwords). Before flashing, confirm with the
  user that it has the two-site keys (`wifi_home_ssid`/`_password` and
  `wifi_workshop_ssid`/`_password`) in place of the old `wifi_ssid`/`wifi_password`;
  otherwise the config fails to validate. The board got
  `10.42.14.100` by DHCP both times; treat it as likely but read the real one
  from the boot log, which prints `IP x.x.x.x` two seconds after WiFi connects.
  `.local` mDNS does not resolve from this Mac.
- Home Assistant test instance: `http://10.42.14.102`. The virtual device is
  paired there. The production build is a different device name
  (`desiccant-dryer`), so the user pairs it as a new device with the same
  `api_key` from `esphome/secrets.yaml`; ask them to do that after the flash.
- First check of the soak: read `sensor/uptime` on the virtual device (see REST
  below). Uptime roughly equal to the time since about 19:35 on 2026-09-14 with
  `fault_message` empty means it ran the night without a crash. Record it.
- A trial production flash was already done on the bare board on 2026-09-14
  19:32 (no hardware attached). Result, useful as a baseline: `Boot:` line
  first, WiFi and IP OK, display buffer allocated (8-bit palette), `sht4x`
  "Communication failed" (expected, no SHT45), and `one_wire: Found no devices!`
  (expected, no probes). If you see "Found no devices!" tomorrow with probes
  attached, it is wiring: DQ of all three to GPIO37, one 4.7 kΩ pullup to 3.3 V,
  VDD on 3.3 V, no parasitic power.
- Quirk: ESPHome preferences persist across a virtual/production reflash because
  the global ids are identical, so the production build boots with the virtual
  run's `active_pack`/`standby_state`/counters. The `Boot:` line will show
  non-zero values; that is not a defect. Turn `Dryer Enabled` off then on for a
  clean start when you begin the cycle test.

## How to drive the board

- Flash over USB: `esphome run --no-logs --device /dev/cu.usbserial-210 esphome/desiccant-dryer.yaml`
  (2 to 4 min; Bash timeout 600000 ms; macOS has no `timeout` command).
  Later flashes over the air: `--device <ip>`.
- Serial log (captures boot): `perl -e 'alarm 45; exec @ARGV' esphome logs --device /dev/cu.usbserial-210 esphome/desiccant-dryer.yaml 2>&1 | sed 's/\x1b\[[0-9;]*m//g' > file`.
  Opening the port does not reset the board. To capture a boot, start the log
  in the background, `sleep 4`, then press Restart over REST. A USB flash ends
  with a hard reset, so a log started right after it sees the boot.
- Network log (no boot lines): same command with `--device <ip>`.
- REST (ESPHome web server): reads `curl -s http://<ip>/text_sensor/dryer_status`
  (any entity: `/switch/valve_a`, `/sensor/pack_a_temperature`, `/number/regen_temp`,
  ...), each returns JSON with `state`. Writes need an empty body:
  `curl -s -X POST -d '' http://<ip>/switch/dryer_enabled/turn_off`,
  `.../number/regen_temp/set?value=30`, `.../button/restart/press`. Object-id
  URLs work but are deprecated; entity-name URLs like
  `/switch/Dryer%20Enabled/turn_off` are the future form.
- `Simulate Humidity` + `Simulated RH` (base build feature) stand in for the
  missing SHT45 during the cycle test; they never persist across reboot.

## What to deliver

1. `esphome/packages/hw-real.yaml` with the three real DS18B20 addresses in the
   right slots (pack A, pack B, case), committed on a branch, PR opened per the
   user's global PR workflow (rebase on `origin/main`, watch CI, address the
   Copilot review). CI compiles both builds.
2. The filled-in bring-up results: which port, the three addresses and which
   probe is which, every row of the outputs table with what was observed, the
   display offset that worked, and the cycle-test log lines. Put them in a PR
   comment and in `docs/hardware-bringup.md` section 6.
3. Any wiring or firmware defect found, fixed if it is firmware, reported
   precisely if it is wiring.
4. At the end, leave the board on the production build unless the user asks
   for the virtual build back (`esphome/desiccant-dryer-virtual.yaml`).

## Ground rules

- Nothing here switches mains: heater GPIOs drive 2N2222 bases only; valves and
  fan are 24 V. Still, never toggle outputs while `Dryer Enabled` is on except
  through the controller; disable it first for manual output tests.
- Do not invent sensor addresses, thresholds, or "tested" values; mark anything
  unverified. Keep C++ in lambdas small.
- Ask the user before any output test that needs them at the bench, and give
  them one instruction at a time (warm probe 1; now probe 2; ...).
- Bench facts that changed (new IP, new port) go into
  `.superpowers/sdd/progress.md` and, if durable, the memory directory.
