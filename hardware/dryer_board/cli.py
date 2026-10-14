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
    from . import project, schematic
    os.makedirs(kicad_env.PROJECT_DIR, exist_ok=True)
    project.write(kicad_env.PROJECT_DIR)
    schematic.write_lib_tables(kicad_env.PROJECT_DIR)
    print("wrote", schematic.write(kicad_env.PROJECT_DIR))
    from . import board, circuit
    pcb = os.path.join(kicad_env.PROJECT_DIR, circuit.PROJECT + ".kicad_pcb")
    board.build(pcb, fresh="--fresh" in _args)
    print("wrote", pcb)
    return 0
COMMANDS["generate"] = cmd_generate

def cmd_route(args):
    from . import route, circuit
    pcb = os.path.join(kicad_env.PROJECT_DIR, circuit.PROJECT + ".kicad_pcb")
    passes = int(args[0]) if args else 50
    print("tracks:", route.route(pcb, passes))
    return 0
COMMANDS["route"] = cmd_route

def cmd_check(_args):
    """ERC on the committed schematic, DRC on the committed board; exit 1 on any violation,
    unconnected pad or ERC error, with both reports printed."""
    import subprocess
    from . import board as board_mod, circuit
    sch = os.path.join(kicad_env.PROJECT_DIR, circuit.PROJECT + ".kicad_sch")
    pcb = os.path.join(kicad_env.PROJECT_DIR, circuit.PROJECT + ".kicad_pcb")
    ok = True
    erc_rpt = sch + ".erc.rpt"
    if os.path.exists(erc_rpt):
        os.remove(erc_rpt)
    erc = subprocess.run([kicad_env.kicad_cli(), "sch", "erc", "--severity-all", "--exit-code-violations",
                          "-o", erc_rpt, sch], capture_output=True, text=True)
    if not os.path.exists(erc_rpt):
        print("ERC did not run (exit %d)\n%s%s" % (erc.returncode, erc.stdout, erc.stderr))
        return 1
    with open(erc_rpt, encoding="utf-8") as f:
        print(f.read())
    ok &= erc.returncode == 0
    text = board_mod.drc_report(pcb)
    print(text)
    ok &= "** Found 0 DRC violations **" in text and "** Found 0 unconnected pads **" in text
    return 0 if ok else 1
COMMANDS["check"] = cmd_check

def main(argv):
    if len(argv) < 2 or argv[1] not in COMMANDS:
        print("usage: python -m dryer_board <%s>" % "|".join(sorted(COMMANDS)))
        return 2
    return COMMANDS[argv[1]](argv[2:])

if __name__ == "__main__":
    sys.exit(main(sys.argv))
