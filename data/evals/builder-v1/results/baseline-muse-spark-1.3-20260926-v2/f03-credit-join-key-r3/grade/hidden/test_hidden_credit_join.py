import json
import unittest

from credit_join import join_runs

T = [{"task_id": "t1", "run_id": "r1"}]


class Hidden(unittest.TestCase):
    def test_reannounced_joins_by_task_run_id(self):
        sub = {"run_id": "announce:requester-settle:9", "payload_json": json.dumps({"taskRunId": "r1"})}
        self.assertEqual(join_runs(T, [sub]), {"t1": sub})

    def test_fallbacks(self):
        for payload in (None, "", "not json", "[1]", json.dumps({"other": 1})):
            sub = {"run_id": "r1", "payload_json": payload}
            self.assertEqual(join_runs(T, [sub]), {"t1": sub}, payload)

    def test_task_run_id_wins_over_run_id(self):
        sub = {"run_id": "r1", "payload_json": json.dumps({"taskRunId": "r9"})}
        self.assertEqual(join_runs(T, [sub]), {"t1": None})

    def test_ambiguous(self):
        a = {"run_id": "r1", "payload_json": None}
        b = {"run_id": "announce:x", "payload_json": json.dumps({"taskRunId": "r1"})}
        self.assertEqual(join_runs(T, [a, b]), {"t1": "AMBIGUOUS"})

    def test_unmatched_and_many(self):
        tasks = [{"task_id": "t1", "run_id": "r1"}, {"task_id": "t2", "run_id": "r2"}]
        sub = {"run_id": "r2", "payload_json": None}
        self.assertEqual(join_runs(tasks, [sub]), {"t1": None, "t2": sub})


if __name__ == "__main__":
    unittest.main()
