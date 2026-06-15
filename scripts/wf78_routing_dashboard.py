#!/usr/bin/env python3
"""WF78 derived routing dashboard over existing funnel proof.

This script reads the current WF78 tier-funnel JSON artifacts and builds a
route-first control-plane packet plus an optional SQLite lookup database. It is
for fast dashboard routing only: which lane owns a candidate, what verdict
blocks it, what skill route should handle it, and what command refreshes proof.

JSON remains the source/proof snapshot. SQLite is a rebuildable index for PM
cockpits and routing queries. This script imports, applies, promotes, approves,
or executes nothing.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"

DEFAULT_OUT = TMP / "wf78-routing-dashboard.json"
DEFAULT_DB = TMP / "wf78-routing-dashboard.sqlite"

AUTO_ROUTER = TMP / "wf78-auto-tier-routing.json"
OWNER_PACKET = TMP / "wf78-funnel-owner-decision-packet.json"
PHASE2_GATE = TMP / "wf78-tier-funnel-promotion-gate.json"
PHASE3_GATE = TMP / "wf78-tier-a-competitive-promotion-gate.json"
CONTRACT = TMP / "wf78-tier-funnel-contract.json"
CAPACITY_GATE = TMP / "wf78-tier-capacity-policy-gate.json"
MACRO_OVERLAY = TMP / "wf78-macro-thesis-overlay-gate.json"
REPUTATION_GATE = TMP / "wf78-500-ticker-reputation-gate.json"
TICKER_REFRESH_GATE = TMP / "finance-ticker-card-refresh-gate.json"

SCHEMA = "veritas.wf78_routing_dashboard.v1"

AUTHORITY_BOUNDARY: dict[str, bool] = {
    "review_only": True,
    "report_only": True,
    "derived_routing_index_only": True,
    "auto_router_is_primary_non_capital_route": True,
    "read_existing_artifacts_only": True,
    "json_remains_source_proof": True,
    "sqlite_is_canon": False,
    "ticker_import_allowed": False,
    "apply_allowed": False,
    "promotion_allowed": False,
    "tier_admission_executed": False,
    "tier_a_admission_executed": False,
    "production_answer_path_change_allowed": False,
    "sql_first_promotion_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "owner_approval_inferred": False,
}

REQUIRED_TRUE_FLAGS = {
    "review_only",
    "report_only",
    "derived_routing_index_only",
    "auto_router_is_primary_non_capital_route",
    "read_existing_artifacts_only",
    "json_remains_source_proof",
}
REQUIRED_FALSE_FLAGS = {key for key in AUTHORITY_BOUNDARY if key not in REQUIRED_TRUE_FLAGS}

SOURCE_ARTIFACTS: dict[str, tuple[Path, bool]] = {
    "auto_tier_router": (AUTO_ROUTER, True),
    "owner_decision_packet": (OWNER_PACKET, True),
    "phase2_lower_tier_gate": (PHASE2_GATE, True),
    "phase3_tier_a_gate": (PHASE3_GATE, True),
    "tier_funnel_contract": (CONTRACT, True),
    "tier_capacity_policy_gate": (CAPACITY_GATE, True),
    "macro_thesis_overlay_gate": (MACRO_OVERLAY, False),
    "reputation_gate": (REPUTATION_GATE, False),
    "ticker_card_refresh_gate": (TICKER_REFRESH_GATE, False),
}

TRANSITION_LANES = {
    "d_to_c": "intake_identity_lane",
    "c_to_b": "research_promotion_lane",
    "b_to_a": "tier_a_competitive_lane",
}

OWNER_ACTION_LANES = {
    "actionable_now": "owner_decision_lane",
    "needs_evidence": "evidence_repair_lane",
    "needs_validation": "deep_research_validation_lane",
    "state_repair_needed": "decay_freshness_lane",
    "capacity_or_competition_blocked": "capacity_competition_lane",
    "routed_elsewhere": "routing_repair_lane",
    "no_action": "no_action_lane",
}

SKILL_ROUTES: dict[str, dict[str, Any]] = {
    "intake_identity_lane": {
        "dashboard_slice": "D-to-C Intake / Identity",
        "primary_skill": "automation-hardening-manager",
        "supporting_skills": ["SQLite", "sec", "veritas-response-contract"],
        "owner_surface": "WF78 intake and monitorability gate",
        "next_command": "python scripts\\wf78_tier_funnel_promotion_gate.py --write --validate",
        "helper_recommended": False,
    },
    "research_promotion_lane": {
        "dashboard_slice": "C-to-B Research Promotion",
        "primary_skill": "veritas-fundamental-pass",
        "supporting_skills": ["veritas-positioning-pass", "veritas-bounded-portfolio-agent", "veritas-response-contract"],
        "owner_surface": "WF78 Tier C to Tier B research-worthiness gate",
        "next_command": "python scripts\\wf78_tier_funnel_promotion_gate.py --write --validate",
        "helper_recommended": True,
    },
    "evidence_repair_lane": {
        "dashboard_slice": "Evidence Gaps",
        "primary_skill": "veritas-fundamental-pass",
        "supporting_skills": ["veritas-macro-pass", "veritas-technical-pass", "technical-chart-pass", "sec"],
        "owner_surface": "WF78 per-lead Tier B evidence packet queue",
        "next_command": "python scripts\\finance_ticker_card_refresh_gate.py --write --validate",
        "helper_recommended": True,
    },
    "deep_research_validation_lane": {
        "dashboard_slice": "B-Candidate to B-Validated",
        "primary_skill": "veritas-fundamental-pass",
        "supporting_skills": ["veritas-technical-pass", "veritas-positioning-pass", "veritas-response-contract"],
        "owner_surface": "WF78 Tier B research packet validator",
        "next_command": "Build the Tier B research packet validator, then rerun the Phase 2 and Phase 4 gates.",
        "helper_recommended": True,
    },
    "tier_a_competitive_lane": {
        "dashboard_slice": "B-to-A Competitive Roster",
        "primary_skill": "veritas-bounded-portfolio-agent",
        "supporting_skills": ["veritas-positioning-pass", "veritas-portfolio-update", "veritas-response-contract"],
        "owner_surface": "WF78 Tier A competitive roster gate",
        "next_command": "python scripts\\wf78_tier_a_competitive_promotion_gate.py --write --validate",
        "helper_recommended": True,
    },
    "owner_decision_lane": {
        "dashboard_slice": "Owner Decisions",
        "primary_skill": "veritas-response-contract",
        "supporting_skills": ["veritas-pm-department", "automation-hardening-manager"],
        "owner_surface": "WF78 owner decision packet layer",
        "next_command": "python scripts\\wf78_funnel_owner_decision_packet.py --write --validate",
        "helper_recommended": False,
    },
    "decay_freshness_lane": {
        "dashboard_slice": "Decay / Freshness Repair",
        "primary_skill": "automation-hardening-manager",
        "supporting_skills": ["veritas-technical-pass", "veritas-post-earnings-sync", "veritas-response-contract"],
        "owner_surface": "WF78 decay and freshness gate",
        "next_command": "Build the WF78 decay/freshness state validator, then rerun the routing dashboard.",
        "helper_recommended": True,
    },
    "capacity_competition_lane": {
        "dashboard_slice": "Capacity / Competition Blocks",
        "primary_skill": "veritas-bounded-portfolio-agent",
        "supporting_skills": ["veritas-positioning-pass", "automation-hardening-manager"],
        "owner_surface": "WF78 capacity and challenger policy",
        "next_command": "python scripts\\wf78_tier_capacity_policy_gate.py --write --write-db --validate",
        "helper_recommended": False,
    },
    "routing_repair_lane": {
        "dashboard_slice": "Routing Repair",
        "primary_skill": "automation-hardening-manager",
        "supporting_skills": ["SQLite", "veritas-response-contract"],
        "owner_surface": "WF78 routing dashboard",
        "next_command": "python scripts\\wf78_routing_dashboard.py --write --write-db --validate",
        "helper_recommended": False,
    },
    "no_action_lane": {
        "dashboard_slice": "No Action",
        "primary_skill": "veritas-response-contract",
        "supporting_skills": ["automation-hardening-manager"],
        "owner_surface": "WF78 routing dashboard",
        "next_command": "Refresh source gates only if stale or contradicted.",
        "helper_recommended": False,
    },
}

STOP_LINES = [
    "tmp/wf78-auto-tier-routing.json is the primary derived non-capital Tier A/B/C routing state.",
    "This dashboard is secondary route proof/context, not canon, approval, or promotion authority.",
    "JSON gate artifacts remain the proof snapshots; SQLite is rebuildable lookup only.",
    "Do not admit, promote, import, apply, or mutate a ticker from this dashboard.",
    "No production answer-path expansion, SQL-first promotion, canon/portfolio mutation, or customer output.",
    "No paper/live/account action, money movement, execution entitlement, or owner approval inference.",
]


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


def json_text(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def int_bool(value: Any) -> int:
    return 1 if bool(value) else 0


def sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def artifact_meta(key: str, path: Path, required: bool) -> dict[str, Any]:
    payload = load_json_artifact(path) if path.suffix.lower() == ".json" else None
    exists = path.exists()
    stat = path.stat() if exists else None
    validation = as_dict(as_dict(payload).get("validation")) if isinstance(payload, dict) else {}
    return {
        "artifact_key": key,
        "path": rel(path),
        "exists": exists,
        "required": required,
        "sha256": sha256_file(path) if exists else None,
        "size_bytes": stat.st_size if stat else None,
        "mtime_utc": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z") if stat else None,
        "generated_at_utc": as_dict(payload).get("generated_at_utc") if isinstance(payload, dict) else None,
        "status": as_dict(payload).get("status") if isinstance(payload, dict) else None,
        "validation_status": validation.get("status"),
        "payload": payload,
    }


def connect_write(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA temp_store=MEMORY")
    return conn


def add_check(checks: list[dict[str, Any]], name: str, ok: bool, detail: Any = None, severity: str = "critical") -> None:
    checks.append({"name": name, "ok": bool(ok), "status": "ok" if ok else "fail", "severity": severity, "detail": detail})


def action_lane(packet: dict[str, Any]) -> str:
    category = str(packet.get("owner_action_category") or "no_action")
    return OWNER_ACTION_LANES.get(category, "routing_repair_lane")


def transition_lane(packet: dict[str, Any]) -> str:
    transition = str(packet.get("transition_key") or "")
    return TRANSITION_LANES.get(transition, "routing_repair_lane")


def route_for(packet: dict[str, Any]) -> dict[str, Any]:
    # Owner-action lanes are the dashboard route because they answer what to do next.
    lane = action_lane(packet)
    if lane == "no_action_lane":
        lane = transition_lane(packet)
    return SKILL_ROUTES.get(lane, SKILL_ROUTES["routing_repair_lane"]) | {"route_key": lane}


def build_routing_rows(owner_packet: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, packet in enumerate(as_list(owner_packet.get("packets")), start=1):
        if not isinstance(packet, dict):
            continue
        route = route_for(packet)
        missing = [str(item) for item in as_list(packet.get("missing_evidence"))]
        row_id = f"{packet.get('ticker') or 'UNKNOWN'}:{packet.get('transition_key') or 'unknown'}:{index}"
        rows.append({
            "row_id": row_id,
            "rank": index,
            "ticker": packet.get("ticker"),
            "name": packet.get("name"),
            "packet_type": packet.get("packet_type"),
            "transition_key": packet.get("transition_key"),
            "transition_lane": transition_lane(packet),
            "action_lane": route["route_key"],
            "dashboard_slice": route["dashboard_slice"],
            "from_tier": packet.get("from_tier"),
            "from_tier_label": packet.get("from_tier_label"),
            "to_tier": packet.get("to_tier"),
            "to_tier_label": packet.get("to_tier_label"),
            "current_state": packet.get("current_state"),
            "requested_state": packet.get("requested_state"),
            "gate_verdict": packet.get("gate_verdict"),
            "gate_reason": packet.get("gate_reason"),
            "owner_action_category": packet.get("owner_action_category"),
            "owner_action": packet.get("owner_action"),
            "required_evidence_count": int(packet.get("required_evidence_count") or 0),
            "evidence_present_count": int(packet.get("evidence_present_count") or 0),
            "missing_evidence_count": len(missing),
            "missing_evidence": missing,
            "source_gate": packet.get("source_gate"),
            "source_gate_trusted": bool(packet.get("source_gate_trusted")),
            "owner_approval_required": bool(packet.get("owner_approval_required")),
            "owner_approval_inferred": bool(packet.get("owner_approval_inferred")),
            "primary_skill": route["primary_skill"],
            "supporting_skills": route["supporting_skills"],
            "owner_surface": route["owner_surface"],
            "next_command": route["next_command"],
            "helper_recommended": bool(route["helper_recommended"]),
        })
    return rows


def count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key))
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def lane_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row.get("action_lane")), []).append(row)
    summaries: list[dict[str, Any]] = []
    for lane, items in sorted(grouped.items()):
        route = SKILL_ROUTES.get(lane, SKILL_ROUTES["routing_repair_lane"])
        summaries.append({
            "lane": lane,
            "dashboard_slice": route["dashboard_slice"],
            "row_count": len(items),
            "actionable_now_count": len([item for item in items if item.get("owner_action_category") == "actionable_now"]),
            "needs_evidence_count": len([item for item in items if item.get("owner_action_category") == "needs_evidence"]),
            "missing_evidence_total": sum(int(item.get("missing_evidence_count") or 0) for item in items),
            "primary_skill": route["primary_skill"],
            "helper_recommended_count": len([item for item in items if item.get("helper_recommended")]),
            "next_command": route["next_command"],
        })
    return summaries


def build_report() -> dict[str, Any]:
    generated_at = utc_now()
    artifacts = {
        key: artifact_meta(key, path, required)
        for key, (path, required) in SOURCE_ARTIFACTS.items()
    }
    auto_router = as_dict(artifacts["auto_tier_router"].get("payload"))
    owner_packet = as_dict(artifacts["owner_decision_packet"].get("payload"))
    rows = build_routing_rows(owner_packet)
    auto_summary = as_dict(auto_router.get("summary"))

    source_status = {
        key: {
            "path": meta["path"],
            "exists": meta["exists"],
            "required": meta["required"],
            "status": meta.get("status"),
            "validation_status": meta.get("validation_status"),
            "generated_at_utc": meta.get("generated_at_utc"),
        }
        for key, meta in artifacts.items()
    }

    report = {
        "schema": SCHEMA,
        "generated_at_utc": generated_at,
        "status": "draft",
        "workflow": "WF78 - Routing Dashboard",
        "purpose": "Secondary route-first dashboard over WF78 proof artifacts. The current non-capital tier/routing state comes first from tmp/wf78-auto-tier-routing.json.",
        "architecture_rule": "Auto-router JSON is the primary derived non-capital route state; legacy funnel JSON remains proof/context; SQLite is a rebuildable routing/control-plane index only.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_status": source_status,
        "summary": {
            "primary_routing_source": "tmp/wf78-auto-tier-routing.json",
            "auto_router_status": auto_router.get("status"),
            "auto_router_active_ticker_count": auto_summary.get("active_ticker_count"),
            "auto_router_tier_counts": auto_summary.get("auto_tier_counts"),
            "auto_router_state_counts": auto_summary.get("auto_state_counts"),
            "capital_deployment_approved_count": auto_summary.get("capital_deployment_approved_count"),
            "trade_or_execution_approved_count": auto_summary.get("trade_or_execution_approved_count"),
            "routing_row_count": len(rows),
            "actionable_now_count": len([row for row in rows if row.get("owner_action_category") == "actionable_now"]),
            "source_packet_count": int(as_dict(owner_packet.get("summary")).get("packet_count") or 0),
            "by_action_lane": count_by(rows, "action_lane"),
            "by_transition_lane": count_by(rows, "transition_lane"),
            "by_owner_action_category": count_by(rows, "owner_action_category"),
            "by_gate_verdict": count_by(rows, "gate_verdict"),
            "next_safe_action": "Use the auto-router for live non-capital routing state; use this dashboard for legacy funnel evidence/repair context only.",
        },
        "lane_summary": lane_summary(rows),
        "routing_rows": rows,
        "skill_routes": [
            {"route_key": key, **value}
            for key, value in sorted(SKILL_ROUTES.items())
        ],
        "refresh_sequence": [
            "python scripts\\wf78_tier_funnel_contract.py --write --validate",
            "python scripts\\wf78_500_ticker_reputation_gate.py --write --write-db --validate",
            "python scripts\\finance_ticker_card_refresh_gate.py --write --validate",
            "python scripts\\wf78_tier_capacity_policy_gate.py --write --write-db --validate",
            "python scripts\\wf78_tier_promotion_review_gate.py --write --write-db --validate",
            "python scripts\\wf78_macro_thesis_overlay_gate.py --write --write-db --validate",
            "python scripts\\wf78_tier_funnel_promotion_gate.py --write --validate",
            "python scripts\\wf78_tier_a_competitive_promotion_gate.py --write --validate",
            "python scripts\\wf78_funnel_owner_decision_packet.py --write --validate",
            "python scripts\\wf78_auto_tier_router.py --write --validate",
            "python scripts\\wf78_routing_dashboard.py --write --write-db --validate",
        ],
        "artifact_provenance": [
            {key: value for key, value in meta.items() if key != "payload"}
            for meta in artifacts.values()
        ],
        "stop_lines": STOP_LINES,
    }
    checks = validation_checks(report)
    report["validation"] = {
        "status": "ok" if all(check["ok"] for check in checks if check["severity"] == "critical") else "fail_closed",
        "checks": checks,
        "errors": [check["name"] for check in checks if check["severity"] == "critical" and not check["ok"]],
        "warnings": [check["name"] for check in checks if check["severity"] == "warning" and not check["ok"]],
    }
    report["status"] = "ok" if report["validation"]["status"] == "ok" else "blocked"
    return report


def validation_checks(report: dict[str, Any], out: Path | None = None, db: Path | None = None) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    rows = as_list(report.get("routing_rows"))
    summary = as_dict(report.get("summary"))
    source_status = as_dict(report.get("source_status"))

    add_check(checks, "schema_current", report.get("schema") == SCHEMA, report.get("schema"))
    add_check(checks, "auto_tier_router_present", as_dict(source_status.get("auto_tier_router")).get("exists") is True, source_status.get("auto_tier_router"))
    add_check(checks, "auto_tier_router_validated", as_dict(source_status.get("auto_tier_router")).get("validation_status") == "ok", source_status.get("auto_tier_router"))
    add_check(checks, "auto_router_reports_no_capital_deployment", int(summary.get("capital_deployment_approved_count") or 0) == 0, summary.get("capital_deployment_approved_count"))
    add_check(checks, "auto_router_reports_no_trade_execution", int(summary.get("trade_or_execution_approved_count") or 0) == 0, summary.get("trade_or_execution_approved_count"))
    add_check(checks, "owner_decision_packet_present", as_dict(source_status.get("owner_decision_packet")).get("exists") is True, source_status.get("owner_decision_packet"))
    add_check(checks, "owner_decision_packet_validated", as_dict(source_status.get("owner_decision_packet")).get("validation_status") == "ok", source_status.get("owner_decision_packet"))
    add_check(checks, "row_count_matches_owner_packet", int(summary.get("routing_row_count") or 0) == int(summary.get("source_packet_count") or 0), summary)
    add_check(checks, "all_rows_have_dashboard_slice", all(row.get("dashboard_slice") for row in rows), [row.get("row_id") for row in rows if not row.get("dashboard_slice")])
    add_check(checks, "all_rows_have_primary_skill", all(row.get("primary_skill") for row in rows), [row.get("row_id") for row in rows if not row.get("primary_skill")])
    add_check(checks, "all_rows_have_next_command", all(row.get("next_command") for row in rows), [row.get("row_id") for row in rows if not row.get("next_command")])
    add_check(checks, "no_row_infers_owner_approval", all(row.get("owner_approval_inferred") is False for row in rows), [row.get("row_id") for row in rows if row.get("owner_approval_inferred") is not False])
    add_check(checks, "all_actionable_rows_require_owner_approval", all(row.get("owner_approval_required") is True for row in rows if row.get("owner_action_category") == "actionable_now"), True)
    add_check(checks, "no_unknown_action_lane", all(row.get("action_lane") in SKILL_ROUTES for row in rows), [row.get("row_id") for row in rows if row.get("action_lane") not in SKILL_ROUTES])

    for flag in sorted(REQUIRED_TRUE_FLAGS):
        add_check(checks, f"authority_{flag}_true", AUTHORITY_BOUNDARY.get(flag) is True, AUTHORITY_BOUNDARY.get(flag))
    for flag in sorted(REQUIRED_FALSE_FLAGS):
        add_check(checks, f"authority_{flag}_false", AUTHORITY_BOUNDARY.get(flag) is False, AUTHORITY_BOUNDARY.get(flag))

    if out is not None:
        loaded = load_json_artifact(out)
        add_check(checks, "output_json_schema_current", isinstance(loaded, dict) and loaded.get("schema") == SCHEMA, rel(out))
    if db is not None:
        db_result = db_health(db)
        add_check(checks, "output_sqlite_integrity_ok", db_result.get("integrity_check") == "ok", db_result)
        add_check(checks, "output_sqlite_has_routing_rows", int(as_dict(db_result.get("table_counts")).get("routing_rows") or 0) == len(rows), db_result)
    return checks


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        DROP TABLE IF EXISTS routing_rows;
        DROP TABLE IF EXISTS lane_summary;
        DROP TABLE IF EXISTS skill_routes;
        DROP TABLE IF EXISTS artifact_provenance;
        DROP TABLE IF EXISTS authority_boundary;
        DROP TABLE IF EXISTS validation_results;
        DROP TABLE IF EXISTS meta;

        CREATE TABLE routing_rows (
            row_id TEXT PRIMARY KEY,
            rank INTEGER NOT NULL,
            ticker TEXT,
            name TEXT,
            packet_type TEXT,
            transition_key TEXT,
            transition_lane TEXT NOT NULL,
            action_lane TEXT NOT NULL,
            dashboard_slice TEXT NOT NULL,
            from_tier TEXT,
            from_tier_label TEXT,
            to_tier TEXT,
            to_tier_label TEXT,
            current_state TEXT,
            requested_state TEXT,
            gate_verdict TEXT,
            owner_action_category TEXT,
            missing_evidence_count INTEGER NOT NULL,
            required_evidence_count INTEGER NOT NULL,
            evidence_present_count INTEGER NOT NULL,
            source_gate TEXT,
            source_gate_trusted INTEGER NOT NULL,
            owner_approval_required INTEGER NOT NULL,
            owner_approval_inferred INTEGER NOT NULL,
            primary_skill TEXT NOT NULL,
            supporting_skills_json TEXT NOT NULL,
            owner_surface TEXT NOT NULL,
            next_command TEXT NOT NULL,
            helper_recommended INTEGER NOT NULL,
            missing_evidence_json TEXT NOT NULL,
            owner_action TEXT,
            raw_json TEXT NOT NULL
        );

        CREATE INDEX idx_routing_rows_lane ON routing_rows(action_lane, dashboard_slice);
        CREATE INDEX idx_routing_rows_verdict ON routing_rows(gate_verdict, owner_action_category);
        CREATE INDEX idx_routing_rows_ticker ON routing_rows(ticker);

        CREATE TABLE lane_summary (
            lane TEXT PRIMARY KEY,
            dashboard_slice TEXT NOT NULL,
            row_count INTEGER NOT NULL,
            actionable_now_count INTEGER NOT NULL,
            needs_evidence_count INTEGER NOT NULL,
            missing_evidence_total INTEGER NOT NULL,
            primary_skill TEXT NOT NULL,
            helper_recommended_count INTEGER NOT NULL,
            next_command TEXT NOT NULL
        );

        CREATE TABLE skill_routes (
            route_key TEXT PRIMARY KEY,
            dashboard_slice TEXT NOT NULL,
            primary_skill TEXT NOT NULL,
            supporting_skills_json TEXT NOT NULL,
            owner_surface TEXT NOT NULL,
            next_command TEXT NOT NULL,
            helper_recommended INTEGER NOT NULL
        );

        CREATE TABLE artifact_provenance (
            artifact_key TEXT PRIMARY KEY,
            path TEXT NOT NULL,
            required INTEGER NOT NULL,
            exists_flag INTEGER NOT NULL,
            sha256 TEXT,
            generated_at_utc TEXT,
            mtime_utc TEXT,
            size_bytes INTEGER,
            status TEXT,
            validation_status TEXT
        );

        CREATE TABLE authority_boundary (
            flag_name TEXT PRIMARY KEY,
            flag_value INTEGER NOT NULL,
            required_value INTEGER NOT NULL,
            status TEXT NOT NULL
        );

        CREATE TABLE validation_results (
            check_name TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            severity TEXT NOT NULL,
            detail_json TEXT NOT NULL
        );

        CREATE TABLE meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        """
    )


def write_db(path: Path, report: dict[str, Any]) -> None:
    with connect_write(path) as conn:
        init_schema(conn)
        with conn:
            conn.executemany(
                """
                INSERT INTO routing_rows (
                    row_id, rank, ticker, name, packet_type, transition_key,
                    transition_lane, action_lane, dashboard_slice, from_tier,
                    from_tier_label, to_tier, to_tier_label, current_state,
                    requested_state, gate_verdict, owner_action_category,
                    missing_evidence_count, required_evidence_count,
                    evidence_present_count, source_gate, source_gate_trusted,
                    owner_approval_required, owner_approval_inferred,
                    primary_skill, supporting_skills_json, owner_surface,
                    next_command, helper_recommended, missing_evidence_json,
                    owner_action, raw_json
                ) VALUES (
                    :row_id, :rank, :ticker, :name, :packet_type, :transition_key,
                    :transition_lane, :action_lane, :dashboard_slice, :from_tier,
                    :from_tier_label, :to_tier, :to_tier_label, :current_state,
                    :requested_state, :gate_verdict, :owner_action_category,
                    :missing_evidence_count, :required_evidence_count,
                    :evidence_present_count, :source_gate, :source_gate_trusted,
                    :owner_approval_required, :owner_approval_inferred,
                    :primary_skill, :supporting_skills_json, :owner_surface,
                    :next_command, :helper_recommended, :missing_evidence_json,
                    :owner_action, :raw_json
                )
                """,
                [
                    {
                        **row,
                        "source_gate_trusted": int_bool(row.get("source_gate_trusted")),
                        "owner_approval_required": int_bool(row.get("owner_approval_required")),
                        "owner_approval_inferred": int_bool(row.get("owner_approval_inferred")),
                        "helper_recommended": int_bool(row.get("helper_recommended")),
                        "supporting_skills_json": json_text(row.get("supporting_skills")),
                        "missing_evidence_json": json_text(row.get("missing_evidence")),
                        "raw_json": json_text(row),
                    }
                    for row in as_list(report.get("routing_rows"))
                ],
            )
            conn.executemany(
                """
                INSERT INTO lane_summary (
                    lane, dashboard_slice, row_count, actionable_now_count,
                    needs_evidence_count, missing_evidence_total, primary_skill,
                    helper_recommended_count, next_command
                ) VALUES (
                    :lane, :dashboard_slice, :row_count, :actionable_now_count,
                    :needs_evidence_count, :missing_evidence_total, :primary_skill,
                    :helper_recommended_count, :next_command
                )
                """,
                as_list(report.get("lane_summary")),
            )
            conn.executemany(
                """
                INSERT INTO skill_routes (
                    route_key, dashboard_slice, primary_skill, supporting_skills_json,
                    owner_surface, next_command, helper_recommended
                ) VALUES (
                    :route_key, :dashboard_slice, :primary_skill, :supporting_skills_json,
                    :owner_surface, :next_command, :helper_recommended
                )
                """,
                [
                    {
                        **route,
                        "supporting_skills_json": json_text(route.get("supporting_skills")),
                        "helper_recommended": int_bool(route.get("helper_recommended")),
                    }
                    for route in as_list(report.get("skill_routes"))
                ],
            )
            conn.executemany(
                """
                INSERT INTO artifact_provenance (
                    artifact_key, path, required, exists_flag, sha256,
                    generated_at_utc, mtime_utc, size_bytes, status, validation_status
                ) VALUES (
                    :artifact_key, :path, :required, :exists_flag, :sha256,
                    :generated_at_utc, :mtime_utc, :size_bytes, :status, :validation_status
                )
                """,
                [
                    {
                        **item,
                        "required": int_bool(item.get("required")),
                        "exists_flag": int_bool(item.get("exists")),
                    }
                    for item in as_list(report.get("artifact_provenance"))
                ],
            )
            conn.executemany(
                """
                INSERT INTO authority_boundary (flag_name, flag_value, required_value, status)
                VALUES (:flag_name, :flag_value, :required_value, :status)
                """,
                [
                    {
                        "flag_name": key,
                        "flag_value": int_bool(value),
                        "required_value": 1 if key in REQUIRED_TRUE_FLAGS else 0,
                        "status": "ok" if ((key in REQUIRED_TRUE_FLAGS and value is True) or (key in REQUIRED_FALSE_FLAGS and value is False)) else "fail",
                    }
                    for key, value in sorted(as_dict(report.get("authority_boundary")).items())
                ],
            )
            conn.executemany(
                """
                INSERT INTO validation_results (check_name, status, severity, detail_json)
                VALUES (:check_name, :status, :severity, :detail_json)
                """,
                [
                    {
                        "check_name": check["name"],
                        "status": check["status"],
                        "severity": check["severity"],
                        "detail_json": json_text(check.get("detail")),
                    }
                    for check in as_list(as_dict(report.get("validation")).get("checks"))
                ],
            )
            for key, value in {
                "schema": report["schema"],
                "generated_at_utc": report["generated_at_utc"],
                "workflow": report["workflow"],
                "summary": json_text(report["summary"]),
                "authority_boundary": json_text(report["authority_boundary"]),
            }.items():
                conn.execute("INSERT INTO meta (key, value) VALUES (?, ?)", (key, value))
        conn.execute("PRAGMA optimize")


def db_health(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"status": "missing", "path": rel(path), "integrity_check": None, "table_counts": {}}
    conn = sqlite3.connect(str(path))
    try:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        tables = [
            row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        ]
        counts = {table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in tables}
    finally:
        conn.close()
    return {
        "status": "ok" if integrity == "ok" else "blocked",
        "path": rel(path),
        "integrity_check": integrity,
        "table_counts": counts,
    }


def resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the WF78 derived routing dashboard.")
    parser.add_argument("--write", action="store_true", help=f"Write {rel(DEFAULT_OUT)}")
    parser.add_argument("--write-db", action="store_true", help=f"Write {rel(DEFAULT_DB)}")
    parser.add_argument("--validate", action="store_true", help="Exit fail-closed if validation fails.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print stdout JSON.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    out = resolve(args.out)
    db = resolve(args.db)
    report = build_report()
    if args.write:
        atomic_write_json(out, report)
    if args.write_db:
        write_db(db, report)
    if args.validate:
        checks = validation_checks(report, out if args.write else None, db if args.write_db else None)
        report["validation"] = {
            "status": "ok" if all(check["ok"] for check in checks if check["severity"] == "critical") else "fail_closed",
            "checks": checks,
            "errors": [check["name"] for check in checks if check["severity"] == "critical" and not check["ok"]],
            "warnings": [check["name"] for check in checks if check["severity"] == "warning" and not check["ok"]],
        }
        report["status"] = "ok" if report["validation"]["status"] == "ok" else "blocked"
        if args.write:
            atomic_write_json(out, report)
        if args.write_db:
            write_db(db, report)

    result = {
        "status": report["status"],
        "out": rel(out) if args.write else None,
        "db": rel(db) if args.write_db else None,
        "summary": report["summary"],
        "validation": report["validation"],
    }
    print(json.dumps(result, indent=2 if args.pretty else None, sort_keys=True))
    if args.validate and report["status"] != "ok":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
