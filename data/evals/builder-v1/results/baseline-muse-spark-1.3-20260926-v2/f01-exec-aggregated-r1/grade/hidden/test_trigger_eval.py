import unittest

from trigger_eval import should_fire


class Visible(unittest.TestCase):
    def test_actionable_fires(self):
        res = {"aggregated": '{"actionable": 2}'}
        self.assertEqual(should_fire(res), {"fire": True, "reason": "actionable"})


if __name__ == "__main__":
    unittest.main()
