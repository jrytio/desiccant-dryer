# hardware/dryer_board/cli.py
"""python -m dryer_board <command>. Commands are added by later tasks; keep this table in step."""
import sys, unittest, os
from . import kicad_env

def cmd_test(_args):
    suite = unittest.defaultTestLoader.discover(os.path.join(kicad_env.REPO, "hardware", "tests"),
                                                top_level_dir=os.path.join(kicad_env.REPO, "hardware"))
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    return 0 if result.wasSuccessful() else 1

def cmd_env(_args):
    print("kicad-cli:", kicad_env.kicad_cli())
    print("symbols:  ", kicad_env.symbol_dir())
    print("footprints:", kicad_env.footprint_dir())
    print("python:   ", sys.executable, sys.version.split()[0])
    return 0

COMMANDS = {"test": cmd_test, "env": cmd_env}

def cmd_generate(_args):
    from . import schematic
    os.makedirs(kicad_env.PROJECT_DIR, exist_ok=True)
    schematic.write_lib_tables(kicad_env.PROJECT_DIR)
    print("wrote", schematic.write(kicad_env.PROJECT_DIR))
    return 0
COMMANDS["generate"] = cmd_generate

def main(argv):
    if len(argv) < 2 or argv[1] not in COMMANDS:
        print("usage: python -m dryer_board <%s>" % "|".join(sorted(COMMANDS)))
        return 2
    return COMMANDS[argv[1]](argv[2:])

if __name__ == "__main__":
    sys.exit(main(sys.argv))
