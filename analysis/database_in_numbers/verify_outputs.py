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
    checks = []

    def check(condition, description):
        if not condition:
            raise AssertionError(description)
        checks.append(description)

    check(len(d) == manifest["datasets"] and d.dataset_id.is_unique, "Dataset identifiers are unique and match manifest")
    check(int(a.landscapes.sum()) == int(d.study_year.notna().sum()), "Annual landscape totals equal all datasets with single study years")
    check(np.isclose(a.structures.sum(), d[d.study_year.notna()].structure_count.sum()), "Annual structure totals equal dated known structure counts")
    check(np.isclose(d.structure_count.sum(), files.structure_count.sum()), "Structure-file and dataset totals agree")
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
    check("The database in numbers" in page.extract_text(), "PDF text is extractable")
    image = Image.open(BASE / "figures/database_in_numbers.png")
    check(abs(image.size[0] - 210 / 25.4 * 300) <= 1 and abs(image.size[1] - 297 / 25.4 * 300) <= 1, "PNG dimensions match A4 at 300 dpi")
    check(abs(image.info.get("dpi", (0, 0))[0] - 300) < 0.1, "PNG declares 300 dpi")
    result = {"status": "passed", "checks_passed": len(checks), "datasets": len(d), "stored_structure_entries": int(d.structure_count.sum()), "named_scientists": len(scientists), "unique_csp_papers": paper_count, "unique_scientific_papers_all_scopes": int(p.is_paper.sum()), "unique_linked_references_all_scopes": len(p), "pdf_fonts": fonts, "png_dimensions": image.size, "checks": checks}
    (BASE / "verification.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "checks"}, indent=2))


if __name__ == "__main__":
    main()
