import bounds
import ledger
import report

assert bounds.within(0, 10, 0) is True, 'lower bound inclusive'
assert bounds.within(0, 10, 10) is True, 'upper bound inclusive'
assert bounds.within(0, 10, -1) is False, 'below range'
assert bounds.within(0, 10, 11) is False, 'above range'

try:
    ledger.balance([{"kind": "reversal", "amount": 5}])
except ValueError:
    pass
else:
    raise AssertionError('unknown kind must raise ValueError')

assert ledger.balance([{"kind": "debit", "amount": 5},
                       {"kind": "credit", "amount": 3}]) == 8
assert report.weekly_total([{"kind": "debit", "amount": 4}]) == 4
