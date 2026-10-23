"""Verify the delivered scientific accounting, sources, PDF and PNG."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image
from pypdf import PdfReader

from analyse import git_sha

BASE = Path(__file__).resolve().parent


def main():
    manifest = json.loads((BASE / "manifest.json").read_text())
    d = pd.read_csv(BASE / "tables/datasets.csv")
    a = pd.read_csv(BASE / "tables/annual_counts.csv")
    r = pd.read_csv(BASE / "tables/dataset_papers.csv")
    p = pd.read_csv(BASE / "tables/papers.csv")
    c = pd.read_csv(BASE / "tables/cumulative_papers.csv")
    cc = pd.read_csv(BASE / "tables/dataset_contributors.csv")
    scientists = pd.read_csv(BASE / "tables/contributors.csv")
    provenance = pd.read_csv(BASE / "tables/provenance.csv")
    files = pd.read_csv(BASE / "tables/structure_file_audit.csv")
    audit = pd.read_csv(BASE / "tables/page_audit.csv")
    archive_counts = pd.read_csv(BASE / "tables/structure_archive_counts.csv")
    dataset_archives = pd.read_csv(BASE / "tables/dataset_archive_counts.csv")
    workbook_counts = pd.read_csv(BASE / "tables/structure_count_reconciliation.csv")
    model_counts = pd.read_csv(BASE / "tables/structure_model_counts.csv")
    plot_data = pd.read_csv(BASE / "tables/plot_datasets.csv")
    energy_models = pd.read_csv(BASE / "tables/energy_models.csv")
    archive_summary = json.loads((BASE / "sources/structure_archive_counts.json").read_text())
    count_provenance = pd.read_csv(BASE / "tables/structure_count_provenance.csv")
    checks = []

    def check(condition, description):
        if not condition:
            raise AssertionError(description)
        checks.append(description)

    check(len(d) == manifest["datasets"] and d.dataset_id.is_unique, "Dataset identifiers are unique and match manifest")
    check(int(a.landscapes.sum()) == int(d.study_year.notna().sum()), "Annual landscape totals equal all datasets with single study years")
    check(a.cumulative_datasets.iloc[-1] == int(d.study_year.notna().sum()) and np.array_equal(a.cumulative_datasets, a.landscapes.cumsum()), "Cumulative dataset series sums annual counts and ends at all single-year datasets")
    check(np.isclose(a.structures.sum(), plot_data[plot_data.study_year.notna()].structure_count.sum()), "Annual structure totals equal dated archive structure counts")
    check(np.array_equal(a.archive_structure_files, a.structures), "Annual structure column explicitly identifies the archive counting basis")
    check(np.isclose(d.structure_count.sum(), files.structure_count.sum()), "Structure-file and dataset totals agree")
    check(archive_summary["snapshot_revision"] == manifest["snapshot_revision"], "Archive audit and figure use the same frozen revision")
    check(archive_counts.status.eq("calculated").all() and dataset_archives.complete.all(), "Every documented model archive and dataset has a complete count")
    check(set(archive_counts.assign(model_id=archive_counts.model_id.astype(str)).set_index(["dataset_id", "model_id"]).index) == set(energy_models[energy_models.kind == "energy_model"].assign(model_id=lambda s: s.model_id.astype(str)).set_index(["dataset_id", "model_id"]).index), "All and only documented energy-model archives are counted")
    check(archive_counts.git_blob_sha.is_unique and archive_counts.duplicate_member_names.eq(0).all(), "No duplicate archive blobs or repeated coordinate member paths are counted")
    check(archive_counts.primary_format.eq(".res").all() and archive_counts.coordinate_files.equals(archive_counts.res_files), "All coordinate counts are RES file counts without mixed-format duplication")
    check(int(archive_counts.coordinate_files.sum()) == int(dataset_archives.archive_coordinate_files.sum()) == int(plot_data.structure_count.sum()) == archive_summary["coordinate_files"], "Model, dataset, figure and archive-summary totals agree")
    check(set(plot_data.dataset_id) == set(d.dataset_id) and plot_data.structure_count.notna().all(), "Figure includes complete archive counts for every documented dataset")
    check(np.isclose(plot_data.visualization_structure_count.sum(), d.structure_count.sum()), "Original visualization counts are preserved separately from figure archive counts")
    check(int(model_counts.records.sum()) == int(workbook_counts.structure_model_records.sum()), "Workbook model records aggregate to workbook dataset totals")
    check(set(count_provenance.dataset_id) == set(d.dataset_id) and count_provenance.source_url.notna().all(), "All revised count scopes have complete per-dataset source provenance")
    check(count_provenance.loc[count_provenance.status == "missing", "value"].isna().all(), "Missing visualization values remain missing in revised provenance")
    check(not model_counts.duplicated(["dataset_id", "model_id"]).any(), "Unnumbered workbook energies are not silently mapped to an existing numbered model")
    check(files.loc[files.status == "calculated", "property_lengths_valid"].eq(True).all(), "Every structure-target property array has the correct length")
    check(d.loc[d.structure_count_status == "missing", "structure_count"].isna().all(), "Missing structure counts remain missing rather than zero")
    check(d.release_year.isna().all(), "Unavailable release/deposition years remain missing")
    check(p.paper_id.is_unique and not r.duplicated(["dataset_id", "paper_id", "relation"]).any(), "References and dataset-paper associations are deduplicated")
    csp_ids = set(r.loc[r.relation == "csp_study", "paper_id"])
    paper_count = len(p[p.paper_id.isin(csp_ids) & p.is_paper])
    check(c.cumulative_unique_papers.iloc[-1] == paper_count, "Cumulative paper endpoint equals the deduplicated CSP-paper total")
    counts = cc.groupby("scientist_name").dataset_id.nunique()
    check(scientists.set_index("scientist_name").dataset_count.sort_index().equals(counts.sort_index()), "Scientist counts agree with explicit dataset-contributor relationships")
    check({"Sally Price", "Louise Price"}.issubset(set(scientists.scientist_name)), "Sally Price and Louise Price remain separate contributors")
    check(set(d.dataset_id) == set(provenance.dataset_id), "Every dataset has field provenance")
    check(provenance.source_url.notna().all() and provenance.status.isin(["reported", "calculated", "inferred", "missing"]).all(), "Provenance statuses and source URLs are complete")
    for row in audit.itertuples():
        if row.status == "accessible":
            raw = (BASE / "sources/html" / (row.git_blob_sha + ".html")).read_bytes()
            check(git_sha(raw) == row.git_blob_sha, "Source HTML SHA verified: " + row.path)
    pdf = PdfReader(BASE / "output/pdf/database_in_numbers.pdf")
    check(len(pdf.pages) == 1, "PDF has exactly one page")
    page = pdf.pages[0]
    check(len(page.images) == 0, "PDF plots remain vector graphics without embedded raster images")
    check(abs(float(page.mediabox.width) - 210 / 25.4 * 72) < 0.01 and abs(float(page.mediabox.height) - 297 / 25.4 * 72) < 0.01, "PDF is exactly A4 portrait")
    fonts = []
    for ref in page["/Resources"]["/Font"].values():
        font = ref.get_object()
        name = str(font["/BaseFont"])
        check("Helvetica" in name, "PDF font is Helvetica: " + name)
        descendants = font.get("/DescendantFonts", [])
        for ref_child in descendants:
            descriptor = ref_child.get_object()["/FontDescriptor"].get_object()
            check(any(k in descriptor for k in ["/FontFile", "/FontFile2", "/FontFile3"]), "PDF font is embedded: " + name)
        fonts.append(name)
    text = page.extract_text()
    check("The CPOSS database in numbers" in text, "Updated PDF title is present and extractable")
    check("Cumulative datasets" in text, "Cumulative dataset panel is present")
    check(f"{archive_summary['coordinate_files']:,}" in text and "archived structure files" in text, "PDF headline displays the reconciled archive count and its counting basis")
    check("Electronic structure theory level" in text and "Electronic levels (top 6)" not in text, "Requested electronic-structure label replaces the previous wording")
    removed_strings = ["CRYSTAL STRUCTURE PREDICTION", "An audit of the publicly linked", "23 OCT 2026", "linked files counted", "Potential families", "Dataset counts; method categories", "documented systems; composition", "CSP study papers; experimental", "Source study year;", "Linked papers per dataset", "Includes molecular calculations;", "Hydrogens included;", "datasets have named credits", "louiseprice.github.io/CPOSS_Database", "Entries in 307 linked Chemiscope files"]
    check(not any(s in text for s in removed_strings), "All annotated text removals are absent from the PDF")
    presentation = manifest["figure_presentation"]
    check("Sally Price" in text and "Sally Price" in presentation["displayed_scientists"] and len(presentation["displayed_scientists"]) == 20, "Contributor chart includes 20 scientists, including Sally Price")
    expected_heights = {"A": 0.218, "B": 0.218, "C": 0.189, "D": 0.213, "E_annual": 0.104, "E_structures": 0.104, "E_cumulative": 0.074, "F": 0.194}
    check(all(np.isclose(presentation["plot_geometry_fraction"][name][3], height, rtol=0, atol=1e-12) for name, height in expected_heights.items()), "All plot heights are unchanged during horizontal compaction")
    check(presentation["panels"]["A"] == "Molecular size" and presentation["panels"]["D"].startswith("Scientist credits"), "Molecular size and scientist panels are swapped to A and D")
    check(presentation["summary_strip_scale"] == 0.7, "Summary strip is scaled to 70 percent")
    image = Image.open(BASE / "figures/database_in_numbers.png")
    check(abs(image.size[0] - 210 / 25.4 * 300) <= 1 and abs(image.size[1] - 297 / 25.4 * 300) <= 1, "PNG dimensions match A4 at 300 dpi")
    check(abs(image.info.get("dpi", (0, 0))[0] - 300) < 0.1, "PNG declares 300 dpi")
    result = {"status": "passed", "checks_passed": len(checks), "datasets": len(d), "archive_structure_files": int(plot_data.structure_count.sum()), "model_archives_counted": len(archive_counts), "visualization_entries": int(d.structure_count.sum()), "workbook_energy_records": int(model_counts.records.sum()), "named_scientists": len(scientists), "unique_csp_papers": paper_count, "unique_scientific_papers_all_scopes": int(p.is_paper.sum()), "unique_linked_references_all_scopes": len(p), "pdf_fonts": fonts, "png_dimensions": image.size, "checks": checks}
    (BASE / "verification.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "checks"}, indent=2))


if __name__ == "__main__":
    main()
