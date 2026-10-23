"""Spot-check workbook model counts against actual downloadable RES files."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import io
import json
from pathlib import Path
from urllib.parse import quote
import zipfile

import pandas as pd
from analyse import BASE, RAW, get_bytes, git_sha, site_path, write_json


def main():
    inventory = json.loads((BASE / "sources/tree.json").read_text())
    files = {r["path"]: r for r in inventory["tree"] if r["type"] == "blob"}
    counts = pd.read_csv(BASE / "tables/structure_model_counts.csv", keep_default_na=False)
    chosen = counts[counts.dataset_id.isin(["AspirinA", "UreaA", "TrinitrobenzeneA", "BTXXXIIA"])]
    cache = Path("/tmp/cposs-model-archive-cache")
    cache.mkdir(exist_ok=True)

    def inspect(row):
        path = site_path(row.archive_url)
        blob = files[path]
        target = cache / (blob["sha"] + ".zip")
        raw = target.read_bytes() if target.exists() else get_bytes(RAW + inventory["sha"] + "/" + quote(path), timeout=180)
        if git_sha(raw) != blob["sha"]:
            raise ValueError("Archive checksum mismatch")
        if not target.exists():
            target.write_bytes(raw)
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            res_files = [i for i in z.infolist() if not i.is_dir() and i.filename.lower().endswith(".res") and not i.filename.startswith("__MACOSX/") and not Path(i.filename).name.startswith("._")]
        return {"dataset_id": row.dataset_id, "model_id": row.model_id, "workbook_records": row.records, "res_files": len(res_files), "counts_match": len(res_files) == row.records, "archive_path": path, "archive_url": row.archive_url, "git_blob_sha": blob["sha"]}

    results = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(inspect, row) for row in chosen.itertuples()]
        for fut in as_completed(futures):
            result = fut.result()
            results.append(result)
            print(f"{result['dataset_id']} model {result['model_id']}: workbook {result['workbook_records']}, RES {result['res_files']}", flush=True)
    pd.DataFrame(results).sort_values(["dataset_id", "model_id"]).to_csv(BASE / "tables/archive_count_spotchecks.csv", index=False)
    write_json(BASE / "sources/archive_count_spotchecks.json", {"snapshot_revision": inventory["sha"], "archives_checked": len(results), "matching_counts": sum(r["counts_match"] for r in results), "results": results})


if __name__ == "__main__":
    main()
