# hardware/tests/test_check_sync.py
import os, shutil, tempfile, unittest
from unittest import mock
from dryer_board import check_sync, project, schematic, board, mains, controller, kicad_env


def _generate(bd):
    d = tempfile.mkdtemp()
    project.write(bd, d); schematic.write_lib_tables(bd, d); schematic.write(bd, d)
    board.build(bd, os.path.join(d, bd.PROJECT + ".kicad_pcb"), fresh=True)
    return d


class CheckSync(unittest.TestCase):
    """On the mains board, which has everything the check compares (mains copper, slot,
    relay areas); the controller gets the in-sync test only."""
    @classmethod
    def setUpClass(cls):
        cls.dir = _generate(mains)
        cls.pcb = os.path.join(cls.dir, mains.PROJECT + ".kicad_pcb")

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
        shutil.copytree(os.path.join(self.dir, "lib"), os.path.join(self.work, "lib"))
        self.wpcb = os.path.join(self.work, mains.PROJECT + ".kicad_pcb")

    def test_fresh_output_is_in_sync(self):
        self.assertEqual(check_sync.all_diffs(mains, self.work), [])

    def test_fresh_controller_is_in_sync(self):
        d = _generate(controller)
        self.addCleanup(shutil.rmtree, d, True)
        self.assertEqual(check_sync.all_diffs(controller, d), [])

    def test_check_leaves_the_project_directory_clean(self):
        before = sorted(os.listdir(self.work))
        check_sync.all_diffs(mains, self.work)
        self.assertEqual(sorted(os.listdir(self.work)), before)

    def test_moved_part_is_reported(self):
        moved = dict(mains.PLACE); moved["R2"] = (10, 10, 0)
        with mock.patch.object(mains, "PLACE", moved):
            diffs = check_sync.board_diffs(mains, self.wpcb)
        self.assertTrue(any("R2" in d for d in diffs), diffs)

    def test_edited_rules_are_reported(self):
        with open(os.path.join(self.work, mains.PROJECT + ".kicad_dru"), "a", encoding="utf-8") as f:
            f.write("\n; edited by hand\n")
        self.assertTrue(any("kicad_dru" in d for d in check_sync.all_diffs(mains, self.work)))

    def test_edited_footprint_copy_is_reported(self):
        name = os.path.basename(mains.by_ref("F1").footprint.split(":")[1]) + ".kicad_mod"
        with open(os.path.join(self.work, "lib", "dryer.pretty", name), "a", encoding="utf-8") as f:
            f.write("\n; edited by hand\n")
        self.assertTrue(any(name in d for d in check_sync.lib_diffs(self.work)))

    def test_renetted_pad_is_reported(self):
        import pcbnew
        b = pcbnew.LoadBoard(self.wpcb)
        fp = b.FindFootprintByReference("R2")
        list(fp.Pads())[0].SetNet(b.FindNet("+5V")); pcbnew.SaveBoard(self.wpcb, b)
        self.assertTrue(any("R2" in d and "pad" in d for d in check_sync.board_diffs(mains, self.wpcb)))

    def test_removed_mains_segment_is_reported(self):
        import pcbnew
        b = pcbnew.LoadBoard(self.wpcb)
        victim = [t for t in b.GetTracks() if t.GetNetname() in mains.MAINS_NETS][0]
        b.Delete(victim); pcbnew.SaveBoard(self.wpcb, b)
        diffs = check_sync.board_diffs(mains, self.wpcb)
        self.assertTrue(any("mains" in d and "missing" in d for d in diffs), diffs)

    def test_unlocked_or_narrow_mains_track_is_reported(self):
        import pcbnew
        b = pcbnew.LoadBoard(self.wpcb)
        t = [t for t in b.GetTracks() if t.GetNetname() in mains.MAINS_NETS][0]
        t.SetLocked(False); t.SetWidth(pcbnew.FromMM(0.5)); pcbnew.SaveBoard(self.wpcb, b)
        diffs = check_sync.board_diffs(mains, self.wpcb)
        self.assertTrue(any("unlocked" in d for d in diffs), diffs)
        self.assertTrue(any("width" in d for d in diffs), diffs)

    def test_via_on_mains_net_is_reported(self):
        import pcbnew
        b = pcbnew.LoadBoard(self.wpcb)
        v = pcbnew.PCB_VIA(b); v.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(45), pcbnew.FromMM(45)))
        v.SetWidth(pcbnew.FromMM(0.6)); v.SetDrill(pcbnew.FromMM(0.3))
        v.SetNet(b.FindNet("N")); b.Add(v); pcbnew.SaveBoard(self.wpcb, b)
        self.assertTrue(any("via" in d for d in check_sync.board_diffs(mains, self.wpcb)))

    def test_shifted_relay_area_is_reported(self):
        import pcbnew
        b = pcbnew.LoadBoard(self.wpcb)
        z = [z for z in b.Zones() if z.GetIsRuleArea() and z.GetZoneName() == "relay_pads"][0]
        z.Move(pcbnew.VECTOR2I_MM(0, 2)); pcbnew.SaveBoard(self.wpcb, b)
        diffs = check_sync.board_diffs(mains, self.wpcb)
        self.assertTrue(any("relay_pads" in d and "missing" in d for d in diffs), diffs)
        self.assertTrue(any("relay_pads" in d and "not in the model" in d for d in diffs), diffs)

    def test_rule_area_flag_change_is_reported(self):
        import pcbnew
        b = pcbnew.LoadBoard(self.wpcb)
        z = [z for z in b.Zones() if z.GetIsRuleArea() and z.GetZoneName() == "mains_nopour"][0]
        z.SetDoNotAllowTracks(True); pcbnew.SaveBoard(self.wpcb, b)
        diffs = check_sync.board_diffs(mains, self.wpcb)
        self.assertTrue(any("mains_nopour" in d and "no tracks" in d for d in diffs), diffs)

    def test_deleted_slot_segment_is_reported(self):
        import pcbnew
        b = pcbnew.LoadBoard(self.wpcb)
        slot = [s for s in b.GetDrawings() if s.GetLayer() == pcbnew.Edge_Cuts and s.GetShape() == pcbnew.SHAPE_T_POLY][0]
        b.Delete(slot); pcbnew.SaveBoard(self.wpcb, b)
        diffs = check_sync.board_diffs(mains, self.wpcb)
        self.assertTrue(any("Edge.Cuts" in d and "missing" in d for d in diffs), diffs)

    def test_resized_board_outline_is_reported(self):
        with mock.patch.object(mains, "BOARD_W", 65.0):
            diffs = check_sync.board_diffs(mains, self.wpcb)
        self.assertTrue(any("Edge.Cuts" in d for d in diffs), diffs)

if __name__ == "__main__":
    unittest.main()
