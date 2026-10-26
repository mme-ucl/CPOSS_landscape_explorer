"""Compare source-reported CPOSS densities with paper-recovered reference histograms."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent
PARENT = BASE.parent
INPUTS = BASE / 'inputs'
TABLES = BASE / 'tables'
EDGES = np.linspace(.8, 2.4, 81)


def rebin_reference(frame, edges=EDGES):
    """Redistribute count mass by bin overlap; never compare unequal-width count bars."""
    mass = np.zeros(len(edges) - 1)
    for row in frame.itertuples():
        overlap = np.maximum(0, np.minimum(edges[1:], row.bin_right_g_cm3) - np.maximum(edges[:-1], row.bin_left_g_cm3))
        mass += row.recovered_count_height * overlap / row.bin_width_g_cm3
    return mass / mass.sum()


def balanced_weights(frame):
    """Equal systems, then equal searches within a system, then equal records."""
    records_per_search = frame.groupby('dataset_id').dataset_id.transform('size')
    searches_per_system = frame.groupby('source_url').dataset_id.transform('nunique')
    weights = 1 / (frame.source_url.nunique() * searches_per_system * records_per_search)
    assert abs(weights.sum() - 1) < 1e-10
    return weights.to_numpy()


def weighted_quantile(values, weights, quantiles):
    order = np.argsort(values, kind='stable')
    x, w = np.asarray(values)[order], np.asarray(weights)[order]
    cdf = np.cumsum(w) / w.sum()
    return x[np.searchsorted(cdf, quantiles, side='left')]


def main():
    TABLES.mkdir(exist_ok=True)
    manifest = json.loads((INPUTS / 'manifest.json').read_text())
    for name, digest in manifest['files'].items():
        assert hashlib.sha256((INPUTS / name).read_bytes()).hexdigest() == digest, name
    records = pd.read_csv(INPUTS / 'cposs_reported_density_records.csv.gz')
    bars = pd.read_csv(INPUTS / 'reference_histogram_bars.csv')
    single = records[(records.component_basis == 'single_molecule') & records.coordinate_validated_system].copy()
    multi = records[(records.component_basis == 'formula_unit') & records.coordinate_validated_system].copy()
    assert not records.duplicated(['dataset_id', 'model_id', 'filename']).any()
    populations = {'CPOSS_single_records': (single, np.ones(len(single))),
                   'CPOSS_single_system_balanced': (single, balanced_weights(single)),
                   'CPOSS_multicomponent_records': (multi, np.ones(len(multi)))}
    histograms, statistics, coverage, cdf_rows = [], [], [], []
    probabilities = {}
    for name, (frame, weights) in populations.items():
        values = frame.density_g_cm3.to_numpy()
        inside = (values >= EDGES[0]) & (values <= EDGES[-1])
        for scope, mask in [('all_available', np.ones(len(frame), dtype=bool)), ('shared_window', inside)]:
            x, w = values[mask], weights[mask]
            if name.endswith('system_balanced'):
                q1, med, q3 = weighted_quantile(x, w, [.25, .5, .75])
                method = 'inverse_weighted_ecdf'
            else:
                q1, med, q3 = np.quantile(x, [.25, .5, .75], method='linear')
                method = 'numpy_linear'
            statistics.append({'population': name, 'scope': scope, 'n_records': len(x),
                               'n_systems': frame.loc[mask, 'source_url'].nunique(),
                               'n_searches': frame.loc[mask, 'dataset_id'].nunique(),
                               'minimum_g_cm3': x.min(), 'q1_g_cm3': q1, 'median_g_cm3': med,
                               'q3_g_cm3': q3, 'maximum_g_cm3': x.max(), 'mean_g_cm3': np.average(x, weights=w),
                               'status': 'computed_from_source_reported_density_values', 'quantile_method': method})
        counts, _ = np.histogram(values[inside], bins=EDGES, weights=weights[inside])
        probabilities[name] = counts / counts.sum()
        coverage.append({'population': name, 'records_all': len(frame), 'systems_all': frame.source_url.nunique(),
                         'searches_all': frame.dataset_id.nunique(), 'records_in_window': int(inside.sum()),
                         'below_window_n': int((values < EDGES[0]).sum()), 'above_window_n': int((values > EDGES[-1]).sum()),
                         'outside_window_percent': 100 * (~inside).mean(),
                         'weighted_mass_outside_window_percent': 100 * weights[~inside].sum() / weights.sum()})
        x = values[inside]
        w = weights[inside]
        order = np.argsort(x, kind='stable')
        x, w = x[order], w[order]
        unique, indices = np.unique(x, return_index=True)
        cumulative = np.cumsum(np.add.reduceat(w, indices)) / w.sum()
        for value, probability in zip(unique, cumulative):
            cdf_rows.append({'population': name, 'density_g_cm3': value, 'cumulative_fraction': probability,
                             'status': 'exact_weighted_ecdf_of_source_reported_values_in_window'})
    for name, frame in bars.groupby('population'):
        probabilities[name] = rebin_reference(frame)
        p = probabilities[name]
        cdf = np.r_[0, np.cumsum(p)]
        q1, med, q3 = np.interp([.25, .5, .75], cdf, EDGES)
        statistics.append({'population': name, 'scope': 'shared_window', 'n_records': None,
                           'n_systems': None, 'n_searches': None, 'minimum_g_cm3': None,
                           'q1_g_cm3': q1, 'median_g_cm3': med, 'q3_g_cm3': q3,
                           'maximum_g_cm3': None, 'mean_g_cm3': np.sum(p * (EDGES[1:] + EDGES[:-1]) / 2),
                           'status': 'approximate_binned_paper_reference_conditional_on_window',
                           'quantile_method': 'uniform_within_rebinned_histogram_bins'})
    for name, p in probabilities.items():
        assert abs(p.sum() - 1) < 1e-12
        for left, right, probability in zip(EDGES[:-1], EDGES[1:], p):
            histograms.append({'population': name, 'bin_left_g_cm3': left, 'bin_right_g_cm3': right,
                               'probability_mass': probability, 'percent_per_bin': probability * 100,
                               'probability_density_cm3_g': probability / (right - left),
                               'status': 'histogram_of_reported_values' if name.startswith('CPOSS') else 'approximate_paper_histogram_recovery'})
    overlap = []
    for name in ['CPOSS_single_records', 'CPOSS_single_system_balanced']:
        for reference in ['OMC25_last_frames', 'CSD_organic']:
            overlap.append({'cp_population': name, 'reference': reference,
                            'shared_window_g_cm3': '0.8--2.4', 'bin_width_g_cm3': .02,
                            'histogram_overlap_percent': 100 * np.minimum(probabilities[name], probabilities[reference]).sum(),
                            'status': 'descriptive_approximate_binned_overlap_not_a_significance_test'})
    for name, rows in [('density_histograms_common_bins', histograms), ('density_statistics', statistics),
                       ('cposs_density_window_coverage', coverage), ('density_binned_overlap', overlap),
                       ('cposs_density_ecdfs', cdf_rows)]:
        pd.DataFrame(rows).to_csv(TABLES / (name + '.csv'), index=False, float_format='%.12g')
    stats = pd.DataFrame(statistics)
    summary = {row['population']: row for row in statistics if row['scope'] == 'shared_window'}
    cp, omc, csd, balanced = [summary[name] for name in ['CPOSS_single_records', 'OMC25_last_frames', 'CSD_organic', 'CPOSS_single_system_balanced']]
    cov = coverage[0]
    paragraph = rf"""% BEGIN DENSITY COMPARISON
\subsection{{Crystal-density distributions}}
We compared CPOSS crystal densities with the OMC25 last-frame and organic CSD 6.00 reference histograms in Fig.~3a of the OMC25 paper\cite{{gharakhanyan2026omc25}} (Fig.~\ref{{fig:cposs_omc25_csd_density}}). The CPOSS density population comprises {len(single):,} archive-linked visualisation records from {single.dataset_id.nunique()} searches covering {single.source_url.nunique()} single-component molecular systems. For each search, we selected the lowest-numbered archived energy model with an unambiguous density column labelled in g\,cm$^{{-3}}$, retained finite positive values whose filenames match that archive, and counted repeated filenames once per search. These are source-reported densities from the visualised subset, rather than a complete density census of all archived CPOSS files. Experimental-match annotations were retained because they also label predicted structures; the records are not claimed to be geometrically unique minima.

The OMC25 and CSD bar heights were recovered from the vector graphic and therefore provide approximate binned references rather than raw per-crystal measurements. Their different original bin widths were accounted for by conservative overlap rebinning to 0.02\,g\,cm$^{{-3}}$ bins. All curves were normalised within the common displayed interval 0.8--2.4\,g\,cm$^{{-3}}$; {cov['outside_window_percent']:.2f}\% of the available CPOSS single-component records fall outside this interval and are reported separately. Within this interval, the CPOSS record-weighted median density is {cp['median_g_cm3']:.2f}\,g\,cm$^{{-3}}$, compared with approximately {omc['median_g_cm3']:.2f}\,g\,cm$^{{-3}}$ for OMC25 and {csd['median_g_cm3']:.2f}\,g\,cm$^{{-3}}$ for the CSD reference. Giving each CPOSS molecular system equal weight, with equal weights for its searches, changes its conditional median to {balanced['median_g_cm3']:.2f}\,g\,cm$^{{-3}}$. This sensitivity reflects the unequal numbers of stored crystal candidates across CPOSS landscapes. Density agreement is descriptive and does not establish agreement in chemical composition, packing motifs or relative stability; the CSD reference contains experimentally determined crystals, whereas the computational populations also depend on their generation, relaxation and selection procedures.
% END DENSITY COMPARISON
"""
    # Edit the open manuscript fragment in place, preserving all other text.
    source_file = PARENT / 'results_section.tex'
    current = source_file.read_text()
    pattern = r'% BEGIN DENSITY COMPARISON.*?% END DENSITY COMPARISON\n?'
    if re.search(pattern, current, flags=re.S):
        updated = re.sub(pattern, lambda _: paragraph, current, flags=re.S)
    else:
        marker = '% BEGIN STANDALONE PREVIEW FOOTER'
        if marker in current:
            updated = current.replace(marker, paragraph + '\n' + marker, 1)
        else:
            updated = current.rstrip() + '\n\n' + paragraph
    source_file.write_text(updated)
    caption = rf"""\caption{{\textbf{{Crystal-density distributions in CPOSS, OMC25 and the CSD.}} \textbf{{(A)}} Normalised histograms of source-reported CPOSS densities and the OMC25 last-relaxation-frame and organic CSD 6.00 references recovered from Fig.~3a of the OMC25 paper\cite{{gharakhanyan2026omc25}}. The CPOSS sample contains {len(single):,} archive-linked visualisation records from {single.dataset_id.nunique()} searches and {single.source_url.nunique()} single-component molecular systems. Each search contributes the lowest-numbered archived energy model with a uniquely matched density column in g\,cm$^{{-3}}$; only finite positive densities whose filenames occur in that archive are retained, and repeated filenames are counted once per search. No geometric deduplication across searches is implied. Experimental-match annotations are retained because they can describe predicted structures. The CPOSS values describe the available visualisation subset, rather than all archived structure files. Reference bar heights are recovered from the paper's vector graphic and remain approximate, with no raw CSD or OMC25 per-crystal densities reconstructed. The original CSD and OMC25 bin widths differ; reference count mass is redistributed by bin overlap onto common 0.02\,g\,cm$^{{-3}}$ bins. Every distribution is normalised independently within 0.8--2.4\,g\,cm$^{{-3}}$, so tails outside this interval are not compared. The excluded-window fraction is {cov['outside_window_percent']:.2f}\% for the available CPOSS single-component records. \textbf{{(B)}} Conditional cumulative distributions. CPOSS curves use the source density values; reference curves assume uniform probability within the recovered bins. The dashed CPOSS curve gives each molecular system equal total weight, then each of its searches equal weight, before conditioning on the common window. This exposes sensitivity to the uneven number of candidates in each landscape.}}
\label{{fig:cposs_omc25_csd_density}}
"""
    (BASE / 'caption.tex').write_text(caption)
    (BASE / 'figure.tex').write_text(r"""\begin{figure*}[t]
  \centering
  \includegraphics[width=\textwidth]{cposs_omc25_csd_density_comparison.pdf}
  \input{density_caption.tex}
\end{figure*}
% Copy caption.tex from this density folder as density_caption.tex in the paper project.
""")
    report = f"""# Density comparison with the OMC25 paper histogram

The comparison uses **{len(single):,} source-reported CPOSS single-component density records**, from **{single.dataset_id.nunique()} searches and {single.source_url.nunique()} molecular systems**. The chemical comparison's eligible single-component population has 190 systems; density availability is a separate inclusion criterion. The density subset is not the full collection of 519,167 archived coordinate files. A further {len(multi):,} multicomponent records from {multi.source_url.nunique()} systems are tabulated separately.

## Reference extraction

[OMC25 paper, Fig. 3a](https://arxiv.org/pdf/2508.02651v1), PDF page 8. Source SHA-256: `{manifest['paper_sha256']}`. The reference is the training split, with one last sampled frame per relaxation trajectory, rather than all training frames. Four original histograms are recovered: last frames, generation first frames, Rigid Press first frames, and organic CSD 6.00. Only the last-frame and CSD references enter the principal comparison. The metadata CSV used for chemical statistics contains no cell volumes or densities and cannot supply these distributions.

The paper's vector rectangle geometry is calibrated against its density ticks (0.8 to 2.4) and count ticks (0, 5,000, 10,000, 15,000). Only rectangles starting at the histogram baseline and matching the four histogram colours are selected; legend swatches are excluded. Underlying bin widths are inferred from the bar-centre spacings, not the narrower rendered bars. The CSD width is approximately 0.008 g/cm^3, versus 0.020 for OMC25. Count mass is redistributed by overlap with common 0.02-wide bins. Every curve is then conditioned on [0.8, 2.4] g/cm^3 and normalized to unit mass. Exact per-crystal values and full-tail sample counts are unavailable for the references. The recovered displayed count sums must not be treated as exact dataset sizes.

## CPOSS source and counting rules

Each search contributes one source density column for the lowest-numbered documented archive with an unambiguous density column labelled /gcm-3. Alternate models are not pooled. Filenames are matched case-insensitively to RES members of the selected archive, excluding MacOS resource forks. Positive finite densities are retained once per filename per search. JSON blobs and archives are Git-checksum-verified. The density column is source-reported and is not recalculated from atom counts or molecular masses. Geometry validation in the earlier chemical analysis validates the molecular-system composition, not every density entry.

Rows with experimental-match annotations are retained: examples such as predicted NAPHTA_opt_* structures carry experimental-match text, so treating every non-empty annotation as an experimental crystal would incorrectly remove predictions. Archived reference structures may remain; this descriptive population is not asserted to contain exclusively independent predicted minima. Search-level missing columns, missing visualisations, unmatched filenames, duplicates and nonpositive/missing values are recorded in the input audit. Very low but positive source values are retained in the all-available statistics; they are not automatically repaired. Outliers and all records outside the comparison window remain in the CSVs.

Primary curves weight each retained CPOSS record equally. The sensitivity curve weights each molecular system equally, each search equally within its system, and records equally within a search, before conditioning on the common window. This is not a reweighting of the OMC25 or CSD reference, whose molecular identities are unavailable from the histogram. Differences in sampling, pressure, temperature, energy models and candidate selection cannot be separated by this comparison.

## Results

Within the common window, median densities (g/cm^3) are CPOSS {cp['median_g_cm3']:.3f}, OMC25 approximately {omc['median_g_cm3']:.3f}, and CSD approximately {csd['median_g_cm3']:.3f}. The system-balanced CPOSS median is {balanced['median_g_cm3']:.3f}. The available single-component CPOSS population has {cov['below_window_n']:,} records below 0.8 and {cov['above_window_n']:,} above 2.4 g/cm^3 ({cov['outside_window_percent']:.3f}% outside overall). Reference quantiles assume uniform probability within bins and should be quoted approximately at the 0.01--0.02 g/cm^3 scale. No significance tests are attached to the digitized references.

`tables/density_statistics.csv` separates all-available source statistics from shared-window statistics and records exact-source versus approximate-reference status. `tables/density_binned_overlap.csv` reports descriptive overlap coefficients within the shared window. Multicomponent CPOSS values are tabulated on a separate population; density is a crystal property, so no formula-unit mass is substituted for cell mass.

## Reproduce

From this folder, with the parent comparison's Python dependencies installed:

```sh
python analyse_density.py
python plot_density.py
python -m unittest -v test_density.py
```

These commands use compact frozen inputs and need no network. `prepare.py` documents recovery from the original paper and the Git-verified CPOSS JSON/archive caches; it additionally needs pdfplumber (version pinned in this folder's requirements.txt). The complete source JSONs and archives are not copied again into this deliverable. Their pinned source URLs, repository revision and checksums are provided for independent reacquisition. The open results_section.tex is updated in place only within its marked density block.
"""
    (BASE / 'report.md').write_text(report)
    validation = {'source_inputs_checksum_verified': True, 'shared_window': [.8, 2.4],
                  'common_bin_width': .02, 'primary_records': len(single), 'primary_systems': single.source_url.nunique(),
                  'primary_searches': single.dataset_id.nunique(), 'multicomponent_records': len(multi),
                  'normalization_max_error': max(abs(p.sum() - 1) for p in probabilities.values()),
                  'reference_status': 'approximate_vector_histogram_recovery',
                  'results_section_updated_in_place': True}
    (BASE / 'analysis_validation.json').write_text(json.dumps(validation, indent=2) + '\n')
    print(json.dumps({'validation': validation, 'conditional_medians_g_cm3': {name: row['median_g_cm3'] for name, row in summary.items()},
                      'overlap': overlap}, indent=2))


if __name__ == '__main__':
    main()
