"""Tests for crystallographic reconstruction and the scientific distance model."""
import unittest
import numpy as np
from ase import Atoms
from scipy.spatial.distance import pdist
from extract_molecules import affine, formula_counter, formula_multiple, molecular_components, parse_res, title_energy
from embed import sigmoid


class CrystalReconstruction(unittest.TestCase):
    def test_affine_fraction_and_mixed_axes(self):
        r,t=affine("Y-X, -X, Z+1/6")
        np.testing.assert_allclose(r@np.array([.2,.3,.4])+t,[.1,-.2,.4+1/6])

    def test_inversion_completes_special_position_molecule(self):
        crystal,info=parse_res("TITL half molecule\nCELL 1 10 10 10 90 90 90\nLATT 1\nSFAC C\nC1 1 .075 0 0\nEND")
        parts=molecular_components(crystal)
        self.assertEqual(info["asymmetric_unit_atoms"],1)
        self.assertEqual(len(parts),1)
        self.assertEqual(parts[0].get_chemical_formula(),"C2")
        self.assertAlmostEqual(float(pdist(parts[0].positions)[0]),1.5)

    def test_wrapped_atoms_form_one_finite_component(self):
        crystal=Atoms("CO",scaled_positions=[[.97,.5,.5],[.11,.5,.5]],cell=[10,10,10],pbc=True)
        parts=molecular_components(crystal)
        self.assertEqual(len(parts),1)
        self.assertAlmostEqual(float(pdist(parts[0].positions)[0]),1.4)

    def test_periodic_polymer_is_not_exported_as_molecule(self):
        crystal=Atoms("C",positions=[[0,0,0]],cell=[1.4,10,10],pbc=True)
        with self.assertRaisesRegex(ValueError,"Periodic covalent network"):
            molecular_components(crystal)

    def test_lattice_centring_generates_distinct_sites(self):
        crystal,_=parse_res("CELL 1 10 10 10 90 90 90\nLATT -4\nSFAC C\nC1 1 .1 .2 .3\nEND")
        self.assertEqual(len(crystal),4)

    def test_unit_composition_instruction_is_not_an_atom(self):
        crystal,_=parse_res("CELL 1 10 10 10 90 90 90\nLATT -1\nSFAC C H N O\nUNIT 32 36 4 8\nC1 1 .1 .2 .3\nEND")
        self.assertEqual(len(crystal),1)

    def test_missing_sfac_element_is_not_guessed(self):
        with self.assertRaisesRegex(ValueError,"SFAC index"):
            parse_res("CELL 1 10 10 10 90 90 90\nLATT -1\nSFAC N O C H\nH1 5 .1 .2 .3\nEND")


class ChemicalDistances(unittest.TestCase):
    def test_formula_comparison_keeps_cell_and_molecule_separate(self):
        self.assertEqual(formula_multiple(formula_counter("C4H16N8O4"),formula_counter("CH4N2O")),4)
        self.assertIsNone(formula_multiple(formula_counter("C10H8"),formula_counter("C8H10")))

    def test_title_energy_does_not_extract_unrelated_numbers(self):
        self.assertEqual(title_energy("TITL a100(-123.45) P21/c"),-123.45)
        self.assertIsNone(title_energy("TITL a100 P21/c"))

    def test_sketchmap_switch_and_saturation(self):
        sigma=.4
        self.assertEqual(float(sigmoid(0,sigma)),0)
        self.assertAlmostEqual(float(sigmoid(sigma,sigma)),.5)
        self.assertGreater(float(sigmoid(100,sigma)),.999)


if __name__=="__main__":unittest.main()
