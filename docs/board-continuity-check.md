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

## PCB rev A

First-article check for the two printed circuit boards in
[hardware.md](hardware.md#printed-circuit-board-rev-a): the controller
board and the mains board, joined by the JST-XH 4-way link (J_RLY on the
controller, J_CTRL on the mains board; pin 1 = 5 V, 2 = GND, 3 = heater A,
4 = heater B). Run it on the first assembled pair, and again on any board
whose relay, fuse holder or 5 V module was changed. Nothing in this section
has been run yet: every "expect" value is derived from
`hardware/dryer_board/controller.py` and `mains.py` and the hardware.md
budget, not measured. The protoboard sections below
(Socket map to step 7) are for the protoboard build only; the socket map
and the socket-position numbering hold for both.

**Before you start:** ESP pulled out of its sockets, 24 V supply off, mains
unplugged, **the link cable unplugged at both ends unless an item says
otherwise, F1 holder empty, SW-USB slid toward its OFF legend.** OFF is defined electrically: SW1 pin 2 to pin 3 closed, pin 2 to pin 1 open (item 6 checks this with the meter). Probe socket positions with a
stiff wire or a spare header pin. Pin numbers are the ones in
hardware.md "Header pinouts" (J_MAINS 1 to 8, J_LOADS 1 to 6, J_24V 1 = 24V+,
2 = 0V). The test points: TP1 GND, TP2 3V3, TP3 5 V, TP4 24 V, TP5 to TP9
the HTR_A, HTR_B, VLV_A, VLV_B and FAN drive lines, all on the controller.
The mains board has no test points: its SELV references are J_CTRL pin 2
(GND) and pin 1 (5 V). K1 and K2 pads are numbered as on the relay (1 COM,
2 and 5 coil, 3 NO, 4 NC).

If any mains reading (items 1, 2, 3 or 8) is wrong, stop: do not apply
mains or connect a heater until it is understood.

### Item 0: Parts on hand, before they go on a board

| | Check | Expect |
|---|---|---|
| [ ] | The 5 V module (U1): current-limited 12 V supply, + on pin 1 and − on pin 2 (pin 1 is the end with the dot; 1 Vin, 2 GND, 3 Vout), nothing on pin 3 but the meter | 5.0 V on pin 3 to pin 2, under 20 mA drawn. A module that reads 0 V, the input voltage, or draws current with nothing on its output has another pinout: do not fit it. The Amazon-listed "TSR 1-2450" has no stated pinout (hardware/README.md) |
| [ ] | The fuse holder (F1): calipers across the two pins, centre to centre | 21.5 to 23.5 mm fits F1's slotted pads (the holders on hand should read about 22.3). A 15 mm holder needs the PTF-76-B footprint instead: do not force it |

### Item 1: Shorts

Beep mode, then the Ω range where noted. **Nothing here should beep.**
The bulk capacitors may chirp while they charge, then the reading climbs;
a steady beep is a short.

| | From → To | Mode | Expect |
|---|---|---|---|
| [ ] | J_24V pin 1 (24V+) → J_24V pin 2 (GND), either probe polarity | beep | open |
| [ ] | TP3 (5 V) → TP1 (GND) | beep | open |
| [ ] | TP2 (3V3) → TP1 (GND) | beep | open |
| [ ] | TP4 (24 V) → TP1 (GND) | beep | open |
| [ ] | J_RLY pin 1 (5 V) → J_RLY pin 2 (GND), controller | beep | open (C4 may chirp) |
| [ ] | J_CTRL pin 1 (5 V) → J_CTRL pin 2 (GND), mains board | beep | open |
| [ ] | Each J_MAINS pin 1 to 8 → J_CTRL pin 2 (GND), then → J_CTRL pin 1 (5 V) | Ω, top range | OL on all 16 readings (not merely no beep) |
| [ ] | Slot, SELV side J_CTRL pin 2 → mains side J_MAINS pin 2 (N) | MΩ range | OL |
| [ ] | Slot, SELV side J_CTRL pin 1 → mains side J_MAINS pin 7 (L fused) | MΩ range | OL |
| [ ] | K1 pad 2 and pad 5 (coil) → K1 pad 1 and pad 3 (contacts), each pair; same for K2 | MΩ range | OL (the coil is the only link across the slot, through its own pads) |
| [ ] | Look along the slot against a light | visual | the routed slot is open through the board in all five segments, with the four gaps only where the coil tracks cross |

### Item 2: Relay identity

Coil unpowered. This proves NO and NC are where the design says on the
parts actually fitted; hardware.md "Relay contacts: NO and NC" explains why
it must be checked. Pad 4 has no copper, so probe the relay's own pin.

| | From → To | Mode | Expect |
|---|---|---|---|
| [ ] | K1 pad 1 (COM) → J_MAINS pin 3 (HTR A) | Ω, top range | **open** |
| [ ] | K1 pad 1 (COM) → K1 pad 4 (NC), probe the pin | beep | **closed** |
| [ ] | K2 pad 1 (COM) → J_MAINS pin 5 (HTR B) | Ω, top range | **open** |
| [ ] | K2 pad 1 (COM) → K2 pad 4 (NC), probe the pin | beep | **closed** |

A closed COM-to-heater reading means NO and NC are swapped on the part
fitted: **stop, do not connect a heater.** Do not use that relay.

### Item 3: Fuse path

| | From → To | Mode | Expect |
|---|---|---|---|
| [ ] | J_MAINS pin 1 (L in) → pin 7 (PSU L), F1 holder empty | beep | open |
| [ ] | Same, with the T 3.15 A fuse fitted and the cover closed | beep | closed |
| [ ] | J_MAINS pin 7 → K1 pad 1, and → K2 pad 1 | beep | closed (fuse in or out) |
| [ ] | J_MAINS pin 2, 4, 6, 8 (N) to each other | beep | closed (N is straight through, unfused) |
| [ ] | J_MAINS pin 2 → pins 1, 3, 5, 7 | Ω, top range | OL |

Remove the fuse again before items 4 to 8 unless a step says otherwise.

### Item 4: Plug keying

| | Check | Expect |
|---|---|---|
| [ ] | Each pluggable plug (24 V 2-pin, loads 6-pin, mains 8-pin, sensors 9-pin) is offered to its own header | seats fully |
| [ ] | The 8-pin mains plug is offered to the 6-pin J_LOADS header and the 2-pin J_24V header | does not enter |
| [ ] | The 3.5 mm sensor plug is offered to every other header | fits only J_SENS |
| [ ] | The display cable is offered to every other header | fits only J_DISP |
| [ ] | The link cable is offered to J_DISP and J_SENS | does not enter (2.5 mm pitch) |
| [ ] | The link cable is plugged into J_RLY and J_CTRL | latch engages at both ends; pin 1 (5V legend) to pin 1 |

### Item 5: Drivers

Resistance mode, from the socket positions (the ESP is out). In-circuit
readings run a little low. Transistor pins: Q1 and Q2 are 1 B, 2 E, 3 C; Q3
to Q5 are 1 G, 2 S, 3 D. Probe the resistor junction pad where the
transistor pin is too small to hold.

| | From → To | Mode | Expect |
|---|---|---|---|
| [ ] | Controller: 12-pin 4 (heater A) → J_RLY pin 3; 12-pin 5 (heater B) → J_RLY pin 4 | Ω | ~1 kΩ (R1, R4) |
| [ ] | Mains board: J_CTRL pin 3 → Q1 base; J_CTRL pin 4 → Q2 base | beep | ~0 Ω |
| [ ] | Mains board: Q1 base → J_CTRL pin 2 (GND); Q2 base → J_CTRL pin 2 | Ω | ~1 kΩ (R2, R5) |
| [ ] | Q1 pin 3 (collector) → K1 pad 5; Q2 pin 3 → K2 pad 5 | beep | ~0 Ω |
| [ ] | J_CTRL pin 1 (5 V) → K1 pad 5, and → K2 pad 5, red on pin 1 | Ω | the coil alone (the LED branch does not conduct at meter voltage); about 70 Ω nominal from the Songle datasheet, not measured |
| [ ] | Link plugged in at both ends: 12-pin 4 → Q1 base, 12-pin 5 → Q2 base, TP1 → J_CTRL pin 2, TP3 → J_CTRL pin 1 | Ω / beep | ~1 kΩ, ~1 kΩ, ~0 Ω, ~0 Ω. Unplug the link again |
| [ ] | 12-pin 6 (valve A) → Q3 gate | Ω | ~100 Ω (R7) |
| [ ] | 12-pin 7 (valve B) → Q4 gate | Ω | ~100 Ω (R10) |
| [ ] | 12-pin 8 (fan) → Q5 gate | Ω | ~100 Ω (R13) |
| [ ] | Q3, Q4, Q5 gate → GND, each | Ω | ~10 kΩ (R8, R11, R14) |
| [ ] | Q3 drain → J_LOADS pin 2 (SW_VA) | beep | ~0 Ω |
| [ ] | Q4 drain → J_LOADS pin 4 (SW_VB) | beep | ~0 Ω |
| [ ] | Q5 drain → J_LOADS pin 6 (SW_FAN) | beep | ~0 Ω |
| [ ] | J_LOADS pins 1, 3, 5 (24 V +) → TP4 | beep | ~0 Ω |
| [ ] | TP5, TP6, TP7, TP8, TP9 → 12-pin 4, 5, 6, 7, 8 in that order | beep | ~0 Ω |

### Item 6: Power path

**Slider and diodes first, with the 24 V supply still off.** Diode mode,
red probe on the anode. The SS34 reads about 0.2 to 0.4 V forward in diode
mode (a meter's test current is small, so a typical reading is expected,
not specified); reversed, OL. The 5 V and 24 V buses have other parts in
parallel, so a reversed reading above a few hundred ohms is fine but a
beep is not.

| | From → To | Mode | Expect |
|---|---|---|---|
| [ ] | D11 forward: red on J_24V pin 1, black on TP4 (through F2, a PPTC, closed when cold) | diode | forward only, about 0.2 to 0.4 V; reversed OL |
| [ ] | D14 forward: red on TP3, black on SW1 pin 2 | diode | forward only, about 0.2 to 0.4 V; reversed OL |
| [ ] | SW1 slider each way: SW1 pin 2 (common) → pin 1, and pin 2 → pin 3 | beep | in one slider position pin 2 to pin 1 is closed and pin 2 to pin 3 is open; the other position swaps them. The position with 2 to 1 closed must be the one toward the ON legend on the silkscreen, and 2 to 3 closed the one toward OFF; if the legend disagrees with the meter, stop |
| [ ] | Slider OFF: 12-pin 3 → TP3 and → TP1 | Ω, top range | OL on both |
| [ ] | Slider ON: 12-pin 3 → SW1 pin 2 | beep | closed (pin 3 of SW1 is unconnected) |
| [ ] | J_RLY pin 1 → TP3; J_RLY pin 2 → TP1 | beep | closed (the 5 V and GND the link carries) |

Return the slider to OFF. **Then power up** (the ESP still out, SW-USB OFF,
DC supply with a current limit if you have one, 24 V on). DC volts, black
on TP1:

| | Probe | Expect | Source of the expectation |
|---|---|---|---|
| [ ] | TP4 | ≈ 23.6 V (the supply minus the SS34's forward drop) | derived, 24 V supply; not measured |
| [ ] | TP3 | 4.9 to 5.1 V | hardware.md "USB-pin drop budget": module worst case 4.87 V low end, 5.13 V high end; 4.87 to 4.9 V is inside the datasheet but fails here and the module is replaced |
| [ ] | TP2 | 0 V (no 3.3 V without the ESP) | derived |
| [ ] | 12-pin 3, SW-USB OFF | 0 V | the switch is open |
| [ ] | D12 and D13 | both lit (green) | item 7 |
| [ ] | The 5 V module is not hot after a minute | touch | only warm |

Then set **SW-USB ON** and measure 12-pin 3 against TP1: **TP3 minus the
SS34 drop at that current.** With the ESP out the only load is the meter,
so the drop is small: expect 12-pin 3 within 0.4 V of TP3 (more than 0.4 V
below TP3 is a fault). The hardware.md budget figure of 0.2 to 0.4 V below
TP3 is for the ESP in; read it in the bring-up steps. Set **SW-USB back OFF**, then turn the 24 V
off. The first reading with an ESP in the sockets belongs in
docs/hardware-bringup.md, not here.

### Item 7: LED table

Read these during item 6's power-up (24 V on, ESP out, SW-USB OFF), before turning the 24 V off. These are the lit-state expectations; the
driven states (an output on) belong to the bring-up steps with the ESP in,
and the LEDs there show only that the driver stage conducts.

| | LED | Net it watches | Colour | Lit means | Expect now (ESP out) |
|---|---|---|---|---|---|
| [ ] | D12 | +24V (R16 10 kΩ to GND) | green | 24 V present after F2 and D11 | lit |
| [ ] | D13 | +5V (R17 2.2 kΩ to GND) | green | 5 V module output present | lit |
| [ ] | D3 (mains board; read with the link plugged in, then unplug it) | COIL_A, Q1 collector | red | Heater A relay driven | dark |
| [ ] | D4 (mains board, as D3) | COIL_B, Q2 collector | red | Heater B relay driven | dark |
| [ ] | D8 | SW_VA, Q3 drain | yellow | Valve A driven | dark |
| [ ] | D9 | SW_VB, Q4 drain | yellow | Valve B driven | dark |
| [ ] | D10 | SW_FAN, Q5 drain | yellow | Fan driven | dark |

With the ESP out **none of the five output LEDs (D3, D4, D8, D9, D10) may
light**, D3 and D4 with the link plugged in and 5 V reaching the mains
board. Any of them lit means a gate or base is floating high or a
transistor is in backwards: power down and look at that stage. Neither
relay may click when the link is plugged in.

### Item 8: Mains isolation

Mains unplugged, 24 V off, ohmmeter on its top range (the highest
resistance range the meter has, or its MΩ range). With the link unplugged,
probe **J_CTRL pin 2 (GND) and pin 1 (5 V)** as the mains board's SELV
side; then plug the link in and repeat the J_MAINS row against **TP1 and
TP3** on the controller, so the cable is included. Every row is two
readings (to GND, to 5 V). **Expect OL on every one.** F1 in place or out
makes no difference to the result; do both for the F1 pads.

| | Mains-side point | → SELV GND and → SELV 5 V | Expect |
|---|---|---|---|
| [ ] | J_MAINS pin 1 (L in), 2 (N), 3 (HTR A), 4, 5 (HTR B), 6, 7 (PSU L), 8 | Ω, top range | OL |
| [ ] | F1 clip 1 (L_IN side) and F1 clip 2 (L_FUSED side) | Ω, top range | OL |
| [ ] | K1 pad 1, pad 3, pad 4 | Ω, top range | OL |
| [ ] | K2 pad 1, pad 3, pad 4 | Ω, top range | OL |

If every row reads OL, the boards are cleared for the mains-side work in
docs/hardware-bringup.md; the formal sign-off (earthing, creepage) is
`docs/inspection-checklist.md`. Record the reading of any row that is not
OL, with its two probe points, before changing anything.

## Socket map

Both rows counted from the USB end. **Bold** = wired on this board.

| # | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 12-pin | BAT | LDO EN | **USB** (5 V in) | **13** heater A | **12** heater B | **11** valve A | **10** valve B | **8** fan | 6 | 4 | SCL=2 | SDA=1 | | | | |
| 16-pin | RESET (EN/CHIP_PU) | **3V3** | NC | **GND** | **17** BLK | 18 | 14 | **9** RES | **7** DC | **5** CS | **36** SCK | **35** MOSI | **37** 1-wire | 33 | 34 | 3 |

Two different pins go by "EN", and neither is wired here. 16-pin #1
is the ESP's own reset (CHIP_PU; silkscreen RST, RESET on the back):
10 kΩ to 3.3 V, the RESET button and the USB auto-reset transistor.
12-pin #2 (silkscreen EN) enables the 3.3 V regulator, 100 kΩ to VIN;
pulled low, it turns the whole 3.3 V rail off. 16-pin #8 "RES" is the
display's reset on GPIO9, not the ESP's.

The numbers in the map are the ESP32-S2 board's GPIOs. The checks on this
page go by socket position and hold for the ESP32-C6 board too; its
numbers are in [hardware.md](hardware.md#fitting-an-esp32-c6-thing-plus).

## 1. Shorts

Beep mode. **Nothing here should beep.** The 100 µF caps may chirp while
they charge, then the reading climbs; a steady beep is a short.

- [ ] 24V+ and GND: open
- [ ] 5 V bus and GND: open
- [ ] 3V3 (16-pin #2) and GND (16-pin #4): open
- [ ] Neighbouring 12-pin positions 13 / 12 / 11 / 10 / 8 to each other: open
- [ ] BAT (12-pin #1) to anything: open
- [ ] 16-pin #15 and #16, 12-pin #9 and #10, each to GND, 3V3, the 5 V bus and its neighbours: open. Nothing is wired to these four; on an ESP32-C6 board they are UART0 TX, the BOOT strap, the RGB LED's data and a boot strap

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
| [ ] | GPIO37 (16-pin #13) → 3V3 (16-pin #2), the 5.1 kΩ pullup | Ω | 4.85–5.35 kΩ |
| [ ] | GPIO37 → each DS18B20 DQ screw terminal (×3) | beep | ~0 Ω |
| [ ] | Each probe's GND terminal → GND, VDD terminal → 3V3 (×3) | beep | ~0 Ω |

With the probes connected, DQ → 3V3 can start lower (around 3.4 kΩ) and
climb to 5.1 kΩ, and DQ → GND can read a steady 10–15 kΩ. That can be the
probes' protection diodes turned partly on by the meter, with the 3V3
decoupling capacitors charging. Unplug the probes: DQ → GND must then read
open or climb toward it. A steady reading with the probes out is leakage on
the board. Powered, DQ should idle near 3.3 V; around 2.2 V or lower means a
real path to ground.

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
| [ ] | 12-pin socket: every neighbouring pair, #1–2 through #11–12. Watch **USB–13** (#3–4, 5 V onto a 3.3 V pin) and **LDO EN–USB** (#2–3) | beep | no beep |
| [ ] | 16-pin socket: every neighbouring pair, #1–2 through #15–16. Watch **9–7** (RES–DC), **36–35** (SCK–MOSI) and **35–37** | beep | no beep |
| [ ] | Display 8-pin header: each neighbouring pair, 1–2 through 7–8 | beep | no beep |
| [ ] | JST harness header, on both boards: 1–2, 2–3, 3–4 | beep | no beep |
| [ ] | 9-position sensor block: each neighbouring pair. 3V3–DQ reads the pullup | Ω | ~5.1 kΩ, never 0 |
| [ ] | 24 V load blocks (valve A, valve B, fan): 24+ to SW on each | beep | no beep |
| [ ] | Every used GPIO socket position → GND, → 3V3, → 5 V | beep | no beep |
| [ ] | Each IRLZ44N: gate → source | Ω | ~10 kΩ, never 0 |
| [ ] | Each IRLZ44N: red on drain, black on source; reversed shows the body diode, which is normal | diode | OL; ~0.5 V reversed |
| [ ] | Each PN2222A: base → emitter | Ω | ~1 kΩ, never 0 |
| [ ] | **Mains isolation:** each relay COM, NO and NC pin, both F1 clips and every mains terminal → 5 V bus and → GND bus | Ω, top range | OL, every one |
| [ ] | Solder side of both boards under a magnifier: every pair of neighbouring pads, above all around the sockets and relay COM pins. Hairline whiskers and flux-filled gaps can pass a meter and short once warm | eyes | clean gaps |
