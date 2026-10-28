# Spreadsheet crosscheck and proposed panel C

The workbook matches all **234 molecular systems, 310 current JSON records and 508 documented energy-model archives** when records are joined at the correct level. It also exposes unresolved differences in chemical formulas, structure counts, search credits and dates. The paper figure is regenerated from the current frozen tables after this audit.

Source: `/Users/matteo/Downloads/Database 2023 checkup.xlsx`. The workbook metadata records modification on `2026-10-23 10:37:35`; it contains updates through 2026 despite its filename. The source workbook and the existing figures have not been edited by this audit. Source SHA-256: `e8a410fa55c3e5cab90d4352a985f694e7f1d5e4b4085f1331edf68602eed2dc`.

## Scope and matching

The `Database` worksheet mixes model records (Study_ID in C), molecule summaries (AC:AN), and administrative notes. Molecule summaries in AC:AN are not additional models. Formulae are read from B; the repeated `Formula` heading in AJ must not overwrite B. Free-text notes with no Study_ID are not converted into data records. `Sheet1` and `Progress` are auxiliary lists/tracking sheets and do not describe the complete scientific population.

All 508 public model archives were matched once, primarily by molecule page and Study_ID. Explicit Github identifiers resolve a Study_ID discrepancy for QuinoliniumFumarate (row 327: workbook 0, website 20). This also handles the shared IYUPEX refcode for pyridineisophthalicacid and pyridiniumisophthalate without merging their distinct pages. The methyl-p-hydroxybenzoate typo in row 72 is resolved by its molecule/Study_ID, not by an unreviewed fuzzy name match. Full joins and evidence are in `model_count_comparison.csv`.

The in-scope workbook `Searches` summary sums to **309**, while the current JSON inventory has **310** records. The difference is BTXII (row 18): the workbook groups Study_IDs 0 and 1 as A1/A2 within one search, whereas the website exposes A and B separately. Both model records are present. This is a grouping difference, not a missing molecule or archive. The `Studies` summary sums to **502**, so it should not be substituted for the 508 counted public model archives. Five additional rows marked uploaded have no corresponding documented model archive in the figure's scope; see `workbook_rows_outside_figure_scope.csv` and `molecule_scope_comparison.csv`.

## Panel A: molecular size

Canonical elemental compositions agree for **224 of 234 systems**. The workbook supplies valid oxygen symbols for **Piracetam and Isobarbituric acid**, which are unparseable in the current website metadata. There are **eight further composition conflicts**. These conflicts require a source choice or chemical verification; the workbook has not automatically been treated as correct wherever the two sources disagree.

| Workbook cell | System | Spreadsheet formula | Website formula | Finding |
| --- | --- | --- | --- | --- |
| Database!B6 | DipicolinicAcid | C7 H5 N1 O4 | C8 H5 N1 O4 | different composition |
| Database!B43 | Piracetam | C6 H10 N2 O2 | C6 H10 N2 02 | workbook resolves invalid website formula |
| Database!B99 | Bipy-2Aminobenzoic | C10 H8 N2 . C7 H7 N1 O2 . C7 H7 N1 O2 | (C7 H7 N1 O2)2 - C8 H7 N1 O4 | different composition |
| Database!B237 | Naphthalene | C10 H8 | C8 H10 | different composition |
| Database!B313 | IsobarbituricAcid | C4 H4 N2 O3 | C4 H4 N2 03 | workbook resolves invalid website formula |
| Database!B321 | FenamicAcid | C13 H11 N1 O2 | C13 H12 N1 O2 | different composition |
| Database!B327 | QuinoliniumFumarate | C9 H8 N1 + . C4 H4 O3 - | C9 H8 N1 - C4 H4 O4 | different composition |
| Database!B418 | Dicyanobenzene-Succinic | C8 H4 N2 . C4 H6 O4 | C6 N2 H4 - C4 O4 H6 | different composition |
| Database!B420 | Bipy-Aminobenzoic | C10 H8 N2 . C7 H7 N1 O2 | C7 H7 N1 O2 - C8 H7 N1 O4 | different composition |
| Database!B448 | BTXV | C8 H4 O2 . C5 H7 N3 | C13 H15 N3 O2 | different composition |

For the two recoverable website typos, the workbook gives Piracetam `C6 H10 N2 O2` (20 atoms, 142.158 g mol⁻¹) and Isobarbituric acid `C4 H4 N2 O3` (13 atoms, 128.087 g mol⁻¹). This restores two molecular-system points, corresponding to three searches because Isobarbituric acid has A and B searches. The earlier caption's maximum of 218 atoms / 2911.56 g mol⁻¹ is not supported by the corrected parsing: these were inflated by joining ambiguous numeric tokens in erroneous formula strings.

The overview figure uses the current website-formula subset; the chemical comparison additionally reconciles workbook formulas with coordinate evidence. The current legend strings are recorded in `audit_summary.json`. All 234 in-scope workbook formulas are parseable after normalizing ionic charge signs and comma-separated formatting.

The formula-based colour classification also differs for three systems:

| Workbook cell | System | Workbook component notation | Website component notation |
| --- | --- | --- | --- |
| Database!B159 | LY2806920HCl | C16 H22 N3 O3 + . Cl - | (C16 H22 N3 O3)+ Cl- |
| Database!B426 | MemantineHydrochloride | C12 H22 N1 + . Cl1 - | C12 H22 N1 Cl1 |
| Database!B448 | BTXV | C8 H4 O2 . C5 H7 N3 | C13 H15 N3 O2 |

The spreadsheet's explicit component notation yields **190 single-component and 44 multicomponent formula units**. Two of these component-encoding differences have the same elemental composition; BTXV additionally has a stoichiometric conflict. Salt/component classification should therefore be reconciled along with the coordinates. Full per-system formulas, atom counts, masses, cell references and source URLs are in `molecular_formula_comparison.csv`. Molar masses use the same RDKit average atomic weights and complete written formula-unit basis as the existing analysis.

## Panel B and the structure headline

The actual archived-file total remains **519,167** under the existing coordinate-file definition. Crosschecking the matched 509 model records against Database!AA gives:

| Matched-model comparison | Models |
| --- | ---: |
| Workbook count equals archive coordinate-file count | 383 |
| Numeric workbook count differs | 122 |
| Workbook count is missing | 4 |
| Total | 509 |

Of the 122 numeric differences, **75 are only one or two files**. Their causes have not been assigned without examining the individual records. The four missing counts are Galunisertib models 1, 3 and 4 (rows 118, 119 and 117) and Iminodibenzyl model 2 (row 157).

On the **same 505 models with workbook counts**, the workbook totals **563,297**, while their archives contain **513,403** files: a difference of **49,894**. The other four archives contribute 5,764 files, bringing the complete archive total to 519,167. Comparing the partial 563,297 spreadsheet sum directly with the full 519,167 archive total would mix coverage.

Largest discrepancies:

| Workbook cell | Dataset | Model | Spreadsheet count | Archive files |
| --- | --- | --- | --- | --- |
| Database!AA467 | BXXIIIA | 1 | 28,189 | 2,664 |
| Database!AA492 | XXVIIA | 1 | 15,803 | 1,000 |
| Database!AA212 | GallicAcidMHA | 1 | 1,995 | 10,724 |
| Database!AA476 | BTXXVIA | 1 | 16,225 | 7,726 |
| Database!AA187 | BTXXXIIA | 1 | 15,042 | 8,829 |
| Database!AA31 | GSK269984BA | 1 | 5,662 | 1,000 |
| Database!AA543 | 25-dichloronitrobenzeneB | 1 | 3,569 | 1,784 |
| Database!AA480 | BTXXIVA | 1 | 2,607 | 3,925 |

Row 467 explicitly says that only a 20 kJ/mol subset went to Github; its workbook energy range is 40 kJ/mol. Thus at least one large discrepancy has an explicit scope difference. The metadata counts should not replace direct file counts or be added to them. The plotted range of 11--20,408 files per search and median 498 remain archive-based values; this spreadsheet does not independently reproduce that distribution.

The three formulas in the structure-count column (AA467, AA476 and AA528) are simple arithmetic sums. Their cached values were independently checked against their formula operands and agree. No workbook recalculation, refresh or edits were performed.

## Panel C: replace electronic levels with reported software

The workbook has a `Programs` column L and informal `DFT-D calculations` notes in S. It does not provide a consistently populated quantum-chemistry method/basis description from which the existing MP2/PBE0/HF bars can be reconstructed. Those bars therefore cannot be independently verified using this file alone.

**Recommended replacement: Reported CSP software**, with the subtitle **Search and refinement programs**. The following frequencies use only the 509 matched public model records. Each search contributes at most once to each program family, irrespective of model count, version or repeated mentions.

| Program family | Searches with an explicit mention | Denominator |
| --- | --- | --- |
| DMACRYS | 189 | 310 |
| MOLPAK | 155 | 310 |
| CrystalPredictor | 148 | 310 |
| DMAREL | 125 | 310 |
| CrystalOptimizer | 110 | 310 |
| DMAflex | 28 | 310 |

Categories overlap: this is a software-coverage plot, not a partition or a count of software executions. Version suffixes are pooled. `CrystOpt` is grouped with CrystalOptimizer; `CrystalPrecictor` is treated as an explicit spelling variant of CrystalPredictor; DMAflex-Q and numbered DMAflex variants are grouped with DMAflex. Bare Study_ID references are not recursively expanded, so these are direct recorded mentions. DFTB3-D3 appears explicitly in Programs for eight searches but is omitted from this software-only panel because the label specifies a calculation method rather than an identifiable software package.

The proposed PDF retains the original C panel's physical dimensions, Helvetica fonts and Plasma count-colour convention. The graph and its row-level evidence are in `proposed_panel_c_counts.csv` and `proposed_panel_c_evidence.csv`.

Suggested replacement caption text:

```latex
\textbf{(C)} Reported CSP software. Numbers of the 311 documented
searches with explicit mentions of each search or refinement program
in the matched energy-model records. Each search is counted once per
program family, pooling program versions. Categories overlap; bare
Study\_ID cross-references are not expanded.
```

## Panel D and named-scientist headline

The workbook confirms **286 searches with named primary-model credits**. Comparing these primary-model credits with website search-level credits gives **292 matching and 19 differing searches**. The primary-model convention is model 1 where archived, otherwise the first matched workbook model (MefenamicAcidA has no archived model 1). This is a comparison convention, not evidence that every additional website credit is incorrect.

The primary-model Scientist cells contain **44 distinct names**, whereas the website search-level table has 45. In particular the workbook says **Erin Stevenson** where the website says **Eric Stevenson**, and Weijia Zhu is included among website search-level credits but not the workbook's primary-model Scientist cells. Additional model/DFT contributions and naming differences need reconciliation before changing the 45-person headline or individual bars. Publication authors are not used to infer credits.

| Workbook cell | Dataset | Spreadsheet primary-model credit | Website search credit |
| --- | --- | --- | --- |
| Database!K20 | 2-fluoroethynylbenzeneA | Joe Ridout | Joe Ridout; Louise Price |
| Database!K516 | 2-fluorotolueneA | Joe Ridout | Joe Ridout; Louise Price |
| Database!K510 | 3-fluorotolueneA | Joe Ridout | Joe Ridout; Louise Price |
| Database!K505 | 4-fluorotolueneA | Joe Ridout | Joe Ridout; Louise Price |
| Database!K87 | 5chlorouracilA | Ashley Hulme; Sarah Barnett | Ashley Hulme |
| Database!K44 | 5ethyluracilA | Nizar Issa | Nizar Issa; Weijia Zhu |
| Database!K458 | 5fluoroisatinA | Sharmarke Mohamed | Louise Price; Sharmarke Mohamed; Weijia Zhu |
| Database!K146 | 5fluorouracilA | Ashley Hulme | Ashley Hulme; Louise Price; Weijia Zhu |
| Database!K250 | 5nitrouracilA | Nizar Issa; Sarah Barnett | Nizar Issa |
| Database!K251 | 5nitrouracilB | Nizar Issa; Sarah Barnett | Nizar Issa |
| Database!K256 | 7fluoroisatinA | Sharmarke Mohamed | Sharmarke Mohamed; Weijia Zhu |
| Database!K165 | AnisoleA | Joe Ridout | Joe Ridout; Louise Price |
| Database!K254 | CaffeineB | Nizar Issa; Panos Karamertzanis | Nizar Issa |
| Database!K299 | EstradiolA | Erin Stevenson | Eric Stevenson |
| Database!K314 | IsobarbituricAcidB | Louise Price; Sarah Barnett | Louise Price |
| Database!K94 | NaproxenB | Doris Braun; Emiliana D'Oria | Emiliana D'Oria |
| Database!K332 | SaccharinA | Merina Corpinot | Louise Price; Merina Corpinot; Rui Guo |
| Database!K352 | SuccinicAcidD | Nizar Issa; Panos Karamertzanis | Nizar Issa |
| Database!K533 | XXXIIIB | Rui Guo | Louise Price; Rui Guo |

## Panel E: study dates

Single-year inclusion and year values agree for **303 of 310 searches** under the primary-model comparison above. Eight dates differ:

| Workbook cell | Dataset | Spreadsheet primary-model date | Website search date |
| --- | --- | --- | --- |
| Database!N22 | BarbituricAcidA | 2005 | 2004 |
| Database!N499 | CaffeineSalicylicAcidA | 2009 | 2010 |
| Database!N227 | Caffeinebis4HBAA | 2009 | 2010 |
| Database!N241 | ClozapineB | 2014 | 2025 |
| Database!N170 | IbuprofenA | 2017 | 2019 |
| Database!N59 | OxcarbazepineA | 2016 | 2017 |
| Database!N290 | PhthalimideA | 2006 | 2006-10 |
| Database!N361 | SulfadiazineA | December 2022 | March 2023 |

For ClozapineB, IbuprofenA and SulfadiazineA the website year occurs on a later matched model: this is a choice of model/study timing, not proof that the year is wrong. Phthalimide has a single year in the workbook but a range on the website. The workbook's primary-model dates produce **237 single-year searches** versus the website's 236. Coronene's unformatted Excel serial `42887` in N88 is interpreted as a 2017 date, avoiding a false missing year. `annual_date_comparison.csv` records the alternative annual bins without replacing the current series.

Column N is the study/model date. Column W (`Date to Github`) records later upload activity and must not be substituted into the existing study-year plots without changing their meaning.

## Panel F: linked literature

For **290 of 310 searches**, the website's raw publication text matches at least one associated workbook model after punctuation/case normalization. This is a text-consistency check, not an independent reconstruction of **75 unique linked CSP papers**. The workbook has plain citations, within-molecule Study_ID pointers, notes and unpublished work, rather than a complete standardized DOI/URL identity table. The existing DOI-deduplicated paper table and linked references remain necessary to verify the cumulative curve. The other 21 text differences are recorded in `search_metadata_comparison.csv`; a text difference does not by itself mean a publication is missing or incorrect.

## Recommended next revision

1. Resolve the eight formula conflicts and explicitly source the two oxygen-symbol repairs to the workbook.
2. Keep the 517,594 headline labelled archived structure files; retain the separate spreadsheet/archive reconciliation.
3. Adopt the proposed software panel C, with its counting rule and overlapping categories stated in the caption.
4. Agree a consistent rule for search versus later-model credits and dates, then regenerate D and E.
5. Rebuild the 3x2 figure from the reconciled data so that panel A and all associated text/captions match the latest source.

Only the audit outputs and proposed standalone panel have been created. The workbook, source tables and existing full figures are unchanged by this audit.
