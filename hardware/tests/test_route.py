import os, shutil, tempfile, unittest
import pcbnew
from dryer_board import route, libs


@unittest.skipUnless(shutil.which("docker"), "docker not available")
class Route(unittest.TestCase):
    def test_small_board_routes(self):
        """Two footprints, one net, must come back with at least one track."""
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        b = pcbnew.BOARD()
        edge = pcbnew.PCB_SHAPE(b)
        edge.SetShape(pcbnew.SHAPE_T_RECT)
        edge.SetStart(pcbnew.VECTOR2I_MM(0, 0))
        edge.SetEnd(pcbnew.VECTOR2I_MM(30, 20))
        edge.SetLayer(pcbnew.Edge_Cuts)
        edge.SetWidth(pcbnew.FromMM(0.1))
        b.Add(edge)
        net = pcbnew.NETINFO_ITEM(b, "A")
        b.Add(net)
        for ref, x in (("R1", 8), ("R2", 22)):
            fp = pcbnew.FootprintLoad(libs.footprint_path("Resistor_SMD:R_0805_2012Metric"),
                                      "R_0805_2012Metric")
            fp.SetReference(ref)
            fp.SetPosition(pcbnew.VECTOR2I_MM(x, 10))
            b.Add(fp)
            list(fp.Pads())[0].SetNet(net)
        pcb = os.path.join(d, "t.kicad_pcb")
        pcbnew.SaveBoard(pcb, b)
        self.assertGreaterEqual(route.route(pcb, passes=5), 1)
