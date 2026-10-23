# Global visualization audit — 23 October 2026

The navigator now uses one scientific preset for every dataset. There are no molecule-specific presets or colour exceptions. The reference controls were captured from the live 2-Aminobenzamide — Search A view before revision in [reference-before.json](reference-before.json).

| Check | Result |
| --- | --- |
| Catalogue snapshot | `d65c1732ab6db46b8af34e0646a760c56a8d559c` |
| Dataset source files | 315; each verified against its Git blob SHA |
| Structure/property rows | 166,991 |
| Source geometry validation | Every structure checked; 0 failures |
| Adapter validation | Every property row checked; 0 failures |
| Native loads/renders | 315 datasets; 0 failures |
| Native marker colours checked | 166,991; 0 mismatches |
| Native PNG raster comparisons | 25 sampled marker centres across 8 datasets/fixtures; 0 failures |
| Automated regression tests | 25 JavaScript + 5 Python passed |
| Embedded Chemiscope/jQuery libraries | Byte-identical to Git HEAD |

The adapter report is [visualization-audit.json](visualization-audit.json). It records resolved axes, paired models, missing-axis rows, space-group sources/counts/unresolved values, the Experimental Info policy, the resolved preset and geometry checks for every catalogue entry. The native report is [native-visualization-audit.json](native-visualization-audit.json). It records actual saved controls, rendered marker arrays, rendered palette/bounds, source-export comparisons and native errors for every dataset.

The native catalogue audit renders **all scatter rows and the original first geometry** for every dataset using Chemiscope's on-demand loader. The other geometries are validated from the full original source by Python; they are not individually rendered. A single long browser batch exhausted graphics resources during preparation, so the final successful run used resumable batches of eight with full document reloads. This batching is only in the QA harness.

[Native raster regressions](native-visualization-regressions.json) compare numeric, reordered-symbol, constant-SG, all-unknown, mixed-missing and legacy-saved-style fixtures, plus 2aminobenzamideA and 26-dichloronitrobenzeneA. International group 14 rendered **RGB (237, 237, 255)** in every applicable case, including the constant-group fixture and both real datasets. Groups 1, 2, 4, 19 and 230 and unknown grey were also sampled as available. These are native exported-raster pixels, in addition to checking controls and Plotly marker specifications.

## Scientific policy

- Axes use the most complete jointly finite Density/Lattice Energy pair from the same model, with deterministic model-order ties. Original field names and units remain visible. No cross-model pairing, unit guessing or replacement measurements.
- Colours use physical international numbers 1–230, normalized from valid numbers/numeric strings or the validated Gemmi 0.7.5 Hermann–Mauguin table. Native log10 is applied once; seismic limits stay 0–2.37. Unresolved or conflicting data are grey. No category-order colouring.
- Custom instance-level compatibility corrects Chemiscope's constant-colour midpoint shortcut and all-unknown validation. Actual data rows remain unchanged in count/order; no dummy SG numbers or structures are inserted.
- Numeric Experimental Info retains supplied numeric values. Text descriptions use a separate display score: nonblank annotation = 0, blank/missing = 1; native flip-linear makes annotations larger. Constant columns use the native uniform reference size. Size factor is always 55 initially. Original descriptions remain available and source exports retain them.
- Initial dataset/URL settings are superseded. Manual control changes and deliberate after-load settings imports remain possible. Filtering, previews and resize do not reapply the preset. All loader paths use the same wrapper.

## Upstream data gaps

- **56 datasets have no space-group field.** In total, **35,976 rows across 75 datasets** have no reliably supplied space group and are consistently grey. This includes five invalid supplied zero values (AlloxanA: 1; DiiodoanthanthroneA: 4). No numbers were inferred from geometry or filenames. Exact counts and dataset names are in the adapter report.
- **BTXIVA has 184 structures but no scientifically named Density/Lattice Energy fields.** Its numerical property names are values such as `1.447035` and `-104.353`. The adapter cannot reliably identify their meaning or units. It therefore shows an empty scientific scatter, with all structures selectable, until the upstream labels are repaired. Its supplied space-group numbers still use the same colour policy.
- **3,010 rows across 60 datasets** lack usable values for the selected axis pair, including BTXIVA's 184 rows. Those points are omitted from that scatter, without removing structures or changing property alignment. Dataset notes names the affected current axes and counts. Other models can be selected deliberately.
- Experimental Info is absent in GuanineB, GuanineC and TransFOX7A; those datasets use uniform reference sizes. The reference dataset has 883 blank descriptions, also giving uniform sizes.
- Urea selects complete model 1 and plots all 850 rows; model 2 lacks 57 Density/Energy values. Eight supplied SG values are missing and grey.
- Some source field names contain suspect supplied units (for example a Density field labelled `/kJmol-1`). The adapter preserves these labels and does not guess corrections.

## Browser interaction verification

Automatic startup, catalogue switching, search/code selection, preview opening/closing and initial embedded/URL-setting priority were checked through the HTTP navigator. A deliberate palette/size-factor change survived filtering and split-preview resizing; switching to another dataset restored seismic/factor 55. The automated native regression also checks deliberate after-load settings API changes. Embedded startup and responsive checks are recorded in [browser-verification.json](browser-verification.json).

The browser declined file-upload permission during the settings-file picker check. File-picker settings import and an actual local/streaming file upload therefore remain **unverified in this browser session**. Unit tests cover the common load wrapper's local/streaming entry points; this is not a claim that the blocked file-picker interaction was tested.

Reproduction instructions are in the README. Implementation and verification are local only; nothing was published or deployed.
