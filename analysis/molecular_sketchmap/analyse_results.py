#!/usr/bin/env python3
"""Conformation comparisons, field provenance, diagnostics, caption and report."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import zipfile

import numpy as np
import pandas as pd
from rdkit import Chem
from rdkit.Chem import rdMolAlign
from scipy.spatial.distance import pdist, squareform

from extract_molecules import BASE, parse_res, write_json
from embed import sigmoid
from plot import helvetica
from matplotlib import pyplot as plt


def table(frame):
    return "\n".join(["| " + " | ".join(frame.columns) + " |", "| " + " | ".join(["---"]*len(frame.columns)) + " |"] + ["| " + " | ".join(str(v).replace("|", "/") for v in row) + " |" for row in frame.itertuples(index=False, name=None)])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--font",type=Path,default=Path("/System/Library/Fonts/Helvetica.ttc"))
    args=parser.parse_args()
    manifest=json.loads((BASE/"inputs/manifest.json").read_text())
    parameters=json.loads((BASE/"parameters.json").read_text())
    summary=json.loads((BASE/"data/embedding_summary.json").read_text())
    data=pd.read_csv(BASE/"tables/dataset_embedding.csv")
    count_sources=pd.read_csv(BASE/"inputs/dataset_archive_counts.csv").set_index("dataset_id")
    data["structure_count_source_urls"]=data.dataset_id.map(count_sources.archive_urls)
    data["structure_count_definition"]="RES files across all documented energy-model archives for this dataset; separate model representations retained; no geometric deduplication"
    data["source_revision"]=manifest["snapshot_revision"]
    data["accessed_date"]=manifest["accessed_date"]
    data.to_csv(BASE/"tables/dataset_embedding.csv",index=False)
    valid=data[data.included].sort_values("dataset_id").reset_index(drop=True)
    excluded=data[~data.included].copy()
    pairs=[]
    for identity,group in valid.groupby("constitution_smiles"):
        if len(group)<2:continue
        reference=group.iloc[0]
        for _,other in group.iloc[1:].iterrows():
            row={"reference_dataset":reference.dataset_id,"dataset_id":other.dataset_id,"constitution":identity,"map_distance":float(np.linalg.norm(other[["sketchmap_x","sketchmap_y"]].to_numpy(float)-reference[["sketchmap_x","sketchmap_y"]].to_numpy(float))),"heavy_atom_rmsd_angstrom":None,"status":"missing"}
            try:
                if reference.bond_assignment_status!="inferred_from_coordinates" or other.bond_assignment_status!="inferred_from_coordinates":raise ValueError("Bond-order identity unresolved; no atom-mapped RMSD assigned")
                reference_mol=Chem.SDMolSupplier(str(BASE/"molecules"/(reference.dataset_id+".sdf")),removeHs=True)[0]
                other_mol=Chem.SDMolSupplier(str(BASE/"molecules"/(other.dataset_id+".sdf")),removeHs=True)[0]
                row["heavy_atom_rmsd_angstrom"]=float(rdMolAlign.GetBestRMS(other_mol,reference_mol,maxMatches=10000))
                row["status"]="calculated"
            except Exception as exc:row["reason"]=str(exc)
            pairs.append(row)
    conformation=pd.DataFrame(pairs)
    conformation.to_csv(BASE/"tables/repeated_identity_conformations.csv",index=False)
    descriptors=np.load(BASE/"data/molecular_descriptors.npz")
    embedding=valid[["sketchmap_x","sketchmap_y"]].to_numpy()
    distances=descriptors["distances"]
    low=squareform(pdist(embedding))
    near=[]
    for i,j in zip(*np.where(np.triu(distances<1e-6,1))):
        near.append({"dataset_a":valid.iloc[i].dataset_id,"dataset_b":valid.iloc[j].dataset_id,"descriptor_distance":distances[i,j],"map_distance":low[i,j]})
    pd.DataFrame(near,columns=["dataset_a","dataset_b","descriptor_distance","map_distance"]).to_csv(BASE/"tables/coincident_descriptors.csv",index=False)
    issues=[];provenance=[]
    for row in data.itertuples():
        raw=json.loads((BASE/"molecules"/(row.dataset_id+".json")).read_text())
        if row.included:
            crystal,_=parse_res((BASE/"selected_crystals"/(row.dataset_id+".res")).read_text())
            if row.formula_validation!="matches_full_unit_cell_stoichiometry":
                issues.append({"dataset_id":row.dataset_id,"issue":"source_formula_conflict","reported_formula":row.reported_formula,"reconstructed_unit_cell_formula":crystal.get_chemical_formula(),"selected_component_formula":row.selected_formula,"source_url":row.source_url,"archive_url":row.archive_url,"selected_filename":row.selected_filename,"action":"Retained extracted coordinates with flag; source formula unchanged"})
            if row.bond_assignment_status!="inferred_from_coordinates":
                issues.append({"dataset_id":row.dataset_id,"issue":"bond_orders_unresolved","selected_component_formula":row.selected_formula,"archive_url":row.archive_url,"selected_filename":row.selected_filename,"action":"SOAP uses validated nuclear coordinates; SDF explicitly connectivity-only; no charge assigned"})
            values=[("selected_filename",row.selected_filename,"reported",row.archive_url,"Original coordinate member"),
                    ("molecular_coordinates",str(row.dataset_id)+".xyz","calculated",row.archive_url,"SHELX symmetry expansion and periodic image unwrapping; no geometry optimization or atom additions"),
                    ("selected_formula",row.selected_formula,"calculated",row.archive_url,"Count elements in reconstructed principal component"),
                    ("principal_component_selection",raw["principal_selection"],"inferred",row.archive_url,"Size-based representative; other components retained in audit"),
                    ("connectivity_and_bond_orders",row.bond_assignment_status,"inferred",row.archive_url,"Distance-based connectivity; RDKit xyz2mol where assignable"),
                    ("formula_validation",row.formula_validation,"calculated",row.source_url,"Compare expanded unit-cell composition with reported full formula"),
                    ("sketchmap_coordinates",json.dumps([row.sketchmap_x,row.sketchmap_y]),"calculated",row.archive_url,"SOAP descriptors and scikit-matter sketch-map; parameters.json")]
        else:
            issues.append({"dataset_id":row.dataset_id,"issue":"excluded_element_table","reported_formula":row.reported_formula,"archive_url":row.archive_url,"action":row.error})
            values=[("molecular_coordinates",None,"missing",row.archive_url,row.error),("sketchmap_coordinates",None,"missing",row.archive_url,"Excluded source element conflict")]
            (BASE/"excluded_sources").mkdir(exist_ok=True)
            candidate=raw["rejected_candidates"][0]["filename"]
            original=BASE/"excluded_sources"/(row.dataset_id+".res")
            if not original.exists():
                with zipfile.ZipFile(Path("/tmp/cposs-model-archive-cache",raw["archive_git_blob_sha"]+".zip")) as archive:
                    original.write_bytes(archive.read(candidate))
        values += [("archived_structure_files",row.structure_count,"calculated",row.structure_count_source_urls,row.structure_count_definition)]
        for field,value,status,source,note in values:
            provenance.append({"dataset_id":row.dataset_id,"field":field,"value":value,"status":status,"source_url":source,"note":note,"source_revision":manifest["snapshot_revision"],"accessed_date":manifest["accessed_date"]})
    pd.DataFrame(issues).to_csv(BASE/"tables/source_issues.csv",index=False)
    pd.DataFrame(provenance).to_csv(BASE/"tables/provenance.csv",index=False)
    excluded.to_csv(BASE/"tables/exclusions.csv",index=False)
    # Separate quality plots are supplementary, leaving the main figure uncluttered.
    helvetica(args.font)
    fig,axes=plt.subplots(2,2,figsize=(7.1,5.2))
    upper=np.triu_indices(len(valid),1); sigma=parameters["sketchmap"]["sigma"]
    axes[0,0].hist(distances[upper],bins=45,color="#9651A5",alpha=.85)
    axes[0,0].axvline(sigma,color="#E8904B",lw=1.5,label=f"sigma = {sigma:.3f}")
    axes[0,0].set(xlabel="Molecular SOAP distance",ylabel="Dataset pairs");axes[0,0].legend(frameon=False,fontsize=7)
    axes[0,1].hexbin(sigmoid(distances[upper],sigma),sigmoid(low[upper],sigma),gridsize=45,mincnt=1,cmap="magma",bins="log")
    axes[0,1].plot([0,1],[0,1],color="#A6ADB2",lw=.7)
    axes[0,1].set(xlabel="Transformed molecular distance",ylabel="Transformed map distance")
    runs=pd.read_csv(BASE/"tables/optimization_runs.csv"); starts=runs[runs.kind=="initialization"]
    axes[1,0].bar(starts.seed.astype(str),starts.sigmoid_pair_mse,color="#C56A89")
    axes[1,0].set(xlabel="Initialization seed",ylabel="Mean squared sigmoid stress")
    stability=pd.read_csv(BASE/"tables/initialization_stability.csv")
    axes[1,1].bar(stability.seed.astype(str),stability.neighbor_retention_k10_to_selected,color="#7965B3")
    axes[1,1].set(xlabel="Initialization seed",ylabel="10-neighbour agreement with selected map",ylim=(0,1.03))
    for ax in axes.flat:
        ax.spines[["top","right"]].set_visible(False);ax.tick_params(labelsize=7,length=2)
    fig.tight_layout(pad=1.5)
    fig.savefig(BASE/"figures/sketchmap_diagnostics.png",dpi=300);plt.close(fig)
    selection=json.loads((BASE/"callout_selection.json").read_text())
    rendering=json.loads((BASE/"data/tachyon_rendering.json").read_text())
    callout_evidence=pd.read_csv(BASE/"inputs/callout_experimental_references.csv")
    callout_names=", ".join(r["label"].lower() for r in selection["molecules"])
    metrics=summary["metrics"]
    flags=valid[valid.formula_validation!="matches_full_unit_cell_stoichiometry"]
    unresolved=valid[valid.bond_assignment_status!="inferred_from_coordinates"]
    duplicate_groups=int((valid.constitution_smiles.value_counts()>1).sum())
    rms=conformation.heavy_atom_rmsd_angstrom.dropna()
    caption=f"""The molecular landscape of CPOSS. The horizontal and vertical coordinates are dimensionless sketch-map coordinates; their orientation is arbitrary and neither axis corresponds to an individual molecular property. Each circle represents one CSP dataset ({len(valid)} of {len(data)} datasets; {int(valid.structure_count.sum()):,} archived structure files represented). A representative crystal was selected from the lowest-numbered documented energy-model archive with a reconstructable molecule, using the lowest finite energy printed in its TITL field after excluding explicit experimental-reference labels; up to five candidates per model were validated. Complete molecules were reconstructed using SHELX symmetry and periodic covalent connectivity. The largest non-water component was retained, with coformers, counterions and stoichiometry recorded separately. The map compares L2-normalized, outer-averaged SOAP power spectra (all atoms and elements; cutoff 4.5 A, Gaussian width 0.4 A, n_max=6, l_max=4; {parameters['descriptor']['features']:,} features). Molecular distances are sqrt(2-2K), with K the squared normalized descriptor dot product. scikit-matter sketch-map minimizes sigmoid-transformed pair-distance stress with sigma={sigma:.4f}, high- and low-dimensional exponents (1,4), and equal dataset weights. Five initializations were tested and the lowest-stress solution was refined. Marker area is 1.8 sqrt(N) square points, where N is the number of model-specific RES files across the dataset's documented archives; the square-root compression keeps small datasets visible. Counts do not weight the embedding and have not been geometrically deduplicated. Colour encodes the extracted component's molar mass on a logarithmic truncated-Plasma scale. Ball-and-stick callouts use matte VMD-inspired materials and native Tachyon ambient-occlusion ray tracing from the same extracted coordinates used in the map. Eight recognizable, experimentally characterized compounds were curated: {callout_names}. Their CPOSS experimental crystal references establish compound identities, not experimental observation of the selected predicted packing or conformer. Standard element colours are used. Leader lines terminate at unjittered dataset positions. Repeated identities and coincident points remain separate dataset records and can overlap. Dark outlines flag {len(flags)} source-formula conflicts, retained without editing source formulas. {len(excluded)} inconsistent element tables prevented molecular assignment and are excluded. Bond orders could not be resolved for {len(unresolved)} formula-consistent components; their SDFs are connectivity-only, and SOAP uses their nuclear coordinates. SOAP does not resolve enantiomers, crystal packing or omitted coformers; proximity reflects composition and local molecular geometry rather than a unique chemical classification.\n"""
    (BASE/"caption.md").write_text(caption)
    exclusion_table=excluded[["dataset_id","structure_count","error"]].rename(columns={"dataset_id":"Dataset","structure_count":"Archived files","error":"Reason"})
    flag_table=flags[["dataset_id","reported_formula","selected_formula"]].rename(columns={"dataset_id":"Dataset","reported_formula":"Reported full formula","selected_formula":"Extracted component"})
    stability_min=float(stability.distance_spearman_to_selected.min())
    sensitivity=pd.DataFrame(summary["sigma_sensitivity"])
    report=f"""# CPOSS molecular sketch-map: methods and quality report

## Coverage and structure counts

All **{len(data)} datasets** were attempted at frozen source revision `{manifest['snapshot_revision']}`, accessed {manifest['accessed_date']}. The complete inventory contains **{int(data.structure_count.sum()):,} RES structure files in {len(pd.read_csv(BASE/'inputs/structure_archive_counts.csv'))} documented energy-model ZIPs**. Molecules were extracted for **{len(valid)} datasets**, representing **{int(valid.structure_count.sum()):,} files** ({100*valid.structure_count.sum()/data.structure_count.sum():.3f}% of inventory files). Counts include separate model-specific representations; geometric uniqueness is unknown. The {len(excluded)} excluded datasets account for **{int(excluded.structure_count.sum())} files**:

{table(exclusion_table)}

The first two files omit chlorine from their SFAC element lists while atom rows refer to a fifth scattering-factor index. TetrachlorobenzeneA declares boron for carbon-labelled ring atoms, contradicting its reported formula. No element identities were substituted. Original failed candidates are retained in `excluded_sources/` with their archive URLs and errors in the audit.

## Crystal and molecular selection

Models are ordered numerically, without inferring that model 1 is the most accurate. Within each selected archive, finite energies in TITL parentheses are ranked, after excluding filenames explicitly marked by nonempty Experimental Info fields in the corresponding workbook. Values are compared only within one model; units are not inferred from the title itself. The lowest valid candidate is retained, trying up to five candidates before moving to another documented model. Filename order is the recorded fallback for the **{int(valid.selected_title_energy.isna().sum())} datasets** lacking parsable title energies. **{int((valid.selected_candidate_rank>1).sum())} selections** used a later candidate. Selection ranks, skipped models and rejection reasons remain in per-dataset JSON. Some experimental references may be unlabelled, so predicted/reference status is not guaranteed solely by this filtering rule.

SHELX LATT, SYMM, centring translations and inversion generate the unit cell. A periodic covalent graph uses 1.20 times ASE covalent radii; image offsets unwrap complete finite components, including molecules crossing cell faces and special positions. No structures were optimized, and no hydrogens or other atoms were added. Disorder, overlapping sites, unresolvable periodic networks and contradictory element assignments are flagged. Connectivity and, where possible, bond orders, formal charge and stereochemistry are inferred from coordinates with RDKit; they are not reported chemical assignments.

The principal component is the largest non-water component by heavy-atom count. Equivalent copies are selected deterministically in source/symmetry order; tied different connectivities are treated as ambiguous. **{int(valid.observed_multicomponent.sum())} datasets** contain multiple molecular/ionic components, including salts with combined empirical source formulas. Full component counts per cell, reported stoichiometry, omitted component types and inferred charges are recorded in molecule JSON. This size-based choice describes a principal component, not the entire chemistry of a salt or cocrystal.

## Formula conflicts and unresolved chemistry

**{len(flags)} datasets** have source formulas inconsistent with the reconstructed unit-cell composition. Coordinates with internally valid chemical connectivity are retained and flagged, including apparent C/H count mistakes, zero/O transcription errors and coformer formula differences. The extracted component is shown below for identification; for multicomponent systems it should not be compared directly with the full reported formula. Detailed reconstructed unit-cell formulas are in `source_issues.csv`. No source formula was changed.

This audit also exposed a defect in the preceding formula parser: whitespace removal joined separated numeric tokens in `N2 03` and `N2 02` into nitrogen counts of 203 and 202. That parser now rejects separated numeric tokens as ambiguous. The earlier database-in-numbers figure was regenerated with those three dataset formula calculations missing, removing two artificial high-mass molecular-system outliers. The archive total is unchanged. The present map uses extracted nuclear compositions and was unaffected by those erroneous formula-derived masses.

{table(flag_table)}

**{len(unresolved)} components** have formula-consistent finite geometry but unresolved RDKit bond orders: {', '.join(unresolved.dataset_id)}. Their SDF bonds encode inferred connectivity with single-bond placeholders, explicitly labelled `connectivity_only_unresolved_bond_orders`; formal charge and canonical chemical identity are left unassigned. XYZ coordinates and element identities are available, and their SOAP descriptors do not depend on bond orders. These three points should not be used as validated chemical graphs.

## Molecular representation and sketch-map

DScribe SOAP uses all atoms, including hydrogen, with a shared element set `{', '.join(parameters['descriptor']['species'])}`; periodicity is disabled after extraction. Settings: cutoff 4.5 A, Gaussian width 0.4 A, Gaussian radial basis, n_max=6, l_max=4, outer averaging of atomic power spectra, and per-molecule L2 normalization. The result has **{parameters['descriptor']['features']:,} features**. There is no per-feature standardization, explicit molecular-mass feature or explicit atom-count feature. Averaging removes extensive size scaling; relative composition and local geometry within the cutoff determine similarity. Long-range shape beyond the cutoff, enantiomeric differences, crystal packing, complete conformational ensembles and omitted coformers are not represented.

The molecular kernel is `K_ij=(x_i dot x_j)^2`; distance is `sqrt(max(0,2-2K_ij))`. The dot product uses DScribe's compact power-spectrum entries directly; this is a defined SOAP-feature polynomial kernel, without additional reweighting to reconstruct duplicated terms of the original analytical SOAP kernel. Rotation, translation and atom-permutation invariance were checked on an actual extracted molecule: maximum normalized descriptor difference **{summary['invariance_max_abs_error']:.2e}**. The normalized descriptors, kernel and complete indexed distance matrix are supplied in NPZ and CSV.

The genuine **scikit-matter {parameters['versions']['skmatter']} SketchMap** estimator is used with precomputed distances. Both sigmoid exponent pairs are (1,4), appropriate to the cited molecular mapping protocol, and sigma is 0.8 times the positive-distance histogram mode, giving **{sigma:.6f}**. Histogram bins use the Freedman-Diaconis estimate clipped to 30-80. Optimization uses L-BFGS-B, 100 raw-distance refinement steps, up to 2,500 main iterations and five gradient-based annealing levels ending in pure sigmoid stress. All datasets have equal weight; structure counts do not enter descriptors, initialization or fitting.

Five initializations use classical MDS coordinates, unperturbed for seed 0 and perturbed for seeds 17, 41, 83 and 137 (Gaussian SD 0.25 times coordinate RMS). The minimum-stress run, seed **{summary['selected_initialization_seed']}**, is refined for up to 5,000 further iterations. A rigid rotation/reflection sets the page orientation; no individual coordinates are shifted or jittered. The displayed orientation has no intrinsic physical meaning. Parameter values, source/code hashes, package versions and all run coordinates are archived.

## Projection quality and sensitivity

- Final mean squared transformed-distance stress: **{metrics['sigmoid_pair_mse']:.8f}**.
- Spearman correlation of all high-/low-dimensional pair distances: **{metrics['distance_spearman']:.4f}**.
- Trustworthiness at 10 neighbours: **{metrics['trustworthiness_k10']:.4f}**.
- Original 10-neighbour retention: **{metrics['neighbor_retention_k10']:.4f}**. The projection does not preserve every molecular neighbour.
- Extra refinement changed stress from **{summary['refinement']['stress_before']:.10f}** to **{summary['refinement']['stress_after']:.10f}** in {summary['refinement']['iterations']} iterations; maximum absolute analytical stress-gradient component is **{summary['refinement']['max_abs_stress_gradient']:.2e}**. This is a convergence diagnostic, not proof of a global minimum.
- Across initializations, pair-distance correlations with the chosen map are at least **{stability_min:.4f}**, with 10-neighbour agreement **{stability.neighbor_retention_k10_to_selected.min():.3f}-{stability.neighbor_retention_k10_to_selected.max():.3f}**. Rigid Procrustes relative RMS can reach **{stability.procrustes_relative_rms_no_scaling.max():.3f}**, so some island positions vary despite stable distance/neighbour relationships.
- Changing sigma by -20%/+20% gives pair-distance correlations with the chosen map of **{sensitivity.distance_spearman_to_selected.min():.4f}-{sensitivity.distance_spearman_to_selected.max():.4f}**, and 10-neighbour agreements **{sensitivity.neighbor_retention_k10_to_selected.min():.3f}-{sensitivity.neighbor_retention_k10_to_selected.max():.3f}**. These settings are a sensitivity check, not a visual tuning procedure.

## Repeated identities and display

There are **{valid.constitution_smiles.nunique()} principal constitutional identity keys**, of which **{duplicate_groups} occur in multiple datasets**. Unresolved graphs use formula-only keys and are separately flagged. Comparisons of repeated identities yield **{len(rms)} calculable heavy-atom, symmetry-matched RMSDs**, ranging **{rms.min():.6f}-{rms.max():.6f} A**; the same constitution can have different conformations. RMSDs use proper rotational alignment (no coordinate reflection), up to 10,000 atom mappings, and the first dataset in each identity group as reference. They are not exhaustive all-pair conformational comparisons. The unresolved metal-complex identity group has no graph-matched RMSD.

**{len(near)} dataset pairs** have SOAP distances below 1e-6. Separate points are retained at their fitted coordinates; no offset is introduced to make them appear distinct. Large markers are drawn first and smaller markers afterward. Overlap can hide points, so the complete dataset table, rather than visual point counting, defines coverage.

Marker area is **1.8 sqrt(N) square points**, with an explicit reference-bubble legend. Square-root area compression keeps small datasets visible over the {int(valid.structure_count.min())}-{int(valid.structure_count.max())} file range; area is not linear in count. The map colours use the current truncated Plasma ramp and logarithmic mass of the extracted component, rather than the full salt/formula-unit mass. The eight callouts are **{callout_names}**. These are curated familiar compounds with explicit experimental crystal references in their CPOSS pages, covering hydrogen-bonding, aromatic, pharmaceutical and halogenated chemistry. Selection is illustrative rather than farthest-point sampling; the rationale and CSD reference codes are in `callout_selection.json` and `tables/callouts.csv`. The evidence table `inputs/callout_experimental_references.csv` contains **{len(callout_evidence)} dataset-reference records** with source URLs and experimental context. It does not imply that the selected predicted packing or conformer has been observed experimentally. The exact same molecular representatives remain in the map and callouts; no coordinates or descriptors were changed for this presentation revision.

Assignment to surrounding positions minimizes leader length. The current ball-and-stick callouts use the **Tachyon 0.99b6 CPU ray tracer**, the rendering engine used by VMD, with a matte/chalky ambient-occlusion appearance. They are native sphere/cylinder scenes, using the original full-precision nuclear coordinates and inferred connectivity: sphere scale 0.28 (hydrogens 0.23), stick radius 0.12 A, orthographic camera and conventional element colours. Frozen camera rotations preserve the approved views without changing geometry. Ambient-occlusion settings are 0.8 ambient, 0.3 direct and 128 ray samples, with diffuse coefficient 1 and specular/Phong coefficients 0. Individual white-background RGB PNGs are 1800 x 1200 pixels with 600 dpi metadata; the full A4 PNG is 300 dpi. The PDF retains vector map points, leaders, colourbar and text, with native-resolution molecular images. Helvetica is used throughout and embedded in the PDF. Native scene files, logs, renderer/source hashes and settings are in `figures/callouts_ao/` and `data/tachyon_rendering.json`; build/reproduction instructions are in `tachyon_build.md`. Earlier PyMOL images and sessions remain as view provenance.

The figure retains the approved 55% larger typography, unlabelled map axes, palette and molecular callout style. Methodological explanations remain in the standalone caption and report. Source records, archive counts, descriptors and map coordinates were recalculated for the current JSON inventory.

## Primary methodological references

- [scikit-matter SketchMap API](https://scikit-matter.readthedocs.io/en/stable/references/decomposition.html#sketchmap) and [documented example](https://scikit-matter.readthedocs.io/en/stable/examples/decomposition/sketchmap.html).
- [Mapping and classifying molecules from a high-throughput structural database](https://pmc.ncbi.nlm.nih.gov/articles/PMC5289135/): molecular SOAP/sketch-map interpretation and sigmoid parameter protocol.
- [DScribe SOAP documentation](https://singroup.github.io/dscribe/latest/tutorials/descriptors/soap.html).
- [SHELXL instructions](https://shelx.uni-goettingen.de/shelxl_html.php): element indices, symmetry and lattice conventions.
- [RDKit coordinate-based bond assignment](https://www.rdkit.org/docs/source/rdkit.Chem.rdDetermineBonds.html).
- [VMD ambient-occlusion rendering](https://www.ks.uiuc.edu/Research/vmd/minitutorials/tachyonao/) and [Tachyon renderer source](https://github.com/thesketh/Tachyon).
- [PyMOL ball-and-stick representation](https://wiki.pymol.org/index.php/Ball_and_Stick) and [open-source PyMOL](https://github.com/schrodinger/pymol-open-source).
"""
    (BASE/"report.md").write_text(report)
    (BASE/"summary.md").write_text(f"""# Molecular sketch-map: findings

The figure maps **{len(valid)} of {len(data)} CPOSS datasets**, accounting for **{int(valid.structure_count.sum()):,} archived structure files**. All datasets were attempted. Three source element tables are contradictory and are excluded, covering {int(excluded.structure_count.sum())} files; their original coordinates and audit reasons are supplied.

One representative molecule is reconstructed from each selected crystal using periodic symmetry and covalent connectivity. For multicomponent systems the largest non-water component is represented; omitted coformers and counterions remain documented. Eleven reported formulas conflict with the coordinates and are flagged. Three formula-consistent molecular geometries have unresolved bond orders; their SDFs are explicitly connectivity-only.

The genuine scikit-matter sketch-map uses molecular SOAP-feature distances and equal dataset weights. Five initializations and two switching-distance sensitivity checks were performed. The selected map has a pair-distance Spearman correlation of **{metrics['distance_spearman']:.3f}**, trustworthiness at 10 neighbours of **{metrics['trustworthiness_k10']:.3f}**, and original-neighbour retention of **{metrics['neighbor_retention_k10']:.3f}**. These support a useful overview while documenting local distortions.

Circle area is proportional to **sqrt(archived file count)**; colour shows extracted-component molar mass. Eight 3D callouts now show curated compounds with explicit experimental crystal references: {callout_names}. They use native Tachyon ray tracing with matte, chalky ambient-occlusion shading inspired by VMD. The references establish experimentally characterized compounds; the displayed geometries remain the selected dataset representatives, not asserted experimental conformers. The A4 PDF combines vector map/text with high-resolution molecular renders, and the full-page PNG is 300 dpi. Both use actual Helvetica.

The representation describes composition and local molecular geometry. It does not resolve crystal packing, enantiomers, complete conformational ensembles or full multicomponent chemistry. See `report.md` for methods, all source conflicts and stability limits, and `caption.md` for the standalone figure caption.
""")
    print(f"Wrote report, caption, provenance, {len(pairs)} repeated-identity comparisons, {len(issues)} source issues",flush=True)


if __name__=="__main__":main()
