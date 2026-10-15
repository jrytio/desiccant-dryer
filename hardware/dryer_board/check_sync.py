# hardware/dryer_board/check_sync.py
"""Is a committed KiCad project what the model would generate? Compared semantically
(netlists, footprints, pad nets, positions, rules, rule-area and Edge.Cuts geometry, mains
copper, the local footprint copies), not byte for byte, so a GUI re-save that changes only
formatting still passes. SELV routing is never compared: the router is not deterministic,
and DRC already judges it."""
import json, os, shutil, tempfile
import pcbnew
from . import kicad_env, parts, project, schematic
from .parts import NC

def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()

def schematic_diffs(bd, project_dir):
    committed = os.path.join(project_dir, bd.PROJECT + ".kicad_sch")
    if not os.path.exists(committed):
        return ["%s missing" % committed]
    diffs = []
    tmp = tempfile.mkdtemp()
    try:
        schematic.write_lib_tables(bd, tmp); schematic.write(bd, tmp); project.write(bd, tmp)
        want = schematic.netlist_from_kicad(os.path.join(tmp, bd.PROJECT + ".kicad_sch"))
        got = schematic.netlist_from_kicad(committed)
        for net in sorted(set(want) | set(got)):
            if want.get(net) != got.get(net):
                diffs.append("schematic net %s: model %s, committed %s"
                             % (net, sorted(want.get(net, [])), sorted(got.get(net, []))))
        for name in (bd.PROJECT + ".kicad_dru", "sym-lib-table", "fp-lib-table"):
            other = os.path.join(project_dir, name)
            if not os.path.exists(other) or _read(os.path.join(tmp, name)) != _read(other):
                diffs.append("%s differs from the generator's output" % name)
        pro = bd.PROJECT + ".kicad_pro"
        other = os.path.join(project_dir, pro)
        if not os.path.exists(other) or json.loads(_read(os.path.join(tmp, pro))) != json.loads(_read(other)):
            diffs.append("%s differs from the generator's output" % pro)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return diffs

def lib_diffs(project_dir):
    """The project's lib/dryer.pretty is a copy of hardware/lib/dryer.pretty: every source
    footprint present and identical."""
    local = os.path.join(project_dir, "lib", "dryer.pretty")
    diffs = []
    for name in sorted(os.listdir(kicad_env.LIB_DIR)):
        if not name.endswith(".kicad_mod"):
            continue
        copy = os.path.join(local, name)
        if not os.path.exists(copy):
            diffs.append("lib/dryer.pretty/%s missing from the project" % name)
        elif _read(copy) != _read(os.path.join(kicad_env.LIB_DIR, name)):
            diffs.append("lib/dryer.pretty/%s differs from hardware/lib/dryer.pretty" % name)
    return diffs

def _seg(layer, a, b):
    """A track segment as a comparable key: layer plus its two end points in micrometres,
    ordered so direction does not matter."""
    pts = sorted([(int(round(a[0] * 1000)), int(round(a[1] * 1000))),
                  (int(round(b[0] * 1000)), int(round(b[1] * 1000)))])
    return (layer, pts[0], pts[1])

def _mains_diffs(b, bd):
    diffs = []
    want = set()
    for _net, layer, pts in bd.MAINS_TRACKS:
        for p, q in zip(pts, pts[1:]):
            want.add(_seg(layer, p, q))
    width = pcbnew.FromMM(bd.NETCLASSES["MAINS"][0]) if "MAINS" in bd.NETCLASSES else None
    have = set()
    for t in b.GetTracks():
        if t.GetNetname() not in bd.MAINS_NETS:
            continue
        if t.Type() == pcbnew.PCB_VIA_T:
            diffs.append("via on mains net %s at (%.2f, %.2f)" % (t.GetNetname(), t.GetPosition().x / 1e6, t.GetPosition().y / 1e6))
            continue
        s, e = t.GetStart(), t.GetEnd()
        key = _seg(b.GetLayerName(t.GetLayer()), (s.x / 1e6, s.y / 1e6), (e.x / 1e6, e.y / 1e6))
        have.add(key)
        if t.GetWidth() != width:
            diffs.append("mains track %s width %.3f mm, model %.3f mm" % (key, t.GetWidth() / 1e6, width / 1e6))
        if not t.IsLocked():
            diffs.append("mains track %s is unlocked" % (key,))
    for key in sorted(want - have):
        diffs.append("mains track %s missing from the board" % (key,))
    for key in sorted(have - want):
        diffs.append("mains track %s on the board but not in the model" % (key,))
    return diffs

# KiCad rounds coordinates on load and save; geometry within this is the same.
TOL_MM = 0.01

def _pts(poly_set):
    """The first outline of a SHAPE_POLY_SET as (x, y) mm tuples."""
    o = poly_set.Outline(0)
    return [(o.CPoint(i).x / 1e6, o.CPoint(i).y / 1e6) for i in range(o.PointCount())]

def _same(a, b):
    """Two outlines with the same corners (in any order or direction), within TOL_MM."""
    return len(a) == len(b) and all(abs(p[0] - q[0]) <= TOL_MM and abs(p[1] - q[1]) <= TOL_MM
                                    for p, q in zip(sorted(a), sorted(b)))

def _fmt(pts):
    return "[%s]" % ", ".join("(%.2f, %.2f)" % p for p in pts)

def _pair(want, have, same):
    """Match model items to board items one to one. Returns (matched pairs, unmatched model
    items, unmatched board items)."""
    have = list(have)
    pairs, missing = [], []
    for w in want:
        h = next((h for h in have if same(w, h)), None)
        if h is None:
            missing.append(w)
        else:
            have.remove(h); pairs.append((w, h))
    return pairs, missing, have

_FLAGS = ("fills", "tracks", "vias", "pads")

def _area_diffs(b, bd):
    """Each rule area board.build lays, by name, outline and what it forbids."""
    want = [(name, [(r[0], r[1]), (r[2], r[1]), (r[2], r[3]), (r[0], r[3])], flags)
            for name, r, flags in bd.rule_areas()]
    have = [(z.GetZoneName(), _pts(z.Outline()),
             (z.GetDoNotAllowZoneFills(), z.GetDoNotAllowTracks(), z.GetDoNotAllowVias(), z.GetDoNotAllowPads()))
            for z in b.Zones() if z.GetIsRuleArea()]
    pairs, missing, extra = _pair(want, have, lambda w, h: w[0] == h[0] and _same(w[1], h[1]))
    diffs = []
    for name, pts, _f in missing:
        diffs.append("rule area %s %s missing from the board" % (name, _fmt(pts)))
    for name, pts, _f in extra:
        diffs.append("rule area %s %s on the board but not in the model" % (name, _fmt(pts)))
    for (name, pts, wf), (_n, _p, hf) in pairs:
        for flag, w, h in zip(_FLAGS, wf, hf):
            if w != h:
                diffs.append("rule area %s %s: no %s is %s, model %s" % (name, _fmt(pts), flag, h, w))
    return diffs

def _edge_diffs(b, bd):
    """The board rectangle and the slot segments on Edge.Cuts."""
    have = []
    for s in b.GetDrawings():
        if s.GetLayer() != pcbnew.Edge_Cuts or s.GetClass() != "PCB_SHAPE":
            continue
        if s.GetShape() == pcbnew.SHAPE_T_RECT:
            (x1, y1), (x2, y2) = [(p.x / 1e6, p.y / 1e6) for p in (s.GetStart(), s.GetEnd())]
            have.append([(x1, y1), (x2, y1), (x2, y2), (x1, y2)])
        elif s.GetShape() == pcbnew.SHAPE_T_POLY:
            have.append(_pts(s.GetPolyShape()))
        else:
            have.append([(p.x / 1e6, p.y / 1e6) for p in (s.GetStart(), s.GetEnd())])
    _pairs, missing, extra = _pair(bd.edge_outlines(), have, _same)
    return (["Edge.Cuts outline %s missing from the board" % _fmt(p) for p in missing] +
            ["Edge.Cuts shape %s on the board but not in the model" % _fmt(p) for p in extra])

def board_diffs(bd, pcb_path):
    diffs = []
    if not os.path.exists(pcb_path):
        return ["%s missing" % pcb_path]
    b = pcbnew.LoadBoard(pcb_path)
    have = {f.GetReference(): f for f in b.GetFootprints()}
    for part in parts.board_parts(bd.PARTS):
        fp = have.pop(part.ref, None)
        if fp is None:
            diffs.append("%s missing from the board" % part.ref); continue
        if fp.GetFPIDAsString() != part.footprint:
            diffs.append("%s footprint %s, model %s" % (part.ref, fp.GetFPIDAsString(), part.footprint))
        x, y, rot = bd.PLACE[part.ref]
        px, py = fp.GetPosition().x / 1e6, fp.GetPosition().y / 1e6
        drot = (fp.GetOrientationDegrees() - rot) % 360
        if abs(px - x) > 0.01 or abs(py - y) > 0.01 or min(drot, 360 - drot) > 0.01:
            diffs.append("%s at (%.2f, %.2f, %.0f), model (%.2f, %.2f, %d)"
                         % (part.ref, px, py, fp.GetOrientationDegrees(), x, y, rot))
        for pad in fp.Pads():
            want = part.pins.get(pad.GetNumber(), NC)
            got = pad.GetNetname() or NC
            if want != got:
                diffs.append("%s pad %s on %s, model %s" % (part.ref, pad.GetNumber(), got, want))
    for ref in have:
        diffs.append("%s on the board but not in the model" % ref)
    return diffs + _area_diffs(b, bd) + _edge_diffs(b, bd) + _mains_diffs(b, bd)

def all_diffs(bd, project_dir):
    return (schematic_diffs(bd, project_dir) + lib_diffs(project_dir)
            + board_diffs(bd, os.path.join(project_dir, bd.PROJECT + ".kicad_pcb")))
