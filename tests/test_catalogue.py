import importlib.util
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location("catalogue", Path(__file__).resolve().parents[1] / "scripts/update_catalogue.py")
catalogue = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(catalogue)


CASE = """
<h2>Alpha molecule (Blind Test IV)</h2><table>
<tr><td>REFCODE</td><td><table><tr><td>ABCDEF</td></tr><tr><td><a href='Alpha.docx'>Download Word</a></td></tr></table></td></tr>
<tr><td>Common Name</td><td>Alpha molecule</td></tr>
<tr><td>Other Names</td><td>First alias; Second alias</td></tr>
<tr><td>CSD Refcodes</td><td>ABCDEF01, ABCDEF02</td></tr>
<tr><td>Search Identifier</td><td><table><tr><td>A</td></tr><tr><td><a href='https://example.org/?load=https%3A%2F%2Flouiseprice.github.io%2FCPOSS_Database%2F0.Chemiscope%2FAlphaA.json'>Open</a></td></tr></table></td></tr>
<tr><td>Energy model</td><td><table><tr><td>1</td></tr><tr><td><a href='https://louiseprice.github.io/CPOSS_Database/Alpha/model1.zip'>Data</a></td></tr></table></td></tr>
<tr><td>Study_ID</td><td>7</td></tr>
<tr><td>Energy model</td><td>2</td></tr>
<tr><td colspan=2>&nbsp;</tr></td>
<tr><td>Search Identifier</td><td><table><tr><td>B</td></tr><tr><td><a href='https://louiseprice.github.io/CPOSS_Database/0.Chemiscope/AlphaB.json'>Open</a></td></tr></table></td></tr>
<tr><td>Energy model</td><td>1</td></tr>
</table>
"""


class CatalogueTest(unittest.TestCase):
    def test_nested_tables_keep_molecule_search_and_models_separate(self):
        heading, metadata, searches = catalogue.parse_case(CASE)
        self.assertEqual(metadata["refcode"], "ABCDEF")
        self.assertEqual(heading, "Alpha molecule (Blind Test IV)")
        self.assertEqual([s["filenames"] for s in searches], [["AlphaA.json"], ["AlphaB.json"]])
        self.assertEqual([m["id"] for m in searches[0]["models"]], ["1", "2"])
        self.assertEqual(searches[0]["models"][0]["studyId"], "7")
        self.assertEqual([m["id"] for m in searches[1]["models"]], ["1"])

    def test_collection_overlap_comes_from_sections_not_names(self):
        source = """<a name='BlindTest'/><a href='../Alpha/Alpha.html'>Alpha IV</a>
        <a name='CPOSS209'/><a href='../Alpha/Alpha.html'>Alpha</a>
        <a name='unpublished'/><a href='../Absent/Absent.html'>Missing</a>"""
        aliases, membership, broken = catalogue.parse_lists({catalogue.FAMILIES: source}, {"Alpha/Alpha.html"})
        self.assertEqual(membership["Alpha/Alpha.html"], {"BlindTest", "CPOSS209"})
        self.assertIn("Alpha IV", aliases["Alpha/Alpha.html"])
        self.assertEqual(broken[0]["target"], "Absent/Absent.html")

    def test_missing_links_never_create_guessed_page_associations(self):
        tree = {"sha": "test", "tree": [{"type": "blob", "path": p} for p in ["Alpha/Alpha.html", "0.Chemiscope/AlphaA.json", "0.Chemiscope/UnmatchedA.json"]]}
        data, report = catalogue.build_catalogue(tree, {"Alpha/Alpha.html": CASE})
        unmatched = next(x for x in data["datasets"] if x["id"] == "UnmatchedA")
        self.assertEqual(unmatched["cases"], [])
        self.assertEqual(unmatched["label"], "UnmatchedA")
        self.assertEqual(report["unmappedDatasets"], ["UnmatchedA.json"])
        self.assertEqual(report["brokenSourceLinks"][0]["target"], "0.Chemiscope/AlphaB.json")

    def test_truncated_inventory_is_rejected(self):
        with self.assertRaises(ValueError):
            catalogue.build_catalogue({"truncated": True}, {})


if __name__ == "__main__":
    unittest.main()
