"""Tests for slug.slugify against its docstring (unittest, stdlib only)."""
import unittest

from slug import slugify


class TestSlugifyNormalCases(unittest.TestCase):
    def test_lowercase_passthrough(self):
        self.assertEqual(slugify("hello"), "hello")

    def test_uppercased_is_lowered(self):
        self.assertEqual(slugify("Hello World"), "hello-world")

    def test_all_caps(self):
        self.assertEqual(slugify("HELLO WORLD"), "hello-world")

    def test_digits_preserved(self):
        self.assertEqual(slugify("Version 2 Release"), "version-2-release")

    def test_digits_only(self):
        self.assertEqual(slugify("123"), "123")

    def test_single_space_becomes_dash(self):
        self.assertEqual(slugify("hello world"), "hello-world")

    def test_run_of_spaces_collapses(self):
        self.assertEqual(slugify("hello   world"), "hello-world")

    def test_tabs_and_newlines_collapse(self):
        self.assertEqual(slugify("hello\nworld"), "hello-world")
        self.assertEqual(slugify("hello\tworld"), "hello-world")
        self.assertEqual(slugify("hello \t\n world"), "hello-world")

    def test_punctuation_run_collapses(self):
        self.assertEqual(slugify("hello, world!"), "hello-world")

    def test_mixed_separator_run_collapses(self):
        self.assertEqual(slugify("a!@#b"), "a-b")
        self.assertEqual(slugify("a   ---___...   b"), "a-b")

    def test_underscores_become_dash(self):
        self.assertEqual(slugify("hello___world"), "hello-world")

    def test_existing_slug_unchanged(self):
        self.assertEqual(slugify("hello-world"), "hello-world")

    def test_leading_separators_stripped(self):
        self.assertEqual(slugify("   hello"), "hello")
        self.assertEqual(slugify("---hello"), "hello")

    def test_trailing_separators_stripped(self):
        self.assertEqual(slugify("hello   "), "hello")
        self.assertEqual(slugify("hello---"), "hello")

    def test_leading_and_trailing_stripped(self):
        self.assertEqual(slugify("  hello world  "), "hello-world")
        self.assertEqual(slugify("---hello---"), "hello-world")
        self.assertEqual(slugify("!!!hello!!!"), "hello")


class TestSlugifyBoundariesAndEdges(unittest.TestCase):
    def test_empty_string_returns_untitled(self):
        self.assertEqual(slugify(""), "untitled")

    def test_only_separators_return_untitled(self):
        for title in ["!!!", "---", "   ", "___", "...", " - - - ", "\n\t "]:
            with self.subTest(title=title):
                self.assertEqual(slugify(title), "untitled")

    def test_non_ascii_becomes_dash(self):
        # Docstring: only ASCII a-z and 0-9 survive; everything else is a separator.
        self.assertEqual(slugify("caf\u00e9"), "caf")
        self.assertEqual(slugify("na\u00efve"), "na-ve")

    def test_non_ascii_uppercase_lowered_first(self):
        # "\u00c4BC".lower() == "\u00e4bc"; "\u00e4" is a separator run -> "-bc" -> "bc".
        self.assertEqual(slugify("\u00c4BC"), "bc")

    def test_single_char(self):
        self.assertEqual(slugify("a"), "a")
        self.assertEqual(slugify("A"), "a")
        self.assertEqual(slugify("1"), "1")
        self.assertEqual(slugify("!"), "untitled")

    def test_truncation_to_default_max_len(self):
        self.assertEqual(slugify("a" * 50), "a" * 40)
        self.assertEqual(slugify("a" * 41), "a" * 40)

    def test_exact_default_max_len_not_truncated(self):
        self.assertEqual(slugify("a" * 40), "a" * 40)

    def test_one_over_default_max_len(self):
        self.assertEqual(slugify("a" * 40 + "b"), "a" * 40)

    def test_truncation_strips_trailing_dash_again(self):
        # First pass gives "a"*39 + "-b" (41 chars); [:40] ends with "-"; final rstrip.
        self.assertEqual(slugify("a" * 39 + "!b"), "a" * 39)

    def test_truncation_keeps_internal_dashes(self):
        title = "ab cd ef gh ij kl mn op qr st uv wx yz 01 23 45 67 89"
        slug = slugify(title)
        self.assertLessEqual(len(slug), 40)
        self.assertFalse(slug.endswith("-"))
        self.assertEqual(slug, slugify(title, max_len=40))

    def test_custom_max_len(self):
        self.assertEqual(slugify("hello world", max_len=5), "hello")
        self.assertEqual(slugify("hello world", max_len=11), "hello-world")
        self.assertEqual(slugify("hello world", max_len=100), "hello-world")

    def test_custom_max_len_one(self):
        self.assertEqual(slugify("hello", max_len=1), "h")

    def test_max_len_zero_returns_untitled(self):
        # Truncate to 0 chars -> empty -> "untitled".
        self.assertEqual(slugify("hello", max_len=0), "untitled")
        self.assertEqual(slugify("", max_len=0), "untitled")

    def test_max_len_exact_result_length(self):
        self.assertEqual(slugify("hello-world", max_len=11), "hello-world")
        self.assertEqual(slugify("hello-world", max_len=10), "hello-worl")

    def test_custom_max_len_trailing_dash_stripped(self):
        # "ab!cd" -> "ab-cd"; [:3] == "ab-" -> "ab".
        self.assertEqual(slugify("ab!cd", max_len=3), "ab")

    def test_empty_after_truncation_returns_untitled(self):
        # "-" * 10 strips to "" -> "untitled"; any slug with max_len=0
        # truncates to "" -> "untitled".
        self.assertEqual(slugify("-" * 10), "untitled")
        self.assertEqual(slugify("-a", max_len=0), "untitled")
        self.assertEqual(slugify("ab", max_len=0), "untitled")

    def test_long_title_with_separators_stays_within_max_len(self):
        slug = slugify("Hello, World! " * 10)
        self.assertLessEqual(len(slug), 40)
        self.assertFalse(slug.startswith("-"))
        self.assertFalse(slug.endswith("-"))
        self.assertNotEqual(slug, "untitled")


class TestSlugifyErrorCases(unittest.TestCase):
    def test_none_title_raises_attribute_error(self):
        with self.assertRaises(AttributeError):
            slugify(None)

    def test_int_title_raises_attribute_error(self):
        with self.assertRaises(AttributeError):
            slugify(12345)

    def test_list_title_raises_attribute_error(self):
        with self.assertRaises(AttributeError):
            slugify(["hello"])

    def test_bytes_title_raises_type_error(self):
        with self.assertRaises(TypeError):
            slugify(b"hello")

    def test_string_max_len_raises_type_error(self):
        with self.assertRaises(TypeError):
            slugify("hello", max_len="5")


if __name__ == "__main__":
    unittest.main()
