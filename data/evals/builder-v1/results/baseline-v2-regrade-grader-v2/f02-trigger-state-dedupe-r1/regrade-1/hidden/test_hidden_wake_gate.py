import unittest

from wake_gate import decide


class Hidden(unittest.TestCase):
    def test_first_run(self):
        self.assertEqual(decide({}, "a"), (True, {"signature": "a", "fired_count": 1}))

    def test_none_state(self):
        self.assertEqual(decide({"state": None}, "a"), (True, {"signature": "a", "fired_count": 1}))

    def test_same_signature_does_not_fire(self):
        state = {"signature": "a", "fired_count": 4}
        fire, new = decide({"state": state}, "a")
        self.assertFalse(fire)
        self.assertEqual(new, {"signature": "a", "fired_count": 4})

    def test_new_signature_increments(self):
        fire, new = decide({"state": {"signature": "a", "fired_count": 4}}, "b")
        self.assertTrue(fire)
        self.assertEqual(new, {"signature": "b", "fired_count": 5})

    def test_sequence(self):
        state = None
        fires = []
        for sig in ["a", "a", "b", "b", "a"]:
            fire, state = decide({"state": state}, sig)
            fires.append(fire)
        self.assertEqual(fires, [True, False, True, False, True])
        self.assertEqual(state["fired_count"], 3)

    def test_ignores_legacy_last_key(self):
        fire, _ = decide({"last": {"signature": "a"}, "state": None}, "a")
        self.assertTrue(fire)


if __name__ == "__main__":
    unittest.main()
