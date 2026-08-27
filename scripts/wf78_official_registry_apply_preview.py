#!/usr/bin/env python3
"""Build a gated apply preview for WF78 official registry proposal rows.

The preview creates diff/hash/proposed-registry proof only. It does not apply
the proposal to the official registry, ticker cards, canon, portfolio,
deployment surfaces, SQL canon/cache, or any execution/account surface.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
REGISTRY = ROOT / "data" / "finance" / "wf78-source-open-official-registry.json"
PROPOSAL = TMP / "wf78-official-registry-proposal.json"
OUT = TMP / "wf78-official-registry-apply-preview.json"
PROPOSED_OUT = TMP / "wf78-official-registry-proposed.preview.json"
SCHEMA = "veritas.wf78_official_registry_apply_preview.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "apply_preview_only": True,
    "proposal_applied": False,
    "registry_mutation_allowed": False,
    "ticker_card_mutation_allowed": False,
    "deployment_surface_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "sql_canon_mutation_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "config_auth_runtime_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_allowed": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "owner_approval_inferred": False,
}


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


def load_dict(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def ticker(value: Any) -> str:
    return str(value or "").strip().upper()


def stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_text(value: Any) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()


def proposed_row(row: dict[str, Any]) -> dict[str, Any]:
    proposed = as_dict(row.get("proposed_registry_row"))
    return {
        "official_earnings_source_url": proposed.get("official_earnings_source_url"),
        "source_label": proposed.get("source_label"),
        "period_label": proposed.get("period_label"),
        "source_section": proposed.get("source_section"),
    }


def build_proposed_registry(registry: dict[str, Any], proposal: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
    proposed = deepcopy(registry) if registry else {"schema_version": 1, "tickers": {}}
    proposed.setdefault("tickers", {})
    tickers = as_dict(proposed.get("tickers"))
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    for item in as_list(proposal.get("rows")):
        item = as_dict(item)
        symbol = ticker(item.get("ticker"))
        action = item.get("proposal_action")
        if not symbol:
            errors.append("proposal row missing ticker")
            continue
        if action != "propose_add_registry_row":
            rows.append({
                "ticker": symbol,
                "preview_action": "skip",
                "reason": action,
                "apply_allowed": False,
            })
            continue
        if symbol in tickers:
            rows.append({
                "ticker": symbol,
                "preview_action": "blocked_existing_row_present",
                "reason": "existing registry row would be overwritten",
                "apply_allowed": False,
            })
            continue
        new_row = proposed_row(item)
        if not new_row.get("official_earnings_source_url"):
            rows.append({
                "ticker": symbol,
                "preview_action": "blocked_missing_official_url",
                "reason": "proposal lacks official_earnings_source_url",
                "apply_allowed": False,
            })
            continue
        tickers[symbol] = new_row
        rows.append({
            "ticker": symbol,
            "preview_action": "would_add_registry_row",
            "reason": "conflict-free not-applied proposal row",
            "apply_allowed": False,
            "old_row_sha256": None,
            "new_row_sha256": sha256_text(new_row),
            "proposed_registry_row": new_row,
            "supporting_company_ir_url": item.get("supporting_company_ir_url"),
            "owner_entry_stop_lineage_still_required": bool(item.get("owner_entry_stop_lineage_still_required")),
        })
    proposed["tickers"] = dict(sorted(tickers.items()))
    proposed["generated_at_utc"] = registry.get("generated_at_utc") if registry else None
    return proposed, rows, errors


def build(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    registry = load_dict(REGISTRY)
    proposal = load_dict(PROPOSAL)
    proposed_registry, rows, errors = build_proposed_registry(registry, proposal)
    warnings: list[str] = []
    current_tickers = as_dict(registry.get("tickers"))
    proposed_tickers = as_dict(proposed_registry.get("tickers"))
    actions = Counter(str(row.get("preview_action")) for row in rows)
    for key, value in AUTHORITY_BOUNDARY.items():
        if key not in {"review_only", "apply_preview_only"} and value is not False:
            errors.append(f"authority flag not false: {key}")
    if args.validate and not rows:
        warnings.append("no_preview_rows_generated")
    if any(row.get("apply_allowed") for row in rows):
        errors.append("preview row implies apply_allowed")
    status = "blocked" if errors else "ok_no_work" if not rows else "ok"
    validation_status = "blocked" if errors else "warning" if warnings else "ok"
    report = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "purpose": "Review-only official registry apply preview; no registry mutation.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": [rel(PROPOSAL), rel(REGISTRY)],
        "preview_outputs": {
            "proposed_registry_path": rel(args.proposed_out),
            "proposed_registry_written": bool(args.write_proposed),
            "registry_apply_executed": False,
        },
        "summary": {
            "current_registry_count": len(current_tickers),
            "preview_registry_count": len(proposed_tickers),
            "preview_row_count": len(rows),
            "would_add_count": actions.get("would_add_registry_row", 0),
            "blocked_or_skipped_count": len(rows) - actions.get("would_add_registry_row", 0),
            "preview_action_counts": dict(actions),
            "current_registry_sha256": sha256_text(registry),
            "proposed_registry_sha256": sha256_text(proposed_registry),
            "registry_apply_executed": False,
            "next_safe_action": "Use this preview for owner/gate review only; applying the registry requires a separate exact approval path.",
        },
        "rows": rows,
        "validation": {"status": validation_status, "errors": errors, "warnings": warnings},
        "stop_lines": [
            "Apply preview only; no registry/card/deployment/canon/portfolio/SQL-canon mutation.",
            "No capital deployment, paper/live execution, brokerage/account action, money movement, customer output, or owner approval inference.",
        ],
    }
    return report, proposed_registry


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build WF78 official registry apply preview.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-proposed", action="store_true", help="Also write the proposed registry preview artifact under tmp/.")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--proposed-out", type=Path, default=PROPOSED_OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report, proposed_registry = build(args)
    if args.write:
        atomic_write_json(args.out, report)
        print(f"wrote {rel(args.out)} status={report['status']} would_add={report['summary']['would_add_count']}")
    else:
        print(json.dumps(report["summary"], indent=2))
    if args.write_proposed:
        atomic_write_json(args.proposed_out, proposed_registry)
        print(f"wrote {rel(args.proposed_out)} preview_only=true")
    if args.validate and report["validation"]["status"] == "blocked":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
