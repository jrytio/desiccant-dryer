# hardware/dryer_board/boards.py
"""The boards the generator builds. Each is a module with the same names (PROJECT, SHORT,
TITLE, REVISION, PARTS, NETCLASSES, MAINS_NETS, RULES, the placement constants, rule_areas(),
edge_outlines(), check()); the generator modules take one as `bd`."""
from . import controller, mains

BOARDS = (controller, mains)

def by_name(name):
    """A board by its SHORT name ("controller", "mains") or PROJECT name."""
    for bd in BOARDS:
        if name in (bd.SHORT, bd.PROJECT):
            return bd
    raise KeyError("no board %r; boards: %s" % (name, ", ".join(b.SHORT for b in BOARDS)))
