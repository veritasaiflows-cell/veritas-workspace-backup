"""Unit tests for duration.parse_duration against its docstring.

Docstring contract:
- Parses "1h30m", "45s", "2h5s" and similar into seconds.
- Units are h, m, s; each appears at most once and in h,m,s order.
- No whitespace allowed anywhere.
- Raises ValueError for empty, malformed, or out-of-order input.
"""

import unittest

from duration import parse_duration


class TestParseDurationNormalCases(unittest.TestCase):
    def test_docstring_examples(self):
        self.assertEqual(parse_duration("1h30m"), 5400)
        self.assertEqual(parse_duration("45s"), 45)
        self.assertEqual(parse_duration("2h5s"), 7205)

    def test_single_units(self):
        self.assertEqual(parse_duration("1h"), 3600)
        self.assertEqual(parse_duration("1m"), 60)
        self.assertEqual(parse_duration("1s"), 1)

    def test_all_units_combined(self):
        self.assertEqual(parse_duration("1h1m1s"), 3661)
        self.assertEqual(parse_duration("2h30m15s"), 2 * 3600 + 30 * 60 + 15)

    def test_each_valid_pair(self):
        self.assertEqual(parse_duration("2h30m"), 2 * 3600 + 30 * 60)
        self.assertEqual(parse_duration("2h5s"), 2 * 3600 + 5)
        self.assertEqual(parse_duration("5m30s"), 5 * 60 + 30)

    def test_zero_values(self):
        self.assertEqual(parse_duration("0h"), 0)
        self.assertEqual(parse_duration("0m"), 0)
        self.assertEqual(parse_duration("0s"), 0)
        self.assertEqual(parse_duration("0h0m0s"), 0)

    def test_leading_zeros(self):
        self.assertEqual(parse_duration("01h"), 3600)
        self.assertEqual(parse_duration("007s"), 7)
        self.assertEqual(parse_duration("00h00m01s"), 1)

    def test_multi_digit_values(self):
        self.assertEqual(parse_duration("10h"), 36000)
        self.assertEqual(parse_duration("100m"), 6000)
        self.assertEqual(parse_duration("123s"), 123)
        self.assertEqual(parse_duration("12h34m56s"), 12 * 3600 + 34 * 60 + 56)

    def test_large_values(self):
        self.assertEqual(parse_duration("100h"), 360000)
        self.assertEqual(parse_duration("999h59m59s"), 999 * 3600 + 59 * 60 + 59)

    def test_returns_int(self):
        result = parse_duration("1h30m")
        self.assertIsInstance(result, int)


class TestParseDurationOrderAndUniqueness(unittest.TestCase):
    def test_valid_orderings(self):
        # Every subset of {h, m, s} in h,m,s order is valid.
        self.assertEqual(parse_duration("1h"), 3600)
        self.assertEqual(parse_duration("1m"), 60)
        self.assertEqual(parse_duration("1s"), 1)
        self.assertEqual(parse_duration("1h1m"), 3660)
        self.assertEqual(parse_duration("1h1s"), 3601)
        self.assertEqual(parse_duration("1m1s"), 61)
        self.assertEqual(parse_duration("1h1m1s"), 3661)

    def test_out_of_order_rejected(self):
        out_of_order = [
            "1m1h",
            "1s1h",
            "1s1m",
            "30m1h",
            "5s2h",
            "10s5m",
            "1m1h1s",
            "1s1m1h",
            "1m1s1h",
        ]
        for text in out_of_order:
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    parse_duration(text)

    def test_duplicate_units_rejected(self):
        duplicates = [
            "1h2h",
            "1m2m",
            "1s2s",
            "1h1h1m",
            "1h1m1m",
            "1h1m1s1s",
            "1h1h1h",
        ]
        for text in duplicates:
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    parse_duration(text)


class TestParseDurationWhitespace(unittest.TestCase):
    def test_any_whitespace_rejected(self):
        bad = [
            " 1h",
            "1h ",
            " 1h ",
            "\t1h",
            "1h\n",
            "1 h",
            "1h 30m",
            "1h30m ",
            "1h 30m 10s",
            "1h\t30m",
        ]
        for text in bad:
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    parse_duration(text)


class TestParseDurationErrors(unittest.TestCase):
    def test_empty_string_rejected(self):
        with self.assertRaises(ValueError):
            parse_duration("")

    def test_none_rejected(self):
        with self.assertRaises(ValueError):
            parse_duration(None)

    def test_bare_and_missing_parts_rejected(self):
        bad = [
            "h",
            "m",
            "s",
            "hms",
            "1",
            "10",
            "1h30",
            "h30m",
            "1hm",
        ]
        for text in bad:
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    parse_duration(text)

    def test_malformed_rejected(self):
        bad = [
            "abc",
            "1x",
            "1H",
            "1M",
            "1S",
            "1hour",
            "1H30M",
            "-1h",
            "+1h",
            "1.5h",
            "1,5h",
            "--1h",
            "1hh",
            "1h-30m",
            "1h+30m",
            "1:30",
            "1h30m10",
            "s1",
            "m1",
            "h1",
        ]
        for text in bad:
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    parse_duration(text)


if __name__ == "__main__":
    unittest.main()
