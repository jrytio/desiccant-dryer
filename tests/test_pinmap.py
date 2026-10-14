#!/usr/bin/env python3
"""The main board is wired by header position; each board package names the GPIO behind
each position. This holds the two against each other so neither can drift. Plain python3,
no PyYAML: the substitutions are parsed with a regex."""
import os, re, sys, unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "hardware"))
from dryer_board import pinmap  # noqa: E402

def substitutions(path):
    """pin_* -> GPIO number from a board package. Handles `pin_x: GPIO8` and the nested
    `pin_x:\n    number: GPIO8` form."""
    with open(path, encoding="utf-8") as f:
        text = f.read()
    out = {}
    for m in re.finditer(r"^  (pin_\w+):(?:[ \t]+GPIO(\d+)|\s*\n\s+number:\s*GPIO(\d+))", text, re.M):
        out[m.group(1)] = int(m.group(2) or m.group(3))
    return out

class PinMap(unittest.TestCase):
    def check(self, board, path):
        subs = substitutions(path)
        for sub, fn in pinmap.SUBSTITUTIONS.items():
            self.assertIn(sub, subs, "%s missing from %s" % (sub, path))
            pos = pinmap.FUNCTIONS[fn]
            self.assertEqual(subs[sub], pinmap.POSITION_GPIO[board][pos],
                             "%s: %s is GPIO%d but position %s carries GPIO%d" % (board, sub, subs[sub], pos, pinmap.POSITION_GPIO[board][pos]))
        self.assertEqual(set(subs), set(pinmap.SUBSTITUTIONS), "substitution list changed; update pinmap.py")

    def test_s2(self):
        self.check("s2", os.path.join(REPO, "esphome", "packages", "board-s2.yaml"))

    def test_c6(self):
        self.check("c6", os.path.join(REPO, "esphome", "packages", "board-c6.yaml"))

    def test_reserved_positions_have_no_function(self):
        for pos in pinmap.RESERVED:
            self.assertNotIn(pos, pinmap.FUNCTIONS.values())

if __name__ == "__main__":
    unittest.main()
