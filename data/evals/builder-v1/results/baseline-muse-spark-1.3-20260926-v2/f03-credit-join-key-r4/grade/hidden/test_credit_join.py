import unittest

from credit_join import join_runs


class Visible(unittest.TestCase):
    def test_plain_match(self):
        sub = {"run_id": "r1", "payload_json": None}
        self.assertEqual(join_runs([{"task_id": "t1", "run_id": "r1"}], [sub]), {"t1": sub})


if __name__ == "__main__":
    unittest.main()
