# hardware/dryer_board/route.py
"""Autoroute a board's SELV nets with Freerouting running in Docker (no Java on the host);
the mains copper is fixed geometry. The routed boards are committed and CI never routes."""
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


# Freerouting reads netclass widths and clearances from the DSN but not the custom rules in
# mains.RULES (6 mm mains to SELV, 3.5 mm at the relay pads, 6 mm from the live NC pad), so
# it does not route the mains nets: their copper is fixed geometry (bd.MAINS_TRACKS, laid by
# board.add_mains_copper). The router gets the board with that copper locked and the mains
# side closed to it, except a narrow corridor from the slot to each relay coil pad. On the
# controller board there is no mains side: the keepout is the strip past the GND pour.

CORRIDOR = 0.9               # half-height of the opening at each coil pad (track 0.8 + 0.2 clearance fits)
COIL_PADS = ("2", "5")


def _keepout(b, x1, y1, x2, y2):
    z = pcbnew.ZONE(b); z.SetIsRuleArea(True); z.SetLayerSet(pcbnew.LSET.AllCuMask(2))
    z.SetDoNotAllowTracks(True); z.SetDoNotAllowVias(True); z.SetDoNotAllowZoneFills(True)
    z.SetDoNotAllowPads(False); z.SetDoNotAllowFootprints(False)
    o = z.Outline(); o.NewOutline()
    for x, y in ((x1, y1), (x2, y1), (x2, y2), (x1, y2)):
        o.Append(pcbnew.VECTOR2I_MM(x, y))
    b.Add(z)


def _coil_pads(b):
    """(x, y, half size) of every relay coil pad, mm."""
    out = []
    for ref in ("K1", "K2"):
        fp = b.FindFootprintByReference(ref)
        if fp is None:           # a board without relays
            continue
        for pad in fp.Pads():
            if pad.GetNumber() in COIL_PADS:
                pos, size = pad.GetPosition(), pad.GetSize(pcbnew.F_Cu)
                out.append((pcbnew.ToMM(pos.x), pcbnew.ToMM(pos.y), pcbnew.ToMM(max(size.x, size.y)) / 2))
    return out


def _routing_copy(bd, pcb_path):
    """The board as the router should see it.
    - KiCad's DSN export writes every rule area as a full keepout, whatever it forbids, so the
      fill-only areas (the whole mains zone, the relay_pads areas) would wall off the coil
      pads; only areas that forbid tracks or vias (the antenna keep-out) are kept.
    - The GND pours export as planes, and Freerouting then leaves GND to them, but the filled
      pour breaks into islands around the tracks: they go, and GND is routed as wires.
    - Mains tracks are locked, so they export as protected wiring. Every other track goes:
      Freerouting keeps wiring it is given, so a bad route would survive every rerun. The
      SELV side is routed from scratch each time (seconds).
    - Everything right of the GND pour's edge (the slot and the mains zone on the mains board,
      the edge strip on the controller) is a keepout except the coil corridors."""
    b = pcbnew.LoadBoard(pcb_path)
    board_mod.apply_netclasses(b, bd)
    for z in list(b.Zones()):
        if not z.GetIsRuleArea() or not (z.GetDoNotAllowTracks() or z.GetDoNotAllowVias()):
            b.Delete(z)
    for t in list(b.GetTracks()):
        if not t.IsLocked():
            b.Delete(t)
    x0 = bd.GND_POUR[2]
    corridors = sorted((y, x + h + 0.3) for x, y, h in _coil_pads(b))
    xc = max([x for _y, x in corridors] + [x0])
    if xc < bd.BOARD_W:
        _keepout(b, xc, 0, bd.BOARD_W, bd.BOARD_H)
    if xc > x0:
        y = 0.0
        for cy, _x in corridors:
            _keepout(b, x0, y, xc, cy - CORRIDOR)
            y = cy + CORRIDOR
        _keepout(b, x0, y, xc, bd.BOARD_H)
    return b


def route(bd, pcb_path, passes=50):
    base = pcb_path[:-len(".kicad_pcb")]
    dsn, ses = base + ".dsn", base + ".ses"
    for p in (dsn, ses):
        if os.path.exists(p):
            os.remove(p)
    board_mod.export_dsn(_routing_copy(bd, pcb_path), dsn)
    run_freerouting(dsn, ses, passes)
    b = pcbnew.LoadBoard(pcb_path)
    board_mod.apply_netclasses(b, bd)
    # The SES carries every wire, the protected mains ones included; import onto a bare board
    # so nothing is doubled, then lay the mains copper again from the table.
    for t in list(b.GetTracks()):
        b.Delete(t)
    if not pcbnew.ImportSpecctraSES(b, ses):
        raise RuntimeError("SES import failed")
    board_mod.add_mains_copper(b, bd)
    b.BuildConnectivity()
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    if board_mod.remove_dangling_vias(b):
        b.BuildConnectivity()
        pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    pcbnew.SaveBoard(pcb_path, b)
    # SaveBoard rewrites the .kicad_pro beside the board with defaults.
    project.write(bd, os.path.dirname(os.path.abspath(pcb_path)))
    for p in (dsn, ses):
        os.remove(p)
    return len(list(b.GetTracks()))
