import unittest

from amounts import format_amount


class Visible(unittest.TestCase):
    def test_current(self):
        self.assertEqual(format_amount(1250), "$12.50")


if __name__ == "__main__":
    unittest.main()
