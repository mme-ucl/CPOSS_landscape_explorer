#!/usr/bin/env python3
"""Count coordinate members in every explicitly documented energy-model ZIP.

Uses the frozen HTML model relationships and verifies downloaded Git blobs.
Counts coordinate files, not crystallographically deduplicated geometries.
Original archives are read-only and cached outside the deliverable.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter
import json
from pathlib import Path
from urllib.parse import quote
import zipfile

import pandas as pd
from analyse import BASE, RAW, get_bytes, git_sha, site_path, write_json


def inspect_archive(path):
    with zipfile.ZipFile(path) as archive:
        members = [i for i in archive.infolist() if not i.is_dir()]
        excluded = [i for i in members if "__MACOSX" in Path(i.filename).parts or Path(i.filename).name.startswith("._")]
        useful = [i for i in members if i not in excluded]
        extensions = Counter(Path(i.filename).suffix.lower() for i in useful)
        formats = [suffix for suffix in [".res", ".cif", ".pdb", ".xyz"] if extensions[suffix]]
        primary = formats[0] if formats else ""
        coordinates = [i for i in useful if Path(i.filename).suffix.lower() == primary] if primary else []
        return {
            "coordinate_files": len(coordinates) if primary else None,
            "primary_format": primary,
            "res_files": extensions[".res"], "cif_files": extensions[".cif"],
            "pdb_files": extensions[".pdb"], "xyz_files": extensions[".xyz"],
            "duplicate_member_names": len(coordinates) - len({i.filename for i in coordinates}),
            "excluded_macos_members": len(excluded),
            "extension_inventory": json.dumps(dict(sorted(extensions.items()))),
            "status": "calculated" if primary else "missing",
        }


def main():
    tree = json.loads((BASE / "sources/tree.json").read_text())
    files = {r["path"]: r for r in tree["tree"] if r["type"] == "blob"}
    models = pd.read_csv(BASE / "tables/energy_models.csv", keep_default_na=False)
    counts = pd.read_csv(BASE / "tables/structure_model_counts.csv", keep_default_na=False)
    cache = Path("/tmp/cposs-model-archive-cache")
    cache.mkdir(exist_ok=True)

    def inspect(row):
        links = row.downloads.split(" | ")
        if len(links) != 1:
            raise ValueError("Expected one model archive: " + row.dataset_id)
        path = site_path(links[0])
        blob = files[path]
        target = cache / (blob["sha"] + ".zip")
        raw = target.read_bytes() if target.exists() else get_bytes(RAW + tree["sha"] + "/" + quote(path), timeout=180)
        if git_sha(raw) != blob["sha"]:
            raise ValueError("Archive checksum mismatch: " + path)
        if not target.exists():
            target.write_bytes(raw)
        matching = counts[(counts.dataset_id == row.dataset_id) & (counts.model_id.astype(str) == str(row.model_id))]
        record = {"dataset_id": row.dataset_id, "model_id": row.model_id, "archive_path": path,
                  "archive_url": links[0], "source_url": row.source_url,
                  "git_blob_sha": blob["sha"], "bytes": len(raw),
                  "workbook_records": int(matching.records.sum()) if len(matching) == 1 else None}
        record.update(inspect_archive(target))
        record["counts_match"] = record["coordinate_files"] == record["workbook_records"]
        return record

    results = []
    targets = list(models[models.kind == "energy_model"].itertuples())
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(inspect, row): row for row in targets}
        for i, future in enumerate(as_completed(futures), 1):
            row = futures[future]
            try:
                results.append(future.result())
            except Exception as exc:
                results.append({"dataset_id": row.dataset_id, "model_id": row.model_id, "archive_url": row.downloads,
                                "source_url": row.source_url, "status": "missing", "error": str(exc)})
            if i % 25 == 0 or i == len(targets):
                pd.DataFrame(results).sort_values(["dataset_id", "model_id"]).to_csv(BASE / "tables/structure_archive_counts.csv", index=False)
                print(f"Archives inspected: {i}/{len(targets)}", flush=True)
    frame = pd.DataFrame(results).sort_values(["dataset_id", "model_id"])
    frame.to_csv(BASE / "tables/structure_archive_counts.csv", index=False)
    grouped = frame.groupby("dataset_id").agg(
        archive_coordinate_files=("coordinate_files", lambda s: s.sum(min_count=1)),
        archives=("model_id", "count"), counted_archives=("status", lambda s: (s == "calculated").sum()),
        archive_urls=("archive_url", lambda s: " | ".join(s)),
    ).reset_index()
    grouped["complete"] = grouped.archives == grouped.counted_archives
    grouped.to_csv(BASE / "tables/dataset_archive_counts.csv", index=False)
    report = {"snapshot_revision": tree["sha"], "archives_expected": len(targets),
              "archives_counted": int(frame.status.eq("calculated").sum()), "datasets": len(grouped),
              "datasets_complete": int(grouped.complete.sum()),
              "coordinate_files": int(frame.coordinate_files.sum()),
              "res_files": int(frame.res_files.sum()), "cif_files": int(frame.cif_files.sum()),
              "pdb_files": int(frame.pdb_files.sum()), "xyz_files": int(frame.xyz_files.sum()),
              "duplicate_member_names": int(frame.duplicate_member_names.sum()),
              "unique_archive_blobs": int(frame.git_blob_sha.nunique()),
              "verified_archive_bytes": int(frame.bytes.sum()),
              "excluded_macos_members": int(frame.excluded_macos_members.sum()),
              "matching_workbook_counts": int(frame.counts_match.fillna(False).sum()),
              "failures": frame.loc[frame.status.ne("calculated"), ["dataset_id", "model_id", "archive_url"]].to_dict("records"),
              "count_definition": "Coordinate members in each documented energy-model archive; RES preferred, otherwise CIF/PDB/XYZ. MacOS resource forks excluded. Separate models retained. No cross-file geometric deduplication; a CIF member is a file count, not a count of its data blocks."}
    write_json(BASE / "sources/structure_archive_counts.json", report)
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
