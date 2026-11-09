"""Golden deployment rows and the size/feature boundary contracts (also pytest-compatible)."""
import tempfile
import unittest

import numpy as np
from sklearn.ensemble import RandomForestClassifier

from harness import window_features
from small_export import check_budget, emit, threshold32
from train_small import FEATURES, REPO
from verify_small_export import compile_library, c_probabilities


class SmallExportTests(unittest.TestCase):
    def test_real_golden_rows_and_nonfinite_rejection(self):
        directory = REPO/'model/small'
        with np.load(directory/'golden.npz', allow_pickle=False) as golden:
            with tempfile.TemporaryDirectory() as temp:
                lib, _ = compile_library(directory, temp)
                for kind in ('rep', 'window'):
                    actual = c_probabilities(lib, 'form_'+kind, golden[kind+'_X'])
                    expected = golden[kind+'_probability']
                    np.testing.assert_allclose(actual, expected, atol=1e-6, rtol=0)
                    np.testing.assert_array_equal(actual >= .5, expected >= .5)
                    for bad in (np.nan, np.inf, -np.inf):
                        row = golden[kind+'_X'][:1].copy(); row[0, -1] = bad
                        self.assertEqual(c_probabilities(lib, 'form_'+kind, row)[0], -1.)

    def test_threshold_grid_preserves_boundary_comparison(self):
        lo = np.float32(1.); hi = np.nextafter(lo, np.float32(np.inf))
        midpoint = (float(lo)+float(hi))/2
        threshold = threshold32(midpoint)
        self.assertEqual(threshold, lo)
        self.assertTrue(lo <= threshold)
        self.assertFalse(hi <= threshold)
        negative = (float(-lo)+float(-hi))/2
        self.assertEqual(threshold32(negative), float(-hi))

    def test_budget_overflow_rejects_even_a_valid_model(self):
        model = RandomForestClassifier(n_estimators=1, max_depth=1, random_state=0).fit([[0.], [1.]], [0, 1])
        sources = {'form_rep': emit(model, 'form_rep', 1)}
        with self.assertRaisesRegex(ValueError, 'budget overflow.*no exports written'):
            check_budget(sources, budget_bytes=1)
        with self.assertRaisesRegex(ValueError, 'budget overflow'):
            check_budget(sources, node_budget=0)

    def test_statistic_major_order(self):
        signal = np.array([[[1., 10., 100.], [3., 14., 106.]]])
        features = window_features(signal)[0]
        self.assertEqual(FEATURES[:6], ['mean_x','mean_y','mean_z','std_x','std_y','std_z'])
        np.testing.assert_array_equal(features[:6], [2., 12., 103., 1., 2., 3.])


if __name__ == '__main__':
    unittest.main()
