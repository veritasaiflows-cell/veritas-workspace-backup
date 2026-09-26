import unittest

from notifier import truncate_message


class Hidden(unittest.TestCase):
    def test_exact_length(self):
        out = truncate_message("x" * 50, limit=10)
        self.assertEqual(len(out), 10)
        self.assertEqual(out, "x" * 9 + "\u2026")

    def test_fits_exactly(self):
        self.assertEqual(truncate_message("x" * 10, limit=10), "x" * 10)

    def test_default_limit(self):
        self.assertEqual(len(truncate_message("y" * 5000)), 4096)


if __name__ == "__main__":
    unittest.main()
