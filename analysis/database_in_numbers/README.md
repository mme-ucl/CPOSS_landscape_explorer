# CPOSS: The database in numbers

Reproducible HTML metadata extraction, structure-array counting, paper metadata enrichment and a one-page A4 figure. Read `report.md` for the scientific definitions and coverage, and `caption.md` for the figure caption.

## Results

- `output/pdf/database_in_numbers.pdf`: vector PDF with embedded Helvetica.
- `figures/database_in_numbers.png`: the same A4 page at 300 dpi.
- `tables/datasets.csv`: one row per documented CSP search, including missing linked files.
- `tables/contributors.csv`, `dataset_contributors.csv`: scientists and explicit search credits.
- `tables/energy_models.csv`: complete reported descriptions, programs and normalised method categories.
- `tables/papers.csv`, `dataset_papers.csv`: deduplicated references, titles, years, authors and DOI/URL links; CSP and experimental contexts kept separate.
- `tables/provenance.csv`: field values, evidence, sources and reported/calculated/inferred/missing statuses.
- `tables/annual_counts.csv`, `cumulative_papers.csv`, `method_frequencies.csv`, `molecular_systems.csv`, `structure_count_ranking.csv`: complete plot data.
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
.venv/bin/python analyse.py --refresh

# Scientific-rule checks and output verification.
.venv/bin/python -m unittest -v test_analysis.py
.venv/bin/python verify_outputs.py
```

Run these commands from this directory. Full coordinate JSON files are cached at `/tmp/cposs-numbers-json-cache` by Git blob SHA, outside the deliverable. Supply `--cache PATH` to change the location. Archived lightweight summaries enable offline extraction without packaging the coordinates. To independently recalculate those summaries, move `sources/structure_summaries.json` aside and rerun online; every original is verified against the frozen Git revision. `--refresh` retrieves the latest inventory and keeps summaries only when the original Git blob SHA matches.

The extractor never edits the existing website, explorer catalogue or source database. Paper metadata caches are archived as retrieved. Field-specific source URLs and source spellings are retained so that inferences can be reviewed or replaced.
