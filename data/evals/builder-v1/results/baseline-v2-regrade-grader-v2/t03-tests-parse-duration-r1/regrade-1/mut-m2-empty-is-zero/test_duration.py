"""Unittest suite for duration.parse_duration against its docstring.

Docstring contract under test:
  Parse "1h30m", "45s", "2h5s" and similar into seconds.
  Units are h, m and s; each appears at most once and in that order
  (h before m before s). No whitespace is allowed anywhere.
  Raises ValueError for empty, malformed or out-of-order input.
"""

import unittest

from duration import parse_duration


class TestParseDurationNormal(unittest.TestCase):
    def test_single_units(self):
        self.assertEqual(parse_duration("1h"), 3600)
        self.assertEqual(parse_duration("1m"), 60)
        self.assertEqual(parse_duration("45s"), 45)
        self.assertEqual(parse_duration("2s"), 2)

    def test_docstring_examples(self):
        self.assertEqual(parse_duration("1h30m"), 5400)
        self.assertEqual(parse_duration("45s"), 45)
        self.assertEqual(parse_duration("2h5s"), 7205)

    def test_all_two_unit_combinations(self):
        self.assertEqual(parse_duration("1h1m"), 3660)
        self.assertEqual(parse_duration("1h1s"), 3601)
        self.assertEqual(parse_duration("1m30s"), 90)

    def test_all_three_units(self):
        self.assertEqual(parse_duration("1h1m1s"), 3661)
        self.assertEqual(parse_duration("2h30m15s"), 9015)

    def test_multi_digit_values(self):
        self.assertEqual(parse_duration("10h"), 36000)
        self.assertEqual(parse_duration("123m"), 7380)
        self.assertEqual(parse_duration("100s"), 100)
        self.assertEqual(parse_duration("12h34m56s"), 45296)

    def test_returns_int(self):
        result = parse_duration("1h30m")
        self.assertIsInstance(result, int)


class TestParseDurationBoundaries(unittest.TestCase):
    def test_zero_values(self):
        self.assertEqual(parse_duration("0h"), 0)
        self.assertEqual(parse_duration("0m"), 0)
        self.assertEqual(parse_duration("0s"), 0)

    def test_all_zero_combined(self):
        self.assertEqual(parse_duration("0h0m0s"), 0)
        self.assertEqual(parse_duration("0h0m"), 0)
        self.assertEqual(parse_duration("0m0s"), 0)
        self.assertEqual(parse_duration("0h0s"), 0)

    def test_zero_mixed_with_nonzero(self):
        self.assertEqual(parse_duration("0h30m"), 1800)
        self.assertEqual(parse_duration("1h0m"), 3600)
        self.assertEqual(parse_duration("1h0m1s"), 3601)
        self.assertEqual(parse_duration("0h0m45s"), 45)

    def test_leading_zeros(self):
        self.assertEqual(parse_duration("01h"), 3600)
        self.assertEqual(parse_duration("007s"), 7)
        self.assertEqual(parse_duration("01h02m03s"), 3723)

    def test_large_values(self):
        self.assertEqual(parse_duration("100h"), 360000)
        self.assertEqual(parse_duration("999h59m59s"), 3599999)

    def test_each_unit_at_most_once_boundary(self):
        # Exactly once each, in order, is the maximum allowed presence.
        self.assertEqual(parse_duration("1h2m3s"), 3723)


class TestParseDurationErrors(unittest.TestCase):
    def assertBad(self, text):
        with self.assertRaises(ValueError, msg=f"input {text!r} should raise ValueError"):
            parse_duration(text)

    def test_empty_raises(self):
        self.assertBad("")

    def test_whitespace_anywhere_raises(self):
        for bad in [
            " ",
            "  ",
            "1h ",
            " 1h",
            "1h 30m",
            "1h30m ",
            " 1h30m",
            "1 h",
            "1h\t30m",
            "1h\n",
            "\t1h",
            "1h30m\n",
            "1 h30m",
            "1h 30 m",
        ]:
            with self.subTest(text=bad):
                self.assertBad(bad)

    def test_malformed_raises(self):
        for bad in [
            "h",
            "m",
            "s",
            "hms",
            "1",
            "0",
            "30",
            "1H",
            "1M",
            "1S",
            "1x",
            "1d",
            "abc",
            "1h30",
            "30m1",
            "hour",
            "1.5h",
            "1,5h",
            "-1h",
            "+1h",
            "1 h",
            "--1h",
            "1hm",
            "1ms",
            "1hs",
            "1h-30m",
            "1h+30m",
        ]:
            with self.subTest(text=bad):
                self.assertBad(bad)

    def test_out_of_order_raises(self):
        for bad in [
            "30m1h",
            "10s1h",
            "10s30m",
            "5s30m",
            "1m1h",
            "1s1m",
            "1s1h",
            "1m1h1s",
            "10s1h30m",
            "30s20m10h",
        ]:
            with self.subTest(text=bad):
                self.assertBad(bad)

    def test_duplicate_unit_raises(self):
        for bad in [
            "1h1h",
            "1m1m",
            "1s1s",
            "1h2h3m",
            "1h1m1m",
            "1m2m3s",
            "1h1h1m1s",
            "1h2m3s4s",
            "0h0h",
        ]:
            with self.subTest(text=bad):
                self.assertBad(bad)

    def test_bare_number_with_unit_missing_raises(self):
        for bad in ["0", "10", "1h30m10", "10 20"]:
            with self.subTest(text=bad):
                self.assertBad(bad)

    def test_error_type_is_valueerror(self):
        for bad in ["", "nope", "1m1h", "1h 30m", "1h1h"]:
            with self.subTest(text=bad):
                with self.assertRaises(ValueError):
                    parse_duration(bad)
                # It must be ValueError specifically, not some other exception.
                try:
                    parse_duration(bad)
                except ValueError:
                    pass
                except Exception as exc:  # pragma: no cover
                    self.fail(f"wrong exception type {type(exc)} for {bad!r}")


if __name__ == "__main__":
    unittest.main()
