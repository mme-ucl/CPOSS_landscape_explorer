"""Freeze the official metadata and existing CPOSS evidence without editing sources."""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
from urllib.request import urlopen

BASE = Path(__file__).resolve().parent
REPO = BASE.parents[1]
EXPECTED_OMC_SHA = 'afd58adbbc5fba225def6903af9fd41b374282259512bafe5102a5c53f9d3832'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def freeze(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if sha(source) != sha(target):
            raise ValueError(f'Frozen input differs: {target}. Review before replacing it.')
    else:
        shutil.copyfile(source, target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--metadata', type=Path)
    parser.add_argument('--repository-info', type=Path)
    parser.add_argument('--workbook', type=Path, default=Path('/Users/matteo/Downloads/Database 2023 checkup.xlsx'))
    args = parser.parse_args()
    dest = BASE / 'inputs'
    dest.mkdir(exist_ok=True)
    info_path = dest / 'omc25_repository_info.json'
    if args.repository_info:
        freeze(args.repository_info, info_path)
    elif not info_path.exists():
        with urlopen('https://huggingface.co/api/datasets/facebook/OMC25') as response:
            info_path.write_bytes(response.read())
    revision = json.loads(info_path.read_text())['sha']
    url = f'https://huggingface.co/datasets/facebook/OMC25/resolve/{revision}/omc25-starting-crystals.csv'
    metadata = dest / 'omc25-starting-crystals.csv'
    if args.metadata:
        freeze(args.metadata, metadata)
    elif not metadata.exists():
        with urlopen(url) as response:
            metadata.write_bytes(response.read())
    assert sha(metadata) == EXPECTED_OMC_SHA, 'OMC25 checksum differs from the reviewed official file'

    sources = {
        'cposs_molecular_systems.csv': REPO / 'analysis/database_in_numbers/tables/molecular_systems.csv',
        'cposs_formula_audit.csv': REPO / 'analysis/database_in_numbers/workbook_crosscheck/molecular_formula_comparison.csv',
        'cposs_formula_audit_report.md': REPO / 'analysis/database_in_numbers/workbook_crosscheck/report.md',
        'cposs_manifest.json': REPO / 'analysis/database_in_numbers/manifest.json',
        'cposs_extraction.csv': REPO / 'analysis/molecular_sketchmap/tables/extraction.csv',
        'cposs_extraction_source_issues.csv': REPO / 'analysis/molecular_sketchmap/tables/source_issues.csv',
        'cposs_extraction_code.py': REPO / 'analysis/molecular_sketchmap/extract_molecules.py',
        'Database 2023 checkup.xlsx': args.workbook,
    }
    for name, path in sources.items():
        freeze(path, dest / name)

    # Preserve complete component counts, not just the selected largest component.
    evidence = []
    with (dest / 'cposs_extraction.csv').open() as stream:
        for row in csv.DictReader(stream):
            record_path = REPO / 'analysis/molecular_sketchmap/molecules' / (row['dataset_id'] + '.json')
            record = json.loads(record_path.read_text())
            keys = ['dataset_id', 'source_url', 'extraction_status', 'included', 'error',
                    'observed_multicomponent', 'component_counts_per_cell',
                    'component_identities_per_cell', 'selected_formula', 'selected_atoms',
                    'selected_heavy_atoms', 'selected_smiles', 'constitution_smiles',
                    'bond_assignment_status', 'selected_file_sha256', 'selected_filename',
                    'archive_url', 'archive_git_blob_sha', 'formula_validation',
                    'crystal_reconstruction']
            item = {key: record.get(key) for key in keys}
            item['evidence_json_sha256'] = sha(record_path)
            if record.get('included'):
                raw_path = REPO / 'analysis/molecular_sketchmap/selected_crystals' / (row['dataset_id'] + '.res')
                assert sha(raw_path) == record['selected_file_sha256']
                freeze(raw_path, dest / 'selected_crystals' / raw_path.name)
            evidence.append(item)
    evidence_file = dest / 'cposs_coordinate_evidence.json'
    text = json.dumps(evidence, indent=2, sort_keys=True) + '\n'
    if evidence_file.exists() and evidence_file.read_text() != text:
        raise ValueError('Frozen coordinate evidence differs')
    evidence_file.write_text(text)

    manifest_path = dest / 'manifest.json'
    manifest = {
        'accessed_utc': datetime.now(timezone.utc).isoformat(),
        'omc25_repository': 'https://huggingface.co/datasets/facebook/OMC25',
        'omc25_revision': revision,
        'omc25_metadata_url': url,
        'omc25_documentation_url': f'https://huggingface.co/datasets/facebook/OMC25/blob/{revision}/README.md',
        'omc25_metadata_official_sha256': EXPECTED_OMC_SHA,
        'omc25_licence': 'CC-BY-4.0',
        'cposs_input_sources': {name: str(path) for name, path in sources.items()},
        'files': {str(path.relative_to(dest)): sha(path) for path in sorted(dest.rglob('*'))
                  if path.is_file() and path != manifest_path and path.name != 'atomic_weights.json'},
    }
    if manifest_path.exists():
        old = json.loads(manifest_path.read_text())
        assert old['files'] == manifest['files'], 'Frozen input manifest has changed'
    else:
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'revision': revision, 'metadata_sha256': sha(metadata),
                      'coordinate_audits': len(evidence), 'frozen_files': len(manifest['files'])}, indent=2))


if __name__ == '__main__':
    main()
