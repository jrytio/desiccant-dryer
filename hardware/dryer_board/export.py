# hardware/dryer_board/export.py
"""Everything the fab and the reviewer need, from a committed project, with kicad-cli. Every
file is named <PROJECT>-rev<REVISION>-..., so both boards' outputs share one directory."""
import csv, os, shutil, subprocess, zipfile
from . import kicad_env

GERBER_LAYERS = "F.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts"


def _cli(*args):
    return subprocess.run([kicad_env.kicad_cli()] + list(args), capture_output=True, text=True)


def jlc_cpl(kicad_csv, out_csv):
    """KiCad position CSV -> JLCPCB CPL. Mounting holes and test points carry no part, so
    they are dropped. Rotation is KiCad's; JLCPCB's viewer is where any per-footprint
    offset (SOT-23, SMA) is corrected before ordering."""
    with open(kicad_csv, newline="") as f, open(out_csv, "w", newline="") as g:
        r = csv.DictReader(f)
        w = csv.writer(g)
        w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        for row in r:
            if row["Ref"].startswith(("H", "TP")):
                continue
            w.writerow([row["Ref"], row["PosX"], row["PosY"], "Top" if row["Side"] == "top" else "Bottom", row["Rot"]])


def clean_bom(path):
    """KiCad appends "?" to a reference that does not end in a digit (J_24V is "unannotated"
    to it). The descriptive references are deliberate, so strip the "?" from the Designator column."""
    with open(path, newline="") as f:
        rows = list(csv.reader(f))
    for row in rows[1:]:
        row[1] = ",".join(d.strip().rstrip("?") for d in row[1].split(","))
    with open(path, "w", newline="") as f:
        csv.writer(f, quoting=csv.QUOTE_ALL, lineterminator="\n").writerows(rows)


def export_all(bd, project_dir, out_dir, docs_dir=None):
    sch = os.path.join(project_dir, bd.PROJECT + ".kicad_sch")
    pcb = os.path.join(project_dir, bd.PROJECT + ".kicad_pcb")
    stem = "%s-rev%s" % (bd.PROJECT, bd.REVISION)
    os.makedirs(out_dir, exist_ok=True)
    gerbers = os.path.join(out_dir, "gerbers-" + bd.SHORT)
    shutil.rmtree(gerbers, ignore_errors=True)
    os.makedirs(gerbers)
    paths = {}
    paths["erc"] = os.path.join(out_dir, stem + "-erc.rpt")
    _cli("sch", "erc", "--severity-all", "-o", paths["erc"], sch)
    paths["drc"] = os.path.join(out_dir, stem + "-drc.rpt")
    _cli("pcb", "drc", "--severity-all", "--refill-zones", "-o", paths["drc"], pcb)
    kicad_env.run_cli("pcb", "export", "gerbers", "-o", gerbers + "/", "-l", GERBER_LAYERS, "--check-zones", pcb)
    kicad_env.run_cli("pcb", "export", "drill", "-o", gerbers + "/", "--format", "excellon", "--excellon-units", "mm",
                      "--generate-map", "--map-format", "gerberx2", pcb)
    paths["gerber_zip"] = os.path.join(out_dir, stem + "-gerbers.zip")
    with zipfile.ZipFile(paths["gerber_zip"], "w", zipfile.ZIP_DEFLATED) as z:
        for name in sorted(os.listdir(gerbers)):
            z.write(os.path.join(gerbers, name), name)
    kpos = os.path.join(out_dir, stem + "-pos-kicad.csv")
    kicad_env.run_cli("pcb", "export", "pos", "--format", "csv", "--units", "mm", "--side", "front", "--exclude-dnp",
                      "-o", kpos, pcb)
    paths["cpl"] = os.path.join(out_dir, stem + "-cpl.csv")
    jlc_cpl(kpos, paths["cpl"])
    paths["bom"] = os.path.join(out_dir, stem + "-bom.csv")
    kicad_env.run_cli("sch", "export", "bom", "--fields", "Value,Reference,Footprint,LCSC",
                      "--labels", "Comment,Designator,Footprint,LCSC Part #", "--group-by", "Value,Footprint,LCSC",
                      "--exclude-dnp", "--ref-range-delimiter", "", "-o", paths["bom"], sch)
    clean_bom(paths["bom"])
    paths["schematic_pdf"] = os.path.join(out_dir, stem + "-schematic.pdf")
    kicad_env.run_cli("sch", "export", "pdf", "-o", paths["schematic_pdf"], sch)
    paths["top_svg"] = os.path.join(out_dir, stem + "-top.svg")
    kicad_env.run_cli("pcb", "export", "svg", "-l", "F.Cu,F.SilkS,F.Fab,Edge.Cuts", "--page-size-mode", "2",
                      "--exclude-drawing-sheet", "--mode-single", "--check-zones", "-o", paths["top_svg"], pcb)
    paths["render_top"] = os.path.join(out_dir, stem + "-render-top.png")
    kicad_env.run_cli("pcb", "render", "-o", paths["render_top"], "--width", "1600", "--height", "1240", pcb)
    paths["render_iso"] = os.path.join(out_dir, stem + "-render-iso.png")
    kicad_env.run_cli("pcb", "render", "-o", paths["render_iso"], "--width", "1600", "--height", "1200",
                      "--rotate", "-45,0,45", "--perspective", "--zoom", "0.9", pcb)
    if docs_dir:
        os.makedirs(docs_dir, exist_ok=True)
        for key, name in (("schematic_pdf", "schematic.pdf"), ("top_svg", "top.svg"),
                          ("render_top", "render-top.png"), ("render_iso", "render-iso.png")):
            shutil.copy(paths[key], os.path.join(docs_dir, bd.SHORT + "-" + name))
    return paths
