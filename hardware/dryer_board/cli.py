"""python -m dryer_board <command>. Every command runs over both boards (boards.BOARDS) unless
a board is named: generate [--fresh] [board], route [board] [passes], check [board],
export [--no-docs] [board], test, env."""
import sys, unittest, os
from . import kicad_env

def _boards(args):
    from . import boards
    named = [boards.by_name(a) for a in args if not a.startswith("-") and not a.isdigit()]
    return named or list(boards.BOARDS)

def _pcb(bd):
    return os.path.join(kicad_env.project_dir(bd), bd.PROJECT + ".kicad_pcb")

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

def cmd_generate(args):
    from . import project, schematic, board
    for bd in _boards(args):
        errs = bd.check()
        for e in errs:
            print("%s: %s" % (bd.SHORT, e))
        if errs:
            return 1
        d = kicad_env.project_dir(bd)
        os.makedirs(d, exist_ok=True)
        project.write(bd, d)
        schematic.write_lib_tables(bd, d)
        print("wrote", schematic.write(bd, d))
        board.build(bd, _pcb(bd), fresh="--fresh" in args)
        print("wrote", _pcb(bd))
    return 0
COMMANDS["generate"] = cmd_generate

def cmd_route(args):
    from . import route
    passes = next((int(a) for a in args if a.isdigit()), 50)
    for bd in _boards(args):
        print("%s tracks: %d" % (bd.SHORT, route.route(bd, _pcb(bd), passes)))
    return 0
COMMANDS["route"] = cmd_route

def cmd_check(args):
    """ERC on each committed schematic, DRC on each committed board; exit 1 on any violation,
    unconnected pad or ERC error, with the reports printed."""
    import subprocess
    from . import board as board_mod, check_sync
    ok = True
    for bd in _boards(args):
        d = kicad_env.project_dir(bd)
        sch, pcb = os.path.join(d, bd.PROJECT + ".kicad_sch"), _pcb(bd)
        print("==", bd.PROJECT)
        diffs = check_sync.all_diffs(bd, d)
        for x in diffs:
            print("OUT OF SYNC:", x)
        ok &= not diffs
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

def cmd_export(args):
    from . import export
    # --no-docs: leave the committed review files in docs/hardware/ alone (CI uses it).
    docs = None if "--no-docs" in args else os.path.join(kicad_env.REPO, "docs", "hardware")
    for bd in _boards(args):
        for k, v in sorted(export.export_all(bd, kicad_env.project_dir(bd), kicad_env.OUT_DIR, docs).items()):
            print("%-10s %-14s %s" % (bd.SHORT, k, v))
    return 0
COMMANDS["export"] = cmd_export

def main(argv):
    if len(argv) < 2 or argv[1] not in COMMANDS:
        print("usage: python -m dryer_board <%s>" % "|".join(sorted(COMMANDS)))
        return 2
    return COMMANDS[argv[1]](argv[2:])

if __name__ == "__main__":
    sys.exit(main(sys.argv))
