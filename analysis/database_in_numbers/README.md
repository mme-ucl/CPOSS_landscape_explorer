# CPOSS: The database in numbers

Reproducible HTML metadata extraction, complete coordinate-archive counting, paper metadata enrichment and a compact journal-style one-page A4 figure. The corrected headline is **519,167 RES structure files across 509 energy-model archives and 311 datasets**. Separate energy-model representations are retained; geometric uniqueness has not been established. Read `structure_count_reconciliation.md` for the full explanation, `report.md` for metadata coverage and `caption.md` for the figure caption.

## Results

- `output/pdf/database_in_numbers.pdf`: vector PDF with embedded Helvetica.
- `figures/database_in_numbers.png`: the same A4 page at 300 dpi.
- `output/pdf/database_in_numbers_3x2.pdf` and `figures/database_in_numbers_3x2.png`: wider paper figure with A-C above D-F. The approved panel C shows reported CSP software from the matched curation-workbook records. Panels A, B and D-F come from the current portrait PDF, including its latest formula checks (233 plotted systems). Panel sizes, fonts and proportions are retained, with translation only. Rebuild using `python make_wide_figure.py` after the portrait PDF and `workbook_crosscheck/plot_panel_c.py`; `verification_3x2.json` records both source PDFs, software data, provenance, panel placements and output checks.
- `caption_3x2.tex`: comprehensive LaTeX caption and `fig:database_in_numbers` label for the wider figure. Input this fragment inside the manuscript's figure environment after the image. The existing `caption.md` describes the portrait reference figure.
- `workbook_crosscheck/report.md`: the worksheet reconciliation and remaining formula, credit and date differences. The wider figure adopts the approved software panel; the other spreadsheet conflicts remain recorded for review.
- `tables/datasets.csv`: one row per documented CSP search, including missing linked files.
- `tables/plot_datasets.csv`: figure view with archive structure counts and the original visualization counts in separate columns. The `structure_count` column in the original `datasets.csv` retains its original JSON-array definition.
- `tables/structure_archive_counts.csv`, `dataset_archive_counts.csv`: all 509 checksum-verified model archives and their per-dataset coordinate-file totals.
- `tables/reconciled_dataset_counts.csv`, `structure_model_counts.csv`, `archive_workbook_discrepancies.csv`: comparisons between visualization entries, workbook records and actual coordinate files.
- `tables/structure_count_provenance.csv`: field-specific count definitions, statuses, source URLs, date and revision; complements the original metadata provenance.
- `tables/contributors.csv`, `dataset_contributors.csv`: scientists and explicit search credits.
- `tables/energy_models.csv`: complete reported descriptions, programs and normalised method categories.
- `tables/papers.csv`, `dataset_papers.csv`: deduplicated references, titles, years, authors and DOI/URL links; CSP and experimental contexts kept separate.
- `tables/provenance.csv`: field values, evidence, sources and reported/calculated/inferred/missing statuses.
- `tables/annual_counts.csv`, `cumulative_papers.csv`, `method_frequencies.csv`, `molecular_systems.csv`, `structure_count_ranking.csv`: complete plot data.
- `tables/annual_counts.csv` also includes cumulative datasets, counting only searches with a single study year. `scientist_plot_data.csv` records the top 20 displayed scientists, including Sally Price; full scientist metadata remain in the original contributor tables.
- `tables/*audit.csv`, `broken_source_links.csv`, `unlinked_json_inventory.csv`, `metadata_conflicts.csv`: source coverage and exceptions.
- `sources/`: Git tree, verified HTML, JSON structure summaries, Crossref/DataCite metadata and external-reference exceptions.
- `manifest.json`, `verification.json`: revision, access date, font checks, versions and accounting/format verification.

## Run

Python 3.12+ and a licensed local copy of **Helvetica** are required. Font files are not distributed. On macOS the script uses `/System/Library/Fonts/Helvetica.ttc`. Elsewhere, pass `--font /path/to/Helvetica.ttf` (regular/bold font files should share that directory). The script fails if Helvetica cannot be used.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt

# Recreate the figure and report from delivered CSVs; no network required.
.venv/bin/python analyse.py --plot-only

# Re-extract metadata from the archived HTML and JSON summaries, then plot.
# This preserves the archived access date rather than claiming a fresh retrieval.
.venv/bin/python analyse.py --offline

# Recheck the frozen revision against downloaded originals, if caches are absent.
.venv/bin/python analyse.py

# New live repository snapshot; downloads may exceed 1 GB.
.venv/bin/python analyse.py --refresh --extract-only
.venv/bin/python reconcile_structure_counts.py
.venv/bin/python count_structure_archives.py
.venv/bin/python analyse.py --plot-only

# Independently recheck the delivered frozen-revision workbook/archive counts.
# Downloaded originals are checked against repository Git blob hashes.
.venv/bin/python reconcile_structure_counts.py
.venv/bin/python count_structure_archives.py
.venv/bin/python analyse.py --plot-only

# Scientific-rule checks and output verification.
.venv/bin/python -m unittest -v test_analysis.py
.venv/bin/python verify_outputs.py
```

Run these commands from this directory. Full coordinate JSON files are cached at `/tmp/cposs-numbers-json-cache` by Git blob SHA, outside the deliverable. Supply `--cache PATH` to change the location. Archived lightweight summaries enable offline extraction without packaging the coordinates. To independently recalculate those summaries, move `sources/structure_summaries.json` aside and rerun online; every original is verified against the frozen Git revision. `--refresh` retrieves the latest inventory and keeps summaries only when the original Git blob SHA matches.

Workbook originals are cached in `/tmp/cposs-workbook-cache` (about 26 MB) and model ZIPs in `/tmp/cposs-model-archive-cache` (about 746 MB), keyed by verified Git blob SHA. They are never modified or redistributed in the analysis bundle. `reconcile_structure_counts.py` reads actual worksheet records and numeric energy cells; `count_structure_archives.py` counts actual coordinate members and excludes MacOS resource forks. `structure_count_report.py` writes the comparison report and provenance when the figure is rebuilt. The figure refuses to combine audits from different revisions or publish partial archive totals. `verify_structure_archives.py` retains the earlier small-sample check; the complete archive audit supersedes it.

The extractor never edits the existing website, explorer catalogue or source database. Paper metadata caches are archived as retrieved. Field-specific source URLs and source spellings are retained so that inferences can be reviewed or replaced.
