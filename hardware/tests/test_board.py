import os, tempfile, unittest
import pcbnew
from dryer_board import board, placement, circuit, project, schematic


class Board(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp()
        project.write(cls.dir)
        schematic.write_lib_tables(cls.dir)
        schematic.write(cls.dir)
        cls.pcb = os.path.join(cls.dir, circuit.PROJECT + ".kicad_pcb")
        cls.b = board.build(cls.pcb, fresh=True)

    def test_every_board_part_placed_once(self):
        refs = sorted(f.GetReference() for f in self.b.GetFootprints())
        self.assertEqual(refs, sorted(p.ref for p in circuit.board_parts()))
        self.assertEqual(set(placement.PLACE), set(p.ref for p in circuit.board_parts()))

    def test_pad_nets_match_model(self):
        for part in circuit.board_parts():
            fp = self.b.FindFootprintByReference(part.ref)
            for pad in fp.Pads():
                want = part.pins.get(pad.GetNumber(), circuit.NC)
                got = pad.GetNetname()
                self.assertEqual(got, "" if want == circuit.NC else want, "%s pad %s" % (part.ref, pad.GetNumber()))

    def test_mains_netclass_resolution(self):
        for i in range(1, self.b.GetNetCount()):
            net = self.b.GetNetInfo().GetNetItem(i)
            is_mains = net.GetNetname() in circuit.MAINS_NETS
            self.assertEqual(net.GetNetClassName() == "MAINS", is_mains, net.GetNetname())

    def test_geometry(self):
        bb = self.b.GetBoardEdgesBoundingBox()
        self.assertAlmostEqual(bb.GetWidth() / 1e6, placement.BOARD_W, delta=0.2)
        self.assertAlmostEqual(bb.GetHeight() / 1e6, placement.BOARD_H, delta=0.2)
        names = sorted(z.GetZoneName() for z in self.b.Zones() if z.GetIsRuleArea())
        self.assertEqual(names, ["antenna_keepout", "mains_nopour", "relay_pads", "relay_pads"])
        pours = [z for z in self.b.Zones() if not z.GetIsRuleArea()]
        self.assertEqual(sorted(z.GetNetname() for z in pours), ["GND", "GND"])

    def test_mains_parts_in_mains_zone(self):
        x0 = placement.MAINS_ZONE[0]
        for ref in ("J_MAINS", "F1"):
            self.assertGreater(placement.PLACE[ref][0], x0, ref)
        for part in circuit.board_parts():
            # The mounting holes sit in both zones.
            if part.ref in ("J_MAINS", "F1", "K1", "K2") or part.ref.startswith("H"):
                continue
            self.assertLess(placement.PLACE[part.ref][0], placement.SLOT_X[0] - 1, part.ref)

    def test_unrouted_drc_has_only_unconnected_items(self):
        text = board.drc_report(self.pcb)
        bad = [l for l in text.splitlines() if l.startswith("[") and not l.startswith("[unconnected_items]")]
        self.assertEqual(bad, [], "\n".join(bad) + "\n\n" + text)

    def test_drc_report_raises_when_drc_cannot_run(self):
        missing = os.path.join(self.dir, "missing.kicad_pcb")
        # A stale report must not be returned in place of a failed run.
        with open(missing + ".drc.rpt", "w", encoding="utf-8") as f:
            f.write("** Found 0 DRC violations **\n")
        with self.assertRaises(RuntimeError):
            board.drc_report(missing)

    def test_dsn_carries_netclasses_and_keepouts(self):
        dsn = os.path.join(self.dir, "t.dsn")
        board.export_dsn(self.b, dsn)
        with open(dsn, encoding="utf-8") as f:
            text = f.read()
        self.assertIn("(class MAINS", text)
        self.assertIn("(width 1500)", text)
        self.assertGreaterEqual(text.count("(keepout"), 4)

    def test_rebuild_keeps_tracks(self):
        gnd = self.b.FindNet("GND")
        t = pcbnew.PCB_TRACK(self.b)
        t.SetStart(pcbnew.VECTOR2I_MM(40, 40))
        t.SetEnd(pcbnew.VECTOR2I_MM(45, 40))
        t.SetWidth(pcbnew.FromMM(0.3))
        t.SetLayer(pcbnew.F_Cu)
        t.SetNet(gnd)
        self.b.Add(t)
        pcbnew.SaveBoard(self.pcb, self.b)
        def routed(b):
            return [x for x in b.GetTracks() if x.GetNetname() not in circuit.MAINS_NETS]
        b2 = board.build(self.pcb, fresh=False)
        self.assertEqual(len(routed(b2)), 1)
        b3 = board.build(self.pcb, fresh=True)
        self.assertEqual(len(routed(b3)), 0)

    def test_mains_copper_is_laid_and_locked(self):
        mains = [t for t in self.b.GetTracks() if t.GetNetname() in circuit.MAINS_NETS]
        self.assertEqual(len(mains), sum(len(pts) - 1 for _n, _l, pts in placement.MAINS_TRACKS))
        for t in mains:
            self.assertTrue(t.IsLocked(), t.GetNetname())
            self.assertEqual(t.GetWidth(), pcbnew.FromMM(1.5), t.GetNetname())


    def test_mains_segments_do_not_carry_the_relay_relaxation_out_of_the_areas(self):
        # insideArea relaxes a whole segment to 3.5 mm if any of it touches a relay area, so a
        # segment that touches one must stay within a cap's reach of it (placement says why).
        half = circuit.NETCLASSES["MAINS"][0] / 2
        def touches(p, q, r):
            x1, y1, x2, y2 = r
            for i in range(101):
                x, y = p[0] + (q[0] - p[0]) * i / 100, p[1] + (q[1] - p[1]) * i / 100
                dx, dy = max(x1 - x, 0, x - x2), max(y1 - y, 0, y - y2)
                if dx * dx + dy * dy < half * half:
                    return True
            return False
        for net, layer, pts in placement.MAINS_TRACKS:
            for p, q in zip(pts, pts[1:]):
                for r in placement.RELAY_AREAS:
                    if touches(p, q, r):
                        g = 2 * half + 0.5
                        for x, y in (p, q):
                            self.assertTrue(r[0] - g <= x <= r[2] + g and r[1] - g <= y <= r[3] + g,
                                            "%s %s segment %s-%s runs out of relay area %s" % (net, layer, p, q, r))

class DanglingVias(unittest.TestCase):
    def _track(self, b, net, layer, x1, x2):
        t = pcbnew.PCB_TRACK(b)
        t.SetStart(pcbnew.VECTOR2I_MM(x1, 10)); t.SetEnd(pcbnew.VECTOR2I_MM(x2, 10))
        t.SetWidth(pcbnew.FromMM(0.3)); t.SetLayer(layer); t.SetNet(net); b.Add(t)

    def test_only_vias_joined_on_both_layers_survive(self):
        b = pcbnew.BOARD()
        net = pcbnew.NETINFO_ITEM(b, "A"); b.Add(net)
        for x in (10, 20, 30):
            v = pcbnew.PCB_VIA(b); v.SetPosition(pcbnew.VECTOR2I_MM(x, 10)); v.SetNet(net)
            v.SetWidth(pcbnew.FromMM(0.6)); v.SetDrill(pcbnew.FromMM(0.3)); b.Add(v)
        self._track(b, net, pcbnew.F_Cu, 5, 10)    # via at 10: F.Cu only
        self._track(b, net, pcbnew.F_Cu, 15, 20)   # via at 20: both layers
        self._track(b, net, pcbnew.B_Cu, 20, 25)
        self.assertEqual(board.remove_dangling_vias(b), 2)
        left = [v.GetPosition() for v in b.GetTracks() if v.GetClass() == "PCB_VIA"]
        self.assertEqual(left, [pcbnew.VECTOR2I_MM(20, 10)])
