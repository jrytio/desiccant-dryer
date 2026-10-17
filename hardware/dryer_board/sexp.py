"""Minimal S-expression support for KiCad files. Quoted strings parse to Str so they
are written back quoted; bare tokens stay str."""
import re

class Str(str):
    """A token that was (and must be) double-quoted."""

_TOKEN = re.compile(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()"]+')

def _unescape(s):
    return s.replace('\\"', '"').replace("\\\\", "\\")

def _escape(s):
    return s.replace("\\", "\\\\").replace('"', '\\"')

def parse(text):
    stack = [[]]
    for tok in _TOKEN.findall(text):
        if tok == "(":
            stack.append([])
        elif tok == ")":
            done = stack.pop()
            stack[-1].append(done)
        elif tok.startswith('"'):
            stack[-1].append(Str(_unescape(tok[1:-1])))
        else:
            stack[-1].append(tok)
    if len(stack) != 1 or len(stack[0]) != 1:
        raise ValueError("unbalanced S-expression")
    return stack[0][0]

def _atom(a):
    if isinstance(a, Str):
        return '"%s"' % _escape(a)
    return a

def dump(node, indent=0):
    """indent=None gives one line; an int gives KiCad-like one-child-per-line output."""
    if not isinstance(node, list):
        return _atom(node)
    if indent is None or not any(isinstance(c, list) for c in node):
        return "(" + " ".join(dump(c, None) for c in node) + ")"
    pad = "\t" * (indent + 1)
    head = [dump(c, None) for c in node if not isinstance(c, list)]
    kids = [pad + dump(c, indent + 1) for c in node if isinstance(c, list)]
    return "(" + " ".join(head) + "\n" + "\n".join(kids) + "\n" + "\t" * indent + ")"

def find(node, key):
    for c in node:
        if isinstance(c, list) and c and c[0] == key:
            return c
    return None

def find_all(node, key):
    return [c for c in node if isinstance(c, list) and c and c[0] == key]
