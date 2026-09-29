"""Unit tests for scripts/tier_transaction_journal.py (temp files only)."""
from __future__ import annotations

import datetime as dt
import os
import socket
import subprocess
import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import tier_transaction_journal as ttj  # noqa: E402

UTC = dt.timezone.utc
NY = ttj.NY


def fam(tier: str, eligible: int | None = None) -> dict:
    eligible = (1 if tier in "AB" else 0) if eligible is None else eligible
    return {"tier": tier, "coverage_obligation_tier": tier, "sql_tier": f"Tier {tier}",
            "tier_decision_scope": f"tier_{tier.lower()}_sql_first_review_scope",
            "decision_grade_eligible": eligible}


class Clock:
    def __init__(self, start: dt.datetime):
        self.now = start

    def __call__(self):
        return self.now


def ny(y, m, d, h=10, mi=0):
    return dt.datetime(y, m, d, h, mi, tzinfo=NY).astimezone(UTC)


def journal(tmp_path, start=None):
    clock = Clock(start or ny(2026, 9, 28, 10))
    return ttj.TierTransactionJournal(tmp_path / "state/finance/tier-transactions.sqlite", clock=clock), clock


def open_one(j, ticker="XYZ", frm="C", to="B", decision="d-xyz-001", holder="w1"):
    return j.open(ticker=ticker, from_tier=frm, to_tier=to, prior_family=fam(frm),
                  forward_family=fam(to), decision_id=decision, decision_sha256="ab" * 32, holder=holder)


# --- market-session timeout ---------------------------------------------------------

@pytest.mark.parametrize("opened,expected", [
    (ny(2026, 9, 28, 10), ny(2026, 9, 29, 16)),       # Monday in session -> Tuesday close
    (ny(2026, 9, 25, 15), ny(2026, 9, 28, 16)),       # Friday -> Monday close
    (ny(2026, 9, 26, 12), ny(2026, 9, 28, 16)),       # Saturday -> Monday close
    (ny(2026, 9, 4, 12), ny(2026, 9, 8, 16)),         # Friday before Labor Day -> Tuesday
    (ny(2026, 4, 2, 12), ny(2026, 4, 6, 16)),         # Thursday before Good Friday -> Monday
    (ny(2026, 11, 25, 12), ny(2026, 11, 27, 13)),     # day before Thanksgiving -> Friday early close
    (ny(2026, 12, 23, 12), ny(2026, 12, 24, 13)),     # Christmas Eve early close
    (ny(2026, 12, 31, 12), ny(2027, 1, 4, 16)),       # New Year's Day 2027 is a Friday
    (ny(2026, 9, 28, 8), ny(2026, 9, 28, 16)),        # Monday pre-open -> Monday close
    (ny(2026, 9, 28, 9, 30), ny(2026, 9, 29, 16)),    # at the open -> next session
    (ny(2026, 9, 7, 8), ny(2026, 9, 8, 16)),          # pre-open on a holiday -> next session
])
def test_end_of_next_market_session(opened, expected):
    assert ttj.end_of_next_market_session(opened) == expected


def test_year_without_holiday_table_only_gets_earlier():
    opened = ny(2030, 12, 24, 12)  # 2030 not in the table: Christmas treated as a session
    assert ttj.end_of_next_market_session(opened) == ny(2030, 12, 25, 16)


# --- open / lease / decision consumption ---------------------------------------------

def test_open_takes_lease_and_records_inverse(tmp_path):
    j, _ = journal(tmp_path)
    txn = open_one(j)
    assert txn["state"] == ttj.PENDING
    assert txn["kind"] == "promotion"
    assert txn["inverse"] == fam("C") and txn["forward"] == fam("B")
    assert txn["prior_version"] == ttj.row_version(fam("C"))
    lease = j.lease("XYZ")
    assert lease["txn_id"] == txn["txn_id"] and lease["expires_at"] == txn["timeout_at"]


def test_second_writer_same_ticker_fails_closed(tmp_path):
    j, _ = journal(tmp_path)
    first = open_one(j)
    with pytest.raises(ttj.JournalRefusal, match="lease_held:XYZ"):
        open_one(j, decision="d-xyz-002", holder="w2")
    assert j.lease("XYZ")["txn_id"] == first["txn_id"]


def test_concurrent_open_only_one_wins(tmp_path):
    j, _ = journal(tmp_path)
    results = []

    def go(n):
        try:
            open_one(j, decision=f"d-race-{n:03d}", holder=f"w{n}")
            results.append("ok")
        except ttj.JournalRefusal as exc:
            results.append(str(exc).split(":")[0])

    threads = [threading.Thread(target=go, args=(n,)) for n in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert results.count("ok") == 1
    assert set(results) == {"ok", "lease_held"}


def test_decision_is_consumed_once_even_after_terminal(tmp_path):
    j, _ = journal(tmp_path)
    txn = open_one(j)
    j.mark_blocked(txn["txn_id"], "test")
    with pytest.raises(ttj.JournalRefusal, match="decision_already_consumed"):
        open_one(j)


def test_open_refuses_prior_version_mismatch(tmp_path):
    j, _ = journal(tmp_path)
    with pytest.raises(ttj.JournalRefusal, match="prior_version_mismatch"):
        j.open(ticker="XYZ", from_tier="C", to_tier="B", prior_family=fam("B"), forward_family=fam("B"),
               decision_id="d-xyz-001", decision_sha256="x", holder="w")
    assert j.lease("XYZ") is None


def test_different_tickers_lease_independently(tmp_path):
    j, _ = journal(tmp_path)
    open_one(j, ticker="AAA", decision="d-aaa-001")
    open_one(j, ticker="BBB", frm="B", to="C", decision="d-bbb-001")
    assert j.lease("AAA") and j.lease("BBB")


# --- check_live -------------------------------------------------------------------------

def test_check_live_passes_then_catches_row_change(tmp_path):
    j, _ = journal(tmp_path)
    txn = open_one(j)
    assert j.check_live(txn["txn_id"], fam("C"))["txn_id"] == txn["txn_id"]
    with pytest.raises(ttj.JournalRefusal, match="prior_version_mismatch"):
        j.check_live(txn["txn_id"], fam("C", eligible=1))


def test_check_live_refuses_after_timeout(tmp_path):
    j, clock = journal(tmp_path)
    txn = open_one(j)
    clock.now = ttj._parse(txn["timeout_at"])
    with pytest.raises(ttj.JournalRefusal, match="timed_out"):
        j.check_live(txn["txn_id"], fam("C"))


def test_check_live_refuses_non_pending(tmp_path):
    j, _ = journal(tmp_path)
    txn = open_one(j)
    j.mark_effective(txn["txn_id"], {"x": 1})
    with pytest.raises(ttj.JournalRefusal, match="not_pending"):
        j.check_live(txn["txn_id"], fam("C"))


# --- transitions -----------------------------------------------------------------------

def test_effective_releases_lease_and_allows_new_transaction(tmp_path):
    j, _ = journal(tmp_path)
    txn = open_one(j)
    done = j.mark_effective(txn["txn_id"], {"audit_path": "a.json"})
    assert done["state"] == ttj.EFFECTIVE and done["commit"] == {"audit_path": "a.json"}
    assert j.lease("XYZ") is None
    nxt = open_one(j, frm="B", to="C", decision="d-xyz-002")
    assert nxt["kind"] == "demotion"


@pytest.mark.parametrize("first,second", [
    ("mark_effective", "mark_blocked"),
    ("mark_blocked", "mark_effective"),
    ("mark_expired", "mark_effective"),
])
def test_illegal_transitions_refused(tmp_path, first, second):
    j, _ = journal(tmp_path)
    txn = open_one(j)
    arg = {"x": 1} if first == "mark_effective" else "r"
    getattr(j, first)(txn["txn_id"], arg)
    arg2 = {"x": 1} if second == "mark_effective" else "r"
    with pytest.raises(ttj.JournalRefusal, match="illegal_transition"):
        getattr(j, second)(txn["txn_id"], arg2)


def test_repeat_transition_is_idempotent(tmp_path):
    j, _ = journal(tmp_path)
    txn = open_one(j)
    j.mark_effective(txn["txn_id"], {"x": 1})
    again = j.mark_effective(txn["txn_id"], {"x": 2})
    assert again["commit"] == {"x": 1}
    assert [e["to_state"] for e in j.events(txn["txn_id"])] == [ttj.PENDING, ttj.EFFECTIVE]


def test_rollback_only_from_effective(tmp_path):
    j, _ = journal(tmp_path)
    txn = open_one(j)
    with pytest.raises(ttj.JournalRefusal, match="illegal_transition"):
        j.mark_rolled_back(txn["txn_id"], {"reason": "x"})
    j.mark_effective(txn["txn_id"], {"x": 1})
    assert j.mark_rolled_back(txn["txn_id"], {"reason": "x"})["state"] == ttj.ROLLED_BACK


# --- recovery ----------------------------------------------------------------------------

def test_recover_finalizes_commit_present(tmp_path):
    j, _ = journal(tmp_path)
    txn = open_one(j)
    settled = j.recover(lambda t: {"canon_audit_event_id": "e1"})
    assert [s["state"] for s in settled] == [ttj.EFFECTIVE]
    assert j.get(txn["txn_id"])["reasons"] == ["recovered_commit_present"]
    assert j.lease("XYZ") is None


def test_recover_expires_after_timeout(tmp_path):
    j, clock = journal(tmp_path)
    txn = open_one(j)
    assert j.recover(lambda t: None) == []  # inside timeout, no crash flag: left pending
    clock.now = ttj._parse(txn["timeout_at"]) + dt.timedelta(seconds=1)
    settled = j.recover(lambda t: None)
    assert settled[0]["state"] == ttj.EXPIRED
    assert settled[0]["reasons"] == ["timeout_end_of_next_market_session"]
    assert j.lease("XYZ") is None


def test_recover_after_crash_blocks_uncommitted(tmp_path):
    j, _ = journal(tmp_path)
    open_one(j)
    settled = j.recover(lambda t: None, after_crash=True)
    assert settled[0]["state"] == ttj.BLOCKED
    assert settled[0]["reasons"] == ["restart_recovery_no_commit"]


def test_recover_after_crash_leaves_live_holder_pending(tmp_path):
    # QA F6: a writer that is still running may yet commit; never block it.
    j, _ = journal(tmp_path)
    live = open_one(j, holder="tier_membership_writer:%s:%d" % (socket.gethostname(), os.getpid()))
    assert j.recover(lambda t: None, after_crash=True) == []
    assert j.get(live["txn_id"])["state"] == ttj.PENDING


def test_recover_after_crash_blocks_exited_local_holder(tmp_path):
    j, _ = journal(tmp_path)
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait()
    dead = open_one(j, holder="tier_membership_writer:%s:%d" % (socket.gethostname(), proc.pid))
    settled = j.recover(lambda t: None, after_crash=True)
    assert [(s["txn_id"], s["state"]) for s in settled] == [(dead["txn_id"], ttj.BLOCKED)]


def test_recover_after_crash_leaves_other_host_holder_pending(tmp_path):
    j, _ = journal(tmp_path)
    open_one(j, holder="tier_membership_writer:some-other-host:1234")
    assert j.recover(lambda t: None, after_crash=True) == []


def test_holder_alive_parsing():
    assert ttj.holder_alive("tier_membership_writer:%d" % os.getpid())  # legacy, no host
    assert not ttj.holder_alive("dead-writer")  # no pid: cannot be proven alive
    assert not ttj.holder_alive("tier_membership_writer:%s:0" % socket.gethostname())


def test_recover_marks_rolled_back_when_inverse_committed(tmp_path):
    # QA F7: crash between the inverse canon commit and mark_rolled_back.
    j, _ = journal(tmp_path)
    txn = open_one(j)
    j.mark_effective(txn["txn_id"], {"canon_transaction_id": "txn_x"})
    assert j.recover(lambda t: None, rollback_probe=lambda t: None) == []
    settled = j.recover(lambda t: None, rollback_probe=lambda t: {"canon_audit_event_id": "rb_1:XYZ"})
    assert [s["state"] for s in settled] == [ttj.ROLLED_BACK]
    assert j.recover(lambda t: None, rollback_probe=lambda t: {"canon_audit_event_id": "rb_1:XYZ"}) == []


def test_later_transactions_sees_newer_effective_and_pending(tmp_path):
    # QA F3: the rollback guard needs every later txn on the same ticker.
    j, clock = journal(tmp_path)
    t1 = open_one(j, decision="d-1")
    j.mark_effective(t1["txn_id"], {})
    assert j.later_transactions(j.get(t1["txn_id"])) == []
    clock.now += dt.timedelta(minutes=5)
    t2 = open_one(j, frm="B", to="C", decision="d-2")
    j.mark_effective(t2["txn_id"], {})
    clock.now += dt.timedelta(minutes=5)
    t3 = open_one(j, decision="d-3")
    later = j.later_transactions(j.get(t1["txn_id"]))
    assert [t["txn_id"] for t in later] == [t2["txn_id"], t3["txn_id"]]
    assert j.later_transactions(j.get(t3["txn_id"])) == []
    assert j.later_transactions(open_one(j, ticker="OTHER", decision="d-4")) == []


def test_recover_is_repeatable(tmp_path):
    j, _ = journal(tmp_path)
    open_one(j)
    j.recover(lambda t: None, after_crash=True)
    assert j.recover(lambda t: None, after_crash=True) == []


def test_journal_reopens_existing_file(tmp_path):
    j, clock = journal(tmp_path)
    txn = open_one(j)
    j2 = ttj.TierTransactionJournal(j.path, clock=clock)
    assert j2.get(txn["txn_id"])["state"] == ttj.PENDING
