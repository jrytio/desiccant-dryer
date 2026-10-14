# hardware/dryer_board/project.py
"""The KiCad project file (netclasses, DRC severities, board rules) and the custom DRC rules.
Net settings use the schema KiCad 10 writes (net_settings meta version 5); an older or
sparser schema is silently ignored by kicad-cli, which is how a rule can fail to apply."""
import json, os
from . import circuit

# The relay NC pad (4) carries no net, so no copper ever reaches it, but COM connects to it
# whenever the coil is off: it is live mains that the netclass rules cannot see. The last
# rule names it directly; it comes after the relay_pads relaxation so that cannot override it.
# memberOfFootprint('K*') does not match in KiCad 10.0.6, so both relays are named.
RULES = """(version 1)
(rule "mains track width"
  (condition "A.NetClass == 'MAINS'")
  (constraint track_width (min 1.5mm)))
(rule "mains to board edge"
  (condition "A.NetClass == 'MAINS'")
  (constraint edge_clearance (min 1mm)))
(rule "mains to selv"
  (condition "A.NetClass == 'MAINS' && B.NetClass != 'MAINS'")
  (constraint clearance (min 6mm)))
(rule "mains to selv at relay pads"
  (condition "A.NetClass == 'MAINS' && B.NetClass != 'MAINS' && A.insideArea('relay_pads')")
  (constraint clearance (min 3.5mm)))
(rule "relay NC contact is live"
  (condition "(A.memberOfFootprint('K1') || A.memberOfFootprint('K2')) && A.Pad_Number == '4' && B.NetClass != 'MAINS'")
  (constraint clearance (min 6mm)))
"""


def _class(name, track, clearance, via, drill, priority):
    return {"bus_width": 12, "clearance": clearance, "diff_pair_gap": 0.25, "diff_pair_via_gap": 0.25,
            "diff_pair_width": 0.2, "line_style": 0, "microvia_diameter": 0.3, "microvia_drill": 0.1,
            "name": name, "pcb_color": "rgba(0, 0, 0, 0.000)", "priority": priority,
            "schematic_color": "rgba(0, 0, 0, 0.000)", "track_width": track, "via_diameter": via,
            "via_drill": drill, "wire_width": 6}


def netclass_patterns():
    out = []
    for name, (_t, _c, _v, _d, patterns) in circuit.NETCLASSES.items():
        for p in patterns:
            out.append((p, name))
    return out


def project_dict():
    classes = []
    for i, (name, (track, clearance, via, drill, _p)) in enumerate(circuit.NETCLASSES.items()):
        classes.append(_class(name, track, clearance, via, drill, 2147483647 if name == "Default" else i))
    return {
        "board": {"design_settings": {
            "rules": {"min_clearance": 0.2, "min_track_width": 0.2, "min_copper_edge_clearance": 0.5,
                      "min_via_diameter": 0.6, "min_via_annular_width": 0.15, "min_through_hole_diameter": 0.3,
                      "min_hole_clearance": 0.25, "min_hole_to_hole": 0.5, "min_silk_clearance": 0.0,
                      # One spoke is a sound joint for these low-current SMD pads; the
                      # default of 2 flags pads the pour reaches from one side only.
                      "min_resolved_spokes": 1},
            # Silk-over-pad and silk-overlap are cosmetic and the fab clips silk on pads;
            # ignoring them keeps "DRC clean" about copper, clearance and connectivity.
            "rule_severities": {"track_dangling": "warning", "via_dangling": "warning",
                                "silk_overlap": "ignore", "silk_over_copper": "ignore",
                                "silk_edge_clearance": "ignore", "lib_footprint_issues": "ignore",
                                "lib_footprint_mismatch": "ignore"}}},
        "meta": {"filename": circuit.PROJECT + ".kicad_pro", "version": 3},
        "net_settings": {"classes": classes, "meta": {"version": 5}, "net_colors": None,
                         "netclass_assignments": None,
                         "netclass_patterns": [{"netclass": c, "pattern": p} for p, c in netclass_patterns()]},
        "text_variables": {"REVISION": circuit.REVISION},
    }


def write(project_dir):
    with open(os.path.join(project_dir, circuit.PROJECT + ".kicad_pro"), "w", encoding="utf-8") as f:
        json.dump(project_dict(), f, indent=2, sort_keys=True)
        f.write("\n")
    with open(os.path.join(project_dir, circuit.PROJECT + ".kicad_dru"), "w", encoding="utf-8") as f:
        f.write(RULES)
