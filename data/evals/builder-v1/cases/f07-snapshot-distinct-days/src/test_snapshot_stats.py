import json
import os
import tempfile
import unittest

from snapshot_stats import coverage


class Visible(unittest.TestCase):
    def test_one_file(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "a.json"), "w") as fh:
                json.dump({"data_date": "2026-09-21"}, fh)
            self.assertEqual(coverage(d)["snapshots"], 1)


if __name__ == "__main__":
    unittest.main()
