# hardware/dryer_board/board.py
"""Build or update a board's .kicad_pcb with pcbnew. The generator owns footprints, nets,
outline, zones, rule areas and text; tracks and vias survive a rebuild unless their net left
the model or fresh=True. `bd` is a board module (boards.py)."""
import os, subprocess, tempfile
import pcbnew
from . import libs, project, kicad_env, parts
from .parts import NC

MM = pcbnew.VECTOR2I_MM
def mm(v): return pcbnew.FromMM(v)

_JUSTIFY = {"left": pcbnew.GR_TEXT_H_ALIGN_LEFT, "right": pcbnew.GR_TEXT_H_ALIGN_RIGHT, "center": pcbnew.GR_TEXT_H_ALIGN_CENTER}
_LAYER = {"F.SilkS": pcbnew.F_SilkS, "B.SilkS": pcbnew.B_SilkS}

def _rect(b, layer, x1, y1, x2, y2, width=0.1):
    s = pcbnew.PCB_SHAPE(b); s.SetShape(pcbnew.SHAPE_T_RECT)
    s.SetStart(MM(x1, y1)); s.SetEnd(MM(x2, y2)); s.SetLayer(layer); s.SetWidth(mm(width)); b.Add(s)

def _segment(b, layer, x1, y1, x2, y2, width=0.3):
    s = pcbnew.PCB_SHAPE(b); s.SetShape(pcbnew.SHAPE_T_SEGMENT)
    s.SetStart(MM(x1, y1)); s.SetEnd(MM(x2, y2)); s.SetLayer(layer); s.SetWidth(mm(width)); b.Add(s)

def _poly(b, layer, pts, width=0.1):
    s = pcbnew.PCB_SHAPE(b); s.SetShape(pcbnew.SHAPE_T_POLY)
    sps = pcbnew.SHAPE_POLY_SET(); sps.NewOutline()
    for x, y in pts:
        sps.Append(MM(x, y))
    s.SetPolyShape(sps); s.SetLayer(layer); s.SetWidth(mm(width)); s.SetFilled(False); b.Add(s)

def _zone_outline(z, x1, y1, x2, y2):
    o = z.Outline(); o.NewOutline()
    for x, y in ((x1, y1), (x2, y1), (x2, y2), (x1, y2)):
        o.Append(MM(x, y))

def _rule_area(b, name, rect, fills=True, tracks=False, vias=False, pads=False):
    z = pcbnew.ZONE(b); z.SetIsRuleArea(True); z.SetZoneName(name); z.SetLayerSet(pcbnew.LSET.AllCuMask(2))
    z.SetDoNotAllowZoneFills(fills); z.SetDoNotAllowTracks(tracks); z.SetDoNotAllowVias(vias)
    z.SetDoNotAllowPads(pads); z.SetDoNotAllowFootprints(False)
    _zone_outline(z, *rect); b.Add(z)

def _pour(b, layer, net, rect):
    z = pcbnew.ZONE(b); z.SetLayer(layer); z.SetNet(net); z.SetZoneName("gnd_" + ("F" if layer == pcbnew.F_Cu else "B"))
    z.SetLocalClearance(mm(0.3)); z.SetMinThickness(mm(0.25)); z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
    _zone_outline(z, *rect); b.Add(z)

def _text(b, text, x, y, size, rot, layer, justify):
    t = pcbnew.PCB_TEXT(b); t.SetText(text); t.SetPosition(MM(x, y)); t.SetLayer(_LAYER[layer])
    t.SetTextSize(MM(size, size)); t.SetTextThickness(mm(max(0.12, size * 0.15)))
    t.SetHorizJustify(_JUSTIFY[justify]); t.SetTextAngleDegrees(rot)
    if layer == "B.SilkS":
        t.SetMirrored(True)
    b.Add(t)

def _clear_generated(b):
    """Remove everything the generator owns: shapes, zones, text. Footprints are reconciled
    separately; tracks are kept. Delete, not Remove: Remove leaves the items unowned and
    SWIG's type table broken, so later GetFootprints() returns bare SwigPyObjects."""
    for item in list(b.GetDrawings()):
        b.Delete(item)
    for z in list(b.Zones()):
        b.Delete(z)

def _net(b, name):
    net = b.FindNet(name)
    if net is None:
        net = pcbnew.NETINFO_ITEM(b, name); b.Add(net)
    return net

def _reconcile_footprints(b, bd):
    model = parts.board_parts(bd.PARTS)
    existing = {f.GetReference(): f for f in b.GetFootprints()}
    for ref, fp in existing.items():
        part = next((p for p in model if p.ref == ref), None)
        if part is None or fp.GetFPIDAsString() != part.footprint:
            b.Delete(fp)
    for part in model:
        fp = b.FindFootprintByReference(part.ref)
        if fp is None:
            fp = pcbnew.FootprintLoad(libs.footprint_path(part.footprint), libs.split(part.footprint)[1])
            fp.SetFPIDAsString(part.footprint); fp.SetReference(part.ref); b.Add(fp)
        fp.SetValue(part.value)
        fp.Reference().SetVisible(part.ref not in bd.HIDDEN_REFS)
        x, y, rot = bd.PLACE[part.ref]
        fp.SetOrientationDegrees(0); fp.SetPosition(MM(x, y)); fp.SetOrientationDegrees(rot)
        for pad in fp.Pads():
            net = part.pins.get(pad.GetNumber(), NC)
            if net == NC:
                pad.SetNetCode(0)
            else:
                pad.SetNet(_net(b, net))

def apply_netclasses(b, bd):
    ns = b.GetDesignSettings().m_NetSettings
    for name, (track, clearance, via, drill, patterns) in bd.NETCLASSES.items():
        if name == "Default":
            continue
        nc = pcbnew.NETCLASS(name)
        nc.SetTrackWidth(mm(track)); nc.SetClearance(mm(clearance)); nc.SetViaDiameter(mm(via)); nc.SetViaDrill(mm(drill))
        ns.SetNetclass(name, nc)
        for p in patterns:
            ns.SetNetclassPatternAssignment(p, name)
    b.SynchronizeNetsAndNetClasses(False)

def _drop_orphan_tracks(b, bd):
    names = set(parts.nets(bd.PARTS))
    for t in list(b.GetTracks()):
        if t.GetNetname() not in names:
            b.Delete(t)

def add_mains_copper(b, bd):
    """Lay the mains tracks from bd.MAINS_TRACKS, locked, replacing any mains copper already
    on the board. The router never routes mains (route.py says why). Seeded, so the mains
    tracks get the same UUIDs whether build or route lays them. A board with no mains copper
    (the controller) lays nothing."""
    pcbnew.KIID.SeedGenerator(UUID_SEED + 2)
    for t in list(b.GetTracks()):
        if t.GetNetname() in bd.MAINS_NETS:
            b.Delete(t)
    if not bd.MAINS_TRACKS:
        return
    width = mm(bd.NETCLASSES["MAINS"][0])
    layers = {"F.Cu": pcbnew.F_Cu, "B.Cu": pcbnew.B_Cu}
    for net, layer, pts in bd.MAINS_TRACKS:
        n = _net(b, net)
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            t = pcbnew.PCB_TRACK(b); t.SetStart(MM(x1, y1)); t.SetEnd(MM(x2, y2))
            t.SetWidth(width); t.SetLayer(layers[layer]); t.SetNet(n); t.SetLocked(True)
            b.Add(t)

# Seed for KiCad's UUID generator, so the same inputs write the same file (footprints are
# sorted by UUID in the saved board).
UUID_SEED = 0x64727972

def build(bd, pcb_path, fresh=False):
    """Build the board and save it. The returned in-memory board keeps the plain pcbnew fill;
    the saved file has the rules-aware fill that refill_with_rules writes after the save."""
    pcbnew.KIID.SeedGenerator(UUID_SEED)
    if os.path.exists(pcb_path) and not fresh:
        b = pcbnew.LoadBoard(pcb_path)
        _clear_generated(b)
    else:
        b = pcbnew.BOARD()
    for name in parts.nets(bd.PARTS):
        _net(b, name)
    _reconcile_footprints(b, bd)
    if fresh:
        for t in list(b.GetTracks()):
            b.Delete(t)
    else:
        _drop_orphan_tracks(b, bd)
    add_mains_copper(b, bd)
    # Reseed so the regenerated items get the same UUIDs whether or not footprints were
    # loaded from an existing file.
    pcbnew.KIID.SeedGenerator(UUID_SEED + 1)
    # outline and slot
    board_outline, *slots = bd.edge_outlines()
    _rect(b, pcbnew.Edge_Cuts, *board_outline[0], *board_outline[2])
    for pts in slots:
        _poly(b, pcbnew.Edge_Cuts, pts)
    # rule areas and pours
    for name, rect, (fills, tracks, vias, pads) in bd.rule_areas():
        _rule_area(b, name, rect, fills=fills, tracks=tracks, vias=vias, pads=pads)
    gnd = _net(b, "GND")
    _pour(b, pcbnew.F_Cu, gnd, bd.GND_POUR)
    _pour(b, pcbnew.B_Cu, gnd, bd.GND_POUR)
    # silkscreen
    for text, x, y, size, rot, layer, justify in bd.SILK:
        _text(b, text.replace("${REVISION}", bd.REVISION), x, y, size, rot, layer, justify)
    for x1, y1, x2, y2 in bd.SILK_LINES:
        _segment(b, pcbnew.F_SilkS, x1, y1, x2, y2)
    apply_netclasses(b, bd)
    # A new BOARD has no connectivity data yet, and without it the filler leaves the pours empty.
    b.BuildConnectivity()
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    pcbnew.SaveBoard(pcb_path, b)
    # SaveBoard writes a default .kicad_pro beside the board; put the canonical one back.
    project.write(bd, os.path.dirname(pcb_path))
    refill_with_rules(bd, pcb_path)
    return b

def _touches(via, layer, b):
    """True if a track end, a pad or a filled zone of the via's net reaches it on this layer."""
    pos, r, net = via.GetPosition(), via.GetWidth(layer) // 2, via.GetNetCode()
    for t in b.GetTracks():
        if t.GetClass() == "PCB_TRACK" and t.GetNetCode() == net and t.GetLayer() == layer:
            if (t.GetStart() - pos).EuclideanNorm() <= r or (t.GetEnd() - pos).EuclideanNorm() <= r:
                return True
    for fp in b.GetFootprints():
        for pad in fp.Pads():
            if pad.GetNetCode() == net and pad.IsOnLayer(layer) and pad.HitTest(pos):
                return True
    for z in b.Zones():
        if not z.GetIsRuleArea() and z.GetNetCode() == net and z.IsOnLayer(layer) \
                and z.GetFilledPolysList(layer).Contains(pos):
            return True
    return False

def remove_dangling_vias(b):
    """Delete vias that are not connected on both of their layers (router leftovers from
    abandoned partial routes). Returns how many went."""
    gone = 0
    for v in list(b.GetTracks()):
        if v.GetClass() == "PCB_VIA" and not (_touches(v, pcbnew.F_Cu, b) and _touches(v, pcbnew.B_Cu, b)):
            b.Delete(v); gone += 1
    return gone

def refill_with_rules(bd, pcb_path):
    """Refill the saved board's pours with the project's rules and save it again. The pcbnew
    filler runs before the .kicad_pro and .kicad_dru are on disk (and does not read them), so
    its fill keeps only the zone's own clearance; DRC with --refill-zones would pass on its own
    refill while the saved copper, which the gerbers are plotted from, sat closer to mains than
    the rules allow. kicad-cli loads the project beside the board, refills, and saves; it exits
    5 when violations exist (an unrouted board), which is still a saved refill."""
    fd, rpt = tempfile.mkstemp(suffix=".rpt")
    os.close(fd)
    try:
        r = subprocess.run([kicad_env.kicad_cli(), "pcb", "drc", "--refill-zones", "--save-board", "-o", rpt, pcb_path],
                           capture_output=True, text=True)
    finally:
        os.remove(rpt)
    if r.returncode not in (0, 5):
        raise RuntimeError("kicad-cli pcb drc --refill-zones --save-board failed (exit %d)\nstdout:\n%s\nstderr:\n%s"
                           % (r.returncode, r.stdout, r.stderr))
    # The save rewrites the .kicad_pro beside the board; put the canonical one back.
    project.write(bd, os.path.dirname(os.path.abspath(pcb_path)))

def export_dsn(b, dsn_path):
    if not pcbnew.ExportSpecctraDSN(b, dsn_path):
        raise RuntimeError("DSN export failed")
    return dsn_path

def drc_report(pcb_path):
    """Run DRC and return the report text. kicad-cli exits 5 on violations, so this does
    not go through run_cli; any other nonzero exit, or no report, is a failed run."""
    rpt = pcb_path + ".drc.rpt"
    if os.path.exists(rpt):
        os.remove(rpt)
    r = subprocess.run([kicad_env.kicad_cli(), "pcb", "drc", "--severity-all", "--refill-zones", "-o", rpt, pcb_path],
                       capture_output=True, text=True)
    if r.returncode not in (0, 5) or not os.path.exists(rpt):
        raise RuntimeError("kicad-cli pcb drc failed (exit %d)\nstdout:\n%s\nstderr:\n%s"
                           % (r.returncode, r.stdout, r.stderr))
    with open(rpt, encoding="utf-8") as f:
        return f.read()
