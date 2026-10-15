"""Where KiCad lives. macOS app bundle first, then the kicad/kicad Docker image layout,
then anything on PATH. Override with KICAD_CLI, KICAD_SYMBOL_DIR, KICAD_FOOTPRINT_DIR."""
import os, shutil, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
HARDWARE_DIR = os.path.join(REPO, "hardware")
OUT_DIR = os.path.join(HARDWARE_DIR, "out")
# The local footprints (dryer:*), shared by both boards; schematic.write_lib_tables copies them
# into each project's lib/dryer.pretty so a project opens on its own.
LIB_DIR = os.path.join(HARDWARE_DIR, "lib", "dryer.pretty")

def project_dir(bd):
    """The committed KiCad project directory of a board (hardware/<PROJECT>/)."""
    return os.path.join(HARDWARE_DIR, bd.PROJECT)

_MAC_APP = "/Applications/KiCad/KiCad.app/Contents"
_CANDIDATES = {
    "cli": [os.environ.get("KICAD_CLI", ""), _MAC_APP + "/MacOS/kicad-cli", "/usr/bin/kicad-cli"],
    "symbols": [os.environ.get("KICAD_SYMBOL_DIR", ""), _MAC_APP + "/SharedSupport/symbols", "/usr/share/kicad/symbols"],
    "footprints": [os.environ.get("KICAD_FOOTPRINT_DIR", ""), _MAC_APP + "/SharedSupport/footprints", "/usr/share/kicad/footprints"],
}

def _first(kind, test):
    for c in _CANDIDATES[kind]:
        if c and test(c):
            return c
    found = shutil.which("kicad-cli") if kind == "cli" else None
    if found:
        return found
    raise FileNotFoundError("KiCad %s not found; set KICAD_CLI / KICAD_SYMBOL_DIR / KICAD_FOOTPRINT_DIR" % kind)

def kicad_cli():
    return _first("cli", os.path.isfile)

def symbol_dir():
    return _first("symbols", os.path.isdir)

def footprint_dir():
    return _first("footprints", os.path.isdir)

def run_cli(*args, cwd=None):
    """Run kicad-cli with args; raise with stdout+stderr on failure."""
    proc = subprocess.run([kicad_cli(), *args], cwd=cwd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError("kicad-cli %s failed (%d):\n%s\n%s" % (" ".join(args), proc.returncode, proc.stdout, proc.stderr))
    return proc
