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
plus expected tier_breakdown, otherwise WAL-safe restore and raise.

Exit codes: 0 ok; 2 usage or precondition refusal (nothing mutated);
4 post-apply verification failure (backup restored, nothing applied).

stdlib only. No network.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

import sqlite_snapshot as snap

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

TIER_FAMILY_COLS = ("tier", "coverage_obligation_tier", "sql_tier",
                    "tier_decision_scope", "decision_grade_eligible")

EXIT_OK = 0
EXIT_REFUSED = 2
EXIT_VERIFY_FAIL = 4
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
        clean.append({
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


def _execute_updates(con, bundle: dict, ctx: dict, txn_id: str, now: str,
                     _fault_after_first: bool = False) -> int:
    """Run the UPDATE+INSERT statements on an open write transaction.
    T5: every UPDATE must affect exactly one row (cur.rowcount; the
    cumulative con.total_changes cannot detect a zero-row UPDATE)."""
    n = 0
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
                  "transaction_id": txn_id}
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
                      _skip_concurrency_check: bool = False) -> int:
    """Single BEGIN IMMEDIATE transaction on a hermetic temp fixture.

    T2 re-reads tier families and A/B counts BEFORE writing; any difference
    from the pre-transaction snapshot means ROLLBACK + Refusal.

    _fault_after_first / _skip_concurrency_check are test-only hooks
    (never CLI): the first raises mid-transaction to prove atomicity;
    the second isolates the T5 rowcount check from the T2 re-read.
    """
    require_hermetic_test_db(db)
    now = _dt.datetime.now(_dt.timezone.utc).isoformat()
    con = sqlite3.connect(str(db))
    con.row_factory = sqlite3.Row
    try:
        con.execute("BEGIN IMMEDIATE")
        if not _skip_concurrency_check:
            live = _reread_families(
                con, db, [d["ticker"] for d in bundle["decisions"]])
            if live != pre_snapshot:
                try:
                    con.rollback()
                except Exception:
                    pass
                raise Refusal(
                    "concurrent_canon_change_detected: membership, band, "
                    "evidence, lineage, baseline, or provider policy changed "
                    "between snapshot and transaction")
        n = _execute_updates(con, bundle, ctx, txn_id, now,
                             _fault_after_first=_fault_after_first)
        con.commit()
        return n
    except Refusal:
        raise
    except Exception:
        try:
            con.rollback()
        except Exception:
            pass
        raise
    finally:
        con.close()


def verify_post_state(mods: dict, db: Path, post_counts: dict,
                      bundle: dict, ctx: dict, txn_id: str) -> dict:
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
            ):
                if detail.get(key) != expected_value:
                    raise RuntimeError(
                        "post_apply_audit_event_mismatch:%s:%s" % (
                            decision["ticker"], key))
        event_count = int(con.execute(
            "SELECT COUNT(*) FROM audit_events WHERE event_type=? "
            "AND event_id LIKE ?",
            (EVENT_TYPE, txn_id + ":%"),
        ).fetchone()[0])
        if event_count != len(bundle["decisions"]):
            raise RuntimeError(
                "post_apply_audit_event_count_mismatch:%d" % event_count)
    finally:
        con.close()
    return {"fingerprint": scope.fingerprint,
            "tier_breakdown": dict(scope.tier_breakdown)}


def do_apply(root: Path, db: Path, bundle: dict, ctx: dict, mods: dict,
             backup_path: Path, audit_path: Path, rollback_path: Path,
             output_dir: Path,
             _fault_after_first: bool = False,
             _force_verify_fail: bool = False,
             _skip_concurrency_check: bool = False) -> dict:
    require_hermetic_test_db(db)
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
    # No WAL-emptiness refusal: a reader-held WAL is normal (T4).
    try:
        backup_info = snap.wal_safe_backup(db, backup_path)
    except ValueError as exc:
        raise Refusal("backup_refused:%s" % (exc,))
    logical_before = backup_info["logical_sha256_before"]
    txn_id = "txn_%s_%s" % (_utc_stamp(),
                            hashlib.sha256(json.dumps(
                                bundle["decisions"],
                                sort_keys=True).encode()).hexdigest()[:8])
    audit_rows = apply_transaction(
        db, bundle, ctx, txn_id, pre_snapshot,
        _fault_after_first=_fault_after_first,
        _skip_concurrency_check=_skip_concurrency_check)
    try:
        logical_after = snap.logical_sha256(db)
    except Exception as exc:
        # Never restore on an unknown post-commit state; preserve the hermetic
        # fixture and backup for diagnosis instead of risking a lost commit.
        raise RuntimeError(
            "post_commit_hash_failed_restore_refused:%s" % exc
        ) from exc

    def restore_if_unchanged(reason: BaseException) -> None:
        current = snap.logical_sha256(db)
        if current != logical_after:
            raise RuntimeError(
                "restore_refused_concurrent_change_after_commit:%s" % reason
            ) from reason
        snap.wal_safe_restore(backup_path, db, logical_before)

    try:
        if _force_verify_fail:
            raise RuntimeError("injected_verify_failure")
        post = verify_post_state(
            mods, db, ctx["post_counts"], bundle, ctx, txn_id)
    except Exception as exc:
        restore_if_unchanged(exc)
        raise RuntimeError("post_apply_failed_restored:%s" % (exc,))
    audit = {
        "schema": AUDIT_SCHEMA,
        "transaction_id": txn_id,
        "as_of": bundle["as_of"],
        "decisions": bundle["decisions"],
        "post_counts": ctx["post_counts"],
        "audit_rows_inserted": audit_rows,
        "backup_path": backup_info["backup_path"],
        "backup_logical_sha256": backup_info["logical_sha256_backup"],
        "db_logical_sha256_before": logical_before,
        "db_logical_sha256_after": logical_after,
        "scope_fingerprint_before": ctx["scope_before"].fingerprint,
        "scope_fingerprint_after": post["fingerprint"],
        "tier_breakdown_after": post["tier_breakdown"],
        "renewal_stop_for_owner_review": True,
        "renewal_stop_note": "scope fingerprint changed; the next weekly "
                             "band renewal must stop for owner review "
                             "before auto-apply (D2 scope-change stop)",
        "authority": {
            "tier_write": True,
            "activation_context": "hermetic_test_only",
            "production_activation_status": "blocked",
            "production_activation_block_reason": ACTIVATION_BLOCK_REASON,
            "owner_approval_inferred": False,
            "concurrency": "BEGIN IMMEDIATE + full membership/band/evidence/"
                           "lineage/baseline/policy re-read",
            "note": "production CLI mutation remains disabled; this record "
                    "is emitted only by the hermetic test activation path",
        },
    }
    rollback = {
        "schema": ROLLBACK_SCHEMA,
        "transaction_id": txn_id,
        "as_of": bundle["as_of"],
        "backup_path": backup_info["backup_path"],
        "backup_logical_sha256": backup_info["logical_sha256_backup"],
        "db_path": str(db.resolve()).replace("\\", "/"),
        "db_logical_sha256_before": logical_before,
        "db_logical_sha256_after": logical_after,
        "before_snapshot": pre_snapshot,
        "decisions": bundle["decisions"],
    }
    if audit_path.exists() or rollback_path.exists():
        reason = RuntimeError("audit_or_rollback_path_already_exists")
        restore_if_unchanged(reason)
        raise reason
    audit_tmp = audit_path.with_name(audit_path.name + ".tmp")
    rollback_tmp = rollback_path.with_name(rollback_path.name + ".tmp")
    if audit_tmp.exists() or rollback_tmp.exists():
        reason = RuntimeError("audit_or_rollback_temp_path_already_exists")
        restore_if_unchanged(reason)
        raise reason
    try:
        audit_tmp.write_text(json.dumps(audit, indent=2, sort_keys=True)
                             + "\n", encoding="utf-8")
        rollback_tmp.write_text(
            json.dumps(rollback, indent=2, sort_keys=True) + "\n",
            encoding="utf-8")
        os.replace(audit_tmp, audit_path)
        os.replace(rollback_tmp, rollback_path)
    except Exception as exc:
        # Preserve any partial proof if drift blocks restoration; delete it
        # only after the fixture DB is safely restored.
        restore_if_unchanged(exc)
        audit_tmp.unlink(missing_ok=True)
        rollback_tmp.unlink(missing_ok=True)
        audit_path.unlink(missing_ok=True)
        rollback_path.unlink(missing_ok=True)
        raise RuntimeError("proof_write_failed_restored:%s" % exc) from exc
    audit["audit_path"] = audit_path.as_posix()
    audit["rollback_path"] = rollback_path.as_posix()
    return audit


def do_rollback(db: Path, rollback_file: Path, mods: dict) -> dict:
    require_hermetic_test_db(db)
    try:
        with open(rollback_file, "r", encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError) as exc:
        raise Refusal("rollback_file_unreadable:%s" % (exc,))
    if not isinstance(doc, dict) or doc.get("schema") != ROLLBACK_SCHEMA:
        raise Refusal("rollback_schema_invalid: need %s" % ROLLBACK_SCHEMA)
    for key in ("backup_path", "backup_logical_sha256", "db_path",
                "db_logical_sha256_before", "db_logical_sha256_after"):
        if key not in doc:
            raise Refusal("rollback_missing_key:%s" % key)
    if Path(str(doc["db_path"])).resolve() != db.resolve():
        raise Refusal("rollback_database_binding_mismatch")
    if doc["backup_logical_sha256"] != doc["db_logical_sha256_before"]:
        raise Refusal("rollback_backup_hash_binding_mismatch")
    root = db.parents[2]
    backup = contained_path(
        root, doc["backup_path"], "rollback_backup", root / "tmp")
    mods["g6"].refuse_markdown_path(str(backup), "rollback backup")
    current = snap.logical_sha256(db)
    if current != doc["db_logical_sha256_after"]:
        raise Refusal("rollback_current_state_mismatch")
    # T1: restore through SQLite; verify against the recorded logical sha.
    # Never unlink sidecars, never copyfile (T4).
    try:
        after = snap.wal_safe_restore(backup, db,
                                      doc["db_logical_sha256_before"])
    except ValueError as exc:
        raise Refusal("rollback_refused:%s" % (exc,))
    access = mods["fsca"].FinanceSqlCanonAccess(db)
    validation = access.validate()
    if validation.get("status") != "ok":
        raise RuntimeError("post_rollback_guard_not_ok:%s" % (
            validation.get("errors"),))
    scope = access.dynamic_entitlement_scope()
    return {"status": "rolled_back",
            "transaction_id": doc.get("transaction_id"),
            "db_logical_sha256": after,
            "tier_breakdown": dict(scope.tier_breakdown),
            "guard": "ok"}


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
                    help="Rollback mode: path to rollback JSON.")
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
    if args.rollback:
        if args.apply or args.write:
            print("error: --rollback refuses --apply/--write",
                  file=sys.stderr)
            return EXIT_REFUSED
        if not test_only_activation_allowed(root, db):
            print(json.dumps({
                "status": "refused",
                "reason": "activation_blocked:%s" % ACTIVATION_BLOCK_REASON,
            }, indent=2, sort_keys=True))
            return EXIT_REFUSED
        try:
            result = do_rollback(db, rollback_file, mods)
        except Refusal as exc:
            print(json.dumps({"status": "refused", "reason": str(exc)},
                             indent=2))
            return EXIT_REFUSED
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
        ctx = check_preconditions(root, db, bundle, mods)
        for d in bundle["decisions"]:
            scan_forbidden(json.dumps(d, sort_keys=True), mods,
                           "decision %s" % d["ticker"])
    except Refusal as exc:
        print(json.dumps({"status": "refused", "reason": str(exc)},
                         indent=2, sort_keys=True))
        return EXIT_REFUSED

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
            "activation_status": "blocked",
            "activation_block_reason": ACTIVATION_BLOCK_REASON,
            "note": "source is inert pending a separate exact apply "
                    "authorization and cutover",
        },
    }
    if not (args.apply and args.write):
        if args.apply != args.write:
            plan["note"] = ("apply requires BOTH --apply and --write; "
                            "no mutation performed")
        print(json.dumps(plan, indent=2, sort_keys=True))
        return EXIT_OK
    if not test_only_activation_allowed(root, db):
        print(json.dumps({
            "status": "refused",
            "reason": "activation_blocked:%s" % ACTIVATION_BLOCK_REASON,
        }, indent=2, sort_keys=True))
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
    except Exception as exc:
        print(json.dumps({"status": "apply_failed",
                          "reason": str(exc)}, indent=2, sort_keys=True))
        return EXIT_VERIFY_FAIL
    print(json.dumps({"status": "applied", "audit": audit},
                     indent=2, sort_keys=True))
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
