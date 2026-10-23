# CPOSS CSP Landscape Navigator

A static Chemiscope viewer with dataset search, five collection filters, and contextual links/previews for the CPOSS molecule database. No build step or server application is required.

## Run locally

From this repository:

```sh
python3 -m http.server 8765 --bind 127.0.0.1
```

Open <http://127.0.0.1:8765/>. Use HTTP rather than opening the HTML as a local file: the catalogue is loaded with `fetch`. Internet access is required for remote datasets, database previews, and the existing Font Awesome stylesheet.

Search by a molecule name, alias, REFCODE, or dataset code. Select a result with a click or the arrow keys and Enter; Escape dismisses the list. Collection filters combine with the search. Filtering does not change the displayed landscape.

Opening the navigator without `?load=...` starts with Aspirin — Search A, a small example with both space-group and experimental-information properties, so the complete default style is visible immediately. The catalogue's first entry, 2-Fluoro Ethynyl Benzene, lacks a space-group property and therefore cannot use space-group colours. It remains selectable with a missing-property notice. Shared `?load=...` URLs and embedded/local datasets retain their own selection. A `?settings=...` URL also overrides the automatic initial example's settings.

“Open molecule database page” opens the source page separately. “Preview beside landscape” embeds it beside the viewer on wide screens and below the viewer on smaller screens. The external link is always available if embedding fails. The preview shows the original database page, whose fixed-width content may require horizontal scrolling.

The existing Chemiscope load/save modal, plot/structure settings, exports, and local file loader remain available. A local upload clears the shared dataset URL and does not inherit a database-page association just because its filename resembles a catalogue entry.

## Default plot appearance

After each successful dataset load, the custom defaults select `Space Group` for colour with native `log` (base 10), fixed limits `0`–`2.37`, and `seismic`. Current public datasets use a numeric `Space Group Number` field instead; when `Space Group` is absent, this supplied numeric field is used with a visible explanatory note. Neither field is renamed or synthesized. Point sizes use `Experimental Info` with native `flip-linear`; the overall size factor and the existing axes are retained. Structures default to a 3×3×3 supercell with the unit cell shown.

Saved dataset settings override these defaults. A subsequent settings-file load or `?settings=...` overrides the result. Filtering, preview toggles, resizing and ordinary user adjustments do not reapply defaults. This applies to shared URLs, catalogue selection, local files (including the streaming loader), and embedded datasets. Original property values and saved settings are not re-encoded or modified by the defaults helper.

The bundled Chemiscope represents string properties as category indices starting at zero, in order of first occurrence. For example, the local Aspirin sample stores space-group symbols and experimental descriptions as strings. The page explicitly reports when its log colours and point sizes refer to those indices, not international space-group numbers or measurements. The first category's `log10(0)` is undefined; Chemiscope's native handling is retained. Constant properties use Chemiscope's native uniform colour/size handling.

Missing or unsupported properties, infinite values, and numeric space-group values ≤0 cause the affected default to be skipped with a visible note. Numeric NaN values are supported for colour and axes; missing sizes cause the size default to be skipped. The other controls remain usable. This bundle supports at most 21 distinct string categories per property. If applying defaults fails, the successfully loaded visualization is restored. No derived property or category encoding is added.

### Urea and missing values

Urea previously failed before rendering because `Space Group Number` mixes 842 numbers with eight `"nan"` strings, which Chemiscope's homogeneous-property validator rejects. The native parser already accepts the 171 numerical NaN entries in the three model-2 properties. Before loading, the custom helper creates a shallow visualization copy and converts only null/`"nan"` missing markers in otherwise numeric columns to numeric NaN. It does not convert numeric strings, space-group symbols, or text-only categories. The source object, every structure index, and source properties in saved dataset exports remain intact.

Urea's default model-2 Density/Energy axes omit 57 of 850 structures because their model-2 values are missing. A persistent notice counts the affected structures and properties for the current axes; switching to the complete model-1 axes displays all 850. All structures remain accessible through Chemiscope's structure selector. Eight unknown space-group values use native grey colouring. Experimental descriptions still use native category indices for point sizes.

## Structures and metadata downloads

The main page provides a direct ZIP button for a single model, or a keyboard-accessible list of model/study-labelled archive choices. It uses the selected case/search's `models[].downloads[]` links. Archive and spreadsheet paths are verified against the GitHub inventory; spreadsheet links come from actual sibling files in the linked search directory. Local, embedded and unmapped datasets have an unavailable state and do not inherit another dataset's links.

Archives are fetched only when a user requests a download. Normal links point directly to the original HTTPS ZIP resource; the browser's ZIP content type provides cross-origin downloading, with `download` as an additional filename hint. Users can also copy or open the original link through its normal context menu.

Only inspected archives are labelled “structures + metadata”. `data/archive-contents.json` records audits bound to each ZIP's Git blob SHA; catalogue refreshes discard audit labels if the archive changes. Other archives use “structures (.zip)” and do not promise metadata inclusion. Urea's verified CrystPred archive contains 850 RES files and `Urea_CrystPred.xlsx`; CrystOpt contains 793 RES files and `Urea_CrystOpt.xlsx`. The separate `UreaA.xlsx` search metadata is also linked.

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

Snapshot refreshed on 23 October 2026, tree `d65c1732ab6db46b8af34e0646a760c56a8d559c`:

- 315 datasets and 236 case HTML pages; 307 datasets have an explicit case-page mapping.
- Collections contain 49 Blind Test, 26 CPOSS209, 30 unpublished, 25 Tricyclics, and 11 Dichloronitrobenzene datasets. Membership can overlap.
- Eight datasets have no verified page association, including the three previously unmapped files and five new `working`/`_full` variants; see the report for exact names. They remain searchable by filename and have no inferred resource links.
- Five source-page dataset links refer to filenames absent from the repository; see the report for exact paths. One is a duplicate misspelled molecule page, and one references a dataset that is not present at all.

Counts are snapshot documentation, not hardcoded application limits. Dataset/case/archive/metadata paths are checked against the repository tree. The refresh does not parse every dataset or verify every external DOI/archive URL with HTTP requests. Archive contents have been inspected for Urea's two models; other content labels remain conservative. Cross-origin browsers do not reliably expose iframe rejection to the parent page, so the preview always provides a visible external-page fallback.

## Check changes

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
node --test tests/*.test.js
node --check assets/navigator.js
node --check assets/visualization.js
```

Node 18+ is sufficient; no npm install is needed. Tests cover legacy nested tables, independent searches and energy models, overlapping collections, missing source references, search aliases/codes, and shared-URL matching without false associations to unrelated hosts.

Plot-default tests also cover every dataset-loader entry point, saved-setting precedence, unchanged axes/size factor, native handler ordering, categorical diagnostics, missing/unsuitable properties and recovery. Missing-marker tests check row alignment, source immutability and saved exports. Resource tests check Urea's two audited archives, search/case associations and unavailable states. The synthetic `tests/fixtures/plot-*.json` files support manual browser checks through `?load=...`; `plot-sparse.json` reproduces Urea's mixed missing-marker problem in four structures. `plot-settings.json` and `urea-settings.json` support `?settings=...` override checks. `tests/embedded.html` exercises the actual navigator startup with embedded numeric, saved, categorical and missing-property fixtures.

For manual responsive checks, open <http://127.0.0.1:8765/tests/responsive.html> and switch among the provided iframe viewport widths. Check search, the five collections, keyboard selection, preview opening/closing, plot resizing and settings. This is a test harness, not part of the navigator interface.

Custom UI code lives in `assets/navigator.js` and `assets/navigator.css`; catalogue/search helpers live in `assets/catalogue.js`; plot defaults and settings precedence live in `assets/visualization.js`. The existing embedded Chemiscope and jQuery libraries are preserved. `old_index.html` is historical and is not used to generate metadata.
