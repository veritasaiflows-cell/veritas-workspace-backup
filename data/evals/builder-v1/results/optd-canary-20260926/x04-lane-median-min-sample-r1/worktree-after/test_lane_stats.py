import unittest

from lane_stats import lane_summary


class Visible(unittest.TestCase):
    def test_odd(self):
        self.assertEqual(lane_summary([5, 1, 3, 2, 4])["median"], 3)


if __name__ == "__main__":
    unittest.main()
