"""Thorough unittest suite (standard library only) for slug.slugify.

Tests are derived strictly from the slugify() docstring:

    Lowercase the title; every run of characters other than ASCII a-z and 0-9
    becomes a single "-"; strip leading and trailing "-"; truncate to max_len
    characters, then strip any trailing "-" again. If the result is empty,
    return "untitled".

Default max_len is 40.
"""

import inspect
import unittest

from slug import slugify


class TestNormalCases(unittest.TestCase):
    def test_simple_lowercase_unchanged(self):
        self.assertEqual(slugify("hello"), "hello")

    def test_uppercase_is_lowercased(self):
        self.assertEqual(slugify("Hello World"), "hello-world")

    def test_all_caps(self):
        self.assertEqual(slugify("ABC"), "abc")

    def test_mixed_case_with_digits(self):
        self.assertEqual(slugify("ABC123"), "abc123")

    def test_digits_preserved(self):
        self.assertEqual(slugify("123"), "123")

    def test_digits_with_surrounding_spaces(self):
        self.assertEqual(slugify(" 123 "), "123")

    def test_spaces_become_single_dash(self):
        self.assertEqual(slugify("hello world"), "hello-world")

    def test_punctuation_becomes_dash(self):
        self.assertEqual(slugify("Hello, World!"), "hello-world")

    def test_dots_become_dashes(self):
        self.assertEqual(slugify("a.b.c"), "a-b-c")

    def test_underscore_becomes_dash(self):
        self.assertEqual(slugify("under_score"), "under-score")

    def test_version_string(self):
        self.assertEqual(slugify("Version 2.0"), "version-2-0")

    def test_existing_dashes_preserved_as_single(self):
        self.assertEqual(slugify("hello-world"), "hello-world")

    def test_mixed_case_with_dashes(self):
        self.assertEqual(slugify("Hello---World"), "hello-world")


class TestSeparatorRuns(unittest.TestCase):
    """Every run of non-[a-z0-9] chars becomes exactly one '-'."""

    def test_multiple_spaces_collapse(self):
        self.assertEqual(slugify("a   b"), "a-b")

    def test_tabs_and_newlines_collapse(self):
        self.assertEqual(slugify("a\t\nb"), "a-b")

    def test_mixed_whitespace_collapses(self):
        self.assertEqual(slugify("a \t \n b"), "a-b")

    def test_run_of_dashes_collapses(self):
        self.assertEqual(slugify("a---b"), "a-b")

    def test_run_of_underscores_collapses(self):
        self.assertEqual(slugify("a___b"), "a-b")

    def test_run_of_mixed_punctuation_collapses(self):
        self.assertEqual(slugify("a!@#$%b"), "a-b")

    def test_mixed_separators_collapse(self):
        self.assertEqual(slugify("a - _ b"), "a-b")

    def test_no_double_dashes_from_mixed_runs(self):
        result = slugify("a!!  __  ..b")
        self.assertEqual(result, "a-b")
        self.assertNotIn("--", result)


class TestLeadingTrailingStrip(unittest.TestCase):
    """Leading and trailing '-' characters are stripped."""

    def test_leading_spaces_stripped(self):
        self.assertEqual(slugify("  leading"), "leading")

    def test_trailing_spaces_stripped(self):
        self.assertEqual(slugify("trailing  "), "trailing")

    def test_both_ends_stripped(self):
        self.assertEqual(slugify("  both  "), "both")

    def test_leading_dashes_stripped(self):
        self.assertEqual(slugify("---abc"), "abc")

    def test_trailing_dashes_stripped(self):
        self.assertEqual(slugify("abc---"), "abc")

    def test_both_dash_ends_stripped(self):
        self.assertEqual(slugify("---abc---"), "abc")

    def test_leading_punctuation_stripped(self):
        self.assertEqual(slugify("!!!hello"), "hello")

    def test_trailing_punctuation_stripped(self):
        self.assertEqual(slugify("hello!!!"), "hello")


class TestNonAscii(unittest.TestCase):
    """Only ASCII a-z and 0-9 survive; everything else is a separator."""

    def test_accented_char_becomes_separator(self):
        self.assertEqual(slugify("caf\u00e9"), "caf")

    def test_accented_char_mid_word(self):
        self.assertEqual(slugify("na\u00efve approach"), "na-ve-approach")

    def test_uppercase_non_ascii_lowered_then_separator(self):
        # "\u00c4BC".lower() == "\u00e4bc"; "\u00e4" is not ASCII so -> "-bc" -> "bc"
        self.assertEqual(slugify("\u00c4BC"), "bc")

    def test_all_non_ascii_gives_untitled(self):
        self.assertEqual(slugify("\u00e9\u00e8\u00ea"), "untitled")

    def test_emoji_becomes_separator(self):
        self.assertEqual(slugify("hi\U0001F600there"), "hi-there")


class TestMaxLen(unittest.TestCase):
    def test_default_max_len_is_40(self):
        sig = inspect.signature(slugify)
        self.assertEqual(sig.parameters["max_len"].default, 40)

    def test_long_input_truncated_to_default_40(self):
        self.assertEqual(slugify("a" * 50), "a" * 40)

    def test_exactly_40_chars_unchanged(self):
        self.assertEqual(slugify("a" * 40), "a" * 40)

    def test_39_chars_unchanged(self):
        self.assertEqual(slugify("a" * 39), "a" * 39)

    def test_41_chars_truncated_to_40(self):
        result = slugify("a" * 41)
        self.assertEqual(result, "a" * 40)
        self.assertEqual(len(result), 40)

    def test_custom_max_len(self):
        self.assertEqual(slugify("a" * 50, max_len=10), "a" * 10)

    def test_custom_max_len_longer_than_input(self):
        self.assertEqual(slugify("hello", max_len=100), "hello")

    def test_result_never_exceeds_max_len(self):
        for n in (1, 2, 5, 10, 39, 40, 41, 100):
            with self.subTest(max_len=n):
                result = slugify("hello world, this is a fairly long title!", max_len=n)
                self.assertLessEqual(len(result), n)

    def test_trailing_dash_stripped_after_truncation(self):
        # Pre-truncation slug is "abc-def"; [:4] == "abc-" -> "abc".
        self.assertEqual(slugify("abc def", max_len=4), "abc")

    def test_truncation_at_word_boundary_dash(self):
        # Pre-truncation slug is "a*b39 + '-b'"; first 40 chars end with "-",
        # so the trailing "-" from truncation is stripped.
        self.assertEqual(slugify("a" * 39 + " " + "b"), "a" * 39)
        self.assertEqual(slugify("a" * 39 + " " + "b", max_len=40), "a" * 39)

    def test_truncation_without_trailing_dash_kept_whole(self):
        # Pre-truncation slug is "ab-cd-ef"; [:5] == "ab-cd" (no trailing dash).
        self.assertEqual(slugify("ab cd ef", max_len=5), "ab-cd")

    def test_max_len_one(self):
        self.assertEqual(slugify("hello", max_len=1), "h")

    def test_max_len_zero_gives_untitled(self):
        self.assertEqual(slugify("hello", max_len=0), "untitled")

    def test_max_len_zero_empty_input_gives_untitled(self):
        self.assertEqual(slugify("", max_len=0), "untitled")


class TestUntitled(unittest.TestCase):
    """If the result is empty, return 'untitled'."""

    def test_empty_string(self):
        self.assertEqual(slugify(""), "untitled")

    def test_only_spaces(self):
        self.assertEqual(slugify("   "), "untitled")

    def test_only_dashes(self):
        self.assertEqual(slugify("---"), "untitled")

    def test_only_punctuation(self):
        self.assertEqual(slugify("!!!"), "untitled")

    def test_single_dash(self):
        self.assertEqual(slugify("-"), "untitled")

    def test_mixed_separators_only(self):
        self.assertEqual(slugify(" -_- ! "), "untitled")

    def test_truncation_to_empty_gives_untitled(self):
        self.assertEqual(slugify("hello", max_len=0), "untitled")


class TestErrorCases(unittest.TestCase):
    """The docstring documents no raised errors; invalid types propagate
    the underlying attribute/type errors from the implementation."""

    def test_none_title_raises_attribute_error(self):
        with self.assertRaises(AttributeError):
            slugify(None)

    def test_int_title_raises_attribute_error(self):
        with self.assertRaises(AttributeError):
            slugify(123)

    def test_list_title_raises_attribute_error(self):
        with self.assertRaises(AttributeError):
            slugify(["a"])

    def test_string_max_len_raises_type_error(self):
        with self.assertRaises(TypeError):
            slugify("hello", max_len="5")


if __name__ == "__main__":
    unittest.main()
