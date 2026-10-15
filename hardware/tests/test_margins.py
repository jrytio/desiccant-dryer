# hardware/tests/test_margins.py
"""Minimum copper distances on the committed mains board, measured with pcbnew's shape
collision at 1 um and printed so a bare pass is visible: mains to SELV outside the relay areas
(>= 6.0), mains copper to each hole edge (>= 6.0), L-side mains nets to each other (>= 1.6).
The relay NC pads (K1/K2 pad 4, netless but live) count as mains at the full 6.0 everywhere.
Layers are compared only where both items have copper, and "inside a relay area" is the real
copper outline against the area, as DRC judges it."""
import os, unittest
import pcbnew
from dryer_board import boards, kicad_env, route
from tests.test_routed_board import _gap

bd = boards.by_name("mains")
PCB = os.path.join(kicad_env.project_dir(bd), bd.PROJECT + ".kicad_pcb")
LAYERS = (pcbnew.F_Cu, pcbnew.B_Cu)


def _layer_gaps(a, b):
    """Gap in mm on each copper layer both items are on."""
    return [_gap(a.GetEffectiveShape(l), b.GetEffectiveShape(l))
            for l in LAYERS if a.IsOnLayer(l) and b.IsOnLayer(l)]


@unittest.skipUnless(os.path.exists(PCB), "no committed mains board")
class Margins(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.b = pcbnew.LoadBoard(PCB)
        pads = [p for fp in cls.b.GetFootprints() for p in fp.Pads()]
        cls.nc = [p for fp in cls.b.GetFootprints() if fp.GetReference() in ("K1", "K2")
                  for p in fp.Pads() if p.GetNumber() == "4"]
        items = list(cls.b.GetTracks()) + pads
        cls.mains = [i for i in items if i.GetNetname() in bd.MAINS_NETS] + cls.nc
        cls.selv = [i for i in items if i.GetNetname() and i.GetNetname() not in bd.MAINS_NETS]
        cls.holes = [(fp.GetReference(), p) for fp in cls.b.GetFootprints() if fp.GetReference().startswith("H") for p in fp.Pads()]
        cls.areas = route.relay_area_polys(bd)

    def test_mains_to_selv_outside_relay_areas(self):
        found = []
        for m in self.mains:
            for l in LAYERS:
                if not m.IsOnLayer(l) or (m not in self.nc and route.in_relay_area(m, l, self.areas)):
                    continue
                for s in self.selv:
                    if s.IsOnLayer(l):
                        found.append((_gap(m.GetEffectiveShape(l), s.GetEffectiveShape(l)),
                                      m.GetNetname() or "NC", s.GetNetname()))
        worst = min(found)
        print("\nmains to SELV outside relay areas: %.3f mm (%s vs %s)" % worst)
        self.assertGreaterEqual(worst[0], 6.0)

    def test_mains_to_holes(self):
        for ref, h in self.holes:
            hole = h.GetEffectiveHoleShape()
            worst = min(_gap(m.GetEffectiveShape(l), hole)
                        for m in self.mains for l in LAYERS if m.IsOnLayer(l))
            print("mains to hole %s: %.3f mm" % (ref, worst))
            self.assertGreaterEqual(worst, 6.0)

    def test_l_side_nets_apart(self):
        l_side = [i for i in self.mains if i.GetNetname() not in ("N", "")]
        found = [(g, a.GetNetname(), c.GetNetname()) for a in l_side for c in l_side
                 if a.GetNetname() < c.GetNetname() for g in _layer_gaps(a, c)]
        worst = min(found)
        print("L-side mains nets apart: %.3f mm (%s vs %s)" % worst)
        self.assertGreaterEqual(worst[0], 1.6)
