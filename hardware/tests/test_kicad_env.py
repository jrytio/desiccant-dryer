import os, unittest
from dryer_board import kicad_env, boards

class KicadEnv(unittest.TestCase):
    def test_tools_exist(self):
        self.assertTrue(os.path.isfile(kicad_env.kicad_cli()))
        self.assertTrue(os.path.isfile(os.path.join(kicad_env.symbol_dir(), "Device.kicad_sym")))
        self.assertTrue(os.path.isdir(os.path.join(kicad_env.footprint_dir(), "Relay_THT.pretty")))

    def test_run_cli_version(self):
        out = kicad_env.run_cli("version").stdout
        self.assertRegex(out.strip(), r"^10\.")

    def test_paths(self):
        self.assertTrue(kicad_env.project_dir(boards.by_name("controller")).endswith("hardware/dryer-controller"))
        self.assertTrue(kicad_env.project_dir(boards.by_name("mains")).endswith("hardware/dryer-mains"))
        self.assertTrue(kicad_env.LIB_DIR.endswith("hardware/lib/dryer.pretty"))
        self.assertTrue(os.path.isdir(kicad_env.LIB_DIR))
        self.assertTrue(os.path.isfile(os.path.join(kicad_env.REPO, "CLAUDE.md")))
