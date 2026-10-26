# OMC25 and CSD reference statistics

Prepared 2026-10-24 from the user-supplied image and the primary OMC25 paper. This is a reference extraction, not a completed CPOSS comparison. The OMC25 metadata CSV has not been analysed for this extraction.

Image: `/var/folders/1_/5wbhw9_91r1ftt9zpxkr13ww0000gn/T/codex-clipboard-d6eb87d8-f371-4f62-8500-b8cbf0b6dd27.png`.

The figure concerns the **OMC25 training split**. Its chemical panels describe OMC25 only. The lower panels compare starting crystals with **organic entries in CSD 6.00**. CCDC is the organisation providing CSD, rather than the name of the plotted dataset. Molecule-level, starting-crystal-level and trajectory-frame counts have different denominators.

Primary references: [OMC25 paper, Table 1 and Figure 2](https://arxiv.org/pdf/2508.02651); [official metadata documentation](https://huggingface.co/datasets/facebook/OMC25/blob/main/README.md).

## Molecular elemental occurrences

All values below are coarse visual estimates from the supplied logarithmic bar chart. They count molecules containing an element, not the number of atoms of that element. One molecule can appear in multiple categories. Percentages use the paper's 44,403 training molecules and the rounded counts; these are not exact metadata-derived percentages.

| Element | Approximate molecules | Approximate molecular prevalence |
| --- | ---: | ---: |
| H | 44,000 | about 99–100% |
| B | 350 | 0.8% |
| C | 44,000 | about 99–100% |
| N | 29,000 | 65% |
| O | 36,000 | 81% |
| F | 3,000 | 6.8% |
| Si | 1,900 | 4.3% |
| P | 2,400 | 5.4% |
| S | 11,000 | 25% |
| Cl | 5,100 | 11% |
| Br | 3,300 | 7.4% |
| I | 640 | 1.4% |

The figure supplies **no corresponding CSD elemental distribution**.

## Size and mass

| Quantity | OMC25 value | Evidence |
| --- | --- | --- |
| Training molecular records | 44,403 | Paper, Table 1 |
| Training starting crystals | 207,271 | Paper, Table 1 |
| Training relaxation frames | 24,870,226 | Paper, Table 1; not independent molecules/crystals |
| Atoms per molecule, including H | 4–164; mean 42 | Paper text |
| Non-H atoms per molecule | Mean approximately 22 | Dotted line in supplied image |
| Atoms per starting unit cell, including H | 12–300; mean 130 | Paper text |
| Non-H atoms per starting unit cell | Mean approximately 112 | Dotted line in supplied image; verify against metadata |
| Molecular mass | Not plotted | Must use `mol.mass` or validated compositions |
| CSD molecular atom counts or masses | Not supplied | Cannot be extracted from this figure |

The approximate modal bins are 30–40 atoms for all-atom molecules, 20–30 for non-H molecular atoms, 75–100 for all-atom cells, and 50–75 for non-H cell atoms. Full histogram bins, medians, quantiles, and mass statistics have not been recovered. Means alone cannot reconstruct the distributions.

## Z values

OMC25 percentages are confirmed by the labelled Sankey diagram in the complete primary Figure 2, which is outside the supplied crop. CSD percentages are approximate bar readings. Z is the number of molecular units per cell, not the atom count.

| Z | OMC25 (%) | Organic CSD 6.00 (approximately %) |
| --- | ---: | ---: |
| 1 | 5.1 | 3 |
| 2 | 38.9 | 27 |
| 4 | 46.5 | 53 |
| 6 | 0.8 | 0.9 |
| 8 | 8.6 | 14 |
| 16 | 0.1 | 1.1 |

These are the six selected CSD Z categories. Do not renormalize their approximate CSD readings to 100% or infer an exact residual.

## Space groups

The supplied panel selects the ten most frequent **CSD** groups. This differs from the ten most frequent OMC25 groups in the complete paper's Sankey diagram. Its `other` category therefore differs too. Values shown with `~` or a range are approximate readings, not exact measurements.

| No. | Space group | OMC25 (%) | Organic CSD 6.00 (approximately %) |
| --- | --- | ---: | ---: |
| 1 | P1 | 10.9 | 1.4 |
| 2 | P-1 | 9.4 | 21–22 |
| 4 | P2_1 | 11.1 | 8–9 |
| 5 | C2 | ~2.1 | 1.2 |
| 9 | Cc | ~2.3 | 1.0 |
| 14 | P2_1/c | 3.1 | 34–36 |
| 15 | C2/c | ~0.3 | 6–7 |
| 19 | P2_12_12_1 | 3.2 | 11 |
| 33 | Pna2_1 | 2.8 | 1.6 |
| 61 | Pbca | ~0.35 | 3.5 |
| — | Other groups outside this selection | ~55 | 9–10 |

OMC25 values without `~` are crosschecked against the labelled primary Sankey diagram; the remainder are visually estimated. The precision of the bar readings is limited, especially for low percentages on logarithmic axes.

## Crystal systems

| Crystal system | OMC25 (%) | Organic CSD 6.00 (%) |
| --- | ---: | ---: |
| Triclinic | 20.3 | ~23 |
| Monoclinic | 38.0 | ~53 |
| Orthorhombic | 24.6 | ~21 |
| Tetragonal | 16.5 | 1.5 |
| Other: trigonal + hexagonal + cubic | 0.7 | 1.9 |

OMC25 values are labelled in the primary Sankey diagram; CSD tetragonal and other percentages are stated in the paper text. The remaining CSD values are approximate image readings. Rounding can prevent totals from summing to exactly 100%.

## Route to exact chemical statistics

Use the official [starting-crystals metadata CSV](https://huggingface.co/datasets/facebook/OMC25/blob/main/omc25-starting-crystals.csv), approximately 23.8 MB. Its documented fields include `csd_refcode`, `split`, `mol.composition`, `mol.natoms`, `mol.mass`, `xtal.composition`, `xtal.natoms`, `xtal.mass`, `z_value`, `xtal.spacegroup`, `genarris_step`, `xtal.id`, and `nframes`. The documented public splits are train and validation. Check the downloaded file rather than assuming test metadata is present.

Filter to training for reproduction of the figure. Validate the molecular fields across rows sharing a molecular identifier before reducing to one record per molecule; otherwise molecular statistics would be weighted by the number of generated packings. Masses are documented in g/mol. Record the downloaded revision and checksum. Exact metadata-derived values should replace the visual estimates in any final comparison figure.
