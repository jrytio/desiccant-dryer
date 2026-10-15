import os, tempfile, unittest
from dryer_board import schematic, boards, kicad_env


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


class Schematic(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sch = {}
        for bd in boards.BOARDS:
            d = tempfile.mkdtemp()
            schematic.write_lib_tables(bd, d)
            cls.sch[bd] = schematic.write(bd, d)

    def test_deterministic(self):
        for bd, path in self.sch.items():
            a = _read(path)
            schematic.write(bd, os.path.dirname(path))
            self.assertEqual(a, _read(path), bd.SHORT)

    def test_boards_do_not_share_uuids(self):
        a, b = [_read(self.sch[bd]) for bd in boards.BOARDS]
        self.assertNotEqual(a.split("\n")[0], b.split("\n")[0])

    def test_kicad_sees_the_model_netlist(self):
        for bd, path in self.sch.items():
            got = schematic.netlist_from_kicad(path)
            want = {net: set(pads) for net, pads in bd.nets().items()}
            for net in want:
                want[net] = {(r, p) for r, p in want[net] if not r.startswith("#")}
            self.assertEqual(got, want, bd.SHORT)

    def test_erc_clean(self):
        for bd, path in self.sch.items():
            rpt = os.path.join(os.path.dirname(path), "erc.rpt")
            kicad_env.run_cli("sch", "erc", "--severity-all", "-o", rpt, path)
            text = _read(rpt)
            self.assertIn("** ERC messages: 0", text, bd.SHORT + "\n" + text)
