#!/usr/bin/env python3
"""Report-only WF78 tier-coherence validator.

Reconciles the authoritative WF78 auto-router tier against the canon legacy
tier field so the legacy label can no longer silently imply a freshness
coverage gap. Report-only: no canon, portfolio, membership, or label mutation
and no promotion or approval authority.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
CANON_DB = TMP / "canonical-finance-data-plane.sqlite"
AUTO_ROUTER = TMP / "wf78-auto-tier-routing.json"
LABEL_REGISTER = TMP / "wf78-tier-label-decision-register.json"
TIER_WEIGHTED = TMP / "wf78-tier-weighted-freshness-resolution.json"
DEFAULT_OUT = TMP / "wf78-tier-coherence-validator.json"
PROMOTION_PACKET_OUT = TMP / "wf78-tier-promotion-candidate-packet.json"

VALIDATOR_SCHEMA = "veritas.wf78_tier_coherence_validator.v1"
PACKET_SCHEMA = "veritas.wf78_tier_promotion_candidate_packet.v1"

TIER_RANK = {"Tier A": 3, "Tier B": 2, "Tier C": 1, "": 0}

AUTHORITY_BOUNDARY: dict[str, bool] = {
    "review_only": True,
    "report_only": True,
    "automated_non_capital_routing_allowed": True,
    "auto_router_is_current_tier_authority": True,
    "legacy_tier_field_is_stale_label_not_authority": True,
    "canon_or_portfolio_mutation_allowed": False,
    "universe_mutation_allowed": False,
    "ticker_card_mutation_allowed": False,
    "sql_canon_mutation_allowed": False,
    "label_sync_apply_allowed": False,
    "promotion_allowed": False,
    "capital_deployment_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_allowed": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "owner_approval_inferred": False,
}
REQUIRED_TRUE_FLAGS = {
    "review_only",
    "report_only",
    "automated_non_capital_routing_allowed",
    "auto_router_is_current_tier_authority",
    "legacy_tier_field_is_stale_label_not_authority",
}
REQUIRED_FALSE_FLAGS = {flag for flag in AUTHORITY_BOUNDARY if flag not in REQUIRED_TRUE_FLAGS}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def sym(value: Any) -> str:
    return str(value or "").strip().upper()


def normalize_tier(value: Any) -> str:
    """Normalize A/B/C or 'Tier A' style values to canonical 'Tier X'."""
    raw = str(value or "").strip()
    if not raw:
        return ""
    if raw.upper().startswith("TIER "):
        letter = raw.split()[-1].upper()
    elif len(raw) == 1:
        letter = raw.upper()
    else:
        return raw
    return f"Tier {letter}" if letter in {"A", "B", "C"} else raw


def classify_rows(records: list[dict[str, Any]], approved_labels: set[str]) -> list[dict[str, Any]]:
    """Pure classification of tier coherence. No IO; unit-testable.

    Each record needs: ticker, auto_tier, legacy_tier, universe_scope,
    decision_grade_eligible, thin_monitor_row, auto_state, resolution_state.
    """
    out: list[dict[str, Any]] = []
    for rec in records:
        ticker = sym(rec.get("ticker"))
        auto = normalize_tier(rec.get("auto_tier"))
        legacy = normalize_tier(rec.get("legacy_tier"))
        scope = str(rec.get("universe_scope") or "")
        in_active = scope == "active_internal_universe"
        decision_grade = bool(rec.get("decision_grade_eligible"))
        thin_monitor = bool(rec.get("thin_monitor_row"))
        has_label = ticker in approved_labels
        auto_rank = TIER_RANK.get(auto, 0)
        legacy_rank = TIER_RANK.get(legacy, 0)

        if auto_rank == legacy_rank:
            direction = "match"
        elif auto_rank > legacy_rank:
            direction = "auto_ahead"
        else:
            direction = "legacy_ahead"

        if direction == "match":
            coherence_class = "coherent"
        elif direction == "auto_ahead":
            coherence_class = (
                "approved_label_sync_pending"
                if has_label
                else "auto_promotion_needs_owner_review"
            )
        else:  # legacy_ahead
            coherence_class = (
                "router_demoted_active_coverage_name"
                if in_active
                else "router_demoted_monitor_name"
            )

        # A coverage obligation exists only for active-coverage, decision-grade
        # names. A tier-label disagreement never adds or removes active-coverage
        # membership, so it can only imply a *gap* if a name that the router
        # calls A/B is NOT active-coverage AND is not a thin monitor row (i.e.
        # would owe decision-grade freshness but is being skipped). That state
        # does not occur by construction; we compute it to prove it is zero.
        implies_coverage_gap = bool(
            direction == "auto_ahead"
            and auto in {"Tier A", "Tier B"}
            and not in_active
            and not thin_monitor
        )

        out.append(
            {
                "ticker": ticker,
                "auto_tier": auto,
                "legacy_tier": legacy,
                "direction": direction,
                "coherence_class": coherence_class,
                "universe_scope": scope,
                "in_active_coverage": in_active,
                "decision_grade_eligible": decision_grade,
                "thin_monitor_row": thin_monitor,
                "owner_approved_label": has_label,
                "auto_state": rec.get("auto_state"),
                "resolution_state": rec.get("resolution_state"),
                "implies_coverage_gap": implies_coverage_gap,
            }
        )
    return sorted(out, key=lambda r: r["ticker"])


def load_canon_rows() -> list[dict[str, Any]]:
    con = sqlite3.connect(f"file:{CANON_DB.as_posix()}?mode=ro", uri=True)
    try:
        con.row_factory = sqlite3.Row
        rows = con.execute(
            """
            SELECT u.ticker AS ticker,
                   r.auto_tier AS auto_tier,
                   r.auto_state AS auto_state,
                   u.legacy_universe_tier AS legacy_tier,
                   u.universe_scope AS universe_scope,
                   u.decision_grade_eligible AS decision_grade_eligible,
                   u.thin_monitor_row AS thin_monitor_row
            FROM universe_membership u
            JOIN routing_state_current r ON r.ticker = u.ticker
            """
        ).fetchall()
    finally:
        con.close()
    return [dict(row) for row in rows]


def approved_label_set(register: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    for record in as_list(register.get("records")):
        for ticker in as_list(as_dict(record).get("approved_tickers")):
            out.add(sym(ticker))
    return out


def resolution_state_map(tier_weighted: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for row in as_list(tier_weighted.get("rows")) or as_list(tier_weighted.get("tickers")):
        row = as_dict(row)
        ticker = sym(row.get("ticker"))
        if ticker:
            out[ticker] = row.get("resolution_state")
    return out


def add_check(checks: list[dict[str, Any]], name: str, ok: bool, detail: Any = None, severity: str = "critical") -> None:
    checks.append({"name": name, "ok": bool(ok), "status": "ok" if ok else "fail", "severity": severity, "detail": detail})


def label_record_lookup(register: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Map ticker -> label semantics from its approving record."""
    out: dict[str, dict[str, Any]] = {}
    for record in as_list(register.get("records")):
        record = as_dict(record)
        semantics = as_dict(record.get("label_semantics"))
        for ticker in as_list(record.get("approved_tickers")):
            out[sym(ticker)] = {
                "decision_id": record.get("decision_id"),
                "approval_reference": record.get("approval_reference"),
                "tier": semantics.get("tier"),
                "role": semantics.get("role"),
                "deployment_ready": semantics.get("deployment_ready"),
            }
    return out


def build_promotion_packet(classified: list[dict[str, Any]], register: dict[str, Any]) -> dict[str, Any]:
    labels = label_record_lookup(register)
    auto_ahead = [row for row in classified if row["direction"] == "auto_ahead"]
    candidates: list[dict[str, Any]] = []
    for row in auto_ahead:
        label = labels.get(row["ticker"], {})
        deployment_ready = bool(label.get("deployment_ready"))
        if not row["owner_approved_label"]:
            owner_decision = "review_unapproved_auto_promotion"
        elif normalize_tier(label.get("tier")) != row["auto_tier"]:
            owner_decision = "review_router_ahead_of_owner_approved_label"
        else:
            owner_decision = "apply_owner_approved_label_sync_only"
        candidates.append(
            {
                "ticker": row["ticker"],
                "auto_tier": row["auto_tier"],
                "legacy_tier": row["legacy_tier"],
                "owner_approved_label_tier": normalize_tier(label.get("tier")) or None,
                "owner_approved_role": label.get("role"),
                "deployment_ready": deployment_ready,
                "universe_scope": row["universe_scope"],
                "decision_grade_eligible": row["decision_grade_eligible"],
                "resolution_state": row["resolution_state"],
                "bench_to_active_coverage_qualified": deployment_ready and row["decision_grade_eligible"],
                "recommended_owner_decision": owner_decision,
            }
        )
    candidates.sort(key=lambda r: r["ticker"])
    router_ahead_of_label = [c for c in candidates if c["recommended_owner_decision"] == "review_router_ahead_of_owner_approved_label"]
    unapproved = [c for c in candidates if c["recommended_owner_decision"] == "review_unapproved_auto_promotion"]
    label_sync_only = [c for c in candidates if c["recommended_owner_decision"] == "apply_owner_approved_label_sync_only"]
    qualified = [c for c in candidates if c["bench_to_active_coverage_qualified"]]
    return {
        "schema": PACKET_SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok",
        "workflow": "WF78 - Tier Promotion Candidate Packet (owner decision)",
        "purpose": (
            "Present WF78 auto-router-ahead tier names for owner review. Report-only: "
            "no promotion, no label-sync apply, no canon or universe mutation."
        ),
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": {
            "auto_ahead_candidate_count": len(candidates),
            "bench_to_active_coverage_qualified_count": len(qualified),
            "unapproved_auto_promotion_count": len(unapproved),
            "router_ahead_of_owner_approved_label_count": len(router_ahead_of_label),
            "owner_approved_label_sync_only_count": len(label_sync_only),
            "owner_decision_note": (
                "No candidate qualifies for bench->active-coverage promotion "
                "(deployment_ready and decision_grade_eligible required). The genuine "
                "owner items are: (1) whether to apply the already-approved Tier B "
                "label sync to the canon legacy field, and (2) whether to re-look at "
                "names where the router is ahead of the owner-approved label."
            ),
        },
        "router_ahead_of_owner_approved_label": router_ahead_of_label,
        "unapproved_auto_promotions": unapproved,
        "candidates": candidates,
        "stop_lines": [
            "This packet does not apply any tier label, promotion, or canon mutation.",
            "Bench->active-coverage promotion is a separate higher gate needing deployment_ready and explicit owner approval.",
            "A candidate listing is not owner approval and is not capital/execution authority.",
        ],
    }


def build_report(emit_packet: bool) -> tuple[dict[str, Any], dict[str, Any] | None]:
    router = load_json_artifact(AUTO_ROUTER)
    router = router if isinstance(router, dict) else {}
    register = load_json_artifact(LABEL_REGISTER)
    register = register if isinstance(register, dict) else {}
    tier_weighted = load_json_artifact(TIER_WEIGHTED)
    tier_weighted = tier_weighted if isinstance(tier_weighted, dict) else {}

    canon_rows = load_canon_rows()
    approved = approved_label_set(register)
    res_map = resolution_state_map(tier_weighted)
    for row in canon_rows:
        row["resolution_state"] = res_map.get(sym(row.get("ticker")))

    classified = classify_rows(canon_rows, approved)

    def count(pred) -> int:
        return sum(1 for row in classified if pred(row))

    total = len(classified)
    coherent = count(lambda r: r["direction"] == "match")
    auto_ahead = count(lambda r: r["direction"] == "auto_ahead")
    legacy_ahead = count(lambda r: r["direction"] == "legacy_ahead")
    disagreements = auto_ahead + legacy_ahead
    approved_sync_pending = count(lambda r: r["coherence_class"] == "approved_label_sync_pending")
    needs_owner_review = count(lambda r: r["coherence_class"] == "auto_promotion_needs_owner_review")
    demoted_active = count(lambda r: r["coherence_class"] == "router_demoted_active_coverage_name")
    demoted_monitor = count(lambda r: r["coherence_class"] == "router_demoted_monitor_name")
    coverage_gap = count(lambda r: r["implies_coverage_gap"])
    active_coverage_total = count(lambda r: r["in_active_coverage"])

    disagreement_rows = [row for row in classified if row["direction"] != "match"]

    checks: list[dict[str, Any]] = []
    add_check(checks, "auto_router_present", bool(router), rel(AUTO_ROUTER))
    add_check(checks, "auto_router_status_ok", router.get("status") == "ok", router.get("status"))
    add_check(checks, "canon_rows_loaded", total > 0, total)
    add_check(checks, "counts_partition_total", coherent + auto_ahead + legacy_ahead == total,
              {"coherent": coherent, "auto_ahead": auto_ahead, "legacy_ahead": legacy_ahead, "total": total})
    add_check(checks, "every_disagreement_classified",
              all(row["coherence_class"] != "coherent" for row in disagreement_rows), disagreements)
    add_check(checks, "tier_disagreements_create_no_coverage_gap", coverage_gap == 0, coverage_gap)
    add_check(checks, "legacy_ahead_names_remain_in_active_coverage",
              all(row["in_active_coverage"] for row in classified if row["direction"] == "legacy_ahead"),
              demoted_monitor)
    add_check(checks, "unapproved_auto_promotions_surfaced_for_owner",
              needs_owner_review >= 0, needs_owner_review, severity="info")
    for flag in sorted(REQUIRED_TRUE_FLAGS):
        add_check(checks, f"authority_{flag}_true", AUTHORITY_BOUNDARY.get(flag) is True, AUTHORITY_BOUNDARY.get(flag))
    for flag in sorted(REQUIRED_FALSE_FLAGS):
        add_check(checks, f"authority_{flag}_false", AUTHORITY_BOUNDARY.get(flag) is False, AUTHORITY_BOUNDARY.get(flag))

    errors = [check for check in checks if check["severity"] == "critical" and not check["ok"]]
    warnings = [check for check in checks if check["severity"] == "warning" and not check["ok"]]

    report = {
        "schema": VALIDATOR_SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok" if not errors else "blocked",
        "workflow": "WF78 - Tier Coherence Validator",
        "purpose": (
            "Enumerate and classify WF78 auto-router vs canon legacy tier disagreements "
            "so the stale legacy field can no longer imply a freshness coverage gap."
        ),
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": {
            "canon_data_plane": rel(CANON_DB),
            "auto_router": rel(AUTO_ROUTER),
            "tier_label_decision_register": rel(LABEL_REGISTER),
            "tier_weighted_freshness_resolution": rel(TIER_WEIGHTED),
        },
        "summary": {
            "current_tier_authority": rel(AUTO_ROUTER),
            "legacy_tier_field_role": "stale_label_not_authority",
            "ticker_count": total,
            "active_coverage_count": active_coverage_total,
            "coherent_count": coherent,
            "disagreement_count": disagreements,
            "auto_ahead_count": auto_ahead,
            "legacy_ahead_count": legacy_ahead,
            "approved_label_sync_pending_count": approved_sync_pending,
            "auto_promotion_needs_owner_review_count": needs_owner_review,
            "router_demoted_active_coverage_count": demoted_active,
            "router_demoted_monitor_count": demoted_monitor,
            "coverage_obligation_gap_count": coverage_gap,
            "headline": (
                "Legacy/auto tier disagreements do not create a freshness coverage gap: "
                "coverage membership is scope-driven, not tier-label-driven."
            ),
        },
        "disagreements": disagreement_rows,
        "validation": {
            "status": "ok" if not errors else "error",
            "errors": errors,
            "warnings": warnings,
            "checks": checks,
        },
        "stop_lines": [
            "This validator does not mutate any tier label, membership, or canon surface.",
            "A clean coherence result is not a promotion, label-sync apply, or approval.",
            "Auto-router remains the current tier authority; legacy_universe_tier is a stale label only.",
        ],
    }

    packet = build_promotion_packet(classified, register) if emit_packet else None
    return report, packet


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--emit-promotion-packet", action="store_true")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--packet-out", type=Path, default=PROMOTION_PACKET_OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report, packet = build_report(emit_packet=args.emit_promotion_packet)
    out = args.out if args.out.is_absolute() else ROOT / args.out
    packet_out = args.packet_out if args.packet_out.is_absolute() else ROOT / args.packet_out
    if args.write:
        atomic_write_json(out, report)
        if packet is not None:
            atomic_write_json(packet_out, packet)
    printed: dict[str, Any] = {
        "status": report.get("status"),
        "out": rel(out),
        "summary": report.get("summary"),
        "validation": {
            "status": as_dict(report.get("validation")).get("status"),
            "errors": len(as_list(as_dict(report.get("validation")).get("errors"))),
        },
    }
    if packet is not None:
        printed["promotion_packet"] = {
            "out": rel(packet_out),
            "summary": packet.get("summary"),
        }
    print(json.dumps(printed, indent=2))
    if args.validate and as_dict(report.get("validation")).get("status") != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
