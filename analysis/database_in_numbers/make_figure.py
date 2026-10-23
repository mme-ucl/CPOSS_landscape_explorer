"""Matplotlib figure, analysis tables, caption and report for CPOSS."""
from __future__ import annotations

from datetime import datetime
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import tempfile
from zoneinfo import ZoneInfo

os.environ.setdefault("MPLCONFIGDIR", "/tmp/cposs-matplotlib")
import matplotlib
matplotlib.use("Agg")
from matplotlib import font_manager, pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
from matplotlib.text import Text
from matplotlib.ticker import MaxNLocator, FuncFormatter
import numpy as np
import pandas as pd

INK = "#172F3D"
MUTED = "#566974"
GRID = "#DCE4E8"
TEAL = "#007F82"
BLUE = "#397CAD"
ORANGE = "#C37529"
LIGHT = "#EEF5F6"


def helvetica(font_path):
    """Extract collection faces locally so matplotlib embeds real bold/italic."""
    if not font_path.exists():
        raise FileNotFoundError("Helvetica required. Supply --font /path/to/Helvetica.ttf or Helvetica.ttc. No substitute will be used.")
    from fontTools.ttLib import TTCollection
    if font_path.suffix.lower() == ".ttc":
        collection = TTCollection(str(font_path))
        font_dir = Path(tempfile.gettempdir()) / "cposs-helvetica-faces"
        font_dir.mkdir(exist_ok=True)
        paths = []
        for font in collection.fonts:
            family = font["name"].getDebugName(1)
            style = font["name"].getDebugName(2)
            if family == "Helvetica" and style in {"Regular", "Bold", "Oblique", "Bold Oblique"}:
                target = font_dir / (font["name"].getDebugName(6) + ".ttf")
                font.save(str(target))
                paths.append(target)
    else:
        paths = [font_path]
        # Additional user-supplied Helvetica faces may sit beside the regular face.
        paths += [p for p in font_path.parent.glob("Helvetica*.ttf") if p != font_path]
    for path in paths:
        font_manager.fontManager.addfont(str(path))
    plt.rcParams.update({"font.family": "Helvetica", "font.sans-serif": ["Helvetica"], "font.size": 8, "axes.labelsize": 8, "axes.titlesize": 10, "xtick.labelsize": 7, "ytick.labelsize": 7, "legend.fontsize": 7, "text.color": INK, "axes.labelcolor": INK, "xtick.color": MUTED, "ytick.color": MUTED, "axes.edgecolor": GRID, "axes.linewidth": 0.6, "pdf.fonttype": 42, "ps.fonttype": 42, "svg.fonttype": "none", "mathtext.fontset": "custom", "mathtext.rm": "Helvetica", "mathtext.it": "Helvetica:italic", "mathtext.bf": "Helvetica:bold", "savefig.facecolor": "white"})
    for weight in ["normal", "bold"]:
        actual = font_manager.findfont(font_manager.FontProperties(family="Helvetica", weight=weight), fallback_to_default=False)
        if font_manager.FontProperties(fname=actual).get_name() != "Helvetica":
            raise RuntimeError("Helvetica font verification failed")
    return {"requested_font": str(font_path), "source_font_sha256": hashlib.sha256(font_path.read_bytes()).hexdigest(), "family": "Helvetica", "faces": [p.name for p in paths]}


def tidy(ax, axis="y"):
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(length=2.5, width=0.5)
    ax.set_axisbelow(True)
    ax.grid(axis=axis, color=GRID, linewidth=0.5)


def panel(fig, rect, letter, title, subtitle):
    x, y, w, h = rect
    fig.text(x, y + h, letter, color=TEAL, weight="bold", fontsize=11, va="top")
    fig.text(x + 0.032, y + h, title, weight="bold", fontsize=10.5, va="top")
    fig.text(x, y + h - 0.023, subtitle, fontsize=6.9, color=MUTED, va="top")


def category_counts(models, field):
    x = models.assign(category=models[field].fillna("").str.split("; ")).explode("category")
    x = x[x.category != ""].drop_duplicates(["dataset_id", "category"])
    return x.groupby("category").dataset_id.nunique().sort_values(ascending=False)


def make_figure(base, font_path):
    table_dir = base / "tables"
    df = pd.read_csv(table_dir / "datasets.csv")
    contributors = pd.read_csv(table_dir / "contributors.csv")
    models = pd.read_csv(table_dir / "energy_models.csv")
    papers = pd.read_csv(table_dir / "papers.csv")
    relations = pd.read_csv(table_dir / "dataset_papers.csv")
    manifest = json.loads((base / "manifest.json").read_text())
    font_info = helvetica(font_path)
    n = len(df)
    known = df[df.structure_count.notna()].copy()
    total = int(known.structure_count.sum())
    dated = df[df.study_year.notna()].copy()
    annual = dated.groupby("study_year").agg(landscapes=("dataset_id", "nunique"), structures=("structure_count", lambda s: s.sum(min_count=1)), landscapes_with_structure_count=("structure_count", "count")).reset_index().rename(columns={"study_year": "year"})
    annual.year = annual.year.astype(int)
    annual["missing_structure_counts"] = annual.landscapes - annual.landscapes_with_structure_count
    years = list(range(int(annual.year.min()), int(annual.year.max()) + 1))
    annual = annual.set_index("year").reindex(years).fillna(0).rename_axis("year").reset_index()
    annual.to_csv(table_dir / "annual_counts.csv", index=False)
    csp_ids = set(relations.loc[relations.relation == "csp_study", "paper_id"])
    csp_papers = papers[papers.paper_id.isin(csp_ids) & papers.is_paper].copy()
    paper_years = csp_papers.publication_year.dropna().astype(int)
    cumulative = paper_years.value_counts().sort_index().rename("new_unique_papers").rename_axis("year").reset_index()
    cumulative = cumulative.set_index("year").reindex(range(int(cumulative.year.min()), int(cumulative.year.max()) + 1)).fillna(0).rename_axis("year").reset_index()
    cumulative["cumulative_unique_papers"] = cumulative.new_unique_papers.cumsum().astype(int)
    cumulative.to_csv(table_dir / "cumulative_papers.csv", index=False)
    potential = category_counts(models, "potential_families")
    electronic = category_counts(models, "electronic_methods")
    pd.concat([potential.rename_axis("category").reset_index(name="datasets").assign(kind="potential_family"), electronic.rename_axis("category").reset_index(name="datasets").assign(kind="electronic_method")]).to_csv(table_dir / "method_frequencies.csv", index=False)
    chemistry = df.drop_duplicates("source_url").dropna(subset=["atom_count", "molar_mass_g_mol"]).copy()
    chemistry.to_csv(table_dir / "molecular_systems.csv", index=False)
    fig = plt.figure(figsize=(210 / 25.4, 297 / 25.4), facecolor="white")
    fig.text(0.067, 0.965, "CPOSS  /  CRYSTAL STRUCTURE PREDICTION", fontsize=8.1, weight="bold", color=TEAL, va="top")
    fig.text(0.067, 0.938, "The database in numbers", fontsize=24, weight="bold", va="top")
    fig.text(0.067, 0.902, "An audit of the publicly linked CSP landscapes", fontsize=10, color=MUTED, va="top")
    fig.text(0.933, 0.964, datetime.fromisoformat(manifest["accessed_date"]).strftime("%d %b %Y").upper(), ha="right", fontsize=8, color=MUTED, va="top")
    fig.add_artist(Rectangle((0.067, 0.817), 0.866, 0.059, facecolor=LIGHT, edgecolor="none", transform=fig.transFigure, zorder=-1))
    stats = [(f"{n:,}", "CSP datasets"), (f"{total:,}", "stored structure entries*"), (str(len(contributors)), "named scientists"), (str(len(csp_papers)), "unique CSP papers")]
    for i, (value, label) in enumerate(stats):
        x = 0.084 + i * 0.217
        fig.text(x, 0.863, value, fontsize=20, weight="bold", color=INK, va="top")
        fig.text(x, 0.832, label, fontsize=7.1, color=MUTED, va="top")
    # Each logical panel occupies a fixed, aligned rectangle; plots have room
    # for full scientist labels and are never clipped to fit the page.
    rects = [(0.067, 0.577, 0.397, 0.21), (0.548, 0.577, 0.385, 0.21), (0.067, 0.322, 0.397, 0.215), (0.548, 0.322, 0.385, 0.215), (0.067, 0.066, 0.397, 0.215), (0.548, 0.066, 0.385, 0.215)]

    # A: dataset-level full counting of explicitly credited people.
    credited_n = int(df.scientist_names.notna().sum())
    panel(fig, rects[0], "A", "The scientists", f"Top 12 of {len(contributors)}; {credited_n}/{n} datasets have named credits")
    axa = fig.add_axes([0.230, 0.600, 0.213, 0.140])
    top = contributors.head(12).iloc[::-1]
    axa.barh(top.scientist_name, top.dataset_count, height=0.61, color=TEAL)
    axa.set_xlim(0, float(top.dataset_count.max()) * 1.14)
    for i, value in enumerate(top.dataset_count):
        axa.text(value + 1, i, str(int(value)), va="center", fontsize=6.7)
    axa.tick_params(axis="y", length=0, labelsize=7)
    axa.xaxis.set_major_locator(MaxNLocator(4, integer=True))
    axa.set_xlabel("Datasets credited", labelpad=3)
    tidy(axa, "x")
    axa.spines["left"].set_visible(False)

    # B: every linked array, ranked rather than unreadable individual labels.
    panel(fig, rects[1], "B", "Structures per dataset", f"{len(known)}/{n} linked files counted; 4 broken JSON links")
    axb = fig.add_axes([0.606, 0.600, 0.315, 0.139])
    ranked = known.sort_values("structure_count", ascending=False).reset_index(drop=True)
    ranked[["dataset_id", "structure_count", "source_url", "json_url"]].assign(rank=np.arange(1, len(ranked) + 1)).to_csv(table_dir / "structure_count_ranking.csv", index=False)
    xx = np.arange(1, len(ranked) + 1)
    axb.fill_between(xx, ranked.structure_count, 8, color=BLUE, alpha=0.24, linewidth=0)
    axb.plot(xx, ranked.structure_count, color=BLUE, linewidth=1.3)
    axb.set_yscale("log")
    axb.set_ylim(8, 3500)
    axb.set_yticks([10, 100, 1000], ["10", "100", "1,000"])
    axb.minorticks_off()
    axb.set_xlim(1, len(ranked))
    axb.set_xticks([1, 100, 200, len(ranked)])
    axb.set_xlabel("Dataset rank (largest first)", labelpad=3)
    axb.set_ylabel("Structure entries (log scale)", labelpad=3)
    median = float(known.structure_count.median())
    axb.text(0.97, 0.92, f"Median {median:,.0f}", transform=axb.transAxes, ha="right", fontsize=7.1, color=BLUE)
    tidy(axb)

    # C: keep force fields and molecular electronic levels visually distinct.
    panel(fig, rects[2], "C", "Energy models", "Dataset counts; method categories can overlap")
    axc1 = fig.add_axes([0.226, 0.430, 0.217, 0.059])
    pp = potential.iloc[::-1]
    labels = [x.replace("Non-empirical / SAPT", "Non-empirical / SAPT").replace("Custom Delaware", "Custom Delaware") for x in pp.index]
    axc1.barh(labels, pp.values, color=TEAL, height=0.61)
    axc1.set_xlim(0, 320)
    axc1.set_xticks([0, 100, 200, 300], ["", "", "", ""])
    axc1.tick_params(axis="y", length=0, labelsize=6.6)
    for i, value in enumerate(pp):
        axc1.text(value + 4, i, str(value), va="center", fontsize=6.5)
    tidy(axc1, "x")
    axc1.spines[["left", "bottom"]].set_visible(False)
    fig.text(0.067, 0.499, "Potential families", fontsize=7.1, color=TEAL, weight="bold")
    axc2 = fig.add_axes([0.226, 0.349, 0.217, 0.061])
    ee = electronic.head(6).iloc[::-1]
    axc2.barh(ee.index, ee.values, color=BLUE, height=0.61)
    axc2.set_xlim(0, 320)
    axc2.set_xticks([0, 100, 200, 300])
    axc2.tick_params(axis="y", length=0, labelsize=6.6)
    for i, value in enumerate(ee):
        axc2.text(value + 4, i, str(value), va="center", fontsize=6.5)
    tidy(axc2, "x")
    axc2.spines["left"].set_visible(False)
    fig.text(0.067, 0.416, "Electronic levels (top 6)", fontsize=7.1, color=BLUE, weight="bold")
    fig.text(0.067, 0.320, f"Includes molecular calculations; {int(df.periodic_dft_supplement.sum())} searches also link pDFT supplements.", fontsize=6.1, color=MUTED)

    # D: one point per documented molecular system, not per repeated search.
    panel(fig, rects[3], "D", "Molecular size", f"{len(chemistry)} documented systems; composition from reported formulas")
    axd = fig.add_axes([0.606, 0.355, 0.315, 0.132])
    for basis, color, label in [("reported molecular formula", BLUE, "Single component"), ("formula unit (multicomponent)", ORANGE, "Multicomponent formula unit")]:
        part = chemistry[chemistry.composition_basis == basis]
        axd.scatter(part.atom_count, part.molar_mass_g_mol, s=15, color=color, alpha=0.65, linewidth=0.3, edgecolors="white", label=f"{label} ({len(part)})")
    axd.set_xscale("log")
    axd.set_yscale("log")
    axd.set_xticks([5, 10, 20, 50, 100, 200], ["5", "10", "20", "50", "100", "200"])
    axd.set_yticks([50, 100, 300, 1000, 3000], ["50", "100", "300", "1,000", "3,000"])
    axd.minorticks_off()
    axd.set_xlabel("Atoms per molecule / formula unit (log scale)", labelpad=3, fontsize=7.3)
    axd.set_ylabel("Molar mass (g/mol; log scale)", labelpad=3, fontsize=7.5)
    axd.set_xlim(chemistry.atom_count.min() * 0.80, chemistry.atom_count.max() * 1.20)
    axd.set_ylim(chemistry.molar_mass_g_mol.min() * 0.72, chemistry.molar_mass_g_mol.max() * 1.30)
    axd.legend(loc="upper left", frameon=False, fontsize=6.4, borderpad=0, labelspacing=0.5, handletextpad=0.3)
    tidy(axd)
    fig.text(0.548, 0.320, "Hydrogens included; formula-unit masses retain written stoichiometry.", fontsize=6.1, color=MUTED)

    # E: aligned bars/line with distinct axes and explicit study-year scope.
    panel(fig, rects[4], "E", "Landscapes through time", f"Source study year; {len(dated)}/{n} datasets have a single year")
    axe = fig.add_axes([0.126, 0.116, 0.281, 0.115])
    axe.bar(annual.year, annual.landscapes, width=0.76, color=TEAL, alpha=0.82)
    axe.set_ylabel("CSP datasets", color=TEAL, labelpad=3)
    axe.yaxis.set_major_locator(MaxNLocator(4, integer=True))
    axe.set_xlim(min(years) - 0.7, max(years) + 0.7)
    axe.set_xticks([2005, 2010, 2015, 2020, 2025])
    axe.set_xlabel("Study year (source Date field)", labelpad=3, fontsize=7.4)
    tidy(axe)
    axe2 = axe.twinx()
    axe2.plot(annual.year, annual.structures / 1000, color=ORANGE, marker="o", markersize=2.5, linewidth=1.2)
    axe2.set_ylabel("Structure entries (thousands)", color=ORANGE, labelpad=3, fontsize=7.2)
    axe2.spines[["top", "left"]].set_visible(False)
    axe2.tick_params(axis="y", labelsize=7, length=2.5, width=0.5)
    axe2.set_ylim(bottom=0)
    axe2.yaxis.set_major_locator(MaxNLocator(4))
    not_assigned = int(df[df.study_year.isna()].structure_count.sum())
    fig.text(0.067, 0.078, f"{n - len(dated)} searches with ranges / pre-2010 dates excluded from annual bins;", fontsize=6.1, color=MUTED)
    fig.text(0.067, 0.067, f"{not_assigned:,} stored structure entries have no single study year.", fontsize=6.1, color=MUTED)

    # F: paper-per-dataset distribution AND deduplicated cumulative papers.
    panel(fig, rects[5], "F", "The linked literature", "CSP study papers; experimental CSD references kept separate")
    axf1 = fig.add_axes([0.606, 0.182, 0.315, 0.050])
    hist = df.csp_paper_count.astype(int).value_counts().sort_index()
    axf1.bar(hist.index, hist.values, color=BLUE, width=0.56)
    axf1.set_xticks(hist.index)
    axf1.set_ylim(0, max(hist.values) * 1.22)
    axf1.set_yticks([0, 100, 200])
    axf1.set_ylabel("Datasets", fontsize=7.5, labelpad=3)
    axf1.set_xlabel("Linked papers per dataset", fontsize=7.2, labelpad=2)
    for x, value in hist.items():
        axf1.text(x, value + 4, str(value), ha="center", fontsize=6.8)
    tidy(axf1)
    axf2 = fig.add_axes([0.606, 0.092, 0.315, 0.049])
    axf2.step(cumulative.year, cumulative.cumulative_unique_papers, color=TEAL, where="post", linewidth=1.5)
    axf2.fill_between(cumulative.year, cumulative.cumulative_unique_papers, step="post", color=TEAL, alpha=0.1)
    axf2.set_ylabel("Unique papers", fontsize=7.5, labelpad=3)
    axf2.set_xlabel("Publication year (cumulative)", fontsize=7.2, labelpad=2)
    axf2.set_xticks([2000, 2010, 2020, 2025])
    axf2.set_xlim(min(cumulative.year), max(cumulative.year) + 1)
    axf2.set_ylim(0, len(csp_papers) * 1.18)
    axf2.set_yticks([0, 25, 50, 75])
    axf2.text(cumulative.year.iloc[-1] + 0.1, len(csp_papers) + 3, str(len(csp_papers)), ha="right", color=TEAL, fontsize=7, weight="bold")
    tidy(axf2)

    fig.add_artist(Line2D([0.067, 0.933], [0.047, 0.047], transform=fig.transFigure, color=GRID, linewidth=0.7))
    fig.text(0.067, 0.035, f"* Entries in {len(known)} linked Chemiscope files, including experimental references; not globally unique predicted crystals.", fontsize=6.4, color=MUTED, va="top")
    fig.text(0.067, 0.023, f"louiseprice.github.io/CPOSS_Database  |  Snapshot {manifest['snapshot_revision'][:12]}  |  See accompanying data and caption.", fontsize=6.1, color=MUTED, va="top")

    output_dir = base / "figures"
    output_dir.mkdir(exist_ok=True)
    pdf_dir = base / "output/pdf"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    fig.canvas.draw()
    actual_fonts = set()
    outside = []
    renderer = fig.canvas.get_renderer()
    for text in fig.findobj(Text):
        if not text.get_text() or not text.get_visible():
            continue
        resolved = font_manager.findfont(text.get_fontproperties(), fallback_to_default=False)
        family = font_manager.FontProperties(fname=resolved).get_name()
        actual_fonts.add(family)
        bounds = text.get_window_extent(renderer)
        if bounds.x0 < -1 or bounds.y0 < -1 or bounds.x1 > fig.bbox.width + 1 or bounds.y1 > fig.bbox.height + 1:
            outside.append(text.get_text())
    if actual_fonts != {"Helvetica"} or outside:
        raise RuntimeError(f"Figure verification failed: fonts={actual_fonts}, outside={outside}")
    timestamp = datetime.fromisoformat(manifest["accessed_date"] + "T00:00:00").replace(tzinfo=ZoneInfo("Europe/London"))
    fig.savefig(pdf_dir / "database_in_numbers.pdf", metadata={"Title": "The database in numbers", "Author": "CPOSS metadata analysis", "Subject": "CSP dataset metadata, structure counts and linked publications", "CreationDate": timestamp, "ModDate": timestamp})
    fig.savefig(output_dir / "database_in_numbers.png", dpi=300)
    plt.close(fig)
    font_info["all_figure_text_families"] = sorted(actual_fonts)
    font_info["text_outside_page"] = outside
    manifest["font_verification"] = font_info
    manifest["software_versions"] = {p: importlib.metadata.version(p) for p in ["pandas", "numpy", "matplotlib", "fonttools", "requests", "rdkit", "pypdf"]}
    (base / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    write_report(base, df, contributors, models, papers, relations, csp_papers, chemistry, annual, cumulative, potential, electronic, manifest)
    print(f"Created PDF/PNG: {n} datasets, {total:,} entries, {len(contributors)} scientists, {len(csp_papers)} CSP papers", flush=True)


def write_report(base, df, contributors, models, papers, relations, csp_papers, chemistry, annual, cumulative, potential, electronic, manifest):
    n = len(df)
    known = df[df.structure_count.notna()]
    total = int(known.structure_count.sum())
    credited_n = df.scientist_names.notna().sum()
    dated = df[df.study_year.notna()]
    json_audit = pd.read_csv(base / "tables/structure_file_audit.csv")
    unavailable = df[df.structure_count.isna()]
    duplicate = json_audit[json_audit.duplicate_filename_count.fillna(0) > 0]
    csp_assoc = relations[relations.relation == "csp_study"]
    top = contributors.iloc[0]
    note = f"""The database in numbers. Metadata were extracted from {manifest['case_pages_with_searches']} molecule pages reachable from the CPOSS index, representing {n} distinct CSP searches in repository snapshot {manifest['snapshot_revision']} (accessed {manifest['accessed_date']}). Each explicitly linked search is one dataset; its energy models are not separate datasets. A, the 12 most frequently credited scientists, with full credit for each named contributor and no inferred authorship from paper author lists ({credited_n}/{n} searches have a named scientist). B, linked Chemiscope structure-array entries per dataset, ranked on a logarithmic axis ({len(known)}/{n} files; median {known.structure_count.median():.0f}); experimental-reference entries and repeated filename labels are retained, so {total:,} is a stored-entry total, not a count of globally distinct predictions or all structures originally generated. C, dataset frequencies for reported potential families and the six most frequent electronic-method categories; categories overlap and electronic levels may describe molecular or multipole calculations rather than periodic DFT. All method categories are tabulated. D, molar mass versus total atom count calculated from reported formulas, with one point per documented molecular system ({len(chemistry)} systems). Multicomponent formulas retain explicitly written stoichiometry; hydrogens are included, and unit-cell atom counts are not used. E, annual CSP-search counts (bars) and stored structure entries (line), using single unambiguous years from the source Date field ({len(dated)}/{n} datasets); date ranges and pre-2010 dates are excluded from annual bins. These are study dates, not release/deposition dates. F, the number of linked CSP papers per dataset and cumulative unique linked CSP papers by publication year ({len(csp_papers)} papers). Papers are deduplicated across datasets by DOI or canonical URL; explicit within-page Study_ID publication pointers are followed and labelled inferred. Experimental CSD citations are recorded separately. Helvetica is used and embedded throughout; the figure is A4 portrait, with a vector PDF and 300 dpi PNG.
"""
    note = note.replace("D, molar mass versus total atom count", "D, molar mass versus total atom count on logarithmic axes")
    (base / "caption.md").write_text(note)
    def markdown_table(frame):
        columns = list(frame.columns)
        lines = ["| " + " | ".join(map(str, columns)) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
        lines += ["| " + " | ".join(str(v).replace("|", "/") for v in row) + " |" for row in frame.itertuples(index=False, name=None)]
        return "\n".join(lines)
    coverage = pd.DataFrame([
        ["Documented CSP searches", n, n],
        ["Linked JSON structure counts", len(known), n],
        ["Named scientist credits", int(credited_n), n],
        ["Single study year", len(dated), n],
        ["Molar mass and atom count from formula", int(df.atom_count.notna().sum()), n],
        ["Dataset release/deposition year", 0, n],
        ["Original generated/optimised/retained counts as numeric HTML fields", 0, n],
    ], columns=["Field", "Available", "Total datasets"])
    methods = pd.concat([potential.rename_axis("Category").reset_index(name="Datasets").assign(Kind="Potential family"), electronic.rename_axis("Category").reset_index(name="Datasets").assign(Kind="Electronic method")])
    paper_hist = df.csp_paper_count.astype(int).value_counts().sort_index().rename_axis("Linked CSP papers per dataset").reset_index(name="Datasets")
    missing_names = ", ".join(unavailable.dataset_id)
    bad_links = pd.read_csv(base / "tables/broken_source_links.csv")
    conflict_count = len(pd.read_csv(base / "tables/metadata_conflicts.csv"))
    unresolved = csp_assoc.merge(papers[["paper_id", "title_status"]], on="paper_id")
    peak = annual.loc[annual.landscapes.idxmax()]
    report = f"""# CPOSS metadata audit and analysis

Snapshot: `{manifest['snapshot_revision']}`. Accessed **{manifest['accessed_date']}**, Europe/London.
Source: [CPOSS database index]({manifest['source_index']}). All source HTML and the repository inventory are archived in `sources/`.

## Findings

- **{n} documented CSP datasets** across **{manifest['case_pages_with_searches']} reachable molecule pages**.
- **{total:,} stored structure entries** in **{len(known)} linked Chemiscope files**. The median is **{known.structure_count.median():.0f}**, the interquartile range is **{known.structure_count.quantile(.25):.1f}-{known.structure_count.quantile(.75):.0f}**, and the range is **{int(known.structure_count.min())}-{int(known.structure_count.max())}** entries per file.
- **{len(contributors)} named scientists** across **{credited_n} datasets**; **{n - credited_n} datasets** say Unknown/Not sure rather than naming a scientist. The most frequently credited person is **{top.scientist_name}**, associated with **{int(top.dataset_count)} datasets**. Credits overlap and are not an assessment of research productivity.
- **{len(chemistry)} documented molecular systems** have parseable formulas. Molar masses span **{chemistry.molar_mass_g_mol.min():.2f}-{chemistry.molar_mass_g_mol.max():.2f} g/mol** and atom counts span **{int(chemistry.atom_count.min())}-{int(chemistry.atom_count.max())}**, on the written molecule/formula-unit basis.
- **{len(csp_papers)} unique linked CSP papers**, **{len(papers)} unique linked references overall**, including experimental-context papers and research data records. **{int((df.csp_paper_count > 0).sum())} datasets** link at least one CSP paper after explicit publication cross-references are resolved.
- The largest annual count with an unambiguous study date is **{int(peak.landscapes)} datasets in {int(peak.year)}**. **{len(dated)} datasets** have single years; **{n - len(dated)}** have ranges or pre-2010 dates, so this is incomplete chronology.

{markdown_table(coverage)}

## Dataset scope and duplicate handling

The extractor follows same-database HTML links from the index and validates them against a complete GitHub repository tree. **{manifest['reachable_html_pages']} of {manifest['inventory_html_pages']} HTML files** are reachable. A contributor-statistics placeholder and a misspelled duplicate molecule page are unlinked and excluded. The audit has **{manifest['search_occurrences_before_deduplication']} search occurrences**, keyed by the explicitly linked Chemiscope filename. A molecule page can describe several searches; an individual search can have several energy models. The analysis includes searches with broken JSON links rather than silently dropping them from the dataset denominator.

**{manifest['unlinked_json_files']} JSON files** exist in the repository but are not explicitly linked from reachable searches. These include full/filtered variants and unmatched files. They are inventoried in `unlinked_json_inventory.csv` and excluded from the headline and structure counts. Consequently, these numbers describe the public HTML-linked collection, not every file in the repository. Existing explorer catalogue files were not changed.

Every archived HTML file and downloaded JSON was checked against its Git blob SHA at the frozen revision. The lightweight JSON summaries retain the verified original file hashes, array counts, property lengths and duplicate-filename checks; the 1+ GB coordinate cache stays outside the deliverable. Rebuilding the figure and extraction offline uses those archived summaries; verifying them from scratch requires downloading the original JSON again.

## What the structure count means

The HTML does not contain numeric totals for all originally generated, optimised or retained candidates. Counts in this report are **calculated from the length of each linked JSON `structures` array**. They describe the distributed visualisation data, including entries associated with experimental references. Original search sizes remain missing, never zero.

**{int((known.structure_count == 1000).sum())} files have exactly 1,000 entries**. This concentration is consistent with a display/export limit, but no uniform limit is assumed. The five unlinked `_full` variants are not added to their linked counterparts. Two linked files repeat filename labels: {', '.join(Path(p).name + ' (' + str(int(n)) + ' repeated labels)' for p, n in zip(duplicate.path, duplicate.duplicate_filename_count))}. Labels alone are insufficient to prove identical geometries, so repeated rows are flagged and retained. Cross-dataset structure matching has not been performed; totals must not be called unique predicted crystals.

Four linked JSON files are absent at the revision: **{missing_names}**. Their structure counts are missing. `structure_file_audit.csv` records the exact broken links and verified array/property-length checks. No fuzzy filename correction was applied.

## Scientist names and molecular composition

Only explicit Scientist fields establish contributor relationships. Paper author lists are separate metadata and do not create dataset contributor credits. Slash, comma, `and` and parenthesis separators are parsed; parentheses are preserved as additional credits, without guessing supervisory roles. `L Price` is expanded to Louise Price and marked inferred. **Sally Price and Louise Price remain distinct**; see [UCL's staff listing](https://www.ucl.ac.uk/mathematical-physical-sciences/chemistry/people/emeritus-honorary-staff) for Sarah (Sally) L. Price. All source spellings remain in the tables.

Formula masses use RDKit's average atomic weights, not monoisotopic masses. The parser supports explicit integer group multipliers, component separators and charge symbols. Charges are ignored for molecular weight; all written components are included. Hydrate and salt/cocrystal masses use the complete **written formula unit**; for example a hemihydrate written as 2 acid molecules plus 1 water is not rescaled to a fractional water molecule. No unit-cell atom count is mistaken for a molecule's atom count. The analysis follows the reported formulas and does not independently validate chemical names, protonation or formula accuracy.

## Energy models and DFT

There are **{int((models.kind == 'energy_model').sum())} energy-model records** and **{int((models.kind == 'supplementary_periodic_DFT').sum())} supplementary pDFT links**. Programs, potential descriptions, intramolecular descriptions, basis sets and explicitly named dispersion corrections are retained in `energy_models.csv`. Raw descriptions remain authoritative; text-based normalisations are marked inferred. PBE0 and PBE1PBE are grouped as a single conventional electronic-method category; no missing method is filled from an unrelated search.

{markdown_table(methods[['Kind', 'Category', 'Datasets']])}

These counts use each dataset at most once per category and may sum above {n}. MP2, HF and hybrid functional labels commonly describe molecular charge densities, multipoles or intramolecular energies. They are **not evidence that the whole crystal landscape was computed with periodic DFT**. The 31 pDFT supplement links provide no functional/basis description in their HTML rows; those details remain missing. The linked ZIP archives and Word descriptions were not mined for additional methodology.

## Dates and the linked literature

Dataset deposition/release years are not reported. Annual counts therefore use the **source study Date field**, with no substitution of page update year or publication year. Single years and month-year dates are accepted. Ranges such as 2005-2008, abbreviated 2005-7, and pre-2010 are excluded instead of assigned arbitrary years. These exclusions leave **{int(annual.structures.sum()):,} entries** in annual bins and **{int(df[df.study_year.isna()].structure_count.sum()):,} entries** without a single year. Known study years with broken JSON links contribute a landscape but no fabricated structure count.

{markdown_table(paper_hist)}

Paper identities use case-normalised DOI, otherwise canonical URL. Explicit `See Study_ID` publication pointers are followed **only within their molecule page** when the target is unambiguous; **{int((csp_assoc.status == 'inferred').sum())} dataset-paper associations** are marked inferred. Figures count the papers associated with CSP Publication fields, not every experimental crystal determination cited on a molecule page. The CSVs retain both CSP and experimental-context associations and per-dataset counts for each scope. A zero linked-paper count means no qualifying linked paper was found, not proof that no paper exists. Plain notes such as Masters thesis, In preparation and No publication planned remain in `publication_raw`.

Crossref supplies titles, authors, reference types and its preferred published year for DOI records. DataCite identifies three eCrystals dataset records, which are not counted as papers. Three truncated Wiley DOI hyperlinks are reconstructed from their complete visible citation strings, marked inferred and validated through Crossref. One CSP reference is identified as a paper from its explicit Trans. ACA citation; its linked proceedings PDF returned HTTP 404, so its title remains missing. **{int(papers.title.isna().sum())} reference title** is unavailable. Online/print years are recorded separately where supplied; the cumulative curve counts each CSP paper once, by the recorded publication year, and does not measure when it was added to CPOSS.

## Validation and deliverables

No conflicting contributor/date/formula values were found across merged dataset mappings (**{conflict_count} conflicts**). All available linked JSON structure-target property lengths match their arrays; the delivered verification report separately checks these lengths, accounting totals, annual aggregation, DOI deduplication, PDF geometry and embedded fonts. The source-link audit lists **{len(bad_links)} missing internal link targets** across HTML, archives and images; these were checked against the repository inventory, not by fetching every ZIP or image. External paper landing pages were not all fetched; metadata-service retrieval and its exceptions are recorded in `sources/doi_metadata.json`.

The page is exactly A4 portrait. All text resolves to Helvetica, with regular/bold faces extracted from the system Helvetica collection for embedding; no proprietary font file is redistributed. The vector PDF and 300 dpi PNG have the same layout. `caption.md` provides the standalone figure caption. `tables/` holds complete results, `sources/` holds archived HTML/metadata, and `manifest.json` records scope, revision, date, fonts and package versions.
"""
    (base / "report.md").write_text(report)
