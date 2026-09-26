import unittest

from retention import DAY_MS, is_expired


class Visible(unittest.TestCase):
    def test_fresh_row(self):
        self.assertFalse(is_expired(1_000_000, 1_000_000 + DAY_MS))


if __name__ == "__main__":
    unittest.main()
