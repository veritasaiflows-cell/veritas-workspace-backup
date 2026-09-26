import json
import os
import tempfile
import unittest

from state_io import write_json


class Visible(unittest.TestCase):
    def test_round_trip(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "s.json")
            write_json(p, {"b": 1, "a": [1, 2]})
            with open(p, encoding="utf-8") as fh:
                self.assertEqual(json.load(fh), {"a": [1, 2], "b": 1})


if __name__ == "__main__":
    unittest.main()
