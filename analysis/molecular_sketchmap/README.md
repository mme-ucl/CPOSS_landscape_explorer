# CPOSS molecular sketch-map

One isolated molecular representative per dataset, mapped with genuine scikit-matter sketch-map using molecular SOAP distances. The final map includes **308 of 311 datasets** and represents **519,004 of 519,167 archived structure files**. Three inconsistent source element tables are excluded and documented. The marker **area is proportional to the square root of the archive count**, with a numerical bubble legend. Counts do not weight the embedding.

## Deliverables

- `output/pdf/cposs_molecular_sketchmap.pdf`: A4 figure with vector map/text, eight high-resolution matte ambient-occlusion molecular callouts and embedded Helvetica.
- `figures/cposs_molecular_sketchmap.png`: same page at 300 dpi.
- `figures/sketchmap_diagnostics.png`: distance, stress and stability diagnostics.
- `caption.md`, `summary.md`, `report.md`: standalone caption, short findings report, full scientific methods and limitations.
- `molecules/`: extracted XYZ and SDF files, plus complete per-dataset JSON audits. Three SDFs have unresolved bond orders and are explicitly connectivity-only.
- `selected_crystals/`: original selected RES files, unchanged from their verified archives.
- `excluded_sources/`: original source files with contradictory element tables.
- `tables/dataset_embedding.csv`: all 311 datasets, archived counts, source/model/crystal selections, molecular identity, geometry validation, map coordinates and exclusions.
- `tables/provenance.csv`, `source_issues.csv`, `exclusions.csv`: reported/calculated/inferred/missing statuses and source URLs.
- `tables/molecular_distances.csv`, `data/molecular_descriptors.npz`: full indexed molecular distances, normalized SOAP vectors and kernel.
- `data/sketchmap_runs.npz`, `tables/optimization_runs.csv`, `initialization_stability.csv`: all five initialization runs, two sigma sensitivity runs and diagnostics.
- `tables/repeated_identity_conformations.csv`, `coincident_descriptors.csv`, `callouts.csv`: repeated-molecule comparisons and traceable callout choices.
- `figures/callouts_ao/`: current Tachyon matte/chalky ambient-occlusion PNGs (1800 x 1200, 600 dpi metadata), native `.dat` scenes and logs.
- `figures/callouts/`: preceding PyMOL images and editable `.pse` sessions, preserved as camera/view provenance.
- `callout_selection.json`, `inputs/callout_experimental_references.csv`: eight curated experimentally characterized compounds, CSD reference codes and 99 dataset-reference records. Experimental evidence identifies the compounds; it does not establish the selected predicted packing or conformer as experimental.
- `render_callouts_tachyon.py`, `tachyon_build.md`, `data/tachyon_rendering.json`: current renderer, build instructions, settings and hashes. Tachyon 0.99b6 was used.
- `render_callouts_pymol.py`, `pymol_environment.yml`, `data/pymol_rendering.json`: preceding PyMOL renderer and settings, retained for provenance.
- `inputs/`: original reconciled inventory, model archive audit and frozen source revision. These are copied from the preceding database-in-numbers analysis and preserved unchanged.
- `parameters.json`, `verification.json`: exact settings, software versions, hashes and output checks.

## Reproduce

Python 3.12+ and a licensed local Helvetica font are required. No proprietary font is redistributed. The macOS default is `/System/Library/Fonts/Helvetica.ttc`; on other platforms provide `--font /path/to/Helvetica.ttf` to plotting/report commands, with regular/bold faces alongside it. Missing Helvetica produces an error.

Run from this directory:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt

# Recreate the main figure from delivered map coordinates; no network needed.
.venv/bin/python plot.py

# Rebuild descriptors and all sketch-map runs from delivered molecules.
.venv/bin/python embed.py
.venv/bin/python plot.py
.venv/bin/python analyse_results.py

# Validate the scientific rules and final outputs.
.venv/bin/python -m unittest -v test_science.py
.venv/bin/python verify_outputs.py

# Independently repeat selection and extraction from original source archives.
# Downloads only if cached originals are absent; sources are checksum-verified.
.venv/bin/python extract_molecules.py --force
.venv/bin/python embed.py
.venv/bin/python plot.py
.venv/bin/python analyse_results.py
.venv/bin/python verify_outputs.py
```

The delivered current callout PNGs are sufficient to recreate the main figure without installing a renderer. To rerender the matte ambient-occlusion callouts from the source coordinates, build or install Tachyon as described in `tachyon_build.md` and run:

```sh
.venv/bin/python render_callouts_tachyon.py --tachyon /path/to/tachyon
.venv/bin/python plot.py
.venv/bin/python verify_outputs.py
```

The title, dataset/count subtitle and bottom explanatory notes have been removed from the figure. Coverage and limitations remain in `caption.md` and `report.md`.

The callouts are urea, succinic acid, aspirin, paracetamol, caffeine, carbamazepine, naproxen and chlorothalonil. This curated selection replaces descriptor-space sampling in response to the request for familiar experimentally characterized examples. Callouts use exactly the extracted representatives used in the embedding. Only the views and presentation change.

The original ZIPs and workbooks are cached by Git blob SHA at `/tmp/cposs-model-archive-cache/` and `/tmp/cposs-workbook-cache/`. To prohibit source downloads use `extract_molecules.py --offline`. Without `--force`, existing per-dataset extraction audits are reused. To inspect a subset use `--dataset DatasetID ...`; this writes subset audit tables and leaves the complete inventory table intact. The extraction preserves the coordinate files and reported metadata, makes no geometry optimizations and adds no missing atoms. Full source archives are excluded from the deliverable; selected original crystals and all extracted molecules are included.

SOAP captures relative composition and local molecular geometry, not crystal packing, enantiomeric identity or complete multicomponent chemistry. Source formulas and inferred molecular assignments are distinct fields. Refer to the report before interpreting map proximity or reusing connectivity-only SDFs.
