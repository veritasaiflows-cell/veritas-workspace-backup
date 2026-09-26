import unittest

from slug import slugify


class T(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(slugify("Hello World"), "hello-world")

    def test_runs_collapse(self):
        self.assertEqual(slugify("a  --  b!!c"), "a-b-c")

    def test_strip_edges(self):
        self.assertEqual(slugify("  --Hi there--  "), "hi-there")

    def test_truncate_then_strip(self):
        self.assertEqual(slugify("abc def", max_len=4), "abc")

    def test_empty(self):
        self.assertEqual(slugify("!!!"), "untitled")
        self.assertEqual(slugify(""), "untitled")


if __name__ == "__main__":
    unittest.main()
