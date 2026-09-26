import hashlib
import unittest

from dispatch_hash import matches, task_hash


class Hidden(unittest.TestCase):
    def test_crlf_and_trailing_newline(self):
        self.assertTrue(matches({"sha256": task_hash("line one\r\nline two\r\n")}, "line one\nline two"))

    def test_lone_cr(self):
        self.assertEqual(task_hash("a\rb"), task_hash("a\nb"))

    def test_internal_whitespace_kept(self):
        self.assertNotEqual(task_hash("a  b"), task_hash("a b"))
        self.assertNotEqual(task_hash("a\n\nb"), task_hash("a\nb"))

    def test_exact_digest(self):
        self.assertEqual(task_hash("  x\r\n"), hashlib.sha256(b"x").hexdigest())

    def test_mismatch(self):
        self.assertFalse(matches({"sha256": task_hash("a")}, "b"))


if __name__ == "__main__":
    unittest.main()
