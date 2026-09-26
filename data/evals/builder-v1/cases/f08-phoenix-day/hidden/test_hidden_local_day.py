import unittest

from local_day import day_bounds_ms, phoenix_day

START_25 = 1790319600000  # 2026-09-25 07:00 UTC = 00:00 Phoenix


class Hidden(unittest.TestCase):
    def test_evening_stays_same_day(self):
        self.assertEqual(phoenix_day(START_25 + 23 * 3_600_000), "2026-09-25")  # 23:00 PHX

    def test_boundaries(self):
        self.assertEqual(phoenix_day(START_25 - 1), "2026-09-24")
        self.assertEqual(phoenix_day(START_25), "2026-09-25")

    def test_bounds(self):
        self.assertEqual(day_bounds_ms("2026-09-25"), (START_25, START_25 + 86_400_000))

    def test_bounds_round_trip_winter(self):
        start, end = day_bounds_ms("2026-01-15")
        self.assertEqual(phoenix_day(start), "2026-01-15")
        self.assertEqual(phoenix_day(end - 1), "2026-01-15")
        self.assertEqual(phoenix_day(end), "2026-01-16")
        self.assertEqual(end - start, 86_400_000)


if __name__ == "__main__":
    unittest.main()
