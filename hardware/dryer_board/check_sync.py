# hardware/dryer_board/check_sync.py
"""Is the committed KiCad project what the model would generate? Compared semantically
(netlists, footprints, pad nets, positions, rules, mains copper), not byte for byte, so a GUI
re-save that changes only formatting still passes. SELV routing is never compared: the router
is not deterministic, and DRC already judges it."""
import json, os, shutil, tempfile
import pcbnew
from . import circuit, placement, project, schematic

def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()

def schematic_diffs(project_dir):
    committed = os.path.join(project_dir, circuit.PROJECT + ".kicad_sch")
    if not os.path.exists(committed):
        return ["%s missing" % committed]
    diffs = []
    tmp = tempfile.mkdtemp()
    try:
        schematic.write_lib_tables(tmp); schematic.write(tmp); project.write(tmp)
        want = schematic.netlist_from_kicad(os.path.join(tmp, circuit.PROJECT + ".kicad_sch"))
        got = schematic.netlist_from_kicad(committed)
        for net in sorted(set(want) | set(got)):
            if want.get(net) != got.get(net):
                diffs.append("schematic net %s: model %s, committed %s"
                             % (net, sorted(want.get(net, [])), sorted(got.get(net, []))))
        for name in (circuit.PROJECT + ".kicad_dru", "sym-lib-table", "fp-lib-table"):
            other = os.path.join(project_dir, name)
            if not os.path.exists(other) or _read(os.path.join(tmp, name)) != _read(other):
                diffs.append("%s differs from the generator's output" % name)
        pro = circuit.PROJECT + ".kicad_pro"
        other = os.path.join(project_dir, pro)
        if not os.path.exists(other) or json.loads(_read(os.path.join(tmp, pro))) != json.loads(_read(other)):
            diffs.append("%s differs from the generator's output" % pro)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return diffs

def _seg(layer, a, b):
    """A track segment as a comparable key: layer plus its two end points in micrometres,
    ordered so direction does not matter."""
    pts = sorted([(int(round(a[0] * 1000)), int(round(a[1] * 1000))),
                  (int(round(b[0] * 1000)), int(round(b[1] * 1000)))])
    return (layer, pts[0], pts[1])

def _mains_diffs(b):
    diffs = []
    want = set()
    for _net, layer, pts in placement.MAINS_TRACKS:
        for p, q in zip(pts, pts[1:]):
            want.add(_seg(layer, p, q))
    width = pcbnew.FromMM(circuit.NETCLASSES["MAINS"][0])
    have = set()
    for t in b.GetTracks():
        if t.GetNetname() not in circuit.MAINS_NETS:
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

def board_diffs(pcb_path):
    diffs = []
    if not os.path.exists(pcb_path):
        return ["%s missing" % pcb_path]
    b = pcbnew.LoadBoard(pcb_path)
    have = {f.GetReference(): f for f in b.GetFootprints()}
    for part in circuit.board_parts():
        fp = have.pop(part.ref, None)
        if fp is None:
            diffs.append("%s missing from the board" % part.ref); continue
        if fp.GetFPIDAsString() != part.footprint:
            diffs.append("%s footprint %s, model %s" % (part.ref, fp.GetFPIDAsString(), part.footprint))
        x, y, rot = placement.PLACE[part.ref]
        px, py = fp.GetPosition().x / 1e6, fp.GetPosition().y / 1e6
        drot = (fp.GetOrientationDegrees() - rot) % 360
        if abs(px - x) > 0.01 or abs(py - y) > 0.01 or min(drot, 360 - drot) > 0.01:
            diffs.append("%s at (%.2f, %.2f, %.0f), model (%.2f, %.2f, %d)"
                         % (part.ref, px, py, fp.GetOrientationDegrees(), x, y, rot))
        for pad in fp.Pads():
            want = part.pins.get(pad.GetNumber(), circuit.NC)
            got = pad.GetNetname() or circuit.NC
            if want != got:
                diffs.append("%s pad %s on %s, model %s" % (part.ref, pad.GetNumber(), got, want))
    for ref in have:
        diffs.append("%s on the board but not in the model" % ref)
    # The rule areas board.build creates, by name.
    want_names = sorted(["antenna_keepout", "mains_nopour"] + ["relay_pads"] * len(placement.RELAY_AREAS))
    names = sorted(z.GetZoneName() for z in b.Zones() if z.GetIsRuleArea())
    if names != want_names:
        diffs.append("rule areas %s, model %s" % (names, want_names))
    return diffs + _mains_diffs(b)

def all_diffs(project_dir):
    return schematic_diffs(project_dir) + board_diffs(os.path.join(project_dir, circuit.PROJECT + ".kicad_pcb"))
