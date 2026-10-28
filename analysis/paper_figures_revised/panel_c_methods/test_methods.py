"""Tests of provenance, stage separation and weighted archive accounting."""
import json
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from classify_methods import classify_refinement, mentioned_searches, trace_search


class ClassificationTests(unittest.TestCase):
    def test_flexible_search_does_not_imply_flexible_refinement(self):
        self.assertEqual(classify_refinement("Flexible CrystalPredictor (2), DMACRYS", "DMA + FIT")[1], "Rigid")
        self.assertEqual(classify_refinement("Rigid CrystalPredictor, CrystalOptimizer, DMACRYS", "DMA + FIT")[1], "Flexible")

    def test_quantum_method_is_not_a_flexibility_flag(self):
        self.assertEqual(classify_refinement("MOLPAK, DMAREL", "GDMA(MP2/6-31G(d,p)) + FIT")[:2], ("DMAREL", "Rigid"))

    def test_explicit_dmaflex_postprocessing_is_flexible(self):
        self.assertEqual(classify_refinement("MOLPAK, DMAflex, DMAREL", "DMA + FIT")[:2], ("DMAREL", "Flexible"))
        self.assertEqual(classify_refinement("Flexible CrystalPredictor, DMACRYS", "CrystalPredictor + DMAflex-Quick + FIT")[1], "Flexible")

    def test_refined_input_geometry_is_not_inherited_as_active_flexibility(self):
        self.assertEqual(classify_refinement("Study_ID=20, DMACRYS", "DMA + FIT")[1], "Rigid")
        self.assertEqual(classify_refinement("Study_ID=12, DMAREL", "DMAflex DMA + FIT")[1], "")

    def test_ambiguous_or_unoptimized_workflows_remain_unresolved(self):
        for programs, potential in [("MOLPAK, DMAREL, DMACRYS", "FIT"),
                                    ("Study_ID=0, unoptimized, DMACRYS", "FIT"),
                                    ("CrystalPredictor, DFTB3-D3, DMACRYS", "DFTB refinement")]:
            self.assertEqual(classify_refinement(programs, potential)[1], "")

    def test_documented_crystaloptimizer_coupling_and_source_typos(self):
        self.assertEqual(classify_refinement("CrystalPredictor CrystalOptimize (2.4.7)", "CrystalOptimizer + FIT")[:2], ("DMACRYS", "Flexible"))
        self.assertEqual(mentioned_searches("Rigid CrystalPrecictor"), {"CrystalPredictor"})

    def test_study_id_resolution_is_same_page_and_cycle_safe(self):
        a = {"page_path": "one.html", "study_id": "1", "programs": "Study_ID=0, DMACRYS", "html_blob_sha": "a"}
        b = {"page_path": "one.html", "study_id": "0", "programs": "MOLPAK, DMAREL", "html_blob_sha": "a"}
        names, chain, status = trace_search(a, {("one.html", "0"): b})
        self.assertEqual(names, {"MOLPAK"})
        self.assertEqual(len(chain), 2)
        self.assertEqual(status, "resolved_Study_ID_reference")
        b["programs"] = "Study_ID=1, DMAREL"
        self.assertEqual(trace_search(a, {("one.html", "0"): b, ("one.html", "1"): a})[2], "cyclic_Study_ID_reference")
        self.assertEqual(trace_search(a, {("other.html", "0"): b})[2], "missing_Study_ID_target")

    def test_published_audit_conserves_all_models_and_repeated_records(self):
        here = Path(__file__).resolve().parent
        frame = pd.read_csv(here / "model_classification.csv")
        summary = json.loads((here / "classification_summary.json").read_text())
        self.assertFalse(frame.duplicated(["dataset_id", "model_id"]).any())
        self.assertEqual((len(frame), frame.dataset_id.nunique()), (508, 310))
        self.assertEqual(frame.archived_structure_model_records.sum(), 517594)
        self.assertEqual(summary["classified_archived_records"] + summary["unresolved_archived_records"], 517594)
        part = frame[frame.dataset_id.eq("TrinitrobenzeneA")]
        self.assertEqual(len(part), 9)
        self.assertEqual(part.archived_structure_model_records.sum(), 1827)
        self.assertTrue(part.refinement_flexibility.eq("Rigid").all())
        matrix = pd.read_csv(here / "matrix_counts.csv")
        np.testing.assert_array_equal(matrix.total_records.to_numpy(),
                                      (matrix.rigid_records + matrix.flexible_records).to_numpy())
        self.assertEqual(matrix.total_records.sum(), frame.loc[frame.included_in_matrix, "archived_structure_model_records"].sum())

    def test_model_pies_use_equal_weights_and_keep_record_weights_separate(self):
        here = Path(__file__).resolve().parent
        frame = pd.read_csv(here / "model_classification.csv")
        counts = pd.read_csv(here / "matrix_counts.csv")
        self.assertTrue(frame.energy_model_weight.eq(1).all())
        self.assertEqual(frame.energy_model_weight.sum(), 508)
        self.assertEqual(frame.matrix_model_weight.sum(), 457)
        self.assertEqual(frame.matrix_record_weight.sum(), 468787)
        self.assertTrue(frame.loc[~frame.included_in_matrix, "matrix_model_weight"].eq(0).all())
        np.testing.assert_array_equal(counts.energy_models.to_numpy(),
                                      (counts.rigid_models + counts.flexible_models).to_numpy())
        for row in counts.itertuples():
            part = frame[frame.included_in_matrix & frame.search_program.eq(row.search_program)
                         & frame.refinement_engine.eq(row.refinement_engine)]
            for treatment in ("rigid", "flexible"):
                self.assertEqual(getattr(row, treatment + "_models"),
                                 part.refinement_flexibility.eq(treatment.title()).sum())
                self.assertEqual(getattr(row, treatment + "_records"),
                                 part[f"matrix_{treatment}_record_weight"].sum())
        cp = counts[counts.search_program.eq("CrystalPredictor") & counts.refinement_engine.eq("DMACRYS")].iloc[0]
        self.assertEqual((cp.flexible_models, cp.energy_models), (157, 287))
        self.assertEqual((cp.flexible_records, cp.total_records), (180405, 419410))
        self.assertNotAlmostEqual(cp.flexible_models / cp.energy_models, cp.flexible_records / cp.total_records)
        tnb = frame[frame.dataset_id.eq("TrinitrobenzeneA")]
        self.assertEqual(tnb.matrix_model_weight.sum(), 9)
        self.assertEqual(tnb.matrix_record_weight.sum(), 1827)


if __name__ == "__main__":
    unittest.main()
