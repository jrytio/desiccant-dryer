import csv, os, tempfile, unittest, zipfile
from dryer_board import export, circuit, kicad_env

PCB = os.path.join(kicad_env.PROJECT_DIR, circuit.PROJECT + ".kicad_pcb")
LAYER_EXTS = (".gtl", ".gbl", ".gtp", ".gbp", ".gto", ".gbo", ".gts", ".gbs", ".gm1")


def _rows(path):
    with open(path, newline="") as f:
        return list(csv.reader(f))


@unittest.skipUnless(os.path.exists(PCB), "no committed board yet")
class Export(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = tempfile.mkdtemp()
        cls.paths = export.export_all(kicad_env.PROJECT_DIR, cls.out)

    def test_files(self):
        for key in ("gerber_zip", "bom", "cpl", "schematic_pdf", "top_svg", "render_top", "render_iso", "erc", "drc"):
            self.assertTrue(os.path.isfile(self.paths[key]), key)
        with zipfile.ZipFile(self.paths["gerber_zip"]) as z:
            names = z.namelist()
        self.assertEqual(len([n for n in names if n.endswith(LAYER_EXTS)]), 9)
        self.assertTrue(any(n.endswith(".drl") for n in names))

    def test_cpl_format(self):
        rows = _rows(self.paths["cpl"])
        self.assertEqual(rows[0], ["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        self.assertTrue(all(r[3] == "Top" for r in rows[1:]))
        self.assertIn("K1", [r[0] for r in rows[1:]])
        self.assertNotIn("H1", [r[0] for r in rows[1:]])

    def test_bom_format(self):
        rows = _rows(self.paths["bom"])
        self.assertEqual(rows[0], ["Comment", "Designator", "Footprint", "LCSC Part #"])
        relay = [r for r in rows if "K1" in r[1]][0]
        self.assertEqual(relay[3], "C35449")
        self.assertFalse(any("H1" in r[1] for r in rows[1:]))
