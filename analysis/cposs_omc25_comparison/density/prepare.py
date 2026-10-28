"""Recover Fig. 3a vector bars and freeze source-reported CPOSS density records."""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import gzip
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import re
import shutil
from statistics import median
from urllib.parse import unquote, urlsplit
import zipfile

import pdfplumber

BASE = Path(__file__).resolve().parent
COMPARISON = BASE.parent
REPO = COMPARISON.parents[1]
SOURCE = REPO / 'analysis/database_in_numbers'
INPUTS = BASE / 'inputs'
COLOURS = {(0.502, 0.502, 0.502): 'CSD_organic',
           (0.8, 0.3804, 0.6902): 'OMC25_last_frames',
           (0.8549, 0.6471, 0.1059): 'OMC25_generated_first_frames',
           (0.1843, 0.5412, 0.7686): 'OMC25_rigid_press_first_frames'}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def git_sha(raw):
    return hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()


def read_csv(path):
    with path.open() as stream:
        return list(csv.DictReader(stream))


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def extract_reference(pdf):
    with pdfplumber.open(pdf) as document:
        page = document.pages[7]
        assert 'Density' in page.extract_text() and 'CSD' in page.extract_text()
        ticks = sorted(l['x0'] for l in page.lines if 649 < l['y0'] < 651 and
                       1 < l['y1'] - l['y0'] < 2 and l['x0'] > 110)
        assert len(ticks) == 9
        slope = (ticks[-1] - ticks[0]) / 1.6
        y_ticks = sorted(l['y0'] for l in page.lines if 96 < l['x0'] < 97 and
                         1 < l['x1'] - l['x0'] < 2 and 650 < l['y0'] < 730)
        assert len(y_ticks) == 4
        baseline = y_ticks[0]
        units = (y_ticks[-1] - baseline) / 15000
        rows, summaries = [], []
        for colour, population in COLOURS.items():
            bars = sorted([r for r in page.rects if r['non_stroking_color'] == colour and
                           abs(r['y0'] - baseline) < 1e-4 and r['y1'] > baseline], key=lambda r: r['x0'])
            centres = [(r['x0'] + r['x1']) / 2 for r in bars]
            spacings = sorted(b - a for a, b in zip(centres, centres[1:]) if b > a)
            step = median(spacings[:len(spacings) // 2 + 1]) / slope
            assert .005 < step < .025
            for rect, centre in zip(bars, centres):
                x = .8 + (centre - ticks[0]) / slope
                rows.append({'population': population, 'bin_centre_g_cm3': x,
                             'bin_left_g_cm3': x - step / 2, 'bin_right_g_cm3': x + step / 2,
                             'bin_width_g_cm3': step, 'recovered_count_height': (rect['y1'] - baseline) / units,
                             'pdf_x0': rect['x0'], 'pdf_x1': rect['x1'], 'pdf_y0': rect['y0'], 'pdf_y1': rect['y1'],
                             'status': 'approximate_vector_histogram_recovery_not_raw_crystal_data'})
            summaries.append({'population': population, 'bars_recovered': len(bars),
                              'inferred_histogram_bin_width_g_cm3': step,
                              'recovered_displayed_count_sum': sum(r['recovered_count_height'] for r in rows if r['population'] == population)})
        return rows, {'source_page_1_based': 8, 'source_figure': '3a',
                      'x_ticks_pdf_points': ticks, 'x_tick_density_values': [.8 + .2 * i for i in range(9)],
                      'y_ticks_pdf_points': y_ticks, 'y_tick_count_values': [0, 5000, 10000, 15000],
                      'colour_populations': summaries}


def norm_filename(value):
    return Path(str(value).replace('\\', '/')).stem.casefold()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--paper', type=Path, default=Path('/tmp/cposs-omc25-density-reference.pdf'))
    parser.add_argument('--json-cache', type=Path, default=Path('/tmp/cposs-numbers-json-cache'))
    parser.add_argument('--archive-cache', type=Path, default=Path('/tmp/cposs-model-archive-cache'))
    args = parser.parse_args()
    INPUTS.mkdir(parents=True, exist_ok=True)
    paper = INPUTS / 'omc25_arxiv_2508.02651v1.pdf'
    shutil.copyfile(args.paper, paper)
    bars, reference = extract_reference(paper)
    write_csv(INPUTS / 'reference_histogram_bars.csv', bars)
    (INPUTS / 'reference_calibration.json').write_text(json.dumps(reference, indent=2) + '\n')
    datasets = read_csv(SOURCE / 'tables/plot_datasets.csv')
    summaries = json.loads((SOURCE / 'sources/structure_summaries.json').read_text())
    archives = read_csv(SOURCE / 'tables/structure_archive_counts.csv')
    by_dataset = {}
    for archive in archives:
        by_dataset.setdefault(archive['dataset_id'], []).append(archive)
    chemical = {row['source_url']: row for row in read_csv(COMPARISON / 'tables/cposs_molecular_systems_audit.csv')}
    counts, records, selected_sources = [], [], []
    for dataset in datasets:
        path = unquote(urlsplit(dataset['json_url']).path).split('/CPOSS_Database/')[-1]
        info = summaries[path]
        if 'git_blob_sha' not in info:
            population = chemical[dataset['source_url']]
            counts.append({'dataset_id': dataset['dataset_id'], 'source_url': dataset['source_url'],
                           'molecular_system': population['molecular_system'],
                           'component_basis': population['component_basis'],
                           'coordinate_validated_system': population['coordinate_validated'],
                           'source_json_url': dataset['json_url'], 'source_rows': 0, 'included_rows': 0,
                           'status': 'excluded_source_visualization_missing_from_frozen_snapshot'})
            continue
        raw = (args.json_cache / (info['git_blob_sha'] + '.json')).read_bytes()
        assert git_sha(raw) == info['git_blob_sha'] and sha(raw) == info['sha256']
        data = json.loads(raw)
        properties = data.get('properties', {})
        names = next((prop['values'] for key, prop in properties.items() if key.casefold() == 'filename'), [])
        annotated = next((prop['values'] for key, prop in properties.items() if key.casefold() == 'experimental info'), [''] * len(names))
        selected, candidates = None, []
        for key, prop in properties.items():
            if not key.lower().startswith('density') or not key.endswith('/gcm-3'):
                continue
            match = re.search(r'\b(\d+)(?:[a-z])?\b', key.split('/')[0])
            model = int(match[1]) if match else 1
            candidates.append((model, key, prop['values']))
        for archive in sorted(by_dataset[dataset['dataset_id']], key=lambda r: int(r['model_id'])):
            matching = [candidate for candidate in candidates if candidate[0] == int(archive['model_id'])]
            if len(matching) == 1:
                selected = archive, matching[0]
                break
        audit = {'dataset_id': dataset['dataset_id'], 'source_url': dataset['source_url'],
                 'molecular_system': chemical[dataset['source_url']]['molecular_system'],
                 'component_basis': chemical[dataset['source_url']]['component_basis'],
                 'coordinate_validated_system': chemical[dataset['source_url']]['coordinate_validated'],
                 'source_json_url': dataset['json_url'], 'source_json_git_blob_sha': info['git_blob_sha'],
                 'source_json_sha256': info['sha256'], 'source_rows': len(names),
                 'density_column': '', 'model_id': '', 'archive_git_blob_sha': '', 'archive_url': '',
                 'included_rows': 0, 'missing_or_nonpositive_rows': 0,
                 'not_in_selected_archive_rows': 0, 'duplicate_rows': 0, 'status': ''}
        if selected is None:
            audit['status'] = 'excluded_no_unambiguous_density_column_with_g_cm3_units_and_archive'
            counts.append(audit)
            continue
        archive, (model, key, values) = selected
        raw_archive = (args.archive_cache / (archive['git_blob_sha'] + '.zip')).read_bytes()
        assert git_sha(raw_archive) == archive['git_blob_sha']
        with zipfile.ZipFile(args.archive_cache / (archive['git_blob_sha'] + '.zip')) as book:
            members = {norm_filename(member.filename) for member in book.infolist()
                       if member.filename.lower().endswith('.res') and '__MACOSX' not in Path(member.filename).parts
                       and not Path(member.filename).name.startswith('._')}
        assert len(values) == len(names) == len(data['structures'])
        audit.update({'density_column': key, 'model_id': model, 'archive_git_blob_sha': archive['git_blob_sha'],
                      'archive_url': archive['archive_url'], 'status': 'reported_density_column_archive_linked'})
        seen = {}
        for index, (filename, value) in enumerate(zip(names, values)):
            try:
                density = float(value)
            except (TypeError, ValueError):
                density = float('nan')
            if not 0 < density < float('inf'):
                audit['missing_or_nonpositive_rows'] += 1
                continue
            name = norm_filename(filename)
            if name not in members:
                audit['not_in_selected_archive_rows'] += 1
                continue
            if name in seen:
                assert abs(seen[name] - density) < 1e-5, 'Conflicting repeated filename densities'
                audit['duplicate_rows'] += 1
                continue
            seen[name] = density
            records.append({'dataset_id': dataset['dataset_id'], 'source_url': dataset['source_url'],
                            'molecular_system': audit['molecular_system'], 'component_basis': audit['component_basis'],
                            'coordinate_validated_system': audit['coordinate_validated_system'],
                            'model_id': model, 'density_column': key, 'source_json_index': index,
                            'filename': filename, 'density_g_cm3': density,
                            'has_experimental_annotation': bool(str(annotated[index]).strip()),
                            'value_status': 'source_reported_density_archive_filename_verified'})
            audit['included_rows'] += 1
        counts.append(audit)
        selected_sources.append({'dataset_id': dataset['dataset_id'], 'source_json_url': dataset['json_url'],
                                 'source_json_git_blob_sha': info['git_blob_sha'], 'source_json_sha256': sha(raw),
                                 'archive_url': archive['archive_url'], 'archive_git_blob_sha': archive['git_blob_sha'],
                                 'archive_sha256': sha(raw_archive)})
    output = INPUTS / 'cposs_reported_density_records.csv.gz'
    with output.open('wb') as raw_output:
        with gzip.GzipFile(filename='', mode='wb', fileobj=raw_output, mtime=0) as zipped:
            import io
            with io.TextIOWrapper(zipped, newline='') as stream:
                writer = csv.DictWriter(stream, fieldnames=list(records[0]))
                writer.writeheader()
                writer.writerows(records)
    write_csv(INPUTS / 'cposs_search_density_audit.csv', counts)
    write_csv(INPUTS / 'cposs_density_source_checksums.csv', selected_sources)
    for name, source in {'cposs_source_datasets.csv': SOURCE / 'tables/plot_datasets.csv',
                         'cposs_source_archive_manifest.csv': SOURCE / 'tables/structure_archive_counts.csv',
                         'cposs_molecular_population_audit.csv': COMPARISON / 'tables/cposs_molecular_systems_audit.csv'}.items():
        shutil.copyfile(source, INPUTS / name)
    manifest = {'accessed_utc': datetime.now(timezone.utc).isoformat(),
                'paper_url': 'https://arxiv.org/pdf/2508.02651v1',
                'paper_sha256': sha(paper.read_bytes()), 'source_figure': '3a',
                'cp_records': len(records), 'searches_with_density': sum(row['included_rows'] > 0 for row in counts),
                'cp_snapshot_revision': json.loads((SOURCE / 'manifest.json').read_text())['snapshot_revision'],
                'reader_version': {'pdfplumber': version('pdfplumber')},
                'source_rule': 'Lowest numbered archived model with one unambiguous density column labelled gcm-3; positive finite values; filename matched to its RES archive; one entry per filename per search',
                'files': {str(path.relative_to(INPUTS)): sha(path.read_bytes()) for path in sorted(INPUTS.iterdir())
                          if path.is_file() and path.name != 'manifest.json'}}
    (INPUTS / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (BASE / 'requirements.txt').write_text('pdfplumber==' + version('pdfplumber') + '\n')
    print(json.dumps({'cp_records': len(records), 'searches_with_density': manifest['searches_with_density'],
                      'paper_histograms': reference['colour_populations']}, indent=2))


if __name__ == '__main__':
    main()
