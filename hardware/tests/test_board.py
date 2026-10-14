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
        b2 = board.build(self.pcb, fresh=False)
        self.assertEqual(len([x for x in b2.GetTracks()]), 1)
        b3 = board.build(self.pcb, fresh=True)
        self.assertEqual(len([x for x in b3.GetTracks()]), 0)
