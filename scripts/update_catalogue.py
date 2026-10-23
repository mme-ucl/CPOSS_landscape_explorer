#!/usr/bin/env python3
"""Refresh navigator metadata from actual CPOSS case-page links (Python 3.9+)."""

import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from html.parser import HTMLParser
import hashlib
import json
from pathlib import Path
import re
import time
from urllib.parse import parse_qs, quote, unquote, urljoin, urlsplit
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
SITE = "https://louiseprice.github.io/CPOSS_Database/"
RAW = "https://raw.githubusercontent.com/LouisePrice/CPOSS_Database/"
TREE_URL = "https://api.github.com/repos/LouisePrice/CPOSS_Database/git/trees/main?recursive=1"
FAMILIES = "0.DatabaseWeb/molecule_list4.html"
COLLECTIONS = [
    ("BlindTest", "Blind Test candidates"),
    ("CPOSS209", "CPOSS209 molecules"),
    ("unpublished", "Systems without a published crystal structure"),
    ("Tricyclics", "TricyclicCycloheptanes and similar"),
    ("Dichloronitrobenzene", "Dichloronitrobenzenes"),
]


def clean(value):
    return " ".join(value.split())


class Node:
    def __init__(self, tag="", attrs=None, parent=None):
        self.tag, self.attrs, self.parent = tag, dict(attrs or []), parent
        self.children = []

    def walk(self, tag=None):
        for child in self.children:
            if isinstance(child, Node):
                if tag is None or child.tag == tag:
                    yield child
                yield from child.walk(tag)

    def text(self):
        if self.tag in ("script", "style"):
            return ""
        return clean(" ".join(c.text() if isinstance(c, Node) else c for c in self.children))


class Document(HTMLParser):
    """Small HTML tree reader; tolerates legacy mismatched closing table tags."""

    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "wbr"}

    def __init__(self, source):
        super().__init__(convert_charrefs=True)
        self.root = Node()
        self.current = self.root
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        child = Node(tag, attrs, self.current)
        self.current.children.append(child)
        if tag not in self.VOID:
            self.current = child

    def handle_startendtag(self, tag, attrs):
        self.current.children.append(Node(tag, attrs, self.current))

    def handle_endtag(self, tag):
        node = self.current
        while node.parent is not None:
            if node.tag == tag:
                self.current = node.parent
                return
            node = node.parent

    def handle_data(self, data):
        self.current.children.append(data)


def database_path(url, base=SITE):
    parsed = urlsplit(urljoin(base, url))
    if parsed.netloc.casefold() == "louiseprice.github.io" and parsed.path.startswith("/CPOSS_Database/"):
        return unquote(parsed.path[len("/CPOSS_Database/"):])
    if parsed.netloc.casefold() == "raw.githubusercontent.com":
        parts = unquote(parsed.path).split("/")
        if len(parts) >= 5 and parts[1].casefold() == "louiseprice" and parts[2] == "CPOSS_Database":
            return "/".join(parts[4:])
    return None


def dataset_filename(href):
    parsed = urlsplit(href)
    target = parse_qs(parsed.query).get("load", [href])[0]
    path = database_path(target)
    if path and path.startswith("0.Chemiscope/") and path.lower().endswith(".json"):
        return Path(path).name
    return None


def value_text(cell):
    # Metadata/search values often contain a nested table with download buttons.
    nested = next(cell.walk("tr"), None)
    return nested.text() if nested else cell.text()


def parse_case(source):
    root = Document(source).root
    headings = [n.text() for n in root.walk() if n.tag in ("h1", "h2")]
    heading = next((x for x in headings if x and not x.startswith("Warning:")), "")
    metadata, searches = {}, []
    current = None
    for row in root.walk("tr"):
        cells = [n for n in row.children if isinstance(n, Node) and n.tag in ("td", "th")]
        if len(cells) != 2:
            continue
        key, value = clean(cells[0].text()).casefold(), cells[1]
        if key in ("refcode", "formula", "common name", "iupac systematic name", "other names", "csd refcodes") and current is None:
            metadata[key] = value_text(value)
        elif key == "search identifier":
            current = {"code": value_text(value), "filenames": [], "models": []}
            for link in value.walk("a"):
                filename = dataset_filename(link.attrs.get("href", ""))
                if filename and filename not in current["filenames"]:
                    current["filenames"].append(filename)
            searches.append(current)
        elif current is not None and key in ("energy model", "pdft structures"):
            downloads = [a.attrs["href"].replace("http://", "https://", 1) for a in value.walk("a") if a.attrs.get("href")]
            current["models"].append({"id": value_text(value), "downloads": downloads})
        elif current is not None and key == "study_id" and current["models"]:
            current["models"][-1]["studyId"] = value_text(value)
    # Some newer page templates place dataset links outside legacy search tables.
    linked = {dataset_filename(a.attrs.get("href", "")) for a in root.walk("a")}
    assigned = {f for search in searches for f in search["filenames"]}
    for filename in sorted(linked - assigned - {None}):
        searches.append({"code": "", "filenames": [filename], "models": []})
    return heading, metadata, searches


def parse_lists(sources, known_pages):
    aliases = defaultdict(set)
    memberships = defaultdict(set)
    invalid = []
    collection_ids = {x[0] for x in COLLECTIONS}
    for path, source in sources.items():
        section = None
        for node in Document(source).root.walk():
            anchor = node.attrs.get("name") or node.attrs.get("id")
            if path == FAMILIES and anchor in collection_ids:
                section = anchor
            if node.tag != "a" or not node.attrs.get("href"):
                continue
            target = database_path(node.attrs["href"], SITE + path)
            if not target or not target.endswith(".html") or target.startswith("0.DatabaseWeb/"):
                continue
            if target not in known_pages:
                invalid.append({"source": path, "target": target})
                continue
            if node.text():
                aliases[target].add(node.text())
            if path == FAMILIES and section:
                memberships[target].add(section)
    return aliases, memberships, invalid


def fetch(url):
    for attempt in range(3):
        try:
            request = Request(url, headers={"User-Agent": "CPOSS-Navigator-Catalogue", "Accept": "application/json, text/html, */*"})
            with urlopen(request, timeout=40) as response:
                return response.read()
        except Exception:
            if attempt == 2:
                raise
            time.sleep(attempt + 1)


def search_resources(models, page_url, files):
    """Use linked archives and actual sibling spreadsheet paths from the tree."""
    result, directories = [], set()
    for model in models:
        downloads = []
        for href in model["downloads"]:
            url = urljoin(page_url, href)
            path = database_path(url)
            if path in files and path.lower().endswith(".zip"):
                downloads.append(url.replace("http://", "https://", 1))
                directories.add(str(Path(path).parent))
        result.append({**model, "downloads": downloads})
    metadata = [{"url": SITE + quote(path), "label": Path(path).name}
                for path in sorted(files) if str(Path(path).parent) in directories and path.lower().endswith((".xlsx", ".csv", ".tsv"))]
    return result, metadata


def build_catalogue(tree, sources):
    if tree.get("truncated"):
        raise ValueError("GitHub returned a truncated file inventory; refusing an incomplete refresh")
    files = {x["path"] for x in tree["tree"] if x["type"] == "blob"}
    case_paths = {p for p in files if p.endswith(".html") and "/" in p and not p.startswith("0.DatabaseWeb/")}
    lists = {p: s for p, s in sources.items() if p.startswith("0.DatabaseWeb/")}
    aliases, memberships, broken = parse_lists(lists, case_paths)
    datasets = {}
    for path in sorted(files, key=str.casefold):
        if path.startswith("0.Chemiscope/") and path.lower().endswith(".json"):
            name = Path(path).name
            datasets[name] = {"id": name[:-5], "filename": name, "url": RAW + "main/" + quote(path), "label": name[:-5], "molecule": "", "aliases": [], "codes": [], "collections": [], "cases": []}
    for path in sorted(case_paths):
        heading, metadata, searches = parse_case(sources[path])
        common = heading or metadata.get("common name", "")
        names = sorted({clean(x) for x in [heading, metadata.get("common name", ""), metadata.get("iupac systematic name", ""), *aliases[path], *re.split(r"[;\n]", metadata.get("other names", ""))]} - {""})
        codes = re.findall(r"[A-Za-z][A-Za-z0-9_-]*", metadata.get("refcode", "") + " " + metadata.get("csd refcodes", ""))
        for alias in names:
            codes.extend("BT" + match for match in re.findall(r"Blind Test\s+([IVXLCDM]+)\b", alias, flags=re.I))
        for search in searches:
            for name in search["filenames"]:
                if name not in datasets:
                    broken.append({"source": path, "target": "0.Chemiscope/" + name})
                    continue
                item = datasets[name]
                page_url = SITE + quote(path)
                models, metadata_downloads = search_resources(search["models"], page_url, files)
                page = {"url": page_url, "molecule": common, "search": search["code"], "models": models, "metadataDownloads": metadata_downloads}
                item["cases"].append(page)
                item["aliases"] = sorted(set(item["aliases"]) | set(names))
                item["codes"] = sorted(set(item["codes"]) | set(codes))
                item["collections"] = sorted(set(item["collections"]) | memberships[path])
                if not item["molecule"]:
                    item["molecule"] = common
                    item["label"] = common + (" — Search " + search["code"] if search["code"] else " — " + item["id"])
    items = list(datasets.values())
    counts = {key: sum(key in x["collections"] for x in items) for key, _ in COLLECTIONS}
    report = {
        "datasetCount": len(items), "casePageCount": len(case_paths),
        "mappedDatasetCount": sum(bool(x["cases"]) for x in items),
        "collectionCounts": counts,
        "unmappedDatasets": [x["filename"] for x in items if not x["cases"]],
        "multipleCaseMappings": [x["filename"] for x in items if len(x["cases"]) > 1],
        "brokenSourceLinks": broken,
        "collectionCasesWithoutDatasets": {key: sorted(path for path in case_paths if key in memberships[path] and not any(SITE + quote(path) == c["url"] for x in items for c in x["cases"])) for key, _ in COLLECTIONS},
        "validation": "Dataset, case, archive and metadata paths checked against the complete GitHub tree. Archive contents are labelled only when a separate content audit matches the current Git blob SHA. Other archive contents and external publication URLs are not fetched.",
    }
    catalogue = {"schemaVersion": 1, "sourceTree": tree["sha"], "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"), "collections": [{"id": key, "label": label, "sourceUrl": SITE + FAMILIES + "#" + key, "count": counts[key]} for key, label in COLLECTIONS], "datasets": items}
    return catalogue, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, default=Path("/tmp/cposs-catalogue-cache"), help="HTML cache, keyed by Git blob SHA")
    parser.add_argument("--tree", type=Path, help="Use a previously fetched complete GitHub tree JSON")
    parser.add_argument("--offline", action="store_true", help="Read only cached HTML (requires --tree)")
    parser.add_argument("--output", type=Path, default=ROOT / "data")
    args = parser.parse_args()
    if args.offline and not args.tree:
        parser.error("--offline requires --tree")
    tree = json.loads(args.tree.read_text() if args.tree else fetch(TREE_URL))
    if tree.get("truncated"):
        raise ValueError("GitHub file inventory is truncated")
    blobs = [x for x in tree["tree"] if x["type"] == "blob" and x["path"].endswith(".html") and "/" in x["path"]]
    args.cache.mkdir(parents=True, exist_ok=True)
    def read(blob):
        path = blob["path"]
        cached = args.cache / (blob["sha"] + ".html")
        if not cached.exists():
            if args.offline:
                raise ValueError("Missing cached page: " + path)
            data = fetch(RAW + tree["sha"] + "/" + quote(path))
            digest = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
            if digest != blob["sha"]:
                raise ValueError("Source hash mismatch: " + path)
            cached.write_bytes(data)
        data = cached.read_bytes()
        # Pages declare legacy Latin-1 headers but are generally UTF-8.
        try:
            return path, data.decode("utf-8")
        except UnicodeDecodeError:
            return path, data.decode("cp1252")
    sources, errors = {}, []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(read, blob): blob["path"] for blob in blobs}
        for future in as_completed(futures):
            try:
                path, source = future.result()
                sources[path] = source
            except Exception as error:
                errors.append(f"{futures[future]}: {error}")
    if errors:
        raise RuntimeError("Refresh aborted; existing catalogue preserved:\n" + "\n".join(errors))
    catalogue, report = build_catalogue(tree, sources)
    # Content labels expire automatically when an upstream archive changes.
    audit_file = ROOT / "data/archive-contents.json"
    blobs_by_path = {x["path"]: x["sha"] for x in tree["tree"] if x["type"] == "blob"}
    audits = json.loads(audit_file.read_text()).get("archives", []) if audit_file.exists() else []
    catalogue["archiveContents"] = {item["url"]: item for item in audits
                                    if blobs_by_path.get(database_path(item["url"])) == item["blobSha"]}
    report["sourceTree"] = tree["sha"]
    args.output.mkdir(parents=True, exist_ok=True)
    for name, value in [("catalogue.json", catalogue), ("catalogue-report.json", report)]:
        (args.output / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("datasetCount", "casePageCount", "mappedDatasetCount", "collectionCounts", "unmappedDatasets", "brokenSourceLinks")}, indent=2))


if __name__ == "__main__":
    main()
