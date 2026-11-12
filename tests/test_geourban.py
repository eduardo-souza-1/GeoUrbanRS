import unittest

import numpy as np

from src.official_tables import numeric
from src.raster_pilot import summarize


class GeoUrbanTests(unittest.TestCase):
    def test_missing_area_is_not_zero(self):
        for x in [None, "nan", "-1"]:
            with self.assertRaises(ValueError):
                numeric(x)
        self.assertEqual(numeric("0"), 0)

    def test_nodata_and_unknown_do_not_become_expansion(self):
        a = np.array([[0, 27, 255, 15]])
        b = np.full_like(a, 24)
        r = summarize(a, b, np.ones_like(a, dtype=bool), 900)
        self.assertAlmostEqual(r["converted_to_urban_ha"], 0.09)
        self.assertEqual(r["excluded_pixels"], 3)

    def test_gross_gain_is_not_net_growth(self):
        a = np.array([[24, 15, 3, 24]])
        b = np.array([[3, 24, 24, 24]])
        r = summarize(a, b, np.ones_like(a, dtype=bool), 900)
        self.assertAlmostEqual(r["converted_to_urban_ha"], 0.18)
        self.assertAlmostEqual(r["urban_to_other_ha"], 0.09)
        self.assertAlmostEqual(r["reconciliation_residual_ha"], 0)
        self.assertEqual(set(r["origin_classes_ha"]), {"15", "3"})

    def test_mask_and_cell_area_are_respected(self):
        a = np.array([[15, 15]])
        b = np.array([[24, 24]])
        r = summarize(a, b, np.array([[True, False]]), 100)
        self.assertEqual(r["converted_to_urban_ha"], 0.01)

    def test_misaligned_arrays_rejected(self):
        with self.assertRaises(ValueError):
            summarize(np.zeros((2, 2)), np.zeros((3, 3)), np.ones((2, 2)), 900)
