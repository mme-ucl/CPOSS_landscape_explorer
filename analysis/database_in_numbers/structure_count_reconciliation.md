# Reconciliation of the CPOSS structure count

**The full documented energy-model archives contain 517,594 RES structure files.** This supports the manuscript's statement that the collection contains more than 500,000 stored structures, provided structures represented under separate energy models are counted separately. It does not establish more than 500,000 geometrically unique crystals.

The earlier **158,344** total measured only the linked Chemiscope visualization exports. Presenting it as the size of the complete downloadable collection was too narrow. The corrected figure uses coordinate-archive counts throughout its headline, dataset ranking and annual structure series.

| Measurement | Total | Meaning |
| --- | ---: | --- |
| Linked visualization entries | 158,344 | 310 available JSON exports; 0 missing |
| Workbook Filename rows | 401,290 | Complete per-search tables, all 310 datasets |
| Workbook rows with at least one numeric model energy | 401,265 | Rows with some recorded lattice-energy result |
| Numeric structure-energy records | 547,014 | Sum of finite numeric lattice-energy cells across 511 energy columns |
| **Archived coordinate files (figure count)** | **517,594** | **All 508 explicitly documented energy-model ZIPs, all 310 datasets** |

These measurements overlap and must not be added together. The energy-record count is not an alternative number of unique geometries.

## How the archive count was verified

The audit follows each of the 508 explicitly documented energy-model ZIP links in `energy_models.csv`, using the frozen repository revision `6a77cc47b35f268f81a1d433b62c3e0917e20ffd` (accessed 2026-10-27). Every archive was downloaded and its Git blob SHA-1 checked against the repository tree. All 508 were readable and contained RES files; no model archive was missing. All 508 archive hashes are distinct.

Only actual `.res` members are counted. Directory entries, `__MACOSX` resource forks and AppleDouble `._` files are excluded. There are no repeated coordinate-member names within an archive and no CIF/PDB/XYZ alternatives in these 508 archives. Ancillary periodic-DFT supplements and unrelated repository ZIPs are outside this count, avoiding an additional sum of overlapping representations. The reproducible counter reports format inventories and missing/error statuses rather than assuming zero on failure.

This is a count of stored coordinate files across model-specific archives. It retains experimental reference structures and possible repeated geometries across models or searches. Coordinate parsing and crystallographic/geometric deduplication have not been performed. The number of candidates originally generated, rejected or optimized before deposition remains unknown.

## Why the visualization count is smaller

**77 linked JSON exports contain exactly 1,000 entries.** Their associated complete workbooks contain 319,970 Filename rows, compared with 77,000 visualization entries. This demonstrates that many visualizations represent subsets; it does not establish a universal export limit. The 0 missing JSON links still have intact model archives, contributing **0** coordinate files. Visualization rows also generally combine multiple energy columns for the same filename, whereas the downloadable models contain separate coordinate representations.

| Dataset | Visualization entries | Workbook rows | Numeric energy records | Archived RES files |
| --- | ---: | ---: | ---: | ---: |
| AspirinA | 14 | 20 | 14 | 21 |
| BTXXXIIA | 1,000 | 15,042 | 25,011 | 18,805 |
| TrinitrobenzeneA | 1,036 | 1,036 | 1,827 | 1,827 |
| UreaA | 850 | 850 | 1,643 | 1,643 |

For UreaA, the two model archives contain 850 and 793 structures, giving 1,643 stored model-specific files; its visualization has 850 entries. For BTXXXIIA, the archives contain 8,829 and 9,976 RES files, giving 18,805, compared with a 1,000-entry visualization.

## Why the workbook and archive totals also differ

**453 of 508 model archives** have exactly the same coordinate-file count as their corresponding numeric workbook energy column. The remaining **55** disagree. Numbered energy columns that match documented HTML models contain **546,905** numeric records, **29,311** more than the archives. The dominant shortfalls are XXVIIA model 1 (1,000 RES files versus 15,803 energy records), BTXXVIA model 1 (7,726 versus 16,225), and BTXXXIIA model 1 (8,829 versus 15,042). Other archives contain extra structures relative to their energy columns. Experimental references and records without numeric energy cells are possible explanations, but the individual identities and causes of these differences were not established.

The workbook and archive versions or retained subsets are therefore not uniformly aligned. The count in the figure is based on the coordinate files actually present, rather than filling these differences from the spreadsheets. All discrepancies are retained in `archive_workbook_discrepancies.csv`.

Three workbook energy columns have no unambiguous HTML model description: GuanineA model 2 (46 records), GuanineB model 2 (40), and GuanineC's unnumbered column (23). These **109** records explain the remainder of the 547,014 workbook total. GuanineC's unnumbered energies differ from its numbered model-1 energies; the unnumbered column is marked unassigned, rather than incorrectly mapped to model 1. These metadata do not add any extra files to the archive-based count.

The spreadsheets contain 250 repeated Filename labels and 25 Filename rows without numeric lattice energy. Eleven finite energy cells are zero and remain flagged, rather than interpreted as missing or successful calculations. Filename labels alone do not establish geometric identity, so no geometry count is inferred from their uniqueness.

## Figure and manuscript wording

Suggested wording: **“The CPOSS database provides 517,594 structure files across 508 energy-model archives associated with 310 CSP datasets. This count includes separate representations under different energy models and has not been deduplicated by crystal geometry.”**

Panel B ranks archive totals per documented CSP search; it includes all 310 searches. Panel E uses the same archive totals and the source study Date field: 488,411 structure files have a single study year and 29,183 belong to the 74 searches with date ranges or pre-2010 dates. Release years and generation dates are not inferred. The existing molecular, contributor, method and literature analyses retain their prior scope.

## Audit files

- `reconciled_dataset_counts.csv`: one row per dataset, comparing all count scopes, with source URLs and revision.
- `structure_archive_counts.csv`: all 508 model archives, SHA-1, format inventory, RES count and workbook comparison.
- `dataset_archive_counts.csv`: complete archive counts aggregated over the 310 datasets.
- `structure_count_provenance.csv`: field-specific source, status, definition, date and revision.
- `structure_model_counts.csv`, `structure_count_reconciliation.csv`: original workbook-derived measurements and visualization comparison.
- `sources/structure_archive_counts.json`, `sources/workbook_summaries.json`: aggregate audit and original workbook headers/count diagnostics.

Run `reconcile_structure_counts.py`, then `count_structure_archives.py`, then `analyse.py --plot-only` to reproduce the audit and corrected figure. The original archives and workbooks are never modified.
