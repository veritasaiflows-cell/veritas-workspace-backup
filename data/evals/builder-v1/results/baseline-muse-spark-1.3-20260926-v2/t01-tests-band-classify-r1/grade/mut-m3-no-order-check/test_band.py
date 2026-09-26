"""Unit tests for band.classify against its docstring.

Docstring contract:
- "below" if price < low
- "above" if price > high
- else "inside"
- low and high are inclusive bounds (price equal to low or high is "inside")
- Raises ValueError if low > high or if any argument is None.
"""

import unittest

from band import classify


class TestClassifyNormalCases(unittest.TestCase):
    def test_clearly_below(self):
        self.assertEqual(classify(5, 10, 20), "below")

    def test_clearly_above(self):
        self.assertEqual(classify(25, 10, 20), "above")

    def test_clearly_inside(self):
        self.assertEqual(classify(15, 10, 20), "inside")

    def test_inside_midpoint(self):
        self.assertEqual(classify(0, -10, 10), "inside")

    def test_float_inside(self):
        self.assertEqual(classify(10.5, 10.0, 20.0), "inside")

    def test_float_below(self):
        self.assertEqual(classify(9.9, 10.0, 20.0), "below")

    def test_float_above(self):
        self.assertEqual(classify(20.1, 10.0, 20.0), "above")

    def test_negative_range_inside(self):
        self.assertEqual(classify(-15, -20, -10), "inside")

    def test_negative_range_below(self):
        self.assertEqual(classify(-25, -20, -10), "below")

    def test_negative_range_above(self):
        self.assertEqual(classify(-5, -20, -10), "above")


class TestClassifyBoundaries(unittest.TestCase):
    def test_price_equal_low_is_inside(self):
        self.assertEqual(classify(10, 10, 20), "inside")

    def test_price_equal_high_is_inside(self):
        self.assertEqual(classify(20, 10, 20), "inside")

    def test_zero_width_interval_equal_is_inside(self):
        self.assertEqual(classify(10, 10, 10), "inside")

    def test_zero_width_interval_below(self):
        self.assertEqual(classify(9, 10, 10), "below")

    def test_zero_width_interval_above(self):
        self.assertEqual(classify(11, 10, 10), "above")

    def test_just_below_low(self):
        self.assertEqual(classify(9, 10, 20), "below")

    def test_just_above_high(self):
        self.assertEqual(classify(21, 10, 20), "above")

    def test_low_equals_high_float(self):
        self.assertEqual(classify(1.5, 1.5, 1.5), "inside")

    def test_zero_bounds(self):
        self.assertEqual(classify(0, 0, 0), "inside")
        self.assertEqual(classify(-1, 0, 0), "below")
        self.assertEqual(classify(1, 0, 0), "above")

    def test_return_values_are_exact_strings(self):
        self.assertIsInstance(classify(5, 10, 20), str)
        self.assertIsInstance(classify(25, 10, 20), str)
        self.assertIsInstance(classify(15, 10, 20), str)


class TestClassifyErrors(unittest.TestCase):
    def test_low_greater_than_high(self):
        with self.assertRaises(ValueError):
            classify(15, 20, 10)

    def test_low_greater_than_high_price_outside(self):
        with self.assertRaises(ValueError):
            classify(5, 20, 10)

    def test_low_greater_than_high_by_one(self):
        with self.assertRaises(ValueError):
            classify(10, 11, 10)

    def test_price_none(self):
        with self.assertRaises(ValueError):
            classify(None, 10, 20)

    def test_low_none(self):
        with self.assertRaises(ValueError):
            classify(15, None, 20)

    def test_high_none(self):
        with self.assertRaises(ValueError):
            classify(15, 10, None)

    def test_all_none(self):
        with self.assertRaises(ValueError):
            classify(None, None, None)

    def test_none_with_inverted_bounds_still_value_error(self):
        # Docstring requires ValueError for either condition; both hold here.
        with self.assertRaises(ValueError):
            classify(None, 20, 10)


if __name__ == "__main__":
    unittest.main()
