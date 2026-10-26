import unittest
import numpy as np
import pandas as pd
from analyse_density import BASE, EDGES, rebin_reference, balanced_weights


class DensityTests(unittest.TestCase):
    def test_reference_rebin_conserves_count_mass_with_unequal_bins(self):
        frame = pd.DataFrame([{'bin_left_g_cm3': .79, 'bin_right_g_cm3': .83,
                               'bin_width_g_cm3': .04, 'recovered_count_height': 4}])
        np.testing.assert_allclose(rebin_reference(frame, np.array([.8, .82, .84])), [2/3, 1/3])

    def test_reference_histograms_are_recovered_not_raw_crystal_records(self):
        frame = pd.read_csv(BASE / 'inputs/reference_histogram_bars.csv')
        self.assertEqual(frame.groupby('population').size().to_dict(),
                         {'CSD_organic': 220, 'OMC25_generated_first_frames': 87,
                          'OMC25_last_frames': 86, 'OMC25_rigid_press_first_frames': 81})
        self.assertTrue(frame.status.str.contains('not_raw_crystal_data').all())
        self.assertTrue((frame.recovered_count_height > 0).all())

    def test_population_and_duplicate_counting(self):
        frame = pd.read_csv(BASE / 'inputs/cposs_reported_density_records.csv.gz')
        self.assertFalse(frame.duplicated(['dataset_id', 'model_id', 'filename']).any())
        single = frame[(frame.component_basis == 'single_molecule') & frame.coordinate_validated_system]
        self.assertEqual((len(single), single.source_url.nunique(), single.dataset_id.nunique()), (114222, 186, 257))
        w = balanced_weights(single)
        sums = pd.Series(w, index=single.index).groupby(single.source_url).sum()
        np.testing.assert_allclose(sums, np.full(186, 1/186))

    def test_window_normalization_and_excluded_tails_are_explicit(self):
        frame = pd.read_csv(BASE / 'tables/density_histograms_common_bins.csv')
        for _, part in frame.groupby('population'):
            self.assertEqual(len(part), 80)
            self.assertAlmostEqual(part.probability_mass.sum(), 1, places=10)
            self.assertTrue((part.probability_mass >= 0).all())
        coverage = pd.read_csv(BASE / 'tables/cposs_density_window_coverage.csv').iloc[0]
        self.assertEqual(int(coverage.records_all), int(coverage.records_in_window + coverage.below_window_n + coverage.above_window_n))
        self.assertEqual((int(coverage.below_window_n), int(coverage.above_window_n)), (900, 119))

    def test_paper_statistics_do_not_invent_sample_sizes(self):
        stats = pd.read_csv(BASE / 'tables/density_statistics.csv')
        refs = stats[stats.population.str.startswith(('OMC25', 'CSD'))]
        self.assertTrue(refs.n_records.isna().all())
        self.assertTrue(refs.status.str.startswith('approximate').all())
        self.assertTrue(refs.minimum_g_cm3.isna().all())


if __name__ == '__main__':
    unittest.main()
