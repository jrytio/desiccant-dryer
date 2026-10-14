"""Read KiCad's stock symbol and footprint libraries. A derived symbol (`extends`) is
flattened the way KiCad embeds it in a schematic: the parent's drawing and pins with the
child's properties, units renamed to the child's name."""
import os, functools
from . import sexp, kicad_env


def split(lib_id):
    lib, name = lib_id.split(":", 1)
    return lib, name


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


@functools.lru_cache(maxsize=None)
def _library(lib):
    path = os.path.join(kicad_env.symbol_dir(), lib + ".kicad_sym")
    return sexp.parse(_read(path))


def _raw_symbol(lib, name):
    for node in _library(lib)[1:]:
        if isinstance(node, list) and node and node[0] == "symbol" and node[1] == name:
            return node
    raise KeyError("symbol %s:%s not in the stock libraries" % (lib, name))


def load_symbol(lib_id):
    lib, name = split(lib_id)
    sym = list(_raw_symbol(lib, name))
    ext = sexp.find(sym, "extends")
    if ext:
        parent_name = ext[1]
        parent = list(_raw_symbol(lib, parent_name))
        child_props = {p[1]: p for p in sexp.find_all(sym, "property")}
        merged = []
        seen = set()
        for node in parent:
            if isinstance(node, list) and node and node[0] == "property":
                merged.append(child_props.get(node[1], node)); seen.add(node[1])
            elif isinstance(node, list) and node and node[0] == "symbol":
                unit = list(node); unit[1] = sexp.Str(name + node[1][len(parent_name):]); merged.append(unit)
            else:
                merged.append(node)
        extra = [p for k, p in child_props.items() if k not in seen]
        last = max(i for i, n in enumerate(merged) if isinstance(n, list) and n and n[0] == "property")
        sym = merged[:last + 1] + extra + merged[last + 1:]
    sym[1] = sexp.Str(lib_id)
    return sym


def symbol_pins(lib_id):
    out = {}
    for unit in sexp.find_all(load_symbol(lib_id), "symbol"):
        for pin in sexp.find_all(unit, "pin"):
            at = sexp.find(pin, "at")
            number = sexp.find(pin, "number")[1]
            out[number] = (float(at[1]), float(at[2]), int(float(at[3])), pin[1])
    return out


def footprint_path(lib_id):
    lib, name = split(lib_id)
    if lib == "dryer":
        base = os.path.join(kicad_env.PROJECT_DIR, "lib", "dryer.pretty")
    else:
        base = os.path.join(kicad_env.footprint_dir(), lib + ".pretty")
    if not os.path.isfile(os.path.join(base, name + ".kicad_mod")):
        raise FileNotFoundError("footprint %s not found under %s" % (lib_id, base))
    return base


@functools.lru_cache(maxsize=None)
def _footprint(lib_id):
    base = footprint_path(lib_id)
    return sexp.parse(_read(os.path.join(base, split(lib_id)[1] + ".kicad_mod")))


def footprint_pad_positions(lib_id):
    """pad number -> (x, y) mm in the footprint's frame (KiCad: y down). Unnumbered pads are skipped."""
    out = {}
    for pad in sexp.find_all(_footprint(lib_id), "pad"):
        if pad[1] == "":
            continue
        at = sexp.find(pad, "at")
        out[pad[1]] = (float(at[1]), float(at[2]))
    return out


def footprint_pads(lib_id):
    return set(footprint_pad_positions(lib_id))
