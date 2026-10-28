# Figure 1C: search and refinement methods

The 2 x 2 bubble-pie matrix contains a pair of pies in each cell and replaces the software-frequency bars in the paper overview. It uses the unchanged 310-record CPOSS inventory, 508 energy-model archives and 517,594 archived RES members at source tree `6a77cc47b35f268f81a1d433b62c3e0917e20ffd` (source snapshot 27 October 2026; classification 28 October 2026).

## Definitions

Columns identify the initial generation program, MOLPAK or CrystalPredictor. The first documented energy model is model 1 when present. If model 1 is absent, the earliest documented model is inspected and its same-page Study_ID references are followed; a missing or cyclic target remains unresolved. Source spelling variants such as CrystalPrecictor are explicitly recognized. Program classifications are checked against the raw, Git-checksum-verified HTML, rather than reconstructed from the previously aggregated program frequencies.

Rows identify the reported refinement engine, DMAREL or DMACRYS. Sector colour denotes the refinement workflow, not search flexibility or chemical rotatability. DMACRYS and DMAREL are rigid-body engines; an explicitly reported CrystalOptimizer or DMAflex wrapper is treated as flexible refinement, including limited iterations. CrystalOptimizer's coupling to DMACRYS also supports the three current records that name CrystalOptimize without separately repeating DMACRYS. A flexible CrystalPredictor search with ordinary DMACRYS postprocessing is rigid at this refinement stage. Electronic methods used to generate a molecular charge density do not establish flexible refinement.

The current model's method is not inherited merely because its input structures came from an earlier flexible refinement. A named flexible postprocessor in an explicit current search/postprocessing workflow is accepted (for example, IbuprofenA model 1's DMAflex-Quick description). A DMAflex label in a potential description paired only with a Study_ID and DMAREL does not establish that this model actively repeated flexible refinement and remains unresolved. Reported single-point or unoptimized variants, sequences involving DFTB without verified intramolecular constraints, and ambiguous multiple-engine assignments are also kept outside the matrix. Explicit CCDC-supplied or Mercury origins are outside the two requested search columns, rather than reassigned to a generation program.

These classifications describe reported model workflows. They do not prove optimization convergence or that every archived experimental-reference entry underwent that workflow. Unknowns are never converted into rigid or flexible by default if the source names another potentially geometry-changing refinement stage.

Each cell contains a left pie labelled Structures and a right pie labelled Models. In the left pie, area is linear in archived file count, with no square-root or logarithmic compression of area. Radius is proportional to sqrt(count). Sector fractions use the same archived-file weighting as bubble area. Each archive contributes its verified RES member count once. The same filename or crystal represented in several energy-model archives contributes once per archive; no geometric deduplication is implied.

In the right pie, each distinct `(dataset_id, model_id)` pair contributes one model, irrespective of archive size. Area is linear in the number of models in the cell, and sectors show the numbers of rigid and flexible models. The two measures have independent area scales. Each size-key row shares the exact physical scale of its corresponding pies; a model bubble should not be compared directly with a structure-record bubble using a common area scale. The rotated row labels make room for the paired pies. All eight numeric callouts give the flexible contribution in the relevant unit; leaders connect to the true sector midpoint and run outside the filled pie interiors.

## Coverage

The matrix includes **457 of 508 models** and **468,787 of 517,594 archived records (90.57%)**. At least one model is classified for 292 of the 310 records. The remaining **51 models / 48,807 files** are outside the requested columns or unresolved. Models from a single dataset can fall in both the classified and excluded subsets.

| Search program | Refinement engine | Rigid records | Flexible records | Total records | Rigid models | Flexible models | Total models |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| MOLPAK | DMAREL | 24,310 | 110 | 24,420 | 114 | 7 | 121 |
| CrystalPredictor | DMAREL | 1,376 | 83 | 1,459 | 2 | 3 | 5 |
| MOLPAK | DMACRYS | 23,460 | 38 | 23,498 | 41 | 3 | 44 |
| CrystalPredictor | DMACRYS | 239,005 | 180,405 | 419,410 | 130 | 157 | 287 |

The model-weighted pies include 457 of 508 models (89.96%); their classified subset and exclusions are identical to those of the record-weighted pies. The nine TrinitrobenzeneA archive counts were independently read from the verified count table. All nine contain 203 RES members, contributing 1,827 rigid CrystalPredictor/DMACRYS records to the Structures pies and nine models to the Models pies. Equal archive counts do not establish identical geometries.

## Files and reproduction

- `model_classification.csv`: all 508 model records, classifications, source wording, original HTML/archive hashes and Study_ID evidence. `energy_model_weight` is one for every distinct dataset/model. The `matrix_*_weight` columns give total, rigid and flexible contributions in records and models; excluded rows contribute zero to both matrix measures.
- `unresolved_models.csv`: every excluded model, including its weight and reason.
- `matrix_counts.csv`: four cell totals and rigid/flexible counts for both archived records and equally weighted energy models.
- `classification_summary.json`: exact coverage, documentation links, source hashes and the Trinitrobenzene audit.
- `panel_validation.json`: two physical area scales, eight bubble radii, four size-key radii, all flexible callouts, row-label rotation and palette.

From the parent database_in_numbers folder, run `.venv/bin/python panel_c_methods/classify_methods.py`, `.venv/bin/python make_wide_figure.py`, and `.venv/bin/python panel_c_methods/draw_panel.py`. Run `../.venv/bin/python -m unittest -v test_methods.py` from this folder. Classification and figure generation require no network access.

## Primary method documentation

- [UCL methods: rigid MOLPAK/DMAREL and DMAflex refinement](https://www.chem.ucl.ac.uk/cposs/results/methods.html).
- [UCL DMACRYS](https://www.chem.ucl.ac.uk/cposs/dmacrys/).
- [UCL CrystalOptimizer coupling and flexibility](https://www.chem.ucl.ac.uk/cposs/computational/crystaloptimizer.html).
- [UCL postprocessing: flexible searches can receive rigid refinement](https://www.chem.ucl.ac.uk/cposs/computational/postprocessing.html).
