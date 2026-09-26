import unittest

from wake_gate import decide


class Visible(unittest.TestCase):
    def test_first_run_fires(self):
        fire, _ = decide({}, "a")
        self.assertTrue(fire)


if __name__ == "__main__":
    unittest.main()
