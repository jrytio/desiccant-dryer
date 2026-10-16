import unittest
from dryer_board import libs, boards, sexp


class Libs(unittest.TestCase):
    def test_plain_symbol(self):
        pins = libs.symbol_pins("Device:R")
        self.assertEqual(set(pins), {"1", "2"})
        self.assertEqual(pins["1"][:3], (0.0, 3.81, 270))

    def test_extends_is_flattened(self):
        sym = libs.load_symbol("Transistor_BJT:MMBT2222A")
        self.assertEqual(sym[1], "Transistor_BJT:MMBT2222A")
        self.assertIsNone(sexp.find(sym, "extends"))
        pins = libs.symbol_pins("Transistor_BJT:MMBT2222A")
        self.assertEqual({n: p[3] for n, p in pins.items()}, {"1": "input", "2": "passive", "3": "passive"})
        units = [u[1] for u in sexp.find_all(sym, "symbol")]
        self.assertTrue(all(u.startswith("MMBT2222A_") for u in units), units)
        self.assertEqual(sexp.find(sym, "property")[1], "Reference")
        values = [p[2] for p in sexp.find_all(sym, "property") if p[1] == "Value"]
        self.assertEqual(values, ["MMBT2222A"])

    def test_every_part_symbol_and_footprint(self):
        for bd in boards.BOARDS:
            for p in bd.PARTS:
                pins = libs.symbol_pins(p.symbol)
                self.assertTrue(set(p.pins) <= set(pins), "%s: pins %s not in symbol %s" % (p.ref, set(p.pins) - set(pins), p.symbol))
                if p.footprint:
                    pads = libs.footprint_pads(p.footprint)
                    self.assertTrue(set(p.pins) <= pads, "%s: pads %s not in footprint %s" % (p.ref, set(p.pins) - pads, p.footprint))

    def test_relay_pad_geometry_matches_songle(self):
        """docs/hardware.md: COM (0,0), coil (2.0, +-6.0), NO/NC (14.2, +-6.0); KiCad's SANYOU pattern is within 0.1 mm."""
        pos = libs.footprint_pad_positions("Relay_THT:Relay_SPDT_SANYOU_SRD_Series_Form_C")
        self.assertAlmostEqual(pos["1"][0], 0.0, delta=0.1)
        self.assertAlmostEqual(pos["1"][1], 0.0, delta=0.1)
        for pad in ("2", "5"):
            self.assertAlmostEqual(pos[pad][0], 2.0, delta=0.1)
            self.assertAlmostEqual(abs(pos[pad][1]), 6.0, delta=0.1)
        for pad in ("3", "4"):
            self.assertAlmostEqual(pos[pad][0], 14.2, delta=0.1)
            self.assertAlmostEqual(abs(pos[pad][1]), 6.0, delta=0.1)
        self.assertGreater(pos["3"][1], 0)   # NO at +y (KiCad y-down); NC at -y
        self.assertLess(pos["4"][1], 0)

    def test_regulator_footprint_pitch(self):
        pos = libs.footprint_pad_positions("Converter_DCDC:Converter_DCDC_TRACO_TSR-1_THT")
        self.assertAlmostEqual(pos["2"][0] - pos["1"][0], 2.54, delta=0.01)
        self.assertAlmostEqual(pos["3"][0] - pos["2"][0], 2.54, delta=0.01)

    def test_fuse_holder_pitch_and_slots(self):
        """22.5 mm nominal (XFCN PTF-77 datasheet), slots 2.4 x 1.6 along the pitch so a BLX-A
        holder at 21.5 to 22.7 mm (its acceptance range) and a PTF-77 both fit."""
        fp = "dryer:Fuseholder_5x20mm_Covered_P22.50mm_Slot"
        pos = libs.footprint_pad_positions(fp)
        self.assertAlmostEqual(pos["2"][0] - pos["1"][0], 22.5, delta=0.01)
        for pad in sexp.find_all(libs._footprint(fp), "pad"):
            drill = sexp.find(pad, "drill")
            self.assertEqual(drill[1], "oval", pad[1])
            self.assertEqual([float(drill[2]), float(drill[3])], [2.4, 1.6], pad[1])

    def test_fitted_fuse_holder_pitch_and_holes(self):
        """The footprint F1 uses is the fab-fitted XFCN PTF-76-B: pins 15 mm apart in 1.6 mm
        holes (its datasheet). The holders on hand do not fit beside the vertical plug."""
        fp = boards.by_name("mains").by_ref("F1").footprint
        self.assertEqual(fp, "dryer:Fuseholder_5x20mm_Covered_XFCN_PTF-76-B_P15.00mm")
        pos = libs.footprint_pad_positions(fp)
        self.assertAlmostEqual(pos["2"][0] - pos["1"][0], 15.0, delta=0.01)
        for pad in sexp.find_all(libs._footprint(fp), "pad"):
            self.assertEqual(float(sexp.find(pad, "drill")[1]), 1.6, pad[1])

    def test_mains_header_is_vertical_with_dorabo_drills(self):
        """J_MAINS: 8 pins on 5.08 mm in a line, 1.7 mm holes for the DORABO 1.0 mm square pins,
        on the local copy of KiCad's MSTBVA vertical footprint."""
        fp = boards.by_name("mains").by_ref("J_MAINS").footprint
        self.assertIn("MSTBVA", fp); self.assertIn("Vertical", fp)
        pos = libs.footprint_pad_positions(fp)
        self.assertEqual(len(pos), 8)
        self.assertAlmostEqual(pos["8"][0] - pos["1"][0], 7 * 5.08, delta=0.01)
        for pad in sexp.find_all(libs._footprint(fp), "pad"):
            self.assertEqual(float(sexp.find(pad, "drill")[1]), 1.7, pad[1])

    def test_link_header_pitch(self):
        pos = libs.footprint_pad_positions(boards.by_name("controller").by_ref("J_RLY").footprint)
        self.assertAlmostEqual(pos["4"][0] - pos["1"][0], 7.5, delta=0.01)   # 3 x 2.50 mm: JST XH, not 2.54
