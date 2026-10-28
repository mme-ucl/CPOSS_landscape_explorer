#!/usr/bin/env python3
"""Verify per-dataset molecules, accounting, descriptors, map and final graphics."""
from collections import Counter
import hashlib
import json
import numpy as np
import pandas as pd
from PIL import Image
from pypdf import PdfReader
from rdkit import Chem
from scipy.spatial.distance import pdist,squareform
from extract_molecules import BASE,write_json
from embed import metrics


def main():
    data=pd.read_csv(BASE/"tables/dataset_embedding.csv")
    source=pd.read_csv(BASE/"inputs/datasets.csv")
    counts=pd.read_csv(BASE/"inputs/dataset_archive_counts.csv").set_index("dataset_id")
    valid=data[data.included].sort_values("dataset_id").reset_index(drop=True)
    parameters=json.loads((BASE/"parameters.json").read_text())
    summary=json.loads((BASE/"data/embedding_summary.json").read_text())
    figure=json.loads((BASE/"data/figure_manifest.json").read_text())
    checks=[]
    def check(value,note):
        if not value:raise AssertionError(note)
        checks.append(note)
    check(data.dataset_id.is_unique and set(data.dataset_id)==set(source.dataset_id),"All source datasets attempted exactly once")
    check(data.set_index("dataset_id").structure_count.sort_index().equals(counts.archive_coordinate_files.sort_index()),"Every dataset's count equals verified archive count")
    check(data.loc[~data.included,["sketchmap_x","sketchmap_y","marker_area_pt2"]].isna().all().all(),"Excluded datasets have missing coordinates and marker areas, never fabricated zeros")
    check(len(data)==310 and int(data.structure_count.sum())==517594,"Current 310-record inventory retains 517,594 archived structure files")
    check(int(valid.structure_count.sum())==figure["represented_structure_files"],"Represented structure count matches figure metadata")
    for row in valid.itertuples():
        label=row.dataset_id
        record=json.loads((BASE/"molecules"/(label+".json")).read_text())
        xyz=(BASE/"molecules"/(label+".xyz")).read_text().splitlines()
        raw=(BASE/"selected_crystals"/(label+".res")).read_bytes()
        check(hashlib.sha256(raw).hexdigest()==record["selected_file_sha256"],label+": selected original coordinate SHA verified")
        check(int(xyz[0])==record["selected_atoms"]==len(record["symbols"]),label+": XYZ/JSON molecular atom counts agree")
        xyz_symbols=[r.split()[0] for r in xyz[2:] if r.strip()]
        xyz_positions=np.asarray([list(map(float,r.split()[1:4])) for r in xyz[2:] if r.strip()])
        check(xyz_symbols==record["symbols"] and np.allclose(xyz_positions,record["coordinates_angstrom"],atol=1e-8),label+": XYZ preserves extracted elements and geometry")
        molecule=Chem.SDMolSupplier(str(BASE/"molecules"/(label+".sdf")),removeHs=False,sanitize=False)[0]
        check(molecule is not None and [a.GetSymbol() for a in molecule.GetAtoms()]==record["symbols"],label+": SDF preserves all atoms and hydrogens")
        check(np.allclose(molecule.GetConformer().GetPositions(),record["coordinates_angstrom"],atol=5.1e-5,rtol=0),label+": SDF preserves geometry within format rounding")
        check(molecule.GetProp("bond_assignment_status")==record["bond_assignment_status"],label+": SDF carries inferred/unresolved bond status")
        if record["bond_assignment_status"]=="connectivity_only_unresolved_bond_orders":
            check(record["inferred_formal_charge"] is None and not record["selected_smiles"],label+": unresolved chemical assignments remain missing")
    npz=np.load(BASE/"data/molecular_descriptors.npz")
    distance=npz["distances"];vectors=npz["normalized_soap"];kernel=npz["soap_kernel"]
    check(list(npz["dataset_ids"])==list(valid.dataset_id),"Descriptor, distance and embedding dataset order agrees")
    check(vectors.shape==(len(valid),parameters["descriptor"]["features"]) and np.isfinite(vectors).all(),"Descriptor shape and finite values are valid")
    check(np.allclose(np.linalg.norm(vectors,axis=1),1),"Molecular descriptors are normalized equally")
    check(np.isfinite(distance).all() and np.all(distance>=0) and np.allclose(distance,distance.T) and np.allclose(np.diag(distance),0),"Distance matrix is finite, nonnegative, symmetric, with zero diagonal")
    expected=np.sqrt(np.maximum(0,2-2*kernel));np.fill_diagonal(expected,0)
    check(np.allclose(distance,expected),"Distances match the documented molecular SOAP kernel")
    check(summary["invariance_max_abs_error"]<1e-6,"Rotation/translation/permutation invariance passed on source coordinates")
    check(np.allclose(valid.marker_area_pt2,1.8*np.sqrt(valid.structure_count)),"Marker areas follow the stated square-root count mapping")
    embedding=valid[["sketchmap_x","sketchmap_y"]].to_numpy()
    measured=metrics(distance,embedding,parameters["sketchmap"]["sigma"])
    check(all(np.isclose(measured[k],summary["metrics"][k],atol=1e-11) for k in measured),"Projection-quality metrics recompute from delivered matrices")
    runs=pd.read_csv(BASE/"tables/optimization_runs.csv")
    check(len(runs[runs.kind=="initialization"])==5 and len(runs[runs.kind=="sigma_sensitivity"])==2,"Five initializations and two switching-distance sensitivity runs are delivered")
    check(parameters["sketchmap"]["implementation"]=="skmatter.decomposition.SketchMap" and parameters["sketchmap"]["mixing_ratio"]==0,"Published sketch-map estimator ends with pure sigmoid stress")
    check(summary["refinement"]["stress_after"]<=summary["refinement"]["stress_before"] and summary["refinement"]["max_abs_stress_gradient"]<1e-4,"Extra refinement confirms small stress change and residual gradient")
    callouts=pd.read_csv(BASE/"tables/callouts.csv")
    check(len(callouts)==8 and callouts.dataset_id.is_unique and set(callouts.dataset_id)<=set(valid.dataset_id),"Eight callouts connect distinct included datasets")
    selection=json.loads((BASE/"callout_selection.json").read_text())
    evidence=pd.read_csv(BASE/"inputs/callout_experimental_references.csv")
    rendering=json.loads((BASE/"data/tachyon_rendering.json").read_text())
    check(set(callouts.dataset_id)==set(selection["dataset_ids"])==set(evidence.dataset_id),"Curated callouts, source evidence and rendered figure use the same compounds")
    check(evidence.source_url.notna().all() and evidence.relation.eq("experimental_context").all(),"Every experimental-reference record has explicit source context")
    check(not evidence.duplicated(["dataset_id","paper_id"]).any(),"Experimental evidence deduplicated within each compound")
    for row in callouts.itertuples():
        check(evidence.dataset_id.eq(row.dataset_id).sum()==row.experimental_reference_count and pd.notna(row.csd_refcode),row.dataset_id+": experimental crystal references and CSD code documented")
        check(valid.set_index("dataset_id").loc[row.dataset_id,"bond_assignment_status"]=="inferred_from_coordinates",row.dataset_id+": callout has resolved inferred chemical graph")
    for render in rendering["renders"]:
        identifier=render["dataset_id"]
        check(hashlib.sha256((BASE/"molecules"/(identifier+".json")).read_bytes()).hexdigest()==render["molecule_json_sha256"],identifier+": renderer used original full-precision molecular coordinates and bonds")
        check(hashlib.sha256((BASE/"molecules"/(identifier+".sdf")).read_bytes()).hexdigest()==render["sdf_sha256"],identifier+": associated delivered SDF hash verified")
        check(hashlib.sha256((BASE/render["render"]).read_bytes()).hexdigest()==render["render_sha256"],identifier+": ray-traced PNG hash verified")
        check(render["camera_orthogonality_max_error"]<2e-6,identifier+": rigid camera rotation preserves molecular geometry")
        molecule_image=Image.open(BASE/render["render"])
        check(molecule_image.size==(1800,1200) and abs(molecule_image.info["dpi"][0]-600)<.1 and molecule_image.mode=="RGB" and molecule_image.getpixel((0,0))==(255,255,255),identifier+": native 600-dpi ray-traced PNG has clean white background")
        check(hashlib.sha256((BASE/render["scene"]).read_bytes()).hexdigest()==render["scene_sha256"],identifier+": native Tachyon scene hash verified")
        scene=(BASE/render["scene"]).read_text()
        check("AMBIENT_OCCLUSION AMBIENT_COLOR 0.8 0.8 0.8 RESCALE_DIRECT 0.3 SAMPLES 128" in scene and "SPECULAR 0" in scene and "PHONG PLASTIC 0" in scene,identifier+": true ray-traced ambient occlusion and matte materials enabled")
        check(scene.count("SPHERE CENTER ")==render["atom_count"] and scene.count("FCYLINDER BASE ")==2*render["bond_count"],identifier+": native scene retains every atom and two coloured halves per bond")
        frustum=next(line.split()[1:] for line in scene.splitlines() if line.startswith("FRUSTUM "))
        check(float(frustum[0])>float(frustum[1]) and "VIEWDIR 0 0 -1" in scene,identifier+": Tachyon camera convention preserves the original screen handedness")
    check(set(r["dataset_id"] for r in rendering["renders"])==set(callouts.dataset_id),"All eight Tachyon renders are traced to selected callouts")
    p=pd.read_csv(BASE/"tables/provenance.csv")
    check(set(p.dataset_id)==set(data.dataset_id) and p.source_url.notna().all() and p.status.isin(["reported","calculated","inferred","missing"]).all(),"Provenance covers every dataset with sources and explicit statuses")
    pdf=PdfReader(BASE/"output/pdf/cposs_molecular_sketchmap.pdf")
    check(len(pdf.pages)==1,"PDF is one page")
    page=pdf.pages[0]
    check(abs(float(page.mediabox.width)-210/25.4*72)<.01 and abs(float(page.mediabox.height)-297/25.4*72)<.01,"PDF is exactly A4 portrait")
    check(len(page.images)==8,"PDF embeds exactly eight ray-traced molecular callouts; map and colourbar remain vector")
    check(all(im.image.size==(1800,1200) for im in page.images),"PDF preserves the native high-resolution molecular images without downsampling")
    fonts=[]
    for ref in page["/Resources"]["/Font"].values():
        font=ref.get_object();name=str(font["/BaseFont"]);fonts.append(name)
        check("Helvetica" in name,"PDF uses actual Helvetica: "+name)
        for child in font.get("/DescendantFonts",[]):
            descriptor=child.get_object()["/FontDescriptor"].get_object()
            check(any(k in descriptor for k in ["/FontFile","/FontFile2","/FontFile3"]),"PDF embeds font: "+name)
    text=page.extract_text()
    check("Archived structure files" in text and "square root of count" not in text,
          "Count legend retained; marker-area explanation is in the caption")
    check("sketch-map 1" not in text and "sketch-map 2" not in text,
          "Map axis labels are removed and explained in the caption")
    check(all(phrase not in text for phrase in ["The molecular landscape of CPOSS",f"{len(valid)} datasets",f"{int(valid.structure_count.sum()):,}","3 datasets excluded", "One isolated molecular component per dataset", "Source-formula conflicts have dark marker outlines"]),"Requested title, count subtitle and bottom explanatory notes are absent")
    check(figure["font_verification"]["all_figure_text_families"]==["Helvetica"] and not figure["font_verification"]["text_outside_page"],"All figure text resolves to Helvetica and stays on page")
    image=Image.open(BASE/"figures/cposs_molecular_sketchmap.png")
    check(abs(image.width-210/25.4*300)<=1 and abs(image.height-297/25.4*300)<=1 and abs(image.info["dpi"][0]-300)<.1,"PNG is A4 at 300 dpi")
    result={"status":"passed","checks_passed":len(checks),"datasets_attempted":len(data),"datasets_included":len(valid),"excluded":list(data.loc[~data.included,"dataset_id"]),"represented_structure_files":int(valid.structure_count.sum()),"pdf_fonts":fonts,"metrics":measured,"checks":checks}
    write_json(BASE/"verification.json",result)
    print(json.dumps({k:v for k,v in result.items() if k!="checks"},indent=2))


if __name__=="__main__":main()
