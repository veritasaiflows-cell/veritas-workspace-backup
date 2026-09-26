import unittest

from trigger_eval import parse_exec_result, should_fire


class Hidden(unittest.TestCase):
    def test_plain_json(self):
        self.assertEqual(parse_exec_result({"aggregated": '{"actionable": 0}'}), {"actionable": 0})

    def test_log_lines_before_json(self):
        res = {"aggregated": "starting\nloaded 32 rows\n{\"actionable\": 3}\n"}
        self.assertEqual(should_fire(res), {"fire": True, "reason": "actionable"})

    def test_trailing_blank_lines(self):
        res = {"aggregated": '{"actionable": 0}\n\n  \n'}
        self.assertEqual(should_fire(res), {"fire": False, "reason": "quiet"})

    def test_non_object_is_unreadable(self):
        self.assertIsNone(parse_exec_result({"aggregated": "[1, 2]"}))

    def test_garbage_is_unreadable(self):
        self.assertEqual(should_fire({"aggregated": "Traceback: boom"})["reason"], "unreadable")

    def test_missing_or_empty(self):
        self.assertIsNone(parse_exec_result({}))
        self.assertIsNone(parse_exec_result({"aggregated": ""}))
        self.assertIsNone(parse_exec_result({"aggregated": None}))


if __name__ == "__main__":
    unittest.main()
