#!/usr/bin/env python3
"""Apply bounded WF78 repair rows into generated ticker-card fields.

This is intentionally narrow: it updates only generated
tmp/ticker-intelligence-cards/*.current.json files from already-built WF78
review artifacts. It does not mutate canon, portfolio notes, deployment
surfaces, SQL canon, cash/sizing rules, or any execution/account surface.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
CARD_DIR = TMP / "ticker-intelligence-cards"
DEFAULT_OUT = TMP / "wf78-ticker-card-field-repair-apply.json"
BACKUP_ROOT = TMP / "wf78-ticker-card-field-repair-backups"

POSITION_PROPOSAL = TMP / "wf78-position-sizing-integration-proposal.json"
BAND_CONTEXT_REPAIR = TMP / "wf78-missing-band-context-repair.json"
DEPLOYMENT_REVIEW = TMP / "wf78-deployment-readiness-review.json"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "generated_ticker_card_field_repair_allowed": True,
    "allowed_target": "tmp/ticker-intelligence-cards/*.current.json",
    "canonical_note_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "deployment_surface_mutation_allowed": False,
    "sql_canon_mutation_allowed": False,
    "cash_or_risk_rule_mutation_allowed": False,
    "sizing_apply_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "capital_deployment_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_allowed": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "paper_order_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "owner_approval_inferred": False,
}

EXPECTED = {
    "position_sizing_ready": 23,
    "deployment_readiness": 3,
    "band_context_recheck": 2,
}

REPAIR_PRIORITY = {
    "position_sizing_ready": 0,
    "band_context_recheck": 1,
    "deployment_readiness": 2,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load_dict(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def card_path(ticker: str) -> Path:
    return CARD_DIR / f"{ticker.upper()}.current.json"


def price_band_payload(row: dict[str, Any], *, source: str, price_source: str | None = None) -> dict[str, Any]:
    band = as_dict(row.get("band"))
    price = row.get("current_price")
    if price is None:
        context = as_dict(row.get("current_band_context"))
        price = context.get("latest_known_price")
        band = {
            "entry_band_low": context.get("entry_band_low"),
            "entry_band_high": context.get("entry_band_high"),
            "stop_or_invalidation": context.get("stop_or_invalidation"),
        }
    status = row.get("band_status") or row.get("fresh_band_status") or as_dict(row.get("current_band_context")).get("band_status")
    return {
        "latest_known_price": price,
        "price_source": price_source or source,
        "entry_band_low": band.get("entry_band_low"),
        "entry_band_high": band.get("entry_band_high"),
        "stop_or_invalidation": band.get("stop_or_invalidation"),
        "band_status": status,
        "band_source": source,
        "stop_source": source,
        "fresh_quote_required": False,
        "staleness_note": None,
    }


def posture_for_band(row: dict[str, Any], repair_type: str) -> tuple[str, str, list[str]]:
    band_state = str(row.get("band_state") or "")
    band_status = str(row.get("band_status") or row.get("fresh_band_status") or as_dict(row.get("current_band_context")).get("band_status") or "")
    if repair_type == "deployment_readiness":
        return (
            "no chase" if band_status == "ABOVE_BAND" else "deployment-readiness review",
            "deployment_readiness_review",
            ["deployment-readiness row is review-only; no capital or execution authority"],
        )
    if band_state.startswith("below_stop") or band_status == "BELOW_STOP":
        return ("invalidation review", "invalidation_review", ["below stop/invalidation; review as risk/invalidation row, not a buy candidate"])
    if band_state.startswith("below_band") or band_status == "BELOW_BAND":
        return ("wait/reclaim review", "wait_reclaim_review", ["below entry band; wait for re-entry/reclaim or owner-approved band review"])
    if band_state.startswith("above_band") or band_status == "ABOVE_BAND":
        return ("no chase", "no_chase", ["above entry band; do not chase"])
    if band_state.startswith("in_band") or band_status == "IN_BAND":
        return ("promotion review", "promotion_review", ["in band for review only; owner approval still required before any capital/execution action"])
    return ("review only", "review_only", ["review-only repaired card field; source-open review still required"])


def remove_family(card: dict[str, Any], families: set[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    kept: list[dict[str, Any]] = []
    removed: list[dict[str, Any]] = []
    for item in as_list(card.get("missing_or_stale_evidence")):
        if isinstance(item, dict) and item.get("family") in families:
            removed.append(item)
        elif isinstance(item, dict):
            kept.append(item)
    return kept, removed


def patch_recommendation(card: dict[str, Any], row: dict[str, Any], repair_type: str, removed_families: set[str]) -> dict[str, Any]:
    recommendation = dict(as_dict(card.get("recommendation_support")))
    posture, posture_key, blockers = posture_for_band(row, repair_type)
    existing = [item for item in as_list(recommendation.get("blockers_or_gates")) if item not in removed_families]
    authority_blocker = "card itself grants no paper/live execution authority and infers no approval"
    merged = []
    for item in [*blockers, *existing, authority_blocker]:
        if item and item not in merged:
            merged.append(item)
    recommendation.update(
        {
            "posture": posture,
            "posture_key": posture_key,
            "support_level": "wf78_repair_integrated_review_context",
            "band_status": row.get("band_status") or row.get("fresh_band_status") or as_dict(row.get("current_band_context")).get("band_status"),
            "fresh_quote_required": False,
            "actionability": "review_only_owner_gated",
            "blockers_or_gates": merged,
        }
    )
    return recommendation


def source_lineage(row: dict[str, Any]) -> dict[str, Any]:
    lineage = as_dict(row.get("source_lineage")) or as_dict(row.get("owner_source_lineage"))
    context = as_dict(row.get("current_band_context"))
    if context:
        lineage = {
            "available": True,
            "owner_source_path": context.get("owner_source_path"),
            "owner_source_timestamp": context.get("owner_source_timestamp"),
            "owner_source_sha256": context.get("owner_source_sha256"),
        }
    return lineage


def apply_row(card: dict[str, Any], row: dict[str, Any], repair_type: str, run_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    ticker = str(row.get("ticker") or "").upper()
    patched = deepcopy(card)
    source = {
        "position_sizing_ready": rel(POSITION_PROPOSAL),
        "band_context_recheck": rel(BAND_CONTEXT_REPAIR),
        "deployment_readiness": rel(DEPLOYMENT_REVIEW),
    }[repair_type]
    price_source = "yfinance 1y close history" if repair_type == "band_context_recheck" else source
    pbs = price_band_payload(row, source=source, price_source=price_source)
    removed_families = {"price_band_stop_position_sizing"}
    if repair_type == "deployment_readiness":
        removed_families = {"deployment_readiness_surface"}

    missing, removed = remove_family(patched, removed_families)
    patched["latest_known_price"] = pbs["latest_known_price"]
    patched["price_band_stop"] = pbs
    patched.setdefault("thesis_bull_bear_entry_context", {})["entry_context"] = pbs
    patched.setdefault("technical_posture", {})["band_status"] = pbs["band_status"]
    if pbs["latest_known_price"] is not None:
        patched.setdefault("technical_posture", {})["latest_close"] = pbs["latest_known_price"]
    patched["missing_or_stale_evidence"] = missing
    patched["recommendation_support"] = patch_recommendation(patched, row, repair_type, removed_families)
    patched.setdefault("portfolio_fit_concentration", {})["wf78_repair_source"] = {
        "repair_type": repair_type,
        "source_artifact": source,
        "tier": row.get("tier") or row.get("auto_tier"),
        "route_state": row.get("route_state"),
        "readiness_impact": row.get("readiness_impact"),
    }
    patched["wf78_card_field_repair"] = {
        "schema": "veritas.wf78_ticker_card_field_repair.v1",
        "run_id": run_id,
        "applied_at_utc": utc_now(),
        "repair_type": repair_type,
        "source_artifact": source,
        "source_lineage": source_lineage(row),
        "removed_missing_or_stale_families": sorted(removed_families),
        "removed_missing_or_stale_rows": removed,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    return patched, {
        "ticker": ticker,
        "repair_type": repair_type,
        "source_artifact": source,
        "source_lineage": source_lineage(row),
        "removed_families": sorted(removed_families),
        "removed_count": len(removed),
        "band_status": pbs["band_status"],
        "latest_known_price": pbs["latest_known_price"],
    }


def repair_priority(row: dict[str, Any]) -> tuple[int, str]:
    repair_type = str(row.get("repair_type") or "")
    ticker = str(row.get("ticker") or "").upper()
    return (REPAIR_PRIORITY.get(repair_type, 99), ticker)


def apply_rows(card: dict[str, Any], rows: list[dict[str, Any]], run_id: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    patched = deepcopy(card)
    step_results: list[dict[str, Any]] = []
    for index, row in enumerate(sorted(rows, key=repair_priority), start=1):
        patched, step_result = apply_row(patched, row, str(row["repair_type"]), f"{run_id}:{index}")
        step_results.append(step_result)
    if step_results:
        patched["wf78_card_field_repair_sequence"] = {
            "schema": "veritas.wf78_ticker_card_field_repair_sequence.v1",
            "run_id": run_id,
            "applied_at_utc": utc_now(),
            "repair_types": [step["repair_type"] for step in step_results],
            "source_artifacts": [step["source_artifact"] for step in step_results],
            "steps": step_results,
            "authority_boundary": AUTHORITY_BOUNDARY,
        }
    return patched, step_results


def collect_rows() -> list[dict[str, Any]]:
    position = load_dict(POSITION_PROPOSAL)
    missing = load_dict(BAND_CONTEXT_REPAIR)
    deployment = load_dict(DEPLOYMENT_REVIEW)

    rows: list[dict[str, Any]] = []
    for row in as_list(position.get("rows")):
        if not isinstance(row, dict):
            continue
        if row.get("proposal_status") == "ready_for_review_integration_proposal" and not row.get("residual_blocker"):
            rows.append({"repair_type": "position_sizing_ready", **row})
    for row in as_list(missing.get("rows")):
        if isinstance(row, dict) and row.get("repair_status") == "ready_for_position_sizing_repair_recheck":
            rows.append({"repair_type": "band_context_recheck", **row})
    for row in as_list(deployment.get("rows")):
        if isinstance(row, dict) and row.get("review_status") == "ready_for_non_executing_deployment_readiness_row":
            rows.append({"repair_type": "deployment_readiness", **row})
    return rows


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rows = collect_rows()
    requested_tickers = {t.upper() for t in (args.tickers or [])}
    selected = [row for row in rows if not requested_tickers or str(row.get("ticker") or "").upper() in requested_tickers]
    counts: dict[str, int] = {}
    for row in selected:
        counts[row["repair_type"]] = counts.get(row["repair_type"], 0) + 1
    selected_by_ticker: dict[str, list[dict[str, Any]]] = {}
    for row in selected:
        ticker = str(row.get("ticker") or "").upper()
        selected_by_ticker.setdefault(ticker, []).append(row)

    errors: list[str] = []
    if not args.tickers and counts.get("position_sizing_ready", 0) != EXPECTED["position_sizing_ready"]:
        errors.append(f"expected 23 ready position-sizing rows, got {counts.get('position_sizing_ready', 0)}")
    if not args.tickers and counts.get("deployment_readiness", 0) != EXPECTED["deployment_readiness"]:
        errors.append(f"expected 3 deployment-readiness rows, got {counts.get('deployment_readiness', 0)}")
    if not args.tickers and counts.get("band_context_recheck", 0) != EXPECTED["band_context_recheck"]:
        errors.append(f"expected 2 band-context recheck rows, got {counts.get('band_context_recheck', 0)}")

    results: list[dict[str, Any]] = []
    backup_dir = BACKUP_ROOT / run_id
    for ticker in sorted(selected_by_ticker):
        ticker_rows = selected_by_ticker[ticker]
        path = card_path(ticker)
        if not path.exists():
            errors.append(f"missing card for {ticker}: {rel(path)}")
            continue
        before_text = path.read_text(encoding="utf-8")
        card = json.loads(before_text)
        patched, step_results = apply_rows(card, ticker_rows, run_id)
        after_text = json.dumps(patched, indent=2, sort_keys=False) + "\n"
        changed = before_text != after_text
        results.append(
            {
                "ticker": ticker,
                "repair_type": step_results[-1]["repair_type"] if step_results else None,
                "repair_types": [step["repair_type"] for step in step_results],
                "source_artifacts": [step["source_artifact"] for step in step_results],
                "step_results": step_results,
                "removed_families": sorted({family for step in step_results for family in step.get("removed_families", [])}),
                "removed_count": sum(int(step.get("removed_count") or 0) for step in step_results),
                "band_status": step_results[-1]["band_status"] if step_results else None,
                "latest_known_price": step_results[-1]["latest_known_price"] if step_results else None,
                "card_path": rel(path),
                "changed": changed,
                "before_sha256": sha256_text(before_text),
                "after_sha256": sha256_text(after_text),
                "written": bool(args.apply and changed and not errors),
                "backup_path": rel(backup_dir / f"{ticker}.current.json") if args.apply and changed and not errors else None,
            }
        )
        if args.apply and changed and not errors:
            backup_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, backup_dir / f"{ticker}.current.json")
            atomic_write_json(path, patched, ensure_ascii=False)

    forbidden_true = [
        key for key, value in AUTHORITY_BOUNDARY.items()
        if value is True and key not in {"review_only", "generated_ticker_card_field_repair_allowed"}
    ]
    if forbidden_true:
        errors.append(f"authority boundary widened unexpectedly: {forbidden_true}")

    return {
        "schema": "veritas.wf78_ticker_card_field_repair_apply.v1",
        "generated_at_utc": utc_now(),
        "status": "blocked" if errors else "ok",
        "mode": "apply" if args.apply else "preview",
        "run_id": run_id,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": [rel(POSITION_PROPOSAL), rel(BAND_CONTEXT_REPAIR), rel(DEPLOYMENT_REVIEW)],
        "expected_counts": EXPECTED,
        "selected_counts": counts,
        "selected_tickers": sorted(selected_by_ticker),
        "summary": {
            "selected_count": len(selected),
            "selected_ticker_count": len(selected_by_ticker),
            "changed_count": sum(1 for row in results if row.get("changed")),
            "written_count": sum(1 for row in results if row.get("written")),
            "backup_dir": rel(backup_dir) if args.apply and not errors else None,
        },
        "results": results,
        "validation": {"status": "blocked" if errors else "ok", "errors": errors, "warnings": []},
        "stop_lines": [
            "Only generated ticker-card JSON fields may be repaired.",
            "No canon, portfolio, deployment-surface, SQL-canon, cash/sizing-rule, customer, paper/live, brokerage/account, or money movement authority.",
            "No capital deployment, trade/execution, or owner approval is inferred.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply bounded WF78 repair rows into generated ticker-card fields.")
    parser.add_argument("--apply", action="store_true", help="Write changed card files. Omit for preview.")
    parser.add_argument("--validate", action="store_true", help="Exit non-zero on validation failure.")
    parser.add_argument("--ticker", action="append", dest="tickers", help="Optional ticker filter for smoke tests.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_report(args)
    out = args.out if args.out.is_absolute() else ROOT / args.out
    atomic_write_json(out, report, ensure_ascii=False)
    print(json.dumps({
        "status": report["status"],
        "mode": report["mode"],
        "out": rel(out),
        "summary": report["summary"],
        "selected_counts": report["selected_counts"],
        "validation": report["validation"],
    }, indent=2, sort_keys=True))
    if args.validate and report["validation"]["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
