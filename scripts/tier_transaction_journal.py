#!/usr/bin/env python3
"""Phase 4 tier-transaction journal: per-ticker lease, state machine, timeout,
restart recovery and one-shot owner-decision consumption.

Implements the mechanics the Tier Entitlement and Atomic Promotion Review
Contract (v0.9.1, "Atomic promotion" / "Atomic demotion") requires before any
guarded-SQL tier write may run:

1. one exclusive ticker lease for the whole transaction;
2. a unique transaction id, expected prior tier and row version, forward
   action, exact inverse and timeout;
3. idempotent steps; a second writer or a prior-version mismatch fails closed;
4. default timeout = end of the next market session; timeout returns the
   ticker to its prior effective tier with reasons;
5. restart recovery finalizes a transaction whose effective-tier commit is
   present, and expires or blocks one without it. A half-promoted ticker is
   never observable as effective, because the canon tier write itself is a
   single SQLite transaction owned by scripts/tier_membership_writer.py.

State machine (per ticker):

    pending_coverage -> effective | blocked | expired
    effective        -> rolled_back

The journal lives in its OWN SQLite file (state/finance/tier-transactions.sqlite),
never inside the finance canon, so creating it changes no canon schema. It
records intent and outcome; it grants no authority. Whether an apply may run
at all is decided by the cutover gate and owner-decision records checked in
scripts/tier_membership_writer.py.

stdlib only. No network.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import socket
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator
from zoneinfo import ZoneInfo

JOURNAL_REL = "state/finance/tier-transactions.sqlite"
SCHEMA_VERSION = 1

PENDING = "pending_coverage"
EFFECTIVE = "effective"
BLOCKED = "blocked"
EXPIRED = "expired"
ROLLED_BACK = "rolled_back"
TERMINAL = {BLOCKED, EXPIRED, ROLLED_BACK}
OPEN_STATES = {PENDING}
ALLOWED_MOVES = {
    PENDING: {EFFECTIVE, BLOCKED, EXPIRED},
    EFFECTIVE: {ROLLED_BACK},
}

NY = ZoneInfo("America/New_York")
SESSION_OPEN = _dt.time(9, 30)
SESSION_CLOSE_HOUR = 16
EARLY_CLOSE_HOUR = 13
# NYSE full-day closures. A year missing from this table is treated as having
# NO holidays, which only ever makes a timeout EARLIER (fail-safe: expire
# sooner, never later).
NYSE_HOLIDAYS = {
    2026: {"2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03", "2026-05-25",
           "2026-06-19", "2026-07-03", "2026-09-07", "2026-11-26", "2026-12-25"},
    2027: {"2027-01-01", "2027-01-18", "2027-02-15", "2027-03-26", "2027-05-31",
           "2027-06-18", "2027-07-05", "2027-09-06", "2027-11-25", "2027-12-24"},
}
# 13:00 early closes (day after Thanksgiving, Christmas Eve on a weekday). An
# early close missing here leaves the timeout at most three hours late on
# that one day.
NYSE_EARLY_CLOSES = {"2026-11-27", "2026-12-24", "2027-11-26"}

Clock = Callable[[], _dt.datetime]


class JournalRefusal(Exception):
    """A journal precondition failed; nothing was changed."""


def utc_now() -> _dt.datetime:
    return _dt.datetime.now(_dt.timezone.utc)


def _iso(moment: _dt.datetime) -> str:
    return moment.astimezone(_dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _parse(value: str) -> _dt.datetime:
    return _dt.datetime.fromisoformat(value.replace("Z", "+00:00"))


def is_market_day(day: _dt.date) -> bool:
    return day.weekday() < 5 and day.isoformat() not in NYSE_HOLIDAYS.get(day.year, set())


def end_of_next_market_session(opened_at: _dt.datetime) -> _dt.datetime:
    """Close of the first market session that starts at or after ``opened_at``.

    Opened before a market day's 09:30 open -> that day's close. Opened during
    or after a session -> the next market day's close (the contract's "end of
    the next market session"), so a transaction always gets one full session.
    """
    local = opened_at.astimezone(NY)
    day = local.date()
    if not (is_market_day(day) and local.time() < SESSION_OPEN):
        day += _dt.timedelta(days=1)
        while not is_market_day(day):
            day += _dt.timedelta(days=1)
    hour = EARLY_CLOSE_HOUR if day.isoformat() in NYSE_EARLY_CLOSES else SESSION_CLOSE_HOUR
    close = _dt.datetime(day.year, day.month, day.day, hour, tzinfo=NY)
    return close.astimezone(_dt.timezone.utc)


def holder_alive(holder: str) -> bool:
    """True unless ``holder`` names a process on this host that has exited.

    Writers record ``<name>:<host>:<pid>`` (older records ``<name>:<pid>`` mean
    this host). A holder on another host is assumed alive, because this host
    cannot check it. A label with no parseable pid is treated as gone, because
    nothing can prove it is running.
    """
    parts = holder.split(":")
    if len(parts) >= 3:
        host, pid_text = parts[-2], parts[-1]
        if host and host.lower() != socket.gethostname().lower():
            return True
    elif len(parts) == 2:
        pid_text = parts[-1]
    else:
        return False
    try:
        pid = int(pid_text)
    except ValueError:
        return False
    return pid_alive(pid)


def pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        # Never os.kill on Windows: any signal other than CTRL_* terminates.
        import ctypes
        from ctypes import wintypes
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        handle = kernel32.OpenProcess(0x1000, False, pid)  # QUERY_LIMITED_INFORMATION
        if not handle:
            return ctypes.get_last_error() == 5  # access denied: it exists
        try:
            code = wintypes.DWORD()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                return True
            return code.value == 259  # STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def row_version(family: dict[str, Any] | None) -> str:
    """Version of a ticker's tier-family row: sha256 of its canonical JSON."""
    return hashlib.sha256(json.dumps(family, sort_keys=True, default=str).encode()).hexdigest()


_DDL = """
CREATE TABLE IF NOT EXISTS journal_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS transactions (
  txn_id TEXT PRIMARY KEY,
  ticker TEXT NOT NULL,
  kind TEXT NOT NULL CHECK (kind IN ('promotion','demotion','lateral')),
  from_tier TEXT NOT NULL,
  to_tier TEXT NOT NULL,
  prior_version TEXT NOT NULL,
  forward_json TEXT NOT NULL,
  inverse_json TEXT NOT NULL,
  decision_id TEXT NOT NULL UNIQUE,
  decision_sha256 TEXT NOT NULL,
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
"""


class TierTransactionJournal:
    def __init__(self, path: Path, clock: Clock = utc_now) -> None:
        self.path = Path(path)
        self.clock = clock
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as con:
            con.executescript(_DDL)
            con.execute(
                "INSERT OR IGNORE INTO journal_meta(key, value) VALUES ('schema_version', ?)",
                (str(SCHEMA_VERSION),),
            )
            con.commit()

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        con = sqlite3.connect(str(self.path), timeout=10, isolation_level=None)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        try:
            yield con
        finally:
            con.close()

    @contextmanager
    def _write(self) -> Iterator[sqlite3.Connection]:
        with self._conn() as con:
            con.execute("BEGIN IMMEDIATE")
            try:
                yield con
            except BaseException:
                con.execute("ROLLBACK")
                raise
            con.execute("COMMIT")

    # ------------------------------------------------------------------ reads

    def get(self, txn_id: str) -> dict[str, Any] | None:
        with self._conn() as con:
            row = con.execute("SELECT * FROM transactions WHERE txn_id=?", (txn_id,)).fetchone()
        return _row(row)

    def lease(self, ticker: str) -> dict[str, Any] | None:
        with self._conn() as con:
            row = con.execute("SELECT * FROM leases WHERE ticker=?", (ticker,)).fetchone()
        return dict(row) if row else None

    def open_transactions(self) -> list[dict[str, Any]]:
        with self._conn() as con:
            rows = con.execute(
                "SELECT * FROM transactions WHERE state IN (%s) ORDER BY opened_at"
                % ",".join("?" for _ in OPEN_STATES), tuple(OPEN_STATES),
            ).fetchall()
        return [_row(r) for r in rows]

    def events(self, txn_id: str) -> list[dict[str, Any]]:
        with self._conn() as con:
            rows = con.execute("SELECT * FROM events WHERE txn_id=? ORDER BY seq", (txn_id,)).fetchall()
        return [dict(r) for r in rows]

    def latest_effective(self, ticker: str) -> dict[str, Any] | None:
        with self._conn() as con:
            row = con.execute(
                "SELECT * FROM transactions WHERE ticker=? AND state=? ORDER BY updated_at DESC LIMIT 1",
                (ticker, EFFECTIVE),
            ).fetchone()
        return _row(row)

    def effective_transactions(self) -> list[dict[str, Any]]:
        with self._conn() as con:
            rows = con.execute(
                "SELECT * FROM transactions WHERE state=? ORDER BY opened_at", (EFFECTIVE,)
            ).fetchall()
        return [_row(r) for r in rows]

    def later_transactions(self, txn: dict[str, Any]) -> list[dict[str, Any]]:
        """Effective or pending transactions on the same ticker opened after ``txn``.

        A rollback of ``txn`` would silently undo or collide with any of them.
        """
        with self._conn() as con:
            rows = con.execute(
                "SELECT * FROM transactions WHERE ticker=? AND txn_id<>? AND state IN (?,?)",
                (txn["ticker"], txn["txn_id"], EFFECTIVE, PENDING),
            ).fetchall()
        # Compare parsed times: ISO strings with and without microseconds do
        # not sort lexically.
        opened = _parse(txn["opened_at"])
        later = [_row(r) for r in rows if _parse(r["opened_at"]) >= opened]
        return sorted(later, key=lambda t: _parse(t["opened_at"]))

    # ----------------------------------------------------------------- writes

    def open(
        self,
        *,
        ticker: str,
        from_tier: str,
        to_tier: str,
        prior_family: dict[str, Any],
        forward_family: dict[str, Any],
        decision_id: str,
        decision_sha256: str,
        holder: str,
    ) -> dict[str, Any]:
        """Open a pending_coverage transaction and take the ticker lease atomically.

        Fails closed when the ticker is already leased by a live transaction or the
        owner decision was already consumed. An expired lease must be cleared by
        ``recover`` first; ``open`` never steals a lease.
        """
        ticker = ticker.upper()
        if prior_family.get("tier") != from_tier:
            raise JournalRefusal(f"prior_version_mismatch:{ticker} row tier={prior_family.get('tier')} expected={from_tier}")
        if forward_family.get("tier") != to_tier:
            raise JournalRefusal(f"forward_family_tier_mismatch:{ticker}")
        now = self.clock()
        timeout = end_of_next_market_session(now)
        kind = _kind(from_tier, to_tier)
        txn_id = "tt_%s_%s_%s" % (
            now.strftime("%Y%m%dT%H%M%S%fZ"), ticker,
            hashlib.sha256(f"{ticker}|{decision_id}|{decision_sha256}".encode()).hexdigest()[:8],
        )
        with self._write() as con:
            held = con.execute("SELECT * FROM leases WHERE ticker=?", (ticker,)).fetchone()
            if held is not None:
                raise JournalRefusal(
                    f"lease_held:{ticker} by {held['txn_id']} ({held['holder']}) until {held['expires_at']}"
                )
            used = con.execute("SELECT txn_id, state FROM transactions WHERE decision_id=?", (decision_id,)).fetchone()
            if used is not None:
                raise JournalRefusal(f"decision_already_consumed:{decision_id} by {used['txn_id']} ({used['state']})")
            con.execute(
                "INSERT INTO transactions(txn_id, ticker, kind, from_tier, to_tier, prior_version, forward_json,"
                " inverse_json, decision_id, decision_sha256, state, opened_at, timeout_at, updated_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (txn_id, ticker, kind, from_tier, to_tier, row_version(prior_family),
                 json.dumps(forward_family, sort_keys=True), json.dumps(prior_family, sort_keys=True),
                 decision_id, decision_sha256, PENDING, _iso(now), _iso(timeout), _iso(now)),
            )
            con.execute(
                "INSERT INTO leases(ticker, txn_id, holder, acquired_at, expires_at) VALUES (?,?,?,?,?)",
                (ticker, txn_id, holder, _iso(now), _iso(timeout)),
            )
            _event(con, txn_id, now, None, PENDING, {"holder": holder, "timeout_at": _iso(timeout)})
        return self.get(txn_id)

    def check_live(self, txn_id: str, current_family: dict[str, Any]) -> dict[str, Any]:
        """Idempotent pre-commit check: lease still ours, not timed out, row unchanged."""
        txn = self.get(txn_id)
        if txn is None:
            raise JournalRefusal(f"unknown_transaction:{txn_id}")
        if txn["state"] != PENDING:
            raise JournalRefusal(f"transaction_not_pending:{txn_id} state={txn['state']}")
        lease = self.lease(txn["ticker"])
        if lease is None or lease["txn_id"] != txn_id:
            raise JournalRefusal(f"lease_lost:{txn['ticker']}")
        if self.clock() >= _parse(txn["timeout_at"]):
            raise JournalRefusal(f"transaction_timed_out:{txn_id} at {txn['timeout_at']}")
        if row_version(current_family) != txn["prior_version"]:
            raise JournalRefusal(f"prior_version_mismatch:{txn['ticker']} row changed since the transaction opened")
        return txn

    def mark_effective(self, txn_id: str, commit: dict[str, Any]) -> dict[str, Any]:
        return self._move(txn_id, EFFECTIVE, {"commit": commit}, commit=commit, release=True)

    def mark_blocked(self, txn_id: str, reason: str) -> dict[str, Any]:
        return self._move(txn_id, BLOCKED, {"reason": reason}, reason=reason, release=True)

    def mark_expired(self, txn_id: str, reason: str) -> dict[str, Any]:
        return self._move(txn_id, EXPIRED, {"reason": reason}, reason=reason, release=True)

    def mark_rolled_back(self, txn_id: str, detail: dict[str, Any]) -> dict[str, Any]:
        return self._move(txn_id, ROLLED_BACK, detail, reason=detail.get("reason"), release=False)

    def _move(self, txn_id, to_state, detail, *, commit=None, reason=None, release=False):
        now = self.clock()
        with self._write() as con:
            row = con.execute("SELECT * FROM transactions WHERE txn_id=?", (txn_id,)).fetchone()
            if row is None:
                raise JournalRefusal(f"unknown_transaction:{txn_id}")
            current = row["state"]
            if current == to_state:
                return _row(row)  # idempotent repeat
            if to_state not in ALLOWED_MOVES.get(current, set()):
                raise JournalRefusal(f"illegal_transition:{txn_id} {current}->{to_state}")
            reasons = json.loads(row["reasons_json"])
            if reason:
                reasons.append(reason)
            con.execute(
                "UPDATE transactions SET state=?, updated_at=?, reasons_json=?, commit_json=COALESCE(?, commit_json)"
                " WHERE txn_id=?",
                (to_state, _iso(now), json.dumps(reasons), json.dumps(commit, sort_keys=True) if commit else None, txn_id),
            )
            if release:
                con.execute("DELETE FROM leases WHERE ticker=? AND txn_id=?", (row["ticker"], txn_id))
            _event(con, txn_id, now, current, to_state, detail)
            out = con.execute("SELECT * FROM transactions WHERE txn_id=?", (txn_id,)).fetchone()
        return _row(out)

    def recover(self, commit_probe: Callable[[dict[str, Any]], dict[str, Any] | None],
                *, after_crash: bool = False,
                rollback_probe: Callable[[dict[str, Any]], dict[str, Any] | None] | None = None,
                is_alive: Callable[[str], bool] = holder_alive) -> list[dict[str, Any]]:
        """Settle every open transaction. Safe to run at any time, any number of times.

        ``commit_probe(txn)`` returns commit evidence when the canon shows the
        transaction's effective-tier commit. The audit event alone is
        sufficient evidence (it is written atomically with the row), and a
        row that a later job changed must never be read as "no commit"
        (round-4 R4-1: that split a paired swap), else None.

        - commit present            -> effective (a crash after commit is finalized)
        - past timeout, no commit   -> expired (prior tier stays authoritative)
        - after_crash, no commit    -> blocked, but only when the holder process is
                                       gone (a live writer may still commit)
        - otherwise                 -> left pending

        ``rollback_probe(txn)`` (optional) returns evidence when the canon holds the
        inverse-rollback audit event of an effective transaction; that transaction
        is then marked rolled_back (a crash after the inverse commit is finalized).
        """
        settled = []
        now = self.clock()
        for txn in self.open_transactions():
            evidence = commit_probe(txn)
            if evidence is not None:
                settled.append(self._move(txn["txn_id"], EFFECTIVE, {"recovered": True, "commit": evidence},
                                          commit=evidence, reason="recovered_commit_present", release=True))
            elif now >= _parse(txn["timeout_at"]):
                settled.append(self.mark_expired(txn["txn_id"], "timeout_end_of_next_market_session"))
            elif after_crash:
                lease = self.lease(txn["ticker"])
                holder = lease["holder"] if lease and lease["txn_id"] == txn["txn_id"] else ""
                if holder and is_alive(holder):
                    continue
                settled.append(self.mark_blocked(txn["txn_id"], "restart_recovery_no_commit"))
        if rollback_probe is not None:
            for txn in self.effective_transactions():
                evidence = rollback_probe(txn)
                if evidence is not None:
                    settled.append(self.mark_rolled_back(
                        txn["txn_id"], {"reason": "recovered_inverse_commit_present", **evidence}))
        return settled


def _kind(frm: str, to: str) -> str:
    order = {"C": 0, "B": 1, "A": 2}
    if order[to] > order[frm]:
        return "promotion"
    if order[to] < order[frm]:
        return "demotion"
    return "lateral"


def _event(con, txn_id, now, from_state, to_state, detail) -> None:
    con.execute(
        "INSERT INTO events(txn_id, at, from_state, to_state, detail_json) VALUES (?,?,?,?,?)",
        (txn_id, _iso(now), from_state, to_state, json.dumps(detail, sort_keys=True, default=str)),
    )


def _row(row) -> dict[str, Any] | None:
    if row is None:
        return None
    out = dict(row)
    out["forward"] = json.loads(out.pop("forward_json"))
    out["inverse"] = json.loads(out.pop("inverse_json"))
    out["reasons"] = json.loads(out.pop("reasons_json"))
    raw_commit = out.pop("commit_json", None)
    out["commit"] = json.loads(raw_commit) if raw_commit else None
    return out
