"""Checks for formula corruption, counting units, and population leakage."""
from collections import Counter
import json
import unittest

import numpy as np
import pandas as pd

import analyse as analysis


class FormulaTests(unittest.TestCase):
    def test_ambiguous_oxygen_tokens_are_not_large_nitrogen_counts(self):
        for formula in ['C6 H10 N2 02', 'C4 H4 N2 03']:
            with self.assertRaises(ValueError):
                analysis.parse_formula(formula)

    def test_hydrate_stoichiometry_is_not_reduced_to_one_component(self):
        self.assertEqual(analysis.parse_formula('C7 H6 O4 . H2 O1 . H2 O1'),
                         {'C': 7, 'H': 10, 'O': 6})
        self.assertEqual(analysis.parse_formula('2(C7H6O4).H2O'),
                         {'C': 14, 'H': 14, 'O': 9})

    def test_charges_do_not_change_nuclear_counts(self):
        self.assertEqual(analysis.parse_formula('C12 H22 N1 + . Cl1 -'),
                         {'C': 12, 'H': 22, 'N': 1, 'Cl': 1})

    def test_invalid_or_fractional_formulae_fail(self):
        for formula in ['C0H4', '(CH4', 'C2H4)', 'C2H4..H2O', 'C1.5H2']:
            with self.assertRaises(ValueError):
                analysis.parse_formula(formula)


class PopulationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.audit = pd.read_csv(analysis.TABLES / 'cposs_molecular_systems_audit.csv')
        cls.omc = pd.read_csv(analysis.TABLES / 'omc25_train_molecules.csv')
        cls.primary = pd.read_csv(analysis.TABLES / 'cposs_primary_molecules.csv')
        cls.prevalence = pd.read_csv(analysis.TABLES / 'elemental_prevalence.csv')

    def test_cposs_counting_unit_and_exclusion_reconciliation(self):
        self.assertEqual((len(self.audit), len(self.primary)), (234, 189))
        self.assertEqual(self.primary.source_url.nunique(), 189)
        self.assertEqual(int(self.audit.included_multicomponent.sum()), 44)
        self.assertEqual(self.audit.loc[~self.audit.coordinate_validated, 'molecular_system'].tolist(), ['Tetrachlorobenzene'])
        self.assertEqual(int(self.audit.n_failed_search_representatives.sum()), 3)

    def test_conflict_choices_use_all_components(self):
        rows = self.audit.set_index('molecular_system')
        self.assertEqual(rows.loc['QuinoliniumFumarate', 'formula'], 'C13H11NO4')
        self.assertEqual(rows.loc['BTXV', 'formula'], 'C13H15N3O2')
        for name in ['QuinoliniumFumarate', 'BTXV', 'MemantineHydrochloride', 'LY2806920HCl']:
            self.assertTrue(rows.loc[name, 'included_multicomponent'])
            self.assertFalse(rows.loc[name, 'included_primary'])

    def test_omc_records_have_not_been_formula_deduplicated(self):
        self.assertEqual(len(self.omc), 44403)
        self.assertEqual(self.omc.csd_refcode.nunique(), 44403)
        self.assertTrue(self.omc.formula.duplicated().any())
        self.assertEqual(set(self.omc.split), {'train'})

    def test_element_prevalence_is_molecular_presence(self):
        counts = Counter()
        for value in self.primary.composition_json:
            counts.update(json.loads(value).keys())
        table = self.prevalence[self.prevalence.population == 'CPOSS_single_verified']
        for row in table.itertuples():
            self.assertEqual(row.records_with_element, counts[row.element])
            self.assertEqual(row.valid_records, 189)
            self.assertAlmostEqual(row.prevalence_percent, 100 * counts[row.element] / 189, places=8)

    def test_atom_count_and_mass_have_consistent_basis(self):
        weights = json.loads((analysis.INPUTS / 'atomic_weights.json').read_text())['weights_g_mol']
        for frame in [self.primary, self.omc]:
            for row in frame.itertuples():
                counts = json.loads(row.composition_json)
                self.assertEqual(row.atom_count, sum(counts.values()))
                self.assertEqual(row.heavy_atom_count, sum(n for e, n in counts.items() if e != 'H'))
                self.assertAlmostEqual(row.molar_mass_g_mol, sum(weights[e] * n for e, n in counts.items()), places=7)
        self.assertLess(self.omc.reported_minus_common_mass_g_mol.abs().max(), .033)

    def test_exported_ecdfs_end_at_one_and_are_monotonic(self):
        curves = pd.read_csv(analysis.TABLES / 'ecdf_coordinates.csv')
        for _, frame in curves.groupby(['population', 'variable']):
            self.assertTrue((np.diff(frame.x) > 0).all())
            self.assertTrue((np.diff(frame.cumulative_fraction) > 0).all())
            self.assertEqual(frame.cumulative_fraction.iloc[-1], 1)


if __name__ == '__main__':
    unittest.main()
