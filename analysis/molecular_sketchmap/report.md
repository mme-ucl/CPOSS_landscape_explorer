# CPOSS molecular sketch-map: methods and quality report

## Coverage and structure counts

All **311 datasets** were attempted at frozen source revision `d65c1732ab6db46b8af34e0646a760c56a8d559c`, accessed 2026-10-23. The complete inventory contains **519,167 RES structure files in 509 documented energy-model ZIPs**. Molecules were extracted for **308 datasets**, representing **519,004 files** (99.969% of inventory files). Counts include separate model-specific representations; geometric uniqueness is unknown. The three excluded datasets account for **163 files**:

| Dataset | Archived files | Reason |
| --- | --- | --- |
| 25-dichloronitrobenzeneA | 70 | Atom SFAC index outside reported element list |
| 35-dichloronitrobenzeneA | 74 | Atom SFAC index outside reported element list |
| TetrachlorobenzeneA | 19 | Element table conflicts with atom labels and reported formula: [('C1', 'B'), ('C4', 'B'), ('C2', 'B'), ('C5', 'B'), ('C1', 'B')] |

The first two files omit chlorine from their SFAC element lists while atom rows refer to a fifth scattering-factor index. TetrachlorobenzeneA declares boron for carbon-labelled ring atoms, contradicting its reported formula. No element identities were substituted. Original failed candidates are retained in `excluded_sources/` with their archive URLs and errors in the audit.

## Crystal and molecular selection

Models are ordered numerically, without inferring that model 1 is the most accurate. Within each selected archive, finite energies in TITL parentheses are ranked, after excluding filenames explicitly marked by nonempty Experimental Info fields in the corresponding workbook. Values are compared only within one model; units are not inferred from the title itself. The lowest valid candidate is retained, trying up to five candidates before moving to another documented model. Filename order is the recorded fallback for the **2 datasets** lacking parsable title energies. **4 selections** used a later candidate. Selection ranks, skipped models and rejection reasons remain in per-dataset JSON. Some experimental references may be unlabelled, so predicted/reference status is not guaranteed solely by this filtering rule.

SHELX LATT, SYMM, centring translations and inversion generate the unit cell. A periodic covalent graph uses 1.20 times ASE covalent radii; image offsets unwrap complete finite components, including molecules crossing cell faces and special positions. No structures were optimized, and no hydrogens or other atoms were added. Disorder, overlapping sites, unresolvable periodic networks and contradictory element assignments are flagged. Connectivity and, where possible, bond orders, formal charge and stereochemistry are inferred from coordinates with RDKit; they are not reported chemical assignments.

The principal component is the largest non-water component by heavy-atom count. Equivalent copies are selected deterministically in source/symmetry order; tied different connectivities are treated as ambiguous. **47 datasets** contain multiple molecular/ionic components, including salts with combined empirical source formulas. Full component counts per cell, reported stoichiometry, omitted component types and inferred charges are recorded in molecule JSON. This size-based choice describes a principal component, not the entire chemistry of a salt or cocrystal.

## Formula conflicts and unresolved chemistry

**11 datasets** have source formulas inconsistent with the reconstructed unit-cell composition. Coordinates with internally valid chemical connectivity are retained and flagged, including apparent C/H count mistakes, zero/O transcription errors and coformer formula differences. The extracted component is shown below for identification; for multicomponent systems it should not be compared directly with the full reported formula. Detailed reconstructed unit-cell formulas are in `source_issues.csv`. No source formula was changed.

This audit also exposed a defect in the preceding formula parser: whitespace removal joined separated numeric tokens in `N2 03` and `N2 02` into nitrogen counts of 203 and 202. That parser now rejects separated numeric tokens as ambiguous. The earlier database-in-numbers figure was regenerated with those three dataset formula calculations missing, removing two artificial high-mass molecular-system outliers. The archive total is unchanged. The present map uses extracted nuclear compositions and was unaffected by those erroneous formula-derived masses.

| Dataset | Reported full formula | Extracted component |
| --- | --- | --- |
| Bipy-2AminobenzoicA | (C7 H7 N1 O2)2 - C8 H7 N1 O4 | C10H8N2 |
| Bipy-AminobenzoicA | C7 H7 N1 O2 - C8 H7 N1 O4 | C10H8N2 |
| Dicyanobenzene-SuccinicA | C6 N2 H4 - C4 O4 H6 | C8H4N2 |
| DipicolinicAcidA | C8 H5 N1 O4 | C7H5NO4 |
| FenamicAcidA | C13 H12 N1 O2 | C13H11NO2 |
| IsobarbituricAcidA | C4 H4 N2 03 | C4H4N2O3 |
| IsobarbituricAcidB | C4 H4 N2 03 | C4H4N2O3 |
| NaphthaleneA | C8 H10 | C10H8 |
| NaphthaleneB | C8 H10 | C10H8 |
| PiracetamA | C6 H10 N2 02 | C6H10N2O2 |
| QuinoliniumFumarateA | C9 H8 N1 - C4 H4 O4 | C9H8N |

**3 components** have formula-consistent finite geometry but unresolved RDKit bond orders: BTXXVIIIA, BTXXVIIIB, DiaminoDinitroPyridineOxideA. Their SDF bonds encode inferred connectivity with single-bond placeholders, explicitly labelled `connectivity_only_unresolved_bond_orders`; formal charge and canonical chemical identity are left unassigned. XYZ coordinates and element identities are available, and their SOAP descriptors do not depend on bond orders. These three points should not be used as validated chemical graphs.

## Molecular representation and sketch-map

DScribe SOAP uses all atoms, including hydrogen, with a shared element set `H, C, N, O, F, Si, S, Cl, Cu, Br, I`; periodicity is disabled after extraction. Settings: cutoff 4.5 A, Gaussian width 0.4 A, Gaussian radial basis, n_max=6, l_max=4, outer averaging of atomic power spectra, and per-molecule L2 normalization. The result has **11,055 features**. There is no per-feature standardization, explicit molecular-mass feature or explicit atom-count feature. Averaging removes extensive size scaling; relative composition and local geometry within the cutoff determine similarity. Long-range shape beyond the cutoff, enantiomeric differences, crystal packing, complete conformational ensembles and omitted coformers are not represented.

The molecular kernel is `K_ij=(x_i dot x_j)^2`; distance is `sqrt(max(0,2-2K_ij))`. The dot product uses DScribe's compact power-spectrum entries directly; this is a defined SOAP-feature polynomial kernel, without additional reweighting to reconstruct duplicated terms of the original analytical SOAP kernel. Rotation, translation and atom-permutation invariance were checked on an actual extracted molecule: maximum normalized descriptor difference **7.08e-16**. The normalized descriptors, kernel and complete indexed distance matrix are supplied in NPZ and CSV.

The genuine **scikit-matter 0.4.1 SketchMap** estimator is used with precomputed distances. Both sigmoid exponent pairs are (1,4), appropriate to the cited molecular mapping protocol, and sigma is 0.8 times the positive-distance histogram mode, giving **0.496798**. Histogram bins use the Freedman-Diaconis estimate clipped to 30-80. Optimization uses L-BFGS-B, 100 raw-distance refinement steps, up to 2,500 main iterations and five gradient-based annealing levels ending in pure sigmoid stress. All datasets have equal weight; structure counts do not enter descriptors, initialization or fitting.

Five initializations use classical MDS coordinates, unperturbed for seed 0 and perturbed for seeds 17, 41, 83 and 137 (Gaussian SD 0.25 times coordinate RMS). The minimum-stress run, seed **41**, is refined for up to 5,000 further iterations. A rigid rotation/reflection sets the page orientation; no individual coordinates are shifted or jittered. The displayed orientation has no intrinsic physical meaning. Parameter values, source/code hashes, package versions and all run coordinates are archived.

## Projection quality and sensitivity

- Final mean squared transformed-distance stress: **0.00628435**.
- Spearman correlation of all high-/low-dimensional pair distances: **0.9381**.
- Trustworthiness at 10 neighbours: **0.9600**.
- Original 10-neighbour retention: **0.5912**. The projection does not preserve every molecular neighbour.
- Extra refinement changed stress from **0.0062843524** to **0.0062843476** in 2 iterations; maximum absolute analytical stress-gradient component is **4.53e-07**. This is a convergence diagnostic, not proof of a global minimum.
- Across initializations, pair-distance correlations with the chosen map are at least **0.9943**, with 10-neighbour agreement **0.949-0.999**. Rigid Procrustes relative RMS can reach **0.242**, so some island positions vary despite stable distance/neighbour relationships.
- Changing sigma by -20%/+20% gives pair-distance correlations with the chosen map of **0.9923-0.9944**, and 10-neighbour agreements **0.892-0.935**. These settings are a sensitivity check, not a visual tuning procedure.

## Repeated identities and display

There are **210 principal constitutional identity keys**, of which **69 occur in multiple datasets**. Unresolved graphs use formula-only keys and are separately flagged. Comparisons of repeated identities yield **97 calculable heavy-atom, symmetry-matched RMSDs**, ranging **0.000075-3.595763 A**; the same constitution can have different conformations. RMSDs use proper rotational alignment (no coordinate reflection), up to 10,000 atom mappings, and the first dataset in each identity group as reference. They are not exhaustive all-pair conformational comparisons. The unresolved metal-complex identity group has no graph-matched RMSD.

**0 dataset pairs** have SOAP distances below 1e-6. Separate points are retained at their fitted coordinates; no offset is introduced to make them appear distinct. Large markers are drawn first and smaller markers afterward. Overlap can hide points, so the complete dataset table, rather than visual point counting, defines coverage.

Marker area is **1.8 sqrt(N) square points**, with an explicit reference-bubble legend. Square-root area compression keeps small datasets visible over the 11-20408 file range; area is not linear in count. The map colours use the current truncated Plasma ramp and logarithmic mass of the extracted component, rather than the full salt/formula-unit mass. The eight callouts are **urea, succinic acid, aspirin, paracetamol, caffeine, carbamazepine, naproxen, chlorothalonil**. These are curated familiar compounds with explicit experimental crystal references in their CPOSS pages, covering hydrogen-bonding, aromatic, pharmaceutical and halogenated chemistry. Selection is illustrative rather than farthest-point sampling; the rationale and CSD reference codes are in `callout_selection.json` and `tables/callouts.csv`. The evidence table `inputs/callout_experimental_references.csv` contains **99 dataset-reference records** with source URLs and experimental context. It does not imply that the selected predicted packing or conformer has been observed experimentally. The exact same molecular representatives remain in the map and callouts; no coordinates or descriptors were changed for this presentation revision.

Assignment to surrounding positions minimizes leader length. The current ball-and-stick callouts use the **Tachyon 0.99b6 CPU ray tracer**, the rendering engine used by VMD, with a matte/chalky ambient-occlusion appearance. They are native sphere/cylinder scenes, using the original full-precision nuclear coordinates and inferred connectivity: sphere scale 0.28 (hydrogens 0.23), stick radius 0.12 A, orthographic camera and conventional element colours. Frozen camera rotations preserve the approved views without changing geometry. Ambient-occlusion settings are 0.8 ambient, 0.3 direct and 128 ray samples, with diffuse coefficient 1 and specular/Phong coefficients 0. Individual white-background RGB PNGs are 1800 x 1200 pixels with 600 dpi metadata; the full A4 PNG is 300 dpi. The PDF retains vector map points, leaders, colourbar and text, with native-resolution molecular images. Helvetica is used throughout and embedded in the PDF. Native scene files, logs, renderer/source hashes and settings are in `figures/callouts_ao/` and `data/tachyon_rendering.json`; build/reproduction instructions are in `tachyon_build.md`. Earlier PyMOL images and sessions remain as view provenance.

The visible title, dataset/count subtitle and bottom exclusion/coformer notes were removed at the author's request. Their scientific context remains in the standalone caption and report. Map coordinates, marker sizing/colour, molecular selection and archive counts are unchanged.

## Primary methodological references

- [scikit-matter SketchMap API](https://scikit-matter.readthedocs.io/en/stable/references/decomposition.html#sketchmap) and [documented example](https://scikit-matter.readthedocs.io/en/stable/examples/decomposition/sketchmap.html).
- [Mapping and classifying molecules from a high-throughput structural database](https://pmc.ncbi.nlm.nih.gov/articles/PMC5289135/): molecular SOAP/sketch-map interpretation and sigmoid parameter protocol.
- [DScribe SOAP documentation](https://singroup.github.io/dscribe/latest/tutorials/descriptors/soap.html).
- [SHELXL instructions](https://shelx.uni-goettingen.de/shelxl_html.php): element indices, symmetry and lattice conventions.
- [RDKit coordinate-based bond assignment](https://www.rdkit.org/docs/source/rdkit.Chem.rdDetermineBonds.html).
- [VMD ambient-occlusion rendering](https://www.ks.uiuc.edu/Research/vmd/minitutorials/tachyonao/) and [Tachyon renderer source](https://github.com/thesketh/Tachyon).
- [PyMOL ball-and-stick representation](https://wiki.pymol.org/index.php/Ball_and_Stick) and [open-source PyMOL](https://github.com/schrodinger/pymol-open-source).
