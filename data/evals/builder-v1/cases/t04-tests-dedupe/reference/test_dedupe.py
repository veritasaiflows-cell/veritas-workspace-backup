import unittest

from dedupe import dedupe_by_key


class T(unittest.TestCase):
    def test_first_kept_in_order(self):
        rows = [{"k": 1, "v": "a"}, {"k": 2, "v": "b"}, {"k": 1, "v": "c"}, {"k": 3, "v": "d"}]
        self.assertEqual([r["v"] for r in dedupe_by_key(rows, "k")], ["a", "b", "d"])

    def test_missing_key_kept(self):
        rows = [{"k": 1}, {"x": 1}, {"x": 1}, {"k": 1}]
        self.assertEqual(dedupe_by_key(rows, "k"), [{"k": 1}, {"x": 1}, {"x": 1}])

    def test_order_not_sorted(self):
        rows = [{"k": 3}, {"k": 1}, {"k": 2}]
        self.assertEqual(dedupe_by_key(rows, "k"), rows)

    def test_input_untouched(self):
        rows = [{"k": 1}, {"k": 1}]
        dedupe_by_key(rows, "k")
        self.assertEqual(rows, [{"k": 1}, {"k": 1}])


if __name__ == "__main__":
    unittest.main()
