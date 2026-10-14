# hardware/tests/test_routed_board.py
"""The gate on the committed, routed board: DRC clean, fully routed, nothing in the antenna
keep-out, wide mains tracks, bare relay NC pads. CI never routes; these run on the file."""
import os, unittest
import pcbnew
from dryer_board import board, circuit, placement, kicad_env

PCB = os.path.join(kicad_env.PROJECT_DIR, circuit.PROJECT + ".kicad_pcb")


@unittest.skipUnless(os.path.exists(PCB), "no committed board yet")
class RoutedBoard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.b = pcbnew.LoadBoard(PCB)
        cls.report = board.drc_report(PCB)

    def test_drc_clean(self):
        bad = [l for l in self.report.splitlines() if l.startswith("[")]
        self.assertEqual(bad, [], "\n".join(bad))

    def test_fully_routed(self):
        self.assertIn("** Found 0 unconnected pads **", self.report)

    def test_no_copper_in_antenna_keepout(self):
        x1, y1, x2, y2 = placement.ANTENNA_KEEPOUT
        box = pcbnew.BOX2I(pcbnew.VECTOR2I_MM(x1, y1), pcbnew.VECTOR2I_MM(x2 - x1, y2 - y1))
        for t in self.b.GetTracks():
            self.assertFalse(t.GetBoundingBox().Intersects(box), "track in the antenna keep-out at %s" % t.GetStart())
        for z in self.b.Zones():
            if z.GetIsRuleArea():
                continue
            for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
                # GetFilledPolysList asserts and aborts on a layer the zone is not on.
                if not z.IsOnLayer(layer):
                    continue
                fill = z.GetFilledPolysList(layer)
                self.assertFalse(fill.BBox().Intersects(box) and fill.Collide(box.Centre()), "pour inside the antenna keep-out")

    def test_mains_tracks_are_wide(self):
        for t in self.b.GetTracks():
            if t.GetNetname() in circuit.MAINS_NETS and t.GetClass() == "PCB_TRACK":
                self.assertGreaterEqual(t.GetWidth(), pcbnew.FromMM(1.5), t.GetNetname())

    def test_nc_pads_bare(self):
        for ref in ("K1", "K2"):
            fp = self.b.FindFootprintByReference(ref)
            pad4 = [p for p in fp.Pads() if p.GetNumber() == "4"][0]
            self.assertEqual(pad4.GetNetCode(), 0)
            for t in self.b.GetTracks():
                self.assertFalse(t.HitTest(pad4.GetPosition()), "%s NC pad has a track" % ref)
