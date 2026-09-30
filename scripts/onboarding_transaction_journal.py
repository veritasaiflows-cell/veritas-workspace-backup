#!/usr/bin/env python3
'''Onboarding transaction intent, ticker leases, and restart recovery.

This journal has its own SQLite file. It records outcomes but grants no
permission to write onboarding state.
'''
from __future__ import annotations

import datetime as dt
import hashlib
import importlib.util
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator


JOURNAL_REL = 'state/finance/onboarding-transactions.sqlite'
SCHEMA_VERSION = 1
LEASE_MINUTES = 30

# Load the accepted tier journal by its sibling path, not through sys.path.
_tier_path = Path(__file__).resolve().parent / 'tier_transaction_journal.py'
_tier_name = '_onboarding_tier_journal_' + hashlib.sha256(str(_tier_path).encode()).hexdigest()[:16]
_spec = importlib.util.spec_from_file_location(_tier_name, _tier_path)
if _spec is None or _spec.loader is None:
    raise ImportError('Cannot load tier_transaction_journal.py by path')
_tier = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_tier)
JournalRefusal = _tier.JournalRefusal
utc_now = _tier.utc_now
_iso = _tier._iso
_parse = _tier._parse
holder_alive = _tier.holder_alive
PENDING = _tier.PENDING
EFFECTIVE = _tier.EFFECTIVE
BLOCKED = _tier.BLOCKED
EXPIRED = _tier.EXPIRED
ROLLED_BACK = _tier.ROLLED_BACK
# Local extension only: exact canon evidence can arrive after timeout/crash settlement.
ALLOWED_MOVES = {state: set(moves) for state, moves in _tier.ALLOWED_MOVES.items()}
ALLOWED_MOVES.setdefault(EXPIRED, set()).add(EFFECTIVE)
ALLOWED_MOVES.setdefault(BLOCKED, set()).add(EFFECTIVE)
OPEN_STATES = _tier.OPEN_STATES

_DDL = '''
CREATE TABLE IF NOT EXISTS journal_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS transactions (
  txn_id TEXT PRIMARY KEY,
  ticker TEXT NOT NULL,
  mode TEXT NOT NULL CHECK (mode IN ('insert','refresh')),
  decision_id TEXT NOT NULL UNIQUE,
  decision_sha256 TEXT NOT NULL,
  band_packet_sha256 TEXT NOT NULL,
  prior_state_sha256 TEXT NOT NULL,
  state TEXT NOT NULL,
  opened_at TEXT NOT NULL,
  timeout_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  reasons_json TEXT NOT NULL DEFAULT '[]',
  commit_json TEXT
);
CREATE TABLE IF NOT EXISTS leases (
  ticker TEXT PRIMARY KEY,
  txn_id TEXT NOT NULL REFERENCES transactions(txn_id),
  holder TEXT NOT NULL,
  acquired_at TEXT NOT NULL,
  expires_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
  seq INTEGER PRIMARY KEY AUTOINCREMENT,
  txn_id TEXT NOT NULL,
  at TEXT NOT NULL,
  from_state TEXT,
  to_state TEXT NOT NULL,
  detail_json TEXT NOT NULL
);
'''


def _row(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    out = dict(row)
    out['reasons'] = json.loads(out.pop('reasons_json'))
    raw_commit = out.pop('commit_json')
    out['commit'] = json.loads(raw_commit) if raw_commit is not None else None
    return out


def _event(con: sqlite3.Connection, txn_id: str, now: dt.datetime,
           from_state: str | None, to_state: str, detail: dict[str, Any]) -> None:
    con.execute(
        'INSERT INTO events(txn_id, at, from_state, to_state, detail_json) VALUES (?,?,?,?,?)',
        (txn_id, _iso(now), from_state, to_state, json.dumps(detail, sort_keys=True, default=str)),
    )


class OnboardingTransactionJournal:
    def __init__(self, path: Path, clock: Callable[[], dt.datetime] = utc_now) -> None:
        self.path = Path(path)
        self.clock = clock
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as con:
            con.executescript(_DDL)
            con.execute(
                'INSERT OR IGNORE INTO journal_meta(key, value) VALUES (?, ?)',
                ('schema_version', str(SCHEMA_VERSION)),
            )
            con.commit()

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        con = sqlite3.connect(str(self.path), timeout=10, isolation_level=None)
        con.row_factory = sqlite3.Row
        con.execute('PRAGMA foreign_keys=ON')
        try:
            yield con
        finally:
            con.close()

    @contextmanager
    def _write(self) -> Iterator[sqlite3.Connection]:
        with self._conn() as con:
            con.execute('BEGIN IMMEDIATE')
            try:
                yield con
            except BaseException:
                con.execute('ROLLBACK')
                raise
            con.execute('COMMIT')

    def get(self, txn_id: str) -> dict[str, Any] | None:
        with self._conn() as con:
            row = con.execute('SELECT * FROM transactions WHERE txn_id=?', (txn_id,)).fetchone()
        return _row(row)

    def lease(self, ticker: str) -> dict[str, Any] | None:
        with self._conn() as con:
            row = con.execute('SELECT * FROM leases WHERE ticker=?', (ticker.upper(),)).fetchone()
        return dict(row) if row else None

    def open_transactions(self) -> list[dict[str, Any]]:
        with self._conn() as con:
            rows = con.execute(
                'SELECT * FROM transactions WHERE state IN (%s) ORDER BY opened_at'
                % ','.join('?' for _ in OPEN_STATES), tuple(OPEN_STATES),
            ).fetchall()
        return [_row(row) for row in rows]

    def effective_transactions(self) -> list[dict[str, Any]]:
        with self._conn() as con:
            rows = con.execute(
                'SELECT * FROM transactions WHERE state=? ORDER BY opened_at', (EFFECTIVE,),
            ).fetchall()
        return [_row(row) for row in rows]

    def events(self, txn_id: str) -> list[dict[str, Any]]:
        with self._conn() as con:
            rows = con.execute(
                'SELECT * FROM events WHERE txn_id=? ORDER BY seq', (txn_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def open(self, *, ticker: str, mode: str, decision_id: str,
             decision_sha256: str, band_packet_sha256: str,
             prior_state_sha256: str, holder: str) -> dict[str, Any]:
        '''Consume a decision and take its ticker lease in one transaction.

        Even an expired lease remains held until recovery settles its transaction.
        '''
        ticker = ticker.upper()
        if mode not in ('insert', 'refresh'):
            raise JournalRefusal('invalid_mode:%s' % mode)
        now = self.clock()
        timeout = now + dt.timedelta(minutes=LEASE_MINUTES)
        txn_id = 'ot_%s_%s_%s' % (
            now.strftime('%Y%m%dT%H%M%S%fZ'), ticker,
            hashlib.sha256(f'{ticker}|{decision_id}|{decision_sha256}'.encode()).hexdigest()[:8],
        )
        with self._write() as con:
            held = con.execute('SELECT * FROM leases WHERE ticker=?', (ticker,)).fetchone()
            if held is not None:
                raise JournalRefusal('lease_held:%s by %s (%s) until %s' %
                                     (ticker, held['txn_id'], held['holder'], held['expires_at']))
            used = con.execute(
                'SELECT txn_id, state FROM transactions WHERE decision_id=?', (decision_id,),
            ).fetchone()
            if used is not None:
                raise JournalRefusal('decision_already_consumed:%s by %s (%s)' %
                                     (decision_id, used['txn_id'], used['state']))
            con.execute(
                'INSERT INTO transactions(txn_id, ticker, mode, decision_id, decision_sha256, '
                'band_packet_sha256, prior_state_sha256, state, opened_at, timeout_at, updated_at) '
                'VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                (txn_id, ticker, mode, decision_id, decision_sha256,
                 band_packet_sha256, prior_state_sha256, PENDING,
                 _iso(now), _iso(timeout), _iso(now)),
            )
            con.execute(
                'INSERT INTO leases(ticker, txn_id, holder, acquired_at, expires_at) VALUES (?,?,?,?,?)',
                (ticker, txn_id, holder, _iso(now), _iso(timeout)),
            )
            _event(con, txn_id, now, None, PENDING,
                   {'holder': holder, 'timeout_at': _iso(timeout)})
        return self.get(txn_id)

    def check_live(self, txn_id: str, current_prior_state_sha256: str) -> dict[str, Any]:
        txn = self.get(txn_id)
        if txn is None:
            raise JournalRefusal('unknown_transaction:%s' % txn_id)
        if txn['state'] != PENDING:
            raise JournalRefusal('transaction_not_pending:%s state=%s' %
                                 (txn_id, txn['state']))
        lease = self.lease(txn['ticker'])
        if lease is None or lease['txn_id'] != txn_id:
            raise JournalRefusal('lease_lost:%s' % txn['ticker'])
        if self.clock() >= _parse(txn['timeout_at']):
            raise JournalRefusal('transaction_timed_out:%s at %s' %
                                 (txn_id, txn['timeout_at']))
        if current_prior_state_sha256 != txn['prior_state_sha256']:
            raise JournalRefusal('prior_state_mismatch:%s state changed since the transaction opened'
                                 % txn['ticker'])
        return txn

    def mark_effective(self, txn_id: str, commit: dict[str, Any]) -> dict[str, Any]:
        return self._move(txn_id, EFFECTIVE, {'commit': commit}, commit=commit, release=True)

    def mark_blocked(self, txn_id: str, reason: str) -> dict[str, Any]:
        return self._move(txn_id, BLOCKED, {'reason': reason}, reason=reason, release=True)

    def mark_expired(self, txn_id: str, reason: str) -> dict[str, Any]:
        return self._move(txn_id, EXPIRED, {'reason': reason}, reason=reason, release=True)

    def mark_rolled_back(self, txn_id: str, detail: dict[str, Any]) -> dict[str, Any]:
        return self._move(txn_id, ROLLED_BACK, detail,
                          reason=detail.get('reason'), release=False)

    def _move(self, txn_id: str, to_state: str, detail: dict[str, Any], *,
              commit: dict[str, Any] | None = None, reason: str | None = None,
              release: bool = False) -> dict[str, Any]:
        now = self.clock()
        with self._write() as con:
            row = con.execute('SELECT * FROM transactions WHERE txn_id=?', (txn_id,)).fetchone()
            if row is None:
                raise JournalRefusal('unknown_transaction:%s' % txn_id)
            current = row['state']
            if current == to_state:
                return _row(row)
            if to_state not in ALLOWED_MOVES.get(current, set()):
                raise JournalRefusal('illegal_transition:%s %s->%s' %
                                     (txn_id, current, to_state))
            if current in (EXPIRED, BLOCKED) and to_state == EFFECTIVE:
                # A late commit cannot reverse a terminal refusal on a bare claim.
                if (not isinstance(commit, dict)
                        or commit.get('canon_audit_event_id') != 'onb_apply_' + txn_id
                        or commit.get('txn_id') != txn_id
                        or commit.get('ticker') != row['ticker']
                        or commit.get('decision_id') != row['decision_id']):
                    raise JournalRefusal('exact_commit_evidence_required:%s' % txn_id)
            reasons = json.loads(row['reasons_json'])
            if reason:
                reasons.append(reason)
            con.execute(
                'UPDATE transactions SET state=?, updated_at=?, reasons_json=?, '
                'commit_json=COALESCE(?, commit_json) WHERE txn_id=?',
                (to_state, _iso(now), json.dumps(reasons),
                 json.dumps(commit, sort_keys=True) if commit is not None else None, txn_id),
            )
            if release:
                con.execute('DELETE FROM leases WHERE ticker=? AND txn_id=?',
                            (row['ticker'], txn_id))
            _event(con, txn_id, now, current, to_state, detail)
            out = con.execute('SELECT * FROM transactions WHERE txn_id=?', (txn_id,)).fetchone()
        return _row(out)

    def recover(self, commit_probe: Callable[[dict[str, Any]], dict[str, Any] | None],
                *, after_crash: bool = False,
                rollback_probe: Callable[[dict[str, Any]], dict[str, Any] | None] | None = None,
                is_alive: Callable[[str], bool] = holder_alive) -> list[dict[str, Any]]:
        '''Settle committed or timed-out pending transactions; optionally reconcile rollback.

        Commit evidence takes precedence over timeout. A still-live holder is not
        blocked during crash recovery. The probes must verify authoritative commits.
        '''
        settled = []
        now = self.clock()
        for txn in self.open_transactions():
            evidence = commit_probe(txn)
            if evidence is not None:
                settled.append(self._move(
                    txn['txn_id'], EFFECTIVE, {'recovered': True, 'commit': evidence},
                    commit=evidence, reason='recovered_commit_present', release=True,
                ))
            elif now >= _parse(txn['timeout_at']):
                settled.append(self.mark_expired(txn['txn_id'], 'timeout_30_minutes'))
            elif after_crash:
                lease = self.lease(txn['ticker'])
                holder = lease['holder'] if lease and lease['txn_id'] == txn['txn_id'] else ''
                if holder and is_alive(holder):
                    continue
                settled.append(self.mark_blocked(txn['txn_id'], 'restart_recovery_no_commit'))
        # A writer can commit after a concurrent recovery expired or blocked its
        # intent. Re-probe terminal rows; absence never changes their state.
        with self._conn() as con:
            rows = con.execute(
                'SELECT * FROM transactions WHERE state IN (?,?) ORDER BY opened_at',
                (EXPIRED, BLOCKED),
            ).fetchall()
        for row in rows:
            txn = _row(row)
            evidence = commit_probe(txn)
            if evidence is not None:
                settled.append(self._move(
                    txn['txn_id'], EFFECTIVE, {'recovered': True, 'commit': evidence},
                    commit=evidence, reason='recovered_commit_present', release=True,
                ))
        if rollback_probe is not None:
            for txn in self.effective_transactions():
                evidence = rollback_probe(txn)
                if evidence is not None:
                    settled.append(self.mark_rolled_back(
                        txn['txn_id'], {'reason': 'recovered_inverse_commit_present', **evidence},
                    ))
        return settled


def consumed(path: Path, decision_id: str) -> dict[str, Any] | None:
    '''Read a consumed decision without initializing a journal. Returns None if absent.'''
    path = Path(path)
    if not path.is_file():
        return None
    con = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)
    con.row_factory = sqlite3.Row
    try:
        return _row(con.execute(
            'SELECT * FROM transactions WHERE decision_id=?', (decision_id,),
        ).fetchone())
    finally:
        con.close()


def onboarding_lease_held(path: Path, ticker: str) -> str | None:
    '''Read a lease without initializing the onboarding journal.'''
    path = Path(path)
    if not path.is_file():
        return None
    con = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)
    con.row_factory = sqlite3.Row
    try:
        row = con.execute(
            'SELECT txn_id, holder, expires_at FROM leases WHERE ticker=?',
            (ticker.upper(),),
        ).fetchone()
        return '%s (%s) until %s' % (row['txn_id'], row['holder'], row['expires_at']) if row else None
    finally:
        con.close()


def tier_lease_held(root: Path, ticker: str) -> str | None:
    '''Inspect the separate tier journal without creating any files or directories.'''
    path = Path(root) / _tier.JOURNAL_REL
    if not path.is_file():
        return None
    con = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)
    con.row_factory = sqlite3.Row
    try:
        row = con.execute(
            'SELECT txn_id, holder, expires_at FROM leases WHERE ticker=?',
            (ticker.upper(),),
        ).fetchone()
        return '%s (%s) until %s' % (row['txn_id'], row['holder'], row['expires_at']) if row else None
    finally:
        con.close()
