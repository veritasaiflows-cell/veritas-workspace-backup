import unittest

from fetch_retry import fetch_with_retry


class Visible(unittest.TestCase):
    def test_success(self):
        self.assertEqual(fetch_with_retry(lambda: 42, sleep=lambda s: None), 42)


if __name__ == "__main__":
    unittest.main()
