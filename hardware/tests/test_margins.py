# hardware/tests/test_margins.py
"""Minimum copper distances on the committed mains board, measured with pcbnew's shape
collision at 1 um and printed so a bare pass is visible: mains to SELV outside the relay areas
(>= 6.0), mains copper to each hole edge (>= 6.0), L-side mains nets to each other (>= 1.6),
mains copper to the board edge and slot (>= 1.0), SELV copper to the relay COM pads (>= 3.5, the
relay-area rule) and J_CTRL to them (>= 6.0). The GND pour fill is covered by
test_saved_pour_fill_keeps_the_mains_rules in test_routed_board.py, not here. The relay NC pads (K1/K2 pad 4, netless but live) count as mains at the full 6.0 everywhere, and as L-side nets (with the relay off the NC
contact sits at L while L_SW_x is pulled to N through the heater, so NC to any L-side net is an
L-to-L gap).
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
        cls.nc_ids = {id(p) for p in cls.nc}
        cls.label = {id(p): p.GetNetname() for p in cls.mains}
        for p in cls.nc:
            cls.label[id(p)] = "%s NC" % p.GetParentFootprint().GetReference()
        cls.areas = route.relay_area_polys(bd)

    def test_mains_to_selv_outside_relay_areas(self):
        found = []
        for m in self.mains:
            for l in LAYERS:
                if not m.IsOnLayer(l) or (id(m) not in self.nc_ids and route.in_relay_area(m, l, self.areas)):
                    continue
                for s in self.selv:
                    if s.IsOnLayer(l):
                        found.append((_gap(m.GetEffectiveShape(l), s.GetEffectiveShape(l)),
                                      m.GetNetname() or "NC", s.GetNetname()))
        worst = min(found)
        print("\nmains to SELV outside relay areas: %.3f mm (%s vs %s)" % worst)
        self.assertGreaterEqual(worst[0], 6.0)

    def test_selv_to_relay_com(self):
        com = [(fp.GetReference(), p) for fp in self.b.GetFootprints() if fp.GetReference() in ("K1", "K2")
               for p in fp.Pads() if p.GetNumber() == "1"]
        self.assertEqual(len(com), 2)
        # Strip copper: the part of each SELV item left of the slot (x < 7). A coil track is
        # one segment from the strip to its relay pad, so it is clipped at the slot's left edge;
        # the relays' own coil pads and the island ends of the coil tracks (4.05 to 4.15 mm
        # from COM, in the docs) are SELV islands in the mains zone, not the strip.
        edge = pcbnew.FromMM(bd.SLOT_X[0])
        found = []
        for ref, c in com:
            for s in self.selv:
                for l in LAYERS:
                    if not (s.IsOnLayer(l) and c.IsOnLayer(l)):
                        continue
                    poly = pcbnew.SHAPE_POLY_SET()
                    s.TransformShapeToPolygon(poly, l, 0, pcbnew.FromMM(0.005), pcbnew.ERROR_OUTSIDE)
                    box = pcbnew.SHAPE_POLY_SET()
                    box.NewOutline()
                    for x, y in ((-10 ** 8, -10 ** 8), (edge, -10 ** 8), (edge, 10 ** 9), (-10 ** 8, 10 ** 9)):
                        box.Append(x, y)
                    poly.BooleanIntersection(box)
                    if poly.OutlineCount():
                        found.append((_gap(poly, c.GetEffectiveShape(l)), s.GetNetname(), ref + " COM"))
        worst = min(found)
        print("\nSELV copper to relay COM: %.3f mm (%s to %s)" % worst)
        self.assertGreaterEqual(worst[0], 3.5)
        jctrl = [p for fp in self.b.GetFootprints() if fp.GetReference() == "J_CTRL" for p in fp.Pads()]
        self.assertTrue(jctrl)
        jworst = min((g, p.GetNetname() or "?", ref + " COM") for p in jctrl for ref, c in com
                     for g in _layer_gaps(p, c))
        print("J_CTRL pads to relay COM: %.3f mm (%s to %s)" % jworst)
        self.assertGreaterEqual(jworst[0], 6.0)

    def test_mains_to_holes(self):
        for ref, h in self.holes:
            hole = h.GetEffectiveHoleShape()
            worst = min(_gap(m.GetEffectiveShape(l), hole)
                        for m in self.mains for l in LAYERS if m.IsOnLayer(l))
            print("mains to hole %s: %.3f mm" % (ref, worst))
            self.assertGreaterEqual(worst, 6.0)

    def test_l_side_nets_apart(self):
        l_side = [i for i in self.mains if i.GetNetname() != "N"]
        found = []
        for n, a in enumerate(l_side):
            for c in l_side[n + 1:]:
                nc_pair = id(a) in self.nc_ids and id(c) in self.nc_ids
                if a.GetNetname() == c.GetNetname() and not nc_pair:
                    continue
                found += [(g, self.label[id(a)], self.label[id(c)]) for g in _layer_gaps(a, c)]
        worst = min(found)
        print("L-side mains nets apart: %.3f mm (%s vs %s)" % worst)
        self.assertGreaterEqual(worst[0], 1.6)

    def test_mains_to_board_edge(self):
        edges = [d for d in self.b.GetDrawings() if d.GetLayer() == pcbnew.Edge_Cuts]
        found = []
        for m in self.mains:
            for l in LAYERS:
                if m.IsOnLayer(l):
                    for e in edges:
                        found.append((_gap(m.GetEffectiveShape(l), e.GetEffectiveShape()),
                                      m.GetNetname() or "NC", m.GetClass()))
        worst = min(found)
        print("mains to board edge and slot: %.3f mm (%s %s)" % worst)
        self.assertGreaterEqual(worst[0], 1.0)
