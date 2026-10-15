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

# Freerouting keeps its netclass clearance (0.2 mm) from the board outline, not the 0.5 mm
# copper-to-edge minimum in the project's rules, so the router gets a keep-out band this wide
# inside the outline (0.5 plus a margin for its rounding).
EDGE_BAND = 0.55
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


# DRC's "mains to selv" (6 mm) applies to mains copper outside the relay areas; the router
# sees only its 0.2 mm, so each such pad or track gets a keepout of its own shape grown by
# this much. Freerouting keeps its 0.2 mm clearance from a keepout as well, so 5.85 holds
# 6.05; at 6.1 (6.3 in effect) RLY_A no longer fits up the strip past F1's pad 1.
MAINS_KEEPOUT = 5.85


def rect_poly(x1, y1, x2, y2):
    """A rectangle in mm as a SHAPE_POLY_SET."""
    area = pcbnew.SHAPE_POLY_SET(); area.NewOutline()
    for x, y in ((x1, y1), (x2, y1), (x2, y2), (x1, y2)):
        area.Append(pcbnew.VECTOR2I_MM(x, y))
    return area


def copper_in_area(item, layer, area):
    """True if any of the item's copper (track, via or pad) on this layer lies inside the area
    polygon. The real outline, as DRC's insideArea judges it, not the bounding box: a diagonal
    segment past an area's corner has a box that overlaps it with no copper inside."""
    poly = pcbnew.SHAPE_POLY_SET()
    item.TransformShapeToPolygon(poly, layer, 0, pcbnew.FromMM(0.005), pcbnew.ERROR_INSIDE)
    poly.BooleanIntersection(area)
    return poly.OutlineCount() != 0


def relay_area_polys(bd):
    """The board's relay areas as polygons."""
    return [rect_poly(*r) for r in getattr(bd, "RELAY_AREAS", [])]


def in_relay_area(item, layer, areas):
    """True if the item's copper on this layer touches any of the relay-area polygons."""
    return any(copper_in_area(item, layer, a) for a in areas)


def _mains_keepouts(b, bd):
    """Keepouts round the mains copper outside the relay areas (F1's pad 1 and the L_IN run
    from it, beside the SELV strip). Inside an area the coil corridors already govern."""
    areas = relay_area_polys(bd)
    items = [t for t in b.GetTracks() if t.GetNetname() in bd.MAINS_NETS]
    items += [p for fp in b.GetFootprints() for p in fp.Pads() if p.GetNetname() in bd.MAINS_NETS]
    n = 0
    for it in items:
        for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
            if not it.IsOnLayer(layer) or in_relay_area(it, layer, areas):
                continue
            poly = pcbnew.SHAPE_POLY_SET()
            it.TransformShapeToPolygon(poly, layer, pcbnew.FromMM(MAINS_KEEPOUT), pcbnew.FromMM(0.01),
                                       pcbnew.ERROR_OUTSIDE)
            z = pcbnew.ZONE(b); z.SetIsRuleArea(True); z.SetLayerSet(pcbnew.LSET.AllCuMask(2))
            z.SetDoNotAllowTracks(True); z.SetDoNotAllowVias(True); z.SetDoNotAllowZoneFills(True)
            z.SetDoNotAllowPads(False); z.SetDoNotAllowFootprints(False)
            # Copy the points into the zone's own outline: SetOutline would hand the zone a
            # SHAPE_POLY_SET Python still owns, and the DSN export then crashes on it.
            o, chain = z.Outline(), poly.Outline(0)
            o.NewOutline()
            for i in range(chain.PointCount()):
                o.Append(chain.CPoint(i))
            b.Add(z); n += 1
            break
    return n


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
    - A band EDGE_BAND wide inside the outline is a keepout (the 0.5 mm edge clearance).
    - Mains copper outside the relay areas is ringed by a MAINS_KEEPOUT keepout.
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
    w, h, e = bd.BOARD_W, bd.BOARD_H, EDGE_BAND
    for rect in ((0, 0, w, e), (0, h - e, w, h), (0, 0, e, h), (w - e, 0, w, h)):
        _keepout(b, *rect)
    _mains_keepouts(b, bd)
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


# The project's minimum track width (project.py, min_track_width).
MIN_TRACK = 0.2


def _widen_necks(b, bd):
    """Freerouting's optimiser leaves the odd short segment necked below the width it was
    given (0.18 mm on a 0.3 mm net, with room beside it for the full width); one under the
    project's 0.2 mm minimum goes back to its netclass width. DRC judges the result, so a
    neck that was holding a clearance shows up as a violation, not as a silent fix."""
    floor = pcbnew.FromMM(MIN_TRACK)
    n = 0
    for t in b.GetTracks():
        if t.GetClass() == "PCB_TRACK" and t.GetWidth() < floor:
            t.SetWidth(pcbnew.FromMM(bd.NETCLASSES[t.GetNetClassName()][0])); n += 1
    return n


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
    _widen_necks(b, bd)
    board_mod.add_mains_copper(b, bd)
    b.BuildConnectivity()
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    if board_mod.remove_dangling_vias(b):
        b.BuildConnectivity()
        pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    pcbnew.SaveBoard(pcb_path, b)
    # SaveBoard rewrites the .kicad_pro beside the board with defaults.
    project.write(bd, os.path.dirname(os.path.abspath(pcb_path)))
    board_mod.refill_with_rules(bd, pcb_path)
    for p in (dsn, ses):
        os.remove(p)
    return len(list(b.GetTracks()))
