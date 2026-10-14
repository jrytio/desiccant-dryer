# hardware/dryer_board/route.py
"""Autoroute with Freerouting running in Docker (no Java on the host). Routing is not
deterministic; the routed board is committed and CI never routes."""
import os, subprocess, shutil
import pcbnew
from . import board as board_mod
from . import project

IMAGE = "ghcr.io/freerouting/freerouting:2.5.0"


def run_freerouting(dsn_path, ses_path, passes=50):
    work = os.path.dirname(os.path.abspath(dsn_path))
    os.makedirs(os.path.join(work, ".freerouting"), exist_ok=True)
    cmd = ["docker", "run", "--rm", "-u", "%d:%d" % (os.getuid(), os.getgid()),
           "-v", work + ":/work", IMAGE,
           "java", "-jar", "/app/freerouting-executable.jar",
           "--user_data_path=/work/.freerouting", "--gui-enabled=false",
           "-de", "/work/" + os.path.basename(dsn_path), "-do", "/work/" + os.path.basename(ses_path),
           "-mp", str(passes), "-mt", "4"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if not os.path.isfile(ses_path):
        raise RuntimeError("Freerouting produced no SES:\n%s\n%s" % (proc.stdout[-3000:], proc.stderr[-3000:]))
    shutil.rmtree(os.path.join(work, ".freerouting"), ignore_errors=True)
    return proc.stdout


def route(pcb_path, passes=50):
    b = pcbnew.LoadBoard(pcb_path)
    board_mod.apply_netclasses(b)
    dsn = pcb_path[:-len(".kicad_pcb")] + ".dsn"
    ses = pcb_path[:-len(".kicad_pcb")] + ".ses"
    for p in (dsn, ses):
        if os.path.exists(p):
            os.remove(p)
    board_mod.export_dsn(b, dsn)
    run_freerouting(dsn, ses, passes)
    if not pcbnew.ImportSpecctraSES(b, ses):
        raise RuntimeError("SES import failed")
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    pcbnew.SaveBoard(pcb_path, b)
    # SaveBoard rewrites the .kicad_pro beside the board with defaults.
    project.write(os.path.dirname(os.path.abspath(pcb_path)))
    for p in (dsn, ses):
        os.remove(p)
    return len(list(b.GetTracks()))
