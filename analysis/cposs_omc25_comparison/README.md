# CPOSS versus OMC25

Reproducible molecular-content comparison: 189 coordinate-validated single-component CPOSS systems, 44 separate CPOSS multicomponent formula units and 44,403 OMC25 training molecular records. `report.md` explains populations, every formula decision, exclusions and mass harmonization.

## Main deliverables

- `output/pdf/cposs_omc25_comparison.pdf` and `figures/cposs_omc25_comparison.png`: wide three-panel comparison, vector PDF and 300-dpi PNG.
- `output/pdf/cposs_omc25_multicomponent.pdf` and corresponding PNG: distinct multicomponent formula-unit comparison.
- `results_section.tex`, `caption.tex`, `caption_supplementary.tex`, `figure.tex`, `figure_supplementary.tex`, `references.bib`: manuscript fragments.
- `tables/`: cleaned molecular populations, elemental prevalence/atomic fractions, exact ECDF coordinates, summary statistics, range coverage, exclusions and conflict resolutions.
- `inputs/`: unchanged frozen source workbook, CSV metadata and selected RES evidence, with checksums and repository revision. The proprietary macOS Helvetica font is not redistributed.

## Reproduce offline

Use Python 3.13. From this directory:

```sh
python3.13 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python analyse.py
.venv/bin/python plot.py --font /System/Library/Fonts/Helvetica.ttc
.venv/bin/python -m unittest -v test_analysis.py
.venv/bin/python verify_outputs.py
```

After installing dependencies, the analysis and figure recreation use only frozen inputs and need no network. `analyse.py` verifies all input checksums before processing. On another platform supply a licensed Helvetica TTF/TTC and matching bold face. Figure scripts preserve physical panel proportions and do not rotate or stretch output. The optional `check_latex.py` compiles all manuscript fragments with pdflatex/BibTeX and checks for undefined references and overfull boxes.

`prepare_inputs.py` documents the initial acquisition and freezing of the existing CPOSS evidence and official OMC25 file. It is not needed for reproduction and refuses to replace changed frozen inputs. Its defaults refer to the original source workspace and workbook.

To integrate with a paper, copy the two PDFs and the LaTeX fragments to the paper project. `figure.tex` uses a two-column `figure*`; change it to `figure` for a one-column document. Add `references.bib` to the paper's bibliography. All captions state their sample populations and counting units.

## Density comparison extension

The density/ folder adds the CPOSS--OMC25--CSD comparison using the OMC25 paper Fig. 3a. Its report explains histogram recovery, the shared density window, source coverage and weighting. The new figure is output/pdf/cposs_omc25_csd_density_comparison.pdf. Reproduce it with density/analyse_density.py and density/plot_density.py, then run density/test_density.py and density/verify_density.py from that folder. The density subsection and editor preview wrappers in results_section.tex are preserved on regeneration.
