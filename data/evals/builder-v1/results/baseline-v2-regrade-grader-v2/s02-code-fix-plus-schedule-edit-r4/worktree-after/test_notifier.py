import unittest

from notifier import truncate_message


class Visible(unittest.TestCase):
    def test_fits(self):
        self.assertEqual(truncate_message("hi", limit=10), "hi")


if __name__ == "__main__":
    unittest.main()
