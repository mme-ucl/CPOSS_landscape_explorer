"""Rearrange the reviewed vector figure into three columns and two rows.

Panels are translated at their original physical size. The approved software
panel replaces C, using its own vector PDF at exactly the same dimensions.
Re-run this after rebuilding the portrait PDF or the software panel.
"""
from __future__ import annotations

import copy
import csv
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from PIL import Image
from pypdf import PdfReader, PdfWriter, Transformation
from pypdf.generic import RectangleObject


BASE = Path(__file__).resolve().parent


def table(name):
    with (BASE / "tables" / (name + ".csv")).open() as stream:
        return list(csv.DictReader(stream))


def panel_c_inputs():
    folder = BASE / "workbook_crosscheck"
    counts_path = folder / "proposed_panel_c_counts.csv"
    with counts_path.open() as stream:
        counts = list(csv.DictReader(stream))
    with (folder / "proposed_panel_c_evidence.csv").open() as stream:
        evidence = list(csv.DictReader(stream))
    datasets = {row["dataset_id"] for row in table("plot_datasets")}
    pairs = {(row["program"], row["dataset_id"]) for row in evidence}
    if len(pairs) != len(evidence) or any(dataset not in datasets for _, dataset in pairs):
        raise ValueError("Software evidence must contain distinct, documented search/program pairs")
    for row in counts:
        if int(row["denominator"]) != len(datasets) or int(row["datasets"]) != len({
                dataset for program, dataset in pairs if program == row["program"]}):
            raise ValueError("Software frequencies do not agree with their search-level evidence")
    audit = json.loads((folder / "audit_summary.json").read_text())
    return {
        "title": "Reported CSP software",
        "counts": {row["program"]: int(row["datasets"]) for row in counts},
        "denominator": len(datasets),
        "counting_rule": "Explicit program mentions; one count per search and program family; versions pooled; categories overlap; bare Study_ID pointers not expanded",
        "counts_csv": str(counts_path.relative_to(BASE)),
        "counts_csv_sha256": hashlib.sha256(counts_path.read_bytes()).hexdigest(),
        "workbook_path": audit["workbook_path"],
        "workbook_sha256": audit["workbook_sha256"],
        "matched_energy_models": audit["matched_archived_models"],
    }


def write_caption():
    manifest = json.loads((BASE / "manifest.json").read_text())
    datasets = table("plot_datasets")
    chemistry = table("molecular_systems")
    contributors = table("contributors")
    archives = table("structure_archive_counts")
    annual = table("annual_counts")
    papers = table("cumulative_papers")
    n = len(datasets)
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
\textbf{{(C)}} Reported CSP software, obtained from the curation
workbook's energy-model records matched to the documented archives.
Each search is counted once per program family, pooling program
versions. Categories overlap; only explicit program mentions are
counted, and bare Study\_ID cross-references are not expanded.
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


def main():
    source = BASE / "output/pdf/database_in_numbers.pdf"
    output = source.with_name("database_in_numbers_3x2.pdf")
    png = BASE / "figures/database_in_numbers_3x2.png"
    pdftoppm = shutil.which("pdftoppm")
    if pdftoppm is None:
        raise RuntimeError("pdftoppm is required to render and verify the result")

    reader = PdfReader(source)
    if len(reader.pages) != 1 or reader.pages[0].rotation:
        raise ValueError("Expected the reviewed, unrotated, single-page figure")
    original = reader.pages[0]
    width, height = float(original.mediabox.width), float(original.mediabox.height)
    if len(original.images):
        raise ValueError("Expected the original vector figure without raster images")
    software_source = source.with_name("panel_c_software_proposal.pdf")
    software_reader = PdfReader(software_source)
    if len(software_reader.pages) != 1 or software_reader.pages[0].rotation or len(software_reader.pages[0].images):
        raise ValueError("Panel C must be one unrotated vector page")
    software = software_reader.pages[0]
    software_info = panel_c_inputs()
    software_text = software.extract_text()
    if software_info["title"] not in software_text or any(
            program not in software_text or str(count) not in software_text
            for program, count in software_info["counts"].items()):
        raise ValueError("The software panel PDF does not match the approved counts")

    # Original panel heading anchors and crop boundaries, in page fractions.
    # Crops include all axis labels, legends, headings and panel E's two notes.
    panels = {
        "A": (0.085, 0.884, 0.610),
        "B": (0.530, 0.884, 0.610),
        "C": (0.085, 0.596, 0.330),
        "D": (0.530, 0.596, 0.330),
        "E": (0.085, 0.314, 0.027),
        "F": (0.530, 0.314, 0.027),
    }
    margin, gutter, heading_padding = 12.0, 18.0, 5.0
    panel_width = 0.425 * width
    first_row_depth = max((panels[p][1] - panels[p][2]) * height for p in "ABC")
    second_row_depth = max((panels[p][1] - panels[p][2]) * height for p in "DEF")
    row_pitch = first_row_depth + 26.0
    header_depth = (1 - panels["A"][1]) * height
    canvas_width = 2 * margin + 3 * panel_width + 2 * gutter
    canvas_height = header_depth + row_pitch + second_row_depth + margin
    row_headings = [canvas_height - header_depth, margin + second_row_depth]

    writer = PdfWriter()
    writer.pdf_header = reader.pdf_header
    page = writer.add_blank_page(width=canvas_width, height=canvas_height)
    placements = {}

    def place(name, bounds, dx, dy, *, source_page=original, source_path=source):
        tile = copy.copy(source_page)
        tile.cropbox = RectangleObject(bounds)
        tile.trimbox = RectangleObject(bounds)
        transform = Transformation().translate(tx=dx, ty=dy)
        if transform.ctm[:4] != (1, 0, 0, 1):
            raise AssertionError("Only translations are allowed")
        page.merge_transformed_page(tile, transform, expand=False)
        destination = [bounds[0] + dx, bounds[1] + dy, bounds[2] + dx, bounds[3] + dy]
        if not (0 <= destination[0] < destination[2] <= canvas_width + 1e-8
                and 0 <= destination[1] < destination[3] <= canvas_height + 1e-8):
            raise AssertionError(f"Content outside the destination page: {name}")
        placements[name] = {
            "source_pdf": str(source_path.relative_to(BASE)),
            "source_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
            "source_crop_pt": list(bounds),
            "translation_pt": [dx, dy],
            "destination_crop_pt": destination,
            "scale_x": 1,
            "scale_y": 1,
            "rotation_degrees": 0,
        }

    # Recenter the complete title and summary strip without changing their size.
    place("header", (0, 0.895 * height, width, height),
          (canvas_width - width) / 2, canvas_height - height)
    for index, (name, (heading_x, heading_y, bottom)) in enumerate(panels.items()):
        row, column = divmod(index, 3)
        left = heading_x * width - heading_padding
        bounds = (left, bottom * height, left + panel_width,
                  heading_y * height + heading_padding)
        destination_left = margin + column * (panel_width + gutter)
        if name == "C":
            replacement_width = float(software.mediabox.width)
            replacement_height = float(software.mediabox.height)
            if abs(replacement_width - panel_width) > 0.01 or abs(replacement_height - (bounds[3] - bounds[1])) > 0.01:
                raise ValueError("Replacement panel C must retain the original physical dimensions")
            place(name, (0, 0, replacement_width, replacement_height), destination_left,
                  row_headings[row] - replacement_height + heading_padding,
                  source_page=software, source_path=software_source)
        else:
            place(name, bounds, destination_left - left,
                  row_headings[row] - heading_y * height)

    metadata = {key: value for key, value in (reader.metadata or {}).items()
                if isinstance(value, str)}
    metadata["/Subject"] = "CPOSS database in numbers; three columns by two rows; workbook-derived CSP software panel C"
    writer.add_metadata(metadata)
    page.compress_content_streams()
    writer.compress_identical_objects()
    with output.open("wb") as stream:
        writer.write(stream)

    result = PdfReader(output)
    if len(result.pages) != 1 or result.pages[0].rotation or len(result.pages[0].images):
        raise AssertionError("Output must remain a single unrotated vector page")
    font_names = []
    for font_ref in result.pages[0]["/Resources"]["/Font"].values():
        font = font_ref.get_object()
        font_names.append(str(font["/BaseFont"]))
        if "Helvetica" not in font_names[-1]:
            raise AssertionError("Original Helvetica fonts must be retained")
        for descendant_ref in font.get("/DescendantFonts", []):
            descriptor = descendant_ref.get_object()["/FontDescriptor"].get_object()
            if not any(key in descriptor for key in ("/FontFile", "/FontFile2", "/FontFile3")):
                raise AssertionError("Fonts must remain embedded")

    subprocess.run([pdftoppm, "-r", "300", "-singlefile", "-png", str(output),
                    str(png.with_suffix(""))], check=True)
    with Image.open(png) as preview:
        expected = [round(canvas_width / 72 * 300), round(canvas_height / 72 * 300)]
        if any(abs(actual - target) > 1 for actual, target in zip(preview.size, expected)):
            raise AssertionError("PNG dimensions must match the PDF at 300 dpi")
        dimensions = list(preview.size)

    verification = {
        "status": "passed",
        "source_pdf": str(source.relative_to(BASE)),
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "output_pdf": str(output.relative_to(BASE)),
        "output_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "layout": [["A", "B", "C"], ["D", "E", "F"]],
        "page_size_pt": [canvas_width, canvas_height],
        "page_size_mm": [canvas_width / 72 * 25.4, canvas_height / 72 * 25.4],
        "png_dimensions": dimensions,
        "png_dpi": 300,
        "fonts": sorted(set(font_names)),
        "vector_graphics": True,
        "all_panel_scales_unchanged": True,
        "all_panel_rotations_zero": True,
        "panel_c": software_info,
        "placements": placements,
    }
    (BASE / "verification_3x2.json").write_text(json.dumps(verification, indent=2) + "\n")
    write_caption()
    print(json.dumps({key: value for key, value in verification.items() if key != "placements"}, indent=2))


if __name__ == "__main__":
    main()
