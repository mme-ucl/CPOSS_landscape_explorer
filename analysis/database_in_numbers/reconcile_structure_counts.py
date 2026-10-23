#!/usr/bin/env python3
"""Read original CPOSS workbooks and reconcile them with visualization exports.

Source workbooks are never modified. XML is read directly to count actual
Filename records rather than styled worksheet dimensions or repeated models.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import posixpath
import re
import xml.etree.ElementTree as ET
import zipfile
from urllib.parse import quote

from analyse import BASE, SITE, RAW, get_bytes, git_sha, site_path, write_json

NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def inspect_workbook(raw):
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        strings = []
        if "xl/sharedStrings.xml" in z.namelist():
            strings = ["".join(n.itertext()) for n in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("s:si", NS)]
        relationships = {r.attrib["Id"]: r.attrib["Target"] for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))}
        sheets, all_ids = [], []
        for sheet in ET.fromstring(z.read("xl/workbook.xml")).findall("s:sheets/s:sheet", NS):
            rid = sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
            target = relationships[rid]
            target = target.lstrip("/") if target.startswith("/") else posixpath.normpath("xl/" + target)
            root = ET.fromstring(z.read(target))
            data = root.findall("s:sheetData/s:row", NS)
            rows = []
            for row in data:
                values = {}
                for cell in row:
                    ref = re.match(r"[A-Z]+", cell.get("r", ""))
                    if not ref:
                        continue
                    value = cell.find("s:v", NS)
                    inline = cell.find("s:is", NS)
                    text = value.text if value is not None else "".join(inline.itertext()) if inline is not None else ""
                    if cell.get("t") == "s" and text:
                        text = strings[int(text)]
                    if text is not None and str(text).strip():
                        values[ref.group(0)] = str(text).strip()
                rows.append(values)
            header_index = next((i for i, row in enumerate(rows[:15]) if any(v.casefold() == "filename" for v in row.values())), None)
            if header_index is None:
                sheets.append({"name": sheet.attrib["name"], "status": "no_filename_header", "nonempty_rows": sum(bool(row) for row in rows)})
                continue
            header = rows[header_index]
            key = next(k for k, v in header.items() if v.casefold() == "filename")
            records = [r for r in rows[header_index + 1:] if r.get(key, "").casefold() not in {"", "filename", "none", "nan"}]
            ids = [r[key] for r in records]
            energies = {v: sum(k in r for r in records) for k, v in header.items() if re.search(r"^Lattice Energy\s*\d*\s*/", v, re.I)}
            energy_nonzero = {v: sum(k in r and r[k] not in {"0", "0.0"} for r in records) for k, v in header.items() if v in energies}
            numeric_energies, nonnumeric = {}, {}
            rows_with_energy = set()
            for column, label in header.items():
                if label not in energies:
                    continue
                valid, invalid = [], []
                for index, row in enumerate(records):
                    if column not in row:
                        continue
                    try:
                        value = float(row[column])
                        if not math.isfinite(value):
                            raise ValueError("nonfinite")
                        valid.append((row[key], value))
                        rows_with_energy.add(index)
                    except ValueError:
                        invalid.append(row[column])
                numeric_energies[label] = {"records": len(valid), "unique_filename_model_pairs": len({name for name, _ in valid}), "zero_energy_records": sum(value == 0 for _, value in valid)}
                if invalid:
                    nonnumeric[label] = dict(Counter(invalid))
            sheets.append({"name": sheet.attrib["name"], "status": "counted", "header_row": header_index + 1, "filename_column": key, "structure_rows": len(ids), "unique_filename_count": len(set(ids)), "duplicate_filename_count": len(ids) - len(set(ids)), "rows_with_any_numeric_lattice_energy": len(rows_with_energy), "energy_column_numeric_counts": numeric_energies, "energy_column_nonnumeric_values": nonnumeric, "energy_column_nonblank_counts": energies, "energy_column_nonzero_counts": energy_nonzero, "header": header})
            all_ids.extend(ids)
        return {"sheets": sheets, "structure_rows_all_sheets": len(all_ids), "unique_filename_count_all_sheets": len(set(all_ids)), "filename_digest": hashlib.sha256("\n".join(sorted(set(all_ids))).encode()).hexdigest()}, set(all_ids)


def main():
    tree = json.loads((BASE / "sources/tree.json").read_text())
    files = {i["path"]: i for i in tree["tree"] if i["type"] == "blob"}
    cache = Path("/tmp/cposs-workbook-cache")
    cache.mkdir(exist_ok=True)
    workbook_files = [p for p in files if p.lower().endswith(".xlsx")]
    summaries, id_sets = {}, {}

    def work(path):
        blob = files[path]
        target = cache / (blob["sha"] + ".xlsx")
        raw = target.read_bytes() if target.exists() else get_bytes(RAW + tree["sha"] + "/" + quote(path))
        if git_sha(raw) != blob["sha"]:
            raise ValueError("Workbook checksum mismatch: " + path)
        if not target.exists():
            target.write_bytes(raw)
        summary, ids = inspect_workbook(raw)
        summary.update({"path": path, "git_blob_sha": blob["sha"], "bytes": len(raw), "source_url": SITE + path, "status": "calculated"})
        return path, summary, ids

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(work, p): p for p in workbook_files}
        for i, fut in enumerate(as_completed(futures), 1):
            path = futures[fut]
            try:
                _, row, ids = fut.result()
                summaries[path], id_sets[path] = row, ids
            except Exception as exc:
                summaries[path] = {"path": path, "status": "missing", "error": str(exc)}
            if i % 40 == 0 or i == len(futures):
                write_json(BASE / "sources/workbook_summaries.json", summaries)
                print(f"Workbooks inspected: {i}/{len(futures)}", flush=True)
    write_json(BASE / "sources/workbook_summaries.json", summaries)
    import pandas as pd
    datasets = pd.read_csv(BASE / "tables/datasets.csv", keep_default_na=False)
    models = pd.read_csv(BASE / "tables/energy_models.csv", keep_default_na=False)
    comparison = []
    used = set()
    for dataset in datasets.itertuples():
        downloads = models.loc[(models.dataset_id == dataset.dataset_id) & (models.kind == "energy_model"), "downloads"]
        directories = {str(Path(p).parent) for text in downloads for href in text.split(" | ") if (p := site_path(href))}
        candidates = [p for p in workbook_files if str(Path(p).parent) in directories]
        method = "same directory as explicitly linked search archive"
        if not candidates:
            candidates = [p for p in workbook_files if Path(p).stem == dataset.dataset_id]
            method = "exact filename stem"
        candidates = list(dict.fromkeys(candidates))
        row = {"dataset_id": dataset.dataset_id, "source_url": dataset.source_url, "visualization_entries": dataset.structure_count, "workbook_path": " | ".join(candidates), "mapping_rule": method, "candidate_count": len(candidates)}
        if len(candidates) == 1 and candidates[0] in id_sets:
            p = candidates[0]
            used.add(p)
            row.update({"workbook_rows": summaries[p]["structure_rows_all_sheets"], "workbook_unique_filenames": len(id_sets[p]), "workbook_url": SITE + p, "workbook_git_blob_sha": files[p]["sha"], "status": "calculated"})
            data_sheets = [s for s in summaries[p]["sheets"] if s.get("status") == "counted"]
            row["rows_with_any_model_energy"] = sum(s["rows_with_any_numeric_lattice_energy"] for s in data_sheets)
            row["structure_model_records"] = sum(v["records"] for s in data_sheets for v in s["energy_column_numeric_counts"].values())
            row["unique_filename_model_pairs"] = sum(v["unique_filename_model_pairs"] for s in data_sheets for v in s["energy_column_numeric_counts"].values())
            json_path = site_path(dataset.json_url)
            if json_path in files:
                source = Path("/tmp/cposs-numbers-json-cache") / (files[json_path]["sha"] + ".json")
                if source.exists():
                    data = json.loads(source.read_bytes())
                    vals = next((v["values"] for k, v in data.get("properties", {}).items() if k.casefold() == "filename"), [])
                    ids = set(map(str, vals))
                    row["visualization_unique_filenames"] = len(ids)
                    row["visualization_ids_not_in_workbook"] = len(ids - id_sets[p])
                    row["workbook_ids_not_in_visualization"] = len(id_sets[p] - ids)
        else:
            row["status"] = "ambiguous" if len(candidates) > 1 else "missing"
        comparison.append(row)
    df = pd.DataFrame(comparison)
    df.to_csv(BASE / "tables/structure_count_reconciliation.csv", index=False)
    model_records = []
    for row in comparison:
        if row["status"] != "calculated":
            continue
        for sheet in summaries[row["workbook_path"]]["sheets"]:
            for label, stats in sheet.get("energy_column_numeric_counts", {}).items():
                # An unnumbered column is not silently assigned to model 1:
                # GuanineC has both numbered and different unnumbered energies.
                model_id = re.search(r"Lattice Energy\s*(\d*)", label).group(1) or "unassigned"
                match = models[(models.dataset_id == row["dataset_id"]) & (models.model_id.astype(str) == model_id) & (models.kind == "energy_model")]
                model_records.append({"dataset_id": row["dataset_id"], "model_id": model_id, "energy_column": label, "sheet": sheet["name"], **stats, "workbook_path": row["workbook_path"], "workbook_url": row["workbook_url"], "html_model_matches": len(match), "archive_url": " | ".join(match.downloads)})
    pd.DataFrame(model_records).to_csv(BASE / "tables/structure_model_counts.csv", index=False)
    unmapped = [{"path": p, "unique_filenames": s.get("unique_filename_count_all_sheets"), "structure_rows": s.get("structure_rows_all_sheets"), "sheets": json.dumps(s.get("sheets", []))} for p, s in summaries.items() if p not in used]
    pd.DataFrame(unmapped).to_csv(BASE / "tables/unmapped_workbooks.csv", index=False)
    report = {"snapshot_revision": tree["sha"], "workbooks_in_inventory": len(workbook_files), "workbooks_successfully_read": len(id_sets), "all_workbook_rows": sum(s.get("structure_rows_all_sheets", 0) for s in summaries.values()), "all_workbook_unique_filename_sum": sum(len(ids) for ids in id_sets.values()), "mapped_datasets": int((df.status == "calculated").sum()), "missing_datasets": df.loc[df.status != "calculated", "dataset_id"].tolist(), "mapped_workbook_rows": int(df.workbook_rows.sum()), "mapped_workbook_unique_filename_sum": int(df.workbook_unique_filenames.sum()), "rows_with_any_model_energy": int(df.rows_with_any_model_energy.sum()), "structure_model_records": int(df.structure_model_records.sum()), "unique_filename_model_pairs": int(df.unique_filename_model_pairs.sum()), "zero_energy_records": sum(m["zero_energy_records"] for m in model_records), "model_columns": len(model_records), "model_columns_without_html_match": sum(m["html_model_matches"] != 1 for m in model_records), "nonnumeric_energy_values": {p: [s["energy_column_nonnumeric_values"] for s in w.get("sheets", []) if s.get("energy_column_nonnumeric_values")] for p, w in summaries.items() if any(s.get("energy_column_nonnumeric_values") for s in w.get("sheets", []))}, "visualization_entries": int(pd.to_numeric(df.visualization_entries, errors="coerce").sum()), "unmapped_workbooks": len(unmapped), "read_failures": [p for p, s in summaries.items() if s["status"] != "calculated"]}
    write_json(BASE / "sources/structure_count_reconciliation.json", report)
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
