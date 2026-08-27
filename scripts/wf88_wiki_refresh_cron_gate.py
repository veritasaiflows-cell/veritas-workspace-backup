#!/usr/bin/env python3
"""Validate the WF88 daily refresh cron's hard guardrails.

Producer packets may carry unrelated workflow warnings or owner-gated hard
stops. This gate checks only the conditions that decide whether the daily
outcome-grading/wiki refresh can quietly complete: outcome grades exist, the
recommendation leak guard is clean, and no auto-apply/execution authority leaked
into the refreshed surfaces.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
GRADING = TMP / "recommendation-outcome-grading-cadence.json"
RECOMMENDATION_LEDGER = TMP / "recommendation-outcome-ledger-current.json"
FINANCE_DIGEST = TMP / "finance-decision-performance-digest.json"
WF88_OS2 = TMP / "wf88-os2-control-packet.json"
WF88_WIKI = TMP / "wf88-wiki-synthesis-packet.json"
OUT = TMP / "wf88-wiki-refresh-cron-gate.json"

SCHEMA = "veritas.wf88_wiki_refresh_cron_gate.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "cron_gate_only": True,
    "auto_apply_allowed": False,
    "delete_archive_move_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "config_auth_runtime_mutation_allowed": False,
    "finance_canon_or_portfolio_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "model_training_claim_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def load(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def int_value(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def build_payload(paths: dict[str, Path]) -> dict[str, Any]:
    grading = load(paths["grading"])
    recommendation = load(paths["recommendation_ledger"])
    digest = load(paths["finance_digest"])
    os2 = load(paths["wf88_os2"])
    wiki = load(paths["wf88_wiki"])

    grading_summary = as_dict(grading.get("summary"))
    recommendation_durable = as_dict(recommendation.get("durable_v2_ledger"))
    os2_summary = as_dict(os2.get("summary"))
    wiki_summary = as_dict(wiki.get("summary"))
    leak_guard = as_dict(wiki.get("recommendation_leak_guard"))
    digest_wf55 = as_dict(digest.get("wf55_recommendation_outcomes"))

    hard_checks = {
        "grading_validation_ok": as_dict(grading.get("validation")).get("status") == "ok",
        "grading_events_present": int_value(grading_summary.get("total_grade_event_count_after_append")) > 0
        or int_value(grading_summary.get("existing_grade_event_count")) > 0,
        "recommendation_ledger_grade_count_positive": int_value(recommendation_durable.get("later_outcome_graded_rows")) > 0,
        "finance_digest_grade_count_positive": int_value(digest_wf55.get("outcome_grade_assigned_count")) > 0,
        "os2_grade_count_positive": int_value(os2_summary.get("recommendation_later_outcome_graded_rows")) > 0,
        "wiki_grade_count_positive": int_value(wiki_summary.get("recommendation_later_outcome_graded_rows")) > 0,
        "recommendation_leak_guard_pass": leak_guard.get("pass") is True,
        "open_unrouted_recommendation_count_zero": int_value(leak_guard.get("open_unrouted_recommendation_count")) == 0,
        "auto_apply_count_zero": int_value(leak_guard.get("auto_apply_count")) == 0,
    }
    errors = [name for name, passed in hard_checks.items() if not passed]
    warnings: list[str] = []
    wiki_validation_status = as_dict(wiki.get("validation")).get("status")
    os2_validation_status = as_dict(os2.get("validation")).get("status")
    if wiki_validation_status not in (None, "ok"):
        warnings.append(f"wiki_validation_status:{wiki_validation_status}")
    if os2_validation_status not in (None, "ok"):
        warnings.append(f"os2_validation_status:{os2_validation_status}")

    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok" if not errors else "blocked",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "hard_checks": hard_checks,
        "summary": {
            "recommendation_later_outcome_graded_rows": int_value(recommendation_durable.get("later_outcome_graded_rows")),
            "finance_digest_grade_count": int_value(digest_wf55.get("outcome_grade_assigned_count")),
            "os2_recommendation_later_outcome_graded_rows": int_value(os2_summary.get("recommendation_later_outcome_graded_rows")),
            "wiki_recommendation_later_outcome_graded_rows": int_value(wiki_summary.get("recommendation_later_outcome_graded_rows")),
            "open_unrouted_recommendation_count": int_value(leak_guard.get("open_unrouted_recommendation_count")),
            "auto_apply_count": int_value(leak_guard.get("auto_apply_count")),
            "wiki_validation_status": wiki_validation_status,
            "os2_validation_status": os2_validation_status,
        },
        "inputs": {key: rel(path) for key, path in paths.items()},
        "validation": {
            "status": "ok" if not errors else "blocked",
            "errors": errors,
            "warnings": warnings,
        },
        "boundary": "Cron gate only. Does not mutate cron, wiki, finance, canon, portfolio, account, or execution state.",
    }
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--grading", type=Path, default=GRADING)
    parser.add_argument("--recommendation-ledger", type=Path, default=RECOMMENDATION_LEDGER)
    parser.add_argument("--finance-digest", type=Path, default=FINANCE_DIGEST)
    parser.add_argument("--wf88-os2", type=Path, default=WF88_OS2)
    parser.add_argument("--wf88-wiki", type=Path, default=WF88_WIKI)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    return parser.parse_args()


def abs_path(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def main() -> int:
    args = parse_args()
    paths = {
        "grading": abs_path(args.grading),
        "recommendation_ledger": abs_path(args.recommendation_ledger),
        "finance_digest": abs_path(args.finance_digest),
        "wf88_os2": abs_path(args.wf88_os2),
        "wf88_wiki": abs_path(args.wf88_wiki),
    }
    payload = build_payload(paths)
    out = abs_path(args.out)
    if args.write:
        atomic_write_json(out, payload)
    print(json.dumps({
        "status": payload.get("status"),
        "validation": payload.get("validation"),
        "summary": payload.get("summary"),
        "out": rel(out) if args.write else None,
    }, indent=2, sort_keys=True))
    if args.validate and as_dict(payload.get("validation")).get("status") != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
