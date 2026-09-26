import unittest

from dispatch_hash import matches, task_hash


class Visible(unittest.TestCase):
    def test_identical_text_matches(self):
        self.assertTrue(matches({"sha256": task_hash("run job")}, "run job"))


if __name__ == "__main__":
    unittest.main()
