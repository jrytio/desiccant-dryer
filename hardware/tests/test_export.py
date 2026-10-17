import csv, os, tempfile, unittest, zipfile
from dryer_board import export, boards, kicad_env

LAYER_EXTS = (".gtl", ".gbl", ".gtp", ".gbp", ".gto", ".gbo", ".gts", ".gbs", ".gm1")
PCBS = {bd: os.path.join(kicad_env.project_dir(bd), bd.PROJECT + ".kicad_pcb") for bd in boards.BOARDS}


def _rows(path):
    with open(path, newline="") as f:
        return list(csv.reader(f))


@unittest.skipUnless(all(os.path.exists(p) for p in PCBS.values()), "no committed boards yet")
class Export(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = tempfile.mkdtemp()
        cls.paths = {bd: export.export_all(bd, kicad_env.project_dir(bd), cls.out) for bd in boards.BOARDS}

    def test_files(self):
        for bd, paths in self.paths.items():
            for key in ("gerber_zip", "bom", "cpl", "schematic_pdf", "top_svg", "render_top", "render_iso", "erc", "drc"):
                self.assertTrue(os.path.isfile(paths[key]), "%s %s" % (bd.SHORT, key))
                self.assertIn(bd.PROJECT + "-rev" + bd.REVISION, os.path.basename(paths[key]), key)
            with zipfile.ZipFile(paths["gerber_zip"]) as z:
                names = z.namelist()
            self.assertEqual(len([n for n in names if n.endswith(LAYER_EXTS)]), 9, bd.SHORT)
            self.assertTrue(any(n.endswith(".drl") for n in names), bd.SHORT)

    def test_cpl_format(self):
        for bd, paths in self.paths.items():
            rows = _rows(paths["cpl"])
            self.assertEqual(rows[0], ["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
            self.assertTrue(all(r[3] == "Top" for r in rows[1:]), bd.SHORT)
            self.assertNotIn("H1", [r[0] for r in rows[1:]])
        self.assertIn("K1", [r[0] for r in _rows(self.paths[boards.by_name("mains")]["cpl"])[1:]])
        self.assertIn("U1", [r[0] for r in _rows(self.paths[boards.by_name("controller")]["cpl"])[1:]])

    def test_cpl_positions_are_part_centres(self):
        """JLCPCB places a part at Mid X/Y, so the CPL must give the centre of the pads, not
        KiCad's anchor (pin 1 on the through-hole parts). y is negated, as in KiCad's file."""
        import pcbnew
        for bd, paths in self.paths.items():
            rows = {r[0]: r for r in _rows(paths["cpl"])[1:]}
            b = pcbnew.LoadBoard(PCBS[bd])
            for fp in b.GetFootprints():
                ref = fp.GetReference()
                if ref not in rows:
                    continue
                xs, ys = [], []
                for p in fp.Pads():
                    bb = p.GetBoundingBox()
                    xs += [bb.GetX(), bb.GetX() + bb.GetWidth()]
                    ys += [bb.GetY(), bb.GetY() + bb.GetHeight()]
                self.assertAlmostEqual(float(rows[ref][1]), (min(xs) + max(xs)) / 2e6, places=3, msg=ref)
                self.assertAlmostEqual(float(rows[ref][2]), -(min(ys) + max(ys)) / 2e6, places=3, msg=ref)
        ctl = {r[0]: r for r in _rows(self.paths[boards.by_name("controller")]["cpl"])[1:]}
        # the 12-pin socket's anchor is its pin 1 at (21.13, 10); its centre is 13.97 mm along the row
        self.assertAlmostEqual(float(ctl["J_ESP12"][1]), 35.10, places=2)
        self.assertAlmostEqual(float(ctl["J_ESP12"][2]), -10.00, places=2)
        self.assertAlmostEqual(float(ctl["C1"][1]), 4.60, places=2)   # a two-pad part: anchor already the centre

    def test_cpl_rotations_follow_jlcpcb(self):
        """The corrections JLCPCB's preview asked for on 2026-10-16 (hardware/README.md)."""
        ctl = {r[0]: r for r in _rows(self.paths[boards.by_name("controller")]["cpl"])[1:]}
        mains = {r[0]: r for r in _rows(self.paths[boards.by_name("mains")]["cpl"])[1:]}
        self.assertEqual(float(ctl["Q3"][4]), 180.0)        # SOT-23 at KiCad 0
        self.assertEqual(float(ctl["J_LOADS"][4]), 180.0)   # pluggable header at KiCad 0
        self.assertEqual(float(ctl["J_ESP12"][4]), 0.0)     # pin socket at KiCad 90
        self.assertEqual(float(ctl["C1"][4]), -90.0)        # electrolytic at KiCad 90
        self.assertEqual(float(ctl["R7"][4]), 0.0)          # resistor: unchanged
        self.assertEqual(float(mains["J_CTRL"][4]), 90.0)   # JST XH at KiCad -90
        self.assertEqual(float(mains["K1"][4]), 0.0)        # relay: no correction known yet

    def test_jlc_rotation_table(self):
        self.assertEqual(export.jlc_rotation("Package_TO_SOT_SMD:SOT-23", 0), 180.0)
        self.assertEqual(export.jlc_rotation("Package_TO_SOT_SMD:SOT-23", 90), -90.0)
        self.assertEqual(export.jlc_rotation("Connector_PinSocket_2.54mm:PinSocket_1x12_P2.54mm_Vertical", 90), 0.0)
        self.assertEqual(export.jlc_rotation("Resistor_SMD:R_0805_2012Metric", 270), -90.0)
        self.assertEqual(export.jlc_rotation("Relay_THT:Relay_SPDT_SANYOU_SRD_Series_Form_C", 0), 0.0)
        self.assertEqual(export.jlc_rotation("Capacitor_SMD:CP_Elec_8x10.5", 180), 0.0)

    def test_cpl_without_board_passes_kicad_values_through(self):
        src = os.path.join(self.out, "plain-pos.csv"); dst = os.path.join(self.out, "plain-cpl.csv")
        with open(src, "w", newline="") as f:
            w = csv.writer(f); w.writerow(["Ref", "Val", "Package", "PosX", "PosY", "Rot", "Side"])
            w.writerow(["Q9", "x", "SOT-23", "1.0", "-2.0", "90.0", "top"]); w.writerow(["TP1", "x", "TestPoint", "0", "0", "0", "top"])
        export.jlc_cpl(src, dst)
        self.assertEqual(_rows(dst)[1:], [["Q9", "1.0", "-2.0", "Top", "90.0"]])

    def test_bom_format(self):
        rows = _rows(self.paths[boards.by_name("mains")]["bom"])
        self.assertEqual(rows[0], ["Comment", "Designator", "Footprint", "LCSC Part #"])
        relay = [r for r in rows if "K1" in r[1]][0]
        self.assertEqual(relay[3], "C35449")
        for bd, paths in self.paths.items():
            self.assertFalse(any("H1" in r[1] for r in _rows(paths["bom"])[1:]), bd.SHORT)

    def test_bom_matches_cpl(self):
        for bd, paths in self.paths.items():
            bom = set()
            for r in _rows(paths["bom"])[1:]:
                bom.update(d.strip() for d in r[1].split(","))
            cpl = set(r[0] for r in _rows(paths["cpl"])[1:])
            self.assertFalse([d for d in bom if "?" in d or "-" in d], bd.SHORT)
            self.assertEqual(bom, cpl, bd.SHORT)

    def test_every_bom_line_has_an_lcsc_number_unless_hand_fitted(self):
        for bd, paths in self.paths.items():
            for r in _rows(paths["bom"])[1:]:
                refs = [d.strip() for d in r[1].split(",")]
                if all(bd.by_ref(ref).hand_fit for ref in refs):
                    self.assertEqual(r[3], "", r)   # U1: hand-fitted (hardware/README.md)
                else:
                    self.assertTrue(r[3], (bd.SHORT, r))

    def test_hand_fitted_parts(self):
        self.assertEqual([p.ref for p in boards.by_name("controller").PARTS if p.hand_fit], ["U1"])
        self.assertEqual([p.ref for p in boards.by_name("mains").PARTS if p.hand_fit], [])
