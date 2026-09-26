import unittest

from report import flag


class Visible(unittest.TestCase):
    def test_ten_is_above_five(self):
        self.assertTrue(flag(10))


if __name__ == "__main__":
    unittest.main()
