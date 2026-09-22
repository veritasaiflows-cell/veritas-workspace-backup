import ledger


def test_known_kinds():
    assert ledger.balance([{"kind": "debit", "amount": 5},
                           {"kind": "credit", "amount": 3}]) == 8
