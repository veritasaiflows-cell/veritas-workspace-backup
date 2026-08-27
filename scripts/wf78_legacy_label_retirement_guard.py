#!/usr/bin/env python3
"""Report-only WF78 legacy-label retirement guard.

Replaces the retired tier-coherence validator. That validator compared the
auto-router tier against the `legacy_universe_tier` compatibility label and
produced a recurring disagreement count that was label-sync debt, not a real
routing defect. The label was retired from the active data plane on 2026-08-20.

This guard tracks the two things that actually matter now:

1. Reintroduction: `legacy_universe_tier` must not reappear in the canonical
   data-plane schema or in active routing/consumer scripts. Any reappearance is
   a blocking error.
2. Seed dependency: tickers whose tier is seeded from the source universe
   `tier` label instead of auto-router evidence. Target is zero. These are
   reported as warnings because retiring the routing seed is a separate,
   owner-gated change that would move real tier assignments.

Report-only: no canon, portfolio, membership, label, capital, or execution
authority.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
SCRIPTS = ROOT / "scripts"
CANON_DB = TMP / "canonical-finance-data-plane.sqlite"
AUTO_ROUTER = TMP / "wf78-auto-tier-routing.json"
LABEL_REGISTER = TMP / "wf78-tier-label-decision-register.json"
DEFAULT_OUT = TMP / "wf78-legacy-label-retirement-guard.json"

SCHEMA = "veritas.wf78_legacy_label_retirement_guard.v1"

RETIRED_FIELD = "legacy_universe_tier"
RETIREMENT_DATE = "2026-08-20"
ARCHIVE_DIR = "09. Archive/WF78 Legacy Universe Tier Retirement/2026-08-20"

# The routing seed in wf78_auto_tier_router.default_state is deliberately still
# live; retiring it moves real tier assignments and needs its own owner gate.
SEED_OWNER_SCRIPT = "wf78_auto_tier_router.py"

AUTHORITY_BOUNDARY: dict[str, bool] = {
    "review_only": True,
    "report_only": True,
    "auto_router_is_current_tier_authority": True,
    "legacy_label_retired_from_active_data_plane": True,
    "canon_or_portfolio_mutation_allowed": False,
    "universe_mutation_allowed": False,
    "sql_canon_mutation_allowed": False,
    "schema_mutation_allowed": False,
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
    "auto_router_is_current_tier_authority",
    "legacy_label_retired_from_active_data_plane",
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


def add_check(checks: list[dict[str, Any]], name: str, ok: bool, detail: Any, severity: str = "error") -> None:
    checks.append({"check": name, "status": "ok" if ok else severity, "detail": detail})


def db_columns() -> list[str]:
    if not CANON_DB.exists():
        return []
    con = sqlite3.connect(f"file:{CANON_DB.as_posix()}?mode=ro", uri=True)
    try:
        return [row[1] for row in con.execute("PRAGMA table_info(universe_membership)")]
    finally:
        con.close()


def script_references() -> list[dict[str, Any]]:
    """Active-script occurrences of the retired field, excluding this guard."""
    hits: list[dict[str, Any]] = []
    for path in sorted(SCRIPTS.glob("*.py")):
        if path.name == Path(__file__).name:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if RETIRED_FIELD not in text:
            continue
        for number, line in enumerate(text.splitlines(), start=1):
            if RETIRED_FIELD in line:
                hits.append({"path": rel(path), "line": number, "text": line.strip()[:200]})
    return hits


def normalize_tier(value: Any) -> str:
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


def label_record_lookup(register: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Map ticker -> owner-approved label semantics from its approving record."""
    out: dict[str, dict[str, Any]] = {}
    for record in as_list(register.get("records")):
        record = as_dict(record)
        semantics = as_dict(record.get("label_semantics"))
        for ticker in as_list(record.get("approved_tickers")):
            out[str(ticker).strip().upper()] = {
                "decision_id": record.get("decision_id"),
                "approval_reference": record.get("approval_reference"),
                "tier": semantics.get("tier"),
                "role": semantics.get("role"),
                "deployment_ready": semantics.get("deployment_ready"),
            }
    return out


def router_ahead_of_approved_label(router: dict[str, Any], register: dict[str, Any]) -> list[dict[str, Any]]:
    """Names where the current router tier differs from the owner-approved label.

    The retired validator only evaluated this over legacy-ahead rows. It is now
    evaluated over every routed ticker, so the signal no longer depends on the
    retired label.
    """
    labels = label_record_lookup(register)
    out: list[dict[str, Any]] = []
    for row in as_list(router.get("rows")):
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker") or "").strip().upper()
        label = labels.get(ticker)
        if not label:
            continue
        approved = normalize_tier(label.get("tier"))
        current = normalize_tier(row.get("auto_tier"))
        if not approved or approved == current:
            continue
        out.append({
            "ticker": ticker,
            "current_tier": current,
            "owner_approved_label_tier": approved,
            "owner_approved_role": label.get("role"),
            "deployment_ready": bool(label.get("deployment_ready")),
            "approval_reference": label.get("approval_reference"),
            "recommended_owner_decision": "review_router_ahead_of_owner_approved_label",
        })
    out.sort(key=lambda r: r["ticker"])
    return out


def seed_rows(router: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for row in as_list(router.get("rows")):
        if not isinstance(row, dict) or not row.get("tier_seeded_from_legacy_label"):
            continue
        rows.append({
            "ticker": row.get("ticker"),
            "name": row.get("name"),
            "current_tier": row.get("auto_tier"),
            "current_state": row.get("auto_state"),
            "route_reason": row.get("route_reason"),
            "remediation": "Route this ticker on auto-router evidence or accept an explicit owner-dated tier decision.",
        })
    rows.sort(key=lambda r: (str(r.get("current_tier") or ""), str(r.get("ticker") or "")))
    return rows


def build_report() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    columns = db_columns()
    refs = script_references()
    router = as_dict(load_json_artifact(AUTO_ROUTER))
    register = as_dict(load_json_artifact(LABEL_REGISTER))
    rows = as_list(router.get("rows"))
    seeded = seed_rows(router)
    label_ahead = router_ahead_of_approved_label(router, register)

    column_present = RETIRED_FIELD in columns
    add_check(checks, "canon_db_present", bool(columns), rel(CANON_DB))
    add_check(checks, "retired_field_absent_from_schema", not column_present, columns)
    add_check(checks, "retired_field_absent_from_active_scripts", not refs, refs[:10])
    add_check(checks, "auto_router_present", bool(rows), rel(AUTO_ROUTER))
    add_check(checks, "auto_router_status_ok", router.get("status") == "ok", router.get("status"))
    add_check(
        checks,
        "router_exposes_seed_dependency_field",
        any(isinstance(r, dict) and "tier_seeded_from_legacy_label" in r for r in rows),
        "tier_seeded_from_legacy_label",
    )

    if column_present:
        errors.append({
            "severity": "critical",
            "code": "retired_legacy_label_column_reintroduced",
            "message": f"`{RETIRED_FIELD}` reappeared in universe_membership after retirement on {RETIREMENT_DATE}.",
            "detail": {"columns": columns},
        })
    if refs:
        errors.append({
            "severity": "critical",
            "code": "retired_legacy_label_referenced_by_active_script",
            "message": f"`{RETIRED_FIELD}` is referenced by active scripts after retirement on {RETIREMENT_DATE}.",
            "detail": {"reference_count": len(refs), "references": refs[:20]},
        })
    if not rows:
        errors.append({
            "severity": "critical",
            "code": "auto_router_artifact_missing_or_empty",
            "message": "Cannot evaluate seed dependency without the auto-router artifact.",
            "detail": {"path": rel(AUTO_ROUTER)},
        })
    if seeded:
        warnings.append({
            "severity": "warning",
            "code": "tier_seeded_from_legacy_label",
            "message": (
                f"{len(seeded)} ticker(s) still take their tier from the source universe label "
                f"instead of auto-router evidence. Retiring the seed in {SEED_OWNER_SCRIPT} is a "
                "separate owner-gated change because it moves real tier assignments."
            ),
            "detail": {"tickers": [r["ticker"] for r in seeded]},
        })

    for flag in REQUIRED_TRUE_FLAGS:
        add_check(checks, f"authority_{flag}_true", AUTHORITY_BOUNDARY.get(flag) is True, AUTHORITY_BOUNDARY.get(flag))
    for flag in REQUIRED_FALSE_FLAGS:
        add_check(checks, f"authority_{flag}_false", AUTHORITY_BOUNDARY.get(flag) is False, AUTHORITY_BOUNDARY.get(flag))

    tier_counts = Counter(str(r.get("current_tier") or "unknown") for r in seeded)

    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "blocked" if errors else "ok",
        "workflow": "WF78 - Legacy Label Retirement Guard",
        "purpose": (
            f"Prove `{RETIRED_FIELD}` stays retired from the active data plane and track how many "
            "tickers still take their tier from a legacy seed instead of auto-router evidence."
        ),
        "authority_boundary": AUTHORITY_BOUNDARY,
        "replaces": {
            "retired_validator": "scripts/wf78_tier_coherence_validator.py",
            "retired_metric": "disagreement_count (auto-router vs legacy_universe_tier)",
            "retired_on": RETIREMENT_DATE,
            "one_time_migration_proof": f"{ARCHIVE_DIR}/wf78-tier-coherence-FINAL-migration-proof.json",
            "historical_label_snapshot": f"{ARCHIVE_DIR}/historical-legacy-universe-tier-snapshot.json",
        },
        "source_artifacts": {
            "canon_data_plane": rel(CANON_DB),
            "auto_router": rel(AUTO_ROUTER),
            "tier_label_decision_register": rel(LABEL_REGISTER),
        },
        "summary": {
            "current_tier_authority": rel(AUTO_ROUTER),
            "active_legacy_label_refs": len(refs),
            "retired_field_in_schema": column_present,
            "ticker_count": len(rows),
            "legacy_seeded_tier_count": len(seeded),
            "legacy_seeded_tier_counts": dict(sorted(tier_counts.items())),
            "legacy_seeded_tickers": [r["ticker"] for r in seeded],
            "router_ahead_of_owner_approved_label_count": len(label_ahead),
            "router_ahead_of_owner_approved_label_tickers": [r["ticker"] for r in label_ahead],
            "seed_retirement_owner_gated": True,
            "seed_owner_script": f"scripts/{SEED_OWNER_SCRIPT}",
            "headline": (
                f"active_legacy_label_refs={len(refs)} (target 0); "
                f"legacy_seeded_tier_count={len(seeded)} (target 0, owner-gated)."
            ),
            "next_safe_action": (
                (
                    "Zero refs and zero seeded tiers: the retired label and the routing seed both stay "
                    "retired. Any non-zero count here means a second label source was reintroduced; "
                    f"trace it in scripts/{SEED_OWNER_SCRIPT} before trusting routing output."
                )
                if not refs and not seeded
                else (
                    "Non-zero counts mean a legacy label source is driving routing. Run an owner-approved "
                    "shadow diff of the router with the legacy seed disabled and review the tier deltas "
                    "before applying."
                )
            ),
        },
        "legacy_seeded_rows": seeded,
        "router_ahead_of_owner_approved_label": label_ahead,
        "active_legacy_label_references": refs,
        "validation": {
            "status": "ok" if not errors else "error",
            "errors": errors,
            "warnings": warnings,
            "checks": checks,
        },
        "stop_lines": [
            "This guard is report-only and mutates no schema, label, membership, or canon surface.",
            "A clean guard result is not a promotion, label-sync apply, or capital/execution approval.",
            "Retiring the routing seed changes real tier assignments and requires separate owner approval.",
            f"The archived legacy label is historical evidence only and must never drive current routing.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_report()
    out = args.out if args.out.is_absolute() else ROOT / args.out
    if args.write:
        atomic_write_json(out, report)
    validation = as_dict(report.get("validation"))
    print(json.dumps({
        "status": report.get("status"),
        "out": rel(out),
        "summary": report.get("summary"),
        "validation": {
            "status": validation.get("status"),
            "errors": len(as_list(validation.get("errors"))),
            "warnings": len(as_list(validation.get("warnings"))),
        },
    }, indent=1))
    if args.validate and validation.get("status") != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
