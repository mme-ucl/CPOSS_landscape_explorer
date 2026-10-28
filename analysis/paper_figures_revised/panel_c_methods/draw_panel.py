"""Paired vector pies with independent archive-record and energy-model area scales."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys

os.environ.setdefault("MPLCONFIGDIR", "/tmp/cposs-matplotlib")
import numpy as np
import pandas as pd
from matplotlib.patches import Circle, Patch, Wedge

BASE = Path(__file__).resolve().parent.parent
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))
from make_figure import COOL, WARM, INK, MUTED, GRID

MEASURES = {
    "records": {"heading": "Structures", "total": "total_records", "rigid": "rigid_records",
                "flexible": "flexible_records", "key": [10000, 100000]},
    "models": {"heading": "Models", "total": "energy_models", "rigid": "rigid_models",
               "flexible": "flexible_models", "key": [10, 100]},
}


def load_summary():
    summary = json.loads((HERE / "classification_summary.json").read_text())
    counts = pd.read_csv(HERE / "matrix_counts.csv")
    assert counts.total_records.sum() == summary["classified_archived_records"]
    assert counts.energy_models.sum() == summary["classified_models"]
    assert np.array_equal(counts.rigid_records + counts.flexible_records, counts.total_records)
    assert np.array_equal(counts.rigid_models + counts.flexible_models, counts.energy_models)
    return summary, counts


def draw_panel(fig, matrix_rect, size_rect, *, legend_anchor):
    summary, counts = load_summary()
    ax = fig.add_axes(matrix_rect)
    ax.set(xlim=(0, 4.4), ylim=(0, 3.0))
    ax.set_aspect("equal", adjustable="box")
    ax.axis("off")
    units_pt = min(matrix_rect[2] * fig.get_figwidth() * 72 / 4.4,
                   matrix_rect[3] * fig.get_figheight() * 72 / 3.0)
    max_radius = .34
    scales = {name: np.pi * (max_radius * units_pt) ** 2 / counts[spec["total"]].max()
              for name, spec in MEASURES.items()}
    ax.plot([2.2, 2.2], [0, 2.80], color=GRID, lw=.65, zorder=0)
    ax.plot([0, 4.4], [1.35, 1.35], color=GRID, lw=.65, zorder=0)
    for x, label in [(1.1, "MOLPAK"), (3.3, "CrystalPredictor")]:
        ax.text(x, 2.94, label, ha="center", va="bottom", fontsize=7, color=INK)
    for origin in (0, 2.2):
        for offset, spec in zip((.55, 1.65), MEASURES.values()):
            ax.text(origin + offset, 2.62, spec["heading"], ha="center", va="bottom", fontsize=6.2, color=MUTED)
    for y, label in [(2.05, "DMAREL"), (.80, "DMACRYS")]:
        ax.text(-.14, y, label, ha="center", va="center", rotation=90, fontsize=7, color=INK)
    radii, callouts = [], []
    for row in counts.to_dict("records"):
        origin = 0 if row["search_program"] == "MOLPAK" else 2.2
        y = 2.05 if row["refinement_engine"] == "DMAREL" else .80
        for (measure, spec), offset in zip(MEASURES.items(), (.55, 1.65)):
            total, rigid, flexible = (int(row[spec[key]]) for key in ("total", "rigid", "flexible"))
            if total == 0:
                continue
            x = origin + offset
            radius = np.sqrt(total * scales[measure] / np.pi) / units_pt
            rigid_angle = 360 * rigid / total
            if rigid:
                ax.add_patch(Wedge((x, y), radius, 90, 90 + rigid_angle,
                                   facecolor=COOL, edgecolor="none", zorder=3))
            if flexible:
                ax.add_patch(Wedge((x, y), radius, 90 + rigid_angle, 450,
                                   facecolor=WARM, edgecolor="none", zorder=3))
            ax.add_patch(Circle((x, y), radius, facecolor="none", edgecolor=INK, lw=.5, zorder=4))
            # Each label is anchored to the actual flexible-sector midpoint.
            theta = np.deg2rad(450 - (360 * flexible / total) / 2)
            target = (x + radius * np.cos(theta), y + radius * np.sin(theta))
            label_y = y - .54
            elbow_x = x + radius + .06
            endpoint_y = y - .40
            ax.plot([target[0], elbow_x, elbow_x, x],
                    [target[1], target[1], endpoint_y, endpoint_y],
                    color=MUTED, lw=.55, solid_joinstyle="round", zorder=5)
            ax.text(x, label_y, f"{flexible:,}", ha="center", va="center", fontsize=6.5, color=INK, zorder=5)
            radii.append({"search": row["search_program"], "engine": row["refinement_engine"],
                          "measure": measure, "count": total, "flexible_count": flexible,
                          "radius_pt": float(radius * units_pt)})
            callouts.append({"search": row["search_program"], "engine": row["refinement_engine"],
                             "measure": measure, "flexible_count": flexible,
                             "text": f"{flexible:,}", "sector_angle_deg": 360 * flexible / total})
    fig.legend(handles=[Patch(facecolor=COOL, label="Rigid"), Patch(facecolor=WARM, label="Flexible")],
               frameon=False, loc="center", bbox_to_anchor=legend_anchor, ncol=2,
               fontsize=7, handlelength=1.1, columnspacing=1.5, handletextpad=.5)
    # Two reference rows, each using its measure's exact physical area scale.
    key = fig.add_axes(size_rect)
    width_pt = size_rect[2] * fig.get_figwidth() * 72
    height_pt = size_rect[3] * fig.get_figheight() * 72
    key.set(xlim=(0, width_pt), ylim=(0, height_pt))
    key.set_aspect("equal", adjustable="box")
    key.axis("off")
    key_radii = []
    for (measure, spec), fraction_y in zip(MEASURES.items(), (.74, .25)):
        cy = fraction_y * height_pt
        key.text(0, cy, spec["heading"], fontsize=6.2, color=MUTED, ha="left", va="center")
        for fraction_x, value in zip((.38, .72), spec["key"]):
            cx = fraction_x * width_pt
            radius = np.sqrt(value * scales[measure] / np.pi)
            if radius > min(cx, width_pt - cx, cy, height_pt - cy):
                raise ValueError("The quantitative size keys must contain complete circles")
            key.add_patch(Circle((cx, cy), radius, facecolor="none", edgecolor=MUTED, lw=.65))
            key.text(cx + radius + 5, cy, f"{value:,}", fontsize=6.2, color=MUTED, va="center", ha="left")
            key_radii.append({"measure": measure, "count": value, "radius_pt": float(radius)})
    for entry in radii + key_radii:
        assert np.isclose(np.pi * entry["radius_pt"] ** 2 / entry["count"], scales[entry["measure"]])
    return summary | {
        "title": "Search and refinement methods", "layout": "paired structures/models pies in each cell",
        "colours": {"Rigid": COOL, "Flexible": WARM}, "row_label_rotation_deg": 90,
        "bubble_area_pt2_per_unit": {k: float(v) for k, v in scales.items()},
        "bubble_radii": radii, "size_key_radii": key_radii, "flexible_callouts": callouts,
        "size_key_counts": {name: spec["key"] for name, spec in MEASURES.items()},
        "legend_scope": "rigid versus flexible molecular refinement; numeric callouts give flexible counts",
    }


def main():
    from make_figure import helvetica
    from matplotlib import pyplot as plt
    from matplotlib.text import Text
    helvetica(Path("/System/Library/Fonts/Helvetica.ttc"))
    fig = plt.figure(figsize=(3.65, 3.25), facecolor="white")
    fig.text(.04, .97, "C", fontsize=9, fontweight="bold", va="top")
    fig.text(.12, .97, "Search and refinement methods", fontsize=9, fontweight="bold", va="top")
    validation = draw_panel(fig, [.13, .30, .85, .55], [.055, .025, .93, .18], legend_anchor=(.55, .245))
    for text in fig.findobj(Text):
        text.set_fontsize(text.get_fontsize() * 1.55)
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    for text in fig.findobj(Text):
        if text.get_visible() and text.get_text():
            b = text.get_window_extent(renderer)
            assert b.x0 >= -1 and b.y0 >= -1 and b.x1 <= fig.bbox.width + 1 and b.y1 <= fig.bbox.height + 1, text.get_text()
    fig.savefig(BASE / "output/pdf/panel_c_search_refinement.pdf", metadata={"CreationDate": None, "ModDate": None})
    fig.savefig(BASE / "figures/panel_c_search_refinement.png", dpi=300)
    (HERE / "panel_validation.json").write_text(json.dumps(validation, indent=2) + "\n")
    plt.close(fig)


if __name__ == "__main__":
    main()
