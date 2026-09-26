import unittest

from duration import parse_duration


class T(unittest.TestCase):
    def test_values(self):
        self.assertEqual(parse_duration("1h30m"), 5400)
        self.assertEqual(parse_duration("45s"), 45)
        self.assertEqual(parse_duration("2h5s"), 7205)
        self.assertEqual(parse_duration("1h1m1s"), 3661)

    def test_rejects(self):
        for bad in ("", "30m1h", "1h1h", "1h 30m", " 45s", "10", "5x", "h"):
            with self.assertRaises(ValueError, msg=bad):
                parse_duration(bad)


if __name__ == "__main__":
    unittest.main()
