# CPOSS CSP Landscape Navigator

A static Chemiscope viewer with dataset search, five collection filters, and contextual links/previews for the CPOSS molecule database. No build step or server application is required.

## Run locally

From this repository:

```sh
python3 -m http.server 8765 --bind 127.0.0.1
```

Open <http://127.0.0.1:8765/>. Use HTTP rather than opening the HTML as a local file: the catalogue is loaded with `fetch`. Internet access is required for remote datasets, database previews, and the existing Font Awesome stylesheet.

Search by a molecule name, alias, REFCODE, or dataset code. Select a result with a click or the arrow keys and Enter; Escape dismisses the list. Collection filters combine with the search. Filtering does not change the displayed landscape.

“Open molecule database page” opens the source page separately. “Preview beside landscape” embeds it beside the viewer on wide screens and below the viewer on smaller screens. The external link is always available if embedding fails. The preview shows the original database page, whose fixed-width content may require horizontal scrolling.

The existing Chemiscope load/save modal, plot/structure settings, exports, and local file loader remain available. A local upload clears the shared dataset URL and does not inherit a database-page association just because its filename resembles a catalogue entry.

## Refresh the catalogue

Python 3.9+ and its standard library are sufficient:

```sh
python3 scripts/update_catalogue.py
```

The script retrieves the complete GitHub file tree and the database's HTML pages, not the full crystal structure datasets. HTML content is fetched at the inventory's immutable tree revision and verified against Git blob hashes. The four molecule lists provide aliases and collection membership; actual case-page Chemiscope links establish molecule/search associations. Nested energy models and their download links remain associated with the correct search.

Generated files:

- `data/catalogue.json`: dataset URLs, labels, names/codes, collections, case-page links and energy-model associations.
- `data/catalogue-report.json`: totals, missing mappings, broken source references, ambiguous mappings, and collection cases without mapped datasets.

HTML is cached outside the repository at `/tmp/cposs-catalogue-cache`, keyed by blob SHA. To archive an inventory for reproducible offline refreshes:

```sh
curl --fail --location 'https://api.github.com/repos/LouisePrice/CPOSS_Database/git/trees/main?recursive=1' -o /tmp/cposs-tree.json
python3 scripts/update_catalogue.py --tree /tmp/cposs-tree.json
python3 scripts/update_catalogue.py --tree /tmp/cposs-tree.json --offline
```

Use `--cache PATH` for a persistent cache and `--output PATH` for a separate output directory. A truncated inventory or failed page download aborts the refresh before replacing the existing catalogue. Review the generated report after every refresh. Source link mismatches are reported rather than automatically corrected by fuzzy filename matching.

Runtime search uses only the static catalogue. It does not call GitHub's API or download structure files until a dataset is selected. Existing `?load=...` links using GitHub raw, GitHub blob, or database Pages URLs remain supported. `?settings=...` is applied after the default structure settings; choosing a different dataset clears that old settings parameter.

## Current source limitations

Snapshot refreshed on 22 October 2026, tree `ff596da6e70766a9a12af56413831c774dd695f1`:

- 310 datasets and 236 case HTML pages; 307 datasets have an explicit case-page mapping.
- Collections contain 49 Blind Test, 26 CPOSS209, 30 unpublished, 25 Tricyclics, and 11 Dichloronitrobenzene datasets. Membership can overlap.
- `4C2NBMHA.json`, `5fluorouracilA.json`, and `PhloroglucinolDihydrateB.json` remain searchable by filename but have no verified page association.
- Five source-page dataset links refer to filenames absent from the repository; see the report for exact paths. One is a duplicate misspelled molecule page, and one references a dataset that is not present at all.

Counts are snapshot documentation, not hardcoded application limits. Dataset/case paths are checked against the repository tree. The refresh does not parse every dataset or verify every external DOI/archive URL with HTTP requests. Cross-origin browsers do not reliably expose iframe rejection to the parent page, so the preview always provides a visible external-page fallback.

## Check changes

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
node --test tests/catalogue.test.js
node --check assets/navigator.js
```

Node 18+ is sufficient; no npm install is needed. Tests cover legacy nested tables, independent searches and energy models, overlapping collections, missing source references, search aliases/codes, and shared-URL matching without false associations to unrelated hosts.

For manual responsive checks, open <http://127.0.0.1:8765/tests/responsive.html> and switch among the provided iframe viewport widths. Check search, the five collections, keyboard selection, preview opening/closing, plot resizing and settings. This is a test harness, not part of the navigator interface.

Custom UI code lives in `assets/navigator.js` and `assets/navigator.css`; pure catalogue/search helpers live in `assets/catalogue.js`. The existing embedded Chemiscope and jQuery libraries are preserved. `old_index.html` is historical and is not used to generate metadata.
