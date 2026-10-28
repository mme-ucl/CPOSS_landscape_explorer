"""Trace search generation and per-model refinement to checksum-verified HTML."""
from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit

import pandas as pd

BASE = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))
from analyse import git_sha, parse_case

SEARCH_PATTERNS = {
    "MOLPAK": r"\bmolpak\b",
    "CrystalPredictor": r"\bcrystal\s*pre(?:dictor|cictor)|\bcrystpred\b",
}
FLEXIBLE = r"\b(?:crystal\s*optimi[sz](?:er|ar|e)?|crystopt|dmaf(?:l)?(?:ex|exquick))"
REFERENCES = {
    "rigid_engines": "https://www.chem.ucl.ac.uk/cposs/results/methods.html",
    "dmacrys": "https://www.chem.ucl.ac.uk/cposs/dmacrys/",
    "crystaloptimizer": "https://www.chem.ucl.ac.uk/cposs/computational/crystaloptimizer.html",
    "search_vs_refinement": "https://www.chem.ucl.ac.uk/cposs/computational/postprocessing.html",
}


def source_path(url):
    return unquote(urlsplit(url).path.split("/CPOSS_Database/", 1)[1])


def mentioned_searches(text):
    return {name for name, pattern in SEARCH_PATTERNS.items() if re.search(pattern, text, re.I)}


def study_references(text):
    """Return explicit IDs; flag alternatives rather than selecting one silently."""
    ids = re.findall(r"\bstudy[_\s-]*id\s*=?\s*(\d+)", text, re.I)
    ambiguous = bool(re.search(r"study[_\s-]*id\s*=?\s*\d+\s+or\s+\d+|not sure", text, re.I))
    return list(dict.fromkeys(ids)), ambiguous


def trace_search(model, index, visited=()):
    key = (model["page_path"], str(model.get("study_id", "")))
    evidence = {"page_path": key[0], "study_id": key[1],
                "programs": model.get("programs", ""),
                "potential_description": model.get("potential description", ""),
                "html_blob_sha": model["html_blob_sha"]}
    programs = model.get("programs", "")
    direct = mentioned_searches(programs)
    if not direct:
        direct = mentioned_searches(model.get("potential description", ""))
    if direct:
        return direct, [evidence], "direct_source_text" if len(direct) == 1 else "multiple_search_programs"
    if re.search(r"CCDC supplied|supplied crystal structures|\bMercury\b", programs, re.I):
        return set(), [evidence], "other_origin_not_MOLPAK_or_CrystalPredictor"
    if key in visited:
        return set(), [evidence], "cyclic_Study_ID_reference"
    ids, ambiguous = study_references(programs)
    if ambiguous:
        return set(), [evidence], "ambiguous_Study_ID_reference"
    if not ids:
        return set(), [evidence], "initial_search_not_reported"
    values, chain = set(), [evidence]
    for identifier in ids:
        target = index.get((key[0], identifier))
        if target is None:
            return set(), chain, "missing_Study_ID_target"
        names, following, status = trace_search(target, index, (*visited, key))
        chain.extend(following)
        if not names:
            return set(), chain, status
        values.update(names)
    return values, chain, "resolved_Study_ID_reference" if len(values) == 1 else "conflicting_Study_ID_origins"


def classify_refinement(programs, potential):
    """Classify the current model, never inherit flexibility from its input geometry."""
    engines = {name for name in ("DMAREL", "DMACRYS") if re.search(r"\b" + name + r"(?=\b|_)", programs, re.I)}
    flexible_program = re.search(FLEXIBLE, programs, re.I)
    flexible_potential = re.search(FLEXIBLE, potential, re.I)
    if len(engines) > 1:
        return "", "", "multiple_refinement_engines_without_explicit_final_assignment"
    engine = next(iter(engines), "")
    engine_rule = "explicit_current_program"
    if not engine and flexible_program and re.search(r"crystal\s*opt|crystopt", programs, re.I):
        engine = "DMACRYS"
        engine_rule = "documented_CrystalOptimizer_DMACRYS_coupling"
    if not engine:
        return "", "", "refinement_engine_not_reported"
    if re.search(r"unoptimi[sz]ed|single[ -]?point", programs, re.I):
        return engine, "", "optimization_not_established_for_current_model"
    if re.search(r"DFTB", programs + " " + potential, re.I):
        return engine, "", "DFTB_sequence_requires_intramolecular_constraint_review"
    if flexible_program:
        return engine, "Flexible", engine_rule + "; explicit_flexible_refinement_program"
    if flexible_potential:
        if mentioned_searches(programs):
            return engine, "Flexible", engine_rule + "; explicit_flexible_postprocessing_in_current_workflow_description"
        return engine, "", "flexible_method_in_potential_but_not_current_programs"
    return engine, "Rigid", engine_rule + "; rigid_body_engine_without_documented_flexible_wrapper"


def main():
    tree = json.loads((BASE / "sources/tree.json").read_text())
    manifest = json.loads((BASE / "manifest.json").read_text())
    assert tree["sha"] == manifest["snapshot_revision"]
    sources, html_hashes = {}, {}
    for blob in tree["tree"]:
        if blob["type"] != "blob" or not blob["path"].endswith(".html"):
            continue
        path = BASE / "sources/html" / (blob["sha"] + ".html")
        if not path.exists():
            continue
        raw = path.read_bytes()
        assert git_sha(raw) == blob["sha"], blob["path"]
        sources[blob["path"]] = parse_case(raw, blob["path"])
        html_hashes[blob["path"]] = blob["sha"]
    index = {}
    for page, parsed in sources.items():
        for search in parsed["searches"]:
            for item in search["models"]:
                if item["kind"] != "energy_model":
                    continue
                key = (page, str(item.get("study_id", "")))
                if key in index:
                    raise ValueError(f"Ambiguous same-page Study_ID: {key}")
                index[key] = dict(item, page_path=page, html_blob_sha=html_hashes[page])
    datasets = pd.read_csv(BASE / "tables/plot_datasets.csv", keep_default_na=False)
    models = pd.read_csv(BASE / "tables/energy_models.csv", keep_default_na=False)
    models = models[models.kind == "energy_model"].copy()
    archives = pd.read_csv(BASE / "tables/structure_archive_counts.csv", keep_default_na=False)
    models["model_id"] = models.model_id.astype(str)
    archives["model_id"] = archives.model_id.astype(str)
    joined = models.merge(archives[["dataset_id", "model_id", "coordinate_files", "archive_url", "git_blob_sha"]],
                          on=["dataset_id", "model_id"], validate="one_to_one")
    assert len(joined) == len(models) == len(archives)
    assert set(joined.dataset_id) == set(datasets.dataset_id)
    initial = {}
    for identifier, group in joined.groupby("dataset_id"):
        first = group[group.model_id == "1"]
        fallback = False
        if len(first) != 1:
            first = group.loc[[group.model_id.astype(int).idxmin()]]
            fallback = True
        row = first.iloc[0]
        source = index[(source_path(row.source_url), str(row.study_id))]
        names, chain, status = trace_search(source, index)
        if fallback:
            status = "energy_model_1_missing; earliest_documented_model: " + status
        initial[identifier] = names, chain, status
    rows = []
    for row in joined.itertuples(index=False):
        page = source_path(row.source_url)
        source = index[(page, str(row.study_id))]
        # The audit and classifier must use the same exact source fields.
        assert source.get("programs", "") == row.programs_raw
        assert source.get("potential description", "") == row.potential_description_raw
        names, chain, search_status = initial[row.dataset_id]
        search = next(iter(names)) if len(names) == 1 else ""
        engine, flexibility, refinement_rule = classify_refinement(row.programs_raw, row.potential_description_raw)
        refs, ambiguous = study_references(row.programs_raw)
        reference_evidence = []
        for identifier in refs:
            target = index.get((page, identifier))
            reference_evidence.append({"study_id": identifier, "status": "ambiguous_alternative" if ambiguous else "found" if target else "not_found",
                                       "programs": target.get("programs", "") if target else "",
                                       "potential_description": target.get("potential description", "") if target else ""})
        included = bool(search and engine and flexibility)
        reasons = ([] if search else [search_status]) + ([] if flexibility and engine else [refinement_rule])
        rows.append({"dataset_id": row.dataset_id, "model_id": row.model_id, "study_id": row.study_id,
                     "archived_structure_model_records": int(row.coordinate_files), "search_program": search,
                     "refinement_engine": engine, "refinement_flexibility": flexibility,
                     "included_in_matrix": included, "search_rule": search_status,
                     "refinement_rule": refinement_rule, "unresolved_reason": "; ".join(reasons),
                     "programs_raw": row.programs_raw, "potential_description_raw": row.potential_description_raw,
                     "intramolecular_description_raw": row.intramolecular_description_raw,
                     "initial_search_evidence": json.dumps(chain, ensure_ascii=False),
                     "current_model_Study_ID_evidence": json.dumps(reference_evidence, ensure_ascii=False),
                     "source_url": row.source_url, "source_html_path": page, "source_html_blob_sha": html_hashes[page],
                     "archive_url": row.archive_url, "archive_git_blob_sha": row.git_blob_sha,
                     "source_revision": tree["sha"]})
    frame = pd.DataFrame(rows).sort_values(["dataset_id", "model_id"])
    assert not frame.duplicated(["dataset_id", "model_id"]).any()
    frame["energy_model_weight"] = 1
    frame["matrix_model_weight"] = frame.included_in_matrix.astype(int)
    frame["matrix_record_weight"] = frame.archived_structure_model_records * frame.matrix_model_weight
    for treatment in ("rigid", "flexible"):
        selected = frame.included_in_matrix & frame.refinement_flexibility.eq(treatment.title())
        frame[f"matrix_{treatment}_model_weight"] = selected.astype(int)
        frame[f"matrix_{treatment}_record_weight"] = selected.astype(int) * frame.archived_structure_model_records
    frame.to_csv(OUT / "model_classification.csv", index=False)
    frame[~frame.included_in_matrix].to_csv(OUT / "unresolved_models.csv", index=False)
    cells = []
    for engine in ["DMAREL", "DMACRYS"]:
        for search in ["MOLPAK", "CrystalPredictor"]:
            part = frame[frame.included_in_matrix & frame.search_program.eq(search) & frame.refinement_engine.eq(engine)]
            rigid = int(part.loc[part.refinement_flexibility.eq("Rigid"), "archived_structure_model_records"].sum())
            flexible = int(part.loc[part.refinement_flexibility.eq("Flexible"), "archived_structure_model_records"].sum())
            rigid_models = int(part.matrix_rigid_model_weight.sum())
            flexible_models = int(part.matrix_flexible_model_weight.sum())
            cells.append({"search_program": search, "refinement_engine": engine, "rigid_records": rigid,
                          "flexible_records": flexible, "total_records": rigid + flexible,
                          "rigid_models": rigid_models, "flexible_models": flexible_models,
                          "energy_models": len(part), "datasets": part.dataset_id.nunique()})
    pd.DataFrame(cells).to_csv(OUT / "matrix_counts.csv", index=False)
    included = frame[frame.included_in_matrix]
    unresolved = frame[~frame.included_in_matrix]
    assert included.archived_structure_model_records.sum() + unresolved.archived_structure_model_records.sum() == datasets.structure_count.sum()
    tnb = frame[frame.dataset_id == "TrinitrobenzeneA"]
    assert set(tnb.model_id.astype(int)) == set(range(1, 10))
    assert tnb.included_in_matrix.all() and tnb.search_program.eq("CrystalPredictor").all()
    assert tnb.refinement_engine.eq("DMACRYS").all() and tnb.refinement_flexibility.eq("Rigid").all()
    summary = {"source_revision": tree["sha"], "source_accessed_date": manifest["accessed_date"],
               "classification_date": "2026-10-28", "inventory_datasets": len(datasets), "energy_models": len(frame),
               "total_archived_records": int(frame.archived_structure_model_records.sum()),
               "classified_models": len(included), "classified_datasets": included.dataset_id.nunique(),
               "classified_archived_records": int(included.archived_structure_model_records.sum()),
               "unresolved_models": len(unresolved), "datasets_with_unresolved_models": unresolved.dataset_id.nunique(),
               "unresolved_archived_records": int(unresolved.archived_structure_model_records.sum()),
               "cell_counts": cells, "unresolved_reason_counts": dict(Counter(unresolved.unresolved_reason)),
               "trinitrobenzene_audit": tnb[["model_id", "archived_structure_model_records"]].to_dict("records"),
               "counting_unit": "RES members per documented energy-model archive; separate model representations retained; no geometric deduplication",
               "method_documentation": REFERENCES,
               "source_table_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in
                                       [BASE / "tables/energy_models.csv", BASE / "tables/structure_archive_counts.csv", BASE / "tables/plot_datasets.csv"]}}
    (OUT / "classification_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
