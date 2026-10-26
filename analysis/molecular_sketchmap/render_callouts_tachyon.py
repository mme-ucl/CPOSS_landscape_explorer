#!/usr/bin/env python3
"""Render VMD-style matte AO ball-and-stick callouts with native Tachyon.

Uses the original extracted coordinates/connectivity and frozen camera rotations.
Only a rigid camera transform is applied; no coordinates or bonds are optimized.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

import numpy as np
from PIL import Image

BASE = Path(__file__).resolve().parent
SOURCE_REVISION = "4e347495c3d996ed5f68d96a424d481d030843da"
ELEMENTS = {
    "H": ((.94, .94, .94), 1.20),
    "C": ((.58, .58, .58), 1.70),
    "N": ((.18, .28, .85), 1.55),
    "O": ((.86, .14, .12), 1.52),
    "Cl": ((.16, .72, .22), 1.75),
}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def vector(values):
    return " ".join(f"{v:.10f}" for v in values)


def scene_text(record, view, width, height, samples, antialias):
    positions = np.asarray(record["coordinates_angstrom"], dtype=float)
    rotation = np.asarray(view[:9]).reshape(3, 3)
    if not np.allclose(rotation.T @ rotation, np.eye(3), atol=2e-6) or np.linalg.det(rotation) < .99999:
        raise ValueError("Camera must preserve geometry and handedness")
    projected = (positions - np.asarray(view[12:15])) @ rotation
    symbols = record["symbols"]
    radii = np.asarray([ELEMENTS[s][1] * (.23 if s == "H" else .28) for s in symbols])
    low = (projected[:, :2] - radii[:, None]).min(axis=0)
    high = (projected[:, :2] + radii[:, None]).max(axis=0)
    middle = (low + high) / 2
    half_y = max((high[1] - low[1]) / 2, (high[0] - low[0]) / 2 * height / width) * 1.16
    half_x = half_y * width / height
    lines = [
        "BEGIN_SCENE", f"RESOLUTION {width} {height}",
        "CAMERA", "PROJECTION ORTHOGRAPHIC", "ZOOM 1", "ASPECTRATIO 1",
        f"ANTIALIASING {antialias}", "RAYDEPTH 8",
        f"CENTER {middle[0]:.10f} {middle[1]:.10f} 50",
        "VIEWDIR 0 0 -1", "UPDIR 0 1 0",
        # Tachyon defines image-right as up x view, a left-handed camera.
        # Reverse its horizontal frustum to match the original PyMOL view,
        # without reflecting any nuclear coordinates or changing stereochemistry.
        f"FRUSTUM {half_x:.10f} {-half_x:.10f} {-half_y:.10f} {half_y:.10f}",
        "END_CAMERA", "BACKGROUND 1 1 1",
        # Lights must precede RESCALE_DIRECT, matching VMD's Tachyon export.
        "DIRECTIONAL_LIGHT DIRECTION 0.2 -0.4 -1 COLOR 1 1 1",
        "SHADER_MODE FULL",
        f"AMBIENT_OCCLUSION AMBIENT_COLOR 0.8 0.8 0.8 RESCALE_DIRECT 0.3 SAMPLES {samples}",
        "END_SHADER_MODE",
    ]
    for symbol in sorted(set(symbols)):
        lines.extend([
            f"TEXDEF element_{symbol}",
            "AMBIENT 0 DIFFUSE 1 SPECULAR 0 OPACITY 1",
            "PHONG PLASTIC 0 PHONG_SIZE 1",
            "COLOR " + vector(ELEMENTS[symbol][0]), "TEXFUNC 0",
        ])
    for i, j, _ in record["bonds"]:
        midpoint = (projected[i] + projected[j]) / 2
        for atom in (i, j):
            lines.append(f"FCYLINDER BASE {vector(projected[atom])} APEX {vector(midpoint)} RAD 0.12 element_{symbols[atom]}")
    for position, radius, symbol in zip(projected, radii, symbols):
        lines.append(f"SPHERE CENTER {vector(position)} RAD {radius:.8f} element_{symbol}")
    lines.append("END_SCENE")
    return "\n".join(lines) + "\n", rotation


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tachyon", type=Path, default=Path(os.environ.get("TACHYON_BIN", shutil.which("tachyon") or "/tmp/cposs-tachyon-runtime/Tachyon/compile/macosx-thr/tachyon")))
    parser.add_argument("--dataset", nargs="*")
    parser.add_argument("--width", type=int, default=1800)
    parser.add_argument("--height", type=int, default=1200)
    parser.add_argument("--ao-samples", type=int, default=128)
    parser.add_argument("--antialias", type=int, default=3)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--output-dir", type=Path, default=BASE / "figures/callouts_ao")
    args = parser.parse_args()
    if not args.tachyon.is_file():
        raise FileNotFoundError("Supply --tachyon /path/to/tachyon; see tachyon_build.md")
    selection = json.loads((BASE / "callout_selection.json").read_text())
    views = {r["dataset_id"]: r for r in json.loads((BASE / "inputs/callout_views.json").read_text())["views"]}
    identifiers = args.dataset or selection["dataset_ids"]
    if not set(identifiers) <= set(selection["dataset_ids"]):
        raise ValueError("Only the documented curated callouts may be rendered")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    records = []
    for identifier in identifiers:
        source = BASE / "molecules" / (identifier + ".json")
        molecule = json.loads(source.read_text())
        scene, rotation = scene_text(molecule, views[identifier]["pymol_view"], args.width, args.height, args.ao_samples, args.antialias)
        dat = args.output_dir / (identifier + ".dat")
        dat.write_text(scene)
        with tempfile.TemporaryDirectory(prefix="cposs-ao-") as temporary:
            raw = Path(temporary) / "render.tga"
            result = subprocess.run([str(args.tachyon), str(dat), "-format", "TARGA", "-o", str(raw), "-numthreads", str(args.threads)], capture_output=True, text=True)
            if result.returncode or not raw.exists():
                raise RuntimeError(result.stdout + result.stderr)
            target = args.output_dir / (identifier + ".png")
            Image.open(raw).convert("RGB").save(target, dpi=(600, 600))
            (args.output_dir / (identifier + ".log")).write_text(result.stdout + result.stderr)
        records.append({
            "dataset_id": identifier, "molecule_json_sha256": sha256(source),
            "sdf_sha256": sha256(source.with_suffix(".sdf")),
            "render_sha256": sha256(target), "scene_sha256": sha256(dat),
            "atom_count": molecule["selected_atoms"], "bond_count": len(molecule["bonds"]),
            "camera_orthogonality_max_error": float(np.max(np.abs(rotation.T @ rotation - np.eye(3)))),
            "render": str(target.relative_to(BASE)) if target.is_relative_to(BASE) else str(target),
            "scene": str(dat.relative_to(BASE)) if dat.is_relative_to(BASE) else str(dat),
        })
        print("Ambient-occlusion render:", identifier, target.stat().st_size, "bytes", flush=True)
    metadata = {
        "renderer": "Tachyon 0.99b6 CPU ray tracer (the renderer used by VMD)",
        "source_repository": "https://github.com/thesketh/Tachyon",
        "source_revision": SOURCE_REVISION, "executable_sha256": sha256(args.tachyon),
        "style": "VMD-inspired matte/chalky ball-and-stick with true ray-traced ambient occlusion",
        "settings": {"ao_ambient": .8, "ao_direct": .3, "ao_samples": args.ao_samples,
                     "material_ambient": 0, "material_diffuse": 1, "material_specular": 0,
                     "phong": 0, "sphere_scale": .28, "hydrogen_sphere_scale": .23,
                     "stick_radius_angstrom": .12, "antialias_samples": args.antialias,
                     "width": args.width, "height": args.height, "dpi": 600,
                     "background": "opaque white", "projection": "orthographic",
                     "camera_handedness": "Tachyon horizontal frustum reversed to preserve PyMOL screen handedness; proper rotation only on nuclear coordinates",
                     "element_colours_and_vdw_radii": ELEMENTS},
        "geometry": "Original extracted nuclear coordinates/connectivity; rigid frozen camera rotation only; no optimization, atom additions or substitutions",
        "camera_source": "inputs/callout_views.json", "renders": records,
    }
    complete = set(identifiers) == set(selection["dataset_ids"]) and args.output_dir == BASE / "figures/callouts_ao"
    output = BASE / "data/tachyon_rendering.json" if complete else args.output_dir / "rendering.json"
    output.write_text(json.dumps(metadata, indent=2) + "\n")


if __name__ == "__main__":
    main()
