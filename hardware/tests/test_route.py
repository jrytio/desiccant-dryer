import os, shutil, tempfile, types, unittest
import pcbnew
from dryer_board import route, libs, controller


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
        # A stand-in board definition: the whole outline is routable.
        bd = types.SimpleNamespace(PROJECT="t", REVISION="A", RULES="(version 1)\n", NETCLASSES=controller.NETCLASSES,
                                   MAINS_NETS=[], MAINS_TRACKS=[], GND_POUR=(0, 0, 30, 20), BOARD_W=30, BOARD_H=20)
        self.assertGreaterEqual(route.route(bd, pcb, passes=5), 1)
