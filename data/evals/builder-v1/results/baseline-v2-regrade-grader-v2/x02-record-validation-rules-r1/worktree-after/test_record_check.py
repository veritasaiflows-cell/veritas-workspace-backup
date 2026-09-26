import unittest

from record_check import validate

GOOD = {"dispatch_id": "d", "agent_id": "qa", "session_key": "agent:qa:job", "label": "L"}


class Visible(unittest.TestCase):
    def test_good(self):
        self.assertEqual(validate(GOOD), [])


if __name__ == "__main__":
    unittest.main()
