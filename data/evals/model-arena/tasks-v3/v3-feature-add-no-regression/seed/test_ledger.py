"""Authoritative ledger suite. Correct as written.

TestExisting already passes against the current code and must keep passing.
TestReversal describes the feature that is not implemented yet.
"""
import unittest

from ledger import balance, validate


class TestExisting(unittest.TestCase):
    def test_empty_ledger(self):
        self.assertEqual(balance([]), 0)

    def test_credits_and_debits(self):
        self.assertEqual(balance([
            {"id": "e1", "kind": "credit", "amount": 500},
            {"id": "e2", "kind": "debit", "amount": 200},
        ]), 300)

    def test_validate_accepts_credit(self):
        self.assertTrue(validate({"id": "e1", "kind": "credit", "amount": 1}))

    def test_unknown_kind_rejected(self):
        with self.assertRaises(ValueError):
            validate({"id": "e1", "kind": "transfer", "amount": 1})

    def test_negative_amount_rejected(self):
        with self.assertRaises(ValueError):
            validate({"id": "e1", "kind": "credit", "amount": -1})

    def test_non_integer_amount_rejected(self):
        with self.assertRaises(ValueError):
            validate({"id": "e1", "kind": "credit", "amount": 1.5})


class TestReversal(unittest.TestCase):
    def test_validate_reversal_needs_no_amount(self):
        self.assertTrue(validate({"id": "r1", "kind": "reversal", "ref": "e1"}))

    def test_validate_reversal_requires_ref(self):
        with self.assertRaises(ValueError):
            validate({"id": "r1", "kind": "reversal"})

    def test_reversal_cancels_a_credit(self):
        self.assertEqual(balance([
            {"id": "e1", "kind": "credit", "amount": 500},
            {"id": "r1", "kind": "reversal", "ref": "e1"},
        ]), 0)

    def test_reversal_cancels_a_debit(self):
        self.assertEqual(balance([
            {"id": "e1", "kind": "credit", "amount": 500},
            {"id": "e2", "kind": "debit", "amount": 200},
            {"id": "r1", "kind": "reversal", "ref": "e2"},
        ]), 500)

    def test_unknown_ref_rejected(self):
        with self.assertRaises(ValueError):
            balance([{"id": "r1", "kind": "reversal", "ref": "nope"}])

    def test_forward_ref_rejected(self):
        with self.assertRaises(ValueError):
            balance([
                {"id": "r1", "kind": "reversal", "ref": "e1"},
                {"id": "e1", "kind": "credit", "amount": 500},
            ])

    def test_double_reversal_rejected(self):
        with self.assertRaises(ValueError):
            balance([
                {"id": "e1", "kind": "credit", "amount": 500},
                {"id": "r1", "kind": "reversal", "ref": "e1"},
                {"id": "r2", "kind": "reversal", "ref": "e1"},
            ])

    def test_reversing_a_reversal_rejected(self):
        with self.assertRaises(ValueError):
            balance([
                {"id": "e1", "kind": "credit", "amount": 500},
                {"id": "r1", "kind": "reversal", "ref": "e1"},
                {"id": "r2", "kind": "reversal", "ref": "r1"},
            ])


if __name__ == "__main__":
    unittest.main()
