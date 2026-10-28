# Density comparison with the OMC25 paper histogram

The comparison uses **114,284 source-reported CPOSS single-component density records**, from **258 searches and 187 molecular systems**. The chemical comparison's eligible single-component population has 189 systems; density availability is a separate inclusion criterion. The density subset is not the full collection of 517,594 archived coordinate files. A further 31,460 multicomponent records from 43 systems are tabulated separately.

## Reference extraction

[OMC25 paper, Fig. 3a](https://arxiv.org/pdf/2508.02651v1), PDF page 8. Source SHA-256: `0d0323aae495bb787445a4ab43f3b4cff87922d52d1e7c4a59460e213d462dae`. The reference is the training split, with one last sampled frame per relaxation trajectory, rather than all training frames. Four original histograms are recovered: last frames, generation first frames, Rigid Press first frames, and organic CSD 6.00. Only the last-frame and CSD references enter the principal comparison. The metadata CSV used for chemical statistics contains no cell volumes or densities and cannot supply these distributions.

The paper's vector rectangle geometry is calibrated against its density ticks (0.8 to 2.4) and count ticks (0, 5,000, 10,000, 15,000). Only rectangles starting at the histogram baseline and matching the four histogram colours are selected; legend swatches are excluded. Underlying bin widths are inferred from the bar-centre spacings, not the narrower rendered bars. The CSD width is approximately 0.008 g cm⁻³, versus 0.020 for OMC25. Count mass is redistributed by overlap with common 0.02-wide bins. Every curve is then conditioned on [0.8, 2.4] g cm⁻³ and normalized to unit mass. Exact per-crystal values and full-tail sample counts are unavailable for the references. The recovered displayed count sums must not be treated as exact dataset sizes.

## CPOSS source and counting rules

Each search contributes one source density column for the lowest-numbered documented archive with an unambiguous density column labelled /gcm-3. Alternate models are not pooled. Filenames are matched case-insensitively to RES members of the selected archive, excluding MacOS resource forks. Positive finite densities are retained once per filename per search. JSON blobs and archives are Git-checksum-verified. The density column is source-reported and is not recalculated from atom counts or molecular masses. Geometry validation in the earlier chemical analysis validates the molecular-system composition, not every density entry.

Rows with experimental-match annotations are retained: examples such as predicted NAPHTA_opt_* structures carry experimental-match text, so treating every non-empty annotation as an experimental crystal would incorrectly remove predictions. Archived reference structures may remain; this descriptive population is not asserted to contain exclusively independent predicted minima. Search-level missing columns, missing visualisations, unmatched filenames, duplicates and nonpositive/missing values are recorded in the input audit. Very low but positive source values are retained in the all-available statistics; they are not automatically repaired. Outliers and all records outside the comparison window remain in the CSVs.

The figure shows only the system-balanced CPOSS population: restrict records to the common window, then weight each molecular system equally, each represented search equally within its system, and records equally within a search. This gives exactly equal system totals in the displayed interval, including when systems have different tail fractions. Record-weighted statistics remain in the tables but are not plotted. Histograms show probability density (unit area), and cumulative curves end at one. This is not a reweighting of the OMC25 or CSD reference, whose molecular identities are unavailable from the histogram. Differences in sampling, pressure, temperature, energy models and candidate selection cannot be separated by this comparison.

## Results

Within the common window, median densities (g cm⁻³) are CPOSS 1.350, OMC25 approximately 1.293, and CSD approximately 1.336. The system-balanced CPOSS median is 1.387. The available single-component CPOSS population has 900 records below 0.8 and 119 above 2.4 g cm⁻³ (0.892% outside overall). Reference quantiles assume uniform probability within bins and should be quoted approximately at the 0.01--0.02 g cm⁻³ scale. No significance tests are attached to the digitized references.

`tables/density_statistics.csv` separates all-available source statistics from shared-window statistics and records exact-source versus approximate-reference status. `tables/density_binned_overlap.csv` reports descriptive overlap coefficients within the shared window. Multicomponent CPOSS values are tabulated on a separate population; density is a crystal property, so no formula-unit mass is substituted for cell mass.

## Reproduce

From this folder, with the parent comparison's Python dependencies installed:

```sh
python analyse_density.py
python plot_density.py
python -m unittest -v test_density.py
```

These commands use compact frozen inputs and need no network. `prepare.py` documents recovery from the original paper and the Git-verified CPOSS JSON/archive caches; it additionally needs pdfplumber (version pinned in this folder's requirements.txt). The complete source JSONs and archives are not copied again into this deliverable. Their pinned source URLs, repository revision and checksums are provided for independent reacquisition. The open results_section.tex is updated in place only within its marked density block.
