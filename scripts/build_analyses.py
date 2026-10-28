#!/usr/bin/env python3
"""Build the static analyses page from the existing scientific result tables.

Uses only Python's standard library. Raw workbooks, source caches and local
filesystem paths are not part of the page's figure-and-table download bundle.
"""
from __future__ import annotations

import csv
from datetime import date
import hashlib
from html import escape
import io
import json
from pathlib import Path
import statistics
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / 'data/analyses'
DB = 'analysis/database_in_numbers'
METHODS = DB + '/panel_c_methods'
CMP = 'analysis/cposs_omc25_comparison'
MAP = 'analysis/molecular_sketchmap'
DENS = CMP + '/density'
SOURCE_FILES = set()


def read_json(path):
    SOURCE_FILES.add(path)
    return json.loads((ROOT / path).read_text())


def read_csv(path):
    SOURCE_FILES.add(path)
    with (ROOT / path).open(newline='') as stream:
        return list(csv.DictReader(stream))


def number(value, places=0):
    if value in ('', None):
        return '—'
    return f'{float(value):,.{places}f}'


def e(value):
    return escape(str(value), quote=True)


def table(headers, rows, caption=None, classes=''):
    heading = ''.join(f'<th scope="col">{e(h)}</th>' for h in headers)
    def cell(value):
        attribute = ' class="numeric"' if isinstance(value, (int, float)) else ''
        return f'<td{attribute}>{e(value)}</td>'
    body = ''.join('<tr>' + ''.join(cell(value) for value in row) + '</tr>' for row in rows)
    title = f'<caption class="sr-only">{e(caption)}</caption>' if caption else ''
    return f'<div class="scroll-table"><table class="mini-table {classes}">{title}<thead><tr>{heading}</tr></thead><tbody>{body}</tbody></table></div>'


def svg_years(rows):
    width, height, left, bottom = 570, 190, 34, 157
    maximum = max(int(r['landscapes']) for r in rows)
    step = (width - left - 12) / len(rows)
    parts = [f'<svg class="plot-svg" viewBox="0 0 {width} {height}" role="img" aria-label="CSP searches with a single study year, 2003 to 2025">']
    for value in [0, 10, 20, 30]:
        y = bottom - value / 30 * 132
        parts.append(f'<line class="grid" x1="{left}" x2="558" y1="{y:.2f}" y2="{y:.2f}"/><text x="25" y="{y+4:.2f}" text-anchor="end">{value}</text>')
    for i, row in enumerate(rows):
        count = int(row['landscapes'])
        x, h = left + i * step + 3, count / 30 * 132
        parts.append(f'<rect class="bar" x="{x:.2f}" y="{bottom-h:.2f}" width="{step-5:.2f}" height="{h:.2f}"><title>{row["year"]}: {count} searches; {number(row["archive_structure_files"])} archived files</title></rect>')
        if i % 4 == 0 or i == len(rows) - 1:
            parts.append(f'<text x="{x+step/2-3:.2f}" y="180" text-anchor="middle">{row["year"]}</text>')
    return ''.join(parts) + '</svg>'


def bar_list(rows, label, value, limit=None):
    rows = rows[:limit] if limit else rows
    maximum = max(float(r[value]) for r in rows)
    return '<div class="bars">' + ''.join(f'<div class="bar-row"><span>{e(r[label])}</span><div class="bar-track"><div class="bar-fill" style="--bar-width:{100*float(r[value])/maximum:.4f}%"></div></div><b>{number(r[value])}</b></div>' for r in rows) + '</div>'


def figure_inventory():
    chemical = read_json(CMP + '/analysis_validation.json')
    sketch = read_json(MAP + '/verification.json')
    methods = read_json(METHODS + '/classification_summary.json')
    definitions = [
        ('chemical-content', 'CPOSS and OMC25: chemical content', 'comparison', 'Current', CMP, 'cposs_omc25_comparison', 'caption.tex',
         f"Elemental prevalence, molecular atom counts and molar-mass distributions for {chemical['cposs_single_verified']} verified single-component CPOSS systems and 44,403 OMC25 training molecular records. Every molecular record receives equal weight.", 'chemical--summary_statistics.csv', ''),
        ('density', 'Crystal densities: CPOSS, OMC25 and CSD', 'comparison', 'Current', CMP, 'cposs_omc25_csd_density_comparison', 'density/caption.tex',
         'Archive-linked CPOSS density records compared with histogram references recovered from the OMC25 paper. CPOSS systems have equal total weight within the shared 0.8–2.4 g cm⁻³ window; each probability density has unit area.', 'density--density_statistics.csv', ''),
        ('molecular-map', 'Molecular diversity in CPOSS', 'map', 'Current', MAP, 'cposs_molecular_sketchmap', 'caption.md',
         f"A molecular SOAP sketch-map of {sketch['datasets_included']} current records. Marker area scales with the square root of archived-file count; colour shows representative-component molar mass. Multicomponent systems use their largest non-water component.", 'map--dataset_embedding.csv', ''),
        ('multicomponent', 'Multicomponent formula units', 'comparison', 'Supplementary', CMP, 'cposs_omc25_multicomponent', 'caption_supplementary.tex',
         'The 44 verified salts, hydrates, solvates and co-crystals are shown separately from the single-component comparison. Atom counts and masses retain all components and stoichiometry of each formula unit.', 'chemical--cposs_multicomponent_formula_units.csv', ''),
        ('software', 'Search and refinement methods', 'overview', 'Current', DB, 'panel_c_search_refinement', 'panel_c_methods/README.md',
         f"Paired pie charts compare MOLPAK/CrystalPredictor searches with DMAREL/DMACRYS refinement. Purple and gold show rigid and flexible refinement. Structures and models use independent area scales. Includes {methods['classified_models']} of {methods['energy_models']} models and {methods['classified_archived_records']:,} archived records.", 'methods--matrix_counts.csv', ''),
    ]
    figures = []
    for ident, title, category, status, directory, stem, caption, description, data, note in definitions:
        image = f'{directory}/figures/{stem}.png'
        pdf = f'{directory}/output/pdf/{stem}.pdf'
        if not (ROOT / image).is_file():
            raise FileNotFoundError(image)
        figures.append({'id': ident, 'title': title, 'category': category, 'status': status,
                        'image': image, 'pdf': pdf if (ROOT / pdf).is_file() else None,
                        'caption': f'{directory}/{caption}' if caption else None,
                        'description': description, 'data': f'data/analyses/{data}', 'note': note})
    return figures


LABELS = {
    'summary_statistics': 'Molecular-size and mass summary statistics',
    'matrix_counts': 'Search and refinement matrix counts',
    'dataset_embedding': 'Molecular sketch-map coordinates and representatives',
    'density_statistics': 'Density statistics and histogram-reference status',
    'cposs_multicomponent_formula_units': 'Verified multicomponent CPOSS formula units',
}
GROUPS = [('methods', 'Search and refinement methods', METHODS),
          ('map', 'Molecular map', MAP + '/tables'),
          ('chemical', 'Chemical comparison', CMP + '/tables'),
          ('density', 'Density comparison', DENS + '/tables')]
PRIORITY = ['chemical--summary_statistics', 'density--density_statistics',
            'methods--matrix_counts', 'map--dataset_embedding',
            'chemical--cposs_multicomponent_formula_units']


def public_cell(value):
    if '/Users/' in value or '/private/tmp/' in value or '/tmp/' in value:
        # Only local provenance/error fields use these strings; no scientific number is changed.
        return 'Local source location omitted; scientific provenance is described on the analyses page.'
    return value


def export_tables(required_paths):
    downloads = []
    for namespace, group, directory in GROUPS:
        for path in sorted((ROOT / directory).glob('*.csv')):
            key = namespace + '--' + path.stem
            filename = key + '.csv'
            public_path = 'data/analyses/' + filename
            if public_path not in required_paths:
                continue
            relative = str(path.relative_to(ROOT))
            rows = read_csv(relative)
            with path.open(newline='') as stream:
                fields = csv.DictReader(stream).fieldnames
            output = io.StringIO(newline='')
            writer = csv.DictWriter(output, fieldnames=fields, lineterminator='\n')
            writer.writeheader()
            writer.writerows({k: public_cell(v or '') for k, v in row.items()} for row in rows)
            raw = output.getvalue().encode()
            (PUBLIC / filename).write_bytes(raw)
            label = LABELS.get(path.stem, path.stem.replace('_', ' ').capitalize())
            downloads.append({'id': key, 'title': label, 'group': group, 'namespace': namespace,
                              'path': public_path, 'rows': len(rows), 'bytes': len(raw),
                              'sha256': hashlib.sha256(raw).hexdigest(), 'source': relative})
    exported = {item['path'] for item in downloads}
    if exported != required_paths:
        raise FileNotFoundError(f'Missing figure tables: {sorted(required_paths - exported)}')
    return sorted(downloads, key=lambda r: (PRIORITY.index(r['id']) if r['id'] in PRIORITY else 100, r['group'], r['title']))


def figure_cards(figures):
    cards = []
    for f in figures:
        links = f'<a class="expand" href="{e(f["image"])}" data-expand="{f["id"]}">Expand figure ↗</a>'
        if f['pdf']:
            links += f'<a href="{e(f["pdf"])}" download>Vector PDF ↓</a>'
        links += f'<a href="{e(f["image"])}" download>PNG ↓</a><a href="{e(f["data"])}" download>Data CSV ↓</a>'
        if f['caption']:
            links += f'<a href="{e(f["caption"])}" download>Caption ↓</a>'
        note = f'<p class="figure-note">{e(f["note"])}</p>' if f['note'] else ''
        cards.append(f'''<article class="figure-card" id="figure-{f['id']}" data-category="{f['category']}">
<a class="figure-preview" href="{e(f['image'])}" data-expand="{f['id']}" aria-label="Expand {e(f['title'])}"><img src="{e(f['image'])}" alt="{e(f['description'])}" loading="lazy" decoding="async"></a>
<div class="figure-body"><div class="figure-meta"><span>{e(f['category'].replace('map', 'Molecular map'))}</span><span class="status">{e(f['status'])}</span></div>
<h3>{e(f['title'])}</h3><p>{e(f['description'])}</p>{note}<div class="figure-links">{links}</div></div></article>''')
    return '\n'.join(cards)


def main():
    PUBLIC.mkdir(parents=True, exist_ok=True)
    SOURCE_FILES.clear()
    manifest = read_json(DB + '/manifest.json')
    comparison = read_json(CMP + '/analysis_validation.json')
    density_validation = read_json(DENS + '/analysis_validation.json')
    sketch = read_json(MAP + '/verification.json')
    datasets = read_csv(DB + '/tables/plot_datasets.csv')
    chemical = read_csv(CMP + '/tables/cposs_molecular_systems_audit.csv')
    molecular = read_csv(CMP + '/tables/summary_statistics.csv')
    elements = read_csv(CMP + '/tables/elemental_prevalence.csv')
    annual = read_csv(DB + '/tables/annual_counts.csv')
    contributors = read_csv(DB + '/tables/contributors.csv')
    contributor_links = read_csv(DB + '/tables/dataset_contributors.csv')
    papers = read_csv(DB + '/tables/cumulative_papers.csv')
    paper_records = read_csv(DB + '/tables/papers.csv')
    method_summary = read_json(METHODS + '/classification_summary.json')
    methods = read_csv(DB + '/tables/method_frequencies.csv')
    density = read_csv(DENS + '/tables/density_statistics.csv')
    density_coverage = read_csv(DENS + '/tables/cposs_density_window_coverage.csv')
    catalogue = read_json('data/catalogue.json')
    files = [int(float(r['structure_count'])) for r in datasets]
    q1, _, q3 = statistics.quantiles(files, n=4, method='inclusive')
    credited = len({r['dataset_id'] for r in contributor_links})
    figures = figure_inventory()
    method_figure = next(figure for figure in figures if figure['id'] == 'software')
    for figure in figures:
        SOURCE_FILES.update(figure[key] for key in ['image', 'pdf', 'caption'] if figure[key])
    downloads = export_tables({figure['data'] for figure in figures})
    counts = manifest['figure_structure_counts']
    assert len(datasets) == len(catalogue['datasets']) == manifest['datasets']
    assert {r['dataset_id'] for r in datasets} == {r['id'] for r in catalogue['datasets']}
    assert sum(files) == counts['archive_structure_files']
    assert method_summary['source_revision'] == manifest['snapshot_revision']
    assert method_summary['energy_models'] == counts['archives']
    assert method_summary['total_archived_records'] == sum(files)
    single = [r for r in chemical if r['component_basis'] == 'single_molecule']
    multi = [r for r in chemical if r['component_basis'] == 'formula_unit']
    linked_papers = sum(float(r['csp_paper_count'] or 0) > 0 for r in datasets)
    summary = {'snapshot': manifest['accessed_date'], 'snapshot_revision': manifest['snapshot_revision'],
               'searches': len(datasets), 'molecular_systems': len(chemical), 'archived_structure_files': sum(files),
               'model_archives': counts['archives'], 'navigator_catalogue_files': len(catalogue['datasets']),
               'visualization_entries': counts['visualization_entries'], 'linked_csp_papers': int(papers[-1]['cumulative_unique_papers']),
               'all_linked_references': len(paper_records), 'searches_with_csp_papers': linked_papers,
               'named_scientists': len(contributors), 'searches_with_named_scientists': credited,
               'structure_files_per_search': {'minimum': min(files), 'q1': q1, 'median': statistics.median(files),
                                             'q3': q3, 'maximum': max(files), 'mean': statistics.mean(files)},
               'single_component_metadata_systems': len(single), 'multicomponent_formula_units': len(multi),
               'coordinate_verified_single_component_systems': comparison['cposs_single_verified'],
               'coordinate_verified_multicomponent_systems': comparison['cposs_multicomponent_verified'],
               'formula_only_systems': comparison['cposs_excluded_systems'],
               'dated_searches': sum(int(r['landscapes']) for r in annual),
               'undated_or_ambiguous_searches': len(datasets) - sum(int(r['landscapes']) for r in annual),
               'search_refinement': {key: method_summary[key] for key in ['classified_archived_records', 'total_archived_records', 'classified_models', 'energy_models', 'unresolved_models', 'unresolved_archived_records']},
               'density': density_validation, 'map': {k: sketch[k] for k in ['datasets_included', 'represented_structure_files', 'metrics']},
               'figures': figures, 'downloads': downloads, 'source_status': 'computed from frozen analysis outputs; OMC25/CSD density reference recovered approximately from a histogram'}
    summary_json = json.dumps(summary, indent=2, ensure_ascii=False) + '\n'
    (PUBLIC / 'summary.json').write_text(summary_json)

    def metric(value, label):
        return f'<div class="stat"><strong>{number(value)}</strong><span>{e(label)}</span></div>'

    metrics = ''.join(metric(value, label) for value, label in [
        (summary['archived_structure_files'], 'archived structure files'), (summary['molecular_systems'], 'molecular systems'),
        (summary['searches'], 'current JSON records'), (summary['model_archives'], 'energy-model archives'), (summary['linked_csp_papers'], 'linked CSP papers'), (summary['named_scientists'], 'named scientists')])
    scope_rows = [['Archived RES coordinate files', number(sum(files)), f"All {summary['model_archives']} documented model archives; models counted separately"],
                  ['Linked visualization entries', number(counts['visualization_entries']), 'Available Chemiscope exports; can be subsets'],
                  ['Archive coverage', f"{len(datasets)} / {len(datasets)} records", 'Complete file counts for every documented search'],
                  ['Single-component systems', f"{len(single)} metadata / {comparison['cposs_single_verified']} verified", 'Tetrachlorobenzene remains formula-only'],
                  ['Multicomponent systems', '44 / 44 verified', 'Complete salts, co-crystals, hydrates and solvates'],
                  ['Dated searches', f'{summary["dated_searches"]} / {len(datasets)}', 'Single unambiguous study year; release years unavailable'],
                  ['Named credits', f'{credited} / {len(datasets)} searches', f'{len(contributors)} scientists; credits can overlap'],
                  ['Searches with a linked CSP paper', f'{linked_papers} / {len(datasets)}', 'A missing link does not establish that no paper exists']]
    method_tables = ''.join(f'<details class="table-details"><summary>{title}</summary>{table(["Category", "Searches"], [[r["category"], int(r["datasets"])] for r in methods if r["kind"] == kind])}<p class="source-note">Categories overlap; each search counts at most once per category.</p></details>' for kind, title in [('potential_family', 'Reported intermolecular potential families'), ('electronic_method', 'Reported molecular electronic-structure methods')])
    cp_stats = {r['variable']: r for r in molecular if r['population'] == 'CPOSS_single_verified'}
    omc_stats = {r['variable']: r for r in molecular if r['population'] == 'OMC25_train'}
    comparison_rows = []
    for key, title, precision in [('atom_count', 'Atoms per molecule', 0), ('heavy_atom_count', 'Non-H atoms per molecule', 0), ('molar_mass_g_mol', 'Molar mass (g mol⁻¹)', 2)]:
        cp, omc = cp_stats[key], omc_stats[key]
        comparison_rows.append([title, f'{number(cp["median"], precision)} ({number(cp["minimum"], precision)}–{number(cp["maximum"], precision)})', f'{number(omc["median"], precision)} ({number(omc["minimum"], precision)}–{number(omc["maximum"], precision)})'])
    element_lookup = {(r['population'], r['element']): r for r in elements}
    element_rows = []
    for row in elements:
        if row['population'] != 'OMC25_train':
            continue
        cp = element_lookup[('CPOSS_single_verified', row['element'])]
        element_rows.append([row['element'], f'{number(cp["prevalence_percent"], 2)}% ({cp["records_with_element"]}/{cp["valid_records"]})',
                             f'{number(row["prevalence_percent"], 2)}% ({number(row["records_with_element"])}/{number(row["valid_records"])})'])
    density_names = {'CPOSS_single_records': 'CPOSS: per record', 'CPOSS_single_system_balanced': 'CPOSS: equal weight per system',
                     'OMC25_last_frames': 'OMC25: last frames (≈)', 'CSD_organic': 'Organic CSD reference (≈)'}
    conditional = {r['population']: r for r in density if r['scope'] == 'shared_window'}
    density_rows = [[label, number(conditional[key]['median_g_cm3'], 2), number(conditional[key]['q1_g_cm3'], 2),
                     number(conditional[key]['q3_g_cm3'], 2), number(conditional[key]['mean_g_cm3'], 2)] for key, label in density_names.items()]
    cov = density_coverage[0]
    contributors_table = table(['Named scientist', 'Credited searches'], [[r['scientist_name'], int(r['dataset_count'])] for r in contributors])
    chronology_table = table(['Study year', 'Searches', 'Archived files', 'Cumulative searches'], [[r['year'], int(r['landscapes']), int(r['archive_structure_files']), int(r['cumulative_datasets'])] for r in annual])
    publication_table = table(['Publication year', 'New linked CSP papers', 'Cumulative CSP papers'], [[r['year'], int(r['new_unique_papers']), int(r['cumulative_unique_papers'])] for r in papers])
    figure_data_json = json.dumps({'figures': figures}, ensure_ascii=False).replace('<', '\\u003c').replace('&', '\\u0026')
    html = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="CPOSS dataset figures, archived structure statistics, molecular diversity, and comparisons with OMC25 and the Cambridge Structural Database.">
<title>Analyses &amp; statistics · CDCCS Landscape Navigator</title>
<link rel="icon" type="image/png" href="assets/cposs-logo-circle-blue.png">
<link rel="stylesheet" href="assets/analyses.css?v=20261028-purple-urea"><link rel="stylesheet" href="assets/site.css?v=20261028-purple-urea"><script src="assets/analyses.js?v=20261027-cleanup" defer></script></head><body>
<a class="skip" href="#main">Skip to analyses</a>
<header class="topbar"><div class="topbar-inner"><a class="cposs-brand nav-return" href="./"><img class="cposs-brand-logo" src="assets/cposs-logo-circle-blue.png" alt="" width="80" height="80" decoding="async"><span>CDCCS Landscape Navigator</span></a><nav class="toplinks site-toplinks" aria-label="Site navigation"><a class="btn btn-sm btn-outline-light" href="https://louiseprice.github.io/CPOSS_Database/index.html">CDCCS website</a><a class="btn btn-sm btn-outline-light nav-return" href="./">← Explore landscapes</a></nav></div></header>
<div class="hero"><div class="wrap"><p class="eyebrow">The CPOSS dataset</p><h1>Analyses &amp; comparisons</h1><p class="intro">The figures, statistics and source data behind the landscapes. Explore molecular diversity, the scope of the archive, and comparisons with OMC25 and the Cambridge Structural Database.</p>
<div class="snapshot"><span>Source snapshot · {date.fromisoformat(manifest['accessed_date']).strftime('%d %B %Y')}</span><span>Revision <code>{manifest['snapshot_revision'][:12]}</code></span></div><div class="stats">{metrics}</div>
</div></div>
<nav class="jump-nav" aria-label="Analysis sections"><div class="wrap"><a href="#figures">All figures</a><a href="#dataset-statistics">Dataset statistics</a><a href="#chemical-comparison">OMC25 comparison</a><a href="#density-comparison">Crystal densities</a></div></nav>
<main id="main" class="wrap">
<section id="figures" aria-labelledby="figures-title"><div class="section-head"><div><h2 id="figures-title">The figure collection</h2><p>Expand a figure to inspect it, or download the original image, vector PDF, caption and underlying tables.</p></div><span class="count">{len(figures)} analysis figures</span></div>
<div class="filters" role="group" aria-label="Filter figures"><button class="chip" data-figure-filter="all" aria-pressed="true">All figures</button><button class="chip" data-figure-filter="comparison" aria-pressed="false">Comparisons</button><button class="chip" data-figure-filter="map" aria-pressed="false">Molecular map</button><button class="chip" data-figure-filter="overview" aria-pressed="false">Dataset overview</button></div>
<p id="figure-count" class="results-status" aria-live="polite"></p><div class="figure-grid">{figure_cards(figures)}</div></section>
<section id="dataset-statistics" aria-labelledby="statistics-title"><div class="section-head"><div><h2 id="statistics-title">The dataset in numbers</h2><p>Archive totals, source coverage, study history and the people and methods named in the database.</p></div><a class="detail-link" href="data/analyses/summary.json" download>Summary JSON ↓</a></div>
<div class="two-up"><article class="panel"><h3>Archive size and coverage</h3><div class="metric-strip"><div><strong>{number(statistics.median(files))}</strong><span>median files per search</span></div><div><strong>{number(min(files))}–{number(max(files))}</strong><span>range per search</span></div></div><p>The middle half of searches contain {number(q1, 1)}–{number(q3, 1)} archived files. All {len(datasets)} records have complete archive counts.</p>{table(['Measurement', 'Available', 'Definition'], scope_rows)}<p class="source-note">Visualization entries, spreadsheet rows and archive files describe overlapping scopes and are not added together.</p></article>
<article class="panel"><h3>Study history</h3>{svg_years(annual)}<div class="metric-strip"><div><strong>{summary['dated_searches']}</strong><span>searches with a single study year</span></div><div><strong>{summary['undated_or_ambiguous_searches']}</strong><span>ambiguous or interval dates</span></div></div><p>The dated searches contain {number(counts['annual_structure_files'])} archived files; {number(counts['unassigned_year_structure_files'])} files fall outside the dated series. Study dates do not measure database release or deposition.</p><details class="table-details"><summary>Annual searches and structure-file totals</summary>{chronology_table}</details><details class="table-details"><summary>Linked CSP papers by publication year</summary>{publication_table}</details></article></div>
<div class="two-up"><article class="panel"><h3>Search and refinement methods</h3><a class="methods-preview" href="{e(method_figure['image'])}" data-expand="software" aria-label="Expand search and refinement methods"><img src="{e(method_figure['image'])}" alt="{e(method_figure['description'])}" loading="lazy" decoding="async"></a><p>The paired pies show archived structure records and equally weighted energy models. Each measure has its own area scale; purple denotes rigid refinement and gold flexible refinement.</p><p class="source-note">{number(method_summary['classified_archived_records'])} of {number(method_summary['total_archived_records'])} records and {number(method_summary['classified_models'])} of {number(method_summary['energy_models'])} models are classified. The remaining {number(method_summary['unresolved_models'])} models / {number(method_summary['unresolved_archived_records'])} records lie outside the matrix or remain unresolved. Structure records retain separate energy-model representations.</p><a class="detail-link" href="{e(method_figure['data'])}" download>Download matrix counts ↓</a>{method_tables}</article>
<article class="panel"><h3>Named scientists and linked literature</h3>{bar_list(contributors, 'scientist_name', 'dataset_count', 8)}<p>{credited} searches name at least one scientist. Credits overlap and follow the source Scientist field; paper authorship is recorded separately.</p><details class="table-details"><summary>All {len(contributors)} named scientists</summary>{contributors_table}</details><div class="metric-strip"><div><strong>{summary['linked_csp_papers']}</strong><span>unique linked CSP papers</span></div><div><strong>{number(summary['all_linked_references'])}</strong><span>linked references overall</span></div></div><p>{linked_papers} searches link a qualifying CSP paper. References are deduplicated by DOI or canonical URL; experimental-context references are recorded separately.</p></article></div></section>
<section id="chemical-comparison" aria-labelledby="chemical-title"><div class="section-head"><div><h2 id="chemical-title">Chemical coverage relative to OMC25</h2><p>Equal weight per documented molecular record: {comparison['cposs_single_verified']} verified single-component CPOSS systems and 44,403 OMC25 training molecular records.</p></div><a class="detail-link" href="#figure-chemical-content">View figure ↑</a></div>
<div class="two-up"><article class="panel"><h3>Molecular size and molar mass</h3>{table(['Variable', 'CPOSS median (range)', 'OMC25 median (range)'], comparison_rows)}<p>The observed CPOSS single-component size and mass ranges lie within OMC25’s ranges. Range overlap does not establish matching chemical environments or crystal packings.</p><div class="population-note"><p>The other 44 verified CPOSS systems are complete multicomponent formula units. They retain coformers, counterions and water; their masses are not single-molecule masses. One additional single-component system remains in the formula-only sensitivity population.</p></div><p class="source-note">Molar masses use one frozen average-atomic-weight convention. Original OMC25 masses are retained; harmonization changes a training mass by at most 0.032 g mol⁻¹.</p></article>
<article class="panel"><h3>Elemental occurrence</h3>{table(['Element', 'CPOSS: percentage (count/N)', 'OMC25: percentage (count/N)'], element_rows)}<p class="source-note">A record contributes once to every element it contains. These overlapping percentages do not sum to 100%. Cu occurs in CPOSS and is outside the OMC25 elemental vocabulary.</p></article></div>
</section>
<section id="density-comparison" aria-labelledby="density-title"><div class="section-head"><div><h2 id="density-title">Crystal-density distributions</h2><p>CPOSS source-reported densities compared with the last-frame OMC25 and organic CSD references from Figure 3a of the OMC25 paper.</p></div><a class="detail-link" href="#figure-density">View figure ↑</a></div>
<div class="two-up"><article class="panel"><h3>Shared interval: 0.8–2.4 g cm⁻³</h3>{table(['Population', 'Median', 'Q1', 'Q3', 'Mean'], density_rows)}<p class="source-note">All values are in g cm⁻³ and conditional on the shared interval. OMC25 and CSD values are approximate histogram recoveries, not statistics calculated from raw crystal records.</p></article>
<article class="panel"><h3>Density coverage and weighting</h3><div class="metric-strip"><div><strong>{number(density_validation['primary_records'])}</strong><span>available source density records</span></div><div><strong>{density_validation['primary_systems']}</strong><span>single-component systems</span></div></div><p>{number(cov['records_in_window'])} records from {density_validation['primary_searches']} searches lie in the comparison window. {number(cov['outside_window_percent'], 2)}% lie outside it and remain in the data tables.</p><p>Each search contributes one archive-linked density column. The CPOSS curves give each molecular system equal total weight within the shared window, with equal weights for its represented searches. This prevents systems with more stored candidates from dominating. OMC25 and CSD are independently normalized histogram references; their molecular-system identities are unavailable for reweighting.</p><p class="source-note">This visualization subset is not a density census of all {number(sum(files))} archived files. Density agreement does not establish equal chemical, packing or stability coverage.</p></article></div>
</section>
</main><footer class="footer"><div class="wrap"><span>CDCCS Landscape Navigator · Analyses &amp; comparisons</span><a class="nav-return" href="./">Return to the Landscape Navigator ↑</a><span>Source snapshot · October 2026</span></div></footer>
<dialog id="figure-dialog" aria-labelledby="dialog-title"><div class="dialog-header"><h2 id="dialog-title"></h2><button id="dialog-close" type="button" aria-label="Close figure">Close ×</button></div><img class="dialog-image" id="dialog-image" alt=""><div class="dialog-footer"><span id="dialog-description"></span><a id="dialog-original" target="_blank" rel="noopener noreferrer">Full-resolution image ↗</a><a id="dialog-pdf" download>Vector PDF ↓</a></div></dialog>
<script type="application/json" id="analysis-data">{figure_data_json}</script>
</body></html>'''
    (ROOT / 'analyses.html').write_text(html)
    guide = f'''# CPOSS figures and statistics

Source snapshot: {manifest['accessed_date']}. Revision: {manifest['snapshot_revision']}.

The page reports {len(datasets)} current JSON records across {len(chemical)} molecular systems, {sum(files):,} model-specific archived RES files, and {summary['model_archives']} model archives. It does not claim geometric uniqueness. The analysis and Navigator now use the same JSON inventory.

The corrected chemical comparison contains {comparison['cposs_single_verified']} coordinate-verified single-component systems, 44 verified complete multicomponent formula units, and a separate {len(single)}-system metadata-only sensitivity population. OMC25 uses 44,403 training molecular identifiers.

Density statistics use {density_validation['primary_records']:,} archive-linked CPOSS visualization records from {density_validation['primary_systems']} systems. The OMC25 and organic CSD references are approximate recoveries from paper Figure 3a. Comparisons are conditional on 0.8–2.4 g cm⁻³, with common 0.02-wide bins. Atomic fractions and molecular elemental prevalence are separate measurements.

The molecular map contains {sketch['datasets_included']} of {len(datasets)} records. Its multicomponent representatives are the largest non-water components, not complete formula units.

The search/refinement pie-chart matrix uses separate area scales for archived records and equally weighted energy models. It classifies {method_summary['classified_archived_records']:,} records and {method_summary['classified_models']} models; the remaining {method_summary['unresolved_models']} models are outside the matrix or unresolved. The linked matrix CSV and methods notes describe this figure, replacing the earlier program-frequency bar chart.

Files: summary.json contains aggregate statistics and the five-figure catalogue; build-manifest.json records source checksums. The five CSVs are the complete result tables linked by the retained figures. The ZIP includes only these figures, captions and linked tables. Earlier overview exports, sketch-map diagnostics and separate molecular illustrations are excluded from the public downloads. Original analysis files and previously exported CSV copies remain on disk, but are not linked by this page or included in its download catalogue or ZIP. Source workbooks and large source caches are not included.

Sources: https://louiseprice.github.io/CPOSS_Database/index.html ; https://huggingface.co/datasets/facebook/OMC25 ; https://doi.org/10.1038/s41597-026-06628-2 .
'''
    (PUBLIC / 'README.md').write_text(guide)
    source_hashes = {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in sorted(SOURCE_FILES)}
    build_manifest = {'schema_version': 1, 'source_snapshot': manifest['accessed_date'],
                      'source_revision': manifest['snapshot_revision'], 'source_sha256': source_hashes,
                      'figures': len(figures), 'result_tables': len(downloads),
                      'source_workbooks_included': False, 'figure_versions_labelled': True,
                      'builder': 'scripts/build_analyses.py'}
    (PUBLIC / 'build-manifest.json').write_text(json.dumps(build_manifest, indent=2) + '\n')
    bundle = PUBLIC / 'cposs_figures_and_statistics.zip'
    include = {ROOT / item['path'] for item in downloads} | {PUBLIC / 'summary.json', PUBLIC / 'build-manifest.json', PUBLIC / 'README.md'}
    for f in figures:
        for key in ['image', 'pdf', 'caption']:
            if f[key]:
                include.add(ROOT / f[key])
    with zipfile.ZipFile(bundle, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(include):
            info = zipfile.ZipInfo(str(path.relative_to(ROOT)), date_time=(2026, 10, 24, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())
    print(json.dumps({'page': 'analyses.html', 'figures': len(figures), 'result_tables': len(downloads),
                      'documented_searches': len(datasets), 'page_bytes': len(html.encode()),
                      'download_bundle_bytes': bundle.stat().st_size}, indent=2))


if __name__ == '__main__':
    main()
