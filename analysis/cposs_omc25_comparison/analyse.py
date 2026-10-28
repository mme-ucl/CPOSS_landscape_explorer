"""Offline molecular comparison using frozen, checksum-verified source evidence."""
from __future__ import annotations

from collections import Counter, defaultdict
from functools import lru_cache
import hashlib
import importlib.metadata
import json
from math import gcd
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import zipfile

import numpy as np
import pandas as pd
from rdkit.Chem import GetPeriodicTable

BASE = Path(__file__).resolve().parent
INPUTS = BASE / 'inputs'
TABLES = BASE / 'tables'
PT = GetPeriodicTable()
OMC_ELEMENTS = {'H', 'B', 'C', 'N', 'O', 'F', 'Si', 'P', 'S', 'Cl', 'Br', 'I'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical(counts):
    order = sorted(counts, key=lambda e: (0 if e == 'C' else 1 if e == 'H' else 2, e))
    return ''.join(e + (str(counts[e]) if counts[e] != 1 else '') for e in order)


@lru_cache(maxsize=None)
def parse_formula(text):
    """Strict integer formula parser. Never concatenate separated numeric tokens."""
    if not text or re.search(r'\d\s+\d|\d\.\d', text):
        raise ValueError(f'Missing/ambiguous numeric token in formula: {text!r}')
    text = text.replace(',', ' ')
    text = re.sub(r'(?<=[A-Za-z0-9)\]])\s*[+-]\s*(?=[.·]|$)', '', text)
    text = re.sub(r'\s+[-+]\s+', '.', text)
    text = re.sub(r'\s+', '', text)
    total = Counter()
    for part in re.split(r'[.·]', text):
        if not part:
            raise ValueError('Empty formula component')
        tokens = re.findall(r'[A-Z][a-z]?|\d+|[()[\]]', part)
        if ''.join(tokens) != part:
            raise ValueError(f'Unsupported formula syntax: {part}')
        pos = 0
        coefficient = int(tokens[0]) if tokens[0].isdigit() else 1
        if tokens[0].isdigit():
            pos += 1

        def group(end=None):
            nonlocal pos
            counts = Counter()
            while pos < len(tokens):
                token = tokens[pos]
                pos += 1
                if token in ')]':
                    if token != end:
                        raise ValueError('Mismatched formula group')
                    return counts
                if token in ('(', '['):
                    chunk = group(')' if token == '(' else ']')
                elif re.fullmatch(r'[A-Z][a-z]?', token):
                    if PT.GetAtomicNumber(token) < 1:
                        raise ValueError('Unknown element')
                    chunk = Counter({token: 1})
                else:
                    raise ValueError('Unexpected numeric token')
                multiplier = 1
                if pos < len(tokens) and tokens[pos].isdigit():
                    multiplier = int(tokens[pos])
                    pos += 1
                if multiplier < 1:
                    raise ValueError('Non-positive atom count')
                counts.update({e: n * multiplier for e, n in chunk.items()})
            if end:
                raise ValueError('Unclosed formula group')
            return counts

        counts = group()
        if not counts or coefficient < 1:
            raise ValueError('Empty or non-positive component')
        total.update({e: n * coefficient for e, n in counts.items()})
    return dict(total)


def scalar_multiple(observed, expected):
    if not expected or set(observed) != set(expected):
        return None
    ratios = {observed[e] / expected[e] for e in expected}
    if len(ratios) != 1:
        return None
    ratio = ratios.pop()
    return int(ratio) if ratio >= 1 and ratio.is_integer() else None


def cell_composition(components):
    total = Counter()
    for formula, number in components.items():
        total.update({e: n * number for e, n in parse_formula(formula).items()})
    return dict(total)


def reduced_components(components):
    divisor = 0
    for count in components.values():
        divisor = gcd(divisor, count)
    return {formula: number // divisor for formula, number in sorted(components.items())}


def read_workbook_cells(path):
    """Read source text directly from XLSX XML. No recalculation or workbook edits."""
    ns = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    relns = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
    with zipfile.ZipFile(path) as book:
        strings = []
        if 'xl/sharedStrings.xml' in book.namelist():
            strings = [''.join(item.itertext()) for item in ET.fromstring(book.read('xl/sharedStrings.xml'))]
        workbook = ET.fromstring(book.read('xl/workbook.xml'))
        rid = next(sheet.attrib[relns + 'id'] for sheet in workbook.find('s:sheets', ns)
                   if sheet.attrib['name'] == 'Database')
        relationships = ET.fromstring(book.read('xl/_rels/workbook.xml.rels'))
        target = next(rel.attrib['Target'] for rel in relationships if rel.attrib['Id'] == rid)
        target = target.lstrip('/') if target.startswith('/') else 'xl/' + target
        sheet = ET.fromstring(book.read(target))
        cells = {}
        for cell in sheet.findall('.//s:sheetData/s:row/s:c', ns):
            value = cell.find('s:v', ns)
            if cell.attrib.get('t') == 's':
                result = strings[int(value.text)]
            elif cell.attrib.get('t') == 'inlineStr':
                result = ''.join(cell.find('s:is', ns).itertext())
            else:
                result = '' if value is None else str(value.text)
            cells[cell.attrib['r']] = result
        return cells


def raw_res_composition(path):
    """Independent atom/SFAC count in the archived asymmetric-unit coordinate file."""
    elements, counts = [], Counter()
    for line in path.read_text(errors='strict').splitlines():
        words = line.split()
        if not words:
            continue
        if words[0].upper() in {'UNIT', 'CELL', 'ZERR', 'LATT', 'SYMM', 'TITL', 'END',
                                'REM', 'FVAR', 'HKLF', 'WGHT', 'SHEL', 'BOND', 'LIST',
                                'TEMP', 'FMAP', 'ACTA', 'PLAN', 'PART', 'AFIX', 'DFIX',
                                'DANG', 'SADI', 'SIMU', 'DELU', 'ISOR'}:
            continue
        if words[0].upper() == 'SFAC':
            tokens = [token.capitalize() for token in words[1:]]
            if not all(re.fullmatch(r'[A-Z][a-z]?', token) for token in tokens):
                raise ValueError('Unsupported non-symbol SFAC record')
            elements.extend(tokens)
        elif len(words) >= 5 and re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', words[0]) and re.fullmatch(r'\d+', words[1]):
            try:
                [float(value) for value in words[2:5]]
            except ValueError:
                continue
            if not elements:
                continue
            index = int(words[1]) - 1
            if not 0 <= index < len(elements):
                raise ValueError('SFAC index outside element table')
            counts[elements[index]] += 1
    if not counts:
        raise ValueError('No atom records found')
    return dict(counts)


def write_csv(name, rows):
    frame = rows if isinstance(rows, pd.DataFrame) else pd.DataFrame(rows)
    frame.to_csv(TABLES / (name + '.csv'), index=False, float_format='%.12g')


def properties(counts, weights):
    return {'formula': canonical(counts), 'composition_json': json.dumps(counts, sort_keys=True),
            'atom_count': sum(counts.values()),
            'heavy_atom_count': sum(n for e, n in counts.items() if e != 'H'),
            'molar_mass_g_mol': round(sum(n * weights[e] for e, n in counts.items()), 6)}


def prepare_cposs(weights):
    original = pd.read_csv(INPUTS / 'cposs_molecular_systems.csv', keep_default_na=False)
    audit = pd.read_csv(INPUTS / 'cposs_formula_audit.csv', keep_default_na=False)
    assert len(audit) == audit.source_url.nunique()
    assert original.source_url.nunique() == len(original)
    missing = set(audit.source_url) - set(original.source_url)
    assert set(audit.loc[audit.source_url.isin(missing), 'molecular_system']) == {'Piracetam', 'IsobarbituricAcid'}
    cells = read_workbook_cells(INPUTS / 'Database 2023 checkup.xlsx')
    evidence_by_page = defaultdict(list)
    evidence_rows = json.loads((INPUTS / 'cposs_coordinate_evidence.json').read_text())
    for evidence in evidence_rows:
        evidence_by_page[evidence['source_url']].append(evidence)
    output, component_rows, workbook_check = [], [], []
    for row in audit.to_dict('records'):
        cell = 'B' + str(row['excel_row'])
        assert cells[cell].strip() == row['workbook_formula'].strip(), (cell, 'Workbook/audit text differs')
        workbook_check.append({'molecular_system': row['molecular_system'], 'workbook_cell': 'Database!' + cell,
                               'source_text': cells[cell], 'audit_text_agrees': True})
        wb = parse_formula(row['workbook_formula'])
        assert wb == parse_formula(row['workbook_formula_normalised']), row['molecular_system']
        page_evidence = evidence_by_page[row['source_url']]
        assert {e['dataset_id'] for e in page_evidence} == set(row['dataset_ids'].split('; '))
        valid, errors = [], []
        for evidence in page_evidence:
            if not evidence.get('included'):
                errors.append(evidence['dataset_id'] + ': ' + str(evidence.get('error')))
                continue
            raw = INPUTS / 'selected_crystals' / (evidence['dataset_id'] + '.res')
            assert sha(raw) == evidence['selected_file_sha256']
            components = evidence['component_counts_per_cell']
            full = cell_composition(components)
            assert sum(full.values()) == evidence['crystal_reconstruction']['expanded_unit_cell_atoms']
            assert scalar_multiple(full, raw_res_composition(raw)) is not None, evidence['dataset_id']
            valid.append((evidence, full))
        selected = wb
        formula_source = 'workbook'
        decision = 'workbook_website_agree_coordinates_confirm'
        include = bool(valid)
        observed_multi = {bool(e['observed_multicomponent']) for e, _ in valid}
        if len(observed_multi) > 1:
            include = False
            decision = 'excluded_inconsistent_component_classification'
        is_multi = (next(iter(observed_multi)) if len(observed_multi) == 1
                    else row['composition_basis'] == 'formula unit (multicomponent)')

        def matches(counts):
            if not valid:
                return False
            return all(scalar_multiple(full, counts) is not None and
                       (is_multi or set(e['component_counts_per_cell']) == {canonical(counts)})
                       for e, full in valid)

        if include and matches(wb):
            if row['status'] == 'different composition':
                decision = 'workbook_selected_coordinates_resolve_composition_conflict'
            elif row['status'] == 'workbook resolves invalid website formula':
                decision = 'workbook_repairs_website_oxygen_symbol_coordinates_confirm'
        elif include:
            # Preserve complete component stoichiometry. Never use the largest component alone.
            reductions = [reduced_components(e['component_counts_per_cell']) for e, _ in valid]
            if all(comps == reductions[0] for comps in reductions):
                selected = cell_composition(reductions[0])
                formula_source = 'archived_coordinate_components'
                decision = 'coordinate_composition_selected_both_source_formulae_reviewed'
                assert matches(selected)
            else:
                include = False
                decision = 'excluded_unresolved_stoichiometry_conflict'
        elif not valid:
            decision = 'excluded_no_valid_coordinate_element_table'
        component_variant = json.dumps([{'dataset_id': e['dataset_id'],
                                         'components_per_cell': e['component_counts_per_cell'],
                                         'archive_url': e['archive_url'],
                                         'selected_file_sha256': e['selected_file_sha256']}
                                        for e, _ in valid], sort_keys=True)
        record = {
            'molecular_system': row['molecular_system'], 'source_url': row['source_url'],
            'dataset_ids': row['dataset_ids'], 'workbook_cell': 'Database!' + cell,
            'workbook_formula': row['workbook_formula'], 'website_formula': row['website_formula'],
            'original_audit_status': row['status'], 'formula_source': formula_source,
            'decision': decision, 'component_basis': 'formula_unit' if is_multi else 'single_molecule',
            'included_primary': include and not is_multi,
            'included_multicomponent': include and is_multi,
            'included_metadata_sensitivity': not is_multi,
            'coordinate_validated': include, 'n_verified_search_representatives': len(valid),
            'n_failed_search_representatives': len(errors), 'source_errors': ' | '.join(errors),
            'component_evidence_json': component_variant,
            **properties(selected, weights), 'value_status': 'computed_from_source_metadata_and_coordinate_audit',
        }
        output.append(record)
        if include:
            example = valid[0][0]
            for formula, number in reduced_components(example['component_counts_per_cell']).items():
                component_rows.append({'molecular_system': row['molecular_system'],
                                       'basis': 'minimum_integer_component_ratio',
                                       'component_formula': formula, 'stoichiometric_coefficient': number,
                                       'source_dataset': example['dataset_id'],
                                       **properties(parse_formula(formula), weights)})
    frame = pd.DataFrame(output).sort_values('molecular_system')
    write_csv('cposs_molecular_systems_audit', frame)
    write_csv('cposs_primary_molecules', frame[frame.included_primary])
    write_csv('cposs_multicomponent_formula_units', frame[frame.included_multicomponent])
    write_csv('cposs_metadata_only_sensitivity', frame[frame.included_metadata_sensitivity])
    write_csv('cposs_component_inventory', component_rows)
    write_csv('workbook_formula_crosscheck', workbook_check)
    write_csv('cposs_formula_conflict_resolutions', frame[frame.original_audit_status != 'equal composition'])
    write_csv('cposs_exclusions', frame[~frame.coordinate_validated])
    return frame


def prepare_omc(weights):
    raw = pd.read_csv(INPUTS / 'omc25-starting-crystals.csv')
    required = ['csd_refcode', 'split', 'mol.composition', 'mol.natoms', 'mol.mass']
    assert not raw[required].isna().any().any()
    assert set(raw.split) == {'train', 'val'}
    assert not raw.duplicated(['csd_refcode', 'z_value', 'genarris_step', 'xtal.id']).any()
    invariants = raw.groupby('csd_refcode')[required[1:]].nunique()
    assert (invariants == 1).all().all(), 'Molecular metadata varies within a molecular identifier'
    molecule_rows = raw.sort_values(['csd_refcode', 'z_value', 'genarris_step', 'xtal.id']).drop_duplicates('csd_refcode')
    clean = []
    for row in molecule_rows.to_dict('records'):
        counts = parse_formula(row['mol.composition'])
        props = properties(counts, weights)
        assert props['atom_count'] == row['mol.natoms']
        clean.append({'csd_refcode': row['csd_refcode'], 'split': row['split'],
                      'source_composition': row['mol.composition'],
                      'reported_molar_mass_g_mol': round(row['mol.mass'], 8),
                      'reported_minus_common_mass_g_mol': row['mol.mass'] - props['molar_mass_g_mol'],
                      'component_basis': 'single_molecule_as_reported_by_OMC25_paper',
                      'value_status': 'computed_from_official_metadata', **props})
    clean = pd.DataFrame(clean)
    assert set().union(*(parse_formula(f) for f in clean.formula)) == OMC_ELEMENTS
    # Validate the full cell relation, including hydrogens, on every starting crystal.
    assert (raw['xtal.natoms'] == raw['z_value'] * raw['mol.natoms']).all()
    for row in raw[['mol.composition', 'xtal.composition', 'z_value']].drop_duplicates().to_dict('records'):
        assert parse_formula(row['xtal.composition']) == {e: n * row['z_value'] for e, n in parse_formula(row['mol.composition']).items()}
    assert np.allclose(raw['xtal.mass'], raw['z_value'] * raw['mol.mass'], atol=1e-8, rtol=0)
    summary = []
    expected = {'train': (207271, 44403, 24870226), 'val': (11570, 2467, 1386816)}
    for split, (crystals, molecules, frames) in expected.items():
        part = raw[raw.split == split]
        assert (len(part), part.csd_refcode.nunique(), int(part.nframes.sum())) == (crystals, molecules, frames)
        summary.append({'split': split, 'starting_crystals': crystals, 'molecular_records': molecules,
                        'sampled_relaxation_frames': frames, 'count_status': 'computed_from_official_metadata'})
    write_csv('omc25_split_validation', summary)
    write_csv('omc25_molecules_train_and_val', clean)
    write_csv('omc25_train_molecules', clean[clean.split == 'train'])
    mass_delta = clean[clean.split == 'train'].reported_minus_common_mass_g_mol
    return clean, {'starting_crystals': len(raw), 'molecular_records': len(clean),
                   'invariant_molecular_fields': True, 'duplicate_starting_crystal_keys': 0,
                   'training_reported_mass_minus_common_min': float(mass_delta.min()),
                   'training_reported_mass_minus_common_max': float(mass_delta.max()),
                   'training_reported_mass_minus_common_max_absolute': float(mass_delta.abs().max())}


def summarize(populations):
    rows, elements, ranges, curves = [], [], [], []
    all_elements = sorted(set().union(*(set().union(*(json.loads(c) for c in frame.composition_json))
                                       for frame, _ in populations.values())), key=PT.GetAtomicNumber)
    reference, _ = populations['OMC25_train']
    for name, (frame, excluded) in populations.items():
        composition = [json.loads(c) for c in frame.composition_json]
        for element in all_elements:
            count = sum(c.get(element, 0) > 0 for c in composition)
            atom_n = sum(c.get(element, 0) for c in composition)
            elements.append({'population': name, 'counting_unit': 'formula_unit' if 'formula_units' in name else 'molecular_record',
                             'element': element, 'records_with_element': count,
                             'valid_records': len(frame), 'prevalence_percent': 100 * count / len(frame),
                             'atoms_of_element': atom_n, 'all_atoms': int(frame.atom_count.sum()),
                             'atomic_fraction_percent': 100 * atom_n / frame.atom_count.sum()})
        variables = ['atom_count', 'heavy_atom_count', 'molar_mass_g_mol']
        if 'reported_molar_mass_g_mol' in frame:
            variables += ['reported_molar_mass_g_mol']
        for variable in variables:
            values = frame[variable].to_numpy(dtype=float)
            q1, median, q3 = np.quantile(values, [.25, .5, .75], method='linear')
            rows.append({'population': name, 'variable': variable, 'unit': 'g/mol' if 'mass' in variable else 'atoms',
                         'n': len(values), 'n_missing': int(np.isnan(values).sum()), 'n_excluded': excluded,
                         'minimum': values.min(), 'q1': q1, 'median': median, 'q3': q3,
                         'maximum': values.max(), 'mean': values.mean(), 'quantile_method': 'numpy_linear'})
            unique, counts = np.unique(values, return_counts=True)
            for x, y in zip(unique, np.cumsum(counts) / len(values)):
                curves.append({'population': name, 'variable': variable, 'x': x, 'cumulative_fraction': y})
            if name != 'OMC25_train' and variable in ['atom_count', 'heavy_atom_count', 'molar_mass_g_mol']:
                low, high = reference[variable].min(), reference[variable].max()
                below, above = int((values < low).sum()), int((values > high).sum())
                ranges.append({'population': name, 'variable': variable, 'omc25_minimum': low,
                               'omc25_maximum': high, 'n': len(values), 'below_n': below, 'above_n': above,
                               'outside_n': below + above, 'outside_percent': 100 * (below + above) / len(values)})
    write_csv('summary_statistics', rows)
    element_frame = pd.DataFrame(elements)
    write_csv('elemental_prevalence', element_frame[['population', 'counting_unit', 'element', 'records_with_element',
                                                   'valid_records', 'prevalence_percent']])
    write_csv('atomic_fractions', element_frame[['population', 'counting_unit', 'element', 'atoms_of_element',
                                               'all_atoms', 'atomic_fraction_percent']])
    write_csv('outside_omc25_ranges', ranges)
    write_csv('ecdf_coordinates', curves)
    return pd.DataFrame(rows), pd.DataFrame(elements)


def main():
    TABLES.mkdir(exist_ok=True)
    manifest = json.loads((INPUTS / 'manifest.json').read_text())
    for name, digest in manifest['files'].items():
        assert sha(INPUTS / name) == digest, f'Input changed: {name}'
    weight_path = INPUTS / 'atomic_weights.json'
    if not weight_path.exists():
        # Freeze one average-mass convention for both datasets; retain OMC25 reported masses separately.
        weight_path.write_text(json.dumps({'convention': 'RDKit average atomic weights',
                                          'rdkit_version': importlib.metadata.version('rdkit'),
                                          'weights_g_mol': {PT.GetElementSymbol(i): PT.GetAtomicWeight(i)
                                                            for i in range(1, 119)}}, indent=2) + '\n')
    assert sha(weight_path) == '252f58ef84ad9a6867d8d1e79089b983ca208b0330b7924f69bb219ef1e658e7', 'Frozen atomic weights changed'
    weights = json.loads(weight_path.read_text())['weights_g_mol']
    cposs = prepare_cposs(weights)
    omc, validation = prepare_omc(weights)
    primary = cposs[cposs.included_primary]
    multi = cposs[cposs.included_multicomponent]
    metadata = cposs[cposs.included_metadata_sensitivity]
    populations = {'CPOSS_single_verified': (primary, int((~cposs.coordinate_validated & (cposs.component_basis == 'single_molecule')).sum())),
                   'OMC25_train': (omc[omc.split == 'train'], 0),
                   'CPOSS_multicomponent_formula_units': (multi, int((~cposs.coordinate_validated & (cposs.component_basis == 'formula_unit')).sum())),
                   'CPOSS_single_metadata_sensitivity': (metadata, 0)}
    statistics, elemental = summarize(populations)
    validation.update({'cposs_total_systems': len(cposs), 'cposs_single_verified': len(primary),
                       'cposs_multicomponent_verified': len(multi),
                       'cposs_excluded_systems': cposs.loc[~cposs.coordinate_validated, 'molecular_system'].tolist(),
                       'cposs_unresolved_composition_conflicts': int(cposs.decision.str.contains('excluded_unresolved').sum()),
                       'cposs_formula_conflicts_reviewed': int((cposs.original_audit_status == 'different composition').sum()),
                       'cposs_malformed_formula_repairs': int(cposs.decision.str.contains('repairs_website').sum()),
                       'atomic_weights_sha256': sha(weight_path),
                       'software_versions': {package: importlib.metadata.version(package)
                                             for package in ['numpy', 'pandas', 'rdkit', 'matplotlib', 'pypdf', 'Pillow']}})
    (BASE / 'analysis_validation.json').write_text(json.dumps(validation, indent=2) + '\n')
    # Imported only after all population and formula checks have succeeded.
    from write_results import write_results
    write_results(cposs, omc, statistics, elemental, validation, manifest)
    print(json.dumps(validation, indent=2))


if __name__ == '__main__':
    main()
