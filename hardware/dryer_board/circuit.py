# hardware/dryer_board/circuit.py
"""The circuit: one table of parts, their pins and the nets they join. Everything
(schematic, board, BOM, position file) derives from this file. Values and reasoning:
docs/hardware.md and the spec."""
from dataclasses import dataclass, field
from typing import Dict, List, Tuple
from . import pinmap

REVISION = "A"
PROJECT = "dryer-controller"
TITLE = "ESP32 desiccant dryer controller"
NC = "NC"

MAINS_NETS = ["L_IN", "L_FUSED", "L_SW_A", "L_SW_B", "N"]

# name -> (track width mm, clearance mm, via diameter mm, via drill mm, net name patterns)
NETCLASSES = {
    "Default": (0.3, 0.2, 0.6, 0.3, []),
    "MAINS":   (1.5, 1.0, 1.2, 0.6, MAINS_NETS),
    "P24":     (0.8, 0.2, 0.8, 0.4, ["+24V*", "SW_VA", "SW_VB", "SW_FAN"]),
    "P5":      (0.8, 0.2, 0.8, 0.4, ["+5V", "V5_D", "VBUS", "COIL_A", "COIL_B"]),
}

@dataclass(frozen=True)
class Part:
    ref: str
    value: str
    symbol: str          # "Library:Name" in KiCad's stock symbol libraries
    footprint: str       # "Library:Name" in KiCad's stock footprint libraries (or dryer:Name, local)
    pins: Dict[str, str] # pad/pin number -> net name, or NC
    lcsc: str = ""       # LCSC part number, filled by Task 15
    hand_fit: bool = False
    description: str = ""

def _r(ref, value, a, b, lcsc="", desc=""):
    return Part(ref, value, "Device:R", "Resistor_SMD:R_0805_2012Metric", {"1": a, "2": b}, lcsc, False, desc)

def _c(ref, value, a, b, lcsc="", desc=""):
    return Part(ref, value, "Device:C", "Capacitor_SMD:C_0805_2012Metric", {"1": a, "2": b}, lcsc, False, desc)

def _led(ref, colour, k, a, lcsc=""):
    return Part(ref, "LED " + colour, "Device:LED", "LED_SMD:LED_0805_2012Metric", {"1": k, "2": a}, lcsc, False, colour + " 0805")

def _s1m(ref, k, a, lcsc=""):
    return Part(ref, "S1M", "Device:D", "Diode_SMD:D_SMA", {"1": k, "2": a}, lcsc, False, "1 A 1000 V flyback, SMA")

def _npn(ref, base, emitter, collector, lcsc=""):
    return Part(ref, "MMBT2222A", "Transistor_BJT:MMBT2222A", "Package_TO_SOT_SMD:SOT-23",
                {"1": base, "2": emitter, "3": collector}, lcsc, False, "relay driver")

def _nfet(ref, gate, source, drain, lcsc=""):
    return Part(ref, "SI2308", "Transistor_FET:Q_NMOS_GSD", "Package_TO_SOT_SMD:SOT-23",
                {"1": gate, "2": source, "3": drain}, lcsc, False, "60 V logic-level N-MOSFET, SOT-23")

def _socket_pins(header):
    """Net for every position of the 16- or 12-pin socket from pinmap."""
    net_for = {"usb_5v": "VBUS", "heater_a": "HTR_A", "heater_b": "HTR_B", "valve_a": "VLV_A",
               "valve_b": "VLV_B", "fan": "FAN", "3v3": "+3V3", "gnd": "GND", "lcd_bl": "LCD_BL",
               "lcd_rst": "LCD_RST", "lcd_dc": "LCD_DC", "lcd_cs": "LCD_CS", "spi_clk": "SPI_CLK",
               "spi_mosi": "SPI_MOSI", "onewire": "OW_DQ"}
    pins = {str(i): NC for i in range(1, header + 1)}
    for fn, (hdr, pos) in pinmap.FUNCTIONS.items():
        if hdr == header and fn in net_for:
            pins[str(pos)] = net_for[fn]
    return pins

PARTS: List[Part] = [
    # ESP sockets (female headers). Rotated 180 on the board so pin 1 is at the USB end.
    Part("J_ESP16", "Thing Plus 16-pin", "Connector_Generic:Conn_01x16",
         "Connector_PinSocket_2.54mm:PinSocket_1x16_P2.54mm_Vertical", _socket_pins(16), description="ESP socket, 16-pin row"),
    Part("J_ESP12", "Thing Plus 12-pin", "Connector_Generic:Conn_01x12",
         "Connector_PinSocket_2.54mm:PinSocket_1x12_P2.54mm_Vertical", _socket_pins(12), description="ESP socket, 12-pin row"),

    # 24 V input: plug -> PPTC -> Schottky -> bulk -> LED
    Part("J_24V", "24 V in", "Connector_Generic:Conn_01x02",
         "Connector_Phoenix_MSTB:PhoenixContact_MSTBVA_2,5_2-G-5,08_1x02_P5.08mm_Vertical", {"1": "+24V_RAW", "2": "GND"},
         description="24 V supply, 2-pin 5.08 mm pluggable header"),
    Part("F2", "PPTC 1.1 A 30 V", "Device:Polyfuse", "Fuse:Fuse_1812_4532Metric", {"1": "+24V_RAW", "2": "+24V_F"},
         description="resettable fuse on the 24 V input (F-03, G-11)"),
    Part("D11", "SS34", "Device:D_Schottky", "Diode_SMD:D_SMA", {"1": "+24V", "2": "+24V_F"},
         description="reverse-polarity series Schottky"),
    Part("C1", "100u 50V", "Device:C_Polarized", "Capacitor_SMD:CP_Elec_8x10.5", {"1": "+24V", "2": "GND"},
         description="24 V bulk"),
    _r("R16", "10k", "+24V", "LED_24V_R"),
    _led("D12", "green", "GND", "LED_24V_R"),

    # 5 V: fixed module in the TSR-1 / 78xx footprint
    Part("U1", "K7805-1000R3", "Converter_DCDC:TSR_1-2450", "Converter_DCDC:Converter_DCDC_TRACO_TSR-1_THT",
         {"1": "+24V", "2": "GND", "3": "+5V"}, description="fixed 5 V 1 A switching module, 78xx pinout"),
    _c("C2", "10u 50V", "+24V", "GND", desc="module input, per datasheet"),
    _c("C3", "22u 10V", "+5V", "GND", desc="module output, per datasheet"),
    Part("C4", "100u 16V", "Device:C_Polarized", "Capacitor_SMD:CP_Elec_6.3x7.7", {"1": "+5V", "2": "GND"},
         description="5 V bulk for the relay coils"),
    _r("R17", "2.2k", "+5V", "LED_5V_R"),
    _led("D13", "green", "GND", "LED_5V_R"),

    # USB pin feed: 5 V -> Schottky -> slide switch -> ESP 12-pin 3
    Part("D14", "SS34", "Device:D_Schottky", "Diode_SMD:D_SMA", {"1": "V5_D", "2": "+5V"},
         description="blocks a USB host back-feeding the 5 V bus"),
    Part("SW1", "SW-USB", "Switch:SW_SPDT", "Button_Switch_THT:SW_Slide_SPDT_Straight_CK_OS102011MS2Q",
         {"1": "VBUS", "2": "V5_D", "3": NC}, description="OFF before any USB-C cable; footprint pinned in Task 15"),

    # Relay stage A (heater A): 1k series, 1k pulldown, MMBT2222A, S1M flyback, LED, Songle relay
    _r("R1", "1k", "HTR_A", "BASE_A"), _r("R2", "1k", "BASE_A", "GND"),
    _npn("Q1", "BASE_A", "GND", "COIL_A"),
    _s1m("D1", "+5V", "COIL_A"),
    _r("R3", "2.2k", "+5V", "LED_HA_R"), _led("D3", "red", "COIL_A", "LED_HA_R"),
    Part("K1", "SRD-05VDC-SL-C", "Relay:SANYOU_SRD_Form_C", "Relay_THT:Relay_SPDT_SANYOU_SRD_Series_Form_C",
         {"1": "L_FUSED", "2": "+5V", "5": "COIL_A", "3": "L_SW_A", "4": NC}, "C35449", False, "heater A relay"),
    # Relay stage B (heater B)
    _r("R4", "1k", "HTR_B", "BASE_B"), _r("R5", "1k", "BASE_B", "GND"),
    _npn("Q2", "BASE_B", "GND", "COIL_B"),
    _s1m("D2", "+5V", "COIL_B"),
    _r("R6", "2.2k", "+5V", "LED_HB_R"), _led("D4", "red", "COIL_B", "LED_HB_R"),
    Part("K2", "SRD-05VDC-SL-C", "Relay:SANYOU_SRD_Form_C", "Relay_THT:Relay_SPDT_SANYOU_SRD_Series_Form_C",
         {"1": "L_FUSED", "2": "+5V", "5": "COIL_B", "3": "L_SW_B", "4": NC}, "C35449", False, "heater B relay"),

    # MOSFET stages: valve A, valve B, fan (100 R gate, 10k pulldown, S1M flyback, LED from 24 V)
    _r("R7", "100", "VLV_A", "GATE_A"), _r("R8", "10k", "GATE_A", "GND"),
    _nfet("Q3", "GATE_A", "GND", "SW_VA"), _s1m("D5", "+24V", "SW_VA"),
    _r("R9", "10k", "+24V", "LED_VA_R"), _led("D8", "yellow", "SW_VA", "LED_VA_R"),
    _r("R10", "100", "VLV_B", "GATE_B"), _r("R11", "10k", "GATE_B", "GND"),
    _nfet("Q4", "GATE_B", "GND", "SW_VB"), _s1m("D6", "+24V", "SW_VB"),
    _r("R12", "10k", "+24V", "LED_VB_R"), _led("D9", "yellow", "SW_VB", "LED_VB_R"),
    _r("R13", "100", "FAN", "GATE_C"), _r("R14", "10k", "GATE_C", "GND"),
    _nfet("Q5", "GATE_C", "GND", "SW_FAN"), _s1m("D7", "+24V", "SW_FAN"),
    _r("R15", "10k", "+24V", "LED_FAN_R"), _led("D10", "yellow", "SW_FAN", "LED_FAN_R"),

    # Mains: fuse and the single 8-pin plug
    Part("F1", "T 3.15 A 5x20", "Device:Fuse", "Fuse:Fuseholder_Clip-5x20mm_Littelfuse_111_Inline_P20.00x5.00mm_D1.05mm_Horizontal",
         {"1": "L_IN", "2": "L_FUSED"}, description="covered holder chosen in Task 15; clips are the stand-in footprint"),
    Part("J_MAINS", "120 VAC", "Connector_Generic:Conn_01x08",
         "Connector_Phoenix_MSTB:PhoenixContact_MSTBA_2,5_8-G-5,08_1x08_P5.08mm_Horizontal",
         {"1": "L_IN", "2": "N", "3": "L_SW_A", "4": "N", "5": "L_SW_B", "6": "N", "7": "L_FUSED", "8": "N"},
         description="L in, N in, heater A L-sw/N, heater B L-sw/N, PSU L (fused)/N; 300 V rated"),

    # 24 V loads and sensors
    Part("J_LOADS", "valves + fan", "Connector_Generic:Conn_01x06",
         "Connector_Phoenix_MSTB:PhoenixContact_MSTBVA_2,5_6-G-5,08_1x06_P5.08mm_Vertical",
         {"1": "+24V", "2": "SW_VA", "3": "+24V", "4": "SW_VB", "5": "+24V", "6": "SW_FAN"},
         description="valve A, valve B, fan: 24+ and SW each"),
    Part("J_SENS", "DS18B20 x3", "Connector_Generic:Conn_01x09",
         "Connector_Phoenix_MC:PhoenixContact_MCV_1,5_9-G-3.5_1x09_P3.50mm_Vertical",
         {"1": "+3V3", "2": "OW_DQ", "3": "GND", "4": "+3V3", "5": "OW_DQ", "6": "GND", "7": "+3V3", "8": "OW_DQ", "9": "GND"},
         description="three 3V3/DQ/GND triples, 3.5 mm pluggable"),
    _r("R18", "5.1k", "+3V3", "OW_DQ", desc="1-wire pullup"),
    _c("C5", "100n", "+3V3", "GND", desc="3V3 at the sensor header"),
    _c("C6", "10u 10V", "+3V3", "GND", desc="3V3 at the sensor header"),
    Part("J_DISP", "ST7789 240x240", "Connector_Generic:Conn_01x08",
         "Connector_PinHeader_2.54mm:PinHeader_1x08_P2.54mm_Vertical",
         {"1": "GND", "2": "+3V3", "3": "SPI_CLK", "4": "SPI_MOSI", "5": "LCD_RST", "6": "LCD_DC", "7": "LCD_CS", "8": "LCD_BL"},
         description="GND 3V3 SCL SDA RES DC CS BLK"),

    # Test points, mounting holes, power flags
    Part("TP1", "GND", "Connector:TestPoint", "TestPoint:TestPoint_Pad_D1.5mm", {"1": "GND"}),
    Part("TP2", "3V3", "Connector:TestPoint", "TestPoint:TestPoint_Pad_D1.5mm", {"1": "+3V3"}),
    Part("TP3", "5V", "Connector:TestPoint", "TestPoint:TestPoint_Pad_D1.5mm", {"1": "+5V"}),
    Part("TP4", "24V", "Connector:TestPoint", "TestPoint:TestPoint_Pad_D1.5mm", {"1": "+24V"}),
    Part("TP5", "HTR_A", "Connector:TestPoint", "TestPoint:TestPoint_Pad_D1.5mm", {"1": "HTR_A"}),
    Part("TP6", "HTR_B", "Connector:TestPoint", "TestPoint:TestPoint_Pad_D1.5mm", {"1": "HTR_B"}),
    Part("TP7", "VLV_A", "Connector:TestPoint", "TestPoint:TestPoint_Pad_D1.5mm", {"1": "VLV_A"}),
    Part("TP8", "VLV_B", "Connector:TestPoint", "TestPoint:TestPoint_Pad_D1.5mm", {"1": "VLV_B"}),
    Part("TP9", "FAN", "Connector:TestPoint", "TestPoint:TestPoint_Pad_D1.5mm", {"1": "FAN"}),
    Part("H1", "M3", "Mechanical:MountingHole", "MountingHole:MountingHole_3.2mm_M3", {}),
    Part("H2", "M3", "Mechanical:MountingHole", "MountingHole:MountingHole_3.2mm_M3", {}),
    Part("H3", "M3", "Mechanical:MountingHole", "MountingHole:MountingHole_3.2mm_M3", {}),
    Part("H4", "M3", "Mechanical:MountingHole", "MountingHole:MountingHole_3.2mm_M3", {}),
    Part("#FLG1", "PWR_FLAG", "power:PWR_FLAG", "", {"1": "+24V"}),
    Part("#FLG2", "PWR_FLAG", "power:PWR_FLAG", "", {"1": "GND"}),
    Part("#FLG3", "PWR_FLAG", "power:PWR_FLAG", "", {"1": "+3V3"}),
]

def by_ref(ref):
    for p in PARTS:
        if p.ref == ref:
            return p
    raise KeyError(ref)

def nets():
    out = {}
    for p in PARTS:
        for pad, net in sorted(p.pins.items()):
            if net != NC:
                out.setdefault(net, []).append((p.ref, pad))
    return out

def board_parts():
    """Parts that exist on the PCB (everything with a footprint)."""
    return [p for p in PARTS if p.footprint]

def check():
    """Invariants the table must satisfy. Returns a list of violations."""
    errs = []
    n = nets()
    for net, pads in n.items():
        if len(pads) < 2:
            errs.append("net %s has one connection: %s" % (net, pads))
    for hdr, pos in pinmap.RESERVED:
        ref = "J_ESP16" if hdr == 16 else "J_ESP12"
        if by_ref(ref).pins[str(pos)] != NC:
            errs.append("%s position %d is reserved (%s)" % (ref, pos, pinmap.RESERVED[(hdr, pos)]))
    for hdr, ref in ((16, "J_ESP16"), (12, "J_ESP12")):
        want = _socket_pins(hdr)
        got = by_ref(ref).pins
        for pos in sorted(want, key=int):
            if got.get(pos) != want[pos]:
                errs.append("%s position %s is %s, pinmap says %s" % (ref, pos, got.get(pos), want[pos]))
    for k in ("K1", "K2"):
        if by_ref(k).pins["4"] != NC:
            errs.append("%s NC contact must stay unconnected" % k)
    for net in MAINS_NETS:
        for ref, _ in n.get(net, []):
            if ref not in ("J_MAINS", "F1", "K1", "K2"):
                errs.append("mains net %s reaches %s" % (net, ref))
    return errs
