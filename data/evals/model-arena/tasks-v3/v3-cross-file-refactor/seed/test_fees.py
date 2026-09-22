"""Authoritative suite for the basis-point fee API. Correct as written."""
import unittest

import fees
from fees import compute_fee
from checkout import order_total
from invoice_export import render_line


class TestComputeFee(unittest.TestCase):
    def test_basis_points(self):
        self.assertEqual(compute_fee(200.00, 250), 5.00)

    def test_rounds_to_cents(self):
        self.assertEqual(compute_fee(19.99, 325), 0.65)

    def test_zero_rate(self):
        self.assertEqual(compute_fee(100.00, 0), 0.0)

    def test_minimum_floor_applies(self):
        self.assertEqual(compute_fee(4.00, 250, minimum_fee=0.50), 0.50)

    def test_minimum_floor_ignored_when_fee_is_larger(self):
        self.assertEqual(compute_fee(400.00, 250, minimum_fee=0.50), 10.00)

    def test_minimum_defaults_to_zero(self):
        self.assertEqual(compute_fee(4.00, 250), 0.10)


class TestOldApiRemoved(unittest.TestCase):
    def test_calc_fee_is_gone(self):
        self.assertFalse(
            hasattr(fees, "calc_fee"),
            "the old decimal-rate entry point must be renamed, not kept alongside")


class TestOrderTotal(unittest.TestCase):
    def test_total_includes_fee(self):
        self.assertEqual(order_total(200.00, 250), 205.00)

    def test_total_respects_minimum(self):
        self.assertEqual(order_total(4.00, 250, minimum_fee=0.50), 4.50)


class TestRenderLine(unittest.TestCase):
    def test_row_uses_new_fee(self):
        self.assertEqual(render_line("Widget", 200.00, 250),
                         "Widget|200.00|5.00|205.00")

    def test_row_respects_minimum(self):
        self.assertEqual(render_line("Sticker", 4.00, 250, minimum_fee=0.50),
                         "Sticker|4.00|0.50|4.50")


if __name__ == "__main__":
    unittest.main()
