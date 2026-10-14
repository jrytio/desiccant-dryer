# hardware/dryer_board/board.py
"""Build or update the .kicad_pcb with pcbnew. The generator owns footprints, nets, outline,
zones, rule areas and text; tracks and vias survive a rebuild unless their net left the
model or fresh=True."""
import os, subprocess
import pcbnew
from . import circuit, libs, placement, project, kicad_env

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

def _reconcile_footprints(b):
    existing = {f.GetReference(): f for f in b.GetFootprints()}
    for ref, fp in existing.items():
        part = next((p for p in circuit.board_parts() if p.ref == ref), None)
        if part is None or fp.GetFPIDAsString() != part.footprint:
            b.Delete(fp)
    for part in circuit.board_parts():
        fp = b.FindFootprintByReference(part.ref)
        if fp is None:
            fp = pcbnew.FootprintLoad(libs.footprint_path(part.footprint), libs.split(part.footprint)[1])
            fp.SetFPIDAsString(part.footprint); fp.SetReference(part.ref); b.Add(fp)
        fp.SetValue(part.value)
        x, y, rot = placement.PLACE[part.ref]
        fp.SetOrientationDegrees(0); fp.SetPosition(MM(x, y)); fp.SetOrientationDegrees(rot)
        for pad in fp.Pads():
            net = part.pins.get(pad.GetNumber(), circuit.NC)
            if net == circuit.NC:
                pad.SetNetCode(0)
            else:
                pad.SetNet(_net(b, net))

def apply_netclasses(b):
    ns = b.GetDesignSettings().m_NetSettings
    for name, (track, clearance, via, drill, patterns) in circuit.NETCLASSES.items():
        if name == "Default":
            continue
        nc = pcbnew.NETCLASS(name)
        nc.SetTrackWidth(mm(track)); nc.SetClearance(mm(clearance)); nc.SetViaDiameter(mm(via)); nc.SetViaDrill(mm(drill))
        ns.SetNetclass(name, nc)
        for p in patterns:
            ns.SetNetclassPatternAssignment(p, name)
    b.SynchronizeNetsAndNetClasses(False)

def _drop_orphan_tracks(b):
    names = set(circuit.nets())
    for t in list(b.GetTracks()):
        if t.GetNetname() not in names:
            b.Delete(t)

# Seed for KiCad's UUID generator, so the same inputs write the same file (footprints are
# sorted by UUID in the saved board).
UUID_SEED = 0x64727972

def build(pcb_path, fresh=False):
    pcbnew.KIID.SeedGenerator(UUID_SEED)
    if os.path.exists(pcb_path) and not fresh:
        b = pcbnew.LoadBoard(pcb_path)
        _clear_generated(b)
    else:
        b = pcbnew.BOARD()
    for name in circuit.nets():
        _net(b, name)
    _reconcile_footprints(b)
    if fresh:
        for t in list(b.GetTracks()):
            b.Delete(t)
    else:
        _drop_orphan_tracks(b)
    # Reseed so the regenerated items get the same UUIDs whether or not footprints were
    # loaded from an existing file.
    pcbnew.KIID.SeedGenerator(UUID_SEED + 1)
    # outline and slot
    _rect(b, pcbnew.Edge_Cuts, 0, 0, placement.BOARD_W, placement.BOARD_H)
    x1, x2 = placement.SLOT_X
    for y1, y2 in placement.SLOT_SEGMENTS:
        _poly(b, pcbnew.Edge_Cuts, [(x1, y1), (x2, y1), (x2, y2), (x1, y2)])
    # rule areas and pours
    _rule_area(b, "antenna_keepout", placement.ANTENNA_KEEPOUT, fills=True, tracks=True, vias=True, pads=True)
    _rule_area(b, "mains_nopour", placement.MAINS_ZONE, fills=True)
    for r in placement.RELAY_AREAS:
        _rule_area(b, "relay_pads", r, fills=False)
    gnd = _net(b, "GND")
    _pour(b, pcbnew.F_Cu, gnd, placement.SELV_POUR)
    _pour(b, pcbnew.B_Cu, gnd, placement.SELV_POUR)
    # silkscreen
    for text, x, y, size, rot, layer, justify in placement.SILK:
        _text(b, text.replace("${REVISION}", circuit.REVISION), x, y, size, rot, layer, justify)
    _segment(b, pcbnew.F_SilkS, 73.5, 3, 73.5, 82)
    apply_netclasses(b)
    # A new BOARD has no connectivity data yet, and without it the filler leaves the pours empty.
    b.BuildConnectivity()
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    pcbnew.SaveBoard(pcb_path, b)
    # SaveBoard writes a default .kicad_pro beside the board; put the canonical one back.
    project.write(os.path.dirname(pcb_path))
    return b

def export_dsn(b, dsn_path):
    if not pcbnew.ExportSpecctraDSN(b, dsn_path):
        raise RuntimeError("DSN export failed")
    return dsn_path

def drc_report(pcb_path):
    """Run DRC and return the report text. kicad-cli exits 5 on violations, so this does
    not go through run_cli."""
    rpt = pcb_path + ".drc.rpt"
    subprocess.run([kicad_env.kicad_cli(), "pcb", "drc", "--severity-all", "--refill-zones", "-o", rpt, pcb_path],
                   capture_output=True, text=True)
    with open(rpt, encoding="utf-8") as f:
        return f.read()
