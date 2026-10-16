# hardware/tests/test_parts.py
"""The two parts tables: their invariants, and the chains each board must wire."""
import unittest
from unittest import mock
from dryer_board import boards, controller, mains, parts, pinmap
from dryer_board.parts import NC, Part

class EveryBoard(unittest.TestCase):
    def test_invariants_hold(self):
        for bd in boards.BOARDS:
            self.assertEqual(bd.check(), [], bd.SHORT)

    def test_refs_unique_and_pins_named(self):
        for bd in boards.BOARDS:
            refs = [p.ref for p in bd.PARTS]
            self.assertEqual(len(refs), len(set(refs)), bd.SHORT)
            for p in bd.PARTS:
                for pad, net in p.pins.items():
                    self.assertTrue(net, "%s %s pad %s has an empty net" % (bd.SHORT, p.ref, pad))

    def test_every_part_has_catalogue_status(self):
        for bd in boards.BOARDS:
            for p in bd.PARTS:
                if p.symbol.startswith("Mechanical:") or p.symbol.startswith("power:") or p.symbol == "Connector:TestPoint":
                    continue
                self.assertTrue(p.lcsc or p.hand_fit, "%s %s needs an LCSC number or hand_fit" % (bd.SHORT, p.ref))

    def test_mounting_holes_are_m4(self):
        for bd in boards.BOARDS:
            for ref in ("H1", "H2", "H3", "H4"):
                self.assertEqual(bd.by_ref(ref).footprint, "MountingHole:MountingHole_4.3mm_M4", "%s %s" % (bd.SHORT, ref))

    def test_link_is_the_same_connector_on_both_boards(self):
        a, b = controller.by_ref("J_RLY"), mains.by_ref("J_CTRL")
        self.assertEqual(a.footprint, b.footprint)
        self.assertEqual(a.lcsc, b.lcsc)
        self.assertEqual(a.pins, parts.LINK_PINS)
        self.assertEqual(b.pins, parts.LINK_PINS)
        # the protoboard harness order (docs/hardware.md): 5 V, GND, heater A, heater B
        self.assertEqual([parts.LINK_PINS[str(i)] for i in range(1, 5)], ["+5V", "GND", "RLY_A", "RLY_B"])

    def test_polarity(self):
        for bd in boards.BOARDS:
            for p in bd.PARTS:
                if p.symbol == "Device:C_Polarized":
                    self.assertIn(p.pins["1"], ("+24V", "+5V"), p.ref)
                    self.assertEqual(p.pins["2"], "GND", p.ref)
                if p.symbol == "Device:LED":
                    self.assertTrue(p.pins["2"].startswith("LED_"), "%s anode must go to its resistor" % p.ref)
                    self.assertIn(p.pins["1"], ("GND", "COIL_A", "COIL_B", "SW_VA", "SW_VB", "SW_FAN"), p.ref)
                if p.ref in ("D1", "D2"):
                    self.assertEqual(p.pins["1"], "+5V")   # flyback cathode to the coil supply
                if p.ref in ("D5", "D6", "D7"):
                    self.assertEqual(p.pins["1"], "+24V")

    def test_mains_nets_only_on_the_mains_board(self):
        for n in mains.MAINS_NETS:
            self.assertNotIn(n, controller.nets())
            self.assertIn(n, mains.nets())
        self.assertEqual(controller.MAINS_NETS, [])
        self.assertEqual(controller.MAINS_TRACKS, [])


class Controller(unittest.TestCase):
    def _pin(self, ref, pad):
        return controller.by_ref(ref).pins[pad]

    def test_sockets_follow_pinmap(self):
        j16, j12 = controller.by_ref("J_ESP16"), controller.by_ref("J_ESP12")
        self.assertEqual(j12.pins[str(pinmap.FUNCTIONS["heater_a"][1])], "HTR_A")
        self.assertEqual(j12.pins[str(pinmap.FUNCTIONS["fan"][1])], "FAN")
        self.assertEqual(j16.pins[str(pinmap.FUNCTIONS["onewire"][1])], "OW_DQ")
        self.assertEqual(j16.pins[str(pinmap.FUNCTIONS["lcd_cs"][1])], "LCD_CS")
        for pos in (9, 10, 11, 12, 1, 2):
            self.assertEqual(j12.pins[str(pos)], NC, "12-pin %d must be free" % pos)
        for pos in (1, 3, 6, 7, 14, 15, 16):
            self.assertEqual(j16.pins[str(pos)], NC, "16-pin %d must be free" % pos)
        self.assertEqual(j12.pins["3"], "VBUS")
        self.assertEqual(j16.pins["2"], "+3V3")
        self.assertEqual(j16.pins["4"], "GND")

    def test_i2c_positions_stay_free_for_qwiic(self):
        """The SHT45 is on the Thing Plus's Qwiic connector, so the I2C positions carry nothing."""
        j12 = controller.by_ref("J_ESP12")
        for fn in ("i2c_scl", "i2c_sda"):
            hdr, pos = pinmap.FUNCTIONS[fn]
            self.assertEqual(hdr, 12)
            self.assertEqual(j12.pins[str(pos)], NC, fn)

    def test_relay_drive_reaches_the_link_through_1k(self):
        for htr, rly, r in (("HTR_A", "RLY_A", "R1"), ("HTR_B", "RLY_B", "R4")):
            self.assertEqual(self._pin(r, "1"), htr)
            self.assertEqual(self._pin(r, "2"), rly)
            self.assertEqual(controller.by_ref(r).value, "1k")
            self.assertEqual(sorted(x for x, _ in controller.nets()[rly]), [r.replace("R", "J_RLY") if False else "J_RLY", r])

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
        self.assertEqual(self._pin("J_RLY", "1"), "+5V")
        self.assertEqual(self._pin("J_RLY", "2"), "GND")

    def test_check_flags_net_on_unowned_socket_position(self):
        j = controller.by_ref("J_ESP16")
        bad = Part(j.ref, j.value, j.symbol, j.footprint, dict(j.pins, **{"6": "GND"}))
        with mock.patch.object(controller, "PARTS", [bad if p.ref == "J_ESP16" else p for p in controller.PARTS]):
            self.assertTrue(any("J_ESP16 position 6" in e for e in controller.check()))

    def test_check_flags_a_mains_net(self):
        j = controller.by_ref("J_RLY")
        bad = Part(j.ref, j.value, j.symbol, j.footprint, dict(j.pins, **{"4": "L_IN"}))
        extra = Part("TPX", "x", "Connector:TestPoint", "TestPoint:TestPoint_Pad_D1.5mm", {"1": "L_IN"})
        with mock.patch.object(controller, "PARTS", [bad if p.ref == "J_RLY" else p for p in controller.PARTS] + [extra]):
            errs = controller.check()
        self.assertTrue(any("mains net L_IN" in e for e in errs), errs)


class Mains(unittest.TestCase):
    def _pin(self, ref, pad):
        return mains.by_ref(ref).pins[pad]

    def test_relay_contacts(self):
        for ref, lsw in (("K1", "L_SW_A"), ("K2", "L_SW_B")):
            k = mains.by_ref(ref)
            self.assertEqual(k.pins["1"], "L_FUSED")   # COM
            self.assertEqual(k.pins["3"], lsw)         # NO -> heater
            self.assertEqual(k.pins["4"], NC)          # NC: no copper
            self.assertEqual(k.pins["2"], "+5V")       # coil
            self.assertIn(k.pins["5"], ("COIL_A", "COIL_B"))

    def test_heater_interlock_wiring(self):
        """Each heater has its own relay, driver and header pins; nothing shared but L_FUSED and N."""
        nets = mains.nets()
        self.assertEqual(sorted(r for r, _ in nets["L_SW_A"]), ["J_MAINS", "K1"])
        self.assertEqual(sorted(r for r, _ in nets["L_SW_B"]), ["J_MAINS", "K2"])
        self.assertEqual(sorted(r for r, _ in nets["L_FUSED"]), ["F1", "J_MAINS", "K1", "K2"])
        self.assertEqual(sorted(r for r, _ in nets["L_IN"]), ["F1", "J_MAINS"])

    def test_relay_channel_chains(self):
        """The link pin is the base net: pulldown, base, then collector to coil, flyback and LED."""
        for rly, coil, pull, q, k, d, led, jp in (("RLY_A", "COIL_A", "R2", "Q1", "K1", "D1", "D3", "3"),
                                                  ("RLY_B", "COIL_B", "R5", "Q2", "K2", "D2", "D4", "4")):
            self.assertEqual(self._pin("J_CTRL", jp), rly)
            self.assertEqual(self._pin(pull, "1"), rly)
            self.assertEqual(self._pin(pull, "2"), "GND")
            self.assertEqual(mains.by_ref(pull).value, "1k")
            self.assertEqual(self._pin(q, "1"), rly)
            self.assertEqual(self._pin(q, "2"), "GND")
            self.assertEqual(self._pin(q, "3"), coil)
            self.assertEqual(self._pin(k, "5"), coil)
            self.assertEqual(self._pin(d, "2"), coil)
            self.assertEqual(self._pin(led, "1"), coil)

    def test_mains_nets_declared(self):
        nets = mains.nets()
        for n in mains.MAINS_NETS:
            self.assertIn(n, nets)
            for ref, _ in nets[n]:
                self.assertIn(ref, mains.MAINS_PARTS, "%s touches mains net %s" % (ref, n))

    def test_fuse_holder_is_the_12_5mm_slotted_footprint(self):
        f1 = mains.by_ref("F1")
        self.assertEqual(f1.footprint, "dryer:Fuseholder_5x20mm_Covered_P12.50mm_Slot")
        self.assertTrue(f1.hand_fit)

    def test_check_flags_mains_pin_on_a_selv_net(self):
        k = mains.by_ref("K1")
        bad = Part(k.ref, k.value, k.symbol, k.footprint, dict(k.pins, **{"3": "HEATER_A"}))
        with mock.patch.object(mains, "PARTS", [bad if p.ref == "K1" else p for p in mains.PARTS]):
            self.assertTrue(any("K1 pin 3 is on HEATER_A" in e for e in mains.check()), mains.check())

    def test_check_flags_a_mains_net_reaching_a_selv_part(self):
        r = mains.by_ref("R2")
        bad = Part(r.ref, r.value, r.symbol, r.footprint, {"1": "L_IN", "2": "GND"})
        with mock.patch.object(mains, "PARTS", [bad if p.ref == "R2" else p for p in mains.PARTS]):
            self.assertTrue(any("mains net L_IN reaches R2" in e for e in mains.check()))
