# hardware/dryer_board/parts.py
"""What a part is, the catalogue the boards draw on, and the helpers that make the common
ones. The parts themselves, and the nets they join, are listed per board in controller.py
and mains.py. Values and reasoning: docs/hardware.md and the spec."""
from dataclasses import dataclass
from typing import Dict, List

NC = "NC"

@dataclass(frozen=True)
class Part:
    ref: str
    value: str
    symbol: str          # "Library:Name" in KiCad's stock symbol libraries
    footprint: str       # "Library:Name" in KiCad's stock footprint libraries (or dryer:Name, local)
    pins: Dict[str, str] # pad/pin number -> net name, or NC
    lcsc: str = ""       # LCSC / JLCPCB part number; "" only for hand-fitted parts and bare pads
    hand_fit: bool = False
    description: str = ""

# Catalogue entries (LCSC number, maker and part number, JLCPCB class), looked up 2026-10-14;
# every one offers JLCPCB assembly. Part pages: https://jlcpcb.com/partdetail/<C-number>
RESISTORS = {  # 0805, 1 %, 125 mW thick film
    "100": ("C17408", "UNI-ROYAL 0805W8F1000T5E"), "1k": ("C17513", "UNI-ROYAL 0805W8F1001T5E"),
    "2.2k": ("C17520", "UNI-ROYAL 0805W8F2201T5E"), "5.1k": ("C27834", "UNI-ROYAL 0805W8F5101T5E"),
    "10k": ("C17414", "UNI-ROYAL 0805W8F1002T5E"),
}
CAPACITORS = {  # 0805 MLCC; a higher voltage rating than the value names is noted
    "10u 50V": ("C440198", "Murata GRM21BR61H106KE43L, 10 uF 50 V X5R"),
    "22u 10V": ("C45783", "Samsung CL21A226MAQNNNE, 22 uF 25 V X5R (25 V part)"),
    "100n": ("C49678", "YAGEO CC0805KRX7R9BB104, 100 nF 50 V X7R"),
    "10u 10V": ("C15850", "Samsung CL21A106KAYNNNE, 10 uF 25 V X5R (25 V part)"),
}
LEDS = {  # 0805; forward voltage from the maker's table
    "red": ("C84256", "NationStar NCD0805R1, Vf 1.5-2.6 V at 20 mA"),
    "yellow": ("C2296", "KENTO KT-0805Y, Vf 1.8-2.4 V at 10 mA"),
    "green": ("C2297", "KENTO KT-0805G, Vf 2.6-3.1 V at 5 mA"),
}

def desc(*parts):
    return "; ".join(p for p in parts if p)

def r(ref, value, a, b, d=""):
    lcsc, mpn = RESISTORS[value]
    return Part(ref, value, "Device:R", "Resistor_SMD:R_0805_2012Metric", {"1": a, "2": b}, lcsc, False,
                desc(d, mpn, "JLCPCB basic"))

def c(ref, value, a, b, d=""):
    lcsc, mpn = CAPACITORS[value]
    return Part(ref, value, "Device:C", "Capacitor_SMD:C_0805_2012Metric", {"1": a, "2": b}, lcsc, False,
                desc(d, mpn, "JLCPCB basic"))

def led(ref, colour, k, a):
    lcsc, mpn = LEDS[colour]
    return Part(ref, "LED " + colour, "Device:LED", "LED_SMD:LED_0805_2012Metric", {"1": k, "2": a}, lcsc, False,
                desc(colour + " 0805", mpn, "JLCPCB basic"))

def s1m(ref, k, a):
    return Part(ref, "S1M", "Device:D", "Diode_SMD:D_SMA", {"1": k, "2": a}, "C95872", False,
                "1 A 1000 V flyback, SMA; MDD M7 (the S1M rating: 1 A, 1000 V, SMA); JLCPCB basic")

def npn(ref, base, emitter, collector):
    return Part(ref, "MMBT2222A", "Transistor_BJT:MMBT2222A", "Package_TO_SOT_SMD:SOT-23",
                {"1": base, "2": emitter, "3": collector}, "C8512", False,
                "relay driver; CJ MMBT2222A 1P (1 B, 2 E, 3 C); JLCPCB basic")

def nfet(ref, gate, source, drain):
    return Part(ref, "CJ2310", "Transistor_FET:Q_NMOS_GSD", "Package_TO_SOT_SMD:SOT-23",
                {"1": gate, "2": source, "3": drain}, "C75882", False,
                "60 V logic-level N-MOSFET, SOT-23; CJ CJ2310 (1 G, 2 S, 3 D; Vgs(th) 2 V max, "
                "Rds(on) 125 mOhm max at 4.5 V); JLCPCB extended")

def hole(ref):
    """M4 clearance hole (4.3 mm, KiCad's MountingHole_4.3mm_M4): the M4 hardware on hand."""
    return Part(ref, "M4", "Mechanical:MountingHole", "MountingHole:MountingHole_4.3mm_M4", {})

def flag(ref, net):
    return Part(ref, "PWR_FLAG", "power:PWR_FLAG", "", {"1": net})

def tp(ref, name, net):
    return Part(ref, name, "Connector:TestPoint", "TestPoint:TestPoint_Pad_D1.5mm", {"1": net})

# The board-to-board link: JST XH 4-way, keyed and latched, the protoboard harness's connector
# and pin order (docs/hardware.md "Harness and off-board wiring"). 2.50 mm pitch, so no other
# plug on either board fits it and it fits no other header.
LINK_PINS = {"1": "+5V", "2": "GND", "3": "RLY_A", "4": "RLY_B"}
LINK_FOOTPRINT = "Connector_JST:JST_XH_B4B-XH-A_1x04_P2.50mm_Vertical"
LINK_LCSC = "C144395"   # JST B4B-XH-A(LF)(SN), JLCPCB extended; docs/datasheets/connectors/jst-xh.pdf
LINK_DESC = "5V GND HTR-A HTR-B; JST B4B-XH-A(LF)(SN), 2.5 mm, keyed; mates XHP-4 housing; JLCPCB extended"

def link(ref, value):
    return Part(ref, value, "Connector_Generic:Conn_01x04", LINK_FOOTPRINT, dict(LINK_PINS), LINK_LCSC,
                description=LINK_DESC)

def by_ref(parts, ref):
    for p in parts:
        if p.ref == ref:
            return p
    raise KeyError(ref)

def nets(parts):
    out = {}
    for p in parts:
        for pad, net in sorted(p.pins.items()):
            if net != NC:
                out.setdefault(net, []).append((p.ref, pad))
    return out

def board_parts(parts):
    """Parts that exist on the PCB (everything with a footprint)."""
    return [p for p in parts if p.footprint]

def check_nets(parts):
    """Every net joins at least two pins. Returns a list of violations."""
    return ["net %s has one connection: %s" % (net, pads) for net, pads in nets(parts).items() if len(pads) < 2]
