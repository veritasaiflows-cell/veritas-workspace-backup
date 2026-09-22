"""Authoritative tests for reorder.py. Run with: python -m unittest -v test_reorder"""
import unittest

from reorder import days_of_cover, needs_reorder, reorder_quantity


class TestDaysOfCover(unittest.TestCase):
    def test_normal(self):
        self.assertEqual(days_of_cover(30, 5), 6.0)

    def test_zero_demand_never_runs_out(self):
        self.assertEqual(days_of_cover(30, 0), float("inf"))

    def test_negative_demand_treated_as_no_demand(self):
        self.assertEqual(days_of_cover(30, -2), float("inf"))


class TestReorderQuantity(unittest.TestCase):
    def test_rounds_up_to_whole_packs(self):
        # target = 5 * (4 + 2) = 30; gap = 20; 20/8 = 2.5 packs -> must order 3 packs.
        # Ordering 2 packs (16 units) leaves the gap uncovered.
        self.assertEqual(reorder_quantity(10, 5, 4, 2, 8), 24)

    def test_exact_multiple_does_not_over_order(self):
        # target = 5 * 6 = 30; gap = 6; 6/3 = exactly 2 packs.
        self.assertEqual(reorder_quantity(24, 5, 4, 2, 3), 6)

    def test_sufficient_stock_orders_nothing(self):
        self.assertEqual(reorder_quantity(100, 5, 4, 2, 8), 0)

    def test_gap_smaller_than_one_pack_still_orders_one(self):
        # target = 30; gap = 2; a partial pack cannot be bought, so order one full pack.
        self.assertEqual(reorder_quantity(28, 5, 4, 2, 8), 8)


class TestNeedsReorder(unittest.TestCase):
    def test_below_lead_time_needs_reorder(self):
        self.assertTrue(needs_reorder(10, 5, 4, 2))

    def test_cover_exactly_equals_lead_plus_safety_needs_reorder(self):
        # cover = 30/5 = 6.0 days; lead + safety = 6. At the boundary the buffer is
        # already fully consumed, so this must reorder.
        self.assertTrue(needs_reorder(30, 5, 4, 2))

    def test_safety_stock_is_respected(self):
        # cover = 25/5 = 5.0 days, which clears lead time (4) but not lead + safety (6).
        self.assertTrue(needs_reorder(25, 5, 4, 2))

    def test_comfortable_stock_does_not_reorder(self):
        # cover = 50/5 = 10.0 days > 6.
        self.assertFalse(needs_reorder(50, 5, 4, 2))

    def test_no_demand_never_reorders(self):
        self.assertFalse(needs_reorder(0, 0, 4, 2))


if __name__ == "__main__":
    unittest.main()
