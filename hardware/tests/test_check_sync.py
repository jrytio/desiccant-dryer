# hardware/tests/test_check_sync.py
import os, shutil, tempfile, unittest
from unittest import mock
from dryer_board import check_sync, project, schematic, board, circuit, placement


class CheckSync(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp()
        project.write(cls.dir); schematic.write_lib_tables(cls.dir); schematic.write(cls.dir)
        cls.pcb = os.path.join(cls.dir, circuit.PROJECT + ".kicad_pcb")
        board.build(cls.pcb, fresh=True)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir, ignore_errors=True)

    def setUp(self):
        # each test mutates its own copy of the generated project
        self.work = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.work, True)
        for name in os.listdir(self.dir):
            src = os.path.join(self.dir, name)
            if os.path.isfile(src):
                shutil.copy(src, self.work)
        self.wpcb = os.path.join(self.work, circuit.PROJECT + ".kicad_pcb")

    def test_fresh_output_is_in_sync(self):
        self.assertEqual(check_sync.all_diffs(self.work), [])

    def test_check_leaves_the_project_directory_clean(self):
        before = sorted(os.listdir(self.work))
        check_sync.all_diffs(self.work)
        self.assertEqual(sorted(os.listdir(self.work)), before)

    def test_moved_part_is_reported(self):
        moved = dict(placement.PLACE); moved["R1"] = (20, 20, 0)
        with mock.patch.object(placement, "PLACE", moved):
            diffs = check_sync.board_diffs(self.wpcb)
        self.assertTrue(any("R1" in d for d in diffs), diffs)

    def test_edited_rules_are_reported(self):
        with open(os.path.join(self.work, circuit.PROJECT + ".kicad_dru"), "a", encoding="utf-8") as f:
            f.write("\n; edited by hand\n")
        self.assertTrue(any("kicad_dru" in d for d in check_sync.all_diffs(self.work)))

    def test_renetted_pad_is_reported(self):
        import pcbnew
        b = pcbnew.LoadBoard(self.wpcb)
        fp = b.FindFootprintByReference("R1")
        list(fp.Pads())[0].SetNet(b.FindNet("GND")); pcbnew.SaveBoard(self.wpcb, b)
        self.assertTrue(any("R1" in d and "pad" in d for d in check_sync.board_diffs(self.wpcb)))

    def test_removed_mains_segment_is_reported(self):
        import pcbnew
        b = pcbnew.LoadBoard(self.wpcb)
        victim = [t for t in b.GetTracks() if t.GetNetname() in circuit.MAINS_NETS][0]
        b.Delete(victim); pcbnew.SaveBoard(self.wpcb, b)
        diffs = check_sync.board_diffs(self.wpcb)
        self.assertTrue(any("mains" in d and "missing" in d for d in diffs), diffs)

    def test_unlocked_or_narrow_mains_track_is_reported(self):
        import pcbnew
        b = pcbnew.LoadBoard(self.wpcb)
        t = [t for t in b.GetTracks() if t.GetNetname() in circuit.MAINS_NETS][0]
        t.SetLocked(False); t.SetWidth(pcbnew.FromMM(0.5)); pcbnew.SaveBoard(self.wpcb, b)
        diffs = check_sync.board_diffs(self.wpcb)
        self.assertTrue(any("unlocked" in d for d in diffs), diffs)
        self.assertTrue(any("width" in d for d in diffs), diffs)

    def test_via_on_mains_net_is_reported(self):
        import pcbnew
        b = pcbnew.LoadBoard(self.wpcb)
        v = pcbnew.PCB_VIA(b); v.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(91), pcbnew.FromMM(40)))
        v.SetWidth(pcbnew.FromMM(0.6)); v.SetDrill(pcbnew.FromMM(0.3))
        v.SetNet(b.FindNet("N")); b.Add(v); pcbnew.SaveBoard(self.wpcb, b)
        self.assertTrue(any("via" in d for d in check_sync.board_diffs(self.wpcb)))


    def test_shifted_relay_area_is_reported(self):
        import pcbnew
        b = pcbnew.LoadBoard(self.wpcb)
        z = [z for z in b.Zones() if z.GetIsRuleArea() and z.GetZoneName() == "relay_pads"][0]
        z.Move(pcbnew.VECTOR2I_MM(0, 2)); pcbnew.SaveBoard(self.wpcb, b)
        diffs = check_sync.board_diffs(self.wpcb)
        self.assertTrue(any("relay_pads" in d and "missing" in d for d in diffs), diffs)
        self.assertTrue(any("relay_pads" in d and "not in the model" in d for d in diffs), diffs)

    def test_rule_area_flag_change_is_reported(self):
        import pcbnew
        b = pcbnew.LoadBoard(self.wpcb)
        z = [z for z in b.Zones() if z.GetIsRuleArea() and z.GetZoneName() == "u1_keepout"][0]
        z.SetDoNotAllowTracks(False); pcbnew.SaveBoard(self.wpcb, b)
        diffs = check_sync.board_diffs(self.wpcb)
        self.assertTrue(any("u1_keepout" in d and "no tracks" in d for d in diffs), diffs)

    def test_deleted_slot_segment_is_reported(self):
        import pcbnew
        b = pcbnew.LoadBoard(self.wpcb)
        slot = [s for s in b.GetDrawings() if s.GetLayer() == pcbnew.Edge_Cuts and s.GetShape() == pcbnew.SHAPE_T_POLY][0]
        b.Delete(slot); pcbnew.SaveBoard(self.wpcb, b)
        diffs = check_sync.board_diffs(self.wpcb)
        self.assertTrue(any("Edge.Cuts" in d and "missing" in d for d in diffs), diffs)

    def test_resized_board_outline_is_reported(self):
        with mock.patch.object(placement, "BOARD_W", 111.0):
            diffs = check_sync.board_diffs(self.wpcb)
        self.assertTrue(any("Edge.Cuts" in d for d in diffs), diffs)

if __name__ == "__main__":
    unittest.main()
