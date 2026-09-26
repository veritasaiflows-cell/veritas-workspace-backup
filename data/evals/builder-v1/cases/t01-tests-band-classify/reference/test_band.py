import unittest

from band import classify


class T(unittest.TestCase):
    def test_regions(self):
        self.assertEqual(classify(5, 10, 20), "below")
        self.assertEqual(classify(15, 10, 20), "inside")
        self.assertEqual(classify(25, 10, 20), "above")

    def test_bounds_inclusive(self):
        self.assertEqual(classify(10, 10, 20), "inside")
        self.assertEqual(classify(20, 10, 20), "inside")
        self.assertEqual(classify(10, 10, 10), "inside")

    def test_errors(self):
        with self.assertRaises(ValueError):
            classify(15, 20, 10)
        for args in ((None, 1, 2), (1, None, 2), (1, 0, None)):
            with self.assertRaises(ValueError):
                classify(*args)


if __name__ == "__main__":
    unittest.main()
