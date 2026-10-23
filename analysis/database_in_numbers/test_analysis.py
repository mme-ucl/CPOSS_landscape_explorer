"""Meaningful checks for chemical arithmetic, scope, dates and references."""
import json
import unittest

from analyse import (git_sha, parse_formula, paper_key, reference,
                     resolve_publication_crossrefs, scientists, study_year,
                     summarise_json)


class MetadataRules(unittest.TestCase):
    def test_molecule_atoms_are_not_unit_cell_atoms(self):
        result = parse_formula("C9 H8 O4")
        self.assertEqual(result["atom_count"], 21)
        self.assertEqual(result["heavy_atom_count"], 13)
        self.assertAlmostEqual(result["molar_mass_g_mol"], 180.159, places=3)

    def test_hydrate_formula_unit_keeps_stoichiometry(self):
        result = parse_formula("2(C7 H6 O4) - H2 O1")
        self.assertEqual(result["atom_count"], 37)
        self.assertEqual(result["composition_basis"], "formula unit (multicomponent)")
        self.assertAlmostEqual(result["molar_mass_g_mol"], 326.257, places=3)
        self.assertEqual(parse_formula("C7 H6 O4 - 2(H2 O1)")["atom_count"], 23)

    def test_cocrystal_coefficient_and_ionic_components(self):
        result = parse_formula("2 [ C21 H26 O2 ] - C8 H12 N2")
        self.assertEqual(result["atom_count"], 120)
        self.assertEqual(parse_formula("C4 H10 N1 O1 + . C10 H10 N3 O3 S1 -")["atom_count"], 43)

    def test_ambiguous_formula_remains_missing(self):
        self.assertEqual(parse_formula("C7 H6 O4 - 0.5 H2O")["status"], "missing")
        self.assertEqual(parse_formula("(C7H6O4")["status"], "missing")

    def test_interval_is_not_silently_assigned_a_year(self):
        self.assertEqual(study_year("April 2023"), 2023)
        for value in ["pre-2010", "2005-7", "2005-2008", "2006-10", "2015-2019"]:
            self.assertIsNone(study_year(value))

    def test_distinct_price_scientists_remain_distinct(self):
        self.assertEqual(scientists("Sally Price")[0][0], "Sally Price")
        self.assertEqual(scientists("Louise Price")[0][0], "Louise Price")
        self.assertEqual({n for n, _, _ in scientists("Sharmarke Mohamed (Weijia Zhu, L Price)")}, {"Sharmarke Mohamed", "Weijia Zhu", "Louise Price"})
        self.assertEqual(scientists("Not sure"), [])

    def test_explicit_study_id_reference_resolution(self):
        ref = reference("https://doi.org/10.1234/abc", "A paper (2005)", "A paper", "csp_study")
        a = {"search": "A", "models": [{"study_id": "0"}], "publications": [ref]}
        b = {"search": "B", "models": [{"study_id": "1"}], "publications": [], "publication_raw": "See Study_ID=0"}
        page = {"searches": [a, b]}
        resolve_publication_crossrefs(page)
        self.assertEqual(len(b["publications"]), 1)
        self.assertEqual(b["publications"][0]["association_status"], "inferred")
        self.assertEqual(paper_key(b["publications"][0]), paper_key(ref))

    def test_doi_case_and_wiley_recovery(self):
        ref = reference("https://doi.org/10.1002/1439-7641(20001103)1:3<127::AID-CPHC127", "3.3.CO;2-T>10.1002/1439-7641(20001103)1:3 < 127::AID-CPHC127>3.3.CO;2-T", "", "experimental_context")
        self.assertEqual(ref["doi_status"], "inferred")
        self.assertTrue(paper_key(ref).endswith("3.3.co;2-t"))
        self.assertEqual(paper_key({"url": "http://dx.doi.org/10.1234/ABC"}), paper_key({"url": "https://doi.org/10.1234/abc"}))

    def test_stored_rows_are_not_deduplicated_by_filename(self):
        raw = json.dumps({"structures": [{"size": 84}, {"size": 84}], "properties": {"Filename": {"target": "structure", "values": ["same-label", "same-label"]}}}).encode()
        result = summarise_json(raw, "sample.json", git_sha(raw))
        self.assertEqual(result["structure_count"], 2)
        self.assertEqual(result["unique_filename_count"], 1)
        self.assertEqual(result["duplicate_filename_count"], 1)
        with self.assertRaises(ValueError):
            summarise_json(raw, "sample.json", "wrong-hash")


if __name__ == "__main__":
    unittest.main()
