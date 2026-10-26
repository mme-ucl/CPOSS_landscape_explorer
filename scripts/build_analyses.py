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
from urllib.parse import quote
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / 'data/analyses'
DB = 'analysis/database_in_numbers'
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


def truth(value):
    return str(value).lower() == 'true'


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
    definitions = [
        ('chemical-content', 'CPOSS and OMC25: chemical content', 'comparison', 'Current', CMP, 'cposs_omc25_comparison', 'caption.tex',
         'Elemental prevalence, molecular atom counts and molar-mass distributions for 190 verified single-component CPOSS systems and 44,403 OMC25 training molecular records. Every molecular record receives equal weight.', 'chemical--summary_statistics.csv', ''),
        ('density', 'Crystal densities: CPOSS, OMC25 and CSD', 'comparison', 'Current', CMP, 'cposs_omc25_csd_density_comparison', 'density/caption.tex',
         'Archive-linked CPOSS density records compared with histogram references recovered from the OMC25 paper. The shared 0.8–2.4 g/cm³ window and a system-weighted sensitivity curve make the counting basis explicit.', 'density--density_statistics.csv', ''),
        ('molecular-map', 'Molecular diversity in CPOSS', 'map', 'Current', MAP, 'cposs_molecular_sketchmap', 'caption.md',
         'A molecular SOAP sketch-map of 308 documented searches. Marker area scales with the square root of archived-file count; colour shows representative-component molar mass. Multicomponent systems use their largest non-water component.', 'map--dataset_embedding.csv', ''),
        ('multicomponent', 'Multicomponent formula units', 'comparison', 'Supplementary', CMP, 'cposs_omc25_multicomponent', 'caption_supplementary.tex',
         'The 44 verified salts, hydrates, solvates and co-crystals are shown separately from the single-component comparison. Atom counts and masses retain all components and stoichiometry of each formula unit.', 'chemical--cposs_multicomponent_formula_units.csv', ''),
        ('software', 'Reported CSP software', 'overview', 'Supporting figure', DB, 'panel_c_software_proposal', '',
         'Explicit program mentions across 311 searches: each search counts once per program family. Versions are pooled and program categories overlap. This is the software panel adopted for the wide overview.', 'audit--proposed_panel_c_counts.csv', ''),
        ('map-diagnostics', 'Sketch-map diagnostics', 'map', 'Supporting figure', MAP, 'sketchmap_diagnostics', '',
         'Distance preservation, local-neighbour retention, optimization and sensitivity diagnostics for the molecular embedding. The full run and stability statistics are available as CSV tables.', 'map--optimization_runs.csv', ''),
        ('overview-wide', 'Database in numbers: wide overview', 'overview', 'Earlier export', DB, 'database_in_numbers_3x2', 'caption_3x2.tex',
         'The six-panel overview of molecular size, archived structures, reported software, scientist credits, study dates and linked literature, arranged in three columns and two rows.', 'database--annual_counts.csv',
         'Its molecular panel predates the reconciled formula audit. Use the current chemistry statistics and comparison above for composition and component counts.'),
        ('overview-portrait', 'Database in numbers: portrait overview', 'overview', 'Earlier export', DB, 'database_in_numbers', 'caption.md',
         'The original portrait arrangement of the database overview. Retained alongside the wide version so figures from the earlier analysis remain accessible.', 'database--structure_count_ranking.csv',
         'This export uses earlier formula metadata and a molecular-method panel. The reconciled chemistry and reported-software results are presented separately on this page.'),
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
    'summary_statistics': 'Molecular-size and mass summary statistics', 'elemental_prevalence': 'Elemental occurrence by molecular record',
    'atomic_fractions': 'Pooled atomic fractions by species', 'annual_counts': 'Annual searches and archived structure counts',
    'contributors': 'All named scientist credits', 'cumulative_papers': 'Cumulative linked CSP papers',
    'structure_count_ranking': 'Searches ranked by archived structure count', 'proposed_panel_c_counts': 'Reported CSP software counts',
    'dataset_embedding': 'Molecular sketch-map coordinates and representatives', 'optimization_runs': 'Sketch-map optimization and sensitivity runs',
    'density_statistics': 'Density statistics and histogram-reference status', 'density_binned_overlap': 'Binned density-distribution overlap',
    'cposs_density_window_coverage': 'CPOSS density coverage and excluded tails', 'density_histograms_common_bins': 'Density histograms on shared bins',
    'cposs_density_ecdfs': 'CPOSS density cumulative distributions', 'cposs_molecular_systems_audit': 'Reconciled molecular systems and inclusion audit',
    'cposs_formula_conflict_resolutions': 'Composition-conflict resolutions', 'cposs_primary_molecules': 'Verified single-component CPOSS molecules',
    'cposs_multicomponent_formula_units': 'Verified multicomponent CPOSS formula units', 'cposs_metadata_only_sensitivity': 'Formula-only sensitivity population',
    'omc25_train_molecules': 'OMC25 training molecular records', 'omc25_split_validation': 'OMC25 split counts and validation',
    'ecdf_coordinates': 'Exact molecular-size and mass ECDF coordinates', 'outside_omc25_ranges': 'CPOSS coverage of OMC25 size and mass ranges',
    'method_frequencies': 'Reported potential families and molecular methods', 'callouts': 'Molecular illustrations and compound references',
    'initialization_stability': 'Embedding stability across initializations', 'exclusions': 'Excluded molecular-map datasets',
    'source_issues': 'Molecular reconstruction source issues', 'molecular_formula_comparison': 'Formula crosscheck before reconciliation',
    'model_count_comparison': 'Curation and archive count comparison', 'molecular_distances': 'Pairwise molecular SOAP distances',
}
GROUPS = [('database', 'Dataset overview', DB + '/tables'),
          ('audit', 'Source audit', DB + '/workbook_crosscheck'),
          ('map', 'Molecular map', MAP + '/tables'),
          ('chemical', 'Chemical comparison', CMP + '/tables'),
          ('density', 'Density comparison', DENS + '/tables')]
PRIORITY = ['chemical--summary_statistics', 'chemical--elemental_prevalence', 'density--density_statistics',
            'database--annual_counts', 'audit--proposed_panel_c_counts', 'map--dataset_embedding',
            'chemical--cposs_molecular_systems_audit', 'database--contributors', 'database--structure_count_ranking',
            'database--cumulative_papers', 'density--cposs_density_window_coverage', 'map--optimization_runs']


def public_cell(value):
    if '/Users/' in value or '/private/tmp/' in value or '/tmp/' in value:
        # Only local provenance/error fields use these strings; no scientific number is changed.
        return 'Local source location omitted; scientific provenance is described on the analyses page.'
    return value


def export_tables():
    downloads = []
    for namespace, group, directory in GROUPS:
        for path in sorted((ROOT / directory).glob('*.csv')):
            relative = str(path.relative_to(ROOT))
            rows = read_csv(relative)
            with path.open(newline='') as stream:
                fields = csv.DictReader(stream).fieldnames
            key = namespace + '--' + path.stem
            filename = key + '.csv'
            output = io.StringIO(newline='')
            writer = csv.DictWriter(output, fieldnames=fields)
            writer.writeheader()
            writer.writerows({k: public_cell(v or '') for k, v in row.items()} for row in rows)
            raw = output.getvalue().encode()
            (PUBLIC / filename).write_bytes(raw)
            label = LABELS.get(path.stem, path.stem.replace('_', ' ').capitalize())
            downloads.append({'id': key, 'title': label, 'group': group, 'namespace': namespace,
                              'path': 'data/analyses/' + filename, 'rows': len(rows), 'bytes': len(raw),
                              'sha256': hashlib.sha256(raw).hexdigest(), 'source': relative})
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
        status_class = 'status earlier' if f['status'] == 'Earlier export' else 'status'
        cards.append(f'''<article class="figure-card" id="figure-{f['id']}" data-category="{f['category']}" data-earlier="{str(f['status'] == 'Earlier export').lower()}">
<a class="figure-preview" href="{e(f['image'])}" data-expand="{f['id']}" aria-label="Expand {e(f['title'])}"><img src="{e(f['image'])}" alt="{e(f['description'])}" loading="lazy" decoding="async"></a>
<div class="figure-body"><div class="figure-meta"><span>{e(f['category'].replace('map', 'Molecular map'))}</span><span class="{status_class}">{e(f['status'])}</span></div>
<h3>{e(f['title'])}</h3><p>{e(f['description'])}</p>{note}<div class="figure-links">{links}</div></div></article>''')
    return '\n'.join(cards)


def stats_table(rows, density=False):
    populations = {'CPOSS_single_verified': 'CPOSS: verified single-component', 'OMC25_train': 'OMC25: training molecules',
                   'CPOSS_multicomponent_formula_units': 'CPOSS: multicomponent formula units',
                   'CPOSS_single_metadata_sensitivity': 'CPOSS: formula-only sensitivity'}
    variables = {'atom_count': 'All atoms', 'heavy_atom_count': 'Non-H atoms', 'molar_mass_g_mol': 'Mass (g/mol)',
                 'reported_molar_mass_g_mol': 'Source-reported mass (g/mol)'}
    data = [[populations[r['population']], variables[r['variable']], number(r['n'])] +
            [number(r[k], 2) for k in ['minimum', 'q1', 'median', 'q3', 'maximum', 'mean']] for r in rows]
    return table(['Population', 'Variable', 'N', 'Min', 'Q1', 'Median', 'Q3', 'Max', 'Mean'], data, 'Complete molecular summary statistics')


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
    programs = read_csv(DB + '/workbook_crosscheck/proposed_panel_c_counts.csv')
    methods = read_csv(DB + '/tables/method_frequencies.csv')
    density = read_csv(DENS + '/tables/density_statistics.csv')
    density_coverage = read_csv(DENS + '/tables/cposs_density_window_coverage.csv')
    density_overlap = read_csv(DENS + '/tables/density_binned_overlap.csv')
    callouts = read_csv(MAP + '/tables/callouts.csv')
    catalogue = read_json('data/catalogue.json')
    files = [int(float(r['structure_count'])) for r in datasets]
    q1, _, q3 = statistics.quantiles(files, n=4, method='inclusive')
    credited = len({r['dataset_id'] for r in contributor_links})
    figures = figure_inventory()
    for figure in figures:
        SOURCE_FILES.update(figure[key] for key in ['image', 'pdf', 'caption'] if figure[key])
    SOURCE_FILES.update(f'{MAP}/figures/callouts_ao/{row["dataset_id"]}.png' for row in callouts)
    downloads = export_tables()
    counts = manifest['figure_structure_counts']
    assert len(datasets) == 311 and len(chemical) == 235 and sum(files) == 519167
    by_page = {row['source_url']: row for row in chemical}
    single = [r for r in chemical if r['component_basis'] == 'single_molecule']
    multi = [r for r in chemical if r['component_basis'] == 'formula_unit']
    catalogue_by_id = {r['id']: r for r in catalogue['datasets']}
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
               'density': density_validation, 'map': {k: sketch[k] for k in ['datasets_included', 'represented_structure_files', 'metrics']},
               'figures': figures, 'downloads': downloads, 'source_status': 'computed from frozen analysis outputs; OMC25/CSD density reference recovered approximately from a histogram'}
    summary_json = json.dumps(summary, indent=2, ensure_ascii=False) + '\n'
    (PUBLIC / 'summary.json').write_text(summary_json)

    def metric(value, label):
        return f'<div class="stat"><strong>{number(value)}</strong><span>{e(label)}</span></div>'

    metrics = ''.join(metric(value, label) for value, label in [
        (summary['archived_structure_files'], 'archived structure files'), (235, 'molecular systems'),
        (311, 'documented CSP searches'), (509, 'energy-model archives'), (75, 'linked CSP papers'), (45, 'named scientists')])
    scope_rows = [['Archived RES coordinate files', number(sum(files)), 'All 509 documented model archives; models counted separately'],
                  ['Linked visualization entries', number(counts['visualization_entries']), 'Available Chemiscope exports; can be subsets'],
                  ['Archive coverage', '311 / 311 searches', 'Complete file counts for every documented search'],
                  ['Single-component systems', '191 metadata / 190 verified', 'Tetrachlorobenzene remains formula-only'],
                  ['Multicomponent systems', '44 / 44 verified', 'Complete salts, co-crystals, hydrates and solvates'],
                  ['Dated searches', f'{summary["dated_searches"]} / 311', 'Single unambiguous study year; release years unavailable'],
                  ['Named credits', f'{credited} / 311 searches', f'{len(contributors)} scientists; credits can overlap'],
                  ['Searches with a linked CSP paper', f'{linked_papers} / 311', 'A missing link does not establish that no paper exists']]
    method_tables = ''.join(f'<details class="table-details"><summary>{title}</summary>{table(["Category", "Searches"], [[r["category"], int(r["datasets"])] for r in methods if r["kind"] == kind])}<p class="source-note">Categories overlap; each search counts at most once per category.</p></details>' for kind, title in [('potential_family', 'Reported intermolecular potential families'), ('electronic_method', 'Reported molecular electronic-structure methods')])
    cp_stats = {r['variable']: r for r in molecular if r['population'] == 'CPOSS_single_verified'}
    omc_stats = {r['variable']: r for r in molecular if r['population'] == 'OMC25_train'}
    comparison_rows = []
    for key, title, precision in [('atom_count', 'Atoms per molecule', 0), ('heavy_atom_count', 'Non-H atoms per molecule', 0), ('molar_mass_g_mol', 'Molar mass (g/mol)', 2)]:
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
    density_all_rows = [[r['population'].replace('_', ' '), r['scope'].replace('_', ' '), number(r['n_records']),
                         *[number(r[k], 3) for k in ['minimum_g_cm3', 'q1_g_cm3', 'median_g_cm3', 'q3_g_cm3', 'maximum_g_cm3', 'mean_g_cm3']]] for r in density]
    scientific_notes = [
        ('Structure files, searches and molecules', 'A search can contain multiple energy models, and a molecule page can describe multiple searches. The headline counts archived RES files with models retained separately. It is not a count of geometrically unique crystals or every structure originally generated.'),
        ('Reconciled chemical populations', 'The later formula audit reviewed eight composition conflicts and repaired two malformed oxygen symbols using curation and coordinate evidence. The verified comparison uses 190 single-component systems and keeps 44 complete multicomponent formula units separate. One further single-component system has formula metadata only.'),
        ('Molecular comparisons', 'Each CPOSS molecular-system source page and OMC25 CSD reference code is counted once. Repeated searches and crystal packings do not weight molecular statistics. Molar masses use the same average atomic weights; source-reported OMC25 masses are retained in a separate table.'),
        ('Density comparison', 'CPOSS contributes source-reported density records from a defined visualization subset. The OMC25 and CSD curves are approximate histogram recoveries from Figure 3a of the OMC25 paper. Different source bin widths are reconciled before normalization within 0.8–2.4 g/cm³; no raw CSD density records are inferred.'),
        ('Molecular map', 'The map represents one reconstructed molecular component per search, with equal search weights in the embedding. The largest non-water component is selected for multicomponent structures. Archived-file count affects marker area only and does not weight the SOAP descriptors or optimization.'),
        ('Dates, credits and reported methods', 'Chronology uses explicit study dates, not database deposition or release dates. Scientist credits and software categories overlap. Molecular electronic-structure labels do not establish that an entire crystal landscape was computed using periodic DFT.'),
        ('Catalogue scope', 'The Navigator indexes available JSON files, including unlinked or alternate exports. These analyses follow documented public searches, including searches with missing visualizations but intact coordinate archives. The catalogue and archive-analysis denominators therefore differ.'),
        ('Figure versions', 'Earlier database overview exports are retained for reference and labelled. Their composition panels predate the reconciled audit; current molecular statistics on this page use the later verified populations. Supporting diagnostics and individual molecular illustrations are distinguished from the main figures.'),
    ]
    dataset_rows = []
    for row in sorted(datasets, key=lambda r: -int(float(r['structure_count']))):
        compound = by_page[row['source_url']]
        item = catalogue_by_id.get(row['dataset_id'])
        url = './?load=' + quote(item['url'], safe='') if item else None
        action = f'<a href="{e(url)}">Open landscape ↗</a>' if url else '<span class="source-note">Visualization unavailable</span>'
        action += f'<br><a href="{e(row["source_url"])}" target="_blank" rel="noopener noreferrer">Molecule page ↗</a>'
        search = ' '.join([row['dataset_id'], row['dataset_name'], compound['molecular_system'], row['refcode'],
                           compound['formula'], row['scientist_names'], row['study_date_raw'],
                           ' '.join(item.get('aliases', [])) if item else ''])
        values = [f'{e(row["dataset_name"])}<span class="dataset-code">{e(row["dataset_id"])}</span>', e(compound['formula']),
                  number(row['energy_model_count']), number(row['structure_count']), e(row['scientist_names'] or 'Unspecified'),
                  e(row['study_date_raw'] or 'Unspecified'), action]
        attrs = f'data-search="{e(search)}" data-name="{e(row["dataset_name"])}" data-files="{int(float(row["structure_count"]))}" data-models="{int(float(row["energy_model_count"]))}"'
        dataset_rows.append(f'<tr {attrs}>' + ''.join(f'<td>{v}</td>' for v in values) + '</tr>')
    download_rows = ''.join(f'<div class="download" data-download data-group="{e(d["group"])}" data-search="{e(d["title"] + " " + d["group"] + " " + d["id"])}"><div><a href="{e(d["path"])}" download>{e(d["title"])} ↓</a><small>{e(d["group"])}</small></div><span class="file-meta">CSV · {number(d["rows"])} rows</span></div>' for d in downloads)
    options = ''.join(f'<option value="{e(group)}">{e(group)}</option>' for _, group, _ in GROUPS)
    illustrations = ''.join(f'<a class="molecule" href="{MAP}/figures/callouts_ao/{e(r["dataset_id"])}.png" target="_blank" rel="noopener noreferrer"><img src="{MAP}/figures/callouts_ao/{e(r["dataset_id"])}.png" alt="Dataset representative of {e(r["dataset_name"])}" loading="lazy" decoding="async"><span>{e(r["dataset_name"])}</span></a>' for r in callouts)
    contributors_table = table(['Named scientist', 'Credited searches'], [[r['scientist_name'], int(r['dataset_count'])] for r in contributors])
    chronology_table = table(['Study year', 'Searches', 'Archived files', 'Cumulative searches'], [[r['year'], int(r['landscapes']), int(r['archive_structure_files']), int(r['cumulative_datasets'])] for r in annual])
    publication_table = table(['Publication year', 'New linked CSP papers', 'Cumulative CSP papers'], [[r['year'], int(r['new_unique_papers']), int(r['cumulative_unique_papers'])] for r in papers])
    method_html = ''.join(f'<article><h3>{e(title)}</h3><p>{e(body)}</p></article>' for title, body in scientific_notes)
    figure_data_json = json.dumps({'figures': figures}, ensure_ascii=False).replace('<', '\\u003c').replace('&', '\\u0026')
    html = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="CPOSS dataset figures, archived structure statistics, molecular diversity, and comparisons with OMC25 and the Cambridge Structural Database.">
<title>Analyses &amp; statistics · CPOSS Landscape Navigator</title>
<link rel="stylesheet" href="assets/analyses.css"><script src="assets/analyses.js" defer></script></head><body>
<a class="skip" href="#main">Skip to analyses</a>
<header class="topbar"><div class="topbar-inner"><a class="brand nav-return" href="./">CPOSS<span>Landscape Navigator</span></a><nav class="toplinks" aria-label="Site navigation"><a href="https://louiseprice.github.io/CPOSS_Database/index.html">CPOSS database ↗</a><a class="nav-return" href="./">← Explore landscapes</a></nav></div></header>
<div class="hero"><div class="wrap"><p class="eyebrow">The CPOSS dataset</p><h1>Analyses &amp; comparisons</h1><p class="intro">The figures, statistics and source data behind the landscapes. Explore molecular diversity, the scope of the archive, and comparisons with OMC25 and the Cambridge Structural Database.</p>
<div class="snapshot"><span>Source snapshot · {date.fromisoformat(manifest['accessed_date']).strftime('%d %B %Y')}</span><span>Revision <code>{manifest['snapshot_revision'][:12]}</code></span><a href="#methods">Counting rules &amp; provenance ↓</a></div><div class="stats">{metrics}</div>
<details class="scope"><summary>What is counted? Why does the Navigator catalogue show {len(catalogue['datasets'])} files?</summary><p>These analyses follow <strong>311 documented searches on 235 molecular-system pages</strong>. The Navigator catalogue contains {len(catalogue['datasets'])} available JSON files, including eight unlinked or alternate exports; four documented searches have no available visualization but retain intact archives. The 519,167-file total counts model-specific RES records, with no geometric deduplication.</p></details></div></div>
<nav class="jump-nav" aria-label="Analysis sections"><div class="wrap"><a href="#figures">All figures</a><a href="#dataset-statistics">Dataset statistics</a><a href="#chemical-comparison">OMC25 comparison</a><a href="#density-comparison">Crystal densities</a><a href="#molecular-map">Molecular map</a><a href="#searches">Search inventory</a><a href="#data-methods">Data &amp; methods</a></div></nav>
<main id="main" class="wrap">
<section id="figures" aria-labelledby="figures-title"><div class="section-head"><div><h2 id="figures-title">The figure collection</h2><p>Expand a figure to inspect it, or download the original image, vector PDF, caption and underlying tables. Earlier exports retain their original scope.</p></div><span class="count">{len(figures)} analysis figures</span></div>
<div class="filters" role="group" aria-label="Filter figures"><button class="chip" data-figure-filter="all" aria-pressed="true">All figures</button><button class="chip" data-figure-filter="comparison" aria-pressed="false">Comparisons</button><button class="chip" data-figure-filter="map" aria-pressed="false">Molecular map</button><button class="chip" data-figure-filter="overview" aria-pressed="false">Dataset overview</button><button class="chip" data-figure-filter="earlier" aria-pressed="false">Earlier exports</button></div>
<p id="figure-count" class="results-status" aria-live="polite"></p><div class="figure-grid">{figure_cards(figures)}</div></section>
<section id="dataset-statistics" aria-labelledby="statistics-title"><div class="section-head"><div><h2 id="statistics-title">The dataset in numbers</h2><p>Archive totals, source coverage, study history and the people and methods named in the database.</p></div><a class="detail-link" href="data/analyses/summary.json" download>Summary JSON ↓</a></div>
<div class="two-up"><article class="panel"><h3>Archive size and coverage</h3><div class="metric-strip"><div><strong>{number(statistics.median(files))}</strong><span>median files per search</span></div><div><strong>{number(min(files))}–{number(max(files))}</strong><span>range per search</span></div></div><p>The middle half of searches contain {number(q1, 1)}–{number(q3, 1)} archived files. All 311 searches have complete archive counts.</p>{table(['Measurement', 'Available', 'Definition'], scope_rows)}<p class="source-note">Visualization entries, spreadsheet rows and archive files describe overlapping scopes and are not added together.</p></article>
<article class="panel"><h3>Study history</h3>{svg_years(annual)}<div class="metric-strip"><div><strong>{summary['dated_searches']}</strong><span>searches with a single study year</span></div><div><strong>{summary['undated_or_ambiguous_searches']}</strong><span>ambiguous or interval dates</span></div></div><p>The dated searches contain {number(counts['annual_structure_files'])} archived files; {number(counts['unassigned_year_structure_files'])} files fall outside the dated series. Study dates do not measure database release or deposition.</p><details class="table-details"><summary>Annual searches and structure-file totals</summary>{chronology_table}</details><details class="table-details"><summary>Linked CSP papers by publication year</summary>{publication_table}</details></article></div>
<div class="two-up"><article class="panel"><h3>Reported CSP software</h3>{bar_list(programs, 'program', 'datasets')}<p>Each search counts at most once per program family. Versions are pooled; categories overlap. Only explicit software mentions are counted.</p><a class="detail-link" href="data/analyses/audit--proposed_panel_c_counts.csv" download>Download software counts ↓</a>{method_tables}<p class="source-note">Molecular electronic-structure labels are not counts of periodic-DFT crystal landscapes.</p></article>
<article class="panel"><h3>Named scientists and linked literature</h3>{bar_list(contributors, 'scientist_name', 'dataset_count', 8)}<p>{credited} searches name at least one scientist. Credits overlap and follow the source Scientist field; paper authorship is recorded separately.</p><details class="table-details"><summary>All {len(contributors)} named scientists</summary>{contributors_table}</details><div class="metric-strip"><div><strong>{summary['linked_csp_papers']}</strong><span>unique linked CSP papers</span></div><div><strong>{number(summary['all_linked_references'])}</strong><span>linked references overall</span></div></div><p>{linked_papers} searches link a qualifying CSP paper. References are deduplicated by DOI or canonical URL; experimental-context references are recorded separately.</p></article></div></section>
<section id="chemical-comparison" aria-labelledby="chemical-title"><div class="section-head"><div><h2 id="chemical-title">Chemical coverage relative to OMC25</h2><p>Equal weight per documented molecular record: 190 verified single-component CPOSS systems and 44,403 OMC25 training molecular records.</p></div><a class="detail-link" href="#figure-chemical-content">View figure ↑</a></div>
<div class="two-up"><article class="panel"><h3>Molecular size and molar mass</h3>{table(['Variable', 'CPOSS median (range)', 'OMC25 median (range)'], comparison_rows)}<p>The observed CPOSS single-component size and mass ranges lie within OMC25’s ranges. Range overlap does not establish matching chemical environments or crystal packings.</p><div class="population-note"><p>The other 44 verified CPOSS systems are complete multicomponent formula units. They retain coformers, counterions and water; their masses are not single-molecule masses. One additional single-component system remains in the formula-only sensitivity population.</p></div><p class="source-note">Molar masses use one frozen average-atomic-weight convention. Original OMC25 masses are retained; harmonization changes a training mass by at most 0.032 g/mol.</p></article>
<article class="panel"><h3>Elemental occurrence</h3>{table(['Element', 'CPOSS: percentage (count/N)', 'OMC25: percentage (count/N)'], element_rows)}<p class="source-note">A record contributes once to every element it contains. These overlapping percentages do not sum to 100%. Pooled atomic fractions are available as a separate CSV. Cu occurs in CPOSS and is outside the OMC25 elemental vocabulary.</p></article></div>
<details class="table-details"><summary>All molecular populations, quartiles, means and source-mass statistics</summary>{stats_table(molecular)}<p class="source-note">Quartiles use linear interpolation. The formula-only sensitivity population includes tetrachlorobenzene; the principal comparison excludes it because no valid coordinate element table was available.</p></details></section>
<section id="density-comparison" aria-labelledby="density-title"><div class="section-head"><div><h2 id="density-title">Crystal-density distributions</h2><p>CPOSS source-reported densities compared with the last-frame OMC25 and organic CSD references from Figure 3a of the OMC25 paper.</p></div><a class="detail-link" href="#figure-density">View figure ↑</a></div>
<div class="two-up"><article class="panel"><h3>Shared interval: 0.8–2.4 g/cm³</h3>{table(['Population', 'Median', 'Q1', 'Q3', 'Mean'], density_rows)}<p class="source-note">All values are in g/cm³ and conditional on the shared interval. OMC25 and CSD values are approximate histogram recoveries, not statistics calculated from raw crystal records.</p></article>
<article class="panel"><h3>Density coverage and weighting</h3><div class="metric-strip"><div><strong>{number(density_validation['primary_records'])}</strong><span>available source density records</span></div><div><strong>{density_validation['primary_systems']}</strong><span>single-component systems</span></div></div><p>{number(cov['records_in_window'])} records from {density_validation['primary_searches']} searches lie in the comparison window. {number(cov['outside_window_percent'], 2)}% lie outside it and remain in the data tables.</p><p>Each search contributes one archive-linked density column. The dashed curve gives each molecular system equal total weight, with equal weights for its searches. This tests sensitivity to the different numbers of stored candidates in each landscape.</p><p class="source-note">This visualization subset is not a density census of all 519,167 archived files. Density agreement does not establish equal chemical, packing or stability coverage.</p></article></div>
<details class="table-details"><summary>All available and shared-window density statistics, including multicomponent systems</summary>{table(['Population', 'Scope', 'Records', 'Min', 'Q1', 'Median', 'Q3', 'Max', 'Mean'], density_all_rows)}<p class="source-note">Very low positive source values are retained without automatic repair. Blank reference counts and extremes are unavailable, not zero. Reference quantiles assume uniform probability within recovered histogram bins.</p></details></section>
<section id="molecular-map" aria-labelledby="map-title"><div class="section-head"><div><h2 id="map-title">Mapping molecular diversity</h2><p>One reconstructed molecular representative per search, compared through local atomic environments using SOAP descriptors and sketch-map.</p></div><a class="detail-link" href="#figure-molecular-map">View map &amp; diagnostics ↑</a></div>
<div class="three-up"><article class="panel"><h3>Coverage</h3><div class="metric-strip"><div><strong>308 / 311</strong><span>searches represented</span></div></div><p>{number(sketch['represented_structure_files'])} of {number(sum(files))} archived files are represented. Three searches covering 163 files are excluded because their source element tables are contradictory.</p></article><article class="panel"><h3>Embedding quality</h3><div class="metric-strip"><div><strong>{sketch['metrics']['distance_spearman']:.3f}</strong><span>pair-distance Spearman correlation</span></div><div><strong>{sketch['metrics']['trustworthiness_k10']:.3f}</strong><span>trustworthiness at 10 neighbours</span></div></div><p>Neighbour retention is {100*sketch['metrics']['neighbor_retention_k10']:.1f}%. Five initializations and two switching-distance sensitivity checks are supplied.</p></article><article class="panel"><h3>What the map represents</h3><p>Composition and local molecular geometry, using equal search weights. The largest non-water component represents a multicomponent system. Marker area scales as the square root of archived-file count.</p><p>Crystal packing, complete coformer stoichiometry and enantiomer separation are outside this representation.</p></article></div>
<details class="table-details"><summary>Eight molecular illustrations used in the map</summary><p class="source-note">These are the selected dataset representatives. Experimental references establish the compounds; the displayed geometries are not asserted experimental conformers.</p><div class="molecule-grid">{illustrations}</div></details></section>
<section id="searches" aria-labelledby="searches-title"><div class="section-head"><div><h2 id="searches-title">Explore the search inventory</h2><p>Inspect all 311 documented searches, their reconciled formulas, archive counts, credits and study dates. Open an available landscape directly in the Navigator.</p></div></div>
<div class="search-tools"><label>Search inventory<input id="search-inventory" type="search" placeholder="Molecule, formula, scientist, REFCODE or search code"></label><label class="narrow">Sort by<select id="inventory-sort"><option value="files-desc">Most archived files</option><option value="files-asc">Fewest archived files</option><option value="name-asc">Molecule A–Z</option><option value="models-desc">Most energy models</option></select></label></div><p id="inventory-count" class="results-status" aria-live="polite">311 documented searches</p>
<div class="scroll-table"><table class="mini-table search-table" id="inventory-table"><caption class="sr-only">Documented CPOSS search inventory</caption><thead><tr><th scope="col">Molecule / search</th><th scope="col">Reconciled formula</th><th scope="col">Models</th><th scope="col">Archived files</th><th scope="col">Named scientists</th><th scope="col">Study date</th><th scope="col">Explore</th></tr></thead><tbody>{''.join(dataset_rows)}</tbody></table></div>
<div class="pagination" id="inventory-pagination" hidden><span id="inventory-page"></span><div><button type="button" id="inventory-previous">← Previous</button><button type="button" id="inventory-next">Next →</button></div></div><p id="inventory-empty" class="empty" hidden>No searches match. Try a molecule name, code or scientist.</p></section>
<section id="data-methods" aria-labelledby="data-title"><div class="section-head"><div><h2 id="data-title">Data &amp; methods</h2><p>Download the complete result tables or select a particular analysis. Every table retains its counting unit and source scope.</p></div><a class="detail-link" href="data/analyses/cposs_figures_and_statistics.zip" download>All figures &amp; tables · ZIP ↓</a></div>
<div class="search-tools"><label>Find a result table<input id="download-search" type="search" placeholder="Density, molecular mass, contributors, archive counts…"></label><label class="narrow">Analysis<select id="download-group"><option value="">All analyses</option>{options}</select></label></div><p id="download-count" class="results-status" aria-live="polite">{len(downloads)} result tables</p><div class="downloads-list">{download_rows}</div><button id="downloads-more" type="button" class="chip" hidden>Show all tables</button><p id="downloads-empty" class="empty" hidden>No result tables match this search.</p>
<div id="methods" class="section-head" style="margin-top:42px"><div><h2>Counting rules &amp; provenance</h2><p>Definitions that matter when reading or reusing these results.</p></div></div><div class="methods-list">{method_html}</div>
<p class="source-note">Sources: <a href="https://louiseprice.github.io/CPOSS_Database/index.html">CPOSS database</a> · <a href="https://huggingface.co/datasets/facebook/OMC25">official OMC25 metadata</a> · <a href="https://doi.org/10.1038/s41597-026-06628-2">OMC25 paper</a>. Source snapshot {manifest['accessed_date']}; source revision {manifest['snapshot_revision'][:12]}. Download the <a href="data/analyses/build-manifest.json" download>page source manifest</a> or <a href="data/analyses/README.md" download>data guide</a>.</p></section>
</main><footer class="footer"><div class="wrap"><span>CPOSS · Dataset analyses &amp; comparisons</span><a class="nav-return" href="./">Return to the Landscape Navigator ↑</a><span>Source snapshot · October 2026</span></div></footer>
<dialog id="figure-dialog" aria-labelledby="dialog-title"><div class="dialog-header"><h2 id="dialog-title"></h2><button id="dialog-close" type="button" aria-label="Close figure">Close ×</button></div><img class="dialog-image" id="dialog-image" alt=""><div class="dialog-footer"><span id="dialog-description"></span><a id="dialog-original" target="_blank" rel="noopener noreferrer">Full-resolution image ↗</a><a id="dialog-pdf" download>Vector PDF ↓</a></div></dialog>
<script type="application/json" id="analysis-data">{figure_data_json}</script>
</body></html>'''
    (ROOT / 'analyses.html').write_text(html)
    guide = f'''# CPOSS figures and statistics

Source snapshot: {manifest['accessed_date']}. Revision: {manifest['snapshot_revision']}.

The page reports 311 documented searches across 235 molecular systems, 519,167 model-specific archived RES files, and 509 model archives. It does not claim geometric uniqueness. The Navigator's catalogue of available JSON exports has a different scope.

The corrected chemical comparison contains 190 coordinate-verified single-component systems, 44 verified complete multicomponent formula units, and a separate 191-system metadata-only sensitivity population. OMC25 uses 44,403 training molecular identifiers.

Density statistics use 114,222 archive-linked CPOSS visualization records from 186 systems. The OMC25 and organic CSD references are approximate recoveries from paper Figure 3a. Comparisons are conditional on 0.8–2.4 g/cm³, with common 0.02-wide bins. Atomic fractions and molecular elemental prevalence are separate measurements.

The molecular map contains 308 of 311 searches. Its multicomponent representatives are the largest non-water components, not complete formula units. Earlier database overview exports are labelled because their chemical panels predate formula reconciliation.

Files: summary.json contains aggregate statistics and the figure/table catalogue; build-manifest.json records source-table checksums. CSVs retain complete result tables. The ZIP includes the scientific figures, captions and these tables. The source workbooks and large source caches are not included.

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
    for row in callouts:
        include.add(ROOT / MAP / 'figures/callouts_ao' / (row['dataset_id'] + '.png'))
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
