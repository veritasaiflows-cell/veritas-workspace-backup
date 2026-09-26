import unittest

from lane_stats import lane_summary


class Hidden(unittest.TestCase):
    def test_even_median(self):
        self.assertEqual(lane_summary([1, 2, 3, 4, 10, 20])["median"], 3.5)

    def test_p90_nearest_rank(self):
        self.assertEqual(lane_summary(list(range(1, 11)))["p90"], 9)
        self.assertEqual(lane_summary(list(range(1, 12)))["p90"], 10)
        self.assertEqual(lane_summary([7, 1, 3, 5, 9])["p90"], 9)

    def test_min_n(self):
        self.assertEqual(lane_summary([1, 2, 3, 4]), {"n": 4, "median": None, "p90": None})
        self.assertEqual(lane_summary([1, 2], min_n=2)["median"], 1.5)

    def test_none_ignored_and_empty(self):
        self.assertEqual(lane_summary([None, 1, None, 2, 3, 4, 5])["n"], 5)
        self.assertEqual(lane_summary([]), {"n": 0, "median": None, "p90": None})
        self.assertEqual(lane_summary([None, None], min_n=0)["n"], 0)


if __name__ == "__main__":
    unittest.main()
