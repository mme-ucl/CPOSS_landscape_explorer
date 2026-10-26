# Ambient-occlusion molecular callouts

The current figure uses the standalone **Tachyon 0.99b6** CPU ray tracer, by John E. Stone, which is also the rendering engine used by VMD. The matte material and diffuse illumination follow the appearance described in the [VMD ambient-occlusion tutorial](https://www.ks.uiuc.edu/Research/vmd/minitutorials/tachyonao/). VMD itself is not required or installed.

The renderer uses native spheres and finite cylinders with true ray-traced ambient occlusion. Settings are AO ambient 0.8, AO direct 0.3, 128 occlusion samples, three additional antialias samples, diffuse coefficient 1, specular/Phong coefficients 0, and an orthographic camera. Colour is assigned by element, with slightly muted red/blue/green for a matte finish. Geometry is the original full-precision extracted JSON coordinates and connectivity. Frozen rotations from the previously approved PyMOL views are in `inputs/callout_views.json`; only a rigid camera transform is applied. Tachyon uses a left-handed image-right convention; reversed horizontal frustum extents preserve the original view without reflecting any nuclear coordinates or molecular stereochemistry. Atom sizes and stick radii retain the preceding figure's values.

The output is 1800 x 1200 RGB pixels on white with 600 dpi metadata. There is no background-removal step or image synthesis. PNG compression simply converts Tachyon's lossless TGA output. The main PDF embeds these pixels without downsampling.

## Reproduce

An existing `tachyon` executable can be supplied through `--tachyon` or `TACHYON_BIN`. The source revision used here is `4e347495c3d996ed5f68d96a424d481d030843da` from the public [Tachyon source mirror](https://github.com/thesketh/Tachyon). On this macOS arm64 machine it built using the existing native target:

```sh
git clone https://github.com/thesketh/Tachyon.git /tmp/cposs-tachyon-source
git -C /tmp/cposs-tachyon-source checkout 4e347495c3d996ed5f68d96a424d481d030843da
make -C /tmp/cposs-tachyon-source/unix macosx-thr -j4

# Use the project's analysis Python environment (NumPy and Pillow required).
python render_callouts_tachyon.py --tachyon /tmp/cposs-tachyon-source/compile/macosx-thr/tachyon
python plot.py
python analyse_results.py
python verify_outputs.py
```

On Linux select the appropriate `linux-thr` or `linux-64-thr` build target, or install the distribution's Tachyon package. The executable hash, source revision, material settings and per-molecule source/scene/image hashes are in `data/tachyon_rendering.json`. Native `.dat` scenes and render logs are delivered beside each PNG in `figures/callouts_ao/`. Monte Carlo sampling can produce small pixel differences with different renderer builds or thread configurations.

The earlier PyMOL renderer, PNGs, sessions and environment specification remain available as provenance of the approved molecular views. They are separate from the current matte renders.
