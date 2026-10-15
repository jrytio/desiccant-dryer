"""The gate on the committed, routed boards: DRC clean, fully routed, nothing in the antenna
keep-out or under U1 (controller), wide mains tracks and bare relay NC pads (mains). CI never
routes; these run on the files."""
import os, unittest
import pcbnew
from dryer_board import board, boards, controller, mains, kicad_env

PCBS = {bd: os.path.join(kicad_env.project_dir(bd), bd.PROJECT + ".kicad_pcb") for bd in boards.BOARDS}


def _rect_poly(x1, y1, x2, y2):
    area = pcbnew.SHAPE_POLY_SET(); area.NewOutline()
    for x, y in ((x1, y1), (x2, y1), (x2, y2), (x1, y2)):
        area.Append(pcbnew.VECTOR2I_MM(x, y))
    return area


def _copper_in(track, layer, area):
    """True if any of the track's (or via's) copper on this layer lies inside the area."""
    poly = pcbnew.SHAPE_POLY_SET()
    track.TransformShapeToPolygon(poly, layer, 0, pcbnew.FromMM(0.005), pcbnew.ERROR_INSIDE)
    poly.BooleanIntersection(area)
    return poly.OutlineCount() != 0


@unittest.skipUnless(all(os.path.exists(p) for p in PCBS.values()), "no committed boards yet")
class RoutedBoard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.b = {bd: pcbnew.LoadBoard(p) for bd, p in PCBS.items()}
        cls.report = {bd: board.drc_report(p) for bd, p in PCBS.items()}

    def test_drc_clean(self):
        for bd, report in self.report.items():
            bad = [l for l in report.splitlines() if l.startswith("[")]
            self.assertEqual(bad, [], bd.SHORT + "\n" + "\n".join(bad))

    def test_fully_routed(self):
        for bd, report in self.report.items():
            self.assertIn("** Found 0 unconnected pads **", report, bd.SHORT)

    def test_no_copper_in_antenna_keepout(self):
        # Exact copper outlines against the rectangle (a diagonal track past the keep-out's
        # corner has a bounding box that overlaps it without any copper inside), as for U1.
        b = self.b[controller]
        x1, y1, x2, y2 = controller.ANTENNA_KEEPOUT
        area = _rect_poly(x1, y1, x2, y2)
        for t in b.GetTracks():
            for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
                if t.IsOnLayer(layer):
                    self.assertFalse(_copper_in(t, layer, area), "%s %s in the antenna keep-out at %s on %s" % (
                        t.GetClass(), t.GetNetname(), t.GetStart(), b.GetLayerName(layer)))
        box = pcbnew.BOX2I(pcbnew.VECTOR2I_MM(x1, y1), pcbnew.VECTOR2I_MM(x2 - x1, y2 - y1))
        for z in b.Zones():
            if z.GetIsRuleArea():
                continue
            for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
                # GetFilledPolysList asserts and aborts on a layer the zone is not on.
                if not z.IsOnLayer(layer):
                    continue
                fill = z.GetFilledPolysList(layer)
                self.assertFalse(fill.BBox().Intersects(box) and fill.Collide(box.Centre()), "pour inside the antenna keep-out")

    def test_nothing_routed_under_u1(self):
        # Exact copper outline against the rectangle, on both layers: a track that only ends at
        # a pad's centre from below still reaches up into it by half its width.
        b = self.b[controller]
        area = _rect_poly(*controller.U1_KEEPOUT)
        for t in b.GetTracks():
            for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
                if t.IsOnLayer(layer):
                    self.assertFalse(_copper_in(t, layer, area), "%s %s under U1 at %s on %s" % (
                        t.GetClass(), t.GetNetname(), t.GetStart(), b.GetLayerName(layer)))

    def test_mains_tracks_are_wide(self):
        for t in self.b[mains].GetTracks():
            if t.GetNetname() in mains.MAINS_NETS and t.GetClass() == "PCB_TRACK":
                self.assertGreaterEqual(t.GetWidth(), pcbnew.FromMM(1.5), t.GetNetname())

    def test_nc_pads_bare(self):
        b = self.b[mains]
        for ref in ("K1", "K2"):
            fp = b.FindFootprintByReference(ref)
            pad4 = [p for p in fp.Pads() if p.GetNumber() == "4"][0]
            self.assertEqual(pad4.GetNetCode(), 0)
            for t in b.GetTracks():
                self.assertFalse(t.HitTest(pad4.GetPosition()), "%s NC pad has a track" % ref)

    def test_controller_carries_no_mains(self):
        b = self.b[controller]
        for n in mains.MAINS_NETS:
            self.assertIsNone(b.FindNet(n), n)
