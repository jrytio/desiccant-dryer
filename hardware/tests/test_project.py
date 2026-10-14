import os, json, tempfile, unittest
import pcbnew
from dryer_board import project, circuit, kicad_env, libs


def _two_track_board(path, gap_mm):
    b = pcbnew.BOARD()
    edge = pcbnew.PCB_SHAPE(b)
    edge.SetShape(pcbnew.SHAPE_T_RECT)
    edge.SetStart(pcbnew.VECTOR2I_MM(0, 0))
    edge.SetEnd(pcbnew.VECTOR2I_MM(60, 40))
    edge.SetLayer(pcbnew.Edge_Cuts)
    edge.SetWidth(pcbnew.FromMM(0.1))
    b.Add(edge)
    for name, y, w in (("L_IN", 10, 1.5), ("GND", 10 + gap_mm, 0.3)):
        net = pcbnew.NETINFO_ITEM(b, name)
        b.Add(net)
        t = pcbnew.PCB_TRACK(b)
        t.SetStart(pcbnew.VECTOR2I_MM(10, y))
        t.SetEnd(pcbnew.VECTOR2I_MM(50, y))
        t.SetWidth(pcbnew.FromMM(w))
        t.SetLayer(pcbnew.F_Cu)
        t.SetNet(net)
        b.Add(t)
    pcbnew.SaveBoard(path, b)


def _relay_board(path, gap_mm):
    """K1 (netless pads, as on the real board) plus a 0.3 mm GND track gap_mm right of pad 4."""
    b = pcbnew.BOARD()
    edge = pcbnew.PCB_SHAPE(b)
    edge.SetShape(pcbnew.SHAPE_T_RECT)
    edge.SetStart(pcbnew.VECTOR2I_MM(0, 0))
    edge.SetEnd(pcbnew.VECTOR2I_MM(60, 50))
    edge.SetLayer(pcbnew.Edge_Cuts)
    edge.SetWidth(pcbnew.FromMM(0.1))
    b.Add(edge)
    lib_id = circuit.by_ref("K1").footprint
    fp = pcbnew.FootprintLoad(libs.footprint_path(lib_id), libs.split(lib_id)[1])
    fp.SetReference("K1")
    fp.SetPosition(pcbnew.VECTOR2I_MM(10, 25))
    b.Add(fp)
    pad4 = [p for p in fp.Pads() if p.GetNumber() == "4"][0]
    bb = pad4.GetBoundingBox()
    x = bb.GetRight() + pcbnew.FromMM(gap_mm + 0.15)
    net = pcbnew.NETINFO_ITEM(b, "GND")
    b.Add(net)
    t = pcbnew.PCB_TRACK(b)
    t.SetStart(pcbnew.VECTOR2I(x, bb.GetCenter().y - pcbnew.FromMM(1)))
    t.SetEnd(pcbnew.VECTOR2I(x, bb.GetCenter().y + pcbnew.FromMM(1)))
    t.SetWidth(pcbnew.FromMM(0.3))
    t.SetLayer(pcbnew.F_Cu)
    t.SetNet(net)
    b.Add(t)
    pcbnew.SaveBoard(path, b)


class Project(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        project.write(self.dir)

    def _drc(self, gap, make=_two_track_board):
        pcb = os.path.join(self.dir, circuit.PROJECT + ".kicad_pcb")
        make(pcb, gap)
        # SaveBoard writes a default .kicad_pro beside the board; put ours back.
        project.write(self.dir)
        rpt = os.path.join(self.dir, "drc.rpt")
        kicad_env.run_cli("pcb", "drc", "--severity-error", "-o", rpt, pcb)
        with open(rpt, encoding="utf-8") as f:
            return f.read()

    def test_red_board_fails_the_mains_rule(self):
        text = self._drc(4.0)
        self.assertIn("rule 'mains to selv'", text, text)

    def test_green_board_passes(self):
        text = self._drc(8.0)
        self.assertIn("** Found 0 DRC violations **", text, text)

    def test_red_track_near_relay_nc_pad_fails(self):
        text = self._drc(2.0, _relay_board)
        self.assertIn("rule 'relay NC contact is live'", text, text)

    def test_green_track_clear_of_relay_nc_pad_passes(self):
        text = self._drc(7.0, _relay_board)
        self.assertIn("** Found 0 DRC violations **", text, text)

    def test_project_json(self):
        with open(os.path.join(self.dir, circuit.PROJECT + ".kicad_pro"), encoding="utf-8") as f:
            pro = json.load(f)
        names = [c["name"] for c in pro["net_settings"]["classes"]]
        self.assertEqual(names[0], "Default")
        self.assertIn("MAINS", names)
        self.assertIn({"netclass": "MAINS", "pattern": "N"}, pro["net_settings"]["netclass_patterns"])
        self.assertEqual(pro["net_settings"]["meta"]["version"], 5)
