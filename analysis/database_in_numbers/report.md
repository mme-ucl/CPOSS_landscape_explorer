# CPOSS metadata audit and analysis

Snapshot: `6a77cc47b35f268f81a1d433b62c3e0917e20ffd`. Accessed **2026-10-27**, Europe/London.
Source: [CPOSS database index](https://louiseprice.github.io/CPOSS_Database/index.html). All source HTML and the repository inventory are archived in `sources/`.

## Findings

- **310 documented CSP datasets** across **234 reachable molecule pages**.
- **517,594 archived structure files** across **508 energy-model ZIP archives**, covering all **310 datasets**. This supports the manuscript's statement of more than 500,000 stored structures when model-specific representations are counted separately. The median per dataset is **497**, the interquartile range is **112.5-1399.2**, and the range is **11-20408** files.
- The former **158,344** total counted only available Chemiscope visualization exports. The spreadsheets contain **401,290 Filename rows** and **547,014 numeric energy records**. These overlapping scopes are compared in [the structure-count reconciliation](structure_count_reconciliation.md); they must not be added together.
- **45 named scientists** across **285 datasets**; **25 datasets** say Unknown/Not sure rather than naming a scientist. The most frequently credited person is **Louise Price**, associated with **65 datasets**. Credits overlap and are not an assessment of research productivity.
- **232 documented molecular systems** have parseable formulas. Molar masses span **32.04-890.88 g/mol** and atom counts span **5-120**, on the written molecule/formula-unit basis.
- **75 unique linked CSP papers**, **577 unique linked references overall**, including experimental-context papers and research data records. **192 datasets** link at least one CSP paper after explicit publication cross-references are resolved.
- The largest annual count with an unambiguous study date is **27 datasets in 2018**. **236 datasets** have single years; **74** have ranges or pre-2010 dates, so this is incomplete chronology.

| Field | Available | Total datasets |
| --- | --- | --- |
| Documented CSP searches | 310 | 310 |
| Complete coordinate-archive structure counts | 310 | 310 |
| Linked JSON visualization counts | 310 | 310 |
| Complete workbook Filename/energy counts | 310 | 310 |
| Named scientist credits | 285 | 310 |
| Single study year | 236 | 310 |
| Molar mass and atom count from formula | 307 | 310 |
| Dataset release/deposition year | 0 | 310 |
| Original generated/optimised/retained counts as numeric HTML fields | 0 | 310 |

## Dataset scope and duplicate handling

The extractor follows same-database HTML links from the index and validates them against a complete GitHub repository tree. **243 of 245 HTML files** are reachable. A contributor-statistics placeholder and a misspelled duplicate molecule page are unlinked and excluded. The audit has **311 search occurrences**, keyed by the explicitly linked Chemiscope filename. A molecule page can describe several searches; an individual search can have several energy models. The current analysis uses exactly one record per JSON file in the pinned inventory. Three outdated page identifiers are reconciled using complete structure-filename coverage against the documented archives. The legacy MethylazetidineoneA search has no current JSON file and is explicitly excluded; `sources/current_inventory_scope.json` preserves the reconciliation and exclusion evidence.

**0 JSON files** exist in the repository but are not explicitly linked from reachable searches. These include full/filtered variants and unmatched files. They are inventoried in `unlinked_json_inventory.csv` and are not added to linked visualization exports or coordinate archives. The headline describes the public HTML-linked model archives, not every representation in the repository.

Every archived HTML file, downloaded JSON, original workbook and model ZIP was checked against its Git blob SHA at the frozen revision. Lightweight summaries retain the original file hashes, counts and diagnostic checks. The large source caches stay outside the deliverable. Rebuilding the figure offline uses delivered CSVs and summaries; independent source verification requires downloading the originals.

## What the structure count means

The figure uses **actual RES coordinate members in every documented energy-model ZIP**, excluding MacOS resource forks. Separate energy models are retained, while ancillary pDFT supplements are not added. All 508 archives were readable, checksum-verified and contained RES files; their Git hashes are distinct. No geometric deduplication across models or searches has been performed, so the total must not be described as unique predicted crystals. The HTML does not give original generation/optimization/retention counts; these remain missing.

**77 linked visualizations have exactly 1,000 entries**, while their full workbooks contain 318,650 Filename rows. Many visualizations therefore represent subsets; no universal export limit is assumed. The JSON measurements remain in the original `datasets.csv`, while `plot_datasets.csv` names both visualization and archive counts explicitly. JSON filename repeats remain flagged: 3aminobenzamideA.json (145 repeated labels), TetramethylpyrazineA.json (105 repeated labels).

All 310 current JSON records have verified visualization summaries. Outdated page identifiers are reconciled in `sources/current_inventory_scope.json`; source searches without a current JSON record are outside this analysis. Archive and workbook counts are tabulated separately in `archive_workbook_discrepancies.csv` and `structure_count_reconciliation.md`.

## Scientist names and molecular composition

Only explicit Scientist fields establish contributor relationships. Paper author lists are separate metadata and do not create dataset contributor credits. Slash, comma, `and` and parenthesis separators are parsed; parentheses are preserved as additional credits, without guessing supervisory roles. `L Price` is expanded to Louise Price and marked inferred. **Sally Price and Louise Price remain distinct**; see [UCL's staff listing](https://www.ucl.ac.uk/mathematical-physical-sciences/chemistry/people/emeritus-honorary-staff) for Sarah (Sally) L. Price. All source spellings remain in the tables.

Formula masses use RDKit's average atomic weights, not monoisotopic masses. The parser supports explicit integer group multipliers, component separators and charge symbols. Charges are ignored for molecular weight; all written components are included. Hydrate and salt/cocrystal masses use the complete **written formula unit**; for example a hemihydrate written as 2 acid molecules plus 1 water is not rescaled to a fractional water molecule. No unit-cell atom count is mistaken for a molecule's atom count. The analysis follows the reported formulas and does not independently validate chemical names, protonation or formula accuracy.

## Energy models and DFT

There are **508 energy-model records** and **31 supplementary pDFT links**. Programs, potential descriptions, intramolecular descriptions, basis sets and explicitly named dispersion corrections are retained in `energy_models.csv`. Raw descriptions remain authoritative; text-based normalisations are marked inferred. PBE0 and PBE1PBE are grouped as a single conventional electronic-method category; no missing method is filled from an unrelated search.

| Kind | Category | Datasets |
| --- | --- | --- |
| Potential family | FIT | 280 |
| Potential family | Williams | 35 |
| Potential family | Day / Rice | 22 |
| Potential family | Non-empirical / SAPT | 4 |
| Potential family | Custom Delaware | 1 |
| Electronic method | MP2 | 175 |
| Electronic method | PBE0 / PBE1PBE | 109 |
| Electronic method | HF / SCF | 41 |
| Electronic method | M06-2X | 12 |
| Electronic method | DFTB3-D3 | 11 |
| Electronic method | B3LYP | 10 |
| Electronic method | B3PW91 | 3 |
| Electronic method | CCSD | 2 |
| Electronic method | PBE | 2 |

These counts use each dataset at most once per category and may sum above 310. MP2, HF and hybrid functional labels commonly describe molecular charge densities, multipoles or intramolecular energies. They are **not evidence that the whole crystal landscape was computed with periodic DFT**. The 31 pDFT supplement links provide no functional/basis description in their HTML rows; those details remain missing. The linked ZIP archives and Word descriptions were not mined for additional methodology.

## Dates and the linked literature

Dataset deposition/release years are not reported. Annual counts use the **source study Date field**, with no substitution of page update year or publication year. Single years and month-year dates are accepted. Ranges such as 2005-2008, abbreviated 2005-7, and pre-2010 are excluded instead of assigned arbitrary years. These exclusions leave **488,411 archived structure files** in annual bins and **29,183 files** without a single year. All 310 archive counts are complete for the current JSON-record inventory.

| Linked CSP papers per dataset | Datasets |
| --- | --- |
| 0 | 118 |
| 1 | 187 |
| 2 | 5 |

Paper identities use case-normalised DOI, otherwise canonical URL. Explicit `See Study_ID` publication pointers are followed **only within their molecule page** when the target is unambiguous; **15 dataset-paper associations** are marked inferred. Figures count the papers associated with CSP Publication fields, not every experimental crystal determination cited on a molecule page. The CSVs retain both CSP and experimental-context associations and per-dataset counts for each scope. A zero linked-paper count means no qualifying linked paper was found, not proof that no paper exists. Plain notes such as Masters thesis, In preparation and No publication planned remain in `publication_raw`.

Crossref supplies titles, authors, reference types and its preferred published year for DOI records. DataCite identifies three eCrystals dataset records, which are not counted as papers. Three truncated Wiley DOI hyperlinks are reconstructed from their complete visible citation strings, marked inferred and validated through Crossref. One CSP reference is identified as a paper from its explicit Trans. ACA citation; its linked proceedings PDF returned HTTP 404, so its title remains missing. **1 reference title** is unavailable. Online/print years are recorded separately where supplied; the cumulative curve counts each CSP paper once, by the recorded publication year, and does not measure when it was added to CPOSS.

## Validation and deliverables

No conflicting contributor/date/formula values were found across merged dataset mappings (**0 conflicts**). All available linked JSON structure-target property lengths match their arrays; the delivered verification report separately checks these lengths, accounting totals, annual aggregation, DOI deduplication, PDF geometry and embedded fonts. The source-link audit lists **5 missing internal link targets** across HTML, archives and images; these were checked against the repository inventory; all documented energy-model archives were also downloaded and checked separately, while images and ancillary ZIPs were not all fetched. External paper landing pages were not all fetched; metadata-service retrieval and its exceptions are recorded in `sources/doi_metadata.json`.

The figure shows molecular size in panel A and scientist credits in panel D. The scientist panel shows the 20 most frequently credited scientists, including Sally Price; the full source tables and headline count retain all 45 scientists. Potential-family bars, paper-per-dataset bars, panel subtitles and the footer are omitted from the figure; their data, provenance and counting rules remain in these tables and the caption. The cumulative dataset curve includes only the 236 searches with a single study year.

The page is exactly A4 portrait, with compact vertical and horizontal gutters, unchanged plot heights, aligned plot baselines, a 14 pt title and 9 pt panel headings. The truncated Plasma palette provides a spectral colourbar-style progression: logarithmic count colours in B-D, a common year ramp in E-F, and fixed single/multicomponent colours in A. All text resolves to Helvetica, with regular/bold faces extracted from the system Helvetica collection for embedding; no proprietary font file is redistributed. The vector PDF and 300 dpi PNG share the same layout. `caption.md` provides the standalone caption. `tables/` holds complete results and source-specific provenance; `sources/` holds archived HTML/metadata. `manifest.json` records revision, date, count rules, font checks and package versions.
