import unittest

from record_check import validate

GOOD = {"dispatch_id": "d", "agent_id": "qa", "session_key": "agent:qa:job", "label": "L"}


def rec(**kw):
    out = dict(GOOD)
    out.update(kw)
    return out


class Hidden(unittest.TestCase):
    def test_whitespace_label(self):
        self.assertEqual(validate(rec(label="  \t")), ["missing:label"])

    def test_scoping(self):
        for key in ("agent:other:job", "agent:qa:", "qa:job", "agent:qajob", "agent:qa"):
            self.assertEqual(validate(rec(session_key=key)), ["session_key_not_scoped"], key)
        self.assertEqual(validate(rec(session_key="agent:qa:job:with:colons")), [])

    def test_scoping_skipped_when_missing(self):
        self.assertEqual(validate(rec(agent_id="")), ["missing:agent_id"])

    def test_created_at(self):
        self.assertEqual(validate(rec(created_at_ms=1790000000000)), [])
        for bad in (0, -5, True, "1790000000000", 1.5, None):
            self.assertEqual(validate(rec(created_at_ms=bad)), ["bad_created_at"], repr(bad))

    def test_order(self):
        out = validate({"agent_id": "qa", "session_key": "agent:x:y", "label": " ", "created_at_ms": False})
        self.assertEqual(out, ["missing:dispatch_id", "missing:label", "session_key_not_scoped", "bad_created_at"])


if __name__ == "__main__":
    unittest.main()
