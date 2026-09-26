import io
import json
import unittest

from lane_report import main

ROWS = [{"agent": "qa", "tokens": 5}, {"agent": "builder", "tokens": 7},
        {"agent": "scout", "tokens": 5}, {"agent": "qa", "tokens": 2}, {"agent": "docs", "tokens": 1}]


def run(argv):
    buf = io.StringIO()
    code = main(argv, rows=ROWS, out=buf)
    return code, buf.getvalue()


class Hidden(unittest.TestCase):
    def test_json_shape_and_order(self):
        code, text = run(["--json"])
        self.assertEqual(code, 0)
        self.assertTrue(text.endswith("\n"))
        self.assertEqual(text.count("\n"), text.rstrip("\n").count("\n") + 1)
        doc = json.loads(text)
        self.assertEqual(doc, {"lanes": [
            {"agent": "builder", "tokens": 7}, {"agent": "qa", "tokens": 7},
            {"agent": "scout", "tokens": 5}, {"agent": "docs", "tokens": 1}], "total": 20})

    def test_json_min_tokens(self):
        _, text = run(["--json", "--min-tokens", "6"])
        self.assertEqual(json.loads(text), {"lanes": [
            {"agent": "builder", "tokens": 7}, {"agent": "qa", "tokens": 7}], "total": 14})

    def test_text_unchanged(self):
        _, text = run(["--min-tokens", "5"])
        self.assertEqual(text, "builder: 7\nqa: 7\nscout: 5\n")

    def test_json_empty(self):
        buf = io.StringIO()
        main(["--json"], rows=[], out=buf)
        self.assertEqual(json.loads(buf.getvalue()), {"lanes": [], "total": 0})


if __name__ == "__main__":
    unittest.main()
