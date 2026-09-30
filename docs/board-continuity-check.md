# Board continuity check

A multimeter pass to confirm that everything moved from the breadboard to
the logic and relay protoboards correctly, and that nothing extra got
connected on the way. Steps 1–6 prove the right points connect; step 7
proves no pad is bridged to its neighbour. The formal sign-off, including
earthing and creepage, is `docs/inspection-checklist.md`; the nets are
listed in [hardware.md](hardware.md#net-list--logic--24-v-board).

**Before you start:** ESP pulled out of its sockets, 24 V supply off, mains
unplugged. Probe a socket position by pushing a stiff wire or a spare
header pin into it.

In-circuit readings run a little low because other parts sit in parallel.
Beep mode: a steady resistance with no beep is normal where resistors sit
in the path.

## Socket map

Both rows counted from the USB end. **Bold** = wired on this board.

| # | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 12-pin | BAT | EN | **USB** (5 V in) | **13** heater A | **12** heater B | **11** valve A | **10** valve B | **8** fan | 6 | 4 | SCL=2 | SDA=1 | | | | |
| 16-pin | EN | **3V3** | NC | **GND** | **17** BLK | 18 | 14 | **9** RES | **7** DC | **5** CS | **36** SCK | **35** MOSI | **37** 1-wire | 33 | 34 | 3 |

## 1. Shorts

Beep mode. **Nothing here should beep.** The 100 µF caps may chirp while
they charge, then the reading climbs; a steady beep is a short.

- [ ] 24V+ and GND: open
- [ ] 5 V bus and GND: open
- [ ] 3V3 (16-pin #2) and GND (16-pin #4): open
- [ ] Neighbouring 12-pin positions 13 / 12 / 11 / 10 / 8 to each other: open
- [ ] BAT (12-pin #1) to anything: open

## 2. Output channels

Resistance mode. Heaters go through the JST harness to the relay board;
valves and fan are MOSFET channels on the logic board. The relay-board
base pulldowns are 1 kΩ; the 1 kΩ *series* resistors sit on the logic
board. If the relay board has 10 kΩ in series and 1 kΩ to ground, the
values are swapped and the relay won't pull in.

| | From → To | Mode | Expect |
|---|---|---|---|
| [ ] | GPIO13 (12-pin #4) → harness pin 3, logic-board end | Ω | ~1 kΩ |
| [ ] | GPIO12 (12-pin #5) → harness pin 4, logic-board end | Ω | ~1 kΩ |
| [ ] | Harness pin 3, relay-board end → PN2222A A base; base → GND | Ω | ~0 Ω; ~1 kΩ |
| [ ] | Harness pin 4, relay-board end → PN2222A B base; base → GND | Ω | ~0 Ω; ~1 kΩ |
| [ ] | Harness pins match end to end: 1 = 5 V, 2 = GND, 3 = GPIO13, 4 = GPIO12 | beep | 1:1 |
| [ ] | GPIO11 (12-pin #6) → valve A IRLZ44N gate; gate → GND | Ω | ~100 Ω; ~10 kΩ |
| [ ] | GPIO10 (12-pin #7) → valve B IRLZ44N gate; gate → GND | Ω | ~100 Ω; ~10 kΩ |
| [ ] | GPIO8 (12-pin #8) → fan IRLZ44N gate; gate → GND | Ω | ~100 Ω; ~10 kΩ |
| [ ] | 5 V bus → each PN2222A collector, through the relay coil | Ω | ~70 Ω (datasheet nominal, not measured) |
| [ ] | Each IRLZ44N drain → its load block "SW" terminal | beep | ~0 Ω |
| [ ] | Relay A is the one wired to heater A (and B to B) | beep | matches |

With the harness plugged in, a GPIO13/12 socket position reads about 2 kΩ
to GND (the 1 kΩ series resistor plus the 1 kΩ pulldown).

A gate-to-GND reading that hunts between a few kΩ and open means the
10 kΩ gate pulldown is not connected: the meter is charging the gate
capacitance. Check the resistor's joints and its link to the GND bus
before powering up (failure mode D-08).

## 3. Display header

Commit `0bc5b6c` moved DC to GPIO7 and RST to GPIO9 (previously DC→9,
RST→14). A board copied from an older breadboard leaves the display dark.

| | Socket | Display header | Expect |
|---|---|---|---|
| [ ] | GND (16-pin #4) | 1 · GND | beep |
| [ ] | 3V3 (16-pin #2) | 2 · VCC | beep |
| [ ] | GPIO36 (16-pin #11) | 3 · SCL | beep |
| [ ] | GPIO35 (16-pin #12) | 4 · SDA | beep |
| [ ] | **GPIO9 (16-pin #8)** | **5 · RES** | beep |
| [ ] | **GPIO7 (16-pin #9)** | **6 · DC** | beep |
| [ ] | GPIO5 (16-pin #10) | 7 · CS | beep |
| [ ] | GPIO17 (16-pin #5) | 8 · BLK | beep |

## 4. 1-wire bus

| | From → To | Mode | Expect |
|---|---|---|---|
| [ ] | GPIO37 (16-pin #13) → 3V3 (16-pin #2), the pullup | Ω | ~4.7 kΩ |
| [ ] | GPIO37 → each DS18B20 DQ screw terminal (×3) | beep | ~0 Ω |
| [ ] | Each probe's GND terminal → GND, VDD terminal → 3V3 (×3) | beep | ~0 Ω |

## 5. Power path

| | From → To | Mode | Expect |
|---|---|---|---|
| [ ] | Buck OUT+ → harness pin 1 and Schottky anode | beep | ~0 Ω |
| [ ] | Schottky: red on anode, black on cathode (JP-USB pin 2); then reversed | diode | 0.15–0.3 V; OL |
| [ ] | JP-USB pin 1 → USB (12-pin #3) | beep | ~0 Ω |
| [ ] | 24 V on, ESP still out, JP-USB out: buck OUT+ to GND | V DC | 5.00–5.10 V |

## 6. Relay board, mains side

Mains unplugged and F1 pulled for every line here.

| | Check | Mode | Expect |
|---|---|---|---|
| [ ] | Coil unpowered: COM → NC beeps, COM → NO open. Heater "L sw" leaves **NO**; NC is empty | beep | NC closed, NO open |
| [ ] | Across each heater, cold | Ω | ~123 Ω |
| [ ] | PSU L terminal → fused side of F1 only; no continuity to inlet L with F1 out | beep | fused side only |

## 7. No bridges between pads

ESP still out, everything unpowered. In beep mode, **nothing here should
beep.**

| | Between | Mode | Expect |
|---|---|---|---|
| [ ] | 12-pin socket: every neighbouring pair, #1–2 through #11–12. Watch **USB–13** (#3–4, 5 V onto a 3.3 V pin) and **EN–USB** (#2–3) | beep | no beep |
| [ ] | 16-pin socket: every neighbouring pair, #1–2 through #15–16. Watch **9–7** (RES–DC), **36–35** (SCK–MOSI) and **35–37** | beep | no beep |
| [ ] | Display 8-pin header: each neighbouring pair, 1–2 through 7–8 | beep | no beep |
| [ ] | JST harness header, on both boards: 1–2, 2–3, 3–4 | beep | no beep |
| [ ] | 9-position sensor block: each neighbouring pair. 3V3–DQ reads the pullup | Ω | ~4.7 kΩ, never 0 |
| [ ] | 24 V load blocks (valve A, valve B, fan): 24+ to SW on each | beep | no beep |
| [ ] | Every used GPIO socket position → GND, → 3V3, → 5 V | beep | no beep |
| [ ] | Each IRLZ44N: gate → source | Ω | ~10 kΩ, never 0 |
| [ ] | Each IRLZ44N: red on drain, black on source; reversed shows the body diode, which is normal | diode | OL; ~0.5 V reversed |
| [ ] | Each PN2222A: base → emitter | Ω | ~1 kΩ, never 0 |
| [ ] | **Mains isolation:** each relay COM, NO and NC pin, both F1 clips and every mains terminal → 5 V bus and → GND bus | Ω, top range | OL, every one |
| [ ] | Solder side of both boards under a magnifier: every pair of neighbouring pads, above all around the sockets and relay COM pins. Hairline whiskers and flux-filled gaps can pass a meter and short once warm | eyes | clean gaps |
