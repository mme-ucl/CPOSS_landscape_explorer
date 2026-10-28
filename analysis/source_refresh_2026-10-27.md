# CPOSS analysis source refresh - 27 October 2026

Pinned repository tree: `6a77cc47b35f268f81a1d433b62c3e0917e20ffd`.

The analysis now follows exactly the 310 JSON records in the current 0.Chemiscope inventory. All source HTML pages, JSON files, workbooks and selected structure archives were checked against this tree's Git blob hashes. Unchanged local sources were reused only after checksum verification.

Three outdated page-link identifiers were reconciled: 4C2NBAMHA -> 4C2NBMHA; FluorouracilA -> 5fluorouracilA; PhloroglucinolDihydrateA -> PhloroglucinolDihydrateB. Every filename in each current JSON occurs in that search's documented structure archives. The original links and per-model overlap counts are retained in database_in_numbers/sources/current_json_aliases.json. MethylazetidineoneA has no current JSON record and is explicitly excluded, rather than retained as an additional dataset. Thus 311 legacy HTML search entries resolve to 310 current JSON records.

| Measurement | Refreshed value |
| --- | ---: |
| Current JSON records | 310 |
| Molecular-system pages | 234 |
| Energy-model archives | 508 |
| Archived RES structure files | 517,594 |
| JSON visualization entries | 158,344 |
| Sketch-map records | 307 of 310 |
| Files represented by sketch-map records | 517,431 |
| Verified single-component chemical systems | 189 |
| Verified multicomponent formula units | 44 |
| Single-component density records | 114,284 |
| Molecular systems contributing those densities | 187 |

The same three coordinate element-table errors exclude 25-dichloronitrobenzeneA, 35-dichloronitrobenzeneA and TetrachlorobenzeneA from the map (163 archived files in total). No element identities were guessed or source structures repaired. Molecular extraction, SOAP descriptors, five sketch-map initializations, refinement and two switching-distance sensitivity runs were repeated. The fitted sigma remains 0.49679834824933117; the selected initialization is now seed 83. The eight callout molecules have unchanged geometry and retain their validated renderings.

The published OMC25 chemical training split and OMC25/CSD density-histogram references retain their established comparison definitions. CPOSS density inputs and all normalized curves were regenerated. Equal molecular-system weighting is applied after restricting CPOSS to the displayed window; reference histograms are independently normalized.

The approved typography, layouts, palette, exponent-form units and removal of in-figure comments are preserved. All 45 tests passed, the molecular output verifier passed 1,970 checks, LaTeX fragments compiled, and the final PDF renderings were visually inspected.

The JSON-inventory mode is reproduced with database_in_numbers/analyse.py --refresh --current-json-inventory --reconcile sources/current_json_aliases.json --extract-only (from its own directory). Follow with reconcile_structure_counts.py, count_structure_archives.py, analyse.py --plot-only, workbook_crosscheck/crosscheck.py and make_wide_figure.py. Refresh molecular inputs with extract_molecules.py --refresh-inputs, then run embed.py, plot.py and analyse_results.py. The comparison supports prepare_inputs.py --refresh, followed by analyse.py and plot.py; repeat density/prepare.py, density/analyse_density.py and density/plot_density.py with the documented reference PDF and verified caches.
