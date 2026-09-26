import json
import os
import tempfile
import unittest

from state_io import write_json


class Hidden(unittest.TestCase):
    def test_format_identical(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "s.json")
            payload = {"z": "\u00e9", "a": {"k": [1, 2]}}
            write_json(p, payload)
            with open(p, encoding="utf-8") as fh:
                self.assertEqual(fh.read(), json.dumps(payload, indent=2, sort_keys=True))

    def test_failure_keeps_original_and_cleans_up(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "s.json")
            write_json(p, {"good": True})
            with open(p, encoding="utf-8") as fh:
                before = fh.read()
            with self.assertRaises(TypeError):
                write_json(p, {"bad": object()})
            with open(p, encoding="utf-8") as fh:
                self.assertEqual(fh.read(), before)
            self.assertEqual(os.listdir(d), ["s.json"])

    def test_failure_on_new_file_leaves_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(TypeError):
                write_json(os.path.join(d, "new.json"), {"bad": object()})
            self.assertEqual(os.listdir(d), [])

    def test_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "s.json")
            write_json(p, {"v": 1})
            write_json(p, {"v": 2})
            with open(p, encoding="utf-8") as fh:
                self.assertEqual(json.load(fh), {"v": 2})
            self.assertEqual(os.listdir(d), ["s.json"])


if __name__ == "__main__":
    unittest.main()
