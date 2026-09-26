import unittest

from tickers import load_watchlist


class Visible(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(load_watchlist("MSFT, nvda ,"), ["MSFT", "nvda"])


if __name__ == "__main__":
    unittest.main()
