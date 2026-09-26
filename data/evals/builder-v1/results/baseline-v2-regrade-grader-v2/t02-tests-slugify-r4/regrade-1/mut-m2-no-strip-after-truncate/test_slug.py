"""Tests for slugify() in slug.py, derived strictly from its docstring.

Docstring under test:
    Make a URL slug.

    Lowercase the title; every run of characters other than ASCII a-z and 0-9 becomes a
    single "-"; strip leading and trailing "-"; truncate to max_len characters, then strip
    any trailing "-" again. If the result is empty, return "untitled".
"""

import unittest

from slug import slugify


class TestSlugifyNormalCases(unittest.TestCase):
    def test_lowercases(self):
        self.assertEqual(slugify("Hello World"), "hello-world")

    def test_already_lowercase_unchanged(self):
        self.assertEqual(slugify("hello-world"), "hello-world")

    def test_uppercase_with_digits(self):
        self.assertEqual(slugify("Version 2.0"), "version-2-0")

    def test_digits_preserved(self):
        self.assertEqual(slugify("123"), "123")
        self.assertEqual(slugify("abc123"), "abc123")

    def test_punctuation_becomes_dash(self):
        self.assertEqual(slugify("Hello, World!"), "hello-world")

    def test_underscore_becomes_dash(self):
        self.assertEqual(slugify("a_b"), "a-b")

    def test_slash_colon_become_dashes(self):
        self.assertEqual(slugify("a:b/c"), "a-b-c")

    def test_dot_becomes_dash(self):
        self.assertEqual(slugify("a.b"), "a-b")

    def test_single_letter_words(self):
        self.assertEqual(slugify("a b c"), "a-b-c")

    def test_mixed_separators(self):
        self.assertEqual(slugify("a_b c:d/e.f"), "a-b-c-d-e-f")


class TestSlugifyRunCollapsing(unittest.TestCase):
    def test_multiple_spaces_become_single_dash(self):
        self.assertEqual(slugify("a   b"), "a-b")

    def test_tabs_and_newlines_collapse(self):
        self.assertEqual(slugify("a\tb\nc"), "a-b-c")
        self.assertEqual(slugify("a \t \n b"), "a-b")

    def test_multiple_dashes_collapse(self):
        self.assertEqual(slugify("a---b"), "a-b")

    def test_mixed_run_collapses_to_single_dash(self):
        self.assertEqual(slugify("a --__..  b"), "a-b")

    def test_underscore_runs_collapse(self):
        self.assertEqual(slugify("a___b"), "a-b")

    def test_long_mixed_separator_run(self):
        self.assertEqual(slugify("hello   ___...   world"), "hello-world")


class TestSlugifyStripLeadingTrailing(unittest.TestCase):
    def test_strips_spaces(self):
        self.assertEqual(slugify("  hello  "), "hello")

    def test_strips_dashes(self):
        self.assertEqual(slugify("---hello---"), "hello")

    def test_strips_punctuation_runs(self):
        self.assertEqual(slugify("!!!hello!!!"), "hello")

    def test_strips_mixed_leading_trailing(self):
        self.assertEqual(slugify("  --__ hello world __--  "), "hello-world")

    def test_only_separators_returns_untitled(self):
        self.assertEqual(slugify("---"), "untitled")
        self.assertEqual(slugify("   "), "untitled")
        self.assertEqual(slugify("!!!"), "untitled")
        self.assertEqual(slugify("___"), "untitled")
        self.assertEqual(slugify("\t\n "), "untitled")


class TestSlugifyAsciiOnly(unittest.TestCase):
    def test_non_ascii_becomes_dash(self):
        # "é" is not ASCII a-z, so "Café" -> "caf-" -> stripped -> "caf"
        self.assertEqual(slugify("Café"), "caf")

    def test_accented_run_collapses(self):
        self.assertEqual(slugify("naïve"), "na-ve")

    def test_non_ascii_only_returns_untitled(self):
        self.assertEqual(slugify("é"), "untitled")

    def test_emoji_becomes_dash_and_stripped(self):
        self.assertEqual(slugify("hi 🙂 there"), "hi-there")

    def test_underscore_is_not_word_char_here(self):
        # Unlike \w-based slugifiers, "_" is not in a-z0-9 so it becomes "-"
        self.assertEqual(slugify("foo_bar"), "foo-bar")


class TestSlugifyEmptyUntitled(unittest.TestCase):
    def test_empty_string(self):
        self.assertEqual(slugify(""), "untitled")

    def test_all_separator_inputs(self):
        for title in ["", "---", "   ", "!!!", "___", "-- --", "\t\n"]:
            with self.subTest(title=title):
                self.assertEqual(slugify(title), "untitled")


class TestSlugifyTruncation(unittest.TestCase):
    def test_no_truncation_when_short(self):
        self.assertEqual(slugify("hello", max_len=40), "hello")
        self.assertEqual(slugify("hello", max_len=5), "hello")

    def test_default_max_len_is_40(self):
        title = "a" * 50
        self.assertEqual(slugify(title), "a" * 40)
        # Explicit 40 matches the default.
        self.assertEqual(slugify(title, max_len=40), slugify(title))

    def test_truncation_at_boundary_lengths(self):
        title = "a" * 50
        self.assertEqual(slugify(title, max_len=40), "a" * 40)
        self.assertEqual(slugify(title, max_len=39), "a" * 39)
        self.assertEqual(slugify(title, max_len=41), "a" * 41)

    def test_truncation_preserves_up_to_max_len(self):
        self.assertEqual(slugify("hello-world", max_len=5), "hello")
        self.assertEqual(slugify("hello-world", max_len=11), "hello-world")
        self.assertEqual(slugify("hello-world", max_len=20), "hello-world")

    def test_truncation_strips_trailing_dash_again(self):
        # Full slug is "abcdef-ghij"; [:7] is "abcdef-" so the second
        # strip must remove the trailing dash.
        self.assertEqual(slugify("abcdef ghij", max_len=7), "abcdef")
        self.assertEqual(slugify("abcdef ghij", max_len=6), "abcdef")

    def test_truncation_leading_to_empty_returns_untitled(self):
        self.assertEqual(slugify("hello", max_len=0), "untitled")

    def test_max_len_one(self):
        self.assertEqual(slugify("hello", max_len=1), "h")
        self.assertEqual(slugify("-hello-", max_len=1), "h")

    def test_truncation_after_collapse_and_strip(self):
        # Leading separators are stripped before truncation counts.
        self.assertEqual(slugify("---abcdef ghij", max_len=6), "abcdef")


class TestSlugifyErrors(unittest.TestCase):
    def test_none_title_raises(self):
        with self.assertRaises((AttributeError, TypeError)):
            slugify(None)

    def test_int_title_raises(self):
        with self.assertRaises((AttributeError, TypeError)):
            slugify(123)

    def test_list_title_raises(self):
        with self.assertRaises((AttributeError, TypeError)):
            slugify(["hello"])

    def test_bytes_title_raises(self):
        with self.assertRaises((AttributeError, TypeError)):
            slugify(b"hello")

    def test_non_int_max_len_raises(self):
        with self.assertRaises(TypeError):
            slugify("hello", max_len="5")

    def test_float_max_len_raises(self):
        with self.assertRaises(TypeError):
            slugify("hello", max_len=5.0)


if __name__ == "__main__":
    unittest.main()
