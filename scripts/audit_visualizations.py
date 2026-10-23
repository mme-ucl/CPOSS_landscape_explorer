#!/usr/bin/env python3
"""Prepare a hash-verified catalogue-wide native visualization audit."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import math
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def fetch(url):
    with urlopen(Request(url, headers={"User-Agent": "CPOSS-Visualization-Audit"}), timeout=90) as response:
        return response.read()


def prepare(args):
    catalogue = json.loads((ROOT / "data/catalogue.json").read_text())
    if args.tree:
        tree = json.loads(args.tree.read_text())
    else:
        tree = json.loads(fetch("https://api.github.com/repos/LouisePrice/CPOSS_Database/git/trees/" + catalogue["sourceTree"] + "?recursive=1"))
    if tree.get("truncated") or tree["sha"] != catalogue["sourceTree"]:
        raise ValueError("Audit inventory must match the complete catalogue source tree")
    files = {item["path"]: item for item in tree["tree"] if item["type"] == "blob"}
    args.cache.mkdir(parents=True, exist_ok=True)
    args.output.mkdir(parents=True, exist_ok=True)
    records = []

    def one(item):
        path = "0.Chemiscope/" + item["filename"]
        blob = files[path]
        filename = blob["sha"] + ".json"
        candidates = [args.cache / filename, args.reuse_cache / filename]
        cached = next((candidate for candidate in candidates if candidate.exists()), None)
        url = "https://raw.githubusercontent.com/LouisePrice/CPOSS_Database/" + tree["sha"] + "/" + quote(path)
        if cached:
            raw = cached.read_bytes()
        elif args.offline:
            raise ValueError("Missing offline source: " + path)
        else:
            raw = fetch(url)
            (args.cache / filename).write_bytes(raw)
        digest = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        if digest != blob["sha"]:
            raise ValueError("Git blob mismatch: " + path)
        dataset = json.loads(raw)
        structures = dataset.get("structures", [])
        geometry_failures = []
        for index, structure in enumerate(structures):
            size = structure.get("size")
            if not isinstance(size, int) or size < 0:
                geometry_failures.append(index)
                continue
            if "data" in structure:
                geometry_failures.append(index)
                continue
            if (any(len(structure.get(key, [])) != size for key in ["names", "x", "y", "z"])
                    or any(not isinstance(value, (int, float)) or not math.isfinite(value)
                           for key in ["x", "y", "z"] for value in structure.get(key, []))
                    or ("cell" in structure and (len(structure["cell"]) != 9 or not all(isinstance(value, (int, float)) and math.isfinite(value) for value in structure["cell"])))):
                geometry_failures.append(index)
        # Real first geometry + all property rows; exercise the native on-demand
        # loader without repeatedly transmitting 1.4 GB of geometry to the browser.
        small = {key: dataset[key] for key in ["meta", "properties", "settings", "environments", "parameters"] if key in dataset}
        small["structures"] = [{"size": structure.get("size", 0), "data": index} for index, structure in enumerate(structures)]
        small["auditFirstStructure"] = structures[0] if structures else None
        (args.output / filename).write_text(json.dumps(small, separators=(",", ":")))
        return {"id": item["id"], "url": url, "blobSha": blob["sha"], "file": filename,
                "bytes": len(raw), "structures": len(structures), "geometryFailures": geometry_failures,
                "sourceKeys": list(dataset), "geometryValidation": "All structure rows checked; native audit renders the original first structure and every scatter row"}

    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs = {pool.submit(one, item): item for item in catalogue["datasets"]}
        for job in as_completed(jobs):
            item = jobs[job]
            try:
                record = job.result()
            except Exception as error:
                record = {"id": item["id"], "error": str(error)}
            records.append(record)
            if "error" in record or len(records) % 40 == 0:
                print(json.dumps({"prepared": len(records), "total": len(jobs), "last": record["id"], "error": record.get("error")}), flush=True)
    manifest = {"sourceTree": tree["sha"], "catalogueCount": len(catalogue["datasets"]), "datasets": sorted(records, key=lambda record: record["id"].lower())}
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"prepared": len(records), "errors": sum("error" in record for record in records)}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tree", type=Path)
    parser.add_argument("--cache", type=Path, default=Path("/tmp/cposs-visualization-cache"))
    parser.add_argument("--reuse-cache", type=Path, default=Path("/tmp/cposs-numbers-json-cache"))
    parser.add_argument("--output", type=Path, default=ROOT / "tests/.audit-data")
    parser.add_argument("--offline", action="store_true")
    prepare(parser.parse_args())
