import unittest

from local_day import phoenix_day


class Visible(unittest.TestCase):
    def test_midday(self):
        # 2026-09-25 19:00 UTC = 12:00 Phoenix
        self.assertEqual(phoenix_day(1790362800000), "2026-09-25")


if __name__ == "__main__":
    unittest.main()
