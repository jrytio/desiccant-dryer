# hardware/tests/test_circuit.py
import unittest
from unittest import mock
from dryer_board import circuit, pinmap

class Circuit(unittest.TestCase):
    def test_invariants_hold(self):
        self.assertEqual(circuit.check(), [])

    def test_refs_unique_and_pins_named(self):
        refs = [p.ref for p in circuit.PARTS]
        self.assertEqual(len(refs), len(set(refs)))
        for p in circuit.PARTS:
            for pad, net in p.pins.items():
                self.assertTrue(net, "%s pad %s has an empty net" % (p.ref, pad))

    def test_relay_contacts(self):
        for ref, lsw in (("K1", "L_SW_A"), ("K2", "L_SW_B")):
            k = circuit.by_ref(ref)
            self.assertEqual(k.pins["1"], "L_FUSED")   # COM
            self.assertEqual(k.pins["3"], lsw)         # NO -> heater
            self.assertEqual(k.pins["4"], circuit.NC)  # NC: no copper
            self.assertEqual(k.pins["2"], "+5V")       # coil
            self.assertIn(k.pins["5"], ("COIL_A", "COIL_B"))

    def test_heater_interlock_wiring(self):
        """Each heater has its own relay, driver and header pins; nothing shared but L_FUSED and N."""
        nets = circuit.nets()
        self.assertEqual(sorted(r for r, _ in nets["L_SW_A"]), ["J_MAINS", "K1"])
        self.assertEqual(sorted(r for r, _ in nets["L_SW_B"]), ["J_MAINS", "K2"])
        self.assertEqual(sorted(r for r, _ in nets["L_FUSED"]), ["F1", "J_MAINS", "K1", "K2"])
        self.assertEqual(sorted(r for r, _ in nets["L_IN"]), ["F1", "J_MAINS"])

    def test_sockets_follow_pinmap(self):
        j16, j12 = circuit.by_ref("J_ESP16"), circuit.by_ref("J_ESP12")
        self.assertEqual(j12.pins[str(pinmap.FUNCTIONS["heater_a"][1])], "HTR_A")
        self.assertEqual(j12.pins[str(pinmap.FUNCTIONS["fan"][1])], "FAN")
        self.assertEqual(j16.pins[str(pinmap.FUNCTIONS["onewire"][1])], "OW_DQ")
        self.assertEqual(j16.pins[str(pinmap.FUNCTIONS["lcd_cs"][1])], "LCD_CS")
        for pos in (9, 10, 11, 12, 1, 2):
            self.assertEqual(j12.pins[str(pos)], circuit.NC, "12-pin %d must be free" % pos)
        for pos in (1, 3, 6, 7, 14, 15, 16):
            self.assertEqual(j16.pins[str(pos)], circuit.NC, "16-pin %d must be free" % pos)
        self.assertEqual(j12.pins["3"], "VBUS")
        self.assertEqual(j16.pins["2"], "+3V3")
        self.assertEqual(j16.pins["4"], "GND")

    def _pin(self, ref, pad):
        return circuit.by_ref(ref).pins[pad]

    def test_relay_channel_chains(self):
        for htr, base, coil, r, q, k, d in (("HTR_A", "BASE_A", "COIL_A", "R1", "Q1", "K1", "D1"),
                                           ("HTR_B", "BASE_B", "COIL_B", "R4", "Q2", "K2", "D2")):
            self.assertEqual(self._pin(r, "1"), htr)
            self.assertEqual(self._pin(r, "2"), base)
            self.assertEqual(self._pin(q, "1"), base)
            self.assertEqual(self._pin(q, "2"), "GND")
            self.assertEqual(self._pin(q, "3"), coil)
            self.assertEqual(self._pin(k, "5"), coil)
            self.assertEqual(self._pin(d, "2"), coil)

    def test_mosfet_channel_chains(self):
        for vlv, gate, sw, r, q, d, jp in (("VLV_A", "GATE_A", "SW_VA", "R7", "Q3", "D5", "2"),
                                           ("VLV_B", "GATE_B", "SW_VB", "R10", "Q4", "D6", "4"),
                                           ("FAN", "GATE_C", "SW_FAN", "R13", "Q5", "D7", "6")):
            self.assertEqual(self._pin(r, "1"), vlv)
            self.assertEqual(self._pin(r, "2"), gate)
            self.assertEqual(self._pin(q, "1"), gate)
            self.assertEqual(self._pin(q, "2"), "GND")
            self.assertEqual(self._pin(q, "3"), sw)
            self.assertEqual(self._pin("J_LOADS", jp), sw)
            self.assertEqual(self._pin(d, "2"), sw)

    def test_supply_chains(self):
        self.assertEqual([self._pin("U1", p) for p in "123"], ["+24V", "GND", "+5V"])
        self.assertEqual(self._pin("J_24V", "1"), "+24V_RAW")
        self.assertEqual(self._pin("F2", "1"), "+24V_RAW")
        self.assertEqual(self._pin("F2", "2"), "+24V_F")
        self.assertEqual(self._pin("D11", "2"), "+24V_F")
        self.assertEqual(self._pin("D11", "1"), "+24V")
        self.assertEqual(self._pin("D14", "2"), "+5V")
        self.assertEqual(self._pin("D14", "1"), "V5_D")
        self.assertEqual(self._pin("SW1", "2"), "V5_D")
        self.assertEqual(self._pin("SW1", "1"), "VBUS")
        self.assertEqual(self._pin("J_ESP12", "3"), "VBUS")

    def test_check_flags_net_on_unowned_socket_position(self):
        j = circuit.by_ref("J_ESP16")
        bad = circuit.Part(j.ref, j.value, j.symbol, j.footprint, dict(j.pins, **{"6": "GND"}))
        parts = [bad if p.ref == "J_ESP16" else p for p in circuit.PARTS]
        with mock.patch.object(circuit, "PARTS", parts):
            self.assertTrue(any("J_ESP16 position 6" in e for e in circuit.check()))

    def test_polarity(self):
        for p in circuit.PARTS:
            if p.symbol == "Device:C_Polarized":
                self.assertIn(p.pins["1"], ("+24V", "+5V"), p.ref)
                self.assertEqual(p.pins["2"], "GND", p.ref)
            if p.symbol == "Device:LED":
                self.assertTrue(p.pins["2"].startswith("LED_"), "%s anode must go to its resistor" % p.ref)
                self.assertIn(p.pins["1"], ("GND", "COIL_A", "COIL_B", "SW_VA", "SW_VB", "SW_FAN"), p.ref)
            if p.symbol in ("Device:D", "Device:D_Schottky") and p.ref in ("D1", "D2"):
                self.assertEqual(p.pins["1"], "+5V")   # flyback cathode to the coil supply
            if p.ref in ("D5", "D6", "D7"):
                self.assertEqual(p.pins["1"], "+24V")

    def test_mains_nets_declared(self):
        nets = circuit.nets()
        for n in circuit.MAINS_NETS:
            self.assertIn(n, nets)
        for n in circuit.MAINS_NETS:
            for ref, _ in nets[n]:
                self.assertIn(ref, ("J_MAINS", "F1", "K1", "K2"), "%s touches mains net %s" % (ref, n))

    @unittest.expectedFailure
    def test_every_part_has_catalogue_status(self):
        for p in circuit.PARTS:
            if p.symbol.startswith("Mechanical:") or p.symbol.startswith("power:") or p.symbol == "Connector:TestPoint":
                continue
            self.assertTrue(p.lcsc or p.hand_fit, "%s needs an LCSC number or hand_fit" % p.ref)
