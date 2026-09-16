# Hardware

## Bill of materials

| Item | Part | Notes |
|---|---|---|
| MCU | SparkFun ESP32-S2 Thing Plus (WRL-17743) | Feather footprint, Qwiic, CP2102 |
| Humidity/temp | Sensirion SHT45 breakout (Qwiic/STEMMA QT) | In outlet air, after the valves |
| Pack/case temp | 3× DS18B20 (probe style) | Shared 1-wire bus, 4.7 kΩ pullup, 125 °C max |
| Display | 1.54" IPS 240×240, ST7789 | 4-wire SPI, no MISO needed |
| Heater relays | 2× Songle SRD-05VDC-SL-C | 5 V coil ~70 mA, 10 A / 250 VAC contacts |
| Relay drivers | 2× PN2222A (TO-92, E-B-C); do not substitute P2N2222A unless rotated 180° | 1 kΩ base (logic-board end), 10 kΩ base pulldown (relay board) |
| Valve/fan drivers | 3× IRLZ44N | 100 Ω gate, 10 kΩ gate pulldown |
| Flyback diodes | 5× 1N4007 (or Schottky) | Across every coil/fan, band (cathode) to + |
| Valves | 2× SMC VDW22QABXB | 24 VDC, 3 W, 2-port NC, brass |
| Fan | 24 V axial | On/off only |
| Supply | 24 V, 1.5 A (e.g. Mean Well LRS-35-24) | Whole system ~12 W; open-frame Class I: FG to PE, guard the mains terminals |
| Buck | MP1584 "mini" 24 V → 5 V module (22 × 17 mm, trimmer), or a fixed-5 V module | Feeds board USB pin (through the Schottky) and relay coils; set to 5.00–5.10 V |
| USB-pin Schottky | SS34 (SMD) or 1N5819 (axial) | Buck 5 V → J-USB → board USB pin |
| Heaters | 2× 120 VAC, 123 Ω (~117 W) | Existing packs; switched by relay contacts |
| Heater over-temp cutouts | 2× one-shot thermal fuse (TCO), Tf ≈ 140 °C (standard 141 °C part), ≥ 2 A / 250 VAC | In series with each heater's switched L lead, clamped to the pack; sizing in [Mains and earthing](#mains-and-earthing) |

Protoboard build (see [Protoboard layout](#protoboard-layout-proposal)), in
addition to the parts above:

| Item | Part | Notes |
|---|---|---|
| Logic board | Double-sided plated FR-4 protoboard, 7 × 9 cm | 2.54 mm grid |
| Relay board | Double-sided plated FR-4 protoboard, 5 × 7 cm | 2.54 mm grid |
| ESP sockets | 1× 16-pin and 1× 12-pin female header, 2.54 mm | ESP is socketed |
| Bulk capacitors | 2× 100 µF / 16 V electrolytic | 5 V on each board; mind polarity |
| J-USB | 2-pin header + shunt | Manual disconnect between buck and USB pin |
| Harness | JST-XH 4-way: B4B-XH-A header on each board, 2× XHP-4 housings, crimps, cable | Or an equivalent keyed 0.1" housing |
| Display cable | 8-pin male header + 8-way female-female cable ≤ 15 cm | |
| Resistors | 4.7 kΩ (1-wire pullup) plus the driver-stage resistors above | |
| Sensor terminals | 9-position 5.08 mm screw terminal block | DS18B20 ×3 |
| 24 V terminals | 4× 2-position 5.08 mm screw terminal block | 24 V in, valve A, valve B, fan |
| Mains terminals | 3× 2-position 5.08 mm **mains-rated** screw terminal block (UL 1059 300 V / 10 A or IEC 250 V class) | 120 VAC in, heater A, heater B |
| Mains fuse | T 3.15 A 5 × 20 mm fuse + panel/inline holder | In L at the inlet, ahead of PSU and heaters |
| Mounting | M3 nylon standoffs | Board corners |
| Wire | Tinned bus wire; insulated hookup wire; mains-rated wire for the relay board | |

Datasheets for these parts, with sources and revisions, are in
[datasheets/README.md](datasheets/README.md).

## Board pinout used

From SparkFun's Eagle schematic (J4 = 16-pin, J2 = 12-pin); pin-by-pin
tables and sources in [pinout-verification.md](pinout-verification.md).

16-pin header, in order: EN, 3V3, NC, GND, A0=17, A1=18, A2=14, A3=9, A4=7,
A5=5, SCK=36, COPI=35, CIPO=37, RX1=33, TX1=34, 3.
Used: 3V3, GND, 17 (backlight PWM), 14 (display RST), 9 (display DC),
5 (display CS), 36 (SCK), 35 (MOSI), 37 (1-wire bus).

12-pin header, in order: BAT, EN, USB, 13, 12, 11, 10, 8, 6, 4, SCL=2, SDA=1.
Used: USB (5 V in), 13 (heater A), 12 (heater B), 11 (valve A), 10 (valve B),
6 (fan). Note the "9" and "5" Feather positions are GPIO8 and GPIO4 here.
Qwiic connector: SDA=1, SCL=2, 3.3 V, GND.

Both header orders above run from the USB end. Component side up with the
USB-C at the left, the 12-pin row is on top and the 16-pin row at the bottom.

On-board blue LED: GPIO13 via 1 kΩ, active high (lights with heater A).
Avoid: GPIO0 (boot button), GPIO19/20 (USB D-/D+), 45/46 (strapping, back
pads only). GPIO18 has an optional pullup (solder jumper, open by default).
GPIO33–37 are free on this quad-SPI module.

## Driver stages

Relay channel (×2):

```
  GPIO ──[1 kΩ]──┬── base   PN2222A
                 │          emitter ── GND
              [10 kΩ]       collector ── relay coil ── +5 V
                 │                       (1N4007 across coil, band (cathode) to +5 V)
                GND
  relay NO contact switches L to the 120 VAC heater
```

MOSFET channel (×3, valves + fan):

```
  GPIO ──[100 Ω]──┬── gate   IRLZ44N
                  │          source ── GND
               [10 kΩ]       drain ── load ── +24 V
                  │                   (1N4007 across load, band (cathode) to +24 V)
                 GND
```

At 3.3 V gate drive the IRLZ44N is only partly enhanced (~40–50 mΩ). Fine for
the 125 mA valves and a small fan; not intended for heavy loads.

Package pinouts: PN2222A TO-92, flat face toward you, legs down: E B C
(P2N2222A, also sold as a TO-92 "2N2222", is C B E; check the datasheet of
the part you have). Bulk TO-92 lead pitch is 1.27 mm; the formed-lead
PN2222ATA/ATF and P2N2222ARL1G are 2.54 mm. IRLZ44N TO-220, marking face
toward you, legs down: G D S. Tab is tied to drain.

## Breadboard layout (bench build)

![Breadboard layout](breadboard.svg)

The ESP board in this picture is drawn from its solder side; component side
up with USB-C at the left, the 12-pin row is on top.

- Top rails: 3.3 V and GND from the board's 3V3/GND pins.
- Bottom rails: 5 V and GND from the buck converter. 24 V supply negative
  ties to the same ground.
- Board USB pin ← bottom 5 V rail. That pin is the USB-C connector's VBUS
  net, with no diode or fuse before it, so pull the USB-pin wire before
  plugging in a USB-C cable, or flash over the air. The buck can't be
  back-fed (the MP1584 is non-synchronous and cannot sink current; a higher
  host VBUS just stops it switching), but a buck set above the host's VBUS
  sources current into the computer's port, up to the MP1584's 4–4.7 A
  current limit. Only pulling the wire (or J-USB on the protoboard) prevents
  that; the protoboard's series Schottky blocks the other direction only
  (see J-USB below).
- Display: GND/VCC to top rails; SCL→36, SDA→35, RES→14, DC→9, CS→5, BLK→17.
- DS18B20 ×3: all GND to top GND, all VDD to top 3.3 V, all DQ tied together
  → GPIO37 with one 4.7 kΩ to 3.3 V. Three-wire hookup; do not use parasitic
  power.
- SHT45: Qwiic cable to the board's connector; nothing on the breadboard.
- Five driver columns below the board, one per output. Relays and the 24 V
  loads live off-board; only the coil/load negative lead returns to the
  transistor collector/drain.
- Nothing above 24 V on the breadboard. Heater contacts and mains wiring go
  on the relay module / a terminal block in the enclosure.

## Protoboard layout (proposal)

![Protoboard layout](board-layout.svg)

Two boards, split at the mains boundary rather than by voltage: a 90 × 70 mm
logic + 24 V board (ESP socketed, buck, three MOSFET channels, 1-wire block,
display header) and a 70 × 50 mm relay board (relays, PN2222A stages,
120 VAC terminals) joined by a 4-wire logic-level harness. Not yet built.
The drawing is a top view of the component side with the wiring on the
underside, and prints 1:1 (check its 10 mm bar).

Geometry sources, all in [datasheets/](datasheets/README.md):

- ESP32-S2 Thing Plus, verified from SparkFun's Eagle `.brd`/`.sch` and
  dimension drawing: PCB 64.77 × 22.86 mm, header rows 1.27 mm in from each
  long edge and 20.32 mm apart, both ending 12.70 mm before the antenna end;
  16-pin pin 1 (EN) 13.97 mm and 12-pin pin 1 (BAT) 24.13 mm from the USB
  end; Qwiic at the USB end on the 12-pin edge; mounting holes only at the
  USB end; the WROOM antenna occupies the last 6.3 mm.
- Placement used: the ESP stands along the left edge, antenna end at the top
  edge (nothing under or beside it), USB-C at the bottom edge with its face
  3.2 mm inside the board (the plug comes in below the elevated board), and
  the Qwiic cable exits to the left. 12-pin socket at x = 6.01 mm, 16-pin
  socket at x = 26.33 mm; all hole centres at 3.47 + k·2.54 mm.
- Songle SRD-05VDC-SL-C (datasheet bottom view, mm; the pattern is
  symmetric, so the top view is the same): COM (0, 0), coil (2.0, ±6.0),
  NO/NC (14.2, ±6.0), 1.3 mm holes, body 19.2 × 15.5 × 15.8 mm. Nearest grid
  fit is rows ±6.35, columns 12.7 apart, COM 2.54 outboard (≈0.35–0.5 mm
  splay per pin). The drawing uses the real positions: the coil and NO/NC
  pins sit 0.35 mm inside hole columns 12.7 mm apart and COM falls on the
  centreline between two columns, where its hole is drilled. These five pins
  are the only pads off the grid.
- The MP1584 mini buck footprint (22 × 17 mm and its pad positions) is
  **unverified**; modules vary by vendor.

### Build steps

1. Before fitting J-USB or the ESP: power the 24 V input, set the MP1584
   module's trimmer to 5.00–5.10 V measured at the buck's OUT+ pad, lock
   the pot, power down. (Measure at OUT+ rather than the socket's USB
   position: that position is downstream of the Schottky and J-USB, so it
   reads open with J-USB out and about 0.3–0.4 V low with it in.) A fixed-5 V
   module avoids the trimmer.
2. Fit the parts; check every net in the tables below with a meter before
   the ESP goes into its sockets.
3. Relay board: identify NC on each relay before wiring. With the coil
   unpowered, NC has continuity to COM; the pin pattern gives no other way
   to tell NO from NC. Wire "L sw" to NO. NC is live whenever the heater is
   off; leave it unconnected. Ream the COM, NO and NC holes to ≥ 1.2 mm
   (those pins are 1.0–1.1 mm flat blades; the coil pins are 0.6 mm round).
4. Before wiring real heaters: make the four heater/valve switches
   `internal: true` with read-only mirrors (the open item in CLAUDE.md), and
   fit a thermal fuse in each heater's switched L lead at the pack (sizing
   under [Mains and earthing](#mains-and-earthing)).

### J-USB and the Schottky

The ESP's USB pin is the USB-C VBUS net with no diode or fuse before it. It
feeds D2 (BAT20J Schottky) → AP2112 3.3 V LDO (600 mA, 6.5 V absolute
maximum) and the MCP73831 charger (7 V absolute maximum). The MP1584 is a
non-synchronous buck and cannot sink current, so a higher host VBUS simply
stops it switching; the real hazard with J-USB fitted and a USB cable
plugged in is the buck, if it is above the host's VBUS, sourcing current
into the computer's port, up to the MP1584's 4–4.7 A current limit.

The layout puts a series Schottky (SS34 or 1N5819) from buck 5 V to J-USB,
but it does **not** block that direction: buck → USB pin is the diode's
forward direction, which is how the board is powered. What the Schottky does
is stop a host from back-feeding the buck's output node, the 5 V bus and the
relay coils, for a 0.3–0.4 V drop; with the buck at 5.0 V the AP2112 still
has ≥ 0.39 V dropout margin at the 430 mA peak, using the worst-case drops
from the BAT20J and AP2112 datasheets.

So J-USB, not the diode, is what keeps the buck off a computer's USB port:

- pull J-USB before plugging in a USB-C cable, every time;
- the buck stays at or below 5.1 V;
- a USB-C host may also refuse to attach while VBUS is pre-biased, which is
  another reason J-USB comes out first.

Making the USB port safe with J-USB fitted would need a real power path (an
ideal-diode/load-switch ORing the two sources), not a series diode. That is
not in this layout.

### Harness and off-board wiring

- Harness: JST-XH 4-way, a B4B-XH-A on each board with XHP-4 housings and a
  1:1 cable. Pin 1 = 5 V, 2 = GND, 3 = GPIO13 through 1 kΩ (heater A),
  4 = GPIO12 through 1 kΩ (heater B). The 1 kΩ base resistors sit at the
  logic-board end; the 10 kΩ pulldowns stay on the relay board. The relay
  board carries no 24 V. XH pitch is 2.50 mm, which fits 0.1" holes over
  four pins.
- Display: 8-pin 1:1 cable to the panel on the enclosure front; keep it
  under 15 cm (ESPHome's ili9xxx runs 40 MHz SPI by default; set
  `data_rate: 20MHz` in `display-st7789.yaml` if the image tears). The
  header order GND 3V3 SCL SDA RES DC CS BLK follows LCDWIKI/QDtech
  MSP1541-style modules; Waveshare's 1.54" module is VCC GND DIN CLK CS DC
  RST BL, so a straight cable would swap its power and ground. BLK must
  drive an on-module transistor (check BLK → VCC ≈ 10 kΩ unpowered); a bare
  LED anode would overload GPIO17.
- SHT45 on the ESP's Qwiic connector. 24 V PSU → 24 V IN. Valves and fan:
  + to 24+, − to SW (the drain). DS18B20s → the 9-position block, one
  3V3/DQ/GND triple per probe.

### Net list — logic + 24 V board

| Net | From | To |
|---|---|---|
| GND | 24 V IN 0V | Buck IN− / OUT− (one net on the module), 100 µF −, ESP GND (16-pin), display GND, harness pin 2, GND bus → 10 kΩ gate pulldowns ×3 and IRLZ44N sources ×3, DS18B20 GND ×3 |
| 3V3 | ESP 3V3 (16-pin) | 3V3 bus → display 3V3, 4.7 kΩ top, DS18B20 3V3 ×3 |
| 5 V | Buck OUT+ | 100 µF +, Schottky anode, harness pin 1 |
| VBUS | Schottky cathode | J-USB pin 2; J-USB pin 1 → ESP USB (12-pin) |
| 24V+ | 24 V IN 24+ | 24V+ bus → load blocks 24+ ×3, 1N4007 cathodes ×3; insulated feed → buck IN+ |
| GPIO13 | ESP 13 (12-pin) | 1 kΩ → harness pin 3 |
| GPIO12 | ESP 12 (12-pin) | 1 kΩ → harness pin 4 |
| GPIO11 | ESP 11 (12-pin) | 100 Ω, valve A channel |
| GPIO10 | ESP 10 (12-pin) | 100 Ω, valve B channel |
| GPIO6 | ESP 6 (12-pin) | 100 Ω, fan channel |
| GPIO36 | ESP 36 (16-pin) | Display SCL |
| GPIO35 | ESP 35 (16-pin) | Display SDA |
| GPIO14 | ESP 14 (16-pin) | Display RES |
| GPIO9 | ESP 9 (16-pin) | Display DC |
| GPIO5 | ESP 5 (16-pin) | Display CS |
| GPIO17 | ESP 17 (16-pin) | Display BLK |
| GPIO37 / DQ | ESP 37 (16-pin) | 4.7 kΩ bottom, DS18B20 DQ ×3 |
| Gate A / B / C | 100 Ω far end | IRLZ44N G, 10 kΩ top (each channel) |
| Drain A / B / C (SW) | IRLZ44N D | 1N4007 anode, load block SW (load −) |

### Net list — relay board

| Net | From | To |
|---|---|---|
| 5 V | Harness pin 1 | 5 V bus → 100 µF +, coil pin (5 V side) ×2, 1N4007 cathodes ×2 |
| GND | Harness pin 2 | GND bus → 100 µF −, 10 kΩ bottom ×2, PN2222A emitters ×2 |
| Base A | Harness pin 3 (GPIO13 via 1 kΩ) | PN2222A A base, 10 kΩ top |
| Base B | Harness pin 4 (GPIO12 via 1 kΩ) | PN2222A B base, 10 kΩ top |
| Coil A − / coil B − | PN2222A collector | Relay coil pin (other side), 1N4007 anode |
| L | 120 VAC IN L | Relay A COM, relay B COM |
| N | 120 VAC IN N | Heater A N, heater B N (passes through, never switched) |
| L sw A | Relay A NO | Heater A "L sw" → thermal fuse at pack A → heater A |
| L sw B | Relay B NO | Heater B "L sw" → thermal fuse at pack B → heater B |
| NC A / NC B | — | Unconnected (live when the heater is off) |
| PE | Not on the protoboard | Inlet PE → PSU FG, chassis, enclosure, heater sheaths at a star point; 0 V bonded to PE at the PSU |

### Mains and earthing

- The Mean Well LRS-35-24 is an open-frame Class I supply: its FG terminal
  goes to protective earth and its mains terminals must be guarded.
- Chassis, enclosure and heater sheaths bond to PE at a star point that is
  **not** on the protoboard.
- 0 V bonds to PE at one point, at the PSU, because the relay's 1500 VAC
  coil–contact rating is a basic-insulation barrier only.
- Fuse T 3.15 A in L at the inlet, ahead of the PSU and heaters.
- Each relay switches L only; N passes straight through.
- Each heater carries its own one-shot thermal fuse (TCO) in series, in the
  switched L lead between the relay board's "L sw" terminal and the heater,
  clamped to the pack body like the DS18B20 so it senses the pack and not
  the air. This is the only protection against a welded relay contact: the
  firmware cannot clear that failure, and the standby pack's heater would
  otherwise stay energised.
- Sizing, from the numbers the firmware already uses: a pack runs up to
  `regen_temp` (default 90 °C) and the firmware latches a fault above
  `overtemp` (default 120 °C — see [control-logic.md](control-logic.md)).
  The fuse therefore has to hold at 120 °C without drifting and open not far
  above it, so Tf ≈ 140 °C (the standard 141 °C part) with the datasheet's
  maximum continuous holding temperature at or above 120 °C; on most TCOs
  that holding figure is Tf minus 15–25 °C, so check the part in hand rather
  than assuming. Each heater draws 117 W / 120 VAC ≈ 1 A, so a 2 A (or the
  common 10 A) 250 VAC rating is ample.
- Crimp or clamp the fuse leads; soldering near the body can trip it.
  Sleeve the leads in high-temperature insulation. A tripped TCO is not
  resettable and means opening the pack, so a resettable bimetal thermostat
  of the same temperature class is the alternative if nuisance trips matter
  more than the one-shot guarantee.
- Unverified: the maximum temperature the pack, its desiccant and the probe
  and valve leads can take. Tf has to sit below that as well as above the
  firmware limit. Record the fuses actually fitted, with their Tf, holding
  temperature and current rating, here.
- COM is mains and sits at the coil end of the relay: 6.3 mm centre to
  centre from each coil pin, which leaves about 4 mm pad edge to pad edge.
  The drawing's mains boundary goes around COM, and the PN2222A/1N4007 stage
  sits at least three hole rows from COM, NO and NC.
- Alternative, not chosen: take the contacts off the protoboard, with
  screw-terminal relay sockets or an off-the-shelf 2-channel 5 V relay module
  fed from 3V3 with its JD-VCC jumper removed.

### Open items (for review)

- Creepage: two empty rows are 5.6 mm pad edge to pad edge, and undrilled
  plated pads between mains and logic reduce it further; a cleared band or
  slot along the boundary, or contacts off the protoboard, is needed.
- The 24 V input has no reverse-polarity protection, fuse or bulk input
  capacitor.
- The thermal fuses above are specified but not yet fitted or verified:
  confirm the pack's safe maximum temperature (Tf must sit below it), the
  fuse's holding temperature at the 120 °C firmware limit, and what the
  original Azco board/packs provided.
- Stock DS18B20 probe leads are rated under 100 °C and the SMC VDW22 valve
  is rated 50 °C, both on a 90 °C pack; verify or change parts.
- The buck module footprint is unverified; measure the module before
  drilling.

## Mechanical notes

- SHT45 must sit downstream of both valves so it sees the air actually sent
  to the ozone generator.
- Pack DS18B20s should be clamped to the pack body (not the heater surface,
  not the airspace). Verify surface stays under 125 °C.
- The packs are open to atmosphere: a regenerated pack slowly reabsorbs
  ambient moisture while idle, so don't leave it READY for long. Tune `arm_rh`
  so heating finishes shortly before the swap is needed.
- Ozone-generator feed target is dew point ≤ −40 °C (≈0.4 % RH at 25 °C).
  Cheap RH sensors can't resolve that; the controller only detects the
  humidity *rise* when a pack saturates.
