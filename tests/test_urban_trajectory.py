import unittest

import numpy as np

from src.urban_trajectory import analyze


class TrajectoryTests(unittest.TestCase):
    def test_reentry_does_not_duplicate_first_conversion(self):
        a = np.array([[[15, 24]], [[24, 24]], [[3, 24]], [[24, 24]]])
        rows, year, origin, domain = analyze(a, np.ones_like(a, dtype=bool), range(1985, 1989), 900)
        self.assertAlmostEqual(sum(r.get("converted_to_urban_ha", 0) for r in rows), 0.18)
        self.assertAlmostEqual(sum(r.get("first_conversion_ha", 0) for r in rows), 0.09)
        self.assertEqual(year.tolist(), [[1986, 0]])
        self.assertEqual(origin.tolist(), [[15, 0]])

    def test_gap_excluded_without_inventing_prior_class(self):
        a = np.array([[[15]], [[27]], [[24]]])
        rows, year, origin, domain = analyze(a, np.ones_like(a, dtype=bool), range(1985, 1988), 900)
        self.assertFalse(domain.any())
        self.assertEqual(rows[-1]["converted_to_urban_ha"], 0)

    def test_missing_year_rejected(self):
        a = np.zeros((2, 1, 1), dtype=np.uint8)
        with self.assertRaises(ValueError):
            analyze(a, np.ones_like(a, dtype=bool), [1985, 1987], 900)
