"""Generate manuscript fragments and the audit report from computed results."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parent


def write_results(cposs, omc, statistics, elemental, validation, manifest):
    n = validation['cposs_single_verified']
    nm = validation['cposs_multicomponent_verified']
    nt = int((omc.split == 'train').sum())
    excluded = validation['cposs_excluded_systems']
    nex = len(excluded)
    exclusion_clause = (f'One CPOSS system with no valid alternative coordinate element table was excluded'
                        if nex == 1 else f'{nex} CPOSS systems with no valid alternative coordinate element table were excluded')
    nmeta = int(cposs.included_metadata_sensitivity.sum())
    source = 'CPOSS_single_verified'
    reference = 'OMC25_train'

    def stat(population, variable):
        return statistics[(statistics.population == population) & (statistics.variable == variable)].iloc[0]

    def prevalence(population, element):
        return elemental[(elemental.population == population) & (elemental.element == element)].iloc[0]

    a, b = stat(source, 'atom_count'), stat(reference, 'atom_count')
    h, k = stat(source, 'heavy_atom_count'), stat(reference, 'heavy_atom_count')
    m, r = stat(source, 'molar_mass_g_mol'), stat(reference, 'molar_mass_g_mol')
    extra = elemental[(elemental.population == source) & (elemental.records_with_element > 0) &
                      (elemental.element.map(lambda e: prevalence(reference, e).records_with_element == 0))]
    extra_text = ', '.join(f'{row.element} ({int(row.records_with_element)}/{n}, '
                           f'{row.prevalence_percent:.2f}%)' for row in extra.itertuples()) or 'none'
    ox, oy = prevalence(source, 'O'), prevalence(reference, 'O')
    nx, ny = prevalence(source, 'N'), prevalence(reference, 'N')
    outside = pd.read_csv(BASE / 'tables/outside_omc25_ranges.csv')
    out = outside[outside.population == source]
    out_text = '; '.join(f'{row.variable}: {int(row.outside_n)}/{int(row.n)} '
                          f'({row.outside_percent:.2f}%)' for row in out.itertuples())
    conflicts = cposs[cposs.original_audit_status != 'equal composition']
    primary_range = f'{int(a.minimum)}--{int(a.maximum)}'
    ref_range = f'{int(b.minimum)}--{int(b.maximum)}'
    mass_shift = validation['training_reported_mass_minus_common_max_absolute']

    results = rf"""\subsection{{Chemical composition and molecular-size coverage}}
We compared the chemical content of CPOSS with the training split of Open Molecular Crystals 2025 (OMC25)\cite{{gharakhanyan2026omc25}}, counting each documented CPOSS molecular system and each OMC25 CSD reference code once (Fig.~\ref{{fig:cposs_omc25_comparison}}). The principal comparison contains {n} single-component CPOSS systems with coordinate-validated compositions and {nt:,} OMC25 molecular records. Repeated CSP searches, energy models, generated packings and relaxation frames do not weight these molecular distributions. A further {nm} CPOSS multicomponent systems are described separately on their complete stoichiometric formula-unit basis. {exclusion_clause} from the coordinate-validated population; including the reported formula gives a supplementary metadata-only population of {nmeta} single-component systems.

CPOSS single-component systems contain {primary_range} atoms per molecule (median {a['median']:.0f}), compared with {ref_range} atoms (median {b['median']:.0f}) in OMC25. The corresponding median non-hydrogen atom counts are {h['median']:.0f} and {k['median']:.0f}. Using one average-atomic-weight convention for both datasets, CPOSS molar masses span {m.minimum:.2f}--{m.maximum:.2f}\,g\,mol$^{{-1}}$ (median {m['median']:.2f}\,g\,mol$^{{-1}}$), whereas OMC25 spans {r.minimum:.2f}--{r.maximum:.2f}\,g\,mol$^{{-1}}$ (median {r['median']:.2f}\,g\,mol$^{{-1}}$). These summaries describe the observed molecular populations and do not establish equivalence of their chemical environments or crystal packings.

Elemental occurrence is expressed as the fraction of molecular records containing each species. Oxygen occurs in {ox.prevalence_percent:.1f}\% of CPOSS systems and {oy.prevalence_percent:.1f}\% of OMC25 molecular records, while nitrogen occurs in {nx.prevalence_percent:.1f}\% and {ny.prevalence_percent:.1f}\%, respectively. The verified CPOSS population also contains Cu, outside the elemental vocabulary of OMC25. Its occurrence does not imply that OMC25 models have been evaluated on this chemistry. CPOSS additionally includes salts, solvates and co-crystals, which require a distinct formula-unit basis and are outside OMC25's stated single-component scope. The comparison therefore describes complementary sampling priorities: repeated crystal-energy-landscape searches in CPOSS and broad molecular sampling for training interatomic potentials in OMC25. The supplied reference figure provides no CSD elemental, molecular-size or mass distributions, so no such CSD curves are inferred here.
"""
    caption = rf"""\caption{{\textbf{{Chemical content of CPOSS and OMC25.}} The comparison uses {n} single-component CPOSS molecular systems with compositions checked against archived coordinate representatives and {nt:,} molecular records from the OMC25 training split. Each CPOSS system is counted once by its documented source page, and each OMC25 molecule once by its CSD reference code after verifying invariant molecular metadata across its starting-crystal records. Records are not merged by molecular formula. Repeated searches, energy models, crystal packings and relaxation frames do not weight the distributions. \textbf{{(A)}} Percentage of molecular records containing each element, using the union of species present in either dataset. Categories overlap and need not sum to 100\%. The ordinate is logarithmic; crosses at the lower edge denote zero occurrence. \textbf{{(B)}} Empirical cumulative distributions of molecular atom counts, including all hydrogens (solid) or excluding hydrogen (dashed). \textbf{{(C)}} Empirical cumulative distributions of molar mass, calculated from complete molecular compositions using the same frozen RDKit average atomic weights for both datasets. Official OMC25 \texttt{{mol.mass}} values are retained in the data tables; harmonisation changes individual training-set masses by at most {mass_shift:.3f}\,g\,mol$^{{-1}}$. All ECDFs are evaluated without binning. The source audit's eight composition conflicts and two malformed website formulas were reviewed against workbook and coordinate evidence, with all source choices recorded. {exclusion_clause} from the primary comparison and retained in a separate metadata-only sensitivity analysis. The {nm} verified multicomponent CPOSS systems are shown separately in the supplementary comparison using complete written stoichiometry or explicitly documented coordinate-derived component ratios. OMC25's molecular basis follows its published single-component definition; connectivity was not independently reconstructed from its metadata CSV. These molecular distributions do not describe unit-cell sizes or counts of independent crystal minima.}}
\label{{fig:cposs_omc25_comparison}}
"""
    supplementary = rf"""\caption{{\textbf{{Single-component and multicomponent CPOSS coverage relative to OMC25.}} The three populations are {n} coordinate-validated single-component CPOSS systems, {nm} coordinate-validated multicomponent CPOSS formula units, and {nt:,} OMC25 training molecular records. Panels and graphical conventions follow Fig.~\ref{{fig:cposs_omc25_comparison}}. Multicomponent systems include salts, hydrates, solvates and co-crystals and retain their full stoichiometric compositions, including counterions, coformers and water. Their atom counts and molar masses describe a formula unit rather than an individual molecule; they are shown as a distinct descriptive population. The complete written stoichiometry is preserved where it agrees with the archived component counts. For QuinoliniumFumarate and BTXV, coordinate-derived minimum integer component ratios resolve conflicting source compositions. Percentages and ECDFs are normalized independently within each population and are not weighted by the number of molecular components, CSP searches or archived structures.}}
\label{{fig:cposs_omc25_multicomponent}}
"""
    # Preserve the density extension and the editor-only preview wrappers on regeneration.
    import re
    target = BASE / 'results_section.tex'
    existing = target.read_text() if target.exists() else ''
    preserved = {}
    for name in ['STANDALONE PREVIEW PREAMBLE', 'DENSITY COMPARISON', 'STANDALONE PREVIEW FOOTER']:
        match = re.search(r'% BEGIN ' + name + r'.*?% END ' + name + r'\n?', existing, flags=re.S)
        preserved[name] = match.group(0) if match else ''
    results = (preserved['STANDALONE PREVIEW PREAMBLE'] + '\n' + results + '\n' +
               preserved['DENSITY COMPARISON'] + '\n' + preserved['STANDALONE PREVIEW FOOTER'])
    target.write_text(results)
    (BASE / 'caption.tex').write_text(caption)
    (BASE / 'caption_supplementary.tex').write_text(supplementary)
    (BASE / 'figure.tex').write_text(r"""% Requires \usepackage{graphicx}. Copy the PDF and caption into the paper project.
\begin{figure*}[t]
  \centering
  \includegraphics[width=\textwidth]{cposs_omc25_comparison.pdf}
  \input{caption.tex}
\end{figure*}
% In a one-column manuscript, use figure instead of figure*.
""")
    (BASE / 'figure_supplementary.tex').write_text(r"""\begin{figure*}[t]
  \centering
  \includegraphics[width=\textwidth]{cposs_omc25_multicomponent.pdf}
  \input{caption_supplementary.tex}
\end{figure*}
""")
    (BASE / 'references.bib').write_text(r"""@article{gharakhanyan2026omc25,
  author = {Gharakhanyan, Vahe and Barroso-Luque, Luis and Yang, Yi and Shuaibi, Muhammed and Michel, Kyle and Levine, Daniel S. and Dzamba, Misko and Fu, Xiang and Gao, Meng and Liu, Xingyu and others},
  title = {{Open Molecular Crystals 2025 (OMC25) dataset and models}},
  journal = {Scientific Data},
  year = {2026},
  doi = {10.1038/s41597-026-06628-2},
  url = {https://www.nature.com/articles/s41597-026-06628-2}
}
""")

    stats_lines = ['| Population | Variable | N | Excluded | Min | Q1 | Median | Q3 | Max | Mean |',
                   '| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for row in statistics.itertuples():
        stats_lines.append(f'| {row.population} | {row.variable} | {row.n} | {row.n_excluded} | '
                           f'{row.minimum:.3f} | {row.q1:.3f} | {row.median:.3f} | {row.q3:.3f} | {row.maximum:.3f} | {row.mean:.3f} |')
    element_lines = ['| Element | CPOSS count / N | CPOSS (%) | OMC25 count / N | OMC25 (%) |',
                     '| --- | ---: | ---: | ---: | ---: |']
    for element in elemental[elemental.population == reference].element:
        p, q = prevalence(source, element), prevalence(reference, element)
        element_lines.append(f'| {element} | {int(p.records_with_element)}/{n} | {p.prevalence_percent:.3f} | '
                             f'{int(q.records_with_element)}/{nt} | {q.prevalence_percent:.3f} |')
    resolution_lines = ['| System | Workbook | Website | Selected formula | Decision |', '| --- | --- | --- | --- | --- |']
    for row in conflicts.itertuples():
        resolution_lines.append(f'| {row.molecular_system} | {row.workbook_formula} | {row.website_formula} | '
                                f'{row.formula} | {row.decision} |')
    report = f"""# CPOSS and OMC25 chemical-content comparison

The principal comparison contains **{n} coordinate-validated single-component CPOSS systems** and **{nt:,} OMC25 training molecular records**. A separate population contains **{nm} CPOSS multicomponent formula units**. The metadata-only single-component sensitivity population contains {nmeta} systems.

## Population and identity rules

CPOSS systems are identified by documented molecular-system source page, not by search, energy model, structure file or molecular formula. All {len(cposs)} source pages from the workbook audit were examined. The pre-existing molecular table contains {len(pd.read_csv(BASE/'inputs/cposs_molecular_systems.csv'))} pages; the two missing pages are restored using workbook oxygen-symbol repairs confirmed by the coordinate representatives. All {len(cposs)} workbook formula cells were read directly from the original XLSX and checked against the audit text. No workbook values were modified or recalculated.

Coordinate evidence comes from the existing molecular-extraction audit, but this analysis uses its **complete component counts per cell**, not just its selected largest component. The raw selected RES files are frozen and checksum-verified, and their SFAC/atom compositions are independently checked against the complete component totals. A CPOSS system is eligible if at least one search representative has valid coordinate evidence; two systems with an invalid representative are retained because another search provides a valid representative. Only tetrachlorobenzene has no valid alternative. A single molecular representative does not establish that every archived structure or model has the same chemistry. Connectivity and component identification inherit the documented extraction method; three unresolved bond-order assignments do not prevent elemental/nuclear composition checks.

OMC25 records use `csd_refcode` as the documented molecular identity. Molecular composition, atom count, molar mass and split are invariant across repeated crystal rows. All training crystal keys are unique. The downloaded train/validation file contains 218,841 starting crystals and 46,870 molecular records; only its 207,271 training starting crystals and 44,403 training molecular records enter the principal comparison. Training `nframes` sums to 24,870,226, which is checked but does not weight chemistry. The test split is not present. Formula-equal identifiers are retained. Thus these are documented molecular records, not a claim of deduplicated constitutional species.

The OMC25 paper explicitly describes single-component pristine molecular crystals with Z'=1. Its component basis is accepted as reported; connectivity cannot be independently established from this composition-only CSV. CPOSS single-component classification is supported by coordinate component identification. LY2806920HCl and MemantineHydrochloride are classified as salts even though their website formulas obscure the component separation. BTXV is also multicomponent.

## Formula decisions and exclusions

Eight composition conflicts and two malformed website formulas were reviewed. The workbook is selected where it agrees with complete coordinate compositions. For QuinoliniumFumarate the coordinates give C9H8N + C4H3O4 (total C13H11NO4); neither conflicting source formula has that total. For BTXV the coordinates give C8H8O2 + C5H7N3 (total C13H15N3O2), agreeing with the website total while restoring explicit components. These are nuclear-composition decisions for the archived systems; formal charges are not inferred by the formula parser. Full per-search evidence and archive URLs are in the inclusion audit.

{chr(10).join(resolution_lines)}

Excluded from the coordinate-validated comparison: **{', '.join(excluded)}**. Their recorded formulas remain in the metadata-only sensitivity population. Their element tables do not support independent coordinate validation. No unresolved formula conflict was silently included in the primary comparison.

## Statistics

Atom counts include all formula hydrogens; non-H counts exclude only H. Molecular elemental prevalence counts records containing at least one atom of a species. It is distinct from the pooled atomic fraction, provided in the separate atomic_fractions.csv table. ECDFs use all observations, exact post-step jumps, independent normalization per population and no binning. Quartiles use NumPy's linear quantile definition. No sampling confidence intervals or significance tests are attached to these enumerated, purpose-selected populations.

{chr(10).join(stats_lines)}

CPOSS fractions outside the observed OMC25 ranges: {out_text}. Range overlap does not establish matching connectivity, chemical environments, stereochemistry or packing coverage. Elements in verified CPOSS systems outside the OMC25 vocabulary: **{extra_text}**.

{chr(10).join(element_lines)}

## Molar-mass convention

Both datasets use the same frozen RDKit average atomic weights, saved in `inputs/atomic_weights.json`. Official OMC25 `mol.mass` values are retained and summarized separately. Their maximum absolute difference from the harmonized training masses is **{mass_shift:.6f} g mol⁻¹**. These small differences reflect atomic-weight conventions and are not used as a reason to infer mass from atom count. Full elemental compositions determine the harmonized masses; `xtal.mass` is used only to validate the unit-cell scaling. Multicomponent masses sum all species in the chosen written stoichiometric formula unit, without reducing its elemental formula to an empirical formula. Coordinate-derived ratios are explicitly labelled for the two cases above.

## Interpretation and limits

The molecular-size and mass distributions describe the documented chemical populations at equal weight per record. CPOSS has repeated CSP landscapes for a relatively small collection of molecular systems; OMC25 samples a broad molecular collection to train interatomic potentials. Neither a greater record count nor more relaxation frames establishes greater diversity of independent minima. The multicomponent population is a separate descriptive comparison because its formula-unit masses are not single-molecule masses. The exclusion of a system without a valid element table and the source identity conventions are material limitations.

No CSD chemical distributions are inferred. The supplied image's organic CSD 6.00 reference provides crystallographic frequencies only. The earlier visual extraction is retained as a reference, but no approximate image values enter these chemical plots or numerical results.

## Sources and provenance

- Official metadata revision: `{manifest['omc25_revision']}`.
- Official metadata SHA-256: `{manifest['omc25_metadata_official_sha256']}`.
- Access time: `{manifest['accessed_utc']}`.
- [Official metadata]({manifest['omc25_metadata_url']}).
- [Official documentation]({manifest['omc25_documentation_url']}).
- [OMC25 paper](https://www.nature.com/articles/s41597-026-06628-2), [preprint](https://arxiv.org/pdf/2508.02651).
- Original workbook SHA-256: `{manifest['files']['Database 2023 checkup.xlsx']}`.
- Frozen source paths and SHA-256 values for all input files are in `inputs/manifest.json`.

All comparison values in the CSV tables are computed from the frozen metadata and audited coordinate compositions. The OMC25 single-component scope and intended use are paper-reported. The prior image estimates are explicitly approximate and do not enter calculations. CSD chemical data are unavailable for this comparison.
"""
    (BASE / 'report.md').write_text(report)
    (BASE / 'README.md').write_text(f"""# CPOSS versus OMC25

Reproducible molecular-content comparison: {n} coordinate-validated single-component CPOSS systems, {nm} separate CPOSS multicomponent formula units and {nt:,} OMC25 training molecular records. `report.md` explains populations, every formula decision, exclusions and mass harmonization.

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
""")
    versions = validation['software_versions'].copy()
    from importlib.metadata import version
    versions['fonttools'] = version('fonttools')
    (BASE / 'requirements.txt').write_text(''.join(f'{name}=={value}\n' for name, value in versions.items()))
    if (BASE / 'density/report.md').exists():
        density_note = ('\n## Density comparison extension\n\n'
                        'The density/ folder adds the CPOSS--OMC25--CSD comparison using the OMC25 paper Fig. 3a. '
                        'Its report explains histogram recovery, the shared density window, source coverage and weighting. '
                        'The new figure is output/pdf/cposs_omc25_csd_density_comparison.pdf. '
                        'Reproduce it with density/analyse_density.py and density/plot_density.py, then run '
                        'density/test_density.py and density/verify_density.py from that folder. '
                        'The density subsection and editor preview wrappers in results_section.tex are preserved on regeneration.\n')
        for filename in ['README.md', 'report.md']:
            with (BASE / filename).open('a') as stream:
                stream.write(density_note)
