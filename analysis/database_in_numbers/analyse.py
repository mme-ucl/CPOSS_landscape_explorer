#!/usr/bin/env python3
"""Reproducible CPOSS metadata extraction and A4 matplotlib figure.

The unit of analysis is an explicitly documented CSP search, not an energy
model, a molecule page, or an unlinked JSON file. See README.md and report.md.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict, deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import time
from urllib.parse import parse_qs, quote, unquote, urljoin, urlsplit
from zoneinfo import ZoneInfo

os.environ.setdefault("MPLCONFIGDIR", "/tmp/cposs-matplotlib")
import numpy as np
import pandas as pd
import requests

BASE = Path(__file__).resolve().parent
SITE = "https://louiseprice.github.io/CPOSS_Database/"
API = "https://api.github.com/repos/LouisePrice/CPOSS_Database/git/trees/main?recursive=1"
RAW = "https://raw.githubusercontent.com/LouisePrice/CPOSS_Database/"
MISSING = {"", "none", "unknown", "not sure", "n/a", "not available"}


def clean(value):
    return " ".join(str(value).split())


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
    """Tolerates the legacy source's mismatched table closing tags."""
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


def cells(node):
    return [c for c in node.children if isinstance(c, Node) and c.tag in ("td", "th")]


def value_text(node):
    first_row = next(node.walk("tr"), None)
    return first_row.text() if first_row else node.text()


def site_path(href, base=SITE):
    p = urlsplit(urljoin(base, href))
    if p.netloc.lower() == "louiseprice.github.io" and p.path.startswith("/CPOSS_Database/"):
        return unquote(p.path[len("/CPOSS_Database/"):])
    if p.netloc.lower() == "raw.githubusercontent.com":
        chunks = unquote(p.path).split("/")
        if len(chunks) >= 5 and chunks[1].lower() == "louiseprice" and chunks[2] == "CPOSS_Database":
            return "/".join(chunks[4:])
    return None


def json_target(href, base):
    target = parse_qs(urlsplit(href).query).get("load", [href])[0]
    p = site_path(target, base)
    return p if p and p.startswith("0.Chemiscope/") and p.lower().endswith(".json") else None


def decode_html(raw):
    # The legacy declaration says Latin-1 even when the actual file is UTF-8.
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("cp1252", errors="replace")


def git_sha(raw):
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def reference(href, citation, context, scope):
    """Keep source URLs, recovering three visibly truncated legacy Wiley DOIs."""
    raw_url = href
    status = "reported"
    if "::aid-" in href.lower() and ">" not in href:
        compact = re.sub(r"\s+", "", citation)
        match = re.search(r"10\.\d{4,9}/.+", compact)
        if match and ">" in match.group(0):
            href = "https://doi.org/" + quote(match.group(0), safe="/():;-")
            status = "inferred"
    return {"url": href, "raw_url": raw_url, "doi_status": status, "citation": citation, "context": context, "scope": scope}


def get_bytes(url, timeout=90):
    for attempt in range(3):
        try:
            r = requests.get(url, timeout=timeout, headers={"User-Agent": "CPOSS-database-in-numbers/1.0"})
            r.raise_for_status()
            return r.content
        except requests.RequestException:
            if attempt == 2:
                raise
            time.sleep(attempt + 1)


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, default=str) + "\n")


def parse_case(raw, path):
    root = Document(decode_html(raw)).root
    heading = next((n.text() for n in root.walk() if n.tag == "h2" and not n.text().startswith("Warning:")), "")
    meta, searches, context_refs = {}, [], []
    current, model, in_csd = None, None, False
    for node in root.walk():
        if node.tag == "h3" and node.text().startswith("CSD structures"):
            in_csd = True
            current = model = None
        if node.tag != "tr":
            continue
        cc = cells(node)
        if in_csd and len(cc) > 3 and not any(c.tag == "th" for c in cc):
            for a in node.walk("a"):
                href = a.attrs.get("href", "")
                if href.startswith(("https://", "http://")):
                    context_refs.append(reference(href, a.text(), node.text(), "experimental_context"))
        if len(cc) != 2:
            continue
        key, val = cc[0].text().casefold(), cc[1]
        if key in {"refcode", "formula", "common name", "iupac systematic name", "other names", "csd refcodes"} and current is None and not in_csd:
            meta[key] = value_text(val)
        elif key == "search identifier" and not in_csd:
            current = {"search": value_text(val), "json_paths": [], "models": [], "publications": [], "page_path": path}
            for a in val.walk("a"):
                target = json_target(a.attrs.get("href", ""), SITE + path)
                if target and target not in current["json_paths"]:
                    current["json_paths"].append(target)
            searches.append(current)
            model = None
        elif current is not None:
            if key in {"scientist", "date"}:
                current[key] = value_text(val)
            elif key == "publication":
                current["publication_raw"] = val.text()
                current["publications"] = [reference(a.attrs.get("href", ""), a.text(), val.text(), "csp_study") for a in val.walk("a") if a.attrs.get("href", "").startswith(("https://", "http://"))]
            elif key == "energy model":
                model = {"model_id": value_text(val), "kind": "energy_model", "downloads": [urljoin(SITE + path, a.attrs["href"]) for a in val.walk("a") if a.attrs.get("href")]}
                current["models"].append(model)
            elif key == "pdft structures":
                current["models"].append({"model_id": "pDFT", "kind": "supplementary_periodic_DFT", "downloads": [urljoin(SITE + path, a.attrs["href"]) for a in val.walk("a") if a.attrs.get("href")]})
            elif model is not None and key in {"study_id", "programs", "potential description", "intramolecular description", "location on s drive"}:
                model[key] = value_text(val)
    return {"heading": heading, "metadata": meta, "searches": searches, "context_refs": context_refs}


def study_year(text):
    """Use a single reported study year; intervals and upper bounds stay missing."""
    years = re.findall(r"\b(?:19|20)\d{2}\b", text or "")
    if len(set(years)) == 1 and not re.search(r"pre|before|\d\s*[-–/]\s*\d", text or "", re.I):
        return int(years[0])
    return None


def scientists(text):
    if clean(text).lower() in MISSING:
        return []
    # Parentheses indicate additional credited people, not a stated role.
    tokens = re.split(r"\s*(?:/|;|,|\band\b|\(|\))\s*", text)
    # Sally (Sarah) Price and Louise Price are different scientists.
    aliases = {"L Price": "Louise Price"}
    return [(aliases.get(t, t), "additional credit (parenthesised)" if re.search(r"\([^)]*" + re.escape(t) + r"[^)]*\)", text) else "scientist (source field)", t) for t in tokens if t and t.lower() not in MISSING]


def parse_formula(text):
    """Conservative formula-unit parser; never confuse formula and unit cell.

    Accepts integer group multipliers and explicit component separators. Keeps
    the written formula unit, rather than reducing hydrate stoichiometry.
    """
    from rdkit.Chem import GetPeriodicTable
    pt = GetPeriodicTable()
    if not text or text.lower() in MISSING:
        return {"status": "missing", "reason": "No formula reported"}
    separated = re.sub(r"\s+-\s+", "|", text)
    separated = re.sub(r"\s+\+\s+(?=[A-Z])", "|", separated)
    compact = re.sub(r"\s+", "", separated)
    multicomponent = bool(re.search(r"[.·|]", compact))
    compact = compact.replace("+", "").replace("-", "")
    parts = re.split(r"[.·|]", compact)
    counts = Counter()
    for part in parts:
        if not part:
            return {"status": "missing", "reason": "Empty formula component"}
        tokens = re.findall(r"[A-Z][a-z]?|\d+|[()[\]]", part)
        if "".join(tokens) != part:
            return {"status": "missing", "reason": "Ambiguous or unsupported formula syntax"}
        position = 0
        coefficient = 1
        if tokens and tokens[0].isdigit():
            coefficient = int(tokens[0])
            position += 1

        def group(end=None):
            nonlocal position
            result = Counter()
            while position < len(tokens):
                token = tokens[position]
                if token in (")", "]"):
                    if token != end:
                        raise ValueError("Mismatched group")
                    position += 1
                    return result
                position += 1
                if token in ("(", "["):
                    chunk = group(")" if token == "(" else "]")
                elif re.fullmatch(r"[A-Z][a-z]?", token):
                    if pt.GetAtomicNumber(token) < 1:
                        raise ValueError("Unrecognised element")
                    chunk = Counter({token: 1})
                else:
                    raise ValueError("Unexpected multiplier")
                multiplier = 1
                if position < len(tokens) and tokens[position].isdigit():
                    multiplier = int(tokens[position])
                    position += 1
                if multiplier < 1:
                    raise ValueError("Zero atom count")
                result.update({el: n * multiplier for el, n in chunk.items()})
            if end:
                raise ValueError("Unclosed group")
            return result

        try:
            component = group()
            if not component or coefficient < 1:
                raise ValueError("Empty formula")
            counts.update({el: n * coefficient for el, n in component.items()})
        except (ValueError, RuntimeError) as exc:
            return {"status": "missing", "reason": str(exc)}
    return {"status": "calculated", "formula_normalised": "".join(el + (str(n) if n != 1 else "") for el, n in sorted(counts.items())), "molar_mass_g_mol": round(sum(pt.GetAtomicWeight(el) * n for el, n in counts.items()), 4), "atom_count": sum(counts.values()), "heavy_atom_count": sum(n for el, n in counts.items() if el != "H"), "composition_basis": "formula unit (multicomponent)" if multicomponent else "reported molecular formula", "reason": "RDKit average atomic weights; sum all explicitly written formula components; charges ignored for mass"}


def normalise_model(model):
    pot = model.get("potential description", "")
    intra = model.get("intramolecular description", "")
    all_text = pot + " " + intra + " " + model.get("programs", "")
    levels = []
    for name, pattern in [("PBE0 / PBE1PBE", r"PBE0|PBE1PBE"), ("MP2", r"\bMP2\b"), ("HF / SCF", r"\bR?HF\b|\bSCF\b"), ("B3LYP", r"B3LYP"), ("M06-2X", r"M0?62X|M06-2X|MO62X"), ("PBE", r"PBEPBE|(?<![A-Z0-9])PBE(?![01A-Z])"), ("B3PW91", r"B3PW91"), ("CCSD", r"CCSD"), ("DFTB3-D3", r"DFTB")]:
        if re.search(pattern, all_text, re.I):
            levels.append(name)
    families = []
    for name, pattern in [("FIT", r"\bFIT\b|fit\.pots"), ("Williams", r"Will(?:iams)?(?:01|99)?\b|\bW99\b"), ("Day / Rice", r"\bDay|Rice|GMD"), ("Non-empirical / SAPT", r"non-empirical|SAPT|CamNoInd|CamwithCT"), ("Custom Delaware", r"Delaware")]:
        if re.search(pattern, pot, re.I):
            families.append(name)
    return {"potential_families": families, "electronic_methods": levels, "basis_sets": sorted(set(re.findall(r"(?:d-aug-|aug-|d-)?cc-pV[A-Za-z0-9]+|(?:d-)?augA?-sadlej|Sadlej(?:\s+pVTZ)?|[36]-\d{1,3}(?:\+\+|\+)?[Gg](?:\+)?(?:\([^)]*\)|\*\*)?", all_text, re.I))), "dispersion": sorted(set(re.findall(r"\bD3(?:\(BJ\))?|\bD2\b|\bTS\b", all_text))), "periodic_dft_details_status": "missing" if model["kind"] == "supplementary_periodic_DFT" else "not_applicable"}


def doi_from_url(url):
    p = urlsplit(url)
    if p.netloc.lower() in {"doi.org", "dx.doi.org", "www.doi.org"}:
        return unquote(p.path).lstrip("/").rstrip(".,;").lower()
    m = re.search(r"10\.\d{4,9}/[^\s?#]+", unquote(url), re.I)
    return m.group(0).rstrip(".,;").lower() if m else ""


def paper_key(ref):
    doi = doi_from_url(ref["url"])
    if doi:
        return "doi:" + doi
    return "url:" + ref["url"].replace("http://", "https://", 1).rstrip("/")


def resolve_publication_crossrefs(page):
    """Resolve explicit 'See Study_ID' pointers within the same molecule page."""
    by_study_id = defaultdict(list)
    for search in page["searches"]:
        for model in search["models"]:
            if model.get("study_id"):
                by_study_id[model["study_id"]].append(search)

    def resolve(search, visited):
        if search["publications"]:
            return search["publications"]
        text = search.get("publication_raw", "")
        match = re.fullmatch(r"See\s+Study_IDs?\s*=?\s*(.*)", text, re.I)
        if not match or search["search"] in visited:
            return []
        refs = []
        for sid in re.findall(r"\d+", match.group(1)):
            targets = by_study_id.get(sid, [])
            # Ambiguous or missing targets must not be guessed.
            if len({s["search"] for s in targets}) != 1:
                continue
            for ref in resolve(targets[0], visited | {search["search"]}):
                refs.append(ref | {"association_status": "inferred", "cross_reference": text})
        return refs

    pending = [(search, resolve(search, set())) for search in page["searches"]]
    for search, resolved in pending:
        search["publications"] = resolved


def fetch_sources(args):
    source_dir = BASE / "sources"
    tree_file = source_dir / "tree.json"
    if args.tree:
        tree = json.loads(args.tree.read_text())
        write_json(tree_file, tree)
    elif args.refresh or not tree_file.exists():
        tree = json.loads(get_bytes(API))
        write_json(tree_file, tree)
    else:
        tree = json.loads(tree_file.read_text())
    if tree.get("truncated"):
        raise ValueError("Truncated GitHub tree: refusing incomplete extraction")
    inventory = {i["path"]: i for i in tree["tree"] if i["type"] == "blob"}
    revision = tree["sha"]
    html_dir = source_dir / "html"
    html_dir.mkdir(parents=True, exist_ok=True)
    pages, audit = {}, []

    def load(path):
        blob = inventory[path]
        target = html_dir / (blob["sha"] + ".html")
        alternate = args.html_cache / target.name
        mode = "archived_verified"
        if target.exists():
            raw = target.read_bytes()
        elif alternate.exists():
            raw = alternate.read_bytes()
            mode = "reused_git_verified_cache"
        elif args.offline:
            raise FileNotFoundError("Missing cached HTML: " + path)
        else:
            raw = get_bytes(RAW + revision + "/" + quote(path))
            mode = "downloaded"
        if git_sha(raw) != blob["sha"]:
            raise ValueError("Git blob checksum mismatch: " + path)
        if not target.exists():
            target.write_bytes(raw)
        return path, raw, mode

    with ThreadPoolExecutor(max_workers=5) as pool:
        todo = {pool.submit(load, path): path for path in inventory if path.endswith(".html")}
        for fut in as_completed(todo):
            path = todo[fut]
            try:
                _, raw, mode = fut.result()
                pages[path] = raw
                audit.append({"path": path, "source_url": SITE + quote(path), "snapshot_url": RAW + revision + "/" + quote(path), "git_blob_sha": inventory[path]["sha"], "status": "accessible", "retrieval": mode, "error": ""})
            except Exception as exc:
                audit.append({"path": path, "source_url": SITE + quote(path), "status": "inaccessible", "error": str(exc)})
    reachable, queue, links = set(), deque(["index.html"]), []
    while queue:
        path = queue.popleft()
        if path in reachable or path not in pages:
            continue
        reachable.add(path)
        for a in Document(decode_html(pages[path])).root.walk("a"):
            href = a.attrs.get("href", "")
            target = site_path(href, SITE + path)
            if target and target.lower().endswith((".html", ".htm")):
                links.append({"source_path": path, "target_path": target, "status": "present" if target in pages else "missing_from_snapshot"})
                if target in pages and target not in reachable:
                    queue.append(target)
    for row in audit:
        row["reachable_from_index"] = row["path"] in reachable
    print(f"Verified {len(pages)} HTML pages; {len(reachable)} reachable from index", flush=True)
    return tree, inventory, pages, reachable, audit, links


def summarise_json(raw, path, expected_sha):
    if git_sha(raw) != expected_sha:
        raise ValueError("Git blob checksum mismatch: " + path)
    data = json.loads(raw)
    structures = data.get("structures", [])
    props = data.get("properties", {})
    lengths = {k: len(v["values"]) for k, v in props.items() if v.get("target") == "structure" and "values" in v}
    invalid = {k: n for k, n in lengths.items() if n != len(structures)}
    filenames = next((v["values"] for k, v in props.items() if k.casefold() == "filename"), [])
    experiment = next((v["values"] for k, v in props.items() if k.casefold() == "experimental info"), [])
    positive_experimental = sum(clean(v).lower() not in MISSING | {"0", "0.0", "nan", "false", "-"} for v in experiment)
    return {"path": path, "git_blob_sha": expected_sha, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw), "structure_count": len(structures), "unique_filename_count": len(set(map(str, filenames))) if filenames else None, "duplicate_filename_count": len(filenames) - len(set(map(str, filenames))) if filenames else None, "property_lengths_valid": not invalid, "property_length_errors": invalid, "property_names": list(props), "experimental_info_unique_values": sorted(set(map(str, experiment)))[:150], "nonempty_experimental_info_count": positive_experimental if experiment else None, "unit_cell_atom_count_min": min((s.get("size", 0) for s in structures), default=None), "unit_cell_atom_count_max": max((s.get("size", 0) for s in structures), default=None), "status": "calculated", "count_definition": "Number of entries in the linked Chemiscope structures array; includes experimental-reference entries and may include repeats; not the original search size or globally distinct packings"}


def obtain_structure_counts(args, paths, inventory, revision):
    summary_file = BASE / "sources/structure_summaries.json"
    summaries = json.loads(summary_file.read_text()) if summary_file.exists() else {}
    args.cache.mkdir(parents=True, exist_ok=True)

    def work(path):
        if path not in inventory:
            return path, {"path": path, "status": "missing", "error": "Linked file absent from repository snapshot"}
        sha = inventory[path]["sha"]
        if path in summaries and summaries[path].get("git_blob_sha") == sha:
            return path, summaries[path]
        target = args.cache / (sha + ".json")
        if target.exists():
            raw = target.read_bytes()
        elif args.offline:
            return path, {"path": path, "status": "missing", "error": "JSON unavailable offline"}
        else:
            raw = get_bytes(RAW + revision + "/" + quote(path), timeout=180)
            if git_sha(raw) != sha:
                raise ValueError("Invalid JSON checksum " + path)
            target.write_bytes(raw)
        return path, summarise_json(raw, path, sha)

    done = 0
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(work, path): path for path in sorted(paths)}
        for fut in as_completed(futures):
            path = futures[fut]
            try:
                _, row = fut.result()
            except Exception as exc:
                row = {"path": path, "status": "missing", "error": str(exc)}
            summaries[path] = row
            done += 1
            if done % 25 == 0 or done == len(paths):
                write_json(summary_file, summaries)
                print(f"Structure summaries: {done}/{len(paths)}", flush=True)
    write_json(summary_file, summaries)
    return {p: summaries[p] for p in paths}


def enrich_papers(args, refs):
    metadata_file = BASE / "sources/doi_metadata.json"
    metadata = json.loads(metadata_file.read_text()) if metadata_file.exists() else {}
    dois = sorted({doi_from_url(r["url"]) for r in refs} - {""})
    missing = [doi for doi in dois if doi not in metadata or (not args.offline and metadata[doi].get("status") == "missing")]
    print(f"Paper identifiers: {len(dois)} DOIs; {len(missing)} to resolve", flush=True)

    def work(doi):
        if args.offline:
            return doi, {"status": "missing", "error": "Not in offline metadata cache"}
        if doi.startswith("10.5258/ecrystals/"):
            url = "https://api.datacite.org/dois/" + quote(doi, safe="")
            try:
                msg = json.loads(get_bytes(url, timeout=35))["data"]["attributes"]
                return doi, {"status": "reported", "title": "; ".join(t["title"] for t in msg.get("titles", [])), "authors": "; ".join(a.get("name", "") for a in msg.get("creators", [])), "year": msg.get("publicationYear"), "type": "dataset", "resource_type": msg.get("types", {}), "metadata_url": url}
            except Exception as exc:
                return doi, {"status": "missing", "error": str(exc), "metadata_url": url}
        url = "https://api.crossref.org/works/" + quote(doi, safe="")
        try:
            msg = json.loads(get_bytes(url, timeout=35))["message"]
            def year_of(key):
                parts = msg.get(key, {}).get("date-parts", [[]])
                return parts[0][0] if parts and parts[0] else None
            return doi, {"status": "reported", "title": clean(" ".join(msg.get("title", []))), "authors": "; ".join(clean(a.get("given", "") + " " + a.get("family", "")) for a in msg.get("author", [])), "year": year_of("published") or year_of("published-print") or year_of("published-online") or year_of("issued"), "year_online": year_of("published-online"), "year_print": year_of("published-print"), "type": msg.get("type", ""), "journal": "; ".join(msg.get("container-title", [])), "metadata_url": url}
        except Exception as exc:
            return doi, {"status": "missing", "error": str(exc), "metadata_url": url}

    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(work, doi) for doi in missing]
        for index, fut in enumerate(as_completed(futures), 1):
            doi, data = fut.result()
            metadata[doi] = data
            if index % 20 == 0 or index == len(futures):
                write_json(metadata_file, metadata)
                print(f"DOI metadata: {index}/{len(futures)}", flush=True)
    write_json(metadata_file, metadata)
    return metadata


def extract(args):
    tree, inventory, pages, reachable, audit, links = fetch_sources(args)
    parsed = {p: parse_case(pages[p], p) for p in sorted(reachable)}
    for page in parsed.values():
        resolve_publication_crossrefs(page)
    grouped = defaultdict(list)
    for path, page in parsed.items():
        for search in page["searches"]:
            targets = search["json_paths"]
            # Explicit same JSON URL means same dataset, even across duplicate pages.
            ident = Path(targets[0]).stem if targets else path.removesuffix(".html") + "::" + search["search"]
            grouped[ident].append((page, search))
    all_json_paths = {p for group in grouped.values() for _, search in group for p in search["json_paths"]}
    summaries = obtain_structure_counts(args, all_json_paths, inventory, tree["sha"])
    refs = [ref for group in grouped.values() for page, search in group for ref in search["publications"] + page["context_refs"]]
    doi_metadata = enrich_papers(args, refs)
    papers, relations, datasets, models, contributions, provenance, conflicts = {}, [], [], [], [], [], []
    accessed = datetime.now(ZoneInfo("Europe/London")).date().isoformat()
    if args.offline and (BASE / "manifest.json").exists():
        accessed = json.loads((BASE / "manifest.json").read_text())["accessed_date"]

    def prov(ident, field, value, status, url, evidence="", method=""):
        provenance.append({"dataset_id": ident, "field": field, "value": value, "status": status, "source_url": url, "evidence": evidence, "method": method, "accessed_date": accessed})

    for ident, group in sorted(grouped.items()):
        page, search = group[0]
        url = SITE + quote(search["page_path"])
        unique_paths = sorted({p for _, s in group for p in s["json_paths"]})
        if len(unique_paths) > 1:
            raise ValueError("Multiple linked JSON files require an explicit counting rule: " + ident)
        count = summaries.get(unique_paths[0], {}) if unique_paths else {}
        formula = page["metadata"].get("formula", "")
        chemistry = parse_formula(formula)
        scientist_raw = search.get("scientist", "")
        credits = scientists(scientist_raw)
        raw_date = search.get("date", "")
        year = study_year(raw_date)
        dataset = {"dataset_id": ident, "dataset_name": page["heading"], "search_identifier": search["search"], "source_url": url, "all_source_urls": " | ".join(sorted({SITE + quote(s["page_path"]) for _, s in group})), "accessed_date": accessed, "scientist_raw": scientist_raw, "scientist_names": "; ".join(sorted({n for n, _, _ in credits})), "scientist_status": "reported" if credits else "missing", "study_date_raw": raw_date, "study_year": year, "study_year_status": "reported" if year else "missing", "release_year": None, "release_year_status": "missing", "formula_raw": formula, "formula_status": "reported" if formula and formula.lower() not in MISSING else "missing", "formula_normalised": chemistry.get("formula_normalised", ""), "molar_mass_g_mol": chemistry.get("molar_mass_g_mol"), "atom_count": chemistry.get("atom_count"), "heavy_atom_count": chemistry.get("heavy_atom_count"), "composition_basis": chemistry.get("composition_basis", ""), "composition_status": chemistry["status"], "composition_note": chemistry.get("reason", ""), "refcode": page["metadata"].get("refcode", ""), "json_url": SITE + quote(unique_paths[0]) if unique_paths else "", "structure_count": count.get("structure_count"), "structure_count_status": count.get("status", "missing"), "structure_count_definition": count.get("count_definition", "Linked JSON missing or inaccessible"), "unique_filename_count": count.get("unique_filename_count"), "duplicate_filename_count": count.get("duplicate_filename_count"), "unit_cell_atom_count_min": count.get("unit_cell_atom_count_min"), "unit_cell_atom_count_max": count.get("unit_cell_atom_count_max"), "original_generated_structure_count": None, "original_generated_structure_count_status": "missing", "publication_raw": search.get("publication_raw", ""), "energy_model_count": 0, "periodic_dft_supplement": False}
        for field in ["scientist_raw", "study_date_raw", "formula_raw", "refcode", "publication_raw", "dataset_name", "search_identifier"]:
            v = dataset[field]
            prov(ident, field, v, "reported" if v and str(v).lower() not in MISSING else "missing", url, v)
        prov(ident, "release_year", "", "missing", url, "No dataset release/deposition year field; page update dates are not release dates")
        prov(ident, "study_year", year, "reported" if year else "missing", url, raw_date, "Single unambiguous year in Date field; ranges and pre-2010 excluded")
        for field in ["molar_mass_g_mol", "atom_count", "heavy_atom_count", "composition_basis", "formula_normalised"]:
            prov(ident, field, dataset[field], chemistry["status"], url, formula, chemistry.get("reason", ""))
        prov(ident, "structure_count", dataset["structure_count"], dataset["structure_count_status"], dataset["json_url"] or url, count.get("git_blob_sha", ""), dataset["structure_count_definition"])
        prov(ident, "original_generated_structure_count", "", "missing", url, "Original generated / optimised / retained search counts not given as numeric HTML fields")
        prov(ident, "scientist_names", dataset["scientist_names"], "inferred" if any(n != raw for n, _, raw in credits) else dataset["scientist_status"], url, scientist_raw, "Split explicit separators; L Price expanded to Louise Price; Sally Price kept distinct; see contributor_aliases.csv")
        for name, role, raw_name in credits:
            contributions.append({"dataset_id": ident, "scientist_name": name, "role": role, "source_name": raw_name, "source_field": scientist_raw, "status": "inferred" if raw_name != name else "reported", "source_url": url})
        seen_models = set()
        for page_i, search_i in group:
            url_i = SITE + quote(search_i["page_path"])
            for field in ["scientist", "date", "publication_raw"]:
                if search_i.get(field, "") != search.get(field, ""):
                    conflicts.append({"dataset_id": ident, "field": field, "selected": search.get(field, ""), "alternative": search_i.get(field, ""), "source_url": url_i})
            if page_i["metadata"].get("formula", "") != formula:
                conflicts.append({"dataset_id": ident, "field": "formula", "selected": formula, "alternative": page_i["metadata"].get("formula", ""), "source_url": url_i})
            for model in search_i["models"]:
                signature = json.dumps(model, sort_keys=True)
                if signature in seen_models:
                    continue
                seen_models.add(signature)
                norm = normalise_model(model)
                row = {"dataset_id": ident, "model_id": model["model_id"], "kind": model["kind"], "source_url": url_i, "study_id": model.get("study_id", ""), "programs_raw": model.get("programs", ""), "potential_description_raw": model.get("potential description", ""), "intramolecular_description_raw": model.get("intramolecular description", ""), "downloads": " | ".join(model.get("downloads", [])), "potential_families": "; ".join(norm["potential_families"]), "electronic_methods": "; ".join(norm["electronic_methods"]), "basis_sets": "; ".join(norm["basis_sets"]), "dispersion_explicit": "; ".join(norm["dispersion"]), "normalisation_status": "inferred", "periodic_dft_details_status": norm["periodic_dft_details_status"]}
                models.append(row)
                if model["kind"] == "energy_model":
                    dataset["energy_model_count"] += 1
                else:
                    dataset["periodic_dft_supplement"] = True
                for field in ["programs_raw", "potential_description_raw", "intramolecular_description_raw", "study_id", "downloads"]:
                    prov(ident, "model_" + model["model_id"] + "." + field, row[field], "reported" if row[field] else "missing", url_i, row[field])
                for field in ["potential_families", "electronic_methods", "basis_sets", "dispersion_explicit"]:
                    prov(ident, "model_" + model["model_id"] + "." + field, row[field], "inferred" if row[field] else "missing", url_i, model.get("potential description", "") + " | " + model.get("intramolecular description", ""), "Conservative text pattern categories; not a claim of periodic DFT")
            for ref in search_i["publications"] + page_i["context_refs"]:
                key = paper_key(ref)
                doi = doi_from_url(ref["url"])
                enrichment = doi_metadata.get(doi, {})
                cited_years = re.findall(r"\b(?:19|20)\d{2}\b", ref["citation"])
                year_ref = int(cited_years[-1]) if cited_years else None
                is_thesis = bool(re.search(r"thesis|dissertation", ref["citation"], re.I)) or enrichment.get("type") == "dissertation"
                ref_type = "dissertation" if is_thesis else enrichment.get("type", "unclassified_reference")
                if not doi and re.search(r"Trans\.\s*ACA", ref["citation"], re.I):
                    ref_type = "paper_reported_citation"
                papers.setdefault(key, {"paper_id": key, "doi": doi, "doi_status": ref.get("doi_status", "reported") if doi else "missing", "url": "https://doi.org/" + quote(doi, safe="/():;-") if doi else ref["url"], "title": enrichment.get("title", ""), "title_status": "reported" if enrichment.get("title") else "missing", "authors": enrichment.get("authors", ""), "authors_status": "reported" if enrichment.get("authors") else "missing", "type": ref_type, "type_status": "inferred" if ref_type == "paper_reported_citation" else ("reported" if ref_type != "unclassified_reference" else "missing"), "publication_year": enrichment.get("year") or year_ref, "publication_year_status": "reported" if enrichment.get("year") or year_ref else "missing", "year_source": enrichment.get("metadata_url", "") if enrichment.get("year") else url_i, "year_online": enrichment.get("year_online"), "year_print": enrichment.get("year_print"), "citation_example": ref["citation"], "metadata_url": enrichment.get("metadata_url", ""), "metadata_status": enrichment.get("status", "missing"), "source_url": url_i})
                relations.append({"dataset_id": ident, "paper_id": key, "relation": ref["scope"], "source_url": url_i, "citation_raw": ref["citation"], "linked_url_raw": ref.get("raw_url", ref["url"]), "normalised_linked_url": ref["url"], "context": ref["context"], "status": ref.get("association_status", "reported"), "cross_reference": ref.get("cross_reference", "")})
        datasets.append(dataset)

    df = pd.DataFrame(datasets)
    rel = pd.DataFrame(relations).drop_duplicates(["dataset_id", "paper_id", "relation"])
    paper_df = pd.DataFrame(papers.values())
    paper_df["is_paper"] = paper_df["type"].isin(["journal-article", "proceedings-article", "posted-content", "paper_reported_citation"])
    paper_lookup = paper_df.set_index("paper_id")
    counts_records = []
    for i, row in df.iterrows():
        assoc = rel[rel.dataset_id == row.dataset_id]
        study = assoc[assoc.relation == "csp_study"]
        study_ids = study.paper_id.unique()
        paper_ids = [key for key in study_ids if bool(paper_lookup.loc[key, "is_paper"])]
        years = [int(paper_lookup.loc[key, "publication_year"]) for key in paper_ids if pd.notna(paper_lookup.loc[key, "publication_year"])]
        values = {"csp_linked_reference_count": len(study_ids), "csp_paper_count": len(paper_ids), "csp_nonpaper_or_unresolved_count": len(study_ids) - len(paper_ids), "experimental_context_reference_count": assoc[assoc.relation == "experimental_context"].paper_id.nunique(), "all_linked_reference_count": assoc.paper_id.nunique(), "publication_years": "; ".join(map(str, sorted(set(years)))), "earliest_csp_publication_year": min(years) if years else None}
        counts_records.append(values)
        for key, val in values.items():
            prov(row.dataset_id, key, val, "calculated", row.source_url, row.publication_raw, "Deduplicate DOI / canonical URL; bibliographic-service paper types plus explicit Trans. ACA paper citation; CSD references separate")
    df = pd.concat([df, pd.DataFrame(counts_records, index=df.index)], axis=1)
    contrib_df = pd.DataFrame(contributions).drop_duplicates(["dataset_id", "scientist_name"])
    contributor_df = contrib_df.groupby("scientist_name").agg(dataset_count=("dataset_id", "nunique"), source_names=("source_name", lambda x: "; ".join(sorted(set(x)))), source_urls=("source_url", lambda x: " | ".join(sorted(set(x))))).reset_index().sort_values("dataset_count", ascending=False)
    all_inventory_json = {p for p in inventory if p.startswith("0.Chemiscope/") and p.endswith(".json")}
    orphan_json = [{"path": p, "git_blob_sha": inventory[p]["sha"], "bytes": inventory[p].get("size"), "reason": "Not linked from a reachable CSP search; excluded, including full/filtered variants"} for p in sorted(all_inventory_json - all_json_paths)]
    # Audit linked files that do not exist, including archives and images.
    file_links = []
    for path in sorted(reachable):
        for node in Document(decode_html(pages[path])).root.walk():
            href = node.attrs.get("href") or node.attrs.get("src")
            target = site_path(href, SITE + path) if href else None
            load = json_target(href, SITE + path) if href else None
            if load:
                target = load
            if target and target not in inventory and target:
                file_links.append({"source_path": path, "target_path": target, "status": "missing_from_snapshot", "original_link": href})
    out = BASE / "tables"
    out.mkdir(parents=True, exist_ok=True)
    tables = {"datasets": df, "contributors": contributor_df, "dataset_contributors": contrib_df, "energy_models": pd.DataFrame(models), "papers": paper_df, "dataset_papers": rel, "provenance": pd.DataFrame(provenance), "page_audit": pd.DataFrame(audit).sort_values("path"), "html_link_audit": pd.DataFrame(links).drop_duplicates(), "broken_source_links": pd.DataFrame(file_links).drop_duplicates(), "unlinked_json_inventory": pd.DataFrame(orphan_json), "metadata_conflicts": pd.DataFrame(conflicts, columns=["dataset_id", "field", "selected", "alternative", "source_url"]), "structure_file_audit": pd.DataFrame(summaries.values()), "contributor_aliases": pd.DataFrame([{"source_name": "L Price", "normalised_name": "Louise Price", "status": "inferred", "rationale": "Initial expansion within explicit scientist field; source spelling retained"}, {"source_name": "Sally Price", "normalised_name": "Sally Price", "status": "reported", "rationale": "Distinct from Louise Price; UCL lists Sarah (Sally) L. Price", "verification_url": "https://www.ucl.ac.uk/mathematical-physical-sciences/chemistry/people/emeritus-honorary-staff"}])}
    for name, table in tables.items():
        table.to_csv(out / (name + ".csv"), index=False)
    manifest = {"source_index": SITE + "index.html", "snapshot_revision": tree["sha"], "accessed_date": accessed, "timezone": "Europe/London", "dataset_definition": "Unique CSP search identified by explicit linked Chemiscope filename; no-link searches by page and search code; repeated pages referencing same file merged", "year_rule": "Single unambiguous year in source Date field (study date); ranges and pre-2010 excluded; no release dates or publication-year substitution", "structure_rule": "Array-entry count of linked JSON only; original search generation size and cross-dataset packing identity unknown", "reachable_html_pages": len(reachable), "inventory_html_pages": len(pages), "case_pages_with_searches": sum(bool(p["searches"]) for p in parsed.values()), "search_occurrences_before_deduplication": sum(len(p["searches"]) for p in parsed.values()), "datasets": len(df), "unlinked_json_files": len(orphan_json)}
    write_json(BASE / "manifest.json", manifest)
    print(json.dumps(manifest, indent=2), flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--tree", type=Path)
    p.add_argument("--refresh", action="store_true", help="Retrieve a fresh repository inventory")
    p.add_argument("--offline", action="store_true", help="Use archived HTML, structure summaries and DOI metadata")
    p.add_argument("--plot-only", action="store_true", help="Recreate figure/report from extracted tables")
    p.add_argument("--extract-only", action="store_true")
    p.add_argument("--cache", type=Path, default=Path("/tmp/cposs-numbers-json-cache"))
    p.add_argument("--html-cache", type=Path, default=Path("/tmp/cposs-catalogue-cache"))
    p.add_argument("--font", type=Path, default=Path("/System/Library/Fonts/Helvetica.ttc"))
    args = p.parse_args()
    if not args.plot_only:
        extract(args)
    if not args.extract_only:
        from make_figure import make_figure
        make_figure(BASE, args.font)


if __name__ == "__main__":
    main()
