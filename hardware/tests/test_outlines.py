# hardware/tests/test_outlines.py
"""The enclosure spaces are hard limits: 85 x 70 (controller) and 45 x 70 (mains).
These run before DRC and fail on size, not on clearance."""
import os, shutil, tempfile, unittest
import pcbnew
from dryer_board import boards, board, parts, project, schematic

SPACES = {"controller": (85.0, 70.0), "mains": (45.0, 70.0)}
# Courtyards that may leave the outline, (board, ref) -> (left, top, right, bottom) mm. None
# today: the mains plug became a vertical header inside the outline in the second review
# round. The Thing Plus body overhangs the controller's left edge, not its socket footprints,
# which must lie inside.
OVERHANG_OK = {}
# The M4 holes sit 4 mm in from each edge (test_declared_sizes), so the stock footprint's
# 9.2 mm head courtyard reaches 0.6 mm past both edges at every corner: a washer seated over
# the corner, not a part leaving the board.
HOLES_OK = {"H1", "H2", "H3", "H4"}
TOL = 0.01

def _built(bd, test):
    d = tempfile.mkdtemp()
    test.addCleanup(shutil.rmtree, d, True)
    project.write(bd, d); schematic.write_lib_tables(bd, d); schematic.write(bd, d)
    pcb = os.path.join(d, bd.PROJECT + ".kicad_pcb")
    board.build(bd, pcb, fresh=True)
    return pcbnew.LoadBoard(pcb)   # reload: only one generator-built board may be alive per process

class Outlines(unittest.TestCase):
    def test_declared_sizes(self):
        for bd in boards.BOARDS:
            self.assertEqual((bd.BOARD_W, bd.BOARD_H), SPACES[bd.SHORT], bd.SHORT)
            self.assertEqual(sorted(bd.HOLES.values()), sorted([(4, 4), (bd.BOARD_W - 4, 4), (4, 66), (bd.BOARD_W - 4, 66)]), bd.SHORT)

    def test_board_edges_match(self):
        for bd in boards.BOARDS:
            b = _built(bd, self)
            # The outline's geometry, not GetBoardEdgesBoundingBox: that includes the Edge.Cuts
            # line width (0.1 mm), which is drawing, not board.
            edges = [d for d in b.GetDrawings() if d.GetLayer() == pcbnew.Edge_Cuts]
            boxes = []
            for d in edges:
                bb = d.GetBoundingBox()
                bb.Inflate(-(d.GetWidth() // 2))
                boxes.append((bb.GetX(), bb.GetY(), bb.GetX() + bb.GetWidth(), bb.GetY() + bb.GetHeight()))
            x1, y1 = min(x[0] for x in boxes) / 1e6, min(x[1] for x in boxes) / 1e6
            x2, y2 = max(x[2] for x in boxes) / 1e6, max(x[3] for x in boxes) / 1e6
            self.assertAlmostEqual(x1, 0.0, delta=TOL, msg=bd.SHORT)
            self.assertAlmostEqual(y1, 0.0, delta=TOL, msg=bd.SHORT)
            self.assertAlmostEqual(x2 - x1, bd.BOARD_W, delta=TOL, msg=bd.SHORT)
            self.assertAlmostEqual(y2 - y1, bd.BOARD_H, delta=TOL, msg=bd.SHORT)

    def test_courtyards_inside(self):
        for bd in boards.BOARDS:
            b = _built(bd, self)
            for fp in b.GetFootprints():
                cy = fp.GetCourtyard(pcbnew.F_CrtYd).BBox()
                x1, y1 = cy.GetX() / 1e6, cy.GetY() / 1e6
                x2, y2 = x1 + cy.GetWidth() / 1e6, y1 + cy.GetHeight() / 1e6
                if fp.GetReference() in HOLES_OK:
                    continue
                ol, ot, orr, ob = OVERHANG_OK.get((bd.SHORT, fp.GetReference()), (0, 0, 0, 0))
                inside = (x1 >= -ol - TOL and y1 >= -ot - TOL and x2 <= bd.BOARD_W + orr + TOL
                          and y2 <= bd.BOARD_H + ob + TOL)
                self.assertTrue(inside, "%s %s courtyard (%.2f,%.2f)-(%.2f,%.2f) leaves the %sx%s board"
                                % (bd.SHORT, fp.GetReference(), x1, y1, x2, y2, bd.BOARD_W, bd.BOARD_H))

    def test_esp_body_clear_of_hole_heads(self):
        """The Thing Plus is 64.77 x 22.86 mm with its USB-C face 3 mm past the left edge;
        an M4 head is about 7 mm across, so no hole centre may be within 3.5 mm of the body."""
        bd = boards.by_name("controller")
        x12, y12, _ = bd.PLACE["J_ESP12"]; x16, y16, _ = bd.PLACE["J_ESP16"]
        top, bottom = min(y12, y16) - 1.27, max(y12, y16) + 1.27
        left, right = -3.0, -3.0 + 64.77
        for ref, (hx, hy) in bd.HOLES.items():
            near = (left - 3.5) <= hx <= (right + 3.5) and (top - 3.5) <= hy <= (bottom + 3.5)
            self.assertFalse(near, "%s at (%s, %s) is under or beside the ESP body" % (ref, hx, hy))

    def test_link_pinout_identical(self):
        for bd, ref in ((boards.by_name("controller"), "J_RLY"), (boards.by_name("mains"), "J_CTRL")):
            self.assertEqual(bd.by_ref(ref).pins, parts.LINK_PINS, ref)
