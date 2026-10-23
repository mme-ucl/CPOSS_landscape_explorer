# CPOSS metadata audit and analysis

Snapshot: `d65c1732ab6db46b8af34e0646a760c56a8d559c`. Accessed **2026-10-23**, Europe/London.
Source: [CPOSS database index](https://louiseprice.github.io/CPOSS_Database/index.html). All source HTML and the repository inventory are archived in `sources/`.

## Findings

- **311 documented CSP datasets** across **235 reachable molecule pages**.
- **155,824 stored structure entries** in **307 linked Chemiscope files**. The median is **438**, the interquartile range is **109.5-1000**, and the range is **11-2105** entries per file.
- **45 named scientists** across **286 datasets**; **25 datasets** say Unknown/Not sure rather than naming a scientist. The most frequently credited person is **Louise Price**, associated with **65 datasets**. Credits overlap and are not an assessment of research productivity.
- **235 documented molecular systems** have parseable formulas. Molar masses span **32.04-2911.56 g/mol** and atom counts span **5-218**, on the written molecule/formula-unit basis.
- **75 unique linked CSP papers**, **577 unique linked references overall**, including experimental-context papers and research data records. **192 datasets** link at least one CSP paper after explicit publication cross-references are resolved.
- The largest annual count with an unambiguous study date is **27 datasets in 2018**. **236 datasets** have single years; **75** have ranges or pre-2010 dates, so this is incomplete chronology.

| Field | Available | Total datasets |
| --- | --- | --- |
| Documented CSP searches | 311 | 311 |
| Linked JSON structure counts | 307 | 311 |
| Named scientist credits | 286 | 311 |
| Single study year | 236 | 311 |
| Molar mass and atom count from formula | 311 | 311 |
| Dataset release/deposition year | 0 | 311 |
| Original generated/optimised/retained counts as numeric HTML fields | 0 | 311 |

## Dataset scope and duplicate handling

The extractor follows same-database HTML links from the index and validates them against a complete GitHub repository tree. **243 of 245 HTML files** are reachable. A contributor-statistics placeholder and a misspelled duplicate molecule page are unlinked and excluded. The audit has **311 search occurrences**, keyed by the explicitly linked Chemiscope filename. A molecule page can describe several searches; an individual search can have several energy models. The analysis includes searches with broken JSON links rather than silently dropping them from the dataset denominator.

**8 JSON files** exist in the repository but are not explicitly linked from reachable searches. These include full/filtered variants and unmatched files. They are inventoried in `unlinked_json_inventory.csv` and excluded from the headline and structure counts. Consequently, these numbers describe the public HTML-linked collection, not every file in the repository. Existing explorer catalogue files were not changed.

Every archived HTML file and downloaded JSON was checked against its Git blob SHA at the frozen revision. The lightweight JSON summaries retain the verified original file hashes, array counts, property lengths and duplicate-filename checks; the 1+ GB coordinate cache stays outside the deliverable. Rebuilding the figure and extraction offline uses those archived summaries; verifying them from scratch requires downloading the original JSON again.

## What the structure count means

The HTML does not contain numeric totals for all originally generated, optimised or retained candidates. Counts in this report are **calculated from the length of each linked JSON `structures` array**. They describe the distributed visualisation data, including entries associated with experimental references. Original search sizes remain missing, never zero.

**76 files have exactly 1,000 entries**. This concentration is consistent with a display/export limit, but no uniform limit is assumed. The five unlinked `_full` variants are not added to their linked counterparts. Two linked files repeat filename labels: TetramethylpyrazineA.json (105 repeated labels), 3aminobenzamideA.json (145 repeated labels). Labels alone are insufficient to prove identical geometries, so repeated rows are flagged and retained. Cross-dataset structure matching has not been performed; totals must not be called unique predicted crystals.

Four linked JSON files are absent at the revision: **4C2NBAMHA, FluorouracilA, MethylazetidineoneA, PhloroglucinolDihydrateA**. Their structure counts are missing. `structure_file_audit.csv` records the exact broken links and verified array/property-length checks. No fuzzy filename correction was applied.

## Scientist names and molecular composition

Only explicit Scientist fields establish contributor relationships. Paper author lists are separate metadata and do not create dataset contributor credits. Slash, comma, `and` and parenthesis separators are parsed; parentheses are preserved as additional credits, without guessing supervisory roles. `L Price` is expanded to Louise Price and marked inferred. **Sally Price and Louise Price remain distinct**; see [UCL's staff listing](https://www.ucl.ac.uk/mathematical-physical-sciences/chemistry/people/emeritus-honorary-staff) for Sarah (Sally) L. Price. All source spellings remain in the tables.

Formula masses use RDKit's average atomic weights, not monoisotopic masses. The parser supports explicit integer group multipliers, component separators and charge symbols. Charges are ignored for molecular weight; all written components are included. Hydrate and salt/cocrystal masses use the complete **written formula unit**; for example a hemihydrate written as 2 acid molecules plus 1 water is not rescaled to a fractional water molecule. No unit-cell atom count is mistaken for a molecule's atom count. The analysis follows the reported formulas and does not independently validate chemical names, protonation or formula accuracy.

## Energy models and DFT

There are **509 energy-model records** and **31 supplementary pDFT links**. Programs, potential descriptions, intramolecular descriptions, basis sets and explicitly named dispersion corrections are retained in `energy_models.csv`. Raw descriptions remain authoritative; text-based normalisations are marked inferred. PBE0 and PBE1PBE are grouped as a single conventional electronic-method category; no missing method is filled from an unrelated search.

| Kind | Category | Datasets |
| --- | --- | --- |
| Potential family | FIT | 281 |
| Potential family | Williams | 35 |
| Potential family | Day / Rice | 22 |
| Potential family | Non-empirical / SAPT | 4 |
| Potential family | Custom Delaware | 1 |
| Electronic method | MP2 | 176 |
| Electronic method | PBE0 / PBE1PBE | 109 |
| Electronic method | HF / SCF | 41 |
| Electronic method | M06-2X | 12 |
| Electronic method | DFTB3-D3 | 11 |
| Electronic method | B3LYP | 10 |
| Electronic method | B3PW91 | 3 |
| Electronic method | CCSD | 2 |
| Electronic method | PBE | 2 |

These counts use each dataset at most once per category and may sum above 311. MP2, HF and hybrid functional labels commonly describe molecular charge densities, multipoles or intramolecular energies. They are **not evidence that the whole crystal landscape was computed with periodic DFT**. The 31 pDFT supplement links provide no functional/basis description in their HTML rows; those details remain missing. The linked ZIP archives and Word descriptions were not mined for additional methodology.

## Dates and the linked literature

Dataset deposition/release years are not reported. Annual counts therefore use the **source study Date field**, with no substitution of page update year or publication year. Single years and month-year dates are accepted. Ranges such as 2005-2008, abbreviated 2005-7, and pre-2010 are excluded instead of assigned arbitrary years. These exclusions leave **133,481 entries** in annual bins and **22,343 entries** without a single year. Known study years with broken JSON links contribute a landscape but no fabricated structure count.

| Linked CSP papers per dataset | Datasets |
| --- | --- |
| 0 | 119 |
| 1 | 187 |
| 2 | 5 |

Paper identities use case-normalised DOI, otherwise canonical URL. Explicit `See Study_ID` publication pointers are followed **only within their molecule page** when the target is unambiguous; **15 dataset-paper associations** are marked inferred. Figures count the papers associated with CSP Publication fields, not every experimental crystal determination cited on a molecule page. The CSVs retain both CSP and experimental-context associations and per-dataset counts for each scope. A zero linked-paper count means no qualifying linked paper was found, not proof that no paper exists. Plain notes such as Masters thesis, In preparation and No publication planned remain in `publication_raw`.

Crossref supplies titles, authors, reference types and its preferred published year for DOI records. DataCite identifies three eCrystals dataset records, which are not counted as papers. Three truncated Wiley DOI hyperlinks are reconstructed from their complete visible citation strings, marked inferred and validated through Crossref. One CSP reference is identified as a paper from its explicit Trans. ACA citation; its linked proceedings PDF returned HTTP 404, so its title remains missing. **1 reference title** is unavailable. Online/print years are recorded separately where supplied; the cumulative curve counts each CSP paper once, by the recorded publication year, and does not measure when it was added to CPOSS.

## Validation and deliverables

No conflicting contributor/date/formula values were found across merged dataset mappings (**0 conflicts**). All available linked JSON structure-target property lengths match their arrays; the delivered verification report separately checks these lengths, accounting totals, annual aggregation, DOI deduplication, PDF geometry and embedded fonts. The source-link audit lists **5 missing internal link targets** across HTML, archives and images; these were checked against the repository inventory, not by fetching every ZIP or image. External paper landing pages were not all fetched; metadata-service retrieval and its exceptions are recorded in `sources/doi_metadata.json`.

The page is exactly A4 portrait. All text resolves to Helvetica, with regular/bold faces extracted from the system Helvetica collection for embedding; no proprietary font file is redistributed. The vector PDF and 300 dpi PNG have the same layout. `caption.md` provides the standalone figure caption. `tables/` holds complete results, `sources/` holds archived HTML/metadata, and `manifest.json` records scope, revision, date, fonts and package versions.
