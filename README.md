# CPOSS CSP Landscape Navigator

A static Chemiscope viewer with dataset search, five collection filters, and contextual links/previews for the CPOSS molecule database. No build step or server application is required.

## Run locally

From this repository:

```sh
python3 -m http.server 8765 --bind 127.0.0.1
```

Open <http://127.0.0.1:8765/>. Use HTTP rather than opening the HTML as a local file: the catalogue is loaded with `fetch`. Internet access is required for remote datasets, database previews, and the existing Font Awesome stylesheet.

Search by a molecule name, alias, molecular formula, REFCODE, or dataset code. Formula matching ignores whitespace, case and Unicode subscript formatting: `C9H8O4`, `C9 H8 O4` and `C₉H₈O₄` find the same datasets. It otherwise matches the complete source formula, retaining element order, explicit counts, charges, coefficients and hydrate/salt/component notation. It does not reorder elements or equate alternative chemical notations. All matching molecules/searches are returned within the selected collection. Formula metadata comes only from explicitly linked database case pages and is stored in the local catalogue; unmapped datasets retain name/code search. Select a result with a click or the arrow keys and Enter; Escape dismisses the list. Collection filters combine with the search. Filtering does not change the displayed landscape.

Opening the navigator without `?load=...` starts with the small Aspirin — Search A example. Every dataset uses the same scientific preset, including datasets with missing properties. Shared `?load=...` URLs and embedded/local datasets retain their dataset selection. Initial embedded settings and `?settings=...` are superseded by the preset; deliberate settings imports after loading remain available.

“Open molecule database page” opens the source page separately. “Preview beside landscape” embeds it beside the viewer on wide screens and below the viewer on smaller screens. The external link is always available if embedding fails. The preview shows the original database page, whose fixed-width content may require horizontal scrolling.

The existing Chemiscope load/save modal, plot/structure settings, exports, and local file loader remain available. A local upload clears the shared dataset URL and does not inherit a database-page association just because its filename resembles a catalogue entry.

## Dataset figures and statistics

Use **Analyses & statistics** in the Navigator header to open [the analyses page](analyses.html). It includes five analysis figures, expandable previews, original PDF/PNG and caption downloads, five linked CSV result tables, and dataset, chemistry and density statistics. The return links preserve a landscape selected through its `?load=...` URL. The analyses page uses local static assets and works without remote dataset downloads.

Counting notes distinguish molecular systems, searches, model-specific archived files and density records. The chemistry summaries use the reconciled composition audit. OMC25/CSD density references remain explicitly approximate histogram recoveries. The available Navigator JSON catalogue and documented archive inventory have different scopes.

After regenerating the scientific analyses, rebuild the checked-in page and public table bundle using Python 3.9+ (standard library only):

```sh
python3 scripts/build_analyses.py
```

The builder reads the existing outputs under `analysis/database_in_numbers/`, `analysis/cposs_omc25_comparison/` and `analysis/molecular_sketchmap/`. It writes `analyses.html` and `data/analyses/`, including source checksums, a data guide and a ZIP containing the five retained figures, their captions and linked result tables. Earlier exports, diagnostics and unrelated table downloads are excluded from the page catalogue and ZIP; original analysis files and previous CSV exports remain on disk. Public table copies omit local filesystem provenance paths. Raw source workbooks and caches are excluded. It does not rerun or change scientific calculations. Source counts are checked against the frozen analysis snapshot; update those checks and the displayed scope together when preparing a new snapshot.

## One global visualization

`assets/visualization.js` defines the single frozen `PRESET`. The reference view is **2-Aminobenzamide — Search A**. Its live rendered controls were captured before revision in `reports/reference-before.json`; the source has no embedded settings. The global style is:

```js
{
  target: "structure",
  map: {
    x: { property: "Density", scale: "linear" },
    y: { property: "Lattice Energy", scale: "linear" },
    z: { property: "" },
    color: { property: "Space Group Number", mode: "log", min: 0, max: 2.37, palette: "seismic" },
    size: { property: "Experimental Info", mode: "flip-linear", factor: 55 }
  },
  structure: [{ supercell: [3, 3, 3], unitCell: true }]
}
```

Names express scientific meaning. One generic adapter resolves the real fields, retaining their names and supplied units. Density and Lattice Energy must belong to the same model. Prefer the pair with the greatest number of jointly finite rows, then the unnumbered/lower numeric model (and suffix/name order for deterministic ties). Model labels may precede or follow their number. No unit conversion or unit inference is performed. If a matching pair is absent, show an empty scientific plot with unavailable-axis labels; do not substitute unrelated properties or pair different models. Structures remain selectable.

### Physical space-group colours

The visualization copy contains a numerical international space-group column, **1–230**, constructed from supplied valid numbers/numeric strings or recognized Hermann–Mauguin symbols. `assets/spacegroups.js` contains 654 normalized aliases from the [Gemmi 0.7.5 space-group table](https://gemmi.readthedocs.io/en/stable/symmetry.html), covering all 230 numbers. Generate it with `scripts/generate_spacegroups.py` and Gemmi 0.7.5 installed in an isolated Python environment. It recognizes validated full/short symbols and setting suffixes, spaces, screw-axis underscores/subscripts and digit overbars. It performs no fuzzy matching. Ambiguous/unrecognized symbols, noninteger/out-of-range numbers, missing markers and conflicting valid supplied fields are unknown (`NaN`) and neutral grey `#aaaaaa`. A valid number/symbol may supply a row where another field is missing or unrecognized; disagreements between valid fields are recorded as conflicts.

Colour uses native mode **log** (`log10` exactly once), the built-in **seismic** palette, and fixed **transformed limits 0–2.37**, in every dataset. Unknown groups never fall back to energy or another measurement. The same number receives the same RGB regardless of dataset/category order or whether it is constant.

This bundled Chemiscope forces any constant colour property to the midpoint before applying its transform and cannot validate an all-unknown colour property. A small instance-level compatibility layer in the custom module bypasses that constant shortcut for the normalized SG column and supplies only a validation/range extent for all-unknown data. It does not append fictitious structures or change missing SG values. The actual marker array retains numeric transformed values and grey unknowns; native palette/rendering and controls are retained. Missing values also remain grey during native map filtering. Unsupported native APIs raise a visible error instead of silently showing a different colour scheme. The embedded bundle is unchanged.

### Experimental Info sizes

Native **flip-linear** sizing and factor **55** apply everywhere. Numeric Experimental Info (including numeric strings) retains supplied values. Missing numeric sizes use Chemiscope's minimum size; a wholly missing/constant column uses its uniform reference size.

Text descriptions remain available in the original field. A separately labelled, display-only `Experimental Info (size)` column uses one deterministic annotation-presence score: **nonblank supplied annotation = 0; blank/missing = 1**. Native flip-linear makes annotated structures larger; it does not rank descriptions alphabetically or use dataset-local category indices. Missing markers include null, NaN, empty/whitespace strings, `nan`, `n/a`, `na`, `null`, `none`, `undefined`, `?` and standalone dashes. A nonblank description is treated only as a supplied annotation, not as proof of a particular experimental status or a numeric measurement. The reference dataset's 883 blank descriptions therefore produce uniform native point sizes; other datasets retain their experimental distinctions.

### Loading, editing and source preservation

The common `app.load` wrapper adapts startup, search/collections, shared URLs, embedded datasets, local files and the native streaming loader. Legacy embedded/URL settings never override the initial preset. To use a different appearance, adjust native controls or import a settings file through **Load / save after loading**. Those deliberate adjustments persist through filtering, previews and resize. Selecting another dataset resets to the global preset.

Normalization occurs only in a visualization copy: numeric strings become numbers, missing scalar markers become numeric NaN, and unsupported mixed scalar fields retain readable text labels. No scientific value is replaced with zero. Source properties, descriptions, structures, row indices and original embedded settings are retained in dataset exports; display-only fields are removed from exported properties. Exporting current settings still uses Chemiscope's native save controls. The custom extended-JSON parser preserves literal text such as `"NaN"` while accepting bare numeric NaN in embedded datasets.

Technical notes stay inside **Load / save → Dataset notes**, including resolved axes, missing rows, unknown SG counts and the annotation policy. Selecting an incomplete model can omit points from the scatter without removing their structures. For example, Urea's complete model-1 pair plots all 850 structures; its model-2 Density/Energy each lack 57 values, and eight SG numbers are missing. No structure/property alignment is changed.

### Reproducible catalogue audit

The audit discovers the dataset count from the current catalogue; it uses no molecule-specific presets or exception list:

```sh
python3 scripts/audit_visualizations.py
node scripts/audit_visualizations.js
python3 -m http.server 8765 --bind 127.0.0.1
```

The Python script downloads the catalogue's immutable Git tree, verifies each dataset's Git blob SHA, validates **every structure's geometry**, and prepares all original property rows plus the original first geometry under ignored `tests/.audit-data/`. Public source JSON is cached outside the repository. Use `--cache PATH` for a persistent cache, `--reuse-cache PATH` to reuse another verified cache, `--tree PATH` for a saved inventory, and `--offline` for reproducible cached runs. It does not rewrite upstream datasets.

The Node script produces **`reports/visualization-audit.json`**: per-dataset axis/model candidates and coverage, SG sources/normalization/unresolved values, Experimental Info policy, the resolved preset, row-alignment checks and geometry failures. Open **[the native audit](http://127.0.0.1:8765/tests/native-audit.html)** and run both buttons. Save reports as `reports/native-visualization-audit.json` and `reports/native-visualization-regressions.json`. The browser audit uses the production adapter and unchanged embedded native bundle, renders all scatter rows and the original first structure for every dataset, checks actual Plotly marker arrays/bounds/palette, and verifies source exports. All other geometry rows are validated by Python, not individually rendered. Periodic iframe recreation prevents QA batch WebGL/context accumulation.

Native regression checks export native PNG rasters and sample actual marker RGB values for numeric, symbolic, reordered, constant and unknown cases and the two named real datasets. This verifies rendered colours in addition to controls. Manual after-load settings API changes are checked separately. File-picker permission was declined in this browser session; see the audit report for that verification limit. A source lacking reliable scientific labels remains an explicit upstream data gap, not a molecule-specific axis guess. See `reports/visualization-audit.md` for the checked snapshot and limitations.

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

- `data/catalogue.json`: dataset URLs, labels, names/codes, collections, case-page links, source formulas and energy-model associations.
- `data/catalogue-report.json`: totals, missing mappings, broken source references, ambiguous mappings, datasets without source formulas, and collection cases without mapped datasets.

HTML is cached outside the repository at `/tmp/cposs-catalogue-cache`, keyed by blob SHA. To archive an inventory for reproducible offline refreshes:

```sh
curl --fail --location 'https://api.github.com/repos/LouisePrice/CPOSS_Database/git/trees/main?recursive=1' -o /tmp/cposs-tree.json
python3 scripts/update_catalogue.py --tree /tmp/cposs-tree.json
python3 scripts/update_catalogue.py --tree /tmp/cposs-tree.json --offline
```

Use `--cache PATH` for a persistent cache and `--output PATH` for a separate output directory. A truncated inventory or failed page download aborts the refresh before replacing the existing catalogue. Review the generated report after every refresh. Source link mismatches are reported rather than automatically corrected by fuzzy filename matching.

Runtime search uses only the static catalogue. It does not call GitHub's API or download structure files until a dataset is selected. Existing `?load=...` links using GitHub raw, GitHub blob, or database Pages URLs remain supported. `?settings=...` is superseded during initial loading; choosing a different dataset clears that old settings parameter. Import settings deliberately after loading to override the initial preset.

## Current source limitations

Snapshot refreshed on 27 October 2026, tree `6a77cc47b35f268f81a1d433b62c3e0917e20ffd`:

- 310 datasets and 236 case HTML pages; 307 datasets have an explicit case-page mapping.
- Collections contain 49 Blind Test, 26 CPOSS209, 30 unpublished, 25 Tricyclics, and 11 Dichloronitrobenzene datasets. Membership can overlap.
- Three datasets have no verified page association: `4C2NBMHA.json`, `5fluorouracilA.json`, and `PhloroglucinolDihydrateB.json`. They remain searchable by filename and have no inferred resource links.
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

Visualization tests cover all 230 group numbers, validated symbol aliases, constant and reordered space groups, numeric strings, missing/mixed markers, matching model selection, source immutability/exports, all load entry points, initial-preset priority and later manual overrides. The existing resource tests cover Urea's two audited archives, case associations and unavailable states. `tests/embedded.html` exercises the real navigator with embedded numeric, saved, categorical and missing-property fixtures. `plot-settings.json` and `urea-settings.json` can be imported after loading to test deliberate overrides; their presence in an initial URL does not override the preset.

For manual responsive checks, open <http://127.0.0.1:8765/tests/responsive.html> and switch among the provided iframe viewport widths. Check search, the five collections, keyboard selection, preview opening/closing, plot resizing and settings. This is a test harness, not part of the navigator interface.

Custom UI code lives in `assets/navigator.js` and `assets/navigator.css`; catalogue/search helpers live in `assets/catalogue.js`; plot defaults and settings precedence live in `assets/visualization.js`. The existing embedded Chemiscope and jQuery libraries are preserved. `old_index.html` is historical and is not used to generate metadata.
