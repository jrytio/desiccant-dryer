# hardware/tests/test_schematic.py
import os, tempfile, unittest
from dryer_board import schematic, circuit, kicad_env


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


class Schematic(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp()
        schematic.write_lib_tables(cls.dir)
        cls.sch = schematic.write(cls.dir)

    def test_deterministic(self):
        a = _read(self.sch)
        schematic.write(self.dir)
        self.assertEqual(a, _read(self.sch))

    def test_kicad_sees_the_model_netlist(self):
        got = schematic.netlist_from_kicad(self.sch)
        want = {net: set(pads) for net, pads in circuit.nets().items()}
        for net in want:
            want[net] = {(r, p) for r, p in want[net] if not r.startswith("#")}
        self.assertEqual(got, want)

    def test_erc_clean(self):
        rpt = os.path.join(self.dir, "erc.rpt")
        kicad_env.run_cli("sch", "erc", "--severity-all", "-o", rpt, self.sch)
        text = _read(rpt)
        self.assertIn("** ERC messages: 0", text, text)
