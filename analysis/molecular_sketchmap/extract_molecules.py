#!/usr/bin/env python3
"""Select archived crystals and reconstruct finite molecules with periodic bonds."""
from collections import Counter, deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from fractions import Fraction
import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
from urllib.parse import quote
import xml.etree.ElementTree as ET
import zipfile

import numpy as np
import pandas as pd
from ase import Atoms
from ase.cell import Cell
from ase.data import atomic_numbers, covalent_radii
from ase.neighborlist import neighbor_list
from rdkit import Chem, RDLogger
from rdkit.Chem import Descriptors, rdDetermineBonds, rdMolDescriptors
import requests

BASE = Path(__file__).resolve().parent
SOURCE = BASE.parent / "database_in_numbers"
INPUTS = BASE / "inputs"
ALLOW_DOWNLOAD = True


def git_sha(raw):
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def prepare_inputs(refresh=False):
    INPUTS.mkdir(exist_ok=True)
    for name in ["datasets.csv", "structure_archive_counts.csv", "structure_count_reconciliation.csv", "dataset_archive_counts.csv", "manifest.json"]:
        target = INPUTS / name
        original = SOURCE / (name if name == "manifest.json" else "tables/" + name)
        if refresh or not target.exists(): shutil.copy2(original, target)


def cached_source(path, sha, cache, suffix):
    target = Path(cache, sha + suffix)
    if not target.exists():
        if not ALLOW_DOWNLOAD: raise FileNotFoundError("Source cache missing in offline mode: " + str(target))
        revision = json.loads((INPUTS / "manifest.json").read_text())["snapshot_revision"]
        url = "https://raw.githubusercontent.com/LouisePrice/CPOSS_Database/" + revision + "/" + quote(path)
        response = requests.get(url, timeout=180); response.raise_for_status()
        if git_sha(response.content) != sha: raise ValueError("Downloaded source checksum mismatch")
        target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(response.content)
    if git_sha(target.read_bytes()) != sha: raise ValueError("Cached source checksum mismatch")
    return target

RDLogger.DisableLog("rdApp.error")
RDLogger.DisableLog("rdApp.warning")
NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
CENTRING = {1: [(0, 0, 0)], 2: [(0, 0, 0), (.5, .5, .5)],
            3: [(0, 0, 0), (2/3, 1/3, 1/3), (1/3, 2/3, 2/3)],
            4: [(0, 0, 0), (0, .5, .5), (.5, 0, .5), (.5, .5, 0)],
            5: [(0, 0, 0), (0, .5, .5)], 6: [(0, 0, 0), (.5, 0, .5)],
            7: [(0, 0, 0), (.5, .5, 0)]}


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def affine(expression):
    """Parse SHELX affine symmetry without evaluating executable expressions."""
    rows, translations = [], []
    for coordinate in expression.upper().replace(" ", "").split(","):
        rotation, translation = np.zeros(3, dtype=int), 0.0
        for term in re.findall(r"[+-]?[^+-]+", coordinate):
            sign = -1 if term.startswith("-") else 1
            value = term.lstrip("+-")
            if value in "XYZ" and len(value) == 1:
                rotation["XYZ".index(value)] += sign
            else:
                translation += sign * float(Fraction(value))
        rows.append(rotation)
        translations.append(translation)
    if len(rows) != 3:
        raise ValueError("Invalid symmetry: " + expression)
    return np.asarray(rows), np.asarray(translations)


def parse_res(text):
    cell, lattice, title, sfac, atoms, operators, warnings = None, 1, "", [], [], [], []
    lattice_reported = False
    for line in text.splitlines():
        fields = line.split("!", 1)[0].split()
        if not fields:
            continue
        key = fields[0].upper()
        if key == "TITL": title = line.strip()
        elif key == "CELL": cell = Cell.fromcellpar(list(map(float, fields[2:8])))
        elif key == "LATT": lattice, lattice_reported = int(fields[1]), True
        elif key == "SYMM": operators.append(affine(line.strip()[4:].split("!", 1)[0]))
        elif key == "SFAC":
            # This collection uses element-list SFAC records, not coefficient lists.
            symbols = [v.capitalize() for v in fields[1:]]
            if not all(v in atomic_numbers for v in symbols):
                raise ValueError("Unsupported scattering-factor specification")
            sfac.extend(symbols)
        elif key == "UNIT":
            continue
        elif key in {"PART", "FVAR"}:
            if key == "PART" and len(fields) > 1 and float(fields[1]) != 0:
                warnings.append("disordered_PART")
        elif key == "END": break
        elif sfac and len(fields) >= 5 and re.fullmatch(r"\d+", fields[1]):
            index = int(fields[1]) - 1
            if index not in range(len(sfac)):
                raise ValueError("Atom SFAC index outside reported element list")
            try:
                frac = [float(x) for x in fields[2:5]]
            except ValueError:
                continue
            if len(fields) > 5:
                try:
                    occupancy = float(fields[5])
                    if abs(occupancy) >= 20 or (0 < abs(occupancy) < 1):
                        warnings.append("nontrivial_occupancy_requires_review")
                except ValueError:
                    pass
            atoms.append((sfac[index], frac, fields[0]))
    if cell is None or not atoms or abs(lattice) not in CENTRING:
        raise ValueError("Missing cell/atoms or unsupported LATT")
    if not lattice_reported:
        warnings.append("LATT_default_1")
    operations = [(np.eye(3, dtype=int), np.zeros(3))] + operators
    if lattice > 0:
        operations += [(-r, -t) for r, t in list(operations)]
    symbols, fractions, labels, unique = [], [], [], set()
    for rotation, translation in operations:
        for centring in CENTRING[abs(lattice)]:
            for symbol, frac, label in atoms:
                position = (rotation @ np.asarray(frac) + translation + centring) % 1
                position[np.isclose(position, 1, atol=1e-7)] = 0
                key = (symbol, *np.round(position, 6))
                if key in unique:
                    continue
                unique.add(key)
                symbols.append(symbol); fractions.append(position); labels.append(label)
    crystal = Atoms(symbols, scaled_positions=fractions, cell=cell, pbc=True)
    return crystal, {"title": title, "lattice": lattice, "asymmetric_unit_atoms": len(atoms),
                     "expanded_unit_cell_atoms": len(crystal), "warnings": sorted(set(warnings)), "source_atom_labels": labels}


def molecular_components(crystal, factor=1.20):
    """Covalent graph plus image offsets reconstructs molecules across any boundary."""
    cutoffs = factor * covalent_radii[crystal.numbers]
    ii, jj, shifts = neighbor_list("ijS", crystal, cutoffs, self_interaction=False)
    graph = [[] for _ in crystal]
    for i, j, shift in zip(ii, jj, shifts):
        distance = np.linalg.norm(crystal.positions[j] + shift @ crystal.cell.array - crystal.positions[i])
        if distance < .35:
            raise ValueError("Unresolved overlapping atomic sites")
        graph[i].append((int(j), shift))
    visited, components = set(), []
    frac = crystal.get_scaled_positions(wrap=True)
    for root in range(len(crystal)):
        if root in visited:
            continue
        offsets, queue = {root: np.zeros(3, dtype=int)}, deque([root])
        visited.add(root)
        while queue:
            i = queue.popleft()
            for j, shift in graph[i]:
                candidate = offsets[i] + shift
                if j in offsets:
                    if not np.array_equal(offsets[j], candidate):
                        raise ValueError("Periodic covalent network or excessive bond cutoff")
                else:
                    offsets[j] = candidate; visited.add(j); queue.append(j)
        ids = sorted(offsets)
        positions = np.asarray([frac[i] + offsets[i] for i in ids]) @ crystal.cell.array
        positions -= positions.mean(axis=0)
        components.append(Atoms([crystal[i].symbol for i in ids], positions=positions))
    return components


def formula_counter(text):
    return Counter({symbol: int(count or 1) for symbol, count in re.findall(r"([A-Z][a-z]?)(\d*)", text)})


def formula_multiple(actual, expected):
    if set(actual) != set(expected) or not expected:
        return None
    ratios = [actual[k] / expected[k] for k in expected]
    return ratios[0] if min(ratios) > 0 and np.allclose(ratios, ratios[0], atol=1e-8) else None


def infer_molecule(atoms):
    """Retain coordinates, infer bonds/charges without adding or deleting atoms."""
    xyz = str(len(atoms)) + "\nextracted coordinates\n" + "\n".join(f"{s} {p[0]:.9f} {p[1]:.9f} {p[2]:.9f}" for s, p in zip(atoms.get_chemical_symbols(), atoms.positions))
    errors = []
    for charge in [0, 1, -1, 2, -2]:
        molecule = Chem.MolFromXYZBlock(xyz)
        try:
            rdDetermineBonds.DetermineBonds(molecule, charge=charge, allowChargedFragments=True, embedChiral=True, maxIterations=10000)
            if any(a.GetNumRadicalElectrons() for a in molecule.GetAtoms()):
                raise ValueError("Unresolved radical/valence")
            Chem.AssignStereochemistryFrom3D(molecule)
            return molecule, charge, "inferred_from_coordinates"
        except Exception as exc:
            errors.append(str(exc)[:160])
    molecule = Chem.MolFromXYZBlock(xyz)
    rdDetermineBonds.DetermineConnectivity(molecule)
    return molecule, None, "connectivity_only_unresolved_bond_orders"


def experimental_names(dataset_id, workbook_table):
    row = workbook_table.loc[dataset_id]
    path = cached_source(row.workbook_path, row.workbook_git_blob_sha, "/tmp/cposs-workbook-cache", ".xlsx")
    names = set()
    with zipfile.ZipFile(path) as archive:
        strings = []
        if "xl/sharedStrings.xml" in archive.namelist():
            strings = ["".join(x.itertext()) for x in ET.fromstring(archive.read("xl/sharedStrings.xml")).findall("s:si", NS)]
        for member in archive.namelist():
            if not re.fullmatch(r"xl/worksheets/sheet\d+\.xml", member): continue
            rows = []
            for xmlrow in ET.fromstring(archive.read(member)).findall("s:sheetData/s:row", NS):
                values = {}
                for c in xmlrow:
                    col = re.match("[A-Z]+", c.get("r", ""))
                    if not col: continue
                    v, inline = c.find("s:v", NS), c.find("s:is", NS)
                    value = v.text if v is not None else "".join(inline.itertext()) if inline is not None else ""
                    if c.get("t") == "s" and value: value = strings[int(value)]
                    if value: values[col[0]] = value.strip()
                rows.append(values)
            header_i = next((i for i, r in enumerate(rows[:15]) if "Filename" in r.values()), None)
            if header_i is None: continue
            header = rows[header_i]
            filename = next(k for k, v in header.items() if v == "Filename")
            exp = [k for k, v in header.items() if "experimental" in v.lower()]
            for r in rows[header_i+1:]:
                if filename in r and any(r.get(k, "").lower() not in {"", "0", "none", "nan", "-"} for k in exp):
                    names.add(Path(r[filename]).stem.casefold())
    return names, "explicit_nonempty_Experimental_Info"


def title_energy(line):
    values = re.findall(r"\(\s*([-+]?\d+(?:\.\d*)?(?:[Ee][-+]?\d+)?)\s*\)", line)
    return float(values[-1]) if values else None


def extract_one(dataset, archives, workbook_table, force=False, model_index=0):
    output = BASE / "molecules" / (dataset.dataset_id + ".json")
    if output.exists() and not force:
        return json.loads(output.read_text())
    options = archives[archives.dataset_id == dataset.dataset_id].sort_values("model_id")
    result = {"dataset_id": dataset.dataset_id, "dataset_name": dataset.dataset_name,
              "source_url": dataset.source_url, "reported_formula": dataset.formula_raw,
              "reported_formula_normalised": dataset.formula_normalised,
              "composition_basis": dataset.composition_basis, "structure_count": int(options.coordinate_files.sum()),
              "extraction_status": "missing", "included": False, "selection_rule": "Lowest numeric model ID with a reconstructable molecule; lowest finite TITL energy among non-reference archived members; deterministic filename tie-break; validate up to five lowest candidates per model"}
    row = options.iloc[model_index]
    result.update({"selected_model_id": int(row.model_id), "archive_url": row.archive_url, "archive_git_blob_sha": row.git_blob_sha})
    attempts = []
    try:
        path = cached_source(row.archive_path, row.git_blob_sha, "/tmp/cposs-model-archive-cache", ".zip")
        exp_names, exp_rule = experimental_names(dataset.dataset_id, workbook_table)
        result["experimental_reference_rule"] = exp_rule
        candidates = []
        with zipfile.ZipFile(path) as archive:
            for member in archive.namelist():
                if not member.lower().endswith(".res") or "__MACOSX" in Path(member).parts or Path(member).name.startswith("._"): continue
                if Path(member).stem.casefold() in exp_names: continue
                with archive.open(member) as stream:
                    line = stream.readline().decode("utf-8", errors="replace")
                energy = title_energy(line)
                candidates.append((energy, member))
            finite = [(e, n) for e, n in candidates if e is not None and np.isfinite(e)]
            ordered = sorted(finite) if finite else [(None, n) for _, n in sorted(candidates, key=lambda x:x[1])]
            if not ordered: raise ValueError("No non-reference coordinate candidates")
            result.update({"candidate_files": len(candidates), "candidates_with_title_energy": len(finite)})
            for rank, (energy, member) in enumerate(ordered[:5], 1):
                try:
                    raw = archive.read(member)
                    crystal, info = parse_res(raw.decode("utf-8", errors="replace"))
                    if any(x in info["warnings"] for x in ["disordered_PART", "nontrivial_occupancy_requires_review"]):
                        raise ValueError("Disorder/occupancy requires manual review: " + str(info["warnings"]))
                    components = molecular_components(crystal)
                    expected = formula_counter(dataset.formula_normalised)
                    ratio = formula_multiple(Counter(crystal.get_chemical_symbols()), expected)
                    if ratio is None:
                        label_elements = {"C": "C", "CAR": "C", "H": "H", "HYD": "H", "HPD": "H", "N": "N", "NIT": "N", "O": "O", "OXY": "O", "CLR": "Cl", "CL": "Cl", "BR": "Br", "SI": "Si", "CU": "Cu", "S": "S", "I": "I"}
                        conflicts = [(label, symbol) for label, symbol in zip(info["source_atom_labels"], crystal.get_chemical_symbols()) if (prefix := re.match("[A-Za-z]+", label)) and prefix[0].upper() in label_elements and label_elements[prefix[0].upper()] != symbol]
                        if conflicts:
                            raise ValueError("Element table conflicts with atom labels and reported formula: " + str(conflicts[:5]))
                    details = []
                    # Infer chemical identity once per repeated rounded intramolecular geometry.
                    cache = {}
                    for atoms in components:
                        key = (tuple(atoms.get_chemical_symbols()), tuple(np.round(np.sort(atoms.get_all_distances().flatten()), 3)))
                        if key not in cache: cache[key] = infer_molecule(atoms)
                        mol, charge, bond_status = cache[key]
                        smiles = Chem.MolToSmiles(Chem.RemoveHs(mol, sanitize=False), isomericSmiles=True) if charge is not None else ""
                        details.append({"atoms": atoms, "molecule": mol, "charge": charge, "bond_status": bond_status,
                                        "formula": atoms.get_chemical_formula(), "smiles": smiles,
                                        "heavy_atoms": int(sum(z != 1 for z in atoms.numbers))})
                    nonwater = [c for c in details if c["formula"] != "H2O"]
                    if not nonwater: raise ValueError("No non-water molecular component")
                    largest = max(c["heavy_atoms"] for c in nonwater)
                    possible = [c for c in nonwater if c["heavy_atoms"] == largest]
                    identities = {c["smiles"] or c["formula"] for c in possible}
                    # Enantiomers share a constitution; the deterministic first component is retained.
                    constitutions = {Chem.MolToSmiles(Chem.RemoveHs(c["molecule"], sanitize=False), isomericSmiles=False) if c["charge"] is not None else c["formula"] for c in possible}
                    if len(constitutions) > 1: raise ValueError("Ambiguous largest components with different connectivity")
                    selected = possible[0]
                    all_constitutions = {Chem.MolToSmiles(Chem.RemoveHs(c["molecule"], sanitize=False), isomericSmiles=False) if c["charge"] is not None else c["formula"] for c in details}
                    formula_status = "matches_full_unit_cell_stoichiometry" if ratio is not None else "source_formula_conflict_coordinates_retained"
                    # SOAP needs positions/elements, not bond orders. Retain a
                    # formula-consistent finite component with plausible degrees
                    # when bond orders cannot be assigned; label its SDF as
                    # connectivity-only, and leave charge/chemical identity unset.
                    if selected["charge"] is None:
                        limits = {1: 1, 5: 4, 6: 4, 7: 4, 8: 3, 9: 1, 14: 6, 15: 6, 16: 6, 17: 1, 29: 6, 35: 1, 53: 1}
                        plausible = all(atom.GetDegree() <= limits.get(atom.GetAtomicNum(), 8) for atom in selected["molecule"].GetAtoms())
                        if ratio is None or not plausible:
                            raise ValueError("Unresolved bond orders with formula/coordination conflict")
                    result.update({"selected_filename": member, "selected_file_sha256": hashlib.sha256(raw).hexdigest(),
                                   "selected_title_energy": energy, "energy_source": "TITL parentheses; numerical values compared only inside selected model archive",
                                   "selected_candidate_rank": rank, "formula_validation": formula_status,
                                   "formula_units_in_cell": ratio, "selected_formula": selected["formula"],
                                   "selected_smiles": selected["smiles"], "constitution_smiles": next(iter(constitutions)),
                                   "inferred_formal_charge": selected["charge"], "bond_assignment_status": selected["bond_status"],
                                   "principal_selection": "Largest non-water component by heavy-atom count; first equivalent component in source/symmetry order",
                                   "selected_atoms": len(selected["atoms"]), "selected_heavy_atoms": largest,
                                   "selected_molar_mass_g_mol": float(sum(Chem.GetPeriodicTable().GetAtomicWeight(int(z)) for z in selected["atoms"].numbers)),
                                   "observed_multicomponent": len(all_constitutions) > 1,
                                   "component_counts_per_cell": dict(Counter(c["formula"] for c in details)),
                                   "component_identities_per_cell": dict(Counter(c["smiles"] or c["formula"] for c in details)),
                                   "component_stoichiometry_per_formula_unit": {k: v / ratio for k, v in Counter(c["formula"] for c in details).items()} if ratio is not None else None,
                                   "omitted_component_types_per_cell": dict(Counter(c["formula"] for c in details if (Chem.MolToSmiles(Chem.RemoveHs(c["molecule"], sanitize=False), isomericSmiles=False) if c["charge"] is not None else c["formula"]) not in constitutions)),
                                   "multiple_largest_stereoisomers": len(identities) > 1,
                                   "crystal_reconstruction": info, "extraction_status": "calculated", "included": True,
                                   "symbols": selected["atoms"].get_chemical_symbols(), "coordinates_angstrom": selected["atoms"].positions.tolist(),
                                   "bonds": [[b.GetBeginAtomIdx(), b.GetEndAtomIdx(), b.GetBondTypeAsDouble()] for b in selected["molecule"].GetBonds()]})
                    molecule = selected["molecule"]
                    molecule.SetProp("_Name", dataset.dataset_id)
                    for key in ["dataset_id", "archive_url", "selected_filename", "reported_formula", "selected_formula", "bond_assignment_status"]:
                        molecule.SetProp(key, str(result[key]))
                    molecule.SetProp("structure_count", str(result["structure_count"]))
                    with Chem.SDWriter(str(output.with_suffix(".sdf"))) as writer: writer.write(molecule)
                    xyz = f"{len(selected['atoms'])}\n{dataset.dataset_id}; extracted from {member}\n"
                    xyz += "\n".join(f"{s} {p[0]:.9f} {p[1]:.9f} {p[2]:.9f}" for s, p in zip(result["symbols"], result["coordinates_angstrom"])) + "\n"
                    output.with_suffix(".xyz").write_text(xyz)
                    (BASE / "selected_crystals" / (dataset.dataset_id + ".res")).write_bytes(raw)
                    break
                except Exception as exc:
                    attempts.append({"candidate_rank": rank, "filename": member, "energy": energy, "error": str(exc)})
            if not result["included"]: result["error"] = attempts[-1]["error"] if attempts else "No candidates"
    except Exception as exc:
        result["error"] = str(exc)
    result["rejected_candidates"] = attempts
    if not result["included"] and model_index + 1 < len(options):
        following = extract_one(dataset, archives, workbook_table, True, model_index + 1)
        following.setdefault("rejected_models", []).insert(0, {"model_id": int(row.model_id), "archive_url": row.archive_url, "attempts": attempts, "error": result.get("error")})
        write_json(output, following)
        return following
    write_json(output, result)
    return result


def main():
    global ALLOW_DOWNLOAD
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--refresh-inputs", action="store_true", help="Replace derived CPOSS input copies from the current parent analysis and repeat extraction")
    parser.add_argument("--dataset", nargs="*")
    parser.add_argument("--offline", action="store_true", help="Require cached originals; never download")
    args = parser.parse_args()
    ALLOW_DOWNLOAD = not args.offline
    for directory in ["molecules", "selected_crystals", "tables", "data", "figures", "output/pdf"]:
        (BASE / directory).mkdir(parents=True, exist_ok=True)
    prepare_inputs(args.refresh_inputs)
    datasets = pd.read_csv(INPUTS / "datasets.csv", keep_default_na=False)
    archives = pd.read_csv(INPUTS / "structure_archive_counts.csv")
    workbooks = pd.read_csv(INPUTS / "structure_count_reconciliation.csv").set_index("dataset_id")
    if args.dataset: datasets = datasets[datasets.dataset_id.isin(args.dataset)]
    results = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(extract_one, row, archives, workbooks, args.force or args.refresh_inputs) for row in datasets.itertuples()]
        for i, future in enumerate(as_completed(futures), 1):
            result = future.result(); results.append(result)
            if i % 20 == 0 or not result["included"] or i == len(futures):
                print(f"Extracted {i}/{len(futures)}; included {sum(r['included'] for r in results)}; latest {result['dataset_id']}: {result.get('error', 'OK')}", flush=True)
    columns = ["dataset_id", "dataset_name", "source_url", "structure_count", "reported_formula", "composition_basis", "observed_multicomponent", "selected_model_id", "archive_url", "archive_git_blob_sha", "selected_filename", "selected_file_sha256", "selected_title_energy", "selected_candidate_rank", "selected_formula", "selected_atoms", "selected_heavy_atoms", "selected_smiles", "constitution_smiles", "inferred_formal_charge", "bond_assignment_status", "formula_validation", "formula_units_in_cell", "selected_molar_mass_g_mol", "multiple_largest_stereoisomers", "extraction_status", "included", "error", "selection_rule", "principal_selection", "energy_source", "candidate_files", "candidates_with_title_energy"]
    frame = pd.DataFrame([{k: r.get(k) for k in columns} | {"component_counts_per_cell": json.dumps(r.get("component_counts_per_cell", {})), "component_identities_per_cell": json.dumps(r.get("component_identities_per_cell", {})), "rejected_candidates": json.dumps(r.get("rejected_candidates", []))} for r in results]).sort_values("dataset_id")
    name = "extraction" if not args.dataset else "extraction_subset"
    frame.to_csv(BASE / "tables" / (name + ".csv"), index=False)
    summary = {"attempted": len(results), "included": int(frame.included.sum()), "excluded": int((~frame.included).sum()), "represented_archive_structure_files": int(frame.loc[frame.included, "structure_count"].sum()), "all_archive_structure_files": int(frame.structure_count.sum()), "exclusions": frame.loc[~frame.included, ["dataset_id", "error"]].to_dict("records")}
    write_json(BASE / "data" / (name + "_summary.json"), summary)
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__": main()
