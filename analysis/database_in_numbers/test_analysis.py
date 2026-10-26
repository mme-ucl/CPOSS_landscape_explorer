"""Meaningful checks for chemical arithmetic, scope, dates and references."""
import json
import io
from pathlib import Path
import tempfile
import unittest
import zipfile

from analyse import (git_sha, parse_formula, paper_key, reference,
                     resolve_publication_crossrefs, scientists, study_year,
                     summarise_json)
from count_structure_archives import inspect_archive
from reconcile_structure_counts import inspect_workbook


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

    def test_separated_numbers_are_not_concatenated_into_atom_counts(self):
        for text in ["C4 H4 N2 03", "C6 H10 N2 02", "C1 H3 2"]:
            self.assertEqual(parse_formula(text)["status"], "missing")
        self.assertEqual(parse_formula("2 (C7 H6 O4) - H2 O1")["atom_count"], 37)

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


class CoordinateCountingRules(unittest.TestCase):
    def test_coordinate_archives_exclude_resource_forks_and_alternate_formats(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "coordinates.zip"
            with zipfile.ZipFile(path, "w") as archive:
                for name in ["model/a.res", "model/b.RES", "model/a.cif", "__MACOSX/model/._a.res", "model/._b.RES", "notes.xlsx"]:
                    archive.writestr(name, "example")
            result = inspect_archive(path)
            self.assertEqual(result["coordinate_files"], 2)
            self.assertEqual(result["primary_format"], ".res")
            self.assertEqual(result["cif_files"], 1)
            self.assertEqual(result["excluded_macos_members"], 2)

    def test_missing_coordinates_are_not_zero(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "empty.zip"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("description.txt", "no coordinates")
            result = inspect_archive(path)
            self.assertIsNone(result["coordinate_files"])
            self.assertEqual(result["status"], "missing")

    def test_workbook_count_uses_actual_rows_and_numeric_energy_cells(self):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as workbook:
            workbook.writestr("xl/workbook.xml", '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="data" sheetId="1" r:id="rId1"/></sheets></workbook>')
            workbook.writestr("xl/_rels/workbook.xml.rels", '<Relationships><Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>')
            workbook.writestr("xl/worksheets/sheet1.xml", '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><dimension ref="A1:C1000000"/><sheetData><row><c r="A1" t="inlineStr"><is><t>Filename</t></is></c><c r="B1" t="inlineStr"><is><t>Lattice Energy 1 /kJmol-1</t></is></c><c r="C1" t="inlineStr"><is><t>Lattice Energy /kJmol-1</t></is></c></row><row><c r="A2" t="inlineStr"><is><t>same</t></is></c><c r="B2"><v>-100</v></c><c r="C2"><v>-50</v></c></row><row><c r="A3" t="inlineStr"><is><t>same</t></is></c><c r="B3"><v>0</v></c></row><row><c r="A4" t="inlineStr"><is><t>missing</t></is></c></row></sheetData></worksheet>')
        summary, identifiers = inspect_workbook(stream.getvalue())
        sheet = summary["sheets"][0]
        self.assertEqual(summary["structure_rows_all_sheets"], 3)
        self.assertEqual(identifiers, {"same", "missing"})
        self.assertEqual(sheet["rows_with_any_numeric_lattice_energy"], 2)
        self.assertEqual(sum(v["records"] for v in sheet["energy_column_numeric_counts"].values()), 3)
        self.assertEqual(sheet["energy_column_numeric_counts"]["Lattice Energy 1 /kJmol-1"]["zero_energy_records"], 1)


if __name__ == "__main__":
    unittest.main()
