#!/usr/bin/env python3
"""Ray-trace curated callouts with the actual open-source PyMOL renderer.

Run with a Python environment containing PyMOL, independently of descriptor
dependencies. Atomic positions and SDF connectivity are never edited.
"""
import hashlib
import json
from pathlib import Path

import pymol2

BASE=Path(__file__).resolve().parent


def main():
    selection=json.loads((BASE/"callout_selection.json").read_text())
    output=BASE/"figures/callouts";output.mkdir(parents=True,exist_ok=True)
    settings={"sphere_scale":.28,"hydrogen_sphere_scale":.23,"stick_radius":.12,"valence":0,"orthoscopic":1,"antialias":2,"ambient":.32,"direct":.68,"specular":.35,"shininess":35,"ray_opaque_background":0,"depth_cue":0,"ray_trace_fog":0,"width":1800,"height":1200,"dpi":600,"view_rotation_degrees":{"x":17,"y":-12},"camera":"PyMOL orient followed by fixed rotations and zoom; no atomic coordinate changes"}
    records=[]
    with pymol2.PyMOL() as instance:
        cmd=instance.cmd
        version=cmd.get_version()
        for identifier in selection["dataset_ids"]:
            source=BASE/"molecules"/(identifier+".sdf")
            molecule=json.loads(source.with_suffix(".json").read_text())
            cmd.reinitialize()
            cmd.load(str(source),"molecule")
            if cmd.count_atoms("molecule")!=molecule["selected_atoms"]:raise AssertionError("PyMOL changed atom count")
            cmd.hide("everything","all");cmd.show("sticks","molecule");cmd.show("spheres","molecule")
            for name,value in settings.items():
                if name not in {"hydrogen_sphere_scale","width","height","dpi","view_rotation_degrees","camera"}:
                    cmd.set(name,value)
            cmd.set("sphere_scale",settings["hydrogen_sphere_scale"],"elem H")
            cmd.color("gray65","elem C");cmd.color("white","elem H")
            cmd.color("blue","elem N");cmd.color("red","elem O")
            cmd.color("green","elem Cl");cmd.color("palegreen","elem F")
            cmd.color("yellow","elem S");cmd.color("salmon","elem Si")
            cmd.color("brown","elem Br");cmd.color("purple","elem I")
            cmd.bg_color("white")
            cmd.viewport(settings["width"],settings["height"])
            cmd.orient("molecule")
            cmd.turn("x",settings["view_rotation_degrees"]["x"])
            cmd.turn("y",settings["view_rotation_degrees"]["y"])
            cmd.zoom("molecule",buffer=.45,complete=1)
            rendered_atoms=cmd.get_model("molecule").atom
            if [a.symbol for a in rendered_atoms]!=molecule["symbols"]:
                raise AssertionError("PyMOL changed element order")
            coordinate_error=max(abs(a.coord[j]-molecule["coordinates_angstrom"][i][j]) for i,a in enumerate(rendered_atoms) for j in range(3))
            if coordinate_error>5.2e-5:
                raise AssertionError("PyMOL changed coordinates beyond SDF rounding")
            target=output/(identifier+".png")
            cmd.png(str(target),width=settings["width"],height=settings["height"],dpi=settings["dpi"],ray=1)
            cmd.save(str(output/(identifier+".pse")))
            records.append({"dataset_id":identifier,"sdf_sha256":hashlib.sha256(source.read_bytes()).hexdigest(),"render_sha256":hashlib.sha256(target.read_bytes()).hexdigest(),"atom_count":molecule["selected_atoms"],"coordinate_max_abs_error_angstrom":coordinate_error,"render":str(target.relative_to(BASE)),"pymol_session":str((output/(identifier+".pse")).relative_to(BASE))})
            print("Ray-traced",identifier,target.stat().st_size,"bytes",flush=True)
    metadata={"renderer":"Actual open-source PyMOL CPU ray tracer","pymol_version":list(version),"settings":settings,"geometry":"Same extracted representatives as the embedding; experimental references identify compounds, not selected predicted crystal packings","renders":records}
    (BASE/"data/pymol_rendering.json").write_text(json.dumps(metadata,indent=2,default=str)+"\n")
    (BASE/"pymol_environment.yml").write_text("name: cposs-pymol\nchannels:\n  - conda-forge\ndependencies:\n  - python=3.12\n  - pymol-open-source="+str(version[0])+"\n")


if __name__=="__main__":main()
