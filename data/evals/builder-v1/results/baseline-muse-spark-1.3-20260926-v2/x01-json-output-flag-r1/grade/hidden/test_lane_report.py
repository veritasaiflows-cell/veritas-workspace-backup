import io
import unittest

from lane_report import main


class Visible(unittest.TestCase):
    def test_text(self):
        buf = io.StringIO()
        main([], rows=[{"agent": "b", "tokens": 2}, {"agent": "a", "tokens": 1}], out=buf)
        self.assertEqual(buf.getvalue(), "a: 1\nb: 2\n")


if __name__ == "__main__":
    unittest.main()
