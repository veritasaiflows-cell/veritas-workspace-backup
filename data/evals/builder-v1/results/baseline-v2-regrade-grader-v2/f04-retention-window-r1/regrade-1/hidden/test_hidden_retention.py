import unittest

from retention import DAY_MS, expiring_within, is_expired

H = 3_600_000
E = 1_790_000_000_000


class Hidden(unittest.TestCase):
    def test_boundary_inclusive(self):
        self.assertTrue(is_expired(E, E + 7 * DAY_MS))
        self.assertFalse(is_expired(E, E + 7 * DAY_MS - 1))

    def test_custom_days(self):
        self.assertTrue(is_expired(E, E + 2 * DAY_MS, days=2))

    def test_running(self):
        self.assertFalse(is_expired(None, E + 100 * DAY_MS))

    def test_expiring_within(self):
        now = E + 7 * DAY_MS - 5 * H
        rows = [
            {"id": "late", "ended_at": E + 2 * H},     # expires now+7h: outside
            {"id": "b", "ended_at": E + H},            # expires now+6h... outside 5h window
            {"id": "a", "ended_at": E},                # expires now+5h: inside (inclusive)
            {"id": "c", "ended_at": E - 3 * H},        # expires now+2h: inside
            {"id": "gone", "ended_at": E - 6 * H},     # already expired
            {"id": "run", "ended_at": None},
        ]
        self.assertEqual(expiring_within(rows, now, 5), ["c", "a"])

    def test_expiring_within_empty(self):
        self.assertEqual(expiring_within([], E, 24), [])


if __name__ == "__main__":
    unittest.main()
