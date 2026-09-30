'''Unit tests for the onboarding journal; all database paths are under tmp_path.'''
from __future__ import annotations

import datetime as dt
import hashlib
import importlib.util
import json
import sqlite3
import threading
from pathlib import Path

import pytest


SCRIPTS = Path(__file__).resolve().parent


def load_by_path(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


oj = load_by_path('_test_onboarding_journal', SCRIPTS / 'onboarding_transaction_journal.py')
tj = load_by_path('_test_tier_journal', SCRIPTS / 'tier_transaction_journal.py')
START = dt.datetime(2026, 9, 28, 14, tzinfo=dt.timezone.utc)


class Clock:
    def __init__(self):
        self.now = START

    def __call__(self):
        return self.now


def journal(tmp_path):
    clock = Clock()
    path = tmp_path / oj.JOURNAL_REL
    return oj.OnboardingTransactionJournal(path, clock=clock), clock


def open_one(j, *, ticker='xyz', mode='insert', decision='d-1', holder='worker'):
    return j.open(ticker=ticker, mode=mode, decision_id=decision,
                  decision_sha256='ab' * 32, band_packet_sha256='cd' * 32,
                  prior_state_sha256='ef' * 32, holder=holder)


def test_open_lease_consumption_and_reopen(tmp_path):
    j, clock = journal(tmp_path)
    txn = open_one(j)
    suffix = hashlib.sha256(('XYZ|d-1|' + 'ab' * 32).encode()).hexdigest()[:8]
    assert txn['txn_id'] == 'ot_20260928T140000000000Z_XYZ_' + suffix
    assert txn['ticker'] == 'XYZ' and txn['mode'] == 'insert'
    assert txn['state'] == oj.PENDING and txn['decision_sha256'] == 'ab' * 32
    assert txn['band_packet_sha256'] == 'cd' * 32
    assert txn['prior_state_sha256'] == 'ef' * 32
    assert txn['timeout_at'] == oj._iso(START + dt.timedelta(minutes=30))
    assert txn['reasons'] == [] and txn['commit'] is None
    assert j.lease('xyz')['txn_id'] == txn['txn_id']
    assert j.lease('XYZ')['expires_at'] == txn['timeout_at']
    assert [r['txn_id'] for r in j.open_transactions()] == [txn['txn_id']]
    assert j.effective_transactions() == []
    event = j.events(txn['txn_id'])[0]
    assert event['from_state'] is None and event['to_state'] == oj.PENDING
    assert json.loads(event['detail_json'])['holder'] == 'worker'
    assert oj.consumed(j.path, 'd-1')['txn_id'] == txn['txn_id']
    assert oj.consumed(j.path, 'unused') is None
    assert oj.OnboardingTransactionJournal(j.path, clock=clock).get(txn['txn_id']) == txn


def test_lease_held_even_past_timeout_and_decision_consumed_after_release(tmp_path):
    j, clock = journal(tmp_path)
    first = open_one(j)
    clock.now += dt.timedelta(hours=1)
    with pytest.raises(oj.JournalRefusal) as exc:
        open_one(j, decision='d-2', holder='second')
    assert str(exc.value) == ('lease_held:XYZ by %s (worker) until %s'
                              % (first['txn_id'], first['timeout_at']))
    assert j.lease('XYZ')['txn_id'] == first['txn_id']
    assert j.get(first['txn_id'])['state'] == oj.PENDING
    j.mark_expired(first['txn_id'], 'timeout')
    with pytest.raises(oj.JournalRefusal) as exc:
        open_one(j)
    assert str(exc.value) == ('decision_already_consumed:d-1 by %s (expired)'
                              % first['txn_id'])
    second = open_one(j, mode='refresh', decision='d-2')
    assert second['mode'] == 'refresh' and j.lease('XYZ')['txn_id'] == second['txn_id']


def test_concurrent_open_has_one_winner(tmp_path):
    j, _ = journal(tmp_path)
    outcomes = []

    def attempt(n):
        try:
            open_one(j, decision='d-%s' % n)
            outcomes.append('opened')
        except oj.JournalRefusal as exc:
            outcomes.append(str(exc).split(':', 1)[0])

    threads = [threading.Thread(target=attempt, args=(n,)) for n in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert outcomes.count('opened') == 1
    assert outcomes.count('lease_held') == 5
    assert len(j.open_transactions()) == 1


def test_invalid_mode_does_not_consume_decision(tmp_path):
    j, _ = journal(tmp_path)
    with pytest.raises(oj.JournalRefusal, match='^invalid_mode:upsert$'):
        open_one(j, mode='upsert')
    assert j.open_transactions() == [] and j.lease('XYZ') is None
    assert oj.consumed(j.path, 'd-1') is None


def test_check_live_all_branches(tmp_path):
    j, clock = journal(tmp_path)
    with pytest.raises(oj.JournalRefusal, match='^unknown_transaction:missing$'):
        j.check_live('missing', 'ef' * 32)
    first = open_one(j)
    assert j.check_live(first['txn_id'], 'ef' * 32) == first
    with pytest.raises(oj.JournalRefusal, match='^prior_state_mismatch:XYZ'):
        j.check_live(first['txn_id'], 'changed')
    clock.now = oj._parse(first['timeout_at'])
    with pytest.raises(oj.JournalRefusal, match='^transaction_timed_out:'):
        j.check_live(first['txn_id'], 'ef' * 32)
    clock.now = START
    with sqlite3.connect(j.path) as con:
        con.execute('DELETE FROM leases WHERE ticker=?', ('XYZ',))
    with pytest.raises(oj.JournalRefusal, match='^lease_lost:XYZ$'):
        j.check_live(first['txn_id'], 'ef' * 32)
    j.mark_blocked(first['txn_id'], 'lost lease')
    with pytest.raises(oj.JournalRefusal, match='^transaction_not_pending:'):
        j.check_live(first['txn_id'], 'ef' * 32)


@pytest.mark.parametrize('method,arg,state', [
    ('mark_effective', {'audit': 'e1'}, oj.EFFECTIVE),
    ('mark_blocked', 'not ready', oj.BLOCKED),
    ('mark_expired', 'timeout', oj.EXPIRED),
])
def test_terminal_moves_release_lease_and_repeat_is_idempotent(tmp_path, method, arg, state):
    j, _ = journal(tmp_path)
    txn = open_one(j)
    moved = getattr(j, method)(txn['txn_id'], arg)
    assert moved['state'] == state and j.lease('XYZ') is None
    assert [e['to_state'] for e in j.events(txn['txn_id'])] == [oj.PENDING, state]
    assert getattr(j, method)(txn['txn_id'], arg) == moved
    assert len(j.events(txn['txn_id'])) == 2
    assert oj.consumed(j.path, 'd-1')['state'] == state
    if state == oj.EFFECTIVE:
        assert moved['commit'] == arg
        assert [t['txn_id'] for t in j.effective_transactions()] == [txn['txn_id']]
    else:
        assert moved['reasons'] == [arg]
        assert j.effective_transactions() == []
    assert j.open_transactions() == []


@pytest.mark.parametrize('first,second', [
    ('mark_effective', 'mark_blocked'),
    ('mark_blocked', 'mark_effective'),
    ('mark_expired', 'mark_effective'),
    ('mark_blocked', 'mark_expired'),
])
def test_illegal_transitions(tmp_path, first, second):
    j, _ = journal(tmp_path)
    txn = open_one(j)
    arg = {'audit': 'e1'} if first == 'mark_effective' else 'reason'
    getattr(j, first)(txn['txn_id'], arg)
    arg = {'audit': 'e2'} if second == 'mark_effective' else 'reason'
    # B2 fix round (QA A3): blocked/expired -> effective is legal only with exact
    # canon commit evidence, so inexact evidence is refused on that ground.
    expected = ('^exact_commit_evidence_required:'
                if first in ('mark_blocked', 'mark_expired') and second == 'mark_effective'
                else '^illegal_transition:')
    with pytest.raises(oj.JournalRefusal, match=expected):
        getattr(j, second)(txn['txn_id'], arg)


@pytest.mark.parametrize('terminal', [oj.EXPIRED, oj.BLOCKED])
def test_terminal_late_exact_commit_recovery_and_mark_effective(tmp_path, terminal):
    j, clock = journal(tmp_path)
    txn = open_one(j)
    txn_id = txn['txn_id']
    if terminal == oj.EXPIRED:
        clock.now = oj._parse(txn['timeout_at'])
        assert [s['state'] for s in j.recover(lambda _: None)] == [oj.EXPIRED]
    else:
        assert [s['state'] for s in j.recover(
            lambda _: None, after_crash=True, is_alive=lambda _: False)] == [oj.BLOCKED]
    assert j.lease('XYZ') is None
    assert j.recover(lambda _: None) == []
    assert j.get(txn_id)['state'] == terminal
    evidence = {'canon_audit_event_id': 'onb_apply_' + txn_id,
                'txn_id': txn_id, 'ticker': 'XYZ', 'decision_id': 'd-1'}
    for wrong in ({'audit': 'e1'},
                  {**evidence, 'decision_id': 'other'},
                  {**evidence, 'canon_audit_event_id': 'onb_apply_' + txn_id + 'x'}):
        with pytest.raises(oj.JournalRefusal, match='^exact_commit_evidence_required:'):
            j.mark_effective(txn_id, wrong)
        assert j.get(txn_id)['state'] == terminal
    # The caller-supplied probe stands for the exact canon event. No event:
    # no promotion. An exact result promotes and remains idempotently settled.
    settled = j.recover(lambda _: evidence)
    assert [s['state'] for s in settled] == [oj.EFFECTIVE]
    assert settled[0]['commit'] == evidence
    assert settled[0]['reasons'][-1] == 'recovered_commit_present'
    assert j.recover(lambda _: evidence) == []


@pytest.mark.parametrize('terminal', [oj.EXPIRED, oj.BLOCKED])
def test_direct_terminal_mark_effective_requires_exact_evidence(tmp_path, terminal):
    j, _ = journal(tmp_path)
    txn = open_one(j)
    txn_id = txn['txn_id']
    if terminal == oj.EXPIRED:
        j.mark_expired(txn_id, 'timeout')
    else:
        j.mark_blocked(txn_id, 'crash')
    evidence = {'canon_audit_event_id': 'onb_apply_' + txn_id,
                'txn_id': txn_id, 'ticker': 'XYZ', 'decision_id': 'd-1'}
    assert j.mark_effective(txn_id, evidence)['state'] == oj.EFFECTIVE


def test_rollback_only_from_effective_repeat_and_no_lease_release(tmp_path):
    j, _ = journal(tmp_path)
    txn = open_one(j)
    with pytest.raises(oj.JournalRefusal, match='^illegal_transition:'):
        j.mark_rolled_back(txn['txn_id'], {'reason': 'inverse'})
    j.mark_effective(txn['txn_id'], {'audit': 'e1'})
    next_txn = open_one(j, decision='d-2')
    rolled = j.mark_rolled_back(txn['txn_id'], {'reason': 'inverse'})
    assert rolled['state'] == oj.ROLLED_BACK and rolled['reasons'] == ['inverse']
    assert j.lease('XYZ')['txn_id'] == next_txn['txn_id']
    assert j.mark_rolled_back(txn['txn_id'], {'reason': 'different'}) == rolled
    assert [e['to_state'] for e in j.events(txn['txn_id'])] == [
        oj.PENDING, oj.EFFECTIVE, oj.ROLLED_BACK,
    ]
    with pytest.raises(oj.JournalRefusal, match='^illegal_transition:'):
        j.mark_effective(txn['txn_id'], {'audit': 'e2'})


def test_unknown_move_refused(tmp_path):
    j, _ = journal(tmp_path)
    with pytest.raises(oj.JournalRefusal, match='^unknown_transaction:missing$'):
        j.mark_expired('missing', 'reason')


def test_recover_commit_precedes_timeout_and_is_repeatable(tmp_path):
    j, clock = journal(tmp_path)
    txn = open_one(j)
    clock.now = oj._parse(txn['timeout_at']) + dt.timedelta(seconds=1)
    settled = j.recover(lambda t: {'audit': 'e1'})
    assert [s['state'] for s in settled] == [oj.EFFECTIVE]
    assert settled[0]['commit'] == {'audit': 'e1'}
    assert settled[0]['reasons'] == ['recovered_commit_present']
    assert j.lease('XYZ') is None and j.recover(lambda t: {'audit': 'e1'}) == []


def test_recover_timeout_expires_and_no_crash_leaves_pending(tmp_path):
    j, clock = journal(tmp_path)
    txn = open_one(j)
    assert j.recover(lambda t: None) == []
    assert j.get(txn['txn_id'])['state'] == oj.PENDING
    clock.now = oj._parse(txn['timeout_at'])
    settled = j.recover(lambda t: None)
    assert [s['state'] for s in settled] == [oj.EXPIRED]
    assert settled[0]['reasons'] == ['timeout_30_minutes']
    assert j.lease('XYZ') is None and j.recover(lambda t: None) == []


@pytest.mark.parametrize('alive,expected', [(False, oj.BLOCKED), (True, oj.PENDING)])
def test_recover_after_crash_respects_holder_liveness(tmp_path, alive, expected):
    j, _ = journal(tmp_path)
    txn = open_one(j, holder='writer:host:123')
    seen = []
    result = j.recover(lambda t: None, after_crash=True,
                       is_alive=lambda holder: seen.append(holder) or alive)
    assert seen == ['writer:host:123']
    assert j.get(txn['txn_id'])['state'] == expected
    assert [s['state'] for s in result] == ([] if alive else [oj.BLOCKED])
    if alive:
        assert j.lease('XYZ')['txn_id'] == txn['txn_id']
    else:
        assert j.lease('XYZ') is None
        assert result[0]['reasons'] == ['restart_recovery_no_commit']


def test_recover_after_crash_without_matching_lease_blocks(tmp_path):
    j, _ = journal(tmp_path)
    txn = open_one(j)
    with sqlite3.connect(j.path) as con:
        con.execute('DELETE FROM leases WHERE ticker=?', ('XYZ',))
    result = j.recover(lambda t: None, after_crash=True,
                       is_alive=lambda holder: pytest.fail('no holder should be checked'))
    assert [s['state'] for s in result] == [oj.BLOCKED]
    assert j.get(txn['txn_id'])['state'] == oj.BLOCKED


def test_recover_rollback_probe_only_effective_and_repeatable(tmp_path):
    j, _ = journal(tmp_path)
    txn = open_one(j)
    j.mark_effective(txn['txn_id'], {'audit': 'e1'})
    assert j.recover(lambda t: None, rollback_probe=lambda t: None) == []
    result = j.recover(lambda t: None,
                       rollback_probe=lambda t: {'audit': 'inverse-e1'})
    assert [s['state'] for s in result] == [oj.ROLLED_BACK]
    assert result[0]['reasons'] == ['recovered_inverse_commit_present']
    assert j.recover(lambda t: None,
                     rollback_probe=lambda t: {'audit': 'inverse-e1'}) == []


def test_read_only_helpers_on_absent_files_create_nothing(tmp_path):
    root = tmp_path / 'does-not-exist'
    assert oj.consumed(root / oj.JOURNAL_REL, 'd-1') is None
    assert oj.onboarding_lease_held(root / oj.JOURNAL_REL, 'XYZ') is None
    assert oj.tier_lease_held(root, 'XYZ') is None
    assert not root.exists()


def test_tier_lease_helper_reads_real_tier_journal(tmp_path):
    clock = Clock()
    tier_path = tmp_path / tj.JOURNAL_REL
    tier = tj.TierTransactionJournal(tier_path, clock=clock)
    prior = {'tier': 'C'}
    forward = {'tier': 'B'}
    txn = tier.open(ticker='xyz', from_tier='C', to_tier='B',
                    prior_family=prior, forward_family=forward,
                    decision_id='tier-d-1', decision_sha256='ab' * 32,
                    holder='tier-writer')
    assert oj.tier_lease_held(tmp_path, 'xyz') == (
        '%s (tier-writer) until %s' % (txn['txn_id'], txn['timeout_at'])
    )
    assert oj.tier_lease_held(tmp_path, 'OTHER') is None
    tier.mark_blocked(txn['txn_id'], 'test')
    assert oj.tier_lease_held(tmp_path, 'XYZ') is None
