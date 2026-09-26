"""Tests for dedupe.dedupe_by_key against its docstring.

Docstring under test (dedupe.py):
    Remove rows whose value for `key` was already seen.
    Keeps the first occurrence of each value and the original order. Rows that do not
    have `key` at all are always kept. The input list is not modified.
"""

import copy
import unittest

from dedupe import dedupe_by_key


class TestDedupeByKeyNormalCases(unittest.TestCase):
    def test_no_duplicates_returns_equal_rows_in_order(self):
        rows = [{"id": 1}, {"id": 2}, {"id": 3}]
        self.assertEqual(dedupe_by_key(rows, "id"), rows)

    def test_duplicate_key_values_removed(self):
        rows = [{"id": 1}, {"id": 2}, {"id": 1}, {"id": 3}, {"id": 2}]
        self.assertEqual(
            dedupe_by_key(rows, "id"),
            [{"id": 1}, {"id": 2}, {"id": 3}],
        )

    def test_keeps_first_occurrence_full_row(self):
        rows = [
            {"id": 1, "name": "first"},
            {"id": 1, "name": "second"},
            {"id": 2, "name": "other"},
        ]
        result = dedupe_by_key(rows, "id")
        self.assertEqual(
            result,
            [{"id": 1, "name": "first"}, {"id": 2, "name": "other"}],
        )

    def test_original_order_preserved_with_interleaved_duplicates(self):
        rows = [
            {"id": 3},
            {"id": 1},
            {"id": 3},
            {"id": 2},
            {"id": 1},
        ]
        self.assertEqual(
            dedupe_by_key(rows, "id"),
            [{"id": 3}, {"id": 1}, {"id": 2}],
        )

    def test_dedupe_uses_named_key_not_whole_row(self):
        rows = [
            {"id": 1, "v": "a"},
            {"id": 1, "v": "b"},  # same key value -> dropped
            {"id": 2, "v": "a"},  # same 'v', different key -> kept
        ]
        self.assertEqual(
            dedupe_by_key(rows, "id"),
            [{"id": 1, "v": "a"}, {"id": 2, "v": "a"}],
        )

    def test_different_key_argument(self):
        rows = [
            {"id": 1, "name": "x"},
            {"id": 1, "name": "y"},
        ]
        # dedupe on "name": values differ, both kept
        self.assertEqual(dedupe_by_key(rows, "name"), rows)
        # dedupe on "id": second dropped
        self.assertEqual(dedupe_by_key(rows, "id"), [{"id": 1, "name": "x"}])


class TestDedupeByKeyBoundaries(unittest.TestCase):
    def test_empty_input(self):
        self.assertEqual(dedupe_by_key([], "id"), [])

    def test_single_row_with_key(self):
        rows = [{"id": 1}]
        self.assertEqual(dedupe_by_key(rows, "id"), [{"id": 1}])

    def test_single_row_without_key(self):
        rows = [{"other": 1}]
        self.assertEqual(dedupe_by_key(rows, "id"), [{"other": 1}])

    def test_all_duplicates_collapse_to_first(self):
        rows = [{"id": 7}, {"id": 7}, {"id": 7}]
        self.assertEqual(dedupe_by_key(rows, "id"), [{"id": 7}])

    def test_all_rows_missing_key_are_all_kept(self):
        rows = [{"a": 1}, {"b": 2}, {"a": 1, "b": 2}]
        self.assertEqual(dedupe_by_key(rows, "id"), rows)

    def test_rows_missing_key_always_kept_even_repeatedly(self):
        rows = [{}, {}, {"id": 1}, {}, {"id": 1}]
        self.assertEqual(
            dedupe_by_key(rows, "id"),
            [{}, {}, {"id": 1}, {}],
        )

    def test_missing_key_rows_interspersed_preserve_order(self):
        rows = [
            {"id": 1},
            {"nope": True},
            {"id": 2},
            {"nope": True},
            {"id": 1},
        ]
        self.assertEqual(
            dedupe_by_key(rows, "id"),
            [{"id": 1}, {"nope": True}, {"id": 2}, {"nope": True}],
        )

    def test_key_with_none_value_dedupes(self):
        rows = [{"id": None}, {"id": None}, {"id": 1}]
        self.assertEqual(
            dedupe_by_key(rows, "id"),
            [{"id": None}, {"id": 1}],
        )

    def test_none_value_distinct_from_missing_key(self):
        rows = [{"id": None}, {}, {"id": None}, {}]
        self.assertEqual(
            dedupe_by_key(rows, "id"),
            [{"id": None}, {}, {}],
        )

    def test_value_types_compared_by_equality(self):
        rows = [{"id": 1}, {"id": "1"}, {"id": 1}]
        self.assertEqual(
            dedupe_by_key(rows, "id"),
            [{"id": 1}, {"id": "1"}],
        )

    def test_zero_and_false_treated_as_same_seen_value(self):
        # Python set semantics: 0 == False, so the second is "already seen".
        rows = [{"id": 0}, {"id": False}, {"id": 1}]
        self.assertEqual(
            dedupe_by_key(rows, "id"),
            [{"id": 0}, {"id": 1}],
        )

    def test_input_list_not_modified(self):
        rows = [{"id": 1}, {"id": 1}, {"x": 1}]
        snapshot = copy.deepcopy(rows)
        dedupe_by_key(rows, "id")
        self.assertEqual(rows, snapshot)

    def test_input_list_not_modified_empty_and_no_dupes(self):
        rows = []
        dedupe_by_key(rows, "id")
        self.assertEqual(rows, [])
        rows2 = [{"id": 1}, {"id": 2}]
        snapshot2 = copy.deepcopy(rows2)
        dedupe_by_key(rows2, "id")
        self.assertEqual(rows2, snapshot2)

    def test_returns_new_list_object(self):
        rows = [{"id": 1}, {"id": 2}]
        result = dedupe_by_key(rows, "id")
        self.assertEqual(result, rows)
        self.assertIsNot(result, rows)


class TestDedupeByKeyErrors(unittest.TestCase):
    def test_unhashable_key_value_raises_type_error(self):
        rows = [{"id": [1, 2]}, {"id": 1}]
        with self.assertRaises(TypeError):
            dedupe_by_key(rows, "id")

    def test_unhashable_dict_value_raises_type_error(self):
        rows = [{"id": {"nested": 1}}]
        with self.assertRaises(TypeError):
            dedupe_by_key(rows, "id")

    def test_rows_none_raises_type_error(self):
        with self.assertRaises(TypeError):
            dedupe_by_key(None, "id")

    def test_non_mapping_row_raises_type_error(self):
        with self.assertRaises(TypeError):
            dedupe_by_key([42, 42], "id")


if __name__ == "__main__":
    unittest.main()
