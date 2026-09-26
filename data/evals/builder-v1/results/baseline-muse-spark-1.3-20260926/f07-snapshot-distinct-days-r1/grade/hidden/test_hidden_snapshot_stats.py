import json
import os
import tempfile
import unittest

from snapshot_stats import coverage


def write(d, name, payload):
    with open(os.path.join(d, name), "w", encoding="utf-8") as fh:
        fh.write(payload if isinstance(payload, str) else json.dumps(payload))


class Hidden(unittest.TestCase):
    def test_duplicates_and_invalid(self):
        with tempfile.TemporaryDirectory() as d:
            write(d, "a.json", {"data_date": "2026-09-21"})
            write(d, "b.json", {"data_date": "2026-09-21"})
            write(d, "c.json", {"data_date": "2026-09-22"})
            write(d, "bad.json", "{not json")
            write(d, "list.json", [1])
            write(d, "nodate.json", {"x": 1})
            write(d, "notes.txt", "ignored")
            out = coverage(d)
            self.assertEqual((out["snapshots"], out["days"]), (6, 2))
            self.assertEqual(out["gaps"], [])

    def test_weekday_gaps(self):
        with tempfile.TemporaryDirectory() as d:
            write(d, "a.json", {"data_date": "2026-09-17"})  # Thursday
            write(d, "b.json", {"data_date": "2026-09-24"})  # next Thursday
            write(d, "c.json", {"data_date": "2026-09-22"})  # Tuesday
            out = coverage(d)
            self.assertEqual(out["gaps"], ["2026-09-18", "2026-09-21", "2026-09-23"])
            self.assertEqual(out["days"], 3)

    def test_empty(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(coverage(d), {"snapshots": 0, "days": 0, "gaps": []})


if __name__ == "__main__":
    unittest.main()
