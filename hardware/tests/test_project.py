"""The custom DRC rules (mains.RULES), each with a red board that must fail and a green one
that must pass, on scratch boards under the mains project's settings."""
import os, json, tempfile, unittest
import pcbnew
from dryer_board import project, mains, kicad_env, libs, board


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


def _hole_board(path, gap_mm):
    """An M4 mounting hole and a 1.5 mm L_IN track whose edge is gap_mm from the hole's edge."""
    b = pcbnew.BOARD()
    edge = pcbnew.PCB_SHAPE(b)
    edge.SetShape(pcbnew.SHAPE_T_RECT)
    edge.SetStart(pcbnew.VECTOR2I_MM(0, 0))
    edge.SetEnd(pcbnew.VECTOR2I_MM(60, 40))
    edge.SetLayer(pcbnew.Edge_Cuts)
    edge.SetWidth(pcbnew.FromMM(0.1))
    b.Add(edge)
    lib_id = mains.by_ref("H2").footprint
    fp = pcbnew.FootprintLoad(libs.footprint_path(lib_id), libs.split(lib_id)[1])
    fp.SetReference("H2")
    fp.SetPosition(pcbnew.VECTOR2I_MM(10, 10))
    b.Add(fp)
    net = pcbnew.NETINFO_ITEM(b, "L_IN")
    b.Add(net)
    y = 10 + 2.15 + gap_mm + 0.75     # 4.3 mm hole
    t = pcbnew.PCB_TRACK(b)
    t.SetStart(pcbnew.VECTOR2I_MM(5, y))
    t.SetEnd(pcbnew.VECTOR2I_MM(50, y))
    t.SetWidth(pcbnew.FromMM(1.5))
    t.SetLayer(pcbnew.F_Cu)
    t.SetNet(net)
    b.Add(t)
    pcbnew.SaveBoard(path, b)


def _relay_board(path, gap_mm, net_name="GND", width=0.3):
    """K1 (netless pads, as on the real board) plus a track on net_name gap_mm right of pad 4."""
    b = pcbnew.BOARD()
    edge = pcbnew.PCB_SHAPE(b)
    edge.SetShape(pcbnew.SHAPE_T_RECT)
    edge.SetStart(pcbnew.VECTOR2I_MM(0, 0))
    edge.SetEnd(pcbnew.VECTOR2I_MM(60, 50))
    edge.SetLayer(pcbnew.Edge_Cuts)
    edge.SetWidth(pcbnew.FromMM(0.1))
    b.Add(edge)
    lib_id = mains.by_ref("K1").footprint
    fp = pcbnew.FootprintLoad(libs.footprint_path(lib_id), libs.split(lib_id)[1])
    fp.SetReference("K1")
    fp.SetPosition(pcbnew.VECTOR2I_MM(10, 25))
    b.Add(fp)
    pad4 = [p for p in fp.Pads() if p.GetNumber() == "4"][0]
    bb = pad4.GetBoundingBox()
    x = bb.GetRight() + pcbnew.FromMM(gap_mm + width / 2)
    net = pcbnew.NETINFO_ITEM(b, net_name)
    b.Add(net)
    t = pcbnew.PCB_TRACK(b)
    t.SetStart(pcbnew.VECTOR2I(x, bb.GetCenter().y - pcbnew.FromMM(1)))
    t.SetEnd(pcbnew.VECTOR2I(x, bb.GetCenter().y + pcbnew.FromMM(1)))
    t.SetWidth(pcbnew.FromMM(width))
    t.SetLayer(pcbnew.F_Cu)
    t.SetNet(net)
    b.Add(t)
    pcbnew.SaveBoard(path, b)


def _mains_by_relay_board(path, gap_mm):
    _relay_board(path, gap_mm, "L_SW_A", 1.5)


def _track_board(path, tracks, areas=(), size=(64, 85)):
    """A bare board: tracks are (net, (x1, y1), (x2, y2), width), all on F.Cu; areas are
    relay_pads rule areas made the way board.build makes them."""
    b = pcbnew.BOARD()
    edge = pcbnew.PCB_SHAPE(b)
    edge.SetShape(pcbnew.SHAPE_T_RECT)
    edge.SetStart(pcbnew.VECTOR2I_MM(0, 0))
    edge.SetEnd(pcbnew.VECTOR2I_MM(*size))
    edge.SetLayer(pcbnew.Edge_Cuts)
    edge.SetWidth(pcbnew.FromMM(0.1))
    b.Add(edge)
    for rect in areas:
        board._rule_area(b, "relay_pads", rect, fills=False)
    nets = {}
    for name, (x1, y1), (x2, y2), w in tracks:
        if name not in nets:
            nets[name] = pcbnew.NETINFO_ITEM(b, name)
            b.Add(nets[name])
        t = pcbnew.PCB_TRACK(b)
        t.SetStart(pcbnew.VECTOR2I_MM(x1, y1))
        t.SetEnd(pcbnew.VECTOR2I_MM(x2, y2))
        t.SetWidth(pcbnew.FromMM(w))
        t.SetLayer(pcbnew.F_Cu)
        t.SetNet(nets[name])
        b.Add(t)
    pcbnew.SaveBoard(path, b)


_SPINE_X = 37          # the mains spine, between the two relay areas (y 38 to 56)
_BETWEEN_Y = 47

def _spine_board(y1, y2):
    """The mains spine from y1 to y2 between the two real relay areas, and a GND track
    gap_mm (copper edge to edge) to its left at y 47, level with the gap between the areas."""
    def make(path, gap_mm):
        x = _SPINE_X - 0.75 - gap_mm - 0.15
        _track_board(path, [("L_FUSED", (_SPINE_X, y1), (_SPINE_X, y2), 1.5), ("GND", (x, _BETWEEN_Y - 2), (x, _BETWEEN_Y + 2), 0.3)],
                     mains.RELAY_AREAS)
    return make


def _in_relay_area_board(path, gap_mm):
    """A mains track and a GND track gap_mm apart, both inside a relay_pads area."""
    x1, y1, x2, _y2 = mains.RELAY_AREAS[0]
    y = y1 + 4
    _track_board(path, [("L_FUSED", (x1 + 4, y), (x2 - 4, y), 1.5), ("GND", (x1 + 4, y + 0.75 + gap_mm + 0.15), (x2 - 4, y + 0.75 + gap_mm + 0.15), 0.3)],
                 [mains.RELAY_AREAS[0]])


def _l_to_l_board(other):
    def make(path, gap_mm):
        _track_board(path, [("L_IN", (10, 10), (50, 10), 1.5), (other, (10, 10 + 1.5 + gap_mm), (50, 10 + 1.5 + gap_mm), 1.5)],
                     size=(60, 40))
    return make


def _narrow_mains_board(path, width):
    _track_board(path, [("L_IN", (10, 10), (50, 10), width)], size=(60, 40))


def _mains_near_edge_board(path, gap_mm):
    _track_board(path, [("L_IN", (10, gap_mm + 0.75), (50, gap_mm + 0.75), 1.5)], size=(60, 40))


class Project(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        project.write(mains, self.dir)

    def _drc(self, gap, make=_two_track_board):
        pcb = os.path.join(self.dir, mains.PROJECT + ".kicad_pcb")
        make(pcb, gap)
        # SaveBoard writes a default .kicad_pro beside the board; put ours back.
        project.write(mains, self.dir)
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

    def test_mains_track_may_pass_the_nc_pad_at_mains_clearance(self):
        # The NC pad is at mains potential: the mains-to-SELV rules must not apply to it.
        text = self._drc(2.0, _mains_by_relay_board)
        self.assertIn("** Found 0 DRC violations **", text, text)

    def test_red_mains_track_near_mounting_hole_fails(self):
        text = self._drc(2.0, _hole_board)
        self.assertIn("rule 'mains to mounting holes'", text, text)

    def test_green_mains_track_clear_of_mounting_hole_passes(self):
        text = self._drc(7.0, _hole_board)
        self.assertIn("** Found 0 DRC violations **", text, text)

    def test_red_mains_between_relay_areas_keeps_6mm(self):
        # The spine's middle piece clears both relay areas, so the 6 mm rule holds on it.
        a, b = mains.RELAY_AREAS
        text = self._drc(4.0, _spine_board(a[3] + 1, b[1] - 1))
        self.assertIn("rule 'mains to selv'", text, text)

    def test_mains_segment_touching_a_relay_area_is_relaxed_along_its_length(self):
        # Why mains.py splits the spines at the area edges: a segment that reaches into a
        # relay area gets 3.5 mm everywhere, here 4 mm at y 47, well outside both areas.
        a, b = mains.RELAY_AREAS
        text = self._drc(4.0, _spine_board(a[3] - 1, b[1] + 1))
        self.assertIn("** Found 0 DRC violations **", text, text)

    def test_red_gap_inside_relay_area_fails_the_relaxed_rule(self):
        text = self._drc(3.0, _in_relay_area_board)
        self.assertIn("rule 'mains to selv at relay pads'", text, text)

    def test_green_gap_inside_relay_area_passes(self):
        text = self._drc(4.0, _in_relay_area_board)
        self.assertIn("** Found 0 DRC violations **", text, text)

    def test_red_l_side_nets_closer_than_1_6mm_fail(self):
        text = self._drc(1.2, _l_to_l_board("L_FUSED"))
        self.assertIn("rule 'mains L to L'", text, text)

    def test_green_l_side_nets_2mm_apart_pass(self):
        text = self._drc(2.0, _l_to_l_board("L_FUSED"))
        self.assertIn("** Found 0 DRC violations **", text, text)

    def test_l_to_n_keeps_the_netclass_clearance(self):
        text = self._drc(1.2, _l_to_l_board("N"))
        self.assertIn("** Found 0 DRC violations **", text, text)

    def test_red_narrow_mains_track_fails(self):
        text = self._drc(1.0, _narrow_mains_board)
        self.assertIn("rule 'mains track width'", text, text)

    def test_red_mains_track_near_board_edge_fails(self):
        text = self._drc(0.5, _mains_near_edge_board)
        self.assertIn("rule 'mains to board edge'", text, text)

    def test_project_json(self):
        with open(os.path.join(self.dir, mains.PROJECT + ".kicad_pro"), encoding="utf-8") as f:
            pro = json.load(f)
        names = [c["name"] for c in pro["net_settings"]["classes"]]
        self.assertEqual(names[0], "Default")
        self.assertIn("MAINS", names)
        self.assertIn({"netclass": "MAINS", "pattern": "N"}, pro["net_settings"]["netclass_patterns"])
        self.assertEqual(pro["net_settings"]["meta"]["version"], 5)

    def test_controller_project_has_no_mains_class_or_rules(self):
        from dryer_board import controller
        d = tempfile.mkdtemp()
        project.write(controller, d)
        with open(os.path.join(d, controller.PROJECT + ".kicad_pro"), encoding="utf-8") as f:
            pro = json.load(f)
        self.assertNotIn("MAINS", [c["name"] for c in pro["net_settings"]["classes"]])
        with open(os.path.join(d, controller.PROJECT + ".kicad_dru"), encoding="utf-8") as f:
            self.assertEqual(f.read().strip(), "(version 1)")
