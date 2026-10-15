"""The gate on the committed, routed boards: DRC clean, fully routed, nothing in the antenna
keep-out or under U1 (controller), wide mains tracks and bare relay NC pads (mains). CI never
routes; these run on the files."""
import gc, os, shutil, tempfile, types, unittest
import pcbnew
from dryer_board import board, boards, controller, mains, kicad_env, route

PCBS = {bd: os.path.join(kicad_env.project_dir(bd), bd.PROJECT + ".kicad_pcb") for bd in boards.BOARDS}


_rect_poly = route.rect_poly
_copper_in = route.copper_in_area


def _gap(a, b, cap=40.0):
    """Edge-to-edge distance in mm between two pcbnew SHAPEs, by bisection on Collide with a
    clearance, to 1 um."""
    lo, hi = 0.0, cap
    while hi - lo > 0.001:
        mid = (lo + hi) / 2
        if a.Collide(b, pcbnew.FromMM(mid)):
            hi = mid
        else:
            lo = mid
    return lo


def pour_to_mains_shortfalls(b, bd):
    """Every (filled polygon of a GND pour, mains track or pad) pair on a layer that sits closer
    than the rules allow in the saved fill: 6 mm, or 3.5 mm where the mains item's copper touches a
    relay area (never for the NC pads) (the relay_pads rule tests the mains item, A). Returns [(gap, floor, description)]."""
    areas = route.relay_area_polys(bd)
    items = [t for t in b.GetTracks() if t.GetNetname() in bd.MAINS_NETS]
    items += [p for fp in b.GetFootprints() for p in fp.Pads() if p.GetNetname() in bd.MAINS_NETS]
    # The relay NC pads are netless but live: 6 mm everywhere, never the relay-area 3.5.
    nc = [p for ref in ("K1", "K2") if b.FindFootprintByReference(ref) is not None
          for p in b.FindFootprintByReference(ref).Pads() if p.GetNumber() == "4"]
    items += nc
    out = []
    for z in b.Zones():
        if z.GetIsRuleArea() or z.GetNetname() != "GND":
            continue
        for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
            if not z.IsOnLayer(layer):
                continue
            fill = z.GetFilledPolysList(layer)
            for i in range(fill.OutlineCount()):
                poly = fill.UnitSet(i)
                for it in items:
                    if not it.IsOnLayer(layer):
                        continue
                    shape = it.GetEffectiveShape(layer)
                    floor = 3.5 if it not in nc and route.in_relay_area(it, layer, areas) else 6.0
                    gap = _gap(poly, shape)
                    if gap < floor:
                        out.append((gap, floor, "%s fill %d on %s to %s %s at %s" % (
                            z.GetZoneName(), i, b.GetLayerName(layer), it.GetClass(), it.GetNetname(),
                            it.GetPosition())))
    return out


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

    def test_saved_pour_fill_keeps_the_mains_rules(self):
        # The saved fill, not DRC's own refill: the gerbers are plotted from the file.
        short = pour_to_mains_shortfalls(self.b[mains], mains)
        self.assertEqual(short, [], "\n".join("%.3f < %.1f: %s" % s for s in short))


class SavedFill(unittest.TestCase):
    def test_build_saves_a_rules_aware_fill(self):
        """A pour drawn to within 4 mm of F1's pad 1 (mains, outside the relay areas) must come
        out of board.build pulled back to 6 mm in the saved file: the pcbnew filler sees only
        the zone's own 0.3 mm clearance, the project's rules come from the refill after it."""
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        bd = types.SimpleNamespace(**{k: getattr(mains, k) for k in dir(mains) if not k.startswith("__")})
        bd.GND_POUR = (2.0, 2.0, 6.5, 68.0)
        pcb = os.path.join(d, bd.PROJECT + ".kicad_pcb")
        b = board.build(bd, pcb, fresh=True)
        del b
        gc.collect()
        short = pour_to_mains_shortfalls(pcbnew.LoadBoard(pcb), bd)
        self.assertEqual(short, [], "\n".join("%.3f < %.1f: %s" % s for s in short))
