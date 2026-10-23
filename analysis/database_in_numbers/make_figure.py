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
from matplotlib.collections import LineCollection, PolyCollection
from matplotlib.colors import LinearSegmentedColormap, LogNorm, Normalize, to_hex
from matplotlib.patches import Rectangle
from matplotlib.text import Text
from matplotlib.ticker import MaxNLocator
import numpy as np
import pandas as pd

INK = "#172F3D"
MUTED = "#566974"
GRID = "#DCE4E8"
LIGHT = "#F6F7F7"
# Spectral-inspired anchors, with a darker gold centre for white-page legibility.
SPECTRAL_ANCHORS = ["#5e4fa2", "#3288bd", "#4ca88b", "#c8ac4c", "#ed814c", "#c62f4c"]
SPECTRAL = LinearSegmentedColormap.from_list("CPOSS_Spectral", SPECTRAL_ANCHORS, N=256)
COOL = SPECTRAL_ANCHORS[1]
WARM = SPECTRAL_ANCHORS[-1]


def count_colors(values):
    values = np.asarray(values, dtype=float)
    return SPECTRAL(LogNorm(vmin=values.min(), vmax=values.max())(values))


def spectral_line(ax, x, y, color_values, norm, *, step=False, baseline=0, fill_alpha=0.15, linewidth=1.4):
    """Vector line and area with a continuous, explicitly defined colour ramp."""
    x, y, color_values = (np.asarray(v, dtype=float) for v in (x, y, color_values))
    segments, segment_values, polygons, polygon_values = [], [], [], []
    for i in range(len(x) - 1):
        if step:
            segments.extend([[(x[i], y[i]), (x[i + 1], y[i])], [(x[i + 1], y[i]), (x[i + 1], y[i + 1])]])
            segment_values.extend([color_values[i], color_values[i + 1]])
            polygons.append([(x[i], baseline), (x[i], y[i]), (x[i + 1], y[i]), (x[i + 1], baseline)])
            polygon_values.append(color_values[i])
        else:
            segments.append([(x[i], y[i]), (x[i + 1], y[i + 1])])
            segment_values.append((color_values[i] + color_values[i + 1]) / 2)
            polygons.append([(x[i], baseline), (x[i], y[i]), (x[i + 1], y[i + 1]), (x[i + 1], baseline)])
            polygon_values.append(segment_values[-1])
    ax.add_collection(PolyCollection(polygons, facecolors=SPECTRAL(norm(polygon_values)), edgecolors="none", alpha=fill_alpha, zorder=1))
    line = LineCollection(segments, cmap=SPECTRAL, norm=norm, linewidths=linewidth, zorder=3)
    line.set_array(np.asarray(segment_values))
    ax.add_collection(line)
    ax.update_datalim(np.column_stack([x, y]))
    ax.autoscale_view()


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


def panel(fig, rect, letter, title):
    x, y, w, h = rect
    fig.text(x, y + h, letter, color=INK, weight="bold", fontsize=9, va="top")
    fig.text(x + 0.029, y + h, title, weight="bold", fontsize=9, va="top")


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
    annual["cumulative_datasets"] = annual.landscapes.cumsum().astype(int)
    annual.to_csv(table_dir / "annual_counts.csv", index=False)
    csp_ids = set(relations.loc[relations.relation == "csp_study", "paper_id"])
    csp_papers = papers[papers.paper_id.isin(csp_ids) & papers.is_paper].copy()
    paper_years = csp_papers.publication_year.dropna().astype(int)
    cumulative = paper_years.value_counts().sort_index().rename("new_unique_papers").rename_axis("year").reset_index()
    cumulative = cumulative.set_index("year").reindex(range(int(cumulative.year.min()), int(cumulative.year.max()) + 1)).fillna(0).rename_axis("year").reset_index()
    cumulative["cumulative_unique_papers"] = cumulative.new_unique_papers.cumsum().astype(int)
    cumulative.to_csv(table_dir / "cumulative_papers.csv", index=False)
    year_norm = Normalize(vmin=min(years[0], int(cumulative.year.min())), vmax=max(years[-1], int(cumulative.year.max())))
    potential = category_counts(models, "potential_families")
    electronic = category_counts(models, "electronic_methods")
    pd.concat([potential.rename_axis("category").reset_index(name="datasets").assign(kind="potential_family"), electronic.rename_axis("category").reset_index(name="datasets").assign(kind="electronic_method")]).to_csv(table_dir / "method_frequencies.csv", index=False)
    chemistry = df.drop_duplicates("source_url").dropna(subset=["atom_count", "molar_mass_g_mol"]).copy()
    chemistry.to_csv(table_dir / "molecular_systems.csv", index=False)
    fig = plt.figure(figsize=(210 / 25.4, 297 / 25.4), facecolor="white")
    fig.text(0.5, 0.970, "The CPOSS database in numbers", fontsize=14, weight="bold", ha="center", va="top")
    # Scale the summary strip by 70% and keep its centre on the page.
    strip_scale = 0.70
    strip_width, strip_height = 0.866 * strip_scale, 0.059 * strip_scale
    strip_left, strip_bottom = (1 - strip_width) / 2, 0.900
    fig.add_artist(Rectangle((strip_left, strip_bottom), strip_width, strip_height, facecolor=LIGHT, edgecolor="none", transform=fig.transFigure, zorder=-1))
    stats = [(f"{n:,}", "CSP datasets"), (f"{total:,}", "stored structure entries"), (str(len(contributors)), "named scientists"), (str(len(csp_papers)), "unique CSP papers")]
    for i, (value, label) in enumerate(stats):
        x = strip_left + (i + 0.5) * strip_width / 4
        fig.text(x, strip_bottom + strip_height - 0.006, value, fontsize=20 * strip_scale, weight="bold", color=INK, ha="center", va="top")
        fig.text(x, strip_bottom + 0.0115, label, fontsize=6.0, color=MUTED, ha="center", va="top")
    # Compact journal layout: align row baselines, reduce vertical gutters and
    # give the data the recovered space. Physical page size remains A4.
    # Move each column 0.018 page widths towards the centre. All plot heights
    # and vertical positions stay identical to the preceding reviewed figure.
    rects = [(0.085, 0.674, 0.397, 0.210), (0.530, 0.674, 0.385, 0.210), (0.085, 0.381, 0.397, 0.215), (0.530, 0.381, 0.385, 0.215), (0.085, 0.054, 0.397, 0.260), (0.530, 0.054, 0.385, 0.260)]

    # A: molecular size, moved into the first panel.
    panel(fig, rects[0], "A", "Molecular size")
    axa = fig.add_axes([0.143, 0.646, 0.315, 0.218])
    for basis, color, label in [("reported molecular formula", COOL, "Single component"), ("formula unit (multicomponent)", WARM, "Multicomponent formula unit")]:
        part = chemistry[chemistry.composition_basis == basis]
        axa.scatter(part.atom_count, part.molar_mass_g_mol, s=15, color=color, alpha=0.65, linewidth=0.3, edgecolors="white", label=f"{label} ({len(part)})")
    axa.set_xscale("log")
    axa.set_yscale("log")
    axa.set_xticks([5, 10, 20, 50, 100, 200], ["5", "10", "20", "50", "100", "200"])
    axa.set_yticks([50, 100, 300, 1000, 3000], ["50", "100", "300", "1,000", "3,000"])
    axa.minorticks_off()
    axa.set_xlabel("Atoms per molecule / formula unit (log scale)", labelpad=3, fontsize=7.3)
    axa.set_ylabel("Molar mass (g/mol; log scale)", labelpad=3, fontsize=7.5)
    axa.set_xlim(chemistry.atom_count.min() * 0.80, chemistry.atom_count.max() * 1.20)
    axa.set_ylim(chemistry.molar_mass_g_mol.min() * 0.72, chemistry.molar_mass_g_mol.max() * 1.30)
    axa.legend(loc="upper left", frameon=False, fontsize=6.4, borderpad=0, labelspacing=0.5, handletextpad=0.3)
    tidy(axa)

    # B: every linked array, ranked rather than unreadable individual labels.
    panel(fig, rects[1], "B", "Structures per dataset")
    axb = fig.add_axes([0.588, 0.646, 0.315, 0.218])
    ranked = known.sort_values("structure_count", ascending=False).reset_index(drop=True)
    ranked[["dataset_id", "structure_count", "source_url", "json_url"]].assign(rank=np.arange(1, len(ranked) + 1)).to_csv(table_dir / "structure_count_ranking.csv", index=False)
    xx = np.arange(1, len(ranked) + 1)
    spectral_line(axb, xx, ranked.structure_count, ranked.structure_count, LogNorm(vmin=ranked.structure_count.min(), vmax=ranked.structure_count.max()), baseline=8, fill_alpha=0.17)
    axb.set_yscale("log")
    axb.set_ylim(8, 3500)
    axb.set_yticks([10, 100, 1000], ["10", "100", "1,000"])
    axb.minorticks_off()
    axb.set_xlim(1, len(ranked))
    axb.set_xticks([1, 100, 200, len(ranked)])
    axb.set_xlabel("Dataset rank (largest first)", labelpad=3)
    axb.set_ylabel("Structure entries (log scale)", labelpad=3)
    median = float(known.structure_count.median())
    axb.text(0.97, 0.92, f"Median {median:,.0f}", transform=axb.transAxes, ha="right", fontsize=7.1, color=MUTED)
    tidy(axb)

    # C: keep only the requested electronic-level comparison.
    panel(fig, rects[2], "C", "Energy models")
    axc2 = fig.add_axes([0.244, 0.363, 0.217, 0.189])
    ee = electronic.head(6).iloc[::-1]
    axc2.barh(ee.index, ee.values, color=count_colors(ee.values), height=0.61)
    axc2.set_xlim(0, 200)
    axc2.set_xticks([0, 50, 100, 150, 200])
    axc2.tick_params(axis="y", length=0, labelsize=7)
    axc2.set_xlabel("Datasets", labelpad=3)
    for i, value in enumerate(ee):
        axc2.text(value + 2.5, i, str(value), va="center", fontsize=6.5)
    tidy(axc2, "x")
    axc2.spines["left"].set_visible(False)
    fig.text(0.085, 0.574, "Electronic structure theory level", fontsize=7.1, color=INK)

    # D: expand the ranking to 20 scientists, with no individual exclusions.
    panel(fig, rects[3], "D", "The scientists")
    axd = fig.add_axes([0.693, 0.363, 0.213, 0.213])
    displayed = contributors.head(20).copy()
    displayed.to_csv(table_dir / "scientist_plot_data.csv", index=False)
    top = displayed.iloc[::-1]
    axd.barh(top.scientist_name, top.dataset_count, height=0.58, color=count_colors(top.dataset_count), linewidth=0)
    axd.set_xlim(0, float(top.dataset_count.max()) * 1.14)
    for i, value in enumerate(top.dataset_count):
        axd.text(value + 1, i, str(int(value)), va="center", fontsize=6.1)
    axd.tick_params(axis="y", length=0, labelsize=6.3)
    axd.xaxis.set_major_locator(MaxNLocator(4, integer=True))
    axd.set_xlabel("Datasets credited", labelpad=3)
    tidy(axd, "x")
    axd.spines["left"].set_visible(False)

    # E: aligned bars/line with distinct axes and explicit study-year scope.
    panel(fig, rects[4], "E", "Landscapes through time")
    axe = fig.add_axes([0.144, 0.190, 0.281, 0.104])
    axe.bar(annual.year, annual.landscapes, width=0.76, color=SPECTRAL(year_norm(annual.year)), alpha=0.93)
    axe.set_ylabel("Datasets / year", color=INK, labelpad=3, fontsize=7.2)
    axe.yaxis.set_major_locator(MaxNLocator(4, integer=True))
    axe.set_xlim(min(years) - 0.7, max(years) + 0.7)
    axe.set_xticks([2005, 2010, 2015, 2020, 2025])
    axe.tick_params(axis="x", labelbottom=False)
    tidy(axe)
    axe2 = axe.twinx()
    axe2.plot(annual.year, annual.structures / 1000, color=INK, marker="o", markersize=2.5, linewidth=1.2)
    axe2.set_ylabel("Structure entries\n(thousands)", color=INK, labelpad=3, fontsize=7.0)
    axe2.spines[["top", "left"]].set_visible(False)
    axe2.tick_params(axis="y", labelsize=7, length=2.5, width=0.5)
    axe2.set_ylim(bottom=0)
    axe2.yaxis.set_major_locator(MaxNLocator(4))
    axec = fig.add_axes([0.144, 0.100, 0.281, 0.074], sharex=axe)
    spectral_line(axec, annual.year, annual.cumulative_datasets, annual.year, year_norm, step=True, fill_alpha=0.13, linewidth=1.5)
    axec.set_ylabel("Cumulative datasets", fontsize=7.2, labelpad=3)
    axec.set_xlabel("Study year", labelpad=3, fontsize=7.4)
    axec.set_ylim(0, len(dated) * 1.20)
    axec.set_yticks([0, 100, 200])
    axec.text(annual.year.iloc[-1], annual.cumulative_datasets.iloc[-1] + 9, str(int(annual.cumulative_datasets.iloc[-1])), ha="right", fontsize=7, color=to_hex(SPECTRAL(year_norm(annual.year.iloc[-1]))), weight="bold")
    tidy(axec)
    not_assigned = int(df[df.study_year.isna()].structure_count.sum())
    fig.text(0.085, 0.045, f"{n - len(dated)} searches with ranges / pre-2010 dates excluded from annual bins;", fontsize=6.1, color=MUTED)
    fig.text(0.085, 0.034, f"{not_assigned:,} stored structure entries have no single study year.", fontsize=6.1, color=MUTED)

    # F: retain only cumulative unique CSP papers.
    panel(fig, rects[5], "F", "The linked literature")
    axf2 = fig.add_axes([0.588, 0.100, 0.315, 0.194])
    spectral_line(axf2, cumulative.year, cumulative.cumulative_unique_papers, cumulative.year, year_norm, step=True, fill_alpha=0.13, linewidth=1.5)
    axf2.set_ylabel("Unique papers", fontsize=7.5, labelpad=3)
    axf2.set_xlabel("Publication year (cumulative)", fontsize=7.2, labelpad=2)
    axf2.set_xticks([2000, 2010, 2020, 2025])
    axf2.set_xlim(min(cumulative.year), max(cumulative.year) + 1)
    axf2.set_ylim(0, len(csp_papers) * 1.18)
    axf2.set_yticks([0, 25, 50, 75])
    axf2.text(cumulative.year.iloc[-1] + 0.1, len(csp_papers) + 3, str(len(csp_papers)), ha="right", color=to_hex(SPECTRAL(year_norm(cumulative.year.iloc[-1]))), fontsize=7, weight="bold")
    tidy(axf2)

    output_dir = base / "figures"
    output_dir.mkdir(exist_ok=True)
    pdf_dir = base / "output/pdf"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    plot_axes = {"A": axa, "B": axb, "C": axc2, "D": axd, "E_annual": axe, "E_structures": axe2, "E_cumulative": axec, "F": axf2}
    expected_heights = {"A": 0.218, "B": 0.218, "C": 0.189, "D": 0.213, "E_annual": 0.104, "E_structures": 0.104, "E_cumulative": 0.074, "F": 0.194}
    geometry = {name: list(ax.get_position().bounds) for name, ax in plot_axes.items()}
    if not all(np.isclose(geometry[name][3], height, rtol=0, atol=1e-12) for name, height in expected_heights.items()):
        raise RuntimeError("A plot height changed during horizontal compaction")
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
    fig.savefig(pdf_dir / "database_in_numbers.pdf", metadata={"Title": "The CPOSS database in numbers", "Author": "CPOSS metadata analysis", "Subject": "CSP dataset metadata, structure counts and linked publications", "CreationDate": timestamp, "ModDate": timestamp})
    fig.savefig(output_dir / "database_in_numbers.png", dpi=300)
    plt.close(fig)
    font_info["all_figure_text_families"] = sorted(actual_fonts)
    font_info["text_outside_page"] = outside
    manifest["font_verification"] = font_info
    manifest["colour_scheme"] = {"name": "CPOSS Spectral-inspired", "anchors": SPECTRAL_ANCHORS, "white_page_adjustment": "Darker gold midtone", "molecular_components": {"single_component": COOL, "multicomponent": WARM}, "count_panels": "Within-panel logarithmic colour mapping in B, C and D; axes and bar lengths carry the quantitative scales", "time_panels": "Common study/publication year colour ramp in E and F; structure-entry line is charcoal", "year_limits": [year_norm.vmin, year_norm.vmax], "new_colourbar_axes": False}
    manifest["figure_presentation"] = {"title": "The CPOSS database in numbers", "layout": "Compact journal-style A4 page with aligned panel baselines and reduced vertical and horizontal gutters", "horizontal_column_inset_fraction": 0.018, "plot_geometry_fraction": geometry, "plot_heights_unchanged": True, "title_font_size_pt": 14, "panel_heading_font_size_pt": 9, "summary_strip_scale": strip_scale, "panels": {"A": "Molecular size", "B": "Structures per dataset", "C": "Electronic structure theory level", "D": "Scientist credits (top 20)", "E": "Annual landscapes and structure entries; cumulative datasets", "F": "Cumulative unique CSP papers"}, "displayed_scientists": list(displayed.scientist_name), "scientist_plot_exclusions": [], "cumulative_datasets_endpoint": int(annual.cumulative_datasets.iloc[-1]), "cumulative_dataset_scope": "Only single unambiguous source study years; intervals and pre-2010 dates excluded"}
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
    note = f"""The CPOSS database in numbers. Metadata were extracted from {manifest['case_pages_with_searches']} molecule pages reachable from the CPOSS index, representing {n} distinct CSP searches in repository snapshot {manifest['snapshot_revision']} (accessed {manifest['accessed_date']}). Each explicitly linked search is one dataset; its energy models are not separate datasets. A, molar mass versus total atom count on logarithmic axes, calculated from reported formulas with one point per documented molecular system ({len(chemistry)} systems). Multicomponent formulas retain explicitly written stoichiometry; hydrogens are included, and unit-cell atom counts are not used. B, linked Chemiscope structure-array entries per dataset, ranked on a logarithmic axis ({len(known)}/{n} files; median {known.structure_count.median():.0f}); experimental-reference entries and repeated filename labels are retained, so {total:,} is a stored-entry total, not a count of globally distinct predictions or all structures originally generated. Four linked JSON files are missing. C, electronic structure theory level, showing dataset frequencies for the six most frequent categories. Categories overlap and electronic levels may describe molecular or multipole calculations rather than periodic DFT. Complete potential-family and electronic-method data are tabulated separately. D, dataset credits for the 20 most frequently credited scientists, including Sally Price, with full credit for each named contributor and no inferred authorship from paper author lists ({credited_n}/{n} searches have a named scientist). The full metadata retain all {len(contributors)} scientists. E, annual CSP-search counts (upper bars) and stored structure entries (upper line), plus cumulative CSP-dataset counts (lower curve), using single unambiguous years from the source Date field ({len(dated)}/{n} datasets). Date ranges and pre-2010 dates are excluded from annual and cumulative bins; the cumulative curve therefore ends at {len(dated)}, not {n}. These are study dates, not release/deposition dates. F, cumulative unique linked CSP papers by publication year ({len(csp_papers)} papers). Papers are deduplicated across datasets by DOI or canonical URL; explicit within-page Study_ID publication pointers are followed and labelled inferred. Experimental CSD citations are recorded separately. Helvetica is used and embedded throughout; the figure is A4 portrait, with a vector PDF and 300 dpi PNG.
"""
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

The figure shows molecular size in panel A and scientist credits in panel D. The scientist panel shows the 20 most frequently credited scientists, including Sally Price; the full source tables and headline count retain all {len(contributors)} scientists. Potential-family bars, paper-per-dataset bars, panel subtitles and the footer are omitted from the figure; their data, provenance and counting rules remain in these tables and the caption. The cumulative dataset curve includes only the {len(dated)} searches with a single study year.

The page is exactly A4 portrait, with compact vertical and horizontal gutters, unchanged plot heights, aligned plot baselines, a 14 pt title and 9 pt panel headings. All text resolves to Helvetica, with regular/bold faces extracted from the system Helvetica collection for embedding; no proprietary font file is redistributed. The vector PDF and 300 dpi PNG have the same layout. `caption.md` provides the standalone figure caption. `tables/` holds complete results, `sources/` holds archived HTML/metadata, and `manifest.json` records scope, revision, date, fonts and package versions.
"""
    (base / "report.md").write_text(report)
