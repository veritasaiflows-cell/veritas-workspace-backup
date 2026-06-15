from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"
CANON_CACHE_DB = TMP / "veritas-canon-cache.sqlite"
ARTIFACT_INDEX_DB = TMP / "veritas-artifact-index.sqlite"
WORKSPACE_INDEX_DB = TMP / "workspace-index.sqlite"
PHASE3F_VALIDATION = TMP / "sql-canon-phase3f-validation.json"
FIELD_PREFLIGHT = TMP / "sql-canon-low-risk-field-family-preflight.json"
OUT_JSON = TMP / "sql-canon-v2-prototype-plan.json"
OUT_MD = TMP / "sql-canon-v2-prototype-plan.md"

FORBIDDEN_AUTHORITY_FLAGS = {
    "canonical_note_mutation_allowed",
    "markdown_mutation_allowed",
    "portfolio_mutation_allowed",
    "owner_approval_inferred",
    "proposal_apply_allowed",
    "trade_or_account_action_allowed",
    "paper_trade_authority_allowed",
    "live_trade_authority_allowed",
    "money_movement_allowed",
    "dashboard_recommendation_deployment_action_state_behavior_change_allowed",
    "approval_inferred",
    "apply_allowed",
}

AUTHORITY_BOUNDARY = (
    "sql_canon_v2_planning_only_no_new_cache_rows_no_consumer_behavior_change_"
    "no_markdown_or_portfolio_mutation_no_execution_authority"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def connect_ro(path: Path) -> sqlite3.Connection:
    uri = path.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def table_names(conn: sqlite3.Connection) -> set[str]:
    return {str(r[0]) for r in conn.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view')")}


def safe_count(conn: sqlite3.Connection, table: str) -> int | None:
    try:
        return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
    except Exception:
        return None


def canon_cache_snapshot() -> dict[str, Any]:
    snap: dict[str, Any] = {
        "path": str(CANON_CACHE_DB.relative_to(WORKSPACE)).replace("\\", "/"),
        "exists": CANON_CACHE_DB.exists(),
        "tables": [],
        "row_count": 0,
        "authority_boundaries": {},
        "field_counts": {},
        "scope_count": 0,
        "stale_or_drift_candidates": [],
        "forbidden_authority_true_hits": [],
    }
    if not CANON_CACHE_DB.exists():
        return snap
    with connect_ro(CANON_CACHE_DB) as conn:
        names = table_names(conn)
        snap["tables"] = sorted(names)
        if "canon_cache_fields" not in names:
            return snap
        rows = [dict(r) for r in conn.execute("SELECT * FROM canon_cache_fields")]
        snap["row_count"] = len(rows)
        snap["authority_boundaries"] = dict(Counter(str(r.get("authority_boundary")) for r in rows))
        snap["field_counts"] = dict(Counter(str(r.get("field_name")) for r in rows))
        snap["scope_count"] = len({str(r.get("scope")) for r in rows})
        stale = []
        for r in rows:
            source_path = WORKSPACE / str(r.get("source_artifact_path", ""))
            owner_path = WORKSPACE / str(r.get("owner_mirror_note_path", ""))
            source_exists = source_path.exists()
            owner_exists = owner_path.exists()
            stale.append({
                "key": f"{r.get('scope')}:{r.get('field_name')}",
                "source_artifact_path": r.get("source_artifact_path"),
                "source_exists": source_exists,
                "owner_mirror_note_path": r.get("owner_mirror_note_path"),
                "owner_exists": owner_exists,
                "last_reconciled_at_utc": r.get("last_reconciled_at_utc"),
            })
        snap["stale_or_drift_candidates"] = [s for s in stale if not s["source_exists"] or not s["owner_exists"]][:50]
    return snap


def index_snapshot(path: Path, label: str) -> dict[str, Any]:
    snap = {"label": label, "path": str(path.relative_to(WORKSPACE)).replace("\\", "/"), "exists": path.exists(), "tables": {}, "integrity_check": None}
    if not path.exists():
        return snap
    with connect_ro(path) as conn:
        try:
            snap["integrity_check"] = conn.execute("PRAGMA quick_check").fetchone()[0]
        except Exception as exc:
            snap["integrity_check"] = f"error:{exc}"
        for name in sorted(table_names(conn)):
            if name.startswith("sqlite_"):
                continue
            count = safe_count(conn, name)
            if count is not None:
                snap["tables"][name] = count
    return snap


def validation_context() -> dict[str, Any]:
    phase3f = read_json(PHASE3F_VALIDATION, {})
    preflight = read_json(FIELD_PREFLIGHT, {})
    failed = [c for c in phase3f.get("checks", []) if not c.get("ok")]
    return {
        "phase3f_status": phase3f.get("status", "missing"),
        "phase3f_failed_checks": failed,
        "field_family_preflight_status": preflight.get("status", "missing"),
        "field_family_summary": preflight.get("summary") or preflight.get("preflight_summary") or {},
    }


def v2_phases() -> list[dict[str, Any]]:
    return [
        {
            "phase": "V2.0 baseline adjudication",
            "objective": "Treat current 265-row cache as a governed metadata store with explicit maturity labels instead of an informal cache.",
            "deliverables": ["single V2 plan artifact", "live DB inventory", "authority boundary assertions", "stale blocker register"],
            "acceptance": ["row counts match live DB", "forbidden authority flags false", "phase3f blockers surfaced, not hidden"],
            "authority": "planning/report-only",
        },
        {
            "phase": "V2.1 freshness and rollback hardening",
            "objective": "Make stale-source/cache drift a first-class gate before any consumer can rely on SQL-canon rows.",
            "deliverables": ["stale-check command", "per-row source/owner mtime/hash comparison", "rollback export verification", "WAL/quick_check/foreign_key proof"],
            "acceptance": ["no blocked stale rows for target family", "rollback SQL or export exists", "DB quick_check ok"],
            "authority": "read-only validation; no new rows",
        },
        {
            "phase": "V2.2 typed view layer",
            "objective": "Expose approved metadata through read-only SQL views/API helpers so consumers stop querying raw cache rows directly.",
            "deliverables": ["typed view contract", "allowed-field registry", "consumer guard wrapper", "fallback-required assertions"],
            "acceptance": ["views include authority boundary columns", "consumer tests prove fallback/no-drift", "blocked families fail closed"],
            "authority": "optional read-only consumption; no behavior change",
        },
        {
            "phase": "V2.3 next-family staging",
            "objective": "Stage candidate metadata families as proposal rows/artifacts before activation.",
            "deliverables": ["candidate family registry", "risk tier", "owner note/source binding", "manual approval packet template"],
            "acceptance": ["eligible vs held families explicit", "no ambiguous deployment/action vocabulary", "source-open requirement preserved"],
            "authority": "proposal-only; exact approval required for writes",
        },
        {
            "phase": "V2.4 governed activation path",
            "objective": "Promote exact approved metadata rows with backup, ledger, rollback, parity, and independent QA.",
            "deliverables": ["preactivation export", "write transaction", "change ledger", "post-activation no-drift", "rollback rehearsal"],
            "acceptance": ["exact key set only", "all authority flags false", "post-apply validators clean", "Active Workflows/skill/startup surfaces updated"],
            "authority": "only after exact Randall approval for family/key set",
        },
        {
            "phase": "V2.5 consumer migration",
            "objective": "Move selected consumers from artifact/Markdown-first to SQL-first with mandatory artifact/owner fallback and no output drift.",
            "deliverables": ["normalized no-drift compare", "fallback simulation", "consumer guard test", "stale DB fail-closed behavior"],
            "acceptance": ["user-visible output unchanged except proof metadata", "stale SQL downgrades confidence", "owner source still wins"],
            "authority": "read-only support; no canon/apply/execution behavior",
        },
    ]


def candidate_families(cache: dict[str, Any], validation: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "family": "current_active_265_metadata_rows",
            "status": "active_bounded_v1_baseline",
            "row_count": cache.get("row_count"),
            "next_step": "V2.1 stale/rollback hardening before wider SQL-first consumers",
            "risk": "low_to_medium_metadata_only",
        },
        {
            "family": "neutral_source_freshness_metadata",
            "status": "partially_active_13_rows",
            "next_step": "only expand if manual_dependency and action/deployment vocabulary are kept out or separately gated",
            "risk": "medium because freshness can influence trust posture",
        },
        {
            "family": "entry_stop_reference_metadata",
            "status": "active_252_rows_reference_only",
            "next_step": "typed read-only views and no-drift consumer migration, not authority expansion",
            "risk": "medium/high because prices/stops can influence action if misused",
        },
        {
            "family": "analyst_consensus_metadata",
            "status": "future_candidate_review_support_only",
            "next_step": "stage from tmp/analyst-consensus-current.json with source_url/provider/staleness/manual_review flags; never buy/sell authority",
            "risk": "medium because analyst targets can bias deployment decisions",
        },
        {
            "family": "official_ir_field_lineage_metadata",
            "status": "future_candidate_low_risk_lineage",
            "next_step": "stage official-source capture field hashes/period/source paths as evidence routing metadata",
            "risk": "low if values remain evidence/provenance only",
        },
        {
            "family": "deployment_or_action_state_metadata",
            "status": "held",
            "next_step": "do not activate unless renamed into neutral proof vocabulary with exact approval and negative tests",
            "risk": "high",
        },
        {
            "family": "sizing_sleeve_cash_risk_rule_execution",
            "status": "blocked_from_sql_canon_v2",
            "next_step": "keep in gated proposal/apply workflows only",
            "risk": "forbidden without separate explicit gate; never execution authority",
        },
    ]


def build_plan() -> dict[str, Any]:
    generated_at = utc_now()
    cache = canon_cache_snapshot()
    validation = validation_context()
    plan = {
        "schema_version": "sql_canon_v2_prototype_plan.v1",
        "generated_at_utc": generated_at,
        "status": "v2_plan_ready_blocked_on_stale_phase3f_targets" if validation["phase3f_status"] == "blocked" else "v2_plan_ready",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "activation_allowed_by_this_artifact": False,
        "sql_writes_allowed_by_this_artifact": False,
        "consumer_behavior_change_allowed_by_this_artifact": False,
        "canonical_note_mutation_allowed": False,
        "portfolio_mutation_allowed": False,
        "owner_approval_inferred": False,
        "trade_or_account_action_allowed": False,
        "paper_trade_authority_allowed": False,
        "live_trade_authority_allowed": False,
        "money_movement_allowed": False,
        "current_state": {
            "canon_cache": cache,
            "artifact_index": index_snapshot(ARTIFACT_INDEX_DB, "artifact_index"),
            "workspace_index": index_snapshot(WORKSPACE_INDEX_DB, "workspace_index"),
            "validation_context": validation,
        },
        "v2_phases": v2_phases(),
        "candidate_families": candidate_families(cache, validation),
        "immediate_implementation_recommendation": {
            "name": "V2.1 stale/rollback/typed-readiness gate",
            "reason": "Current Phase 3F preflight is blocked by stale target evidence for the original NVDA lifecycle fields; broad SQL-first advancement should not proceed until stale/drift checks are mechanized and visible.",
            "first_safe_code_step": "extend planner/validator surfaces, not activation; then add typed read-only views/wrappers only after stale gate is green",
            "acceptance": [
                "phase3f no_phase4_target_stale_blockers green for selected target family",
                "canon cache quick_check ok and row counts match approved 265 boundary",
                "forbidden authority true hits = 0",
                "fallback-required consumer tests pass",
            ],
        },
        "stop_lines": [
            "No new SQL-canon rows from this artifact.",
            "No Markdown/canonical note or portfolio mutation.",
            "No dashboard recommendation/deployment/action-state behavior change.",
            "No owner approval inference.",
            "No paper/live trade/account/brokerage/money movement authority.",
            "No config/auth/channel/service/runtime mutation.",
            "Source-open remains required before consequential finance claims.",
        ],
    }
    return plan


def validate_plan(plan: dict[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    def add(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    cache = plan["current_state"]["canon_cache"]
    add("boundary_is_planning_only", plan.get("authority_boundary") == AUTHORITY_BOUNDARY)
    add("activation_not_allowed", plan.get("activation_allowed_by_this_artifact") is False)
    add("sql_writes_not_allowed", plan.get("sql_writes_allowed_by_this_artifact") is False)
    for flag in FORBIDDEN_AUTHORITY_FLAGS:
        if flag in plan:
            add(f"forbidden_false:{flag}", plan.get(flag) is False)
    add("canon_cache_exists", cache.get("exists") is True)
    add("canon_cache_row_count_265", cache.get("row_count") == 265, str(cache.get("row_count")))
    add("approved_authority_boundaries_only", set(cache.get("authority_boundaries", {})) <= {
        "phase7_sql_canon_source_freshness_metadata_exact_thirteen_keys_no_execution_authority",
        "wf72_entry_stop_reference_metadata_exact_key_gated_no_execution_authority",
    }, json.dumps(cache.get("authority_boundaries", {}), sort_keys=True))
    add("artifact_index_quick_check_ok", plan["current_state"]["artifact_index"].get("integrity_check") == "ok", str(plan["current_state"]["artifact_index"].get("integrity_check")))
    add("workspace_index_available", plan["current_state"]["workspace_index"].get("exists") is True)
    add("phase3f_blocker_visible", plan["current_state"]["validation_context"].get("phase3f_status") in {"ok", "blocked"})
    add("v2_has_at_least_five_phases", len(plan.get("v2_phases", [])) >= 5)
    add("candidate_families_include_blocked_execution", any(c.get("family") == "sizing_sleeve_cash_risk_rule_execution" and c.get("status") == "blocked_from_sql_canon_v2" for c in plan.get("candidate_families", [])))
    return checks


def render_md(plan: dict[str, Any], checks: list[dict[str, Any]]) -> str:
    failed = [c for c in checks if not c["ok"]]
    lines = [
        "# SQL Canon V2 Prototype Plan",
        "",
        f"Generated: `{plan['generated_at_utc']}`",
        f"Status: `{plan['status']}`",
        f"Boundary: `{plan['authority_boundary']}`",
        "",
        "## Current baseline",
        f"- Canon cache rows: `{plan['current_state']['canon_cache'].get('row_count')}`",
        f"- Authority boundaries: `{json.dumps(plan['current_state']['canon_cache'].get('authority_boundaries', {}), sort_keys=True)}`",
        f"- Phase3F status: `{plan['current_state']['validation_context'].get('phase3f_status')}`",
        f"- Failed validation checks visible: `{len(plan['current_state']['validation_context'].get('phase3f_failed_checks', []))}`",
        "",
        "## V2 phases",
    ]
    for phase in plan["v2_phases"]:
        lines.extend([
            f"### {phase['phase']}",
            f"- Objective: {phase['objective']}",
            f"- Authority: {phase['authority']}",
            f"- Deliverables: {', '.join(phase['deliverables'])}",
            f"- Acceptance: {', '.join(phase['acceptance'])}",
            "",
        ])
    lines.append("## Candidate families")
    for family in plan["candidate_families"]:
        lines.append(f"- `{family['family']}` - `{family['status']}` / risk `{family['risk']}` / next: {family['next_step']}")
    lines.extend([
        "",
        "## Immediate recommendation",
        f"- {plan['immediate_implementation_recommendation']['name']}: {plan['immediate_implementation_recommendation']['reason']}",
        "",
        "## Stop lines",
    ])
    lines.extend([f"- {s}" for s in plan["stop_lines"]])
    lines.extend([
        "",
        "## Validation",
        f"- Checks: `{len(checks)}`",
        f"- Failed: `{len(failed)}`",
    ])
    if failed:
        lines.append("- Failed checks:")
        lines.extend([f"  - `{c['name']}`: {c['detail']}" for c in failed])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate SQL-canon V2 prototype plan and validation")
    parser.add_argument("--write", action="store_true", help="write tmp/sql-canon-v2-prototype-plan.json/.md")
    parser.add_argument("--validate", action="store_true", help="validate generated plan")
    parser.add_argument("--no-md", action="store_true", help="skip markdown output")
    args = parser.parse_args()

    plan = build_plan()
    checks = validate_plan(plan)
    failed = [c for c in checks if not c["ok"]]
    plan["validation"] = {"status": "ok" if not failed else "blocked", "checks": checks, "summary": {"checks": len(checks), "failed": len(failed)}}
    if args.write:
        OUT_JSON.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if not args.no_md:
            OUT_MD.write_text(render_md(plan, checks), encoding="utf-8")
    print(json.dumps({
        "status": plan["validation"]["status"],
        "plan_status": plan["status"],
        "checks": len(checks),
        "failed": len(failed),
        "outputs": [str(OUT_JSON.relative_to(WORKSPACE)).replace("\\", "/")] + ([] if args.no_md else [str(OUT_MD.relative_to(WORKSPACE)).replace("\\", "/")]),
        "canon_cache_rows": plan["current_state"]["canon_cache"].get("row_count"),
        "phase3f_status": plan["current_state"]["validation_context"].get("phase3f_status"),
    }, indent=2))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
