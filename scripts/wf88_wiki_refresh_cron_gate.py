#!/usr/bin/env python3
"""Validate the WF88 daily refresh cron's hard guardrails.

Producer packets may carry unrelated workflow warnings or owner-gated hard
stops. This gate checks only the conditions that decide whether the daily
outcome/wiki refresh can quietly complete: frozen outcome grades exist, the
recommendation leak guard is clean, and no auto-apply/execution authority leaked
into the refreshed surfaces.

Producer-evidence honesty (fail-closed allowlist): the gate verifies the wiki
packet's embedded producer evidence (retrieval, decision-compiler, RSI
outcome) is fresh AND healthy. A fresh wiki packet timestamp alone never
greens the gate: each descriptor must declare present=true, a non-blank
string status with no failure markers (blocked/fail_closed/fail_open/failed/
critical/error), and validation status exactly ok-or-warning. Missing, blank,
or failure-marked evidence blocks. Review-only warnings (RSI maturity,
decision-compiler review-only state, unexecuted owner-gated pilots) stay
warnings and never become hard failures.
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
# The recommendation grading cadence was retired 2026-09-25 (its feeders stopped
# 2026-08-29); the gate reads the frozen append-only grade history directly.
GRADE_HISTORY = ROOT / "data" / "state-history" / "recommendation-outcome-grades.jsonl"
RECOMMENDATION_LEDGER = TMP / "recommendation-outcome-ledger-current.json"
FINANCE_DIGEST = TMP / "finance-decision-performance-digest.json"
WF88_OS2 = TMP / "wf88-os2-control-packet.json"
WF88_WIKI = TMP / "wf88-wiki-synthesis-packet.json"
OUT = TMP / "wf88-wiki-refresh-cron-gate.json"

SCHEMA = "veritas.wf88_wiki_refresh_cron_gate.v1"

PRODUCER_EVIDENCE = {
    "retrieval_quality_scorecard": {"max_age_hours": 168},
    "wf88_decision_compiler": {"max_age_hours": 24},
    "rsi_outcome_scorecard": {"max_age_hours": 24},
}

EVIDENCE_VALIDATION_ALLOWLIST = {"ok", "warning"}

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


def parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def load(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def jsonl_row_count(path: Path) -> int:
    """Count parseable JSON object rows; a missing file counts zero."""
    if not path.exists():
        return 0
    count = 0
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            try:
                count += isinstance(json.loads(line), dict)
            except json.JSONDecodeError:
                continue
    return count


def int_value(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def blocked_text(value: Any) -> bool:
    text = str(value or "").lower()
    return (
        ("blocked" in text)
        or ("fail_closed" in text)
        or ("fail_open" in text)
        or ("failed" in text)
        or ("critical" in text)
        or ("error" in text)
    )


PRODUCER_STATUS_ALLOWLIST = frozenset({"ok", "warning", "decision_objects_warning_review_only", "wiki_synthesis_warning_no_apply_authority"})


def valid_evidence_status(value: Any) -> bool:
    """Explicit allowlist for producer-evidence statuses.

    Enumerated from test_gate_accepts_known_review_only_statuses and exact
    current producer descriptors (ok / decision_objects_warning_review_only /
    warning). Unknown/banana/hyphenated fail-open/fail-closed and non-string
    types reject; legitimate review-only states still pass.
    """
    return isinstance(value, str) and value.strip() in PRODUCER_STATUS_ALLOWLIST


def producer_evidence_healthy(descriptor: dict[str, Any]) -> bool:
    """Fail-closed health allowlist for one embedded producer descriptor."""
    if descriptor.get("present") is not True:
        return False
    if descriptor.get("validation_status") not in EVIDENCE_VALIDATION_ALLOWLIST:
        return False
    return valid_evidence_status(descriptor.get("status"))


def producer_evidence_freshness(descriptor: dict[str, Any], *, max_age_hours: float) -> tuple[bool, str, float | None]:
    """Check embedded producer evidence without trusting packet timestamps.

    Recomputes age from the descriptor's generated_at_utc against the producer
    contract window. Missing or unparseable timestamps can never count as
    fresh evidence.
    """
    if not descriptor:
        return False, "missing_evidence_descriptor", None
    generated = parse_utc(descriptor.get("generated_at_utc"))
    if generated is None:
        return False, "unknown_generated_at", None
    age_hours = round((datetime.now(timezone.utc) - generated).total_seconds() / 3600, 2)
    if age_hours < 0 or age_hours > float(max_age_hours):
        return False, f"stale_age_hours_{age_hours}_max_{max_age_hours}", age_hours
    return True, "fresh", age_hours


def build_payload(paths: dict[str, Path]) -> dict[str, Any]:
    grade_history_rows = jsonl_row_count(paths["grade_history"])
    recommendation = load(paths["recommendation_ledger"])
    digest = load(paths["finance_digest"])
    os2 = load(paths["wf88_os2"])
    wiki = load(paths["wf88_wiki"])

    recommendation_durable = as_dict(recommendation.get("durable_v2_ledger"))
    os2_summary = as_dict(os2.get("summary"))
    wiki_summary = as_dict(wiki.get("summary"))
    leak_guard = as_dict(wiki.get("recommendation_leak_guard"))
    digest_wf55 = as_dict(digest.get("wf55_recommendation_outcomes"))
    if not digest_wf55:
        digest_wf55 = as_dict(digest.get("recommendation_outcomes"))

    hard_checks = {
        "grade_history_present": grade_history_rows > 0,
        "recommendation_ledger_grade_count_positive": int_value(recommendation_durable.get("later_outcome_graded_rows")) > 0,
        "finance_digest_grade_count_positive": int_value(digest_wf55.get("outcome_grade_assigned_count")) > 0,
        "os2_grade_count_positive": int_value(os2_summary.get("recommendation_later_outcome_graded_rows")) > 0,
        "wiki_grade_count_positive": int_value(wiki_summary.get("recommendation_later_outcome_graded_rows")) > 0,
        "recommendation_leak_guard_pass": leak_guard.get("pass") is True,
        "open_unrouted_recommendation_count_zero": int_value(leak_guard.get("open_unrouted_recommendation_count")) == 0,
        "auto_apply_count_zero": int_value(leak_guard.get("auto_apply_count")) == 0,
        "decision_compiler_leak_guard_pass": wiki_summary.get("decision_compiler_leak_guard_pass") is True,
    }
    producer_evidence: dict[str, Any] = {}
    wiki_inputs = as_dict(wiki.get("inputs"))
    for evidence_key, contract in PRODUCER_EVIDENCE.items():
        descriptor = as_dict(wiki_inputs.get(evidence_key))
        fresh, detail, age_hours = producer_evidence_freshness(
            descriptor, max_age_hours=contract["max_age_hours"]
        )
        healthy = fresh and producer_evidence_healthy(descriptor)
        producer_evidence[evidence_key] = {
            "fresh": fresh,
            "healthy": healthy,
            "detail": detail,
            "age_hours": age_hours,
            "max_age_hours": contract["max_age_hours"],
            "present": descriptor.get("present"),
            "status": descriptor.get("status"),
            "validation_status": descriptor.get("validation_status"),
        }
        hard_checks[f"producer_evidence_fresh:{evidence_key}"] = fresh
        hard_checks[f"producer_evidence_healthy:{evidence_key}"] = healthy
    errors = [name for name, passed in hard_checks.items() if not passed]
    warnings: list[str] = []
    wiki_validation_status = as_dict(wiki.get("validation")).get("status")
    os2_validation_status = as_dict(os2.get("validation")).get("status")
    if wiki_validation_status not in (None, "ok"):
        warnings.append(f"wiki_validation_status:{wiki_validation_status}")
    if os2_validation_status not in (None, "ok"):
        warnings.append(f"os2_validation_status:{os2_validation_status}")
    # Review-only operational signals stay warnings: RSI later-outcome maturity
    # and the decision-compiler review-only state describe unexecuted or
    # immature evidence, not runner failure, and must never flip the gate
    # to blocked on their own.
    if wiki_summary.get("rsi_outcome_mature") is not True:
        warnings.append("rsi_outcome_maturity_not_met")
    compiler_status = wiki_summary.get("decision_compiler_status")
    if isinstance(compiler_status, str) and "warning" in compiler_status.lower():
        warnings.append("decision_compiler_upstream_warning_visible")

    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok" if not errors else "blocked",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "hard_checks": hard_checks,
        "summary": {
            "grade_history_row_count": grade_history_rows,
            "recommendation_later_outcome_graded_rows": int_value(recommendation_durable.get("later_outcome_graded_rows")),
            "finance_digest_grade_count": int_value(digest_wf55.get("outcome_grade_assigned_count")),
            "os2_recommendation_later_outcome_graded_rows": int_value(os2_summary.get("recommendation_later_outcome_graded_rows")),
            "wiki_recommendation_later_outcome_graded_rows": int_value(wiki_summary.get("recommendation_later_outcome_graded_rows")),
            "open_unrouted_recommendation_count": int_value(leak_guard.get("open_unrouted_recommendation_count")),
            "auto_apply_count": int_value(leak_guard.get("auto_apply_count")),
            "wiki_validation_status": wiki_validation_status,
            "os2_validation_status": os2_validation_status,
            "decision_compiler_leak_guard_pass": wiki_summary.get("decision_compiler_leak_guard_pass"),
            "rsi_outcome_mature": wiki_summary.get("rsi_outcome_mature"),
        },
        "producer_evidence": producer_evidence,
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
    parser.add_argument("--grade-history", type=Path, default=GRADE_HISTORY)
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
        "grade_history": abs_path(args.grade_history),
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
