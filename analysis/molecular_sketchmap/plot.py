#!/usr/bin/env python3
"""Publication A4 sketch-map with chalky Tachyon ambient-occlusion callouts."""
import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import tempfile
import textwrap
from zoneinfo import ZoneInfo

os.environ.setdefault("MPLCONFIGDIR", "/tmp/cposs-sketchmap-matplotlib")
import matplotlib
matplotlib.use("Agg")
from matplotlib import font_manager, pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, LogNorm
from matplotlib.lines import Line2D
from matplotlib.patches import ConnectionPatch
from matplotlib.text import Text
import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment

from extract_molecules import BASE, write_json

INK, MUTED = "#172F3D", "#566974"


def helvetica(path):
    from fontTools.ttLib import TTCollection
    if not path.exists(): raise FileNotFoundError("Actual Helvetica is required; supply --font")
    fonts = []
    if path.suffix.lower() == ".ttc":
        target = Path(tempfile.gettempdir()) / "cposs-sketchmap-helvetica"; target.mkdir(exist_ok=True)
        for font in TTCollection(str(path)).fonts:
            if font["name"].getDebugName(1) == "Helvetica" and font["name"].getDebugName(2) in {"Regular", "Bold", "Oblique", "Bold Oblique"}:
                file = target / (font["name"].getDebugName(6) + ".ttf"); font.save(str(file)); fonts.append(file)
    else:
        fonts = [path] + [p for p in path.parent.glob("Helvetica*.ttf") if p != path]
    for font in fonts: font_manager.fontManager.addfont(str(font))
    plt.rcParams.update({"font.family": "Helvetica", "font.sans-serif": ["Helvetica"], "font.size": 8, "text.color": INK, "axes.labelcolor": INK, "axes.edgecolor": "#A5B0B6", "axes.linewidth": .6, "xtick.color": MUTED, "ytick.color": MUTED, "pdf.fonttype": 42, "ps.fonttype": 42, "savefig.facecolor": "white"})
    return {"source": str(path), "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "embedded_faces": [p.name for p in fonts]}


def draw_molecule(ax, record):
    render = BASE / "figures/callouts_ao" / (record["dataset_id"] + ".png")
    if not render.exists():
        raise FileNotFoundError(
            "Ambient-occlusion callout missing; run render_callouts_tachyon.py: " + str(render)
        )
    # PDF keeps the native ray-traced pixels rather than downsampling to the
    # interactive figure's display DPI. PNG export still uses its own 300 DPI.
    ax.imshow(plt.imread(render), interpolation="none")
    ax.axis("off")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--font", type=Path, default=Path("/System/Library/Fonts/Helvetica.ttc"))
    args = parser.parse_args()
    font = helvetica(args.font)
    all_data = pd.read_csv(BASE / "tables/dataset_embedding.csv")
    frame = all_data[all_data.included].sort_values("dataset_id").reset_index(drop=True)
    descriptors = np.load(BASE / "data/molecular_descriptors.npz")
    if list(descriptors["dataset_ids"]) != list(frame.dataset_id): raise AssertionError("Descriptor/map ordering mismatch")
    embedding = frame[["sketchmap_x", "sketchmap_y"]].to_numpy()
    anchors = np.array([[.13,.85],[.50,.85],[.87,.85],[.92,.52],[.87,.235],[.50,.235],[.13,.235],[.08,.52]])
    selection=json.loads((BASE/"callout_selection.json").read_text())
    rendering=json.loads((BASE/"data/tachyon_rendering.json").read_text())
    if selection["mode"]!="curated_experimental_compounds":raise ValueError("Unknown callout-selection rule")
    indices=[int(frame.index[frame.dataset_id==identifier][0]) for identifier in selection["dataset_ids"]]
    experimental=pd.read_csv(BASE/"inputs/callout_experimental_references.csv")
    if any(not experimental.dataset_id.eq(identifier).any() for identifier in selection["dataset_ids"]):
        raise ValueError("Every curated callout must have explicit experimental crystal references")
    map_rect = [.18,.31,.64,.45]
    centre = embedding.mean(axis=0)
    span = max(np.ptp(embedding[:,0]), np.ptp(embedding[:,1]))*1.18
    limits = np.array([centre-span/2,centre+span/2])
    normalized = (embedding-limits[0])/span
    page_xy = normalized*np.array(map_rect[2:])+np.array(map_rect[:2])
    assignment, positions = linear_sum_assignment(np.sum((page_xy[indices,None,:]-anchors[None,:,:])**2,axis=2))
    callouts = [(indices[i], int(j)) for i,j in zip(assignment,positions)]
    palette = LinearSegmentedColormap.from_list("CPOSS_Plasma_truncated",plt.get_cmap("plasma")(np.linspace(0,.88,256)))
    norm = LogNorm(vmin=float(frame.selected_molar_mass_g_mol.min()), vmax=float(frame.selected_molar_mass_g_mol.max()))
    fig = plt.figure(figsize=(210/25.4,297/25.4),facecolor="white")
    ax = fig.add_axes(map_rect)
    ax.set_facecolor("none")
    ax.set_xlim(limits[:,0]); ax.set_ylim(limits[:,1]); ax.set_aspect("equal",adjustable="box")
    # Small points drawn last so large datasets do not hide their centres.
    order = np.argsort(-frame.structure_count.to_numpy())
    conflicts = frame.formula_validation.ne("matches_full_unit_cell_stoichiometry").to_numpy()
    edge = np.where(conflicts,"#172F3D","white")
    scatter = ax.scatter(embedding[order,0],embedding[order,1],s=frame.marker_area_pt2.to_numpy()[order],c=frame.selected_molar_mass_g_mol.to_numpy()[order],cmap=palette,norm=norm,alpha=.88,edgecolors=edge[order],linewidths=np.where(conflicts[order],.8,.32),zorder=4)
    ax.set_xticks([]); ax.set_yticks([])
    ax.set_xlabel("sketch-map 1",fontsize=8,labelpad=5); ax.set_ylabel("sketch-map 2",fontsize=8,labelpad=5)
    for spine in ax.spines.values(): spine.set_color("#A5B0B6")
    callout_rows = []
    for index, anchor_index in callouts:
        row = frame.iloc[index]
        record = json.loads((BASE / "molecules" / (row.dataset_id+".json")).read_text())
        x,y = anchors[anchor_index]
        width, height = (.15,.090) if anchor_index in {3,7} else (.245,.100)
        molecule_ax = fig.add_axes([x-width/2,y-height/2,width,height])
        draw_molecule(molecule_ax, record)
        # Callouts sit outside the map; leaders end at actual, unjittered points.
        title = row.dataset_name
        if len(title)>48: title=row.dataset_id
        label = "\n".join(textwrap.wrap(str(title),27))
        line_count = len(label.splitlines())
        if anchor_index in {0,1,2}: start = (x,y-height/2-.006-.010*line_count-.014)
        elif anchor_index in {4,5,6}:
            # Route beneath the x-axis label, entering away from its central text.
            initial = (x,y+height/2+.004)
            entry_x = {4:.75,5:.31,6:.20}[anchor_index]
            start = (entry_x,map_rect[1]+.002)
            knee = (entry_x,initial[1])
            fig.add_artist(Line2D([initial[0],knee[0],start[0]],[initial[1],knee[1],start[1]],transform=fig.transFigure,color="#7A858D",lw=.65,zorder=-.5))
        elif anchor_index == 3: start = (x-width/2,y)
        else:
            # White-background renders stay outside the map and its y label.
            # Route the left leader beneath the label rather than across it.
            initial = (x+width/2,y)
            knee = (initial[0],map_rect[1]+.175)
            start = (map_rect[0]+.002,knee[1])
            fig.add_artist(Line2D([initial[0],knee[0],start[0]],[initial[1],knee[1],start[1]],transform=fig.transFigure,color="#7A858D",lw=.65,zorder=-.5))
        line = ConnectionPatch(xyA=start,coordsA=fig.transFigure,xyB=embedding[index],coordsB=ax.transData,arrowstyle="-",lw=.65,color="#7A858D",zorder=-.5,shrinkA=0,shrinkB=3)
        fig.add_artist(line)
        fig.text(x,y-height/2-.006,label,ha="center",va="top",fontsize=7.0,weight="bold")
        fig.text(x,y-height/2-.006-.010*line_count,f"{int(row.structure_count):,} archived files",ha="center",va="top",fontsize=6.2,color=MUTED)
        evidence=next(r for r in selection["molecules"] if r["dataset_id"]==row.dataset_id)
        callout_rows.append({"dataset_id":row.dataset_id,"dataset_name":row.dataset_name,"selection":evidence["selection_reason"],"csd_refcode":evidence["csd_refcode"],"experimental_reference_count":evidence["experimental_reference_count"],"experimental_evidence_table":"inputs/callout_experimental_references.csv","geometry_scope":selection["geometry_scope"],"renderer":rendering["renderer"]+"; matte ambient-occlusion ball-and-stick","anchor_index":anchor_index,"sketchmap_x":row.sketchmap_x,"sketchmap_y":row.sketchmap_y,"selected_formula":row.selected_formula,"structure_count":row.structure_count})
    # Quantitative legends in the free lower margin.
    cax = fig.add_axes([.31,.082,.38,.008])
    colorbar = fig.colorbar(scatter,cax=cax,orientation="horizontal")
    colorbar.solids.set_rasterized(False)
    colorbar.solids.set_edgecolor("face")
    ticks = [v for v in [50,100,300,1000,3000] if norm.vmin <= v <= norm.vmax]
    colorbar.set_ticks(ticks,labels=[f"{v:,}" for v in ticks])
    colorbar.ax.minorticks_off()
    colorbar.ax.tick_params(labelsize=7,length=2,width=.5)
    colorbar.set_label("Extracted molecule molar mass (g/mol; log colour scale)",fontsize=7,labelpad=4)
    legend_ax = fig.add_axes([.18,.112,.64,.030]); legend_ax.axis("off")
    handles = [legend_ax.scatter([],[],s=1.8*np.sqrt(n),color="#9F77AF",edgecolors=INK,linewidths=.4) for n in [10,100,1000,10000]]
    legend_ax.legend(handles,[f"{n:,}" for n in [10,100,1000,10000]],title="Archived structure files; marker area proportional to square root of count",loc="center",ncol=4,frameon=False,fontsize=7,title_fontsize=7,labelspacing=.9,columnspacing=2.5,handletextpad=.9)
    fig.canvas.draw(); renderer=fig.canvas.get_renderer(); outside=[]; families=set()
    for text in fig.findobj(Text):
        if not text.get_visible() or not text.get_text():continue
        path=font_manager.findfont(text.get_fontproperties(),fallback_to_default=False)
        families.add(font_manager.FontProperties(fname=path).get_name())
        box=text.get_window_extent(renderer)
        if box.x0 < -1 or box.y0 < -1 or box.x1>fig.bbox.width+1 or box.y1>fig.bbox.height+1:outside.append(text.get_text())
    if families!={"Helvetica"} or outside:raise AssertionError({"fonts":list(families),"outside":outside})
    timestamp=datetime(2026,10,23,tzinfo=ZoneInfo("Europe/London"))
    fig.savefig(BASE/"output/pdf/cposs_molecular_sketchmap.pdf",metadata={"Title":"The molecular landscape of CPOSS","Author":"CPOSS molecular analysis","CreationDate":timestamp,"ModDate":timestamp})
    fig.savefig(BASE/"figures/cposs_molecular_sketchmap.png",dpi=300)
    plt.close(fig)
    pd.DataFrame(callout_rows).to_csv(BASE/"tables/callouts.csv",index=False)
    font.update({"all_figure_text_families":sorted(families),"text_outside_page":outside})
    write_json(BASE/"data/figure_manifest.json",{"font_verification":font,"page":"A4 portrait","dpi":300,"map_points":len(frame),"represented_structure_files":int(frame.structure_count.sum()),"marker_area_rule":"s = 1.8 sqrt(N) pt^2; N counts model-specific RES files; no optimization weights","colour":"Truncated Plasma [0,0.88]; logarithmic extracted molecule molar mass","callout_selection":selection["rationale"],"molecular_rendering":rendering["style"]+"; 1800x1200 white-background PNGs at 600 dpi; vector map and text","molecular_renderer":rendering["renderer"],"removed_annotations":["title","dataset/count subtitle","bottom exclusion/coformer notes"],"geometry_scope":selection["geometry_scope"],"jitter":False,"callouts":list(pd.DataFrame(callout_rows).dataset_id)})
    print("Created PDF/PNG with",len(frame),"dataset points and",len(callouts),"molecular callouts",flush=True)


if __name__=="__main__":main()
