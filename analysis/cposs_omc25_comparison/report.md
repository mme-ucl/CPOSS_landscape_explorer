# CPOSS and OMC25 chemical-content comparison

The principal comparison contains **190 coordinate-validated single-component CPOSS systems** and **44,403 OMC25 training molecular records**. A separate population contains **44 CPOSS multicomponent formula units**. The metadata-only single-component sensitivity population contains 191 systems.

## Population and identity rules

CPOSS systems are identified by documented molecular-system source page, not by search, energy model, structure file or molecular formula. All 235 source pages from the workbook audit were examined. The pre-existing molecular table contains 233 pages; the two missing pages are restored using workbook oxygen-symbol repairs confirmed by the coordinate representatives. All 235 workbook formula cells were read directly from the original XLSX and checked against the audit text. No workbook values were modified or recalculated.

Coordinate evidence comes from the existing molecular-extraction audit, but this analysis uses its **complete component counts per cell**, not just its selected largest component. The raw selected RES files are frozen and checksum-verified, and their SFAC/atom compositions are independently checked against the complete component totals. A CPOSS system is eligible if at least one search representative has valid coordinate evidence; two systems with an invalid representative are retained because another search provides a valid representative. Only tetrachlorobenzene has no valid alternative. A single molecular representative does not establish that every archived structure or model has the same chemistry. Connectivity and component identification inherit the documented extraction method; three unresolved bond-order assignments do not prevent elemental/nuclear composition checks.

OMC25 records use `csd_refcode` as the documented molecular identity. Molecular composition, atom count, molar mass and split are invariant across repeated crystal rows. All training crystal keys are unique. The downloaded train/validation file contains 218,841 starting crystals and 46,870 molecular records; only its 207,271 training starting crystals and 44,403 training molecular records enter the principal comparison. Training `nframes` sums to 24,870,226, which is checked but does not weight chemistry. The test split is not present. Formula-equal identifiers are retained. Thus these are documented molecular records, not a claim of deduplicated constitutional species.

The OMC25 paper explicitly describes single-component pristine molecular crystals with Z'=1. Its component basis is accepted as reported; connectivity cannot be independently established from this composition-only CSV. CPOSS single-component classification is supported by coordinate component identification. LY2806920HCl and MemantineHydrochloride are classified as salts even though their website formulas obscure the component separation. BTXV is also multicomponent.

## Formula decisions and exclusions

Eight composition conflicts and two malformed website formulas were reviewed. The workbook is selected where it agrees with complete coordinate compositions. For QuinoliniumFumarate the coordinates give C9H8N + C4H3O4 (total C13H11NO4); neither conflicting source formula has that total. For BTXV the coordinates give C8H8O2 + C5H7N3 (total C13H15N3O2), agreeing with the website total while restoring explicit components. These are nuclear-composition decisions for the archived systems; formal charges are not inferred by the formula parser. Full per-search evidence and archive URLs are in the inclusion audit.

| System | Workbook | Website | Selected formula | Decision |
| --- | --- | --- | --- | --- |
| BTXV | C8 H4 O2 . C5 H7 N3 | C13 H15 N3 O2 | C13H15N3O2 | coordinate_composition_selected_both_source_formulae_reviewed |
| Bipy-2Aminobenzoic | C10 H8 N2 . C7 H7 N1 O2 . C7 H7 N1 O2 | (C7 H7 N1 O2)2 - C8 H7 N1 O4 | C24H22N4O4 | workbook_selected_coordinates_resolve_composition_conflict |
| Bipy-Aminobenzoic | C10 H8 N2 . C7 H7 N1 O2 | C7 H7 N1 O2 - C8 H7 N1 O4 | C17H15N3O2 | workbook_selected_coordinates_resolve_composition_conflict |
| Dicyanobenzene-Succinic | C8 H4 N2 . C4 H6 O4 | C6 N2 H4 - C4 O4 H6 | C12H10N2O4 | workbook_selected_coordinates_resolve_composition_conflict |
| DipicolinicAcid | C7 H5 N1 O4 | C8 H5 N1 O4 | C7H5NO4 | workbook_selected_coordinates_resolve_composition_conflict |
| FenamicAcid | C13 H11 N1 O2 | C13 H12 N1 O2 | C13H11NO2 | workbook_selected_coordinates_resolve_composition_conflict |
| IsobarbituricAcid | C4 H4 N2 O3 | C4 H4 N2 03 | C4H4N2O3 | workbook_repairs_website_oxygen_symbol_coordinates_confirm |
| Naphthalene | C10 H8 | C8 H10 | C10H8 | workbook_selected_coordinates_resolve_composition_conflict |
| Piracetam | C6 H10 N2 O2 | C6 H10 N2 02 | C6H10N2O2 | workbook_repairs_website_oxygen_symbol_coordinates_confirm |
| QuinoliniumFumarate | C9 H8 N1 + . C4 H4 O3 - | C9 H8 N1 - C4 H4 O4 | C13H11NO4 | coordinate_composition_selected_both_source_formulae_reviewed |

Excluded from the coordinate-validated comparison: **Tetrachlorobenzene**. Their recorded formulas remain in the metadata-only sensitivity population. Their element tables do not support independent coordinate validation. No unresolved formula conflict was silently included in the primary comparison.

## Statistics

Atom counts include all formula hydrogens; non-H counts exclude only H. Molecular elemental prevalence counts records containing at least one atom of a species. It is distinct from the pooled atomic fraction, provided in the separate atomic_fractions.csv table. ECDFs use all observations, exact post-step jumps, independent normalization per population and no binning. Quartiles use NumPy's linear quantile definition. No sampling confidence intervals or significance tests are attached to these enumerated, purpose-selected populations.

| Population | Variable | N | Excluded | Min | Q1 | Median | Q3 | Max | Mean |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| CPOSS_single_verified | atom_count | 190 | 1 | 5.000 | 14.000 | 18.000 | 28.750 | 100.000 | 22.758 |
| CPOSS_single_verified | heavy_atom_count | 190 | 1 | 2.000 | 9.250 | 12.000 | 17.000 | 48.000 | 13.853 |
| CPOSS_single_verified | molar_mass_g_mol | 190 | 1 | 32.042 | 129.340 | 179.689 | 246.560 | 890.880 | 201.409 |
| OMC25_train | atom_count | 44403 | 0 | 4.000 | 31.000 | 39.000 | 48.000 | 164.000 | 41.540 |
| OMC25_train | heavy_atom_count | 44403 | 0 | 2.000 | 17.000 | 21.000 | 26.000 | 92.000 | 22.652 |
| OMC25_train | molar_mass_g_mol | 44403 | 0 | 30.026 | 252.892 | 312.150 | 386.620 | 1386.316 | 329.979 |
| OMC25_train | reported_molar_mass_g_mol | 44403 | 0 | 30.026 | 252.888 | 312.146 | 386.605 | 1386.292 | 329.972 |
| CPOSS_multicomponent_formula_units | atom_count | 44 | 0 | 14.000 | 23.000 | 31.000 | 40.750 | 120.000 | 36.273 |
| CPOSS_multicomponent_formula_units | heavy_atom_count | 44 | 0 | 9.000 | 14.000 | 18.000 | 23.250 | 56.000 | 20.523 |
| CPOSS_multicomponent_formula_units | molar_mass_g_mol | 44 | 0 | 131.091 | 212.109 | 245.258 | 332.316 | 757.072 | 288.455 |
| CPOSS_single_metadata_sensitivity | atom_count | 191 | 0 | 5.000 | 14.000 | 18.000 | 28.500 | 100.000 | 22.702 |
| CPOSS_single_metadata_sensitivity | heavy_atom_count | 191 | 0 | 2.000 | 9.500 | 12.000 | 17.000 | 48.000 | 13.832 |
| CPOSS_single_metadata_sensitivity | molar_mass_g_mol | 191 | 0 | 32.042 | 129.586 | 180.156 | 244.804 | 890.880 | 201.485 |

CPOSS fractions outside the observed OMC25 ranges: atom_count: 0/190 (0.00%); heavy_atom_count: 0/190 (0.00%); molar_mass_g_mol: 0/190 (0.00%). Range overlap does not establish matching connectivity, chemical environments, stereochemistry or packing coverage. Elements in verified CPOSS systems outside the OMC25 vocabulary: **Cu (1/190, 0.53%)**.

| Element | CPOSS count / N | CPOSS (%) | OMC25 count / N | OMC25 (%) |
| --- | ---: | ---: | ---: | ---: |
| H | 187/190 | 98.421 | 44248/44403 | 99.651 |
| B | 0/190 | 0.000 | 354/44403 | 0.797 |
| C | 190/190 | 100.000 | 44393/44403 | 99.977 |
| N | 136/190 | 71.579 | 29021/44403 | 65.358 |
| O | 150/190 | 78.947 | 36356/44403 | 81.877 |
| F | 16/190 | 8.421 | 2989/44403 | 6.732 |
| Si | 1/190 | 0.526 | 1855/44403 | 4.178 |
| P | 0/190 | 0.000 | 2444/44403 | 5.504 |
| S | 13/190 | 6.842 | 11019/44403 | 24.816 |
| Cl | 37/190 | 19.474 | 5175/44403 | 11.655 |
| Cu | 1/190 | 0.526 | 0/44403 | 0.000 |
| Br | 3/190 | 1.579 | 3245/44403 | 7.308 |
| I | 2/190 | 1.053 | 630/44403 | 1.419 |

## Molar-mass convention

Both datasets use the same frozen RDKit average atomic weights, saved in `inputs/atomic_weights.json`. Official OMC25 `mol.mass` values are retained and summarized separately. Their maximum absolute difference from the harmonized training masses is **0.032180 g/mol**. These small differences reflect atomic-weight conventions and are not used as a reason to infer mass from atom count. Full elemental compositions determine the harmonized masses; `xtal.mass` is used only to validate the unit-cell scaling. Multicomponent masses sum all species in the chosen written stoichiometric formula unit, without reducing its elemental formula to an empirical formula. Coordinate-derived ratios are explicitly labelled for the two cases above.

## Interpretation and limits

The molecular-size and mass distributions describe the documented chemical populations at equal weight per record. CPOSS has repeated CSP landscapes for a relatively small collection of molecular systems; OMC25 samples a broad molecular collection to train interatomic potentials. Neither a greater record count nor more relaxation frames establishes greater diversity of independent minima. The multicomponent population is a separate descriptive comparison because its formula-unit masses are not single-molecule masses. The exclusion of a system without a valid element table and the source identity conventions are material limitations.

No CSD chemical distributions are inferred. The supplied image's organic CSD 6.00 reference provides crystallographic frequencies only. The earlier visual extraction is retained as a reference, but no approximate image values enter these chemical plots or numerical results.

## Sources and provenance

- Official metadata revision: `5730920a2099cbc93613f7f0b8b98a8c607d47af`.
- Official metadata SHA-256: `afd58adbbc5fba225def6903af9fd41b374282259512bafe5102a5c53f9d3832`.
- Access time: `2026-10-24T13:48:38.343869+00:00`.
- [Official metadata](https://huggingface.co/datasets/facebook/OMC25/resolve/5730920a2099cbc93613f7f0b8b98a8c607d47af/omc25-starting-crystals.csv).
- [Official documentation](https://huggingface.co/datasets/facebook/OMC25/blob/5730920a2099cbc93613f7f0b8b98a8c607d47af/README.md).
- [OMC25 paper](https://www.nature.com/articles/s41597-026-06628-2), [preprint](https://arxiv.org/pdf/2508.02651).
- Original workbook SHA-256: `e8a410fa55c3e5cab90d4352a985f694e7f1d5e4b4085f1331edf68602eed2dc`.
- Frozen source paths and SHA-256 values for all input files are in `inputs/manifest.json`.

All comparison values in the CSV tables are computed from the frozen metadata and audited coordinate compositions. The OMC25 single-component scope and intended use are paper-reported. The prior image estimates are explicitly approximate and do not enter calculations. CSD chemical data are unavailable for this comparison.

## Density comparison extension

See density/report.md for the comparison with the OMC25 paper Figure 3a density histograms, including reference recovery, source coverage and weighting. The figure is output/pdf/cposs_omc25_csd_density_comparison.pdf. Density statistics and inclusion audits are under density/tables and density/inputs. Reproduce with density/analyse_density.py and density/plot_density.py from that folder, then run density/test_density.py and density/verify_density.py. The open results_section.tex contains the density subsection and supports both its editor preview and inclusion in a paper.
