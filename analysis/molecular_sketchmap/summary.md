# Molecular sketch-map: findings

The figure maps **308 of 311 CPOSS datasets**, accounting for **519,004 archived structure files**. All datasets were attempted. Three source element tables are contradictory and are excluded, covering 163 files; their original coordinates and audit reasons are supplied.

One representative molecule is reconstructed from each selected crystal using periodic symmetry and covalent connectivity. For multicomponent systems the largest non-water component is represented; omitted coformers and counterions remain documented. Eleven reported formulas conflict with the coordinates and are flagged. Three formula-consistent molecular geometries have unresolved bond orders; their SDFs are explicitly connectivity-only.

The genuine scikit-matter sketch-map uses molecular SOAP-feature distances and equal dataset weights. Five initializations and two switching-distance sensitivity checks were performed. The selected map has a pair-distance Spearman correlation of **0.938**, trustworthiness at 10 neighbours of **0.960**, and original-neighbour retention of **0.591**. These support a useful overview while documenting local distortions.

Circle area is proportional to **sqrt(archived file count)**; colour shows extracted-component molar mass. Eight 3D callouts now show curated compounds with explicit experimental crystal references: urea, succinic acid, aspirin, paracetamol, caffeine, carbamazepine, naproxen, chlorothalonil. They use native Tachyon ray tracing with matte, chalky ambient-occlusion shading inspired by VMD. The references establish experimentally characterized compounds; the displayed geometries remain the selected dataset representatives, not asserted experimental conformers. The A4 PDF combines vector map/text with high-resolution molecular renders, and the full-page PNG is 300 dpi. Both use actual Helvetica.

The representation describes composition and local molecular geometry. It does not resolve crystal packing, enantiomers, complete conformational ensembles or full multicomponent chemistry. See `report.md` for methods, all source conflicts and stability limits, and `caption.md` for the standalone figure caption.
