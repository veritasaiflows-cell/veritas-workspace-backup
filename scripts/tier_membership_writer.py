#!/usr/bin/env python3
"""Activation-blocked per-name SQL tier-writer foundation (P4-2 C r3).

Validates owner-decision packet shapes and produces dry-run plans. Production
apply/rollback remain blocked until a separate exact authorization and cutover
contract exists. Transaction paths run only behind the hermetic-test gate.
--root is required in every mode.

NEVER run mutation paths against the live canon; no exact apply gate exists.
Never edits data/finance/universe-v1.json (legacy tier mirror; its sha
anchors evidence lineage). Never calls finance_sql_canon.py (its rebuild
would reset tiers from stale JSON).

WAL safety (T1): the canon runs in WAL mode, so file copies and file-sha
proofs are silently wrong (a commit can sit in -wal while the main-file
sha is unchanged; a copyfile restore then "verifies" yet changes stay
visible). Backup/restore go ONLY through the shared
scripts/sqlite_snapshot.py owner (logical_sha256 / wal_safe_backup /
wal_safe_restore). No g6.backup_db, no copyfile, no sidecar deletion,
and no file-sha proof is treated as authoritative.

Concurrency (T2): inside BEGIN IMMEDIATE the writer re-reads every
decision ticker's tier-family columns plus the A/B counts and compares
against the pre-transaction snapshot; any difference means ROLLBACK and
refusal concurrent_canon_change_detected. Every UPDATE is checked with
cur.rowcount == 1 (T5; con.total_changes is cumulative and cannot do
this).

Preconditions fail closed BEFORE backup. Post-apply guard validation
plus expected tier_breakdown; on failure our rows are put back by
compare-and-swap under the write lock (P4-3). A whole-DB restore is used
only by the hermetic-only --rollback, never on a live canon.

Exit codes: 0 ok; 2 usage or precondition refusal (nothing mutated);
4 failure with our change absent from canon (never applied, or undone by
compare-and-swap compensation; other jobs' commits are kept);
5 canon holds or may hold our change but it could not be verified,
compensated or journalled (journal left pending for --recover; owner review).

stdlib only. No network.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import socket
import sqlite3
import sys
import tempfile
from pathlib import Path

import sqlite_snapshot as snap
import tier_owner_decision as tod
import tier_transaction_journal as ttj

DECISION_SCHEMA = "veritas.tier_decision_set.v1"
AUDIT_SCHEMA = "veritas.tier_apply_audit.v1"
ROLLBACK_SCHEMA = "veritas.tier_rollback.v1"

TIER_A_CAP = 15
TIER_B_CAP = 17

ALLOWED_TRANSITIONS = {("A", "B"), ("B", "A"), ("B", "C"), ("C", "B")}

# Band-before-promotion: promoted-from-C reference raw_json must carry
# phase4_onboarding.band_packet_as_of_date within this many days of as_of
# (and not in the future).
ONBOARDING_MAX_AGE_DAYS = 14

EVENT_TYPE = "phase4_tier_transition"
ROLLBACK_EVENT_TYPE = "phase4_tier_transition_inverse"

TIER_FAMILY_COLS = ("tier", "coverage_obligation_tier", "sql_tier",
                    "tier_decision_scope", "decision_grade_eligible")

EXIT_OK = 0
EXIT_REFUSED = 2
EXIT_VERIFY_FAIL = 4
EXIT_COMMITTED_UNSETTLED = 5
ACTIVATION_BLOCK_REASON = "exact_apply_authorization_not_implemented"


class Refusal(Exception):
    """Precondition refusal: raised before any mutation."""


def contained_path(root: Path, value: str | Path, label: str,
                   base: Path, *, exact: Path | None = None) -> Path:
    """Resolve through links and require the path's canonical owner base."""
    root = root.resolve()
    raw = Path(value)
    full = (raw if raw.is_absolute() else root / raw).resolve()
    base = base.resolve()
    try:
        full.relative_to(base)
    except ValueError as exc:
        raise Refusal("%s_outside_owner_base:%s" % (label, full)) from exc
    if exact is not None and full != exact.resolve():
        raise Refusal("%s_not_exact_owner:%s" % (label, full))
    return full


def require_hermetic_test_db(db: Path) -> Path:
    """Refuse every mutation target outside an OS temp fixture root."""
    db = db.resolve()
    root = db.parents[2]
    temp_root = Path(tempfile.gettempdir()).resolve()
    try:
        root.relative_to(temp_root)
    except ValueError as exc:
        raise Refusal("mutation_target_not_under_os_temp") from exc
    if (os.environ.get("VERITAS_P42_TEST_ONLY_ACTIVATION") != "1"
            or (root / ".git").exists()
            or not (root / ".p42-hermetic-test-root").is_file()
            or db != (root / "state" / "finance" / "finance-canon.sqlite").resolve()):
        raise Refusal("mutation_target_not_hermetic_fixture")
    return root


def test_only_activation_allowed(root: Path, db: Path) -> bool:
    if os.environ.get("VERITAS_P42_TEST_ONLY_ACTIVATION") != "1":
        return False
    try:
        return require_hermetic_test_db(db) == root.resolve()
    except Refusal:
        return False


def require_mutation_target(db: Path) -> tuple[Path, str]:
    """Hermetic fixture, or the canon of a root whose cutover gate is active.

    P4-3: the production path exists but stays closed until Randall approves
    the cutover (tier_owner_decision.cutover_gate). Every mutation also needs a
    bound, unexpired, unconsumed owner decision per ticker (checked in main).
    """
    try:
        return require_hermetic_test_db(db), "hermetic_test"
    except Refusal:
        pass
    db = db.resolve()
    root = db.parents[2]
    if db != (root / "state" / "finance" / "finance-canon.sqlite").resolve():
        raise Refusal("mutation_target_not_canon")
    try:
        tod.cutover_gate(root)
    except tod.DecisionRefusal as exc:
        raise Refusal("activation_blocked:%s" % exc) from None
    return root, "production_cutover"


def mutation_allowed(root: Path, db: Path) -> tuple[bool, str]:
    try:
        target_root, context = require_mutation_target(db)
    except Refusal as exc:
        return False, str(exc)
    if target_root != root.resolve():
        return False, "mutation_target_root_mismatch"
    return True, context


def journal_for(root: Path, clock=None) -> "ttj.TierTransactionJournal":
    kwargs = {"clock": clock} if clock is not None else {}
    return ttj.TierTransactionJournal(root / ttj.JOURNAL_REL, **kwargs)


def forward_family(decision: dict, ctx: dict) -> dict:
    to_tier = decision["to_tier"]
    return {
        "tier": to_tier,
        "coverage_obligation_tier": to_tier,
        "sql_tier": "Tier %s" % to_tier,
        "tier_decision_scope": "tier_%s_sql_first_review_scope" % to_tier.lower(),
        "decision_grade_eligible": ctx["eligible_convention"][to_tier],
    }


def bind_owner_decisions(root: Path, bundle: dict, now=None) -> None:
    """Every entry must match a recorded owner decision exactly (P4-3)."""
    now = now or _dt.datetime.now(_dt.timezone.utc)
    for d in bundle["decisions"]:
        try:
            record, sha = tod.load_decision(root, d["owner_decision_id"])
            tod.bind(record, d, now)
        except tod.DecisionRefusal as exc:
            raise Refusal("owner_decision_refused:%s" % exc) from None
        d["owner_decision_sha256"] = sha


def _audit_events_matching(con, event_type: str, key: str, value: str,
                           ticker: str | None = None) -> list:
    """(event_id, detail) of audit events whose detail[key] == value EXACTLY.

    Round-5 R5-1: SQL LIKE treats '_' (present in every txn id) as a
    wildcard and folds ASCII case, so a different id could match. instr()
    is only a literal, case-sensitive prefilter; the match itself is the
    parsed-JSON equality (plus the ticker, when given).
    """
    out = []
    for event_id, detail_json in con.execute(
            "SELECT event_id, detail_json FROM audit_events WHERE event_type=? "
            "AND instr(detail_json, ?) > 0", (event_type, json.dumps(value))):
        try:
            detail = json.loads(str(detail_json))
        except ValueError:
            continue
        found = detail.get(key) if isinstance(detail, dict) else None
        # type-exact: JSON true must never equal 1, nor a number a string
        if type(found) is not type(value) or found != value:
            continue
        if ticker is not None and detail.get("ticker") != ticker:
            continue
        out.append((event_id, detail))
    return out


def canon_commit_probe(db: Path):
    """Commit evidence for journal recovery: this txn's canon audit event.

    The forward row and the audit event are written in ONE canon
    transaction, so the event alone proves the apply committed -- even when
    a later job has since changed the row (round-4 R4-1: a changed row must
    never be read as "no commit"; that expired one leg of a paired swap
    while its sibling went effective). Event absent = never committed, no
    matter what the row happens to hold. The event must name this exact
    txn id and ticker (R5-1).
    """
    def probe(txn: dict) -> dict | None:
        con = sqlite3.connect(snap._ro_uri(db), uri=True)
        try:
            events = _audit_events_matching(con, EVENT_TYPE, "journal_txn_id",
                                            txn["txn_id"], txn["ticker"])
            return {"canon_audit_event_id": events[0][0]} if events else None
        finally:
            con.close()
    return probe


def canon_rollback_probe(db: Path):
    """Evidence that an effective txn's inverse rollback committed in canon.

    The inverse audit event is written in the same canon transaction as the
    inverse row update, so its presence proves the rollback committed.
    """
    def probe(txn: dict) -> dict | None:
        con = sqlite3.connect(snap._ro_uri(db), uri=True)
        try:
            events = _audit_events_matching(con, ROLLBACK_EVENT_TYPE,
                                            "journal_txn_id", txn["txn_id"],
                                            txn["ticker"])
            if not events:
                return None
            event_id = events[0][0]
            return {"canon_audit_event_id": event_id,
                    "rollback_id": str(event_id).rsplit(":", 1)[0]}
        finally:
            con.close()
    return probe


def recover_journal(journal, db: Path, after_crash: bool = False) -> list:
    """Settle the journal while holding the canon write lock.

    A writer holds that lock from its journal check through its canon COMMIT,
    so recovery either runs entirely before it (and the writer's check then
    refuses a txn recovery expired or blocked) or entirely after it (and the
    probe sees the commit). It can never expire a txn that is mid-commit.
    Lock order is always canon, then journal.
    """
    con = sqlite3.connect(str(db), timeout=30)
    try:
        con.execute("BEGIN IMMEDIATE")
        try:
            return journal.recover(canon_commit_probe(db), after_crash=after_crash,
                                   rollback_probe=canon_rollback_probe(db))
        finally:
            _quiet_rollback(con)
    finally:
        con.close()


def _quiet_close(con: sqlite3.Connection) -> None:
    """close() after COMMIT must never turn a durable commit into a failure (R6-1)."""
    try:
        con.close()
    except Exception:
        pass


def _exact_events_present(db: Path, event_type: str, expected: dict) -> bool:
    """Whether THIS attempt's audit events are in canon (fresh read-only read).

    ``expected`` maps each exact event_id the attempt writes to the
    journal_txn_id it records. Round-7 R7-1: bound to exact ids, not a prefix
    count. event_id is the PRIMARY KEY, so no earlier row can stand in for
    ours (our INSERT would have failed before COMMIT) and no other writer
    creates these ids. True = all present, False = none present; a partial
    set or a foreign journal id is no possible outcome of one atomic COMMIT
    and raises (the caller turns that into _CommittedUnsettled).
    """
    con = sqlite3.connect(snap._ro_uri(db), uri=True)
    try:
        found = 0
        for event_id, journal_txn_id in expected.items():
            row = con.execute(
                "SELECT detail_json FROM audit_events WHERE event_id=? "
                "AND event_type=?", (event_id, event_type)).fetchone()
            if row is None:
                continue
            if json.loads(str(row[0])).get("journal_txn_id") != journal_txn_id:
                raise RuntimeError("commit_probe_foreign_event:%s" % event_id)
            found += 1
    finally:
        _quiet_close(con)
    if found and found != len(expected):
        raise RuntimeError("commit_probe_partial:%d/%d" % (found, len(expected)))
    return bool(expected) and found == len(expected)


def _commit_or_prove_aborted(con, landed) -> None:
    """COMMIT, treating a raised COMMIT as UNKNOWN until canon says otherwise.

    Round-6 R6-1: an exception from COMMIT does not prove the transaction
    aborted. Whatever is still open is rolled back, then ``landed()`` reads
    canon on a fresh connection: True means the commit is durable and the
    caller carries on as committed; False proves the abort and the original
    error is re-raised; a failed probe raises _CommittedUnsettled (exit 5).
    """
    try:
        con.commit()
    except Exception as exc:
        _quiet_rollback(con)
        try:
            did_land = landed()
        except Exception as probe_exc:
            raise _CommittedUnsettled(
                "commit_outcome_unknown:%s probe_failed:%s"
                % (exc, probe_exc)) from exc
        if not did_land:
            raise exc


def _journal_states(journal, txn_ids) -> list:
    """Sorted journal states after COMMIT; a failed or missing read is
    reported as a state, never raised (round-5 R5-3), so the caller always
    ends in _CommittedUnsettled rather than a bare exit-4 exception."""
    states = set()
    for jtxn in txn_ids:
        try:
            txn = journal.get(jtxn)
            states.add(txn["state"] if txn else "missing:%s" % jtxn)
        except Exception as exc:
            states.add("unreadable:%s:%s" % (jtxn, type(exc).__name__))
    return sorted(states)


def canon_decision_consumed(db: Path, decision_id: str) -> str | None:
    """Canon audit event that already used ``decision_id``, if any.

    One-shot consumption is recorded in the journal; this second check keeps a
    decision single-use even if the journal file is lost or restored from an
    older copy.
    """
    con = sqlite3.connect(snap._ro_uri(db), uri=True)
    try:
        events = _audit_events_matching(con, EVENT_TYPE, "owner_decision_id",
                                        decision_id)
        return str(events[0][0]) if events else None
    finally:
        con.close()


def writer_holder() -> str:
    return "tier_membership_writer:%s:%d" % (socket.gethostname(), os.getpid())


def _logical_sha256_conn(con: sqlite3.Connection) -> str:
    """snap.logical_sha256 computed on an open connection (inside its lock)."""
    h = hashlib.sha256()
    for line in con.iterdump():
        h.update(line.encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()


def _locked_logical_restore(con: sqlite3.Connection, backup: Path,
                            expected_logical_sha256: str) -> str:
    """Whole-content restore of main from ``backup`` inside the caller's
    BEGIN IMMEDIATE (round-4 R4-3).

    ``snap.wal_safe_restore`` cannot run while the canon write lock is held
    (its destination must not be in a transaction), so the restore is
    replayed logically: every user object in main is dropped and rebuilt
    from the backup's own dump, in this one transaction. The transaction
    commits only when the replayed content hashes exactly to
    ``expected_logical_sha256``; otherwise it rolls back and canon is
    untouched. Never copyfile, never unlink sidecars (T1).

    Known fail-closed limit (round-6 on R5-2): SQLite cannot drop
    sqlite_sequence, so a live DB that has one cannot be made to match a
    backup that lacks one; the hash check refuses and nothing changes. The
    caller cannot reach that case: it requires live == recorded after-hash,
    and an apply creates no AUTOINCREMENT table, so both sides agree.
    """
    if snap.logical_sha256(backup) != expected_logical_sha256:
        raise ValueError("restore refused: backup logical hash != recorded")
    src = sqlite3.connect(snap._ro_uri(backup), uri=True)
    try:
        # The dump already carries sqlite_sequence (DELETE + INSERTs); replaying
        # it a second time duplicated rows and failed every restore (R5-2).
        dump = list(src.iterdump())
    finally:
        src.close()
    for typ, name in reversed(con.execute(
            "SELECT type, name FROM sqlite_master "
            "WHERE name NOT LIKE 'sqlite_%'").fetchall()):
        con.execute('DROP %s IF EXISTS "%s"'
                    % (typ.upper(), str(name).replace('"', '""')))
    for stmt in dump:
        head = stmt.lstrip().upper()
        if head.startswith(("BEGIN", "COMMIT", "PRAGMA")):
            continue
        con.execute(stmt)
    after = _logical_sha256_conn(con)
    if after != expected_logical_sha256:
        raise ValueError("restore FAILED: live logical hash != backup logical hash")
    return after



# --------------------------------------------------------------------------
# staged imports (bound to --root at runtime)
# --------------------------------------------------------------------------

_staged: dict = {}


def staged_modules(root: Path) -> dict:
    """Import fsca + provider policy + g6 path-refusal from <root>/scripts.

    Only g6.refuse_markdown_path is reused (pure path check). Backup and
    restore NEVER use g6 (see module docstring).
    """
    key = root.as_posix()
    if key in _staged:
        return _staged[key]
    # Per-root fresh exec: pop plain names from sys.modules first, or a
    # second root in the same process would inherit the first root's
    # already-imported modules (whose internal ROOT points elsewhere).
    # _staged keeps the per-root refs; our code only uses those.
    names = ("alerts_os_sql_retirement_policy", "market_data_utils",
             "dynamic_entitlement_provider_policy",
             "finance_sql_canon_access", "g6_yahoo32_sql_apply")
    scripts = (root / "scripts").as_posix()
    sys.path.insert(0, scripts)
    try:
        for name in names:
            sys.modules.pop(name, None)
        import finance_sql_canon_access as fsca  # type: ignore
        import dynamic_entitlement_provider_policy as depp  # type: ignore
        import g6_yahoo32_sql_apply as g6  # type: ignore
    finally:
        try:
            sys.path.remove(scripts)
        except ValueError:
            pass
    _staged[key] = {"fsca": fsca, "depp": depp, "g6": g6}
    return _staged[key]


# --------------------------------------------------------------------------
# decision file
# --------------------------------------------------------------------------

def _parse_iso(value) -> _dt.datetime | None:
    try:
        return _dt.datetime.fromisoformat(str(value))
    except ValueError:
        return None


def load_decisions(path: Path) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError) as exc:
        raise Refusal("decision_file_unreadable:%s" % (exc,))
    if not isinstance(doc, dict) or doc.get("schema") != DECISION_SCHEMA:
        raise Refusal("decision_file_schema_invalid: need %s"
                      % DECISION_SCHEMA)
    as_of = doc.get("as_of")
    try:
        as_of_d = _dt.date.fromisoformat(str(as_of))
    except ValueError:
        raise Refusal("decision_file_as_of_invalid:%s" % (as_of,))
    decisions = doc.get("decisions")
    if not isinstance(decisions, list) or not decisions:
        raise Refusal("decision_file_empty: no decisions")
    seen: set[str] = set()
    clean: list[dict] = []
    for i, d in enumerate(decisions):
        if not isinstance(d, dict):
            raise Refusal("decision_entry_not_object:index=%d" % i)
        ticker = str(d.get("ticker") or "").upper()
        frm = str(d.get("from_tier") or "").upper()
        to = str(d.get("to_tier") or "").upper()
        if not ticker:
            raise Refusal("decision_entry_missing_ticker:index=%d" % i)
        if ticker in seen:
            raise Refusal("duplicate_ticker:%s" % ticker)
        seen.add(ticker)
        if d.get("decision") != "approved":
            raise Refusal("unapproved_entry:%s decision=%s"
                          % (ticker, d.get("decision")))
        if not str(d.get("approval_reference") or "").strip():
            raise Refusal("missing_approval_reference:%s" % ticker)
        if not str(d.get("card_id") or "").strip():
            raise Refusal("missing_card_id:%s" % ticker)
        packet_sha = str(d.get("proposal_packet_sha256") or "").strip()
        if (len(packet_sha) != 64
                or any(ch not in "0123456789abcdefABCDEF"
                       for ch in packet_sha)):
            raise Refusal("missing_or_invalid_proposal_packet_sha256:%s"
                          % ticker)
        # T7: owner acceptance timestamp is mandatory.
        accepted_at = str(d.get("accepted_at") or "").strip()
        if not accepted_at or _parse_iso(accepted_at) is None:
            raise Refusal("missing_or_invalid_accepted_at:%s "
                          "(ISO-8601 required)" % ticker)
        if (frm, to) not in ALLOWED_TRANSITIONS:
            raise Refusal("transition_not_allowed:%s %s->%s "
                          "(only A<->B and B<->C; no C->A jump)" % (
                              ticker, frm, to))
        # P4-3: each entry names the recorded owner decision it executes.
        owner_decision_id = str(d.get("owner_decision_id") or "").strip()
        if not owner_decision_id:
            raise Refusal("missing_owner_decision_id:%s" % ticker)
        clean.append({
            "owner_decision_id": owner_decision_id,
            "ticker": ticker, "from_tier": frm, "to_tier": to,
            "decision": "approved",
            "approval_reference": str(d["approval_reference"]).strip(),
            "accepted_at": accepted_at,
            "card_id": str(d.get("card_id") or ""),
            "proposal_packet_sha256": packet_sha.lower(),
        })
    return {"as_of": str(as_of), "as_of_date": as_of_d,
            "decisions": clean}


def verify_proposal_packet(bundle: dict, packet_path: Path | None) -> None:
    """Bind every decision to one exact, promotion-ready packet card."""
    shas = {d["proposal_packet_sha256"] for d in bundle["decisions"]}
    if len(shas) != 1:
        raise Refusal("proposal_packet_sha_inconsistent_across_decisions")
    if packet_path is None:
        raise Refusal("proposal_packet_required")
    try:
        raw = packet_path.read_bytes()
        doc = json.loads(raw.decode("utf-8"))
    except (OSError, ValueError) as exc:
        raise Refusal("proposal_packet_unreadable:%s" % (exc,))
    actual = hashlib.sha256(raw).hexdigest()
    expected = next(iter(shas))
    if actual != expected:
        raise Refusal("proposal_packet_sha_mismatch: expected=%s actual=%s"
                      % (expected, actual))

    cards: dict[str, dict] = {}

    def walk(node):
        if isinstance(node, dict):
            card_id = node.get("card_id")
            if isinstance(card_id, str) and card_id:
                if card_id in cards:
                    raise Refusal("duplicate_card_id_in_packet:%s" % card_id)
                cards[card_id] = node
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(doc)
    required_ready_proofs = (
        "identity_listing_resolution",
        "thesis_lineage_risks_macro_catalysts",
        "evidence_recency",
        "quote_session_eligibility",
        "duplicate_surface_census",
    )
    for decision in bundle["decisions"]:
        card = cards.get(decision["card_id"])
        if card is None:
            raise Refusal("card_id_not_in_packet:%s card=%s" % (
                decision["ticker"], decision["card_id"]))
        if str(card.get("ticker") or "").upper() != decision["ticker"]:
            raise Refusal("packet_card_ticker_mismatch:%s" % decision["ticker"])
        if str(card.get("prior_tier") or "").upper() != decision["from_tier"]:
            raise Refusal("packet_card_prior_tier_mismatch:%s"
                          % decision["ticker"])
        proposed = card.get("proposed_tier")
        if proposed is None:
            proposed = (card.get("b_to_a_case") or {}).get("to_tier")
        if str(proposed or "").upper() != decision["to_tier"]:
            raise Refusal("packet_card_proposed_tier_mismatch:%s"
                          % decision["ticker"])
        proofs = card.get("proofs") or {}
        for proof_name in required_ready_proofs:
            if (proofs.get(proof_name) or {}).get("status") != "satisfied":
                raise Refusal("packet_card_proof_not_satisfied:%s:%s" % (
                    decision["ticker"], proof_name))
        if decision["from_tier"] == "C" and card.get("status") != (
                "promotion_candidate:capacity_check"):
            raise Refusal("packet_card_not_promotion_ready:%s"
                          % decision["ticker"])
        if decision["to_tier"] == "A" and not (
                card.get("b_to_a_case") or {}).get("credible"):
            raise Refusal("packet_card_not_advancement_ready:%s"
                          % decision["ticker"])
        if (decision["to_tier"] in ("B", "C")
                and decision["from_tier"] in ("A", "B")
                and card.get("role") != "demotion_proposed"):
            raise Refusal("packet_card_not_demotion_ready:%s"
                          % decision["ticker"])


# --------------------------------------------------------------------------
# preconditions (all before backup)
# --------------------------------------------------------------------------

def check_preconditions(root: Path, db: Path, bundle: dict,
                        mods: dict) -> dict:
    """Fail closed. Returns context for apply on success."""
    fsca, depp = mods["fsca"], mods["depp"]
    access = fsca.FinanceSqlCanonAccess(db)
    try:
        validation = access.validate()
    except Exception as exc:
        raise Refusal("canon_guard_raised:%s" % (exc,))
    if validation.get("status") != "ok":
        raise Refusal("canon_guard_not_ok:%s" % (validation.get("errors"),))
    try:
        policy = depp.load_provider_policy(root)
    except Exception as exc:
        raise Refusal("provider_policy_unloadable:%s" % (exc,))
    try:
        scope = access.dynamic_entitlement_scope()
        members = access.universe_memberships()
        ref_records = access.reference_level_records()
    except Exception as exc:
        raise Refusal("guarded_read_failed:%s" % (exc,))

    decisions = bundle["decisions"]
    # expected-prior check: current tier == from_tier
    for d in decisions:
        row = members.get(d["ticker"])
        if row is None:
            raise Refusal("prior_tier_unknown:%s not in guarded SQL"
                          % d["ticker"])
        if row.tier != d["from_tier"]:
            raise Refusal("prior_tier_mismatch:%s current=%s expected=%s"
                          % (d["ticker"], row.tier, d["from_tier"]))

    # post-state caps
    counts = {"A": 0, "B": 0, "C": 0}
    for t, row in members.items():
        if row.tier in counts:
            counts[row.tier] += 1
    for d in decisions:
        counts[d["from_tier"]] -= 1
        counts[d["to_tier"]] += 1
    post_a, post_b = counts["A"], counts["B"]
    if post_a > TIER_A_CAP:
        raise Refusal("cap_breach:Tier A post=%d cap=%d; promotion needs "
                      "a paired demotion" % (post_a, TIER_A_CAP))
    if post_b > TIER_B_CAP:
        raise Refusal("cap_breach:Tier B post=%d cap=%d; promotion needs "
                      "a paired demotion" % (post_b, TIER_B_CAP))
    if post_a + post_b > policy.max_scope_count:
        raise Refusal("cap_breach:evaluated post=%d cap=%d"
                      % (post_a + post_b, policy.max_scope_count))

    # T3: band-before-promotion reads the live row. Every ticker ending in
    # A/B needs reference + freshness rows; promoted-from-C needs a fresh
    # onboarded band (phase4_onboarding within 14 days, not future) and
    # non-null reference_confidence.
    ending_ab = {d["ticker"] for d in decisions if d["to_tier"] in ("A", "B")}
    for t in sorted(ending_ab):
        rec = ref_records.get(t)
        if rec is None:
            raise Refusal("bandless_destination:%s has no reference_levels "
                          "row; onboard a band first" % t)
        try:
            fresh = access.evidence_freshness(t)
        except Exception as exc:
            raise Refusal("freshness_read_failed:%s:%s" % (t, exc))
        if fresh is None:
            raise Refusal("freshness_row_missing:%s has no "
                          "evidence_freshness row" % t)
    for d in decisions:
        if d["from_tier"] == "C":
            rec = ref_records.get(d["ticker"])
            raw = (rec.raw_json or {}) if rec else {}
            ob = raw.get("phase4_onboarding")
            if not isinstance(ob, dict):
                raise Refusal(
                    "band_before_promotion_missing:%s reference row has no "
                    "phase4_onboarding block" % d["ticker"])
            pkt = ob.get("band_packet_as_of_date")
            try:
                pkt_d = _dt.date.fromisoformat(str(pkt)[:10])
            except (ValueError, TypeError):
                pkt_d = None
            age = ((bundle["as_of_date"] - pkt_d).days
                   if pkt_d else None)
            if age is None or not 0 <= age <= ONBOARDING_MAX_AGE_DAYS:
                raise Refusal(
                    "stale_band_promotion_refused:%s packet date=%s age=%s "
                    "(need 0..%d days, not future)" % (
                        d["ticker"], pkt, age, ONBOARDING_MAX_AGE_DAYS))
            if rec.reference_confidence is None:
                raise Refusal(
                    "null_confidence_promotion_refused:%s" % d["ticker"])

    # decision_grade_eligible convention follows the current rows:
    # A/B rows carry 1, C rows carry 0.
    convention: dict[str, int] = {}
    for tier in ("A", "B", "C"):
        vals = {int(members[t].decision_grade_eligible)
                for t in members if members[t].tier == tier}
        if len(vals) == 1:
            convention[tier] = vals.pop()
        else:
            convention[tier] = 1 if tier in ("A", "B") else 0

    return {
        "validation": validation,
        "scope_before": scope,
        "members": members,
        "post_counts": {"A": post_a, "B": post_b, "C": counts["C"]},
        "max_scope": policy.max_scope_count,
        "eligible_convention": convention,
    }


def scan_forbidden(text: str, mods: dict, what: str) -> None:
    low = text.lower()
    for token in mods["fsca"].FORBIDDEN_CURRENT_TEXT:
        if token in low:
            raise Refusal("forbidden_text:%s contains %s" % (what, token))


# --------------------------------------------------------------------------
# apply: ONE transaction, T2 re-read, T5 rowcount, WAL-safe backup/restore
# --------------------------------------------------------------------------

def _utc_stamp() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _snapshot_from_conn(con: sqlite3.Connection, db: Path,
                        tickers: list[str]) -> dict:
    """Snapshot every membership plus decision-band/evidence gate inputs."""
    con.row_factory = sqlite3.Row
    families = {}
    band_inputs = {}
    for ticker in tickers:
        row = con.execute(
            "SELECT %s FROM universe_membership WHERE ticker=?"
            % ", ".join(TIER_FAMILY_COLS), (ticker,)
        ).fetchone()
        families[ticker] = dict(row) if row else None
        ref = con.execute(
            "SELECT * FROM reference_levels WHERE ticker=?", (ticker,)
        ).fetchone()
        evidence = con.execute(
            "SELECT * FROM evidence_freshness WHERE ticker=?", (ticker,)
        ).fetchone()
        lineage = con.execute(
            "SELECT * FROM source_lineage WHERE scope_key=? "
            "ORDER BY lineage_id", (ticker,)
        ).fetchall()
        band_inputs[ticker] = {
            "reference": tuple(ref) if ref else None,
            "evidence": tuple(evidence) if evidence else None,
            "lineage": [tuple(item) for item in lineage],
        }
    all_memberships = [tuple(row) for row in con.execute(
        "SELECT %s FROM universe_membership ORDER BY ticker"
        % ", ".join(("ticker",) + TIER_FAMILY_COLS)
    ).fetchall()]
    baseline_meta = con.execute(
        "SELECT value FROM finance_state_meta "
        "WHERE key='alerts_os_reference_baseline_v1'"
    ).fetchone()
    policy = db.parents[2] / "state" / "dynamic-entitlement-provider-policy.json"
    policy_sha = (hashlib.sha256(policy.read_bytes()).hexdigest()
                  if policy.is_file() else None)
    counts = dict(con.execute(
        "SELECT tier, COUNT(*) FROM universe_membership WHERE tier IN "
        "('A','B') GROUP BY tier").fetchall())
    return {
        "families": families,
        "all_memberships": all_memberships,
        "band_inputs": band_inputs,
        "baseline_meta": str(baseline_meta[0]) if baseline_meta else None,
        "provider_policy_sha256": policy_sha,
        "count_a": int(counts.get("A", 0)),
        "count_b": int(counts.get("B", 0)),
    }


def snapshot_rows(db: Path, tickers: list[str]) -> dict:
    """Pre-transaction snapshot compared under BEGIN IMMEDIATE."""
    con = sqlite3.connect(str(db))
    try:
        return _snapshot_from_conn(con, db, tickers)
    finally:
        con.close()


def _reread_families(con, db: Path, tickers: list[str]) -> dict:
    return _snapshot_from_conn(con, db, tickers)


def _decision_digest(d: dict) -> str:
    """Canonical digest of one decision record, as written to the rollback file."""
    return hashlib.sha256(json.dumps(d, sort_keys=True, separators=(",", ":"))
                          .encode("utf-8")).hexdigest()


def _execute_updates(con, bundle: dict, ctx: dict, txn_id: str, now: str,
                     _fault_after_first: bool = False,
                     journal_txns: dict | None = None,
                     binding: dict | None = None) -> int:
    """Run the UPDATE+INSERT statements on an open write transaction.
    T5: every UPDATE must affect exactly one row (cur.rowcount; the
    cumulative con.total_changes cannot detect a zero-row UPDATE).

    Round 10: each audit event also records the decision's digest and, when
    ``binding`` is given, the backup and at-lock logical hashes, atomically
    with the apply, so a later rollback file is authenticated by canon."""
    n = 0
    journal_txns = journal_txns or {}
    for i, d in enumerate(bundle["decisions"]):
        to = d["to_tier"]
        cur = con.execute(
            "UPDATE universe_membership SET tier=?, "
            "coverage_obligation_tier=?, sql_tier=?, "
            "tier_decision_scope=?, decision_grade_eligible=? "
            "WHERE ticker=?",
            (to, to, "Tier %s" % to,
             "tier_%s_sql_first_review_scope" % to.lower(),
             ctx["eligible_convention"][to], d["ticker"]))
        if cur.rowcount != 1:
            raise RuntimeError("update_affected_%d_rows:%s"
                               % (cur.rowcount, d["ticker"]))
        detail = {"ticker": d["ticker"], "from": d["from_tier"],
                  "to": d["to_tier"],
                  "approval_reference": d["approval_reference"],
                  "accepted_at": d["accepted_at"],
                  "card_id": d["card_id"],
                  "proposal_packet_sha256": d["proposal_packet_sha256"],
                  "owner_decision_id": d.get("owner_decision_id"),
                  "owner_decision_sha256": d.get("owner_decision_sha256"),
                  "journal_txn_id": journal_txns.get(d["ticker"]),
                  "transaction_id": txn_id,
                  "decision_sha256": _decision_digest(d)}
        detail.update(binding or {})
        con.execute(
            "INSERT INTO audit_events(event_id, event_time_utc, "
            "event_type, detail_json) VALUES (?, ?, ?, ?)",
            ("%s:%s" % (txn_id, d["ticker"]), now, EVENT_TYPE,
             json.dumps(detail, sort_keys=True)))
        n += 1
        if _fault_after_first and i == 0:
            raise RuntimeError("injected_fault_after_first_update")
    return n


def apply_transaction(db: Path, bundle: dict, ctx: dict, txn_id: str,
                      pre_snapshot: dict,
                      _fault_after_first: bool = False,
                      _skip_concurrency_check: bool = False,
                      journal=None, journal_txns: dict | None = None,
                      result: dict | None = None,
                      backup_logical_sha256: str | None = None) -> int:
    """Single BEGIN IMMEDIATE transaction on a permitted mutation target.

    T2 re-reads tier families and A/B counts BEFORE writing; any difference
    from the pre-transaction snapshot means ROLLBACK + Refusal. P4-3: under the
    same write lock every journal transaction must still hold its lease, be
    inside its timeout and see an unchanged prior row version. When ``result``
    is given, the logical hashes at lock time and just before COMMIT are
    taken on the locked connection, so no other commit can fall between them
    and our write.

    _fault_after_first / _skip_concurrency_check are test-only hooks
    (never CLI): the first raises mid-transaction to prove atomicity;
    the second isolates the T5 rowcount check from the T2 re-read.
    """
    require_mutation_target(db)
    now = _dt.datetime.now(_dt.timezone.utc).isoformat()
    con = sqlite3.connect(str(db))
    con.row_factory = sqlite3.Row
    try:
        con.execute("BEGIN IMMEDIATE")
        if result is not None:
            result["logical_at_lock"] = _logical_sha256_conn(con)
        tickers = [d["ticker"] for d in bundle["decisions"]]
        live = None
        if not _skip_concurrency_check:
            live = _reread_families(con, db, tickers)
            if live != pre_snapshot:
                try:
                    con.rollback()
                except Exception:
                    pass
                raise Refusal(
                    "concurrent_canon_change_detected: membership, band, "
                    "evidence, lineage, baseline, or provider policy changed "
                    "between snapshot and transaction")
        if journal is not None:
            families = (live or _reread_families(con, db, tickers))["families"]
            for ticker, jtxn in (journal_txns or {}).items():
                try:
                    journal.check_live(jtxn, families[ticker])
                except ttj.JournalRefusal as exc:
                    try:
                        con.rollback()
                    except Exception:
                        pass
                    raise Refusal("journal_check_failed:%s" % exc) from None
        binding = None
        if result is not None and backup_logical_sha256 is not None:
            binding = {"backup_logical_sha256": backup_logical_sha256,
                       "db_logical_sha256_at_lock": result["logical_at_lock"]}
        n = _execute_updates(con, bundle, ctx, txn_id, now,
                             _fault_after_first=_fault_after_first,
                             journal_txns=journal_txns, binding=binding)
        if result is not None:
            result["logical_after"] = _logical_sha256_conn(con)
        ours = {"%s:%s" % (txn_id, d["ticker"]): (journal_txns or {}).get(d["ticker"])
                for d in bundle["decisions"]}
        _commit_or_prove_aborted(
            con, lambda: _exact_events_present(db, EVENT_TYPE, ours))
        return n
    except (Refusal, _CommittedUnsettled):
        raise
    except Exception:
        try:
            con.rollback()
        except Exception:
            pass
        raise
    finally:
        _quiet_close(con)


def verify_post_state(mods: dict, db: Path, post_counts: dict,
                      bundle: dict, ctx: dict, txn_id: str,
                      journal_txns: dict | None = None) -> dict:
    fsca = mods["fsca"]
    access = fsca.FinanceSqlCanonAccess(db)
    validation = access.validate()
    if validation.get("status") != "ok":
        raise RuntimeError("post_apply_guard_not_ok:%s" % (
            validation.get("errors"),))
    scope = access.dynamic_entitlement_scope()
    expected = {"A": post_counts["A"], "B": post_counts["B"]}
    if dict(scope.tier_breakdown) != expected:
        raise RuntimeError("post_apply_breakdown_mismatch:%s != %s" % (
            scope.tier_breakdown, expected))
    con = sqlite3.connect(str(db))
    con.row_factory = sqlite3.Row
    try:
        for decision in bundle["decisions"]:
            row = con.execute(
                "SELECT %s FROM universe_membership WHERE ticker=?"
                % ", ".join(TIER_FAMILY_COLS),
                (decision["ticker"],),
            ).fetchone()
            to_tier = decision["to_tier"]
            expected_row = {
                "tier": to_tier,
                "coverage_obligation_tier": to_tier,
                "sql_tier": "Tier %s" % to_tier,
                "tier_decision_scope": (
                    "tier_%s_sql_first_review_scope" % to_tier.lower()),
                "decision_grade_eligible": ctx["eligible_convention"][to_tier],
            }
            if row is None or dict(row) != expected_row:
                raise RuntimeError(
                    "post_apply_row_mismatch:%s:%s" % (
                        decision["ticker"], dict(row) if row else None))
            event = con.execute(
                "SELECT detail_json FROM audit_events WHERE event_id=? "
                "AND event_type=?",
                ("%s:%s" % (txn_id, decision["ticker"]), EVENT_TYPE),
            ).fetchone()
            if event is None:
                raise RuntimeError(
                    "post_apply_audit_event_missing:%s" % decision["ticker"])
            detail = json.loads(str(event[0]))
            for key, expected_value in (
                ("ticker", decision["ticker"]),
                ("from", decision["from_tier"]),
                ("to", decision["to_tier"]),
                ("approval_reference", decision["approval_reference"]),
                ("accepted_at", decision["accepted_at"]),
                ("card_id", decision["card_id"]),
                ("proposal_packet_sha256",
                 decision["proposal_packet_sha256"]),
                ("transaction_id", txn_id),
                ("journal_txn_id", (journal_txns or {}).get(decision["ticker"])),
            ):
                if detail.get(key) != expected_value:
                    raise RuntimeError(
                        "post_apply_audit_event_mismatch:%s:%s" % (
                            decision["ticker"], key))
        prefix = txn_id + ":"
        event_count = int(con.execute(
            "SELECT COUNT(*) FROM audit_events WHERE event_type=? "
            "AND substr(event_id, 1, ?) = ?",
            (EVENT_TYPE, len(prefix), prefix),
        ).fetchone()[0])
        if event_count != len(bundle["decisions"]):
            raise RuntimeError(
                "post_apply_audit_event_count_mismatch:%d" % event_count)
    finally:
        con.close()
    return {"fingerprint": scope.fingerprint,
            "tier_breakdown": dict(scope.tier_breakdown)}


class _CanonUnchanged(Exception):
    """Wraps a failure after which our change is provably absent from canon."""


class _CommittedUnsettled(RuntimeError):
    """Canon holds (or may hold) our commit, but it could not be verified,
    compensated or journalled. The journal is left for recovery (exit 5)."""


class _SimulatedCrash(BaseException):
    """Test-only: process death after commit (not caught by except Exception)."""


def do_apply(root: Path, db: Path, bundle: dict, ctx: dict, mods: dict,
             backup_path: Path, audit_path: Path, rollback_path: Path,
             output_dir: Path,
             _fault_after_first: bool = False,
             _force_verify_fail: bool = False,
             _skip_concurrency_check: bool = False,
             _journal_clock=None,
             _crash_after_commit: bool = False) -> dict:
    """Journal-wrapped apply (P4-3).

    Order: owner-decision binding and the canon single-use check; path
    preflight and WAL-safe backup (a failure here consumes nothing); journal
    recovery; one pending_coverage transaction (lease + timeout) per ticker,
    which consumes the owner decisions; the canon transaction; verification;
    mark effective.

    A refusal, or a failure after which our change was compensated out of
    canon, marks the txns blocked. A failure whose canon state is unknown
    leaves them pending for recovery and raises _CommittedUnsettled.
    ``_crash_after_commit`` (test-only) simulates a process death right after
    the canon commit.
    """
    _, activation_context = require_mutation_target(db)
    # Binding is enforced here, not only in main(): every caller must present
    # decisions that match their recorded owner decisions exactly.
    bind_owner_decisions(root, bundle)
    for d in bundle["decisions"]:
        used = canon_decision_consumed(db, d["owner_decision_id"])
        if used is not None:
            raise Refusal("decision_already_consumed_in_canon:%s by %s"
                          % (d["owner_decision_id"], used))
    # Preflight before the journal: an operator path error or a failed backup
    # must not consume the owner decisions.
    try:
        paths, pre_snapshot, backup_info = _preflight_and_backup(
            root, db, bundle, mods, backup_path, audit_path, rollback_path,
            output_dir)
    except Refusal:
        raise
    except Exception as exc:
        raise RuntimeError("preflight_failed_canon_unchanged:%s" % exc) from exc
    journal = journal_for(root, _journal_clock)
    recover_journal(journal, db)
    pre_families = pre_snapshot["families"]
    journal_txns: dict[str, str] = {}
    try:
        for d in bundle["decisions"]:
            opened = journal.open(
                ticker=d["ticker"], from_tier=d["from_tier"], to_tier=d["to_tier"],
                prior_family=pre_families[d["ticker"]] or {},
                forward_family=forward_family(d, ctx),
                decision_id=d["owner_decision_id"],
                decision_sha256=d["owner_decision_sha256"],
                holder=writer_holder())
            journal_txns[d["ticker"]] = opened["txn_id"]
    except Exception as exc:
        for jtxn in journal_txns.values():
            journal.mark_blocked(jtxn, "sibling_open_refused:%s" % exc)
        if isinstance(exc, ttj.JournalRefusal):
            raise Refusal("journal_open_refused:%s" % exc) from None
        raise

    def settle_without_change(reason: str) -> None:
        # Compensation only runs while every txn is still pending (checked
        # under the canon lock), so pending -> blocked is the only move. A
        # crash before this point leaves pending txns whose canon shows no
        # commit; recovery then blocks or expires them.
        for jtxn in journal_txns.values():
            if journal.get(jtxn)["state"] == ttj.PENDING:
                journal.mark_blocked(jtxn, reason)

    try:
        audit = _commit_and_verify(
            root, db, bundle, ctx, mods, paths, journal, journal_txns,
            activation_context, pre_snapshot, backup_info,
            _fault_after_first=_fault_after_first,
            _force_verify_fail=_force_verify_fail,
            _skip_concurrency_check=_skip_concurrency_check,
            _crash_after_commit=_crash_after_commit)
    except Refusal as exc:
        settle_without_change("refused:%s" % exc)
        raise
    except _CanonUnchanged as exc:
        settle_without_change("failed_canon_unchanged:%s" % exc.__cause__)
        raise RuntimeError(str(exc.__cause__)) from exc.__cause__
    try:
        commit = {"audit_path": audit.get("audit_path"),
                  "canon_transaction_id": audit["transaction_id"],
                  "db_logical_sha256_after": audit["db_logical_sha256_after"]}
        for jtxn in journal_txns.values():
            journal.mark_effective(jtxn, commit)
    except Exception as exc:
        # Canon holds the verified commit; recovery settles from evidence.
        try:
            recover_journal(journal, db)
        except Exception:
            pass
        states = _journal_states(journal, journal_txns.values())
        if states != [ttj.EFFECTIVE]:
            raise _CommittedUnsettled(
                "committed_journal_unsettled:%s states=%s" % (exc, states)
            ) from exc
    audit["journal_txn_ids"] = journal_txns
    return audit


def _commit_and_verify(root: Path, db: Path, bundle: dict, ctx: dict,
                       mods: dict, paths: tuple, journal, journal_txns: dict,
                       activation_context: str, pre_snapshot: dict,
                       backup_info: dict,
                       _fault_after_first: bool = False,
                       _force_verify_fail: bool = False,
                       _skip_concurrency_check: bool = False,
                       _crash_after_commit: bool = False) -> dict:
    backup_path, audit_path, rollback_path = paths
    logical_before = backup_info["logical_sha256_before"]
    txn_id = "txn_%s_%s" % (_utc_stamp(),
                            hashlib.sha256(json.dumps(
                                bundle["decisions"],
                                sort_keys=True).encode()).hexdigest()[:8])
    locked: dict = {}
    try:
        audit_rows = apply_transaction(
            db, bundle, ctx, txn_id, pre_snapshot,
            _fault_after_first=_fault_after_first,
            _skip_concurrency_check=_skip_concurrency_check,
            journal=journal, journal_txns=journal_txns, result=locked,
            backup_logical_sha256=backup_info["logical_sha256_backup"])
    except (Refusal, _CommittedUnsettled):
        raise
    except Exception as exc:
        # apply_transaction rolled back (a raised COMMIT is re-raised only
        # once canon proves it aborted): canon is at its prior state.
        raise _CanonUnchanged() from exc
    if _crash_after_commit:
        raise _SimulatedCrash("test-only crash after canon commit")

    def undo(reason: BaseException, label: str) -> None:
        _compensate_apply(db, bundle, ctx, txn_id, pre_snapshot["families"],
                          reason, journal, journal_txns)
        raise _CanonUnchanged() from RuntimeError("%s:%s" % (label, reason))

    # Every failure after COMMIT ends compensated (_CanonUnchanged) or
    # explicitly unsettled (_CommittedUnsettled), never as a bare exception.
    try:
        # Round-4 NEW-4 residual: even reading the post-COMMIT result keys
        # stays inside the guarded region, so no failure after COMMIT can
        # escape without compensation.
        logical_after = locked["logical_after"]
        backup_matches_lock_state = locked["logical_at_lock"] == logical_before
        try:
            if _force_verify_fail:
                raise RuntimeError("injected_verify_failure")
            post = verify_post_state(
                mods, db, ctx["post_counts"], bundle, ctx, txn_id,
                journal_txns=journal_txns)
        except Exception as exc:
            undo(exc, "post_apply_failed_restored")
        audit = {
            "schema": AUDIT_SCHEMA,
            "transaction_id": txn_id,
            "as_of": bundle["as_of"],
            "decisions": bundle["decisions"],
            "post_counts": ctx["post_counts"],
            "audit_rows_inserted": audit_rows,
            "backup_path": backup_info["backup_path"],
            "backup_logical_sha256": backup_info["logical_sha256_backup"],
            "backup_matches_lock_state": backup_matches_lock_state,
            "db_logical_sha256_before": logical_before,
            "db_logical_sha256_after": logical_after,
            "scope_fingerprint_before": ctx["scope_before"].fingerprint,
            "scope_fingerprint_after": post["fingerprint"],
            "tier_breakdown_after": post["tier_breakdown"],
            "renewal_stop_for_owner_review": True,
            "renewal_stop_note": "scope fingerprint changed; the next weekly "
                                 "band renewal must stop for owner review "
                                 "before auto-apply (D2 scope-change stop)",
            "journal_txn_ids": dict(journal_txns),
            "owner_decision_ids": {d["ticker"]: d["owner_decision_id"]
                                   for d in bundle["decisions"]},
            "authority": {
                "tier_write": True,
                "activation_context": activation_context,
                "owner_decision_bound": True,
                "owner_approval_inferred": False,
                "concurrency": "journal lease + BEGIN IMMEDIATE + full membership/"
                               "band/evidence/lineage/baseline/policy re-read",
                "note": ("hermetic fixture only" if activation_context == "hermetic_test"
                         else "production cutover gate active; bound owner decisions"),
            },
        }
        rollback = {
            "schema": ROLLBACK_SCHEMA,
            "transaction_id": txn_id,
            "as_of": bundle["as_of"],
            "backup_path": backup_info["backup_path"],
            "backup_logical_sha256": backup_info["logical_sha256_backup"],
            "backup_matches_lock_state": backup_matches_lock_state,
            "db_path": str(db.resolve()).replace("\\", "/"),
            "db_logical_sha256_before": logical_before,
            "db_logical_sha256_after": logical_after,
            "before_snapshot": pre_snapshot,
            "decisions": bundle["decisions"],
            "journal_txn_ids": dict(journal_txns),
        }
        if audit_path.exists() or rollback_path.exists():
            undo(RuntimeError("audit_or_rollback_path_already_exists"),
                 "proof_path_race_restored")
        audit_tmp = audit_path.with_name(audit_path.name + ".tmp")
        rollback_tmp = rollback_path.with_name(rollback_path.name + ".tmp")
        if audit_tmp.exists() or rollback_tmp.exists():
            undo(RuntimeError("audit_or_rollback_temp_path_already_exists"),
                 "proof_path_race_restored")
        try:
            audit_tmp.write_text(json.dumps(audit, indent=2, sort_keys=True)
                                 + "\n", encoding="utf-8")
            rollback_tmp.write_text(
                json.dumps(rollback, indent=2, sort_keys=True) + "\n",
                encoding="utf-8")
            os.replace(audit_tmp, audit_path)
            os.replace(rollback_tmp, rollback_path)
        except Exception as exc:
            # Compensate first; partial proof is deleted only once canon is back.
            _compensate_apply(db, bundle, ctx, txn_id, pre_snapshot["families"],
                              exc, journal, journal_txns)
            # canon is back: a cleanup error must not trigger a second undo
            for leftover in (audit_tmp, rollback_tmp, audit_path, rollback_path):
                try:
                    leftover.unlink(missing_ok=True)
                except OSError:
                    pass
            raise _CanonUnchanged() from RuntimeError(
                "proof_write_failed_restored:%s" % exc)
        audit["audit_path"] = audit_path.as_posix()
        audit["rollback_path"] = rollback_path.as_posix()
        return audit
    except (_CanonUnchanged, _CommittedUnsettled):
        raise
    except Exception as exc:
        undo(exc, "post_commit_failed_restored")


def _compensate_apply(db: Path, bundle: dict, ctx: dict, txn_id: str,
                      pre_families: dict, reason: BaseException,
                      journal, journal_txns: dict) -> None:
    """Undo OUR committed apply by compare-and-swap, never a whole-DB restore.

    Under one BEGIN IMMEDIATE: each decision row must still hold our forward
    values; it is set back to its prior values and our own audit event is
    deleted. Every other row, including commits other jobs made meanwhile, is
    untouched. Any mismatch or error leaves canon as it is and raises
    _CommittedUnsettled, so the journal stays pending for recovery.

    Never compensates underneath a settled journal: recovery cannot run while
    this lock is held, and if it already marked a txn (e.g. effective from the
    brief commit evidence), canon keeps the commit and _CommittedUnsettled is
    raised, so journal and canon stay consistent for owner review.
    """
    try:  # R7-2: even opening the connection is inside the guard
        con = sqlite3.connect(str(db))
        con.row_factory = sqlite3.Row
    except Exception as exc:
        raise _CommittedUnsettled(
            "compensation_connect_failed:%s after %s" % (exc, reason)) from exc
    try:
        con.execute("BEGIN IMMEDIATE")
        states = {t: journal.get(j)["state"] for t, j in journal_txns.items()}
        if set(states.values()) != {ttj.PENDING}:
            raise _CommittedUnsettled(
                "compensation_skipped_journal_already_settled:%s after %s"
                % (json.dumps(states, sort_keys=True), reason))
        for d in bundle["decisions"]:
            ticker = d["ticker"]
            row = con.execute(
                "SELECT %s FROM universe_membership WHERE ticker=?"
                % ", ".join(TIER_FAMILY_COLS), (ticker,)).fetchone()
            if row is None or dict(row) != forward_family(d, ctx):
                raise _CommittedUnsettled(
                    "compensation_refused_row_changed_after_commit:%s:%s"
                    % (ticker, reason))
            prior = pre_families[ticker]
            cur = con.execute(
                "UPDATE universe_membership SET %s WHERE ticker=?"
                % ", ".join("%s=?" % c for c in TIER_FAMILY_COLS),
                tuple(prior[c] for c in TIER_FAMILY_COLS) + (ticker,))
            if cur.rowcount != 1:
                raise _CommittedUnsettled(
                    "compensation_update_affected_%d_rows:%s"
                    % (cur.rowcount, ticker))
            cur = con.execute(
                "DELETE FROM audit_events WHERE event_id=? AND event_type=?",
                ("%s:%s" % (txn_id, ticker), EVENT_TYPE))
            if cur.rowcount != 1:
                raise _CommittedUnsettled(
                    "compensation_audit_event_missing:%s" % ticker)
        con.commit()
    except _CommittedUnsettled:
        _quiet_rollback(con)
        raise
    except BaseException as exc:
        _quiet_rollback(con)
        if isinstance(exc, Exception):
            raise _CommittedUnsettled(
                "compensation_failed:%s after %s" % (exc, reason)) from exc
        raise
    finally:
        _quiet_close(con)


def _quiet_rollback(con: sqlite3.Connection) -> None:
    try:
        con.rollback()
    except Exception:
        pass


def _preflight_and_backup(root: Path, db: Path, bundle: dict, mods: dict,
                          backup_path: Path, audit_path: Path,
                          rollback_path: Path, output_dir: Path):
    output_dir = contained_path(
        root, output_dir, "output_dir", root / "tmp")
    backup_path = contained_path(
        root, backup_path, "backup_path", root / "tmp")
    audit_path = contained_path(
        root, audit_path, "audit_path", root / "tmp")
    rollback_path = contained_path(
        root, rollback_path, "rollback_path", root / "tmp")
    g6 = mods["g6"]
    for p, what in ((backup_path, "backup path"),
                    (audit_path, "audit path"),
                    (rollback_path, "rollback path")):
        g6.refuse_markdown_path(str(p), what)
    # Every directory and final/temp proof path is preflighted before commit.
    for directory in {output_dir, backup_path.parent, audit_path.parent,
                      rollback_path.parent}:
        directory.mkdir(parents=True, exist_ok=True)
    for path in (audit_path, rollback_path,
                 audit_path.with_name(audit_path.name + ".tmp"),
                 rollback_path.with_name(rollback_path.name + ".tmp")):
        if path.exists():
            raise Refusal("proof_path_already_exists:%s" % path)
    tickers = [d["ticker"] for d in bundle["decisions"]]
    pre_snapshot = snapshot_rows(db, tickers)
    # T1: WAL-safe backup; logical (WAL-inclusive) hashes are the proof.
    # No WAL-emptiness refusal: a reader-held WAL is normal (T4). The backup
    # is evidence; failures are undone by compensation, never by restoring it.
    try:
        backup_info = snap.wal_safe_backup(db, backup_path)
    except ValueError as exc:
        raise Refusal("backup_refused:%s" % (exc,))
    return (backup_path, audit_path, rollback_path), pre_snapshot, backup_info


def do_rollback(db: Path, rollback_file: Path, mods: dict) -> dict:
    """Whole-database restore to the pre-apply backup.

    Hermetic fixtures only; a live canon uses --rollback-txn
    (compare-and-swap inverse). The current-hash check, the journal-state
    check and the restore all run inside one canon BEGIN IMMEDIATE
    (round-4 R4-3), so no other job's commit can land in the gap and a
    failed restore leaves canon untouched. Also refused unless the backup
    equalled canon at the apply's lock time and nothing has committed since
    the apply.
    """
    _, context = require_mutation_target(db)
    if context != "hermetic_test":
        raise Refusal("whole_db_rollback_hermetic_only: use --rollback-txn "
                      "on a live canon")
    try:
        with open(rollback_file, "r", encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError) as exc:
        raise Refusal("rollback_file_unreadable:%s" % (exc,))
    if not isinstance(doc, dict) or doc.get("schema") != ROLLBACK_SCHEMA:
        raise Refusal("rollback_schema_invalid: need %s" % ROLLBACK_SCHEMA)
    for key in ("backup_path", "backup_logical_sha256", "db_path",
                "db_logical_sha256_before", "db_logical_sha256_after",
                "transaction_id", "decisions"):
        if key not in doc:
            raise Refusal("rollback_missing_key:%s" % key)
    if Path(str(doc["db_path"])).resolve() != db.resolve():
        raise Refusal("rollback_database_binding_mismatch")
    if doc["backup_logical_sha256"] != doc["db_logical_sha256_before"]:
        raise Refusal("rollback_backup_hash_binding_mismatch")
    if doc.get("backup_matches_lock_state") is not True:
        raise Refusal("rollback_backup_missed_commits_before_lock")
    root = db.parents[2]
    backup = contained_path(
        root, doc["backup_path"], "rollback_backup", root / "tmp")
    mods["g6"].refuse_markdown_path(str(backup), "rollback backup")
    # R4-3: hash check, journal check and restore under ONE lock.
    journal_ids = doc.get("journal_txn_ids") or {}
    journal = journal_for(root) if journal_ids else None
    try:
        apply_events = {"%s:%s" % (doc["transaction_id"], d["ticker"]):
                        journal_ids.get(d["ticker"]) for d in doc["decisions"]}
    except (TypeError, KeyError, AttributeError) as exc:
        raise Refusal("rollback_decisions_invalid:%s" % (exc,))
    if not apply_events:
        raise Refusal("rollback_decisions_invalid:empty")
    con = sqlite3.connect(str(db))
    try:
        con.execute("BEGIN IMMEDIATE")
        try:
            if _logical_sha256_conn(con) != doc["db_logical_sha256_after"]:
                raise Refusal("rollback_current_state_mismatch")
            # Round-8 R8-1: the file must describe the COMPLETE apply. Canon's
            # own events for this transaction (atomic with the apply) are the
            # authority: exactly these event ids, these journal ids, and a
            # journal map covering every one. A file that omits a sibling
            # would restore both tickers but settle one journal txn.
            prefix = "%s:" % doc["transaction_id"]
            canon_details = {
                str(event_id): json.loads(str(detail))
                for event_id, detail in con.execute(
                    "SELECT event_id, detail_json FROM audit_events "
                    "WHERE event_type=? AND substr(event_id, 1, ?) = ?",
                    (EVENT_TYPE, len(prefix), prefix))}
            canon_events = {eid: d.get("journal_txn_id")
                            for eid, d in canon_details.items()}
            if (canon_events != apply_events
                    or len(doc["decisions"]) != len(apply_events)):
                raise Refusal("rollback_file_not_the_complete_apply:canon=%s file=%s"
                              % (sorted(canon_events), sorted(apply_events)))
            # Rounds 9-10 (R8-1, R10-1): every trust-bearing field of the file
            # is attested by canon's own apply events, written atomically with
            # the apply: the whole decision record (digest), the backup hash,
            # and that the backup equalled canon at the apply's lock time.
            for d in doc["decisions"]:
                recorded = canon_details["%s%s" % (prefix, d["ticker"])]
                if recorded.get("decision_sha256") != _decision_digest(d):
                    raise Refusal("rollback_file_not_the_complete_apply:"
                                  "decision_mismatch:%s" % d["ticker"])
                if (recorded.get("backup_logical_sha256") != doc["backup_logical_sha256"]
                        or recorded.get("db_logical_sha256_at_lock")
                        != doc["backup_logical_sha256"]):
                    raise Refusal("rollback_backup_not_canon_attested:%s" % d["ticker"])
            canon_journal = {eid[len(prefix):]: jid for eid, jid in canon_events.items()
                             if jid is not None}
            if journal_ids != canon_journal:
                raise Refusal("rollback_journal_map_not_the_complete_apply")
            # the after-state cannot be in canon's event (it includes the
            # event); the journal recorded it at mark_effective, so a file
            # whose after-hash was moved to cover later commits is refused.
            if not journal_ids:
                raise Refusal("rollback_after_state_unattested:no_journal")
            for jtxn in journal_ids.values():
                txn = journal.get(jtxn)
                if txn is None or txn["state"] != ttj.EFFECTIVE:
                    raise Refusal(
                        "rollback_journal_txn_not_effective:%s state=%s"
                        % (jtxn, txn["state"] if txn else None))
                commit = txn.get("commit") or {}
                if (commit.get("db_logical_sha256_after") != doc["db_logical_sha256_after"]
                        or commit.get("canon_transaction_id") != doc["transaction_id"]):
                    raise Refusal("rollback_after_state_unattested:%s" % jtxn)
            after = _locked_logical_restore(
                con, backup, doc["db_logical_sha256_before"])
        except BaseException:
            _quiet_rollback(con)
            raise
        # R7-1: a whole-DB hash is not stable once COMMIT frees the lock
        # (another job may commit first), so the probe reads this apply's own
        # audit events, which no writer recreates. Present = no restore of
        # this apply committed, ours included: proven abort. Absent = canon IS
        # restored, but (R8) a concurrent restore of the same apply could have
        # done it, so the outcome is settled yet reported unattributed (exit 5).
        unattributed = []

        def restore_landed() -> bool:
            if _exact_events_present(db, EVENT_TYPE, apply_events):
                return False
            unattributed.append(True)
            return True
        _commit_or_prove_aborted(con, restore_landed)
    except ValueError as exc:
        raise Refusal("rollback_refused:%s" % (exc,))
    finally:
        _quiet_close(con)
    # Round-5 R5-4: canon is restored from here on. The journal is settled
    # first (it must follow canon whatever the guard says), and any failure
    # after the restore COMMIT is committed-unsettled (exit 5), never a
    # plain failure that reads as "nothing changed" (exit 4). Whole-DB
    # restore writes no inverse event, so --recover cannot settle it later.
    try:
        for jtxn in journal_ids.values():
            journal.mark_rolled_back(jtxn, {"reason": "whole_db_restore",
                                            "rollback_file": str(rollback_file)})
    except Exception as exc:
        raise _CommittedUnsettled(
            "whole_db_restored_journal_unsettled:%s states=%s" % (
                exc, _journal_states(journal, journal_ids.values()))) from exc
    if unattributed:
        raise _CommittedUnsettled(
            "whole_db_restore_commit_raised_canon_restored_unattributed: journal "
            "settled to canon (states=%s); owner review"
            % (_journal_states(journal, journal_ids.values()),))
    try:
        access = mods["fsca"].FinanceSqlCanonAccess(db)
        validation = access.validate()
        if validation.get("status") != "ok":
            raise RuntimeError("post_rollback_guard_not_ok:%s" % (
                validation.get("errors"),))
        scope = access.dynamic_entitlement_scope()
        return {"status": "rolled_back",
                "transaction_id": doc.get("transaction_id"),
                "journal_txn_ids": journal_ids,
                "db_logical_sha256": after,
                "tier_breakdown": dict(scope.tier_breakdown),
                "guard": "ok"}
    except Exception as exc:
        raise _CommittedUnsettled(
            "whole_db_restored_post_check_failed:%s" % exc) from exc


def _canon_sibling_journal_txns(con, journal_txn_id: str) -> set | None:
    """Journal txn ids written by the same canon apply as ``journal_txn_id``.

    Read from canon audit events, so it also covers txns settled by recovery.
    None means canon holds no apply event for ``journal_txn_id``.
    """
    events = _audit_events_matching(con, EVENT_TYPE, "journal_txn_id",
                                    journal_txn_id)
    if not events:
        return None
    canon_txn = events[0][1].get("transaction_id")
    prefix = "%s:" % canon_txn
    ids = set()
    for event_id, detail in con.execute(
            "SELECT event_id, detail_json FROM audit_events WHERE event_type=? "
            "AND substr(event_id, 1, ?) = ?", (EVENT_TYPE, len(prefix), prefix)):
        jid = json.loads(str(detail)).get("journal_txn_id")
        if jid:
            ids.add(jid)
    return ids


def do_inverse_rollback(root: Path, db: Path, journal_txn_ids: list[str],
                        mods: dict, backup_path: Path,
                        _journal_clock=None,
                        _force_verify_fail: bool = False,
                        _crash_after_commit: bool = False) -> dict:
    """Live-safe rollback of effective journal transactions (P4-3).

    Compare-and-swap per ticker in ONE BEGIN IMMEDIATE transaction, with an
    audit event per ticker. Under that write lock it refuses unless:

    - every txn is still effective and is the latest on its ticker (no later
      effective or pending txn it would silently undo);
    - the request covers every txn written by the same canon apply (a paired
      swap, or any multi-name apply, is one rollback unit);
    - each current row still equals the txn's forward values;
    - post-rollback A/B counts stay within the caps.

    A verification failure after COMMIT is undone by compensation (forward
    values back, our inverse events deleted), never by restoring the backup,
    which is evidence only (``backup_matches_lock_state`` records whether it
    equals canon at lock time).

    Rows other jobs changed (bands, freshness, other tickers) are untouched,
    so this is safe on a canon the renewal and freshness jobs keep writing.
    ``_crash_after_commit`` is a test-only hook (never CLI).
    """
    require_mutation_target(db)
    if not journal_txn_ids or len(set(journal_txn_ids)) != len(journal_txn_ids):
        raise Refusal("inverse_rollback_needs_distinct_txn_ids")
    journal = journal_for(root, _journal_clock)
    recover_journal(journal, db)
    txns = []
    for jtxn in journal_txn_ids:
        txn = journal.get(jtxn)
        if txn is None:
            raise Refusal("inverse_rollback_unknown_txn:%s" % jtxn)
        if txn["state"] != ttj.EFFECTIVE:
            raise Refusal("inverse_rollback_txn_not_effective:%s state=%s"
                          % (jtxn, txn["state"]))
        txns.append(txn)
    if len({t["ticker"] for t in txns}) != len(txns):
        raise Refusal("inverse_rollback_duplicate_ticker")
    access = mods["fsca"].FinanceSqlCanonAccess(db)
    validation = access.validate()
    if validation.get("status") != "ok":
        raise Refusal("canon_guard_not_ok:%s" % (validation.get("errors"),))
    backup_path = contained_path(root, backup_path, "backup_path", root / "tmp")
    mods["g6"].refuse_markdown_path(str(backup_path), "backup path")
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        backup_info = snap.wal_safe_backup(db, backup_path)
    except ValueError as exc:
        raise Refusal("backup_refused:%s" % (exc,))
    # Round-8: a per-attempt nonce, so two identical requests in the same
    # second never share event ids (the landed probe binds to them).
    rb_id = "rb_%s_%s_%s" % (_utc_stamp(), hashlib.sha256(
        "|".join(journal_txn_ids).encode()).hexdigest()[:8], os.urandom(6).hex())
    now = _dt.datetime.now(_dt.timezone.utc).isoformat()
    requested = set(journal_txn_ids)
    con = sqlite3.connect(str(db))
    con.row_factory = sqlite3.Row
    try:
        con.execute("BEGIN IMMEDIATE")
        backup_matches_lock_state = (
            _logical_sha256_conn(con) == backup_info["logical_sha256_before"])
        for t in txns:
            fresh = journal.get(t["txn_id"])
            if fresh is None or fresh["state"] != ttj.EFFECTIVE:
                raise Refusal("inverse_rollback_txn_not_effective:%s state=%s"
                              % (t["txn_id"], fresh["state"] if fresh else None))
            later = journal.later_transactions(t)
            if later:
                raise Refusal("inverse_rollback_later_transaction_on_ticker:%s %s"
                              % (t["ticker"], ",".join(x["txn_id"] for x in later)))
            siblings = _canon_sibling_journal_txns(con, t["txn_id"])
            if siblings is None:
                raise Refusal("inverse_rollback_canon_commit_evidence_missing:%s"
                              % t["txn_id"])
            missing = siblings - requested
            if missing:
                raise Refusal("inverse_rollback_incomplete_canon_transaction:%s "
                              "roll back together with %s"
                              % (t["txn_id"], ",".join(sorted(missing))))
        found = dict(con.execute(
            "SELECT tier, COUNT(*) FROM universe_membership WHERE tier IN "
            "('A','B') GROUP BY tier").fetchall())
        counts = {"A": int(found.get("A", 0)), "B": int(found.get("B", 0))}
        for t in txns:
            if t["to_tier"] in counts:
                counts[t["to_tier"]] -= 1
            if t["from_tier"] in counts:
                counts[t["from_tier"]] += 1
        if counts["A"] > TIER_A_CAP or counts["B"] > TIER_B_CAP:
            raise Refusal("inverse_rollback_cap_breach:A=%d B=%d"
                          % (counts["A"], counts["B"]))
        for t in txns:
            row = con.execute(
                "SELECT %s FROM universe_membership WHERE ticker=?"
                % ", ".join(TIER_FAMILY_COLS), (t["ticker"],)).fetchone()
            if row is None or dict(row) != t["forward"]:
                raise Refusal("inverse_rollback_row_changed_since_commit:%s"
                              % t["ticker"])
            inv = t["inverse"]
            cur = con.execute(
                "UPDATE universe_membership SET %s WHERE ticker=?"
                % ", ".join("%s=?" % c for c in TIER_FAMILY_COLS),
                tuple(inv[c] for c in TIER_FAMILY_COLS) + (t["ticker"],))
            if cur.rowcount != 1:
                raise RuntimeError("inverse_update_affected_%d_rows:%s"
                                   % (cur.rowcount, t["ticker"]))
            con.execute(
                "INSERT INTO audit_events(event_id, event_time_utc, "
                "event_type, detail_json) VALUES (?, ?, ?, ?)",
                ("%s:%s" % (rb_id, t["ticker"]), now, ROLLBACK_EVENT_TYPE,
                 json.dumps({"ticker": t["ticker"], "journal_txn_id": t["txn_id"],
                             "restored": inv, "reverted": t["forward"],
                             "rollback_id": rb_id}, sort_keys=True)))
        logical_after = _logical_sha256_conn(con)
        ours = {"%s:%s" % (rb_id, t["ticker"]): t["txn_id"] for t in txns}
        _commit_or_prove_aborted(
            con, lambda: _exact_events_present(db, ROLLBACK_EVENT_TYPE, ours))
    except BaseException:
        try:
            con.rollback()
        except Exception:
            pass
        raise
    finally:
        _quiet_close(con)
    if _crash_after_commit:
        raise _SimulatedCrash("test-only crash after inverse commit")
    try:
        if _force_verify_fail:
            raise RuntimeError("injected_verify_failure")
        post = access.validate()
        if post.get("status") != "ok":
            raise RuntimeError("post_rollback_guard_not_ok:%s" % (post.get("errors"),))
        scope = access.dynamic_entitlement_scope()
    except Exception as exc:
        _compensate_inverse(db, txns, rb_id, exc, journal)
        raise RuntimeError("inverse_rollback_failed_restored:%s" % exc) from exc
    try:
        for t in txns:
            journal.mark_rolled_back(t["txn_id"], {"reason": "inverse_rollback",
                                                   "rollback_id": rb_id})
    except Exception as exc:
        # The inverse is committed and verified; recovery settles it from the
        # inverse events. Anything short of rolled_back is owner-visible.
        try:
            recover_journal(journal, db)
        except Exception:
            pass
        states = _journal_states(journal, [t["txn_id"] for t in txns])
        if states != [ttj.ROLLED_BACK]:
            raise _CommittedUnsettled(
                "inverse_committed_journal_unsettled:%s states=%s" % (exc, states)
            ) from exc
    # Round-4 R4-2: the inverse is committed and the journal settled; a
    # failure building the success proof is committed-unsettled (exit 5),
    # never a plain failure that reads as "our change absent" (exit 4).
    try:
        return {"status": "rolled_back_inverse", "rollback_id": rb_id,
                "journal_txn_ids": list(journal_txn_ids),
                "tickers": [t["ticker"] for t in txns],
                "backup_path": backup_info["backup_path"],
                "backup_matches_lock_state": backup_matches_lock_state,
                "db_logical_sha256_after": logical_after,
                "tier_breakdown": dict(scope.tier_breakdown), "guard": "ok"}
    except Exception as exc:
        raise _CommittedUnsettled(
            "inverse_committed_proof_failed:%s" % exc) from exc


def _compensate_inverse(db: Path, txns: list, rb_id: str,
                        reason: BaseException, journal) -> None:
    """Undo OUR committed inverse by compare-and-swap, never a whole-DB restore.

    Each row must still hold the inverse values; it is set back to the
    forward values and our inverse audit event is deleted, in one BEGIN
    IMMEDIATE. On any mismatch or error canon is left as it is and
    _CommittedUnsettled is raised; recovery then sees the inverse event and
    marks the txns rolled_back.

    Runs only while every txn is still effective in the journal (checked under
    this lock, which recovery also needs). If recovery already marked them
    rolled_back from the inverse event, canon keeps the inverse and
    _CommittedUnsettled is raised instead of reversing it underneath.
    """
    try:  # R7-2: even opening the connection is inside the guard
        con = sqlite3.connect(str(db))
        con.row_factory = sqlite3.Row
    except Exception as exc:
        raise _CommittedUnsettled(
            "inverse_compensation_connect_failed:%s after %s" % (exc, reason)) from exc
    try:
        con.execute("BEGIN IMMEDIATE")
        states = {t["txn_id"]: journal.get(t["txn_id"])["state"] for t in txns}
        if set(states.values()) != {ttj.EFFECTIVE}:
            raise _CommittedUnsettled(
                "inverse_committed_unverified_journal_%s after %s"
                % (json.dumps(states, sort_keys=True), reason))
        for t in txns:
            row = con.execute(
                "SELECT %s FROM universe_membership WHERE ticker=?"
                % ", ".join(TIER_FAMILY_COLS), (t["ticker"],)).fetchone()
            if row is None or dict(row) != t["inverse"]:
                raise _CommittedUnsettled(
                    "inverse_compensation_refused_row_changed:%s:%s"
                    % (t["ticker"], reason))
            cur = con.execute(
                "UPDATE universe_membership SET %s WHERE ticker=?"
                % ", ".join("%s=?" % c for c in TIER_FAMILY_COLS),
                tuple(t["forward"][c] for c in TIER_FAMILY_COLS) + (t["ticker"],))
            if cur.rowcount != 1:
                raise _CommittedUnsettled(
                    "inverse_compensation_update_affected_%d_rows:%s"
                    % (cur.rowcount, t["ticker"]))
            cur = con.execute(
                "DELETE FROM audit_events WHERE event_id=? AND event_type=?",
                ("%s:%s" % (rb_id, t["ticker"]), ROLLBACK_EVENT_TYPE))
            if cur.rowcount != 1:
                raise _CommittedUnsettled(
                    "inverse_compensation_event_missing:%s" % t["ticker"])
        con.commit()
    except _CommittedUnsettled:
        _quiet_rollback(con)
        raise
    except BaseException as exc:
        _quiet_rollback(con)
        if isinstance(exc, Exception):
            raise _CommittedUnsettled(
                "inverse_compensation_failed:%s after %s" % (exc, reason)) from exc
        raise
    finally:
        _quiet_close(con)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def default_output_dir(root: Path) -> Path:
    stamp = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return (root / "tmp" / "p4-2-writer-lane-20260927" / "slice-a" / "v2"
            / "writer-output" / stamp)


def parse_args(argv: list[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Activation-blocked per-name SQL tier-writer foundation "
                    "(dry-run only; never touch universe-v1.json).")
    # T6: --root is REQUIRED in every mode.
    ap.add_argument("--root", required=True,
                    help="Workspace root holding scripts/, state/, tmp/.")
    ap.add_argument("--decision-file", default=None)
    ap.add_argument("--db", default=None)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--backup-path", default=None)
    ap.add_argument("--rollback-path", default=None)
    ap.add_argument("--audit-path", default=None)
    ap.add_argument("--output-dir", default=None)
    ap.add_argument("--proposal-packet", default=None,
                    help="T7: proposal packet JSON backing the decisions' "
                         "proposal_packet_sha256 values.")
    ap.add_argument("--rollback", default=None,
                    help="Whole-DB rollback mode: path to rollback JSON "
                         "(only while nothing else has committed since).")
    ap.add_argument("--rollback-txn", action="append", default=None,
                    help="P4-3 live-safe inverse rollback of an effective "
                         "journal transaction (repeat for a paired swap).")
    ap.add_argument("--recover", action="store_true",
                    help="Settle open journal transactions from canon evidence.")
    ap.add_argument("--after-crash", action="store_true",
                    help="With --recover: block open transactions that have "
                         "no canon commit (their writer is gone).")
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    root = Path(args.root).resolve()
    if not root.is_dir() or not args.db:
        print("error: --root directory and --db are required",
              file=sys.stderr)
        return EXIT_REFUSED
    try:
        db = contained_path(
            root, args.db, "db", root / "state" / "finance",
            exact=root / "state" / "finance" / "finance-canon.sqlite")
        rollback_file = (contained_path(
            root, args.rollback, "rollback", root / "tmp")
            if args.rollback else None)
    except Refusal as exc:
        print(json.dumps({"status": "refused", "reason": str(exc)},
                         indent=2, sort_keys=True))
        return EXIT_REFUSED
    mods = staged_modules(root)
    if args.recover:
        if args.apply or args.write or args.rollback or args.rollback_txn:
            print("error: --recover runs alone", file=sys.stderr)
            return EXIT_REFUSED
        # Recovery writes the journal, so it sits behind the same gate as
        # every other mutation path; a refused root never gets a journal.
        allowed, why = mutation_allowed(root, db)
        if not allowed:
            print(json.dumps({"status": "refused", "reason": why},
                             indent=2, sort_keys=True))
            return EXIT_REFUSED
        settled = recover_journal(journal_for(root), db,
                                  after_crash=args.after_crash)
        print(json.dumps({"status": "recovered", "settled": [
            {"txn_id": t["txn_id"], "ticker": t["ticker"], "state": t["state"],
             "reasons": t["reasons"]} for t in settled]}, indent=2, sort_keys=True))
        return EXIT_OK
    if args.rollback_txn:
        if args.apply or args.write or args.rollback:
            print("error: --rollback-txn refuses --apply/--write/--rollback",
                  file=sys.stderr)
            return EXIT_REFUSED
        allowed, why = mutation_allowed(root, db)
        if not allowed:
            print(json.dumps({"status": "refused", "reason": why},
                             indent=2, sort_keys=True))
            return EXIT_REFUSED
        try:
            backup = contained_path(
                root, args.backup_path or (default_output_dir(root)
                                           / "inverse-rollback.logical-backup.sqlite"),
                "backup_path", root / "tmp")
            result = do_inverse_rollback(root, db, args.rollback_txn, mods, backup)
        except Refusal as exc:
            print(json.dumps({"status": "refused", "reason": str(exc)}, indent=2))
            return EXIT_REFUSED
        except _CommittedUnsettled as exc:
            print(json.dumps({"status": "committed_unsettled", "reason": str(exc),
                              "next": "run --recover, then owner review"}, indent=2))
            return EXIT_COMMITTED_UNSETTLED
        except Exception as exc:
            print(json.dumps({"status": "rollback_failed", "reason": str(exc)},
                             indent=2))
            return EXIT_VERIFY_FAIL
        print(json.dumps(result, indent=2, sort_keys=True))
        return EXIT_OK
    if args.rollback:
        if args.apply or args.write:
            print("error: --rollback refuses --apply/--write",
                  file=sys.stderr)
            return EXIT_REFUSED
        allowed, why = mutation_allowed(root, db)
        if not allowed:
            print(json.dumps({"status": "refused", "reason": why},
                             indent=2, sort_keys=True))
            return EXIT_REFUSED
        try:
            result = do_rollback(db, rollback_file, mods)
        except Refusal as exc:
            print(json.dumps({"status": "refused", "reason": str(exc)},
                             indent=2))
            return EXIT_REFUSED
        except _CommittedUnsettled as exc:
            print(json.dumps({"status": "committed_unsettled", "reason": str(exc),
                              "next": "canon restored; owner review of journal"},
                             indent=2))
            return EXIT_COMMITTED_UNSETTLED
        except Exception as exc:
            print(json.dumps({"status": "rollback_failed",
                              "reason": str(exc)}, indent=2))
            return EXIT_VERIFY_FAIL
        print(json.dumps(result, indent=2, sort_keys=True))
        return EXIT_OK

    if not args.decision_file:
        print("error: --decision-file is required", file=sys.stderr)
        return EXIT_REFUSED
    if not db.is_file():
        print("error: --db not found: %s" % db, file=sys.stderr)
        return EXIT_REFUSED
    try:
        decision_file = contained_path(
            root, args.decision_file, "decision_file", root / "tmp")
        packet_file = (contained_path(
            root, args.proposal_packet, "proposal_packet", root / "tmp")
            if args.proposal_packet else None)
        bundle = load_decisions(decision_file)
        verify_proposal_packet(bundle, packet_file)
        bind_owner_decisions(root, bundle)
        ctx = check_preconditions(root, db, bundle, mods)
        for d in bundle["decisions"]:
            scan_forbidden(json.dumps(d, sort_keys=True), mods,
                           "decision %s" % d["ticker"])
    except Refusal as exc:
        print(json.dumps({"status": "refused", "reason": str(exc)},
                         indent=2, sort_keys=True))
        return EXIT_REFUSED

    allowed, why = mutation_allowed(root, db)
    plan = {
        "status": "dry_run_plan",
        "as_of": bundle["as_of"],
        "decisions": bundle["decisions"],
        "post_counts": ctx["post_counts"],
        "tier_breakdown_before": dict(ctx["scope_before"].tier_breakdown),
        "authority": {
            "tier_write": False,
            "mode": "dry_run",
            "owner_approval_inferred": False,
            "owner_decisions_bound": True,
            "activation_status": "permitted" if allowed else "blocked",
            "activation_context_or_block_reason": why,
        },
    }
    if not (args.apply and args.write):
        if args.apply != args.write:
            plan["note"] = ("apply requires BOTH --apply and --write; "
                            "no mutation performed")
        print(json.dumps(plan, indent=2, sort_keys=True))
        return EXIT_OK
    if not allowed:
        print(json.dumps({"status": "refused", "reason": why},
                         indent=2, sort_keys=True))
        return EXIT_REFUSED

    try:
        out = contained_path(
            root, args.output_dir or default_output_dir(root),
            "output_dir", root / "tmp")
        backup_path = contained_path(
            root, args.backup_path or out / "finance-canon.logical-backup.sqlite",
            "backup_path", root / "tmp")
        audit_path = contained_path(
            root, args.audit_path or out / "tier_apply_audit.json",
            "audit_path", root / "tmp")
        rollback_path = contained_path(
            root, args.rollback_path or out / "tier_rollback.json",
            "rollback_path", root / "tmp")
        protected = {db.resolve(), decision_file.resolve(), packet_file.resolve()}
        if any(path.resolve() in protected
               for path in (backup_path, audit_path, rollback_path)):
            raise Refusal("output_path_aliases_protected_input")
    except Refusal as exc:
        print(json.dumps({"status": "refused", "reason": str(exc)},
                         indent=2, sort_keys=True))
        return EXIT_REFUSED
    try:
        audit = do_apply(root, db, bundle, ctx, mods, backup_path,
                         audit_path, rollback_path, out)
    except Refusal as exc:
        print(json.dumps({"status": "refused", "reason": str(exc)},
                         indent=2, sort_keys=True))
        return EXIT_REFUSED
    except _CommittedUnsettled as exc:
        print(json.dumps({"status": "committed_unsettled", "reason": str(exc),
                          "next": "run --recover, then owner review"},
                         indent=2, sort_keys=True))
        return EXIT_COMMITTED_UNSETTLED
    except Exception as exc:
        print(json.dumps({"status": "apply_failed",
                          "reason": str(exc)}, indent=2, sort_keys=True))
        return EXIT_VERIFY_FAIL
    print(json.dumps({"status": "applied", "audit": audit},
                     indent=2, sort_keys=True))
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
