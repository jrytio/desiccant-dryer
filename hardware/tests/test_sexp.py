import unittest
from dryer_board import sexp

class Sexp(unittest.TestCase):
    def test_roundtrip_quoted_and_bare(self):
        src = '(pin passive line (at 0 3.81 270) (name "~" (effects (font (size 1.27 1.27)))) (number "1"))'
        tree = sexp.parse(src)
        self.assertEqual(tree[0], "pin")
        self.assertEqual(sexp.find(tree, "number")[1], "1")
        self.assertIsInstance(sexp.find(tree, "number")[1], sexp.Str)
        self.assertEqual(sexp.dump(tree, indent=None), src)

    def test_escapes(self):
        tree = sexp.parse(r'(property "Value" "1 \"kΩ\" x")')
        self.assertEqual(tree[2], '1 "kΩ" x')
        self.assertEqual(sexp.dump(tree, indent=None), r'(property "Value" "1 \"kΩ\" x")')

    def test_find_all(self):
        tree = sexp.parse('(a (pin 1) (pin 2) (x))')
        self.assertEqual([p[1] for p in sexp.find_all(tree, "pin")], ["1", "2"])
        self.assertIsNone(sexp.find(tree, "nope"))
