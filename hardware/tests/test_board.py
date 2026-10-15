"""board.build on each board, in a scratch project. Only one generator-built BOARD may be alive
in a process: building a second one invalidates the first (pcbnew segfaults on the next access),
so setUpClass drops the built object and every test reloads its board from the saved file."""
import gc, os, tempfile, unittest
import pcbnew
from dryer_board import board, boards, controller, mains, parts, project, schematic


def _generate(bd):
    """Write and build a board in a fresh directory; return its .kicad_pcb path."""
    d = tempfile.mkdtemp()
    project.write(bd, d)
    schematic.write_lib_tables(bd, d)
    schematic.write(bd, d)
    pcb = os.path.join(d, bd.PROJECT + ".kicad_pcb")
    b = board.build(bd, pcb, fresh=True)
    del b
    gc.collect()
    return pcb


class Board(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pcb = {bd: _generate(bd) for bd in boards.BOARDS}

    def _load(self, bd):
        return pcbnew.LoadBoard(self.pcb[bd])

    def test_every_board_part_placed_once(self):
        for bd in boards.BOARDS:
            b = self._load(bd)
            refs = sorted(f.GetReference() for f in b.GetFootprints())
            self.assertEqual(refs, sorted(p.ref for p in bd.board_parts()), bd.SHORT)
            self.assertEqual(set(bd.PLACE), set(p.ref for p in bd.board_parts()), bd.SHORT)

    def test_pad_nets_match_model(self):
        for bd in boards.BOARDS:
            b = self._load(bd)
            for part in bd.board_parts():
                fp = b.FindFootprintByReference(part.ref)
                for pad in fp.Pads():
                    want = part.pins.get(pad.GetNumber(), parts.NC)
                    got = pad.GetNetname()
                    self.assertEqual(got, "" if want == parts.NC else want, "%s %s pad %s" % (bd.SHORT, part.ref, pad.GetNumber()))

    def test_mains_netclass_resolution(self):
        b = self._load(mains)
        for i in range(1, b.GetNetCount()):
            net = b.GetNetInfo().GetNetItem(i)
            is_mains = net.GetNetname() in mains.MAINS_NETS
            self.assertEqual(net.GetNetClassName() == "MAINS", is_mains, net.GetNetname())

    def test_geometry(self):
        names = {controller: ["antenna_keepout", "u1_keepout"], mains: ["mains_nopour", "relay_pads", "relay_pads"]}
        for bd in boards.BOARDS:
            b = self._load(bd)
            bb = b.GetBoardEdgesBoundingBox()
            self.assertAlmostEqual(bb.GetWidth() / 1e6, bd.BOARD_W, delta=0.2, msg=bd.SHORT)
            self.assertAlmostEqual(bb.GetHeight() / 1e6, bd.BOARD_H, delta=0.2, msg=bd.SHORT)
            self.assertEqual(sorted(z.GetZoneName() for z in b.Zones() if z.GetIsRuleArea()), names[bd], bd.SHORT)
            pours = [z for z in b.Zones() if not z.GetIsRuleArea()]
            self.assertEqual(sorted(z.GetNetname() for z in pours), ["GND", "GND"], bd.SHORT)

    def test_mains_parts_in_mains_zone(self):
        x0 = mains.MAINS_ZONE[0]
        for ref in ("J_MAINS", "F1"):
            self.assertGreater(mains.PLACE[ref][0], x0, ref)
        for part in mains.board_parts():
            # The mounting holes sit in both zones.
            if part.ref in mains.MAINS_PARTS or part.ref.startswith("H"):
                continue
            self.assertLess(mains.PLACE[part.ref][0], mains.SLOT_X[0] - 1, part.ref)

    def test_mounting_holes_at_the_corners(self):
        for bd in boards.BOARDS:
            for ref, (x, y) in bd.HOLES.items():
                self.assertEqual(bd.PLACE[ref][:2], (x, y), "%s %s" % (bd.SHORT, ref))
                self.assertIn(x, (4, bd.BOARD_W - 4), "%s %s" % (bd.SHORT, ref))
                self.assertIn(y, (4, bd.BOARD_H - 4), "%s %s" % (bd.SHORT, ref))

    def test_unrouted_drc_has_only_unconnected_items(self):
        for bd in boards.BOARDS:
            text = board.drc_report(self.pcb[bd])
            bad = [l for l in text.splitlines() if l.startswith("[") and not l.startswith("[unconnected_items]")]
            self.assertEqual(bad, [], bd.SHORT + "\n" + "\n".join(bad) + "\n\n" + text)

    def test_drc_report_raises_when_drc_cannot_run(self):
        missing = os.path.join(os.path.dirname(self.pcb[controller]), "missing.kicad_pcb")
        # A stale report must not be returned in place of a failed run.
        with open(missing + ".drc.rpt", "w", encoding="utf-8") as f:
            f.write("** Found 0 DRC violations **\n")
        with self.assertRaises(RuntimeError):
            board.drc_report(missing)

    def test_dsn_carries_netclasses_and_keepouts(self):
        b = self._load(mains)
        dsn = os.path.join(os.path.dirname(self.pcb[mains]), "t.dsn")
        board.export_dsn(b, dsn)
        with open(dsn, encoding="utf-8") as f:
            text = f.read()
        self.assertIn("(class MAINS", text)
        self.assertIn("(width 1500)", text)
        self.assertGreaterEqual(text.count("(keepout"), 3)

    def test_rebuild_keeps_tracks(self):
        pcb = self.pcb[controller]
        b = self._load(controller)
        gnd = b.FindNet("GND")
        t = pcbnew.PCB_TRACK(b)
        t.SetStart(pcbnew.VECTOR2I_MM(40, 40))
        t.SetEnd(pcbnew.VECTOR2I_MM(45, 40))
        t.SetWidth(pcbnew.FromMM(0.3))
        t.SetLayer(pcbnew.F_Cu)
        t.SetNet(gnd)
        b.Add(t)
        pcbnew.SaveBoard(pcb, b)
        del b
        gc.collect()
        b2 = board.build(controller, pcb, fresh=False)
        kept = len(list(b2.GetTracks()))
        del b2
        gc.collect()
        b3 = board.build(controller, pcb, fresh=True)
        fresh = len(list(b3.GetTracks()))
        del b3
        gc.collect()
        self.assertEqual((kept, fresh), (1, 0))

    def test_mains_copper_is_laid_and_locked(self):
        b = self._load(mains)
        laid = [t for t in b.GetTracks() if t.GetNetname() in mains.MAINS_NETS]
        self.assertEqual(len(laid), sum(len(pts) - 1 for _n, _l, pts in mains.MAINS_TRACKS))
        for t in laid:
            self.assertTrue(t.IsLocked(), t.GetNetname())
            self.assertEqual(t.GetWidth(), pcbnew.FromMM(1.5), t.GetNetname())
        self.assertEqual(list(self._load(controller).GetTracks()), [])

    def test_mains_segments_do_not_carry_the_relay_relaxation_out_of_the_areas(self):
        # insideArea relaxes a whole segment to 3.5 mm if any of it touches a relay area, so a
        # segment that touches one must stay within a cap's reach of it (mains.py says why).
        half = mains.NETCLASSES["MAINS"][0] / 2
        def touches(p, q, r):
            x1, y1, x2, y2 = r
            for i in range(101):
                x, y = p[0] + (q[0] - p[0]) * i / 100, p[1] + (q[1] - p[1]) * i / 100
                dx, dy = max(x1 - x, 0, x - x2), max(y1 - y, 0, y - y2)
                if dx * dx + dy * dy < half * half:
                    return True
            return False
        for net, layer, pts in mains.MAINS_TRACKS:
            for p, q in zip(pts, pts[1:]):
                for r in mains.RELAY_AREAS:
                    if touches(p, q, r):
                        g = 2 * half + 0.5
                        for x, y in (p, q):
                            self.assertTrue(r[0] - g <= x <= r[2] + g and r[1] - g <= y <= r[3] + g,
                                            "%s %s segment %s-%s runs out of relay area %s" % (net, layer, p, q, r))

    def test_mains_tracks_start_and_end_on_their_pads(self):
        """Every mains polyline end lies on a pad of its net or joins another segment (the
        hand-laid copper connects)."""
        b = self._load(mains)
        for net, _layer, pts in mains.MAINS_TRACKS:
            for x, y in (pts[0], pts[-1]):
                pos = pcbnew.VECTOR2I_MM(x, y)
                hit = [fp.GetReference() for fp in b.GetFootprints() for pad in fp.Pads()
                       if pad.GetNetname() == net and pad.HitTest(pos)]
                # A stub may end on the interior of another segment (the COM stubs meet the spine
                # mid-length), so count every same-net segment whose copper covers the point.
                joined = sum(1 for t in b.GetTracks() if t.GetClass() == "PCB_TRACK" and t.GetNetname() == net
                             and t.HitTest(pos))
                self.assertTrue(hit or joined > 1, "%s polyline end (%s, %s) is on no pad or other segment" % (net, x, y))


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
