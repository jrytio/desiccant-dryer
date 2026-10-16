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
