"""Write the three-scope structure-count reconciliation and field provenance."""
import json
from pathlib import Path

import pandas as pd


def write_structure_reconciliation(base):
    tables = base / "tables"
    manifest = json.loads((base / "manifest.json").read_text())
    summary = json.loads((base / "sources/structure_archive_counts.json").read_text())
    workbook_summary = json.loads((base / "sources/structure_count_reconciliation.json").read_text())
    datasets = pd.read_csv(tables / "datasets.csv")
    workbooks = pd.read_csv(tables / "structure_count_reconciliation.csv")
    archives = pd.read_csv(tables / "structure_archive_counts.csv")
    dataset_archives = pd.read_csv(tables / "dataset_archive_counts.csv")
    models = pd.read_csv(tables / "structure_model_counts.csv")
    comparison = workbooks.merge(dataset_archives, on="dataset_id", validate="one_to_one")
    comparison["archive_count_status"] = comparison.complete.map({True: "calculated", False: "missing"})
    comparison["accessed_date"] = manifest["accessed_date"]
    comparison["snapshot_revision"] = manifest["snapshot_revision"]
    comparison.to_csv(tables / "reconciled_dataset_counts.csv", index=False)
    differences = archives[~archives.counts_match].copy()
    differences["archive_minus_workbook"] = differences.coordinate_files - differences.workbook_records
    differences.sort_values("archive_minus_workbook").to_csv(tables / "archive_workbook_discrepancies.csv", index=False)
    unknown = models[models.html_model_matches != 1]
    capped = comparison[comparison.visualization_entries == 1000]
    dated_ids = set(datasets.loc[datasets.study_year.notna(), "dataset_id"])
    dated_files = int(comparison.loc[comparison.dataset_id.isin(dated_ids), "archive_coordinate_files"].sum())
    undated_files = int(comparison.loc[~comparison.dataset_id.isin(dated_ids), "archive_coordinate_files"].sum())
    provenance = []
    originals = datasets.set_index("dataset_id")
    for row in comparison.itertuples():
        original = originals.loc[row.dataset_id]
        definitions = [
            ("visualization_entries", row.visualization_entries, original.json_url, original.structure_count_status, "Linked Chemiscope structures-array length"),
            ("workbook_filename_rows", row.workbook_rows, row.workbook_url, row.status, "Actual nonempty Filename rows; formatted worksheet dimensions ignored"),
            ("workbook_numeric_energy_records", row.structure_model_records, row.workbook_url, row.status, "Finite numeric lattice-energy cells attached to Filename rows; separate energy columns retained"),
            ("archive_structure_files", row.archive_coordinate_files, row.archive_urls, row.archive_count_status, summary["count_definition"]),
        ]
        for field, value, source, status, definition in definitions:
            provenance.append({"dataset_id": row.dataset_id, "field": field, "value": value, "status": status,
                               "source_url": source, "definition": definition, "accessed_date": manifest["accessed_date"],
                               "snapshot_revision": manifest["snapshot_revision"]})
    pd.DataFrame(provenance).to_csv(tables / "structure_count_provenance.csv", index=False)
    examples = comparison[comparison.dataset_id.isin(["BTXXXIIA", "TrinitrobenzeneA", "UreaA", "AspirinA"])].sort_values("dataset_id")
    rows = "\n".join(f"| {r.dataset_id} | {int(r.visualization_entries):,} | {r.workbook_rows:,} | {r.structure_model_records:,} | {r.archive_coordinate_files:,} |" for r in examples.itertuples())
    missing_json = comparison[comparison.visualization_entries.isna()]
    note = f"""# Reconciliation of the CPOSS structure count

**The full documented energy-model archives contain {summary['coordinate_files']:,} RES structure files.** This supports the manuscript's statement that the collection contains more than 500,000 stored structures, provided structures represented under separate energy models are counted separately. It does not establish more than 500,000 geometrically unique crystals.

The earlier **{workbook_summary['visualization_entries']:,}** total measured only the linked Chemiscope visualization exports. Presenting it as the size of the complete downloadable collection was too narrow. The corrected figure uses coordinate-archive counts throughout its headline, dataset ranking and annual structure series.

| Measurement | Total | Meaning |
| --- | ---: | --- |
| Linked visualization entries | {workbook_summary['visualization_entries']:,} | 307 available JSON exports; four missing |
| Workbook Filename rows | {workbook_summary['mapped_workbook_rows']:,} | Complete per-search tables, all 311 datasets |
| Workbook rows with at least one numeric model energy | {workbook_summary['rows_with_any_model_energy']:,} | Rows with some recorded lattice-energy result |
| Numeric structure-energy records | {workbook_summary['structure_model_records']:,} | Sum of finite numeric lattice-energy cells across {workbook_summary['model_columns']} energy columns |
| **Archived coordinate files (figure count)** | **{summary['coordinate_files']:,}** | **All {summary['archives_counted']} explicitly documented energy-model ZIPs, all {len(comparison)} datasets** |

These measurements overlap and must not be added together. The energy-record count is not an alternative number of unique geometries.

## How the archive count was verified

The audit follows each of the 509 explicitly documented energy-model ZIP links in `energy_models.csv`, using the frozen repository revision `{manifest['snapshot_revision']}` (accessed {manifest['accessed_date']}). Every archive was downloaded and its Git blob SHA-1 checked against the repository tree. All 509 were readable and contained RES files; no model archive was missing. All 509 archive hashes are distinct.

Only actual `.res` members are counted. Directory entries, `__MACOSX` resource forks and AppleDouble `._` files are excluded. There are no repeated coordinate-member names within an archive and no CIF/PDB/XYZ alternatives in these 509 archives. Ancillary periodic-DFT supplements and unrelated repository ZIPs are outside this count, avoiding an additional sum of overlapping representations. The reproducible counter reports format inventories and missing/error statuses rather than assuming zero on failure.

This is a count of stored coordinate files across model-specific archives. It retains experimental reference structures and possible repeated geometries across models or searches. Coordinate parsing and crystallographic/geometric deduplication have not been performed. The number of candidates originally generated, rejected or optimized before deposition remains unknown.

## Why the visualization count is smaller

**{len(capped)} linked JSON exports contain exactly 1,000 entries.** Their associated complete workbooks contain {int(capped.workbook_rows.sum()):,} Filename rows, compared with {int(capped.visualization_entries.sum()):,} visualization entries. This demonstrates that many visualizations represent subsets; it does not establish a universal export limit. The {len(missing_json)} missing JSON links still have intact model archives, contributing **{int(missing_json.archive_coordinate_files.sum()):,}** coordinate files. Visualization rows also generally combine multiple energy columns for the same filename, whereas the downloadable models contain separate coordinate representations.

| Dataset | Visualization entries | Workbook rows | Numeric energy records | Archived RES files |
| --- | ---: | ---: | ---: | ---: |
{rows}

For UreaA, the two model archives contain 850 and 793 structures, giving 1,643 stored model-specific files; its visualization has 850 entries. For BTXXXIIA, the archives contain 8,829 and 9,976 RES files, giving 18,805, compared with a 1,000-entry visualization.

## Why the workbook and archive totals also differ

**{summary['matching_workbook_counts']} of {len(archives)} model archives** have exactly the same coordinate-file count as their corresponding numeric workbook energy column. The remaining **{len(differences)}** disagree. Numbered energy columns that match documented HTML models contain **{int(archives.workbook_records.sum()):,}** numeric records, **{int(archives.workbook_records.sum() - archives.coordinate_files.sum()):,}** more than the archives. The dominant shortfalls are XXVIIA model 1 (1,000 RES files versus 15,803 energy records), BTXXVIA model 1 (7,726 versus 16,225), and BTXXXIIA model 1 (8,829 versus 15,042). Other archives contain extra structures relative to their energy columns. Experimental references and records without numeric energy cells are possible explanations, but the individual identities and causes of these differences were not established.

The workbook and archive versions or retained subsets are therefore not uniformly aligned. The count in the figure is based on the coordinate files actually present, rather than filling these differences from the spreadsheets. All discrepancies are retained in `archive_workbook_discrepancies.csv`.

Three workbook energy columns have no unambiguous HTML model description: GuanineA model 2 (46 records), GuanineB model 2 (40), and GuanineC's unnumbered column (23). These **{int(unknown.records.sum())}** records explain the remainder of the {workbook_summary['structure_model_records']:,} workbook total. GuanineC's unnumbered energies differ from its numbered model-1 energies; the unnumbered column is marked unassigned, rather than incorrectly mapped to model 1. These metadata do not add any extra files to the archive-based count.

The spreadsheets contain 250 repeated Filename labels and 25 Filename rows without numeric lattice energy. Eleven finite energy cells are zero and remain flagged, rather than interpreted as missing or successful calculations. Filename labels alone do not establish geometric identity, so no geometry count is inferred from their uniqueness.

## Figure and manuscript wording

Suggested wording: **“The CPOSS database provides {summary['coordinate_files']:,} structure files across {len(archives)} energy-model archives associated with {len(comparison)} CSP datasets. This count includes separate representations under different energy models and has not been deduplicated by crystal geometry.”**

Panel B ranks archive totals per documented CSP search; it includes all {len(comparison)} searches. Panel E uses the same archive totals and the source study Date field: {dated_files:,} structure files have a single study year and {undated_files:,} belong to the {len(datasets) - len(dated_ids)} searches with date ranges or pre-2010 dates. Release years and generation dates are not inferred. The existing molecular, contributor, method and literature analyses retain their prior scope.

## Audit files

- `reconciled_dataset_counts.csv`: one row per dataset, comparing all count scopes, with source URLs and revision.
- `structure_archive_counts.csv`: all 509 model archives, SHA-1, format inventory, RES count and workbook comparison.
- `dataset_archive_counts.csv`: complete archive counts aggregated over the 311 datasets.
- `structure_count_provenance.csv`: field-specific source, status, definition, date and revision.
- `structure_model_counts.csv`, `structure_count_reconciliation.csv`: original workbook-derived measurements and visualization comparison.
- `sources/structure_archive_counts.json`, `sources/workbook_summaries.json`: aggregate audit and original workbook headers/count diagnostics.

Run `reconcile_structure_counts.py`, then `count_structure_archives.py`, then `analyse.py --plot-only` to reproduce the audit and corrected figure. The original archives and workbooks are never modified.
"""
    (base / "structure_count_reconciliation.md").write_text(note)
    return summary, workbook_summary


if __name__ == "__main__":
    write_structure_reconciliation(Path(__file__).resolve().parent)
