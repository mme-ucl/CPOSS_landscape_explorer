"""Rebuild the paper overview from frozen tables with 55% larger typography."""
from __future__ import annotations

import csv
import hashlib
import json
import os
os.environ.setdefault("MPLCONFIGDIR", "/tmp/cposs-matplotlib")
from pathlib import Path

from PIL import Image
from pypdf import PdfReader
import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
from matplotlib.colors import LogNorm, Normalize, to_hex
from matplotlib.patches import Rectangle
from matplotlib.text import Text
from matplotlib.ticker import MaxNLocator
from panel_c_methods.draw_panel import draw_panel, load_summary
from make_figure import helvetica, tidy, count_colors, spectral_line, INK, MUTED, LIGHT, COOL, WARM, SPECTRAL


BASE = Path(__file__).resolve().parent


def table(name):
    with (BASE / "tables" / (name + ".csv")).open() as stream:
        return list(csv.DictReader(stream))


def panel_c_inputs():
    summary, counts = load_summary()
    datasets = table("plot_datasets")
    if summary["inventory_datasets"] != len(datasets) or summary["total_archived_records"] != sum(int(row["structure_count"]) for row in datasets):
        raise ValueError("Panel C must use the current figure inventory and archive counts")
    folder = BASE / "panel_c_methods"
    return summary | {"audit_csv": "panel_c_methods/model_classification.csv",
                      "audit_csv_sha256": hashlib.sha256((folder / "model_classification.csv").read_bytes()).hexdigest(),
                      "counts_csv": "panel_c_methods/matrix_counts.csv",
                      "counts_csv_sha256": hashlib.sha256((folder / "matrix_counts.csv").read_bytes()).hexdigest()}


def write_caption():
    manifest = json.loads((BASE / "manifest.json").read_text())
    datasets = table("plot_datasets")
    chemistry = table("molecular_systems")
    contributors = table("contributors")
    archives = table("structure_archive_counts")
    annual = table("annual_counts")
    papers = table("cumulative_papers")
    n = len(datasets)
    methods = panel_c_inputs()
    systems = len({row["source_url"] for row in datasets})
    single = sum(row["composition_basis"] == "reported molecular formula" for row in chemistry)
    multi = len(chemistry) - single
    credited = sum(bool(row["scientist_names"]) for row in datasets)
    dated = sum(int(float(row["landscapes"])) for row in annual)
    dated_files = sum(int(float(row["structures"])) for row in annual)
    total = sum(int(row["coordinate_files"]) for row in archives)
    text = rf"""% Caption for database_in_numbers_3x2.pdf. Input inside the figure environment.
\caption{{
\textbf{{The CPOSS database in numbers.}}
Overview of {n} documented crystal structure prediction (CSP) searches
covering {systems} molecular systems in the repository snapshot accessed
on {manifest['accessed_date']}. The headline counts {total:,} \texttt{{RES}}
coordinate files across {len(archives)} documented energy-model archives.
Separate model representations and any archived experimental reference
structures are retained; geometric deduplication across models and
searches has not been performed.
\textbf{{(A)}} Molar mass against total atom count on logarithmic axes
for {len(chemistry)} systems with unambiguously parseable website formulas:
{single} single-component systems (purple) and {multi} multicomponent
formula units (yellow). Atom counts include hydrogen, and multicomponent
formulas retain their complete written stoichiometry. The other
{systems - len(chemistry)} systems have ambiguous website formulas and
are excluded from this panel.
\textbf{{(B)}} Archived structure-file counts per search, ranked from
largest to smallest on a logarithmic vertical axis (median 498).
\textbf{{(C)}} Search and refinement methods. Columns identify the initial
search program (MOLPAK or CrystalPredictor), taken from energy model 1
where available and traced through unambiguous same-page Study\_ID references.
Rows identify the refinement engine (DMAREL or DMACRYS). Each cell contains
two pies: Structures (left) weights archived structure--model records;
Models (right) counts each distinct dataset/energy-model combination once.
Circle areas represent cell totals on independent scales, given by their
respective size keys. Purple and gold denote rigid and flexible molecular
refinement; numeric callouts give flexible counts in each pie's unit.
Flexible searching alone does not establish flexible refinement;
CrystalOptimizer or DMAflex is treated as flexible refinement only when
explicitly documented for the current workflow. Both views include
{methods['classified_models']} of {methods['energy_models']} energy models
({100*methods['classified_models']/methods['energy_models']:.1f}\%) and
{methods['classified_archived_records']:,} of {methods['total_archived_records']:,} stored files
({100*methods['classified_archived_records']/methods['total_archived_records']:.1f}\%).
The {methods['unresolved_models']} excluded archives ({methods['unresolved_archived_records']:,} files) have
other search origins or unresolved refinement histories; exclusions and
reasons are retained in the model-level audit. Separate representations
across energy models are retained: TrinitrobenzeneA's nine archives of
203 files each contribute 1,827 records to Structures and nine models
to Models, without implying geometrically identical populations.
\textbf{{(D)}} Website search-level credits for the 20 most frequently
named scientists, drawn from {len(contributors)} named scientists overall.
Every explicitly named contributor receives full credit for an associated
search; {credited} of the {n} searches have named credits.
\textbf{{(E)}} Annual search counts (bars) and archived structure-file
totals (line), with cumulative search counts below. The temporal plots
include {dated} searches containing {dated_files:,} archived files with
single unambiguous website study years. The other {n - dated} searches,
containing {total - dated_files:,} files, have date ranges or non-specific
dates and are excluded. These dates describe studies rather than
database release or deposition.
\textbf{{(F)}} Cumulative unique linked CSP papers by publication year,
reaching {int(float(papers[-1]['cumulative_unique_papers']))} papers.
References are deduplicated by DOI or canonical URL; experimental-context
references are recorded separately.
}}
\label{{fig:database_in_numbers}}
"""
    (BASE / "caption_3x2.tex").write_text(text)


FONT_SCALE = 1.55


def main():
    font = helvetica(Path("/System/Library/Fonts/Helvetica.ttc"))
    datasets = pd.read_csv(BASE / "tables/plot_datasets.csv")
    chemistry = pd.read_csv(BASE / "tables/molecular_systems.csv")
    contributors = pd.read_csv(BASE / "tables/contributors.csv")
    annual = pd.read_csv(BASE / "tables/annual_counts.csv")
    papers = pd.read_csv(BASE / "tables/cumulative_papers.csv")
    software_info = panel_c_inputs()
    total = int(datasets.structure_count.sum())
    year_norm = Normalize(min(annual.year.min(), papers.year.min()),
                          max(annual.year.max(), papers.year.max()))
    # Keep the established paper canvas; reflow text and axes instead of enlarging it.
    fig = plt.figure(figsize=(11.378, 8.45), facecolor="white")
    fig.text(.5, .978, "The CPOSS database in numbers", fontsize=14,
             weight="bold", ha="center", va="top")
    fig.add_artist(Rectangle((.14, .872), .72, .066, facecolor=LIGHT,
                             edgecolor="none", transform=fig.transFigure, zorder=-1))
    stats = [(f"{len(datasets):,}", "CSP datasets"), (f"{total:,}", "archived structure files"),
             (str(len(contributors)), "named scientists"),
             (str(int(papers.cumulative_unique_papers.iloc[-1])), "unique CSP papers")]
    for index, (value, label) in enumerate(stats):
        x = .14 + (index + .5) * .72 / 4
        fig.text(x, .929, value, fontsize=14, weight="bold", ha="center", va="top")
        fig.text(x, .887, label, fontsize=6, color=MUTED, ha="center", va="center")
    for x, y, letter, title in [(.018,.840,"A","Molecular size"),
                               (.357,.840,"B","Structures per dataset"),
                               (.701,.840,"C","Search and refinement methods"),
                               (.018,.447,"D","The scientists"),
                               (.357,.447,"E","Landscapes through time"),
                               (.701,.447,"F","The linked literature")]:
        fig.text(x, y, letter, fontsize=9, weight="bold", va="top")
        fig.text(x+.025, y, title, fontsize=9, weight="bold", va="top")
    axa = fig.add_axes([.075,.548,.235,.263])
    for basis, colour, label in [("reported molecular formula",COOL,"Single component"),
                                  ("formula unit (multicomponent)",WARM,"Multicomponent formula unit")]:
        part = chemistry[chemistry.composition_basis == basis]
        axa.scatter(part.atom_count, part.molar_mass_g_mol, s=15, color=colour,
                    alpha=.65, linewidth=.3, edgecolors="white", label=f"{label} ({len(part)})")
    axa.set_xscale("log"); axa.set_yscale("log")
    axa.set_xticks([5,10,20,50,100], ["5","10","20","50","100"])
    axa.set_yticks([50,100,300,1000], ["50","100","300","1,000"])
    axa.minorticks_off()
    axa.set_xlim(chemistry.atom_count.min()*.8, chemistry.atom_count.max()*1.2)
    axa.set_ylim(chemistry.molar_mass_g_mol.min()*.72, chemistry.molar_mass_g_mol.max()*2.1)
    axa.set_xlabel("Atoms per molecule or formula unit", fontsize=7.3, labelpad=5)
    axa.set_ylabel(r"Molar mass (g mol$^{-1}$)", fontsize=7.5, labelpad=4)
    axa.legend(loc="upper left", frameon=True, facecolor="white", edgecolor="none",
               framealpha=.96, fontsize=6.4, borderpad=.2,
               labelspacing=.5, handletextpad=.3, handlelength=.8)
    tidy(axa)
    axb = fig.add_axes([.408,.548,.235,.263])
    ranked = datasets.sort_values("structure_count", ascending=False)
    spectral_line(axb, np.arange(1,len(ranked)+1), ranked.structure_count, ranked.structure_count,
                  LogNorm(ranked.structure_count.min(), ranked.structure_count.max()), baseline=8, fill_alpha=.17)
    axb.set_yscale("log"); axb.set_ylim(8, ranked.structure_count.max()*1.4)
    axb.set_yticks([10,100,1000,10000], ["10","100","1,000","10,000"])
    axb.minorticks_off(); axb.set_xlim(1,len(ranked)); axb.set_xticks([1,100,200,len(ranked)])
    axb.set_xlabel("Dataset rank (largest first)", labelpad=5)
    axb.set_ylabel("Structure files", labelpad=4)
    tidy(axb)
    geometry = draw_panel(fig, [.729,.561,.26,.239], [.706,.470,.284,.070],
                          legend_anchor=(.845,.551))
    software_info.update({key: geometry[key] for key in ["title", "layout", "colours", "row_label_rotation_deg", "bubble_area_pt2_per_unit", "bubble_radii", "size_key_radii", "size_key_counts", "flexible_callouts", "legend_scope"]})
    axd = fig.add_axes([.156,.070,.154,.344])
    top = contributors.head(20).iloc[::-1]
    axd.barh(top.scientist_name, top.dataset_count, height=.58, color=count_colors(top.dataset_count), linewidth=0)
    axd.set_ylim(-.6,len(top)-.4); axd.set_xlim(0,top.dataset_count.max()*1.15)
    axd.tick_params(axis="y",length=0,labelsize=6.3); axd.xaxis.set_major_locator(MaxNLocator(4,integer=True))
    axd.set_xlabel("Datasets credited", labelpad=5)
    for i, value in enumerate(top.dataset_count):
        axd.text(value+1,i,str(int(value)),va="center",fontsize=6.1)
    tidy(axd,"x"); axd.spines["left"].set_visible(False)
    axe = fig.add_axes([.408,.238,.208,.176])
    axe.bar(annual.year, annual.landscapes, width=.76, color=SPECTRAL(year_norm(annual.year)), alpha=.93)
    axe.set_ylabel(r"Datasets year$^{-1}$",fontsize=7.2,labelpad=5)
    axe.yaxis.set_major_locator(MaxNLocator(4,integer=True))
    axe.set_xlim(annual.year.min()-.7,annual.year.max()+.7)
    axe.set_xticks([2005,2010,2015,2020,2025]); axe.tick_params(axis="x",labelbottom=False)
    tidy(axe)
    axr = axe.twinx()
    axr.plot(annual.year,annual.structures/1000,color=INK,marker="o",markersize=2.5,linewidth=1.2)
    axr.set_ylabel("Structure files\n(thousands)",fontsize=7,labelpad=4)
    axr.spines[["top","left"]].set_visible(False); axr.set_ylim(bottom=0)
    axr.yaxis.set_major_locator(MaxNLocator(4)); axr.tick_params(axis="y",labelsize=7,length=2.5,width=.5)
    axec = fig.add_axes([.408,.070,.208,.119],sharex=axe)
    spectral_line(axec,annual.year,annual.cumulative_datasets,annual.year,year_norm,step=True,fill_alpha=.13,linewidth=1.5)
    axec.set_ylabel("Cumulative datasets",fontsize=7.2,labelpad=5)
    axec.set_xlabel("Study year",fontsize=7.4,labelpad=5)
    axec.set_ylim(0,annual.cumulative_datasets.max()*1.2); axec.set_yticks([0,100,200]); tidy(axec)
    axf = fig.add_axes([.761,.070,.221,.344])
    spectral_line(axf,papers.year,papers.cumulative_unique_papers,papers.year,year_norm,step=True,fill_alpha=.13,linewidth=1.5)
    axf.set_ylabel("Unique papers",fontsize=7.5,labelpad=4)
    axf.set_xlabel("Publication year",fontsize=7.2,labelpad=5)
    axf.set_xlim(papers.year.min(),papers.year.max()+1); axf.set_ylim(0,papers.cumulative_unique_papers.max()*1.18)
    axf.set_xticks([2000,2010,2020,2025]); axf.set_yticks([0,25,50,75]); tidy(axf)
    for text in fig.findobj(Text):
        text.set_fontsize(text.get_fontsize()*FONT_SCALE)
    fig.canvas.draw()
    outside = []
    renderer = fig.canvas.get_renderer()
    for text in fig.findobj(Text):
        if text.get_visible() and text.get_text():
            b = text.get_window_extent(renderer)
            if b.x0 < -1 or b.y0 < -1 or b.x1 > fig.bbox.width+1 or b.y1 > fig.bbox.height+1:
                outside.append(text.get_text())
    if outside:
        raise AssertionError({"text_outside_page":outside})
    output = BASE / "output/pdf/database_in_numbers_3x2.pdf"
    png = BASE / "figures/database_in_numbers_3x2.png"
    fig.savefig(output, metadata={"Title":"The CPOSS database in numbers","CreationDate":None,"ModDate":None})
    fig.savefig(png,dpi=300)
    size = list(fig.get_size_inches())
    plt.close(fig)
    page = PdfReader(output).pages[0]
    fonts = [str(ref.get_object()["/BaseFont"]) for ref in page["/Resources"]["/Font"].values()]
    assert all("Helvetica" in name for name in fonts), fonts
    assert not page.images
    with Image.open(png) as im:
        dimensions = list(im.size)
    verification = {"status":"passed","layout":[["A","B","C"],["D","E","F"]],
                    "output_pdf":str(output.relative_to(BASE)),
                    "output_sha256":hashlib.sha256(output.read_bytes()).hexdigest(),
                    "page_size_pt":[v*72 for v in size],"png_dimensions":dimensions,"png_dpi":300,
                    "fonts":fonts,"vector_graphics":True,"font_scale":FONT_SCALE,
                    "out_of_bounds_text":outside,"panel_c":software_info,
                    "source_tables_sha256":{name:hashlib.sha256((BASE / "tables" / (name+".csv")).read_bytes()).hexdigest()
                                            for name in ["plot_datasets","molecular_systems","contributors","annual_counts","cumulative_papers"]},
                    "font_verification":font,"embedded_comments":False}
    (BASE / "verification_3x2.json").write_text(json.dumps(verification,indent=2)+"\n")
    write_caption()
    print(json.dumps({"status":"passed","font_scale":FONT_SCALE,"fonts":fonts,"size_inches":size},indent=2))


if __name__ == "__main__":
    main()
