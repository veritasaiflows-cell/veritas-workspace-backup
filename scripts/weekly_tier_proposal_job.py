#!/usr/bin/env python3
"""Weekly tier promotion/demotion candidate proposal job (P4-2 slice A, v2).

Drafting only. Dry-run by design: no apply mode exists. Reads tier, scope,
bands, and evidence ONLY through the guarded read path
``scripts/finance_sql_canon_access.py`` (never raw sqlite against the canon).
Emits a proposal packet (JSON + Markdown owner digest) under --output-dir.

Exit codes: 0 draft packet written; 2 CLI/usage error; 3 guard blocked
(a blocked packet is still written, then exit 3).

Run with --root pointing at a workspace root whose ``scripts/`` holds the
guarded access layer (tests use a tempdir copy of staged-root).

stdlib only. No network. No writes outside --output-dir.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import math
import os
import stat
import sys
from pathlib import Path

SCHEMA = "veritas.weekly_tier_proposal.v1"

# Proof-period admission caps (owner-stated). Tier A/B caps are checked
# against live guarded-SQL counts; the evaluated-scope cap comes from the
# standing provider policy (max_scope_count) via its strict loader.
TIER_A_CAP = 15
TIER_B_CAP = 17

# The contract's 10 promotion proofs, verbatim ("Promotion proof must
# include", docs/tier-entitlement-contract.md). Each card proof carries one
# of these keys, a status in {satisfied, missing, blocked,
# enumerated_exception}, and an evidence pointer. A free-text
# not_applicable value never satisfies a proof.
PROOF_KEYS = (
    "identity_listing_resolution",          # 1. resolved identity/listing vs
                                            #    most recent corporate-action
                                            #    and symbol-change record
    "prior_tier_version",                   # 2. prior effective tier+version
    "thesis_lineage_risks_macro_catalysts",  # 3. current thesis, lineage,
                                            #    risks, macro/sector, catalysts
    "destination_enrollments",              # 4. destination-tier producer and
                                            #    consumer enrollment
    "evidence_recency",                     # 5. every evidence class inside
                                            #    its recency limit
    "capacity_or_displacement",             # 6. capacity headroom or approved
                                            #    comparative displacement
    "quote_session_eligibility",            # 7. current quote/session
                                            #    eligibility
    "card_queue_enrollment",                # 8. recommendation-card and queue
                                            #    enrollment
    "duplicate_surface_census",             # 9. no competing tier owner
    "rollback_crashrecovery_validation_audit",  # 10. rollback, crash-recovery,
                                            #    validation, audit proof
)

PROOF_STATUSES = ("satisfied", "missing", "blocked",
                  "enumerated_exception")

CANON_DB_REL = "state/finance/finance-canon.sqlite"
THESIS_DIR_REL = "state/finance/thesis"
THESIS_SCHEMA = "veritas.thesis_record.v1"
METRICS_REL = "tmp/fundamental-metrics-current.json"
CONTROLLER_REL = "tmp/alert-level-freshness-controller.json"

# Band-before-promotion: a promoted-from-C reference row must carry a
# phase4_onboarding block this fresh relative to the packet as_of date.
ONBOARDING_MAX_AGE_DAYS = 14

# Screening rank formula (documented; deterministic):
#   completeness = 2*clean + 1*partial + count of non-null core fields
#   composite    = mean(available per-field percentile ranks among
#                  screened Tier C names with non-null values, ties
#                  averaged) * (non_null_fields / 3)
#   order key    = (-completeness, -composite, ticker)
CORE_QUALITY_FIELDS = ("revenue_yoy_pct", "operating_margin_pct",
                       "fcf_yield_pct")
MISSING_QUALITY_PENALTY = -1000.0

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_BLOCKED = 3


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def _phoenix_today() -> str:
    """Default packet date: America/Phoenix via fixed UTC-7 offset
    (Phoenix has no DST; avoids a tzdata dependency on Windows)."""
    return (_dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(hours=7)
            ).date().isoformat()


def _utc_today() -> str:  # retained alias; default is Phoenix (P4)
    return _phoenix_today()


def _parse_date(value: str):
    try:
        return _dt.date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _proof(status: str, detail: str, evidence: str = "",
           exception_reason: str = "", classes: dict | None = None
           ) -> dict:
    assert status in PROOF_STATUSES, status
    slot: dict = {"status": status, "detail": detail,
                  "evidence": evidence}
    if status == "enumerated_exception":
        slot["exception_reason"] = exception_reason
    if classes is not None:
        slot["classes"] = classes
    return slot


def _num(value):
    try:
        number = None if value is None else float(value)
    except (TypeError, ValueError):
        return None
    return number if number is not None and math.isfinite(number) else None


def _is_reparse_point(path: Path) -> bool:
    try:
        info = os.lstat(path)
    except OSError:
        return False
    return bool(
        getattr(info, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    ) or path.is_symlink()


def resolve_output_dir(root: Path, value: str | Path) -> Path:
    """Resolve output under a physical, non-reparse <root>/tmp owner."""
    root = root.resolve()
    tmp_path = root / "tmp"
    if _is_reparse_point(tmp_path):
        raise ValueError("<root>/tmp must not be a link or junction")
    tmp_root = tmp_path.resolve()
    raw = Path(value)
    candidate = (raw if raw.is_absolute() else root / raw).resolve()
    try:
        candidate.relative_to(tmp_root)
    except ValueError as exc:
        raise ValueError(
            "--output-dir must resolve under <root>/tmp: %s" % candidate
        ) from exc
    return candidate


def refuse_forbidden_markdown(path: Path, what: str) -> Path:
    """Narrow refusal for the owner digest: allow .md under --output-dir,
    but never under '03. Alerts and Recommendations/' or alert-register
    (Alert Bands / Invalidation Register) paths.

    NOTE: g6_yahoo32_sql_apply.refuse_markdown_path is intentionally NOT
    reused here: it refuses every .md target, and the owner digest .md is a
    required deliverable of this job. The digest still never touches canon
    or alert-register surfaces.
    """
    s = path.as_posix().lower()
    if any(seg.lower().startswith("03.") for seg in path.parts):
        raise ValueError("%s resolves into 03. Alerts dir: %s" % (what, path))
    if "alert bands" in s or "invalidation register" in s:
        raise ValueError("%s touches forbidden alert-register path: %s"
                         % (what, path))
    return path


# --------------------------------------------------------------------------
# guarded inputs (read-only; fail closed)
# --------------------------------------------------------------------------

class BlockedPacket(Exception):
    pass


def load_guarded(root: Path):
    """Import staged scripts and return (fsca, depp) bound to root.

    Inserting <root>/scripts first on sys.path makes the access module's
    internal ROOT resolve to the (copied) workspace root under test.
    """
    scripts = root / "scripts"
    sys.path.insert(0, str(scripts))
    try:
        # Fresh exec per root (see tier_membership_writer.staged_modules
        # for why the sys.modules pop matters with multiple roots).
        for name in ("alerts_os_sql_retirement_policy",
                     "market_data_utils",
                     "dynamic_entitlement_provider_policy",
                     "finance_sql_canon_access"):
            sys.modules.pop(name, None)
        import finance_sql_canon_access as fsca  # type: ignore
        import dynamic_entitlement_provider_policy as depp  # type: ignore
    finally:
        try:
            sys.path.remove(str(scripts))
        except ValueError:
            pass
    return fsca, depp


def read_json_ro(path: Path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def load_theses(root: Path) -> tuple[dict, list[str]]:
    """Read-only per-name thesis records; only schema-valid records count."""
    tdir = root / THESIS_DIR_REL
    theses: dict = {}
    debt: list[str] = []
    try:
        files = sorted(tdir.glob("*.json"))
    except OSError:
        files = []
    if not files:
        debt.append("thesis_dir_empty_or_missing:%s" % tdir.as_posix())
        return theses, debt
    for fp in files:
        data = read_json_ro(fp)
        if not isinstance(data, dict):
            debt.append("thesis_unparseable:%s" % fp.name)
            continue
        if data.get("schema") != THESIS_SCHEMA:
            continue  # schema document itself, not a thesis record
        t = str(data.get("ticker") or fp.stem).upper()
        theses[t] = data
    return theses, debt


def index_rows(doc, key="ticker") -> dict:
    out: dict = {}
    rows = (doc or {}).get("rows") if isinstance(doc, dict) else None
    if isinstance(rows, list):
        for rec in rows:
            if isinstance(rec, dict) and rec.get(key):
                out[str(rec[key]).upper()] = rec
    return out


# --------------------------------------------------------------------------
# band readiness (band-before-promotion)
# --------------------------------------------------------------------------

def band_readiness(ticker: str, ref_records: dict, as_of: str) -> dict:
    """has_reference_row, phase4_onboarding presence/age, confidence."""
    rec = ref_records.get(ticker)
    info = {"ticker": ticker, "has_reference_row": rec is not None,
            "onboarding_present": False, "band_packet_as_of_date": None,
            "onboarding_age_days": None, "confidence": None,
            "fresh_onboarded_band": False}
    if rec is None:
        return info
    info["confidence"] = rec.reference_confidence
    raw = rec.raw_json or {}
    ob = raw.get("phase4_onboarding")
    if isinstance(ob, dict):
        info["onboarding_present"] = True
        asof = _parse_date(as_of)
        pkt = ob.get("band_packet_as_of_date")
        info["band_packet_as_of_date"] = pkt
        pkt_d = _parse_date(pkt) if pkt else None
        if asof and pkt_d:
            info["onboarding_age_days"] = (asof - pkt_d).days
    fresh = (info["onboarding_present"]
             and info["onboarding_age_days"] is not None
             and 0 <= info["onboarding_age_days"] <= ONBOARDING_MAX_AGE_DAYS
             and info["confidence"] is not None)
    info["fresh_onboarded_band"] = bool(fresh)
    return info


# --------------------------------------------------------------------------
# evidence recency: six-class breakdown (P1). SQL stale_families_json is a
# frozen 2026-08-30 migration label and NEVER decides recency; it is only
# reported as sql_stale_label. Quote/session is current when it is the
# last completed session with the market closed. The controller label alone
# is insufficient: quote_data_date must match the open session date or fall
# within the bounded closed-market window. A class with no dated recency
# source in the inputs is missing. Overall recency is satisfied only if all
# six classes are satisfied.
# --------------------------------------------------------------------------

RECENCY_CLASSES = ("quote_session", "official_filing_review",
                   "fundamental_packet", "macro_overlay",
                   "catalyst_event", "analyst_context")


def recency_breakdown(ticker: str, ctl_row, metrics, thesis,
                      sql_stale_label, as_of: str) -> dict:
    """Return only recency that the supplied dated inputs actually prove."""
    classes = {}
    as_of_date = _parse_date(as_of)
    cal = str((ctl_row or {}).get("quote_calendar_status") or "")
    qfresh = str((ctl_row or {}).get("quote_freshness_status") or "")
    window = str((ctl_row or {}).get("market_session_window") or "")
    quote_date = _parse_date((ctl_row or {}).get("quote_data_date"))
    quote_age = ((as_of_date - quote_date).days
                 if as_of_date and quote_date else None)
    current_open = (cal == "current_market_session"
                    and quote_age == 0)
    current_closed = (
        cal == "current_last_completed_session"
        and window == "market_closed_weekend_or_holiday"
        and quote_age is not None
        and 0 <= quote_age <= 4
    )
    if ctl_row is None:
        quote_status = "missing"
        quote_reason = "no controller row in inputs"
    elif current_open or current_closed:
        quote_status = "satisfied"
        quote_reason = (
            "calendar=%s freshness=%s window=%s data_date=%s age_days=%s"
            % (cal, qfresh, window, (ctl_row or {}).get("quote_data_date"),
               quote_age)
        )
    else:
        quote_status = "missing"
        quote_reason = (
            "calendar/date proof failed: calendar=%s freshness=%s window=%s "
            "data_date=%s age_days=%s" % (
                cal or "none", qfresh or "none", window or "none",
                (ctl_row or {}).get("quote_data_date"), quote_age)
        )
    classes["quote_session"] = {
        "status": quote_status, "reason": quote_reason}
    classes["official_filing_review"] = {
        "status": "missing",
        "reason": "no_recency_source_in_inputs: no filing-review "
                    "recency source"}

    m = metrics or {}
    dq = str(m.get("data_quality") or "unknown")
    present = [f for f in CORE_QUALITY_FIELDS if _num(m.get(f)) is not None]
    absent = [f for f in CORE_QUALITY_FIELDS if _num(m.get(f)) is None]
    metrics_period = str(m.get("period_end") or "")
    thesis_period = str((thesis or {}).get("fundamentals_period_end") or "")
    classes["fundamental_packet"] = {
        "status": "missing",
        "reason": "period/source presence is not a recency proof: "
                  "metrics_period=%s thesis_period=%s match=%s "
                  "data_quality=%s present=%s null=%s; no input proves this "
                  "is the most recent completed reporting period" % (
                      metrics_period or "none", thesis_period or "none",
                      bool(metrics_period and metrics_period == thesis_period),
                      dq, present, absent)}

    classes["macro_overlay"] = {
        "status": "missing",
        "reason": "no_recency_source_in_inputs: no dated macro-overlay "
                    "source"}
    dated = [c for c in ((thesis or {}).get("catalysts") or [])
             if isinstance(c, dict) and c.get("event")
             and _parse_date(c.get("expected_date"))]
    sourced_evidence = [
        e for e in ((thesis or {}).get("evidence") or [])
        if isinstance(e, dict) and e.get("source") and _parse_date(e.get("as_of"))
    ]
    classes["catalyst_event"] = {
        "status": "missing",
        "reason": "dated presence is not a recency proof: catalysts=%d "
                  "named_dated_sources=%d; no input proves next-event "
                  "completeness plus material events since the last session"
                  % (len(dated), len(sourced_evidence))}
    classes["analyst_context"] = {
        "status": "missing",
        "reason": "no_recency_source_in_inputs: no analyst-context "
                    "source"}
    overall = ("satisfied" if all(
        c["status"] == "satisfied" for c in classes.values())
        else "missing")
    return {"ticker": ticker, "overall": overall, "classes": classes,
            "sql_stale_label": list(sql_stale_label or []),
            "sql_stale_label_note": "frozen 2026-08-30 migration label; "
                                      "reported only, never decides "
                                      "recency"}


# --------------------------------------------------------------------------
# screening rank: percentile composite (P3). Raw percentage sums let one
# outlier dominate, so each core field is percentile-ranked (average ranks
# for ties, 0..1) among screened Tier C names with a non-null value;
# composite = mean(available percentiles) * (non_null_fields / 3);
# order (-completeness, -composite, ticker). Raw values and per-field
# percentiles stay in screen_reason.
# --------------------------------------------------------------------------

def screen_score(ticker: str, metrics: dict | None) -> dict:
    m = metrics or {}
    dq = str(m.get("data_quality") or "")
    completeness = (2 if dq == "clean" else 1 if dq == "partial" else 0)
    raws = {}
    for field in CORE_QUALITY_FIELDS:
        v = _num(m.get(field))
        if v is not None:
            completeness += 1
        raws[field] = v
    return {"ticker": ticker, "completeness": completeness,
            "raws": raws, "data_quality": dq or "unknown"}


def rank_screened(scored: list[dict]) -> list[dict]:
    """Attach composite + order key; deterministic."""
    by_field: dict[str, list[float]] = {}
    for field in CORE_QUALITY_FIELDS:
        vals = sorted(s["raws"][field] for s in scored
                      if s["raws"][field] is not None)
        by_field[field] = vals

    def pct(field, v):
        vals = by_field[field]
        n = len(vals)
        if n == 0 or v is None:
            return None
        below = sum(1 for x in vals if x < v)
        equal = sum(1 for x in vals if x == v)
        return (below + (equal - 1) / 2.0 + 0.5) / n \
            if n > 1 else 1.0

    for s in scored:
        pcts = {}
        for field in CORE_QUALITY_FIELDS:
            p = pct(field, s["raws"][field])
            if p is not None:
                pcts[field] = round(p, 4)
        k = len(pcts)
        comp = (sum(pcts.values()) / k * (k / 3.0)) if k else 0.0
        s["percentiles"] = pcts
        s["composite"] = round(comp, 4)
        parts = []
        for field in CORE_QUALITY_FIELDS:
            v = s["raws"][field]
            if v is None:
                parts.append("%s=null" % field)
            else:
                parts.append("%s=%s[p%.3f]" % (
                    field, v, pcts[field]))
        s["reason"] = ("completeness=%d composite=%.3f (%s)" % (
            s["completeness"], s["composite"], "; ".join(parts)))
        s["order"] = (-s["completeness"], -s["composite"],
                        s["ticker"])
    return sorted(scored, key=lambda s: s["order"])


# --------------------------------------------------------------------------
# packet assembly
# --------------------------------------------------------------------------

def _incumbent_card(ticker, member, thesis, ctl_row, sql_fresh, metrics,
                    band, dest_headroom, cap_note, role, as_of) -> dict:
    proofs = {}
    proofs["identity_listing_resolution"] = _proof(
        "missing",
        "guarded-SQL identity row present with yfinance_symbol=%s, but the "
        "most recent corporate-action/symbol-change record is not in the "
        "job inputs" % (member.yfinance_symbol,),
        evidence="guarded_sql:universe_membership+securities")
    proofs["prior_tier_version"] = _proof(
        "missing",
        "prior effective tier %s is recorded, but universe_membership has "
        "no version witness and this contract does not authorize treating "
        "tier value alone as a version exception" % (member.tier,),
        evidence="guarded_sql:universe_membership.tier")
    accepted = (thesis or {}).get("status") == "accepted"
    risks = (thesis or {}).get("key_risks") or []
    catalysts = (thesis or {}).get("catalysts") or []
    lineage = [e for e in ((thesis or {}).get("evidence") or [])
               if isinstance(e, dict) and e.get("source")
               and _parse_date(e.get("as_of"))]
    regime_fit = (thesis or {}).get("regime_fit")
    proofs["thesis_lineage_risks_macro_catalysts"] = _proof(
        "missing",
        "thesis presence is not full proof completion: status=%s risks=%d "
        "catalysts=%d named_dated_sources=%d regime_fit=%s; no dedicated "
        "input verifies official-source class and current macro/sector "
        "sensitivity" % (
            (thesis or {}).get("status", "none"),
            len(risks) if isinstance(risks, list) else 0,
            len(catalysts) if isinstance(catalysts, list) else 0,
            len(lineage), bool(regime_fit)),
        evidence="state/finance/thesis/%s.json" % ticker)
    proofs["destination_enrollments"] = _proof(
        "blocked",
        "producer/consumer enrollment happens in the owner-gated apply "
        "(tier_membership_writer); a proposal cannot enroll",
        evidence="phase4-unified-plan:Stage 1")
    sql_label = (sql_fresh.stale_families if sql_fresh else []) or []
    rec = recency_breakdown(
        ticker, ctl_row, metrics, thesis, sql_label, as_of)
    proofs["evidence_recency"] = _proof(
        rec["overall"],
        "six-class recency: %s; sql_stale_label=%s (frozen label, "
        "reported only)" % (
            ", ".join("%s=%s" % (k, v["status"])
                        for k, v in rec["classes"].items()),
            sql_label or "none"),
        evidence="freshness-controller+metrics+thesis",
        classes=rec["classes"])
    proofs["capacity_or_displacement"] = _proof(
        "satisfied" if dest_headroom else "blocked", cap_note,
        evidence="tier caps + provider policy max_scope_count")
    qclass = rec["classes"]["quote_session"]
    proofs["quote_session_eligibility"] = _proof(
        qclass["status"],
        "%s; alert_fire_eligible=%s" % (
            qclass["reason"], (ctl_row or {}).get("alert_fire_eligible")),
        evidence="freshness-controller")
    proofs["card_queue_enrollment"] = _proof(
        "blocked",
        "card/queue enrollment happens in the owner-gated apply; a "
        "proposal cannot enroll",
        evidence="phase4-unified-plan:Stage 1")
    proofs["duplicate_surface_census"] = _proof(
        "missing",
        "guarded SQL is the tier owner used by this read, but the required "
        "competing-surface census is not present in the job inputs",
        evidence="guarded_sql:universe_membership.tier")
    proofs["rollback_crashrecovery_validation_audit"] = _proof(
        "blocked",
        "rollback/crash-recovery/validation/audit proof is produced by "
        "the owner-gated apply, not the proposal",
        evidence="tier_membership_writer audit+rollback")
    return {"ticker": ticker, "role": role,
            "prior_tier": member.tier, "proofs": proofs,
            "band": band}


def build_packet(root: Path, as_of: str, max_candidates: int,
                 fsca, depp) -> dict:
    repair_debt: list[str] = []
    db = root / CANON_DB_REL
    access = fsca.FinanceSqlCanonAccess(db)
    try:
        validation = access.validate()
    except Exception as exc:
        raise BlockedPacket("canon guard raised: %s" % (exc,))
    if validation.get("status") != "ok":
        raise BlockedPacket("canon guard not ok: %s" % (
            validation.get("errors"),))
    try:
        policy = depp.load_provider_policy(root)
    except Exception as exc:  # fail closed on policy problems
        raise BlockedPacket("provider policy unloadable: %s" % (exc,))
    max_scope = policy.max_scope_count
    try:
        scope = access.dynamic_entitlement_scope()
        members = access.universe_memberships()
        ref_records = access.reference_level_records()
    except Exception as exc:
        raise BlockedPacket("guarded read failed: %s" % (exc,))

    theses, thesis_debt = load_theses(root)
    repair_debt.extend(thesis_debt)
    metrics_doc = read_json_ro(root / METRICS_REL)
    if metrics_doc is None:
        repair_debt.append("metrics_missing:%s" % METRICS_REL)
    ctl_doc = read_json_ro(root / CONTROLLER_REL)
    if ctl_doc is None:
        repair_debt.append("controller_missing:%s" % CONTROLLER_REL)
    metrics_by = index_rows(metrics_doc)
    ctl_by = index_rows(ctl_doc)

    tiers: dict[str, list[str]] = {"A": [], "B": [], "C": []}
    for t, row in members.items():
        if row.tier in tiers:
            tiers[row.tier].append(t)
    count_a, count_b, count_c = (len(tiers["A"]), len(tiers["B"]),
                                 len(tiers["C"]))
    evaluated = count_a + count_b

    def flag(count, cap, margin=0):
        if count >= cap:
            return "full" if count == cap else "over_cap"
        if margin and count >= cap - margin:
            return "approaching"
        return "ok"

    cap_flags = {
        "tier_a": {"count": count_a, "cap": TIER_A_CAP,
                   "headroom": TIER_A_CAP - count_a,
                   "state": flag(count_a, TIER_A_CAP)},
        "tier_b": {"count": count_b, "cap": TIER_B_CAP,
                   "headroom": TIER_B_CAP - count_b,
                   "state": flag(count_b, TIER_B_CAP)},
        "evaluated_scope": {
            "count": evaluated, "cap": max_scope,
            "headroom": max_scope - evaluated,
            "state": flag(evaluated, max_scope, margin=8),
            "definition": "tier A+B count vs provider-policy "
                          "max_scope_count"},
    }
    a_headroom = count_a < TIER_A_CAP
    b_headroom = count_b < TIER_B_CAP
    evaluated_headroom = evaluated < max_scope
    b_admission_headroom = b_headroom and evaluated_headroom

    sql_fresh_cache: dict = {}

    def sql_fresh(t):
        if t not in sql_fresh_cache:
            try:
                sql_fresh_cache[t] = access.evidence_freshness(t)
            except Exception:
                sql_fresh_cache[t] = None
        return sql_fresh_cache[t]

    incumbents: list[dict] = []
    demotions: list[dict] = []
    # Incumbent review: every A/B name gets an evidence card; demotion only
    # on sourced sustained impairment (retired thesis with proponent+source,
    # recorded invalidation breach, or sourced impairment flag whose sole
    # source is not a beneficiary of the vacated capacity).
    for tier in ("A", "B"):
        for t in sorted(tiers[tier]):
            member = members[t]
            thesis = theses.get(t)
            band = band_readiness(t, ref_records, as_of)
            # P5: incumbents are covered by weekly renewal; show the
            # row's level pin age, never imply they need onboarding.
            ctl = ctl_by.get(t)
            band["band_owner"] = "weekly_renewal"
            band["level_as_of_utc"] = (ctl or {}).get("level_as_of_utc")
            band["quote_as_of_utc"] = (ctl or {}).get("quote_as_of_utc")
            band["quote_data_date"] = (ctl or {}).get("quote_data_date")
            card = _incumbent_card(
                t, member, thesis, ctl, sql_fresh(t), metrics_by.get(t),
                band,
                a_headroom if tier == "B" else b_headroom,
                "Tier %s %d/%d" % (tier, len(tiers[tier]),
                                   TIER_A_CAP if tier == "A" else TIER_B_CAP),
                "incumbent", as_of)
            card["card_id"] = "card_%s_%s_incumbent" % (as_of, t)
            demote_ev = impairment_evidence(t, member, thesis,
                                            metrics_by.get(t))
            if demote_ev["sustained"]:
                card["role"] = "demotion_proposed"
                card["proposed_tier"] = ("B" if tier == "A"
                                            else "C")
                card["demotion_evidence"] = demote_ev
                demotions.append(card)
            else:
                if demote_ev["note"]:
                    repair_debt.append(demote_ev["note"])
                # P1: the SQL stale_families value is a frozen 2026-08-30
                # migration label; it is reported on the card only and
                # never cited as staleness. Missing thesis is repair debt.
                if thesis is None:
                    repair_debt.append(
                        "repair_debt:%s: no thesis record in inputs; "
                        "incumbent review incomplete until thesis "
                        "present; never a demotion reason." % t)
                if ctl is None:
                    repair_debt.append(
                        "repair_debt:%s: no controller row in inputs; "
                        "quote_session class unprovable; never a "
                        "demotion reason." % t)
            if tier == "B":
                card["b_to_a_case"] = advancement_case(
                    t, card, thesis, metrics_by.get(t), a_headroom,
                    count_a)
            if tier == "B":
                pass  # b_to_a_case already set above
            elif card["role"] != "demotion_proposed":
                card["b_to_a_case"] = None
                card["proposed_tier"] = None
            else:
                card["b_to_a_case"] = None
            incumbents.append(card)

    # Tier C screening: deterministic rank over SQL tier-C names with
    # fundamental-metric rows; top --max-candidates screened. Tier C has no
    # accepted thesis, so at most "promotion_candidate: thesis_required";
    # without a fresh onboarded band the status is "needs_candidate_band"
    # (next action: promotion_candidate_band.py then
    # reference_level_onboarding_writer.py), never promotable.
    scored = []
    for t in sorted(tiers["C"]):
        m = metrics_by.get(t)
        if m is None:
            repair_debt.append("repair_debt:%s: no fundamental-metrics row; "
                               "unscreenable; repair debt." % t)
            continue
        scored.append(screen_score(t, m))
    ranked = rank_screened(scored)
    for rank, s in enumerate(ranked, start=1):
        s["screen_rank"] = rank
    screened = ranked[:max_candidates]
    # P2: challengers get the same 10-proof card builder as incumbents
    # (thesis missing for C names; capacity blocked with the swap note).
    candidates: list[dict] = []
    for s in screened:
        t = s["ticker"]
        band = band_readiness(t, ref_records, as_of)
        band["band_owner"] = "candidate_band_required"
        if band["fresh_onboarded_band"]:
            status = ("promotion_candidate:thesis_required"
                      if t not in theses or
                      (theses.get(t) or {}).get("status") != "accepted"
                      else "promotion_candidate:capacity_check")
        else:
            status = "needs_candidate_band"
        next_action = ("promotion_candidate_band.py then "
                       "reference_level_onboarding_writer.py"
                       if status == "needs_candidate_band"
                       else "thesis draft + owner acceptance, then band")
        if not b_headroom:
            cap_note = (
                "capacity_blocked: Tier B full/over-cap %d/%d; needs "
                "owner-paired displacement swap" % (count_b, TIER_B_CAP)
            )
        elif not evaluated_headroom:
            cap_note = (
                "capacity_blocked: evaluated scope full/over-cap %d/%d; "
                "needs owner-paired displacement" % (evaluated, max_scope)
            )
        else:
            cap_note = (
                "headroom: Tier B %d and evaluated scope %d"
                % (TIER_B_CAP - count_b, max_scope - evaluated)
            )
        card = _incumbent_card(
            t, members[t], theses.get(t), ctl_by.get(t), None,
            metrics_by.get(t), band, b_admission_headroom, cap_note,
            "challenger", as_of)
        card["card_id"] = "card_%s_%s_candidate" % (as_of, t)
        card["proposed_tier"] = "B"
        card["screen_rank"] = s["screen_rank"]
        card["screen_reason"] = s["reason"]
        card["screen_composite"] = s["composite"]
        card["screen_percentiles"] = s["percentiles"]
        card["status"] = status
        card["capacity"] = cap_note
        card["next_action"] = next_action
        candidates.append(card)

    packet = {
        "schema": SCHEMA,
        "as_of": as_of,
        "authority": {
            "mode": "dry_run",
            "tier_write": False,
            "canon_write": False,
            "schedule_write": False,
            "state_write": False,
            "apply_mode_exists": False,
            "owner_approval_inferred": False,
            "read_path": "scripts/finance_sql_canon_access.py "
                         "(guarded; never raw sqlite)",
            "note": "Proposal evidence only. Every effective tier change "
                    "needs a separate owner approval; nothing here "
                    "authorizes or applies one.",
        },
        "inputs": {
            "root": root.as_posix(),
            "canon_db": CANON_DB_REL,
            "guard_status": validation.get("status"),
            "scope_source": scope.source,
            "scope_fingerprint": scope.fingerprint,
            "tier_breakdown": dict(scope.tier_breakdown),
            "max_scope_count": max_scope,
            "metrics_present": metrics_doc is not None,
            "controller_present": ctl_doc is not None,
            "thesis_records": len(theses),
        },
        "counts": {"tier_a": count_a, "tier_b": count_b,
                   "tier_c": count_c, "evaluated": evaluated},
        "cap_flags": cap_flags,
        "incumbents": incumbents,
        "demotions": demotions,
        "swap_pairs": pair_swaps(incumbents, demotions),
        "candidates": candidates,
        "screened_total": len(scored),
        "max_candidates": max_candidates,
        "repair_debt": sorted(set(repair_debt)),
        "proof_keys": list(PROOF_KEYS),
        "screen_formula": ("completeness=2*clean+1*partial+non-null core "
                           "fields; composite=mean(available per-field "
                           "percentile ranks among screened C, ties "
                           "averaged)*(non_null/3); order=(-completeness,"
                           "-composite,ticker)"),
    }
    return packet


def advancement_case(ticker, card, thesis, metrics, a_headroom,
                   count_a) -> dict:
    """B->A advancement: test (b) — a clear reason intensive coverage
    adds value (accepted thesis + catalysts or distinct value)."""
    proofs = card["proofs"]
    thesis_ok = proofs["thesis_lineage_risks_macro_catalysts"][
        "status"] == "satisfied"
    catalysts = ((thesis or {}).get("catalysts") or [])
    has_catalysts = bool(catalysts)
    sector = str((metrics or {}).get("sector") or "")
    reasons = []
    if thesis_ok:
        reasons.append("accepted thesis with risks+catalysts")
    if has_catalysts:
        reasons.append("%d recorded catalysts" % len(catalysts))
    if sector:
        reasons.append("sector=%s distinct-value review" % sector)
    credible = thesis_ok and (has_catalysts or bool(sector))
    return {
        "credible": credible,
        "reasons": reasons,
        "to_tier": "A",
        "capacity": ("headroom %d" % (TIER_A_CAP - count_a)
                       if a_headroom
                       else "capacity_blocked: Tier A full %d/%d" % (
                           count_a, TIER_A_CAP)),
    }


def pair_swaps(incumbents: list[dict], demotions: list[dict]) -> list[dict]:
    """Pair capacity-blocked B->A advancement cases with demotions that
    free Tier A headroom (demotion from A). Owner must approve both halves;
    the packet only proposes the pairing."""
    pairs = []
    a_demotions = [c for c in demotions if c.get("prior_tier") == "A"]
    idx = 0
    for card in incumbents:
        case = card.get("b_to_a_case") or {}
        if not case.get("credible"):
            continue
        if not str(case.get("capacity", "")).startswith(
                "capacity_blocked"):
            continue
        if idx >= len(a_demotions):
            card["swap_pair"] = None
            continue
        dem = a_demotions[idx]
        idx += 1
        pair = {"advance_card_id": card["card_id"],
                "advance_ticker": card["ticker"],
                "demote_card_id": dem["card_id"],
                "demote_ticker": dem["ticker"],
                "tier": "A",
                "note": "owner must approve both halves; either half "
                          "alone stays capacity_blocked"}
        card["swap_pair"] = pair
        pairs.append(pair)
    return pairs


def impairment_evidence(ticker, member, thesis, metrics) -> dict:
    """Sustained-impairment check. Returns {sustained, proponent, source,
    note}. Staleness or missing evidence never counts."""
    m = metrics or {}
    th = thesis or {}
    # 1. retired thesis naming a proponent and impairment source
    if th.get("status") == "retired":
        prop = th.get("demotion_proponent") or ""
        src = th.get("impairment_evidence_source") or ""
        if prop and src:
            return {"sustained": True, "proponent": prop,
                    "source": src, "note": "",
                    "basis": "retired_thesis_with_proponent"}
        return {"sustained": False, "proponent": prop, "source": src,
                "note": "repair_debt:%s: retired thesis lacks named "
                        "proponent/source; demotion not proposed." % ticker,
                "basis": "retired_thesis_unsourced"}
    # 2. thesis-recorded invalidation breach with named source
    breach = th.get("invalidation_breach") or {}
    if isinstance(breach, dict) and breach.get("breached") is True:
        src = breach.get("source") or ""
        prop = breach.get("proponent") or ""
        if prop and src:
            return {"sustained": True, "proponent": prop,
                    "source": src, "note": "",
                    "basis": "recorded_invalidation_breach"}
        return {"sustained": False, "proponent": prop, "source": src,
                "note": "repair_debt:%s: breach claim lacks named "
                        "proponent/source." % ticker,
                "basis": "breach_unsourced"}
    # 3. sourced impairment flag outside the thesis
    if m.get("sustained_impairment") is True:
        src = m.get("impairment_source") or ""
        prop = m.get("impairment_proponent") or src
        beneficiary = m.get("impairment_beneficiary") or ""
        if src and beneficiary and src == beneficiary:
            return {"sustained": False, "proponent": prop,
                    "source": src,
                    "note": "repair_debt:%s: sole impairment source %s "
                            "benefits from vacated capacity; not sole "
                            "evidence." % (ticker, src),
                    "basis": "beneficiary_sole_source"}
        if src:
            return {"sustained": True, "proponent": prop,
                    "source": src, "note": "",
                    "basis": "sourced_impairment_flag"}
        return {"sustained": False, "proponent": prop, "source": src,
                "note": "repair_debt:%s: impairment flag without named "
                        "source." % ticker,
                "basis": "impairment_unsourced"}
    return {"sustained": False, "proponent": "", "source": "",
            "note": "", "basis": "none"}


# --------------------------------------------------------------------------
# renderers (write only under output_dir)
# --------------------------------------------------------------------------

def render_markdown(packet: dict) -> str:
    L: list[str] = []
    A = packet["authority"]
    L.append("# Weekly tier proposal packet — %s" % packet["as_of"])
    L.append("")
    L.append("Status: DRAFT evidence only. tier_write=%s canon_write=%s "
             "owner_approval_inferred=%s. No apply mode exists."
             % (A["tier_write"], A["canon_write"],
                A["owner_approval_inferred"]))
    L.append("")
    L.append("Guard: %s; scope fingerprint `%s`; breakdown %s."
             % (packet["inputs"].get("guard_status", "blocked"),
                packet["inputs"].get("scope_fingerprint"),
                packet["inputs"].get("tier_breakdown")))
    L.append("")
    L.append("## Summary")
    L.append("")
    c = packet["counts"]
    if packet.get("status") == "blocked":
        L.append("BLOCKED: %s" % packet.get("block_reason"))
        L.append("")
        L.append("## Authority")
        L.append("")
        L.append("```json")
        L.append(json.dumps(A, indent=2, sort_keys=True))
        L.append("```")
        L.append("")
        return "\n".join(L)
    L.append("Counts: A=%d B=%d C=%d evaluated(A+B)=%d; incumbents=%d; "
             "demotions=%d; swap_pairs=%d; screened C=%d; candidates=%d; "
             "repair debt=%d."
             % (c["tier_a"], c["tier_b"], c["tier_c"], c["evaluated"],
                len(packet["incumbents"]), len(packet["demotions"]),
                len(packet.get("swap_pairs", [])),
                packet["screened_total"], len(packet["candidates"]),
                len(packet["repair_debt"])))
    for key in ("tier_a", "tier_b", "evaluated_scope"):
        f = packet["cap_flags"][key]
        L.append("- cap %s: count=%s cap=%s headroom=%s state=%s" % (
            key, f["count"], f["cap"], f["headroom"], f["state"]))
    L.append("")
    L.append("## Incumbents (%d)" % len(packet["incumbents"]))
    L.append("")
    for card in packet["incumbents"]:
        proofs = card["proofs"]
        sat = sum(1 for p in proofs.values()
                  if p["status"] == "satisfied")
        L.append("- %s (Tier %s, role=%s): %d/10 proofs satisfied; band "
                 "row=%s onboarded-fresh=%s."
                 % (card["ticker"], card["prior_tier"], card["role"], sat,
                    card["band"]["has_reference_row"],
                    card["band"]["fresh_onboarded_band"]))
    L.append("")
    L.append("## Candidates (%d)" % len(packet["candidates"]))
    L.append("")
    for cand in packet["candidates"]:
        L.append("- rank %d %s -> %s: %s; %s; band row=%s onboarded-fresh=%s"
                 % (cand["screen_rank"], cand["ticker"],
                    cand["proposed_tier"], cand["status"],
                    cand["capacity"],
                    cand["band"]["has_reference_row"],
                    cand["band"]["fresh_onboarded_band"]))
        L.append("  why ranked: %s" % cand["screen_reason"])
        L.append("  next: %s" % cand["next_action"])
    L.append("")
    L.append("## Repair debt (%d)" % len(packet["repair_debt"]))
    L.append("")
    for r in packet["repair_debt"]:
        L.append("- %s" % r)
    L.append("")
    L.append("## Authority")
    L.append("")
    L.append("```json")
    L.append(json.dumps(A, indent=2, sort_keys=True))
    L.append("```")
    L.append("")
    return "\n".join(L)


def write_packet(packet: dict, root: Path, output_dir: Path) -> dict:
    output_dir = resolve_output_dir(root, output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = "weekly_tier_proposal_%s" % packet["as_of"]
    json_path = (output_dir / (stem + ".json")).resolve()
    md_path = (output_dir / (stem + ".md")).resolve()
    tmp_root = (root.resolve() / "tmp").resolve()
    for path in (json_path, md_path):
        try:
            path.relative_to(tmp_root)
        except ValueError as exc:
            raise ValueError("packet output escaped <root>/tmp: %s" % path) from exc
        if path.parent != output_dir.resolve():
            raise ValueError(
                "packet filename escaped --output-dir: %s" % path)
    refuse_forbidden_markdown(md_path, "owner digest")
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(packet, fh, indent=2, sort_keys=True)
        fh.write("\n")
    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write(render_markdown(packet))
    return {"json": str(json_path), "markdown": str(md_path)}


def blocked_packet(root: Path, as_of: str, reason: str) -> dict:
    return {
        "schema": SCHEMA,
        "as_of": as_of,
        "status": "blocked",
        "block_reason": reason,
        "authority": {
            "mode": "dry_run",
            "tier_write": False,
            "canon_write": False,
            "schedule_write": False,
            "state_write": False,
            "apply_mode_exists": False,
            "owner_approval_inferred": False,
            "read_path": "scripts/finance_sql_canon_access.py "
                         "(guarded; never raw sqlite)",
        },
        "inputs": {"root": root.as_posix(), "guard_status": "blocked"},
        "counts": {}, "cap_flags": {}, "incumbents": [],
        "demotions": [], "swap_pairs": [], "candidates": [],
        "repair_debt": [reason],
        "proof_keys": list(PROOF_KEYS),
    }


# --------------------------------------------------------------------------
# CLI — dry-run only; no apply mode exists by design
# --------------------------------------------------------------------------

def parse_args(argv: list[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Weekly tier proposal job v2 (drafting only; no apply).")
    ap.add_argument("--root", required=True,
                    help="Workspace root holding scripts/, state/, tmp/.")
    ap.add_argument("--as-of", default=_phoenix_today(),
                    help="Packet date YYYY-MM-DD (default: today in "
                         "America/Phoenix, fixed UTC-7).")
    ap.add_argument("--max-candidates", type=int, default=10,
                    help="Max screened Tier C candidates (default 10).")
    ap.add_argument("--output-dir", default=None,
                    help="Packet output dir (default: <root>/tmp/"
                         "p4-2-writer-lane-20260927/slice-a/v2/output/"
                         "<as-of>).")
    args = ap.parse_args(argv)
    if args.max_candidates < 0:
        ap.error("--max-candidates must be >= 0")
    if (len(str(args.as_of)) != 10
            or _parse_date(args.as_of) is None
            or _parse_date(args.as_of).isoformat() != args.as_of):
        ap.error("--as-of must be exactly YYYY-MM-DD")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    root = Path(args.root).resolve()
    if not root.is_dir():
        print("error: --root is not a directory: %s" % root,
              file=sys.stderr)
        return EXIT_USAGE
    raw_out = (Path(args.output_dir) if args.output_dir
               else root / "tmp" / "p4-2-writer-lane-20260927"
               / "slice-a" / "v2" / "output" / args.as_of)
    try:
        out = resolve_output_dir(root, raw_out)
    except ValueError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return EXIT_USAGE
    fsca, depp = load_guarded(root)
    try:
        packet = build_packet(root, args.as_of, args.max_candidates,
                              fsca, depp)
    except BlockedPacket as exc:
        packet = blocked_packet(root, args.as_of, str(exc))
        written = write_packet(packet, root, out)
        print(json.dumps({"status": "blocked_packet_written",
                          "reason": str(exc),
                          "authority": packet["authority"],
                          "written": written},
                         indent=2, sort_keys=True))
        return EXIT_BLOCKED
    written = write_packet(packet, root, out)
    print(json.dumps({"status": "draft_packet_written",
                      "authority": packet["authority"],
                      "counts": packet["counts"],
                      "cap_flags": {k: v["state"] for k, v in
                                    packet["cap_flags"].items()},
                      "incumbents": len(packet["incumbents"]),
                      "demotions": len(packet["demotions"]),
                      "swap_pairs": len(packet.get("swap_pairs", [])),
                      "candidates": len(packet["candidates"]),
                      "repair_debt": len(packet["repair_debt"]),
                      "written": written}, indent=2, sort_keys=True))
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
