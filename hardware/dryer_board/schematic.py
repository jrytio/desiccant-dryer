# hardware/dryer_board/schematic.py
"""Write the schematic as a net-label grid: every symbol in its own cell, a global label on
every pin. KiCad 8 file format (version 20231120), which KiCad 10 reads."""
import os, re, shutil, tempfile, uuid
from . import circuit, libs, sexp, kicad_env

NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "https://github.com/jrytio/desiccant-dryer/hardware")
CELL = 38.1
COLS = 10
ORIGIN = 25.4
ROOT = None  # set in write()

def uuid_for(key):
    return str(uuid.uuid5(NAMESPACE, "dryer/" + key))

def _q(s):
    return '"%s"' % str(s).replace("\\", "\\\\").replace('"', '\\"')

def _prop(name, value, x, y, hide=False, size=1.27):
    h = " (hide yes)" if hide else ""
    return '(property %s %s (at %.2f %.2f 0) (effects (font (size %s %s))%s))' % (_q(name), _q(value), x, y, size, size, h)

def _symbol_instance(part, cx, cy):
    props = [_prop("Reference", part.ref, cx, cy - 2.54), _prop("Value", part.value, cx, cy + 2.54),
             _prop("Footprint", part.footprint, cx, cy, hide=True), _prop("Datasheet", "~", cx, cy, hide=True),
             _prop("LCSC", part.lcsc, cx, cy, hide=True), _prop("Description", part.description, cx, cy, hide=True)]
    if part.hand_fit:
        props.append(_prop("Hand fit", "yes", cx, cy, hide=True))
    pins = " ".join('(pin %s (uuid %s))' % (_q(n), _q(uuid_for(part.ref + "/pin/" + n))) for n in sorted(libs.symbol_pins(part.symbol)))
    in_bom = "no" if part.ref.startswith(("#", "H")) else "yes"
    return ('(symbol (lib_id %s) (at %.2f %.2f 0) (unit 1) (exclude_from_sim no) (in_bom %s) (on_board yes) (dnp no) (uuid %s) %s %s '
            '(instances (project %s (path %s (reference %s) (unit 1)))))'
            % (_q(part.symbol), cx, cy, in_bom, _q(uuid_for(part.ref)), " ".join(props), pins,
               _q(circuit.PROJECT), _q("/" + ROOT), _q(part.ref)))

_LABEL_ANGLE = {0: 180, 180: 0, 90: 270, 270: 90}

def _label(net, x, y, angle, key):
    return ('(global_label %s (shape input) (at %.2f %.2f %d) (effects (font (size 1.27 1.27)) (justify left)) (uuid %s))'
            % (_q(net), x, y, angle, _q(uuid_for("label/" + key))))

def _no_connect(x, y, key):
    return '(no_connect (at %.2f %.2f) (uuid %s))' % (x, y, _q(uuid_for("nc/" + key)))

def _cell(i):
    return ORIGIN + (i % COLS) * CELL, ORIGIN + (i // COLS) * CELL

def write(project_dir):
    global ROOT
    ROOT = uuid_for("root")
    body, embedded, seen = [], [], set()
    for i, part in enumerate(circuit.PARTS):
        cx, cy = _cell(i)
        if part.symbol not in seen:
            seen.add(part.symbol); embedded.append(sexp.dump(libs.load_symbol(part.symbol), indent=None))
        body.append(_symbol_instance(part, cx, cy))
        pins = libs.symbol_pins(part.symbol)
        for number, (px, py, angle, _etype) in sorted(pins.items()):
            x, y = cx + px, cy - py
            net = part.pins.get(number, circuit.NC)
            key = part.ref + "/" + number
            if net == circuit.NC:
                body.append(_no_connect(x, y, key))
            else:
                body.append(_label(net, x, y, _LABEL_ANGLE[angle % 360], key))
    doc = ('(kicad_sch (version 20231120) (generator "dryer_board") (generator_version "1.0") (uuid %s) (paper "A2")\n'
           '(title_block (title %s) (rev %s) (company "AGPL-3.0, github.com/jrytio/desiccant-dryer"))\n'
           '(lib_symbols %s)\n%s\n(sheet_instances (path "/" (page "1"))))\n'
           % (_q(ROOT), _q(circuit.TITLE), _q(circuit.REVISION), "\n".join(embedded), "\n".join(body)))
    path = os.path.join(project_dir, circuit.PROJECT + ".kicad_sch")
    with open(path, "w", encoding="utf-8") as f:
        f.write(doc)
    return path

def write_lib_tables(project_dir):
    """Project-local tables for the stock libraries the parts use, plus the local footprint
    library. kicad-cli has no global tables in CI, so these are required for ERC and DRC."""
    sym_libs = sorted({libs.split(p.symbol)[0] for p in circuit.PARTS})
    fp_libs = sorted({libs.split(p.footprint)[0] for p in circuit.PARTS if p.footprint and not p.footprint.startswith("dryer:")})
    with open(os.path.join(project_dir, "sym-lib-table"), "w", encoding="utf-8") as f:
        f.write("(sym_lib_table (version 7)\n")
        for lib in sym_libs:
            f.write('  (lib (name "%s") (type "KiCad") (uri "${KICAD10_SYMBOL_DIR}/%s.kicad_sym") (options "") (descr ""))\n' % (lib, lib))
        f.write(")\n")
    with open(os.path.join(project_dir, "fp-lib-table"), "w", encoding="utf-8") as f:
        f.write("(fp_lib_table (version 7)\n")
        for lib in fp_libs:
            f.write('  (lib (name "%s") (type "KiCad") (uri "${KICAD10_FOOTPRINT_DIR}/%s.pretty") (options "") (descr ""))\n' % (lib, lib))
        f.write('  (lib (name "dryer") (type "KiCad") (uri "${KIPRJMOD}/lib/dryer.pretty") (options "") (descr "local footprints"))\n')
        f.write(")\n")
    os.makedirs(os.path.join(project_dir, "lib", "dryer.pretty"), exist_ok=True)
    # kicad-cli only reads the project-local tables when a project file sits beside the sheet.
    pro = os.path.join(project_dir, circuit.PROJECT + ".kicad_pro")
    if not os.path.exists(pro):
        with open(pro, "w", encoding="utf-8") as f:
            f.write("{}\n")

def netlist_from_kicad(sch_path):
    # In a temporary directory, so reading a committed sheet leaves its project directory clean.
    tmp = tempfile.mkdtemp()
    try:
        out_path = os.path.join(tmp, "netlist.net")
        kicad_env.run_cli("sch", "export", "netlist", "--format", "kicadsexpr", "-o", out_path, sch_path)
        with open(out_path, encoding="utf-8") as f:
            tree = sexp.parse(f.read())
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    nets = {}
    for net in sexp.find_all(sexp.find(tree, "nets"), "net"):
        name = sexp.find(net, "name")[1]
        nodes = {(sexp.find(n, "ref")[1], sexp.find(n, "pin")[1]) for n in sexp.find_all(net, "node")}
        nodes = {(r, p) for r, p in nodes if not r.startswith("#")}
        if len(nodes) > 1:
            nets[name] = nodes
    return nets
