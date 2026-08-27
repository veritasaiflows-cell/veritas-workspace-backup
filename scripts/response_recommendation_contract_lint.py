#!/usr/bin/env python3
"""Lint response/closeout text for decision-support recommendations.

The linter catches the recurring failure mode where an answer reports facts,
repairs, and validators but does not provide ranked recommendations, action
labels, do/don't guidance, or prevention/improvement guidance.

It is text lint only. It does not send messages, apply skills, mutate finance
state, infer approval, or execute any recommended action.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_OUT = TMP / "response-recommendation-contract-lint.json"
SCHEMA = "veritas.response_recommendation_contract_lint.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "text_lint_only": True,
    "sends_messages": False,
    "applies_skill_proposals": False,
    "code_mutation_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "config_auth_runtime_mutation_allowed": False,
    "finance_canon_or_portfolio_mutation_allowed": False,
    "cash_sizing_or_risk_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "owner_approval_inferred": False,
}

ACTION_LABELS = (
    "auto-safe",
    "auto safe",
    "review-only",
    "review only",
    "owner-gated",
    "owner gated",
    "blocked",
)

RECOMMENDATION_MARKERS = (
    "top recommendations",
    "recommendations",
    "next steps",
    "next actions",
)

DO_MARKERS = ("do:", "do -", "do\n", "do\r\n")
DO_NOT_MARKERS = ("don't:", "dont:", "do not:", "don\u2019t:")
IMPROVEMENT_MARKERS = (
    "improvement",
    "prevention",
    "prevent recurrence",
    "harden",
    "hardening",
    "so this does not recur",
    "so it does not recur",
)

P_MARKERS = ("p0", "p1", "p2")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def workspace_path(value: str | None, default: Path) -> Path:
    if not value:
        return default
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().casefold())


def line_lower(text: str) -> list[str]:
    return [line.strip().casefold() for line in text.splitlines()]


def has_recommendation_heading(text: str) -> bool:
    lowered = normalize_text(text)
    return any(marker in lowered for marker in RECOMMENDATION_MARKERS)


def has_ranked_recommendations(text: str) -> bool:
    lowered = normalize_text(text)
    return all(re.search(rf"\b{marker}\b", lowered) for marker in P_MARKERS)


def has_action_labels(text: str) -> bool:
    lowered = normalize_text(text)
    found = {label for label in ACTION_LABELS if label in lowered}
    # One label proves the response is using the authority vocabulary, but two
    # catches thin "blocked" mentions that are not recommendation labels.
    return len(found) >= 2 or any(label in found for label in {"auto-safe", "auto safe", "owner-gated", "owner gated"})


def has_do_dont(text: str) -> bool:
    lowered_lines = "\n".join(line_lower(text))
    return any(marker in lowered_lines for marker in DO_MARKERS) and any(marker in lowered_lines for marker in DO_NOT_MARKERS)


def has_improvement(text: str) -> bool:
    lowered = normalize_text(text)
    return any(marker in lowered for marker in IMPROVEMENT_MARKERS)


def lint_text(text: str, *, strict: bool = True) -> dict[str, Any]:
    findings: list[dict[str, str]] = []

    checks = {
        "recommendation_section": has_recommendation_heading(text),
        "ranked_p0_p1_p2": has_ranked_recommendations(text),
        "action_labels": has_action_labels(text),
        "do_dont_guidance": has_do_dont(text),
        "improvement_or_prevention": has_improvement(text),
    }
    for code, ok in checks.items():
        if not ok:
            findings.append({
                "severity": "error" if strict else "warning",
                "code": code,
                "message": f"Missing response recommendation contract element: {code}",
            })

    status = "ok" if not findings or not strict else "blocked"
    if findings and not strict:
        status = "warning"
    return {
        "status": status,
        "checks": checks,
        "finding_count": len(findings),
        "findings": findings,
    }


GOOD_SAMPLE = """Bottom line: the repair is complete and warning-grade only.

Top recommendations:
1. P0 - Auto-safe now: add the linter to closeout proof. Why: it catches recommendation-free answers before closeout.
2. P1 - Review-only: keep the next finance answer under the new contract. Why: it proves the behavior in live use.
3. P2 - Owner-gated: defer any capital action. Why: response quality does not create approval.

Do:
- Keep the ranked next actions visible.

Don't:
- Do not treat validator success as a recommendation by itself.

Improvement: keep this lint in the closeout bundle so the same failure does not recur.
"""

BAD_SAMPLE = """Bottom line: the repair is complete.

Validation passed: focused tests, changed-file router, and release contract.
Remaining warning: none.
"""


def self_test() -> dict[str, Any]:
    good = lint_text(GOOD_SAMPLE, strict=True)
    bad = lint_text(BAD_SAMPLE, strict=True)
    passed = good["status"] == "ok" and bad["status"] == "blocked"
    return {
        "status": "ok" if passed else "blocked",
        "good_sample_status": good["status"],
        "bad_sample_status": bad["status"],
        "bad_sample_findings": bad["findings"],
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    texts: list[dict[str, str]] = []
    if args.text:
        texts.append({"source": "inline", "text": args.text})
    for raw_path in args.file or []:
        path = workspace_path(raw_path, ROOT)
        texts.append({"source": rel(path), "text": path.read_text(encoding="utf-8")})
    results = []
    for item in texts:
        result = lint_text(item["text"], strict=not args.warning_only)
        result["source"] = item["source"]
        results.append(result)

    errors = [
        f"{row['source']}:{finding['code']}"
        for row in results
        for finding in row["findings"]
        if finding["severity"] == "error"
    ]
    warnings = [
        f"{row['source']}:{finding['code']}"
        for row in results
        for finding in row["findings"]
        if finding["severity"] == "warning"
    ]

    self_result = self_test() if args.self_test else None
    if self_result and self_result["status"] != "ok":
        errors.append("self_test_failed")

    status = "blocked" if errors else "warning" if warnings else "ok"
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "summary": {
            "text_count": len(results),
            "blocked_count": sum(1 for row in results if row["status"] == "blocked"),
            "warning_count": sum(1 for row in results if row["status"] == "warning"),
            "ok_count": sum(1 for row in results if row["status"] == "ok"),
            "next_safe_action": (
                "Rewrite the response/closeout with ranked recommendations, action labels, Do/Don't, and prevention guidance."
                if status != "ok"
                else "Response recommendation contract lint passed."
            ),
        },
        "self_test": self_result,
        "results": results,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "validation": {
            "status": "error" if errors else "warning" if warnings else "ok",
            "errors": errors,
            "warnings": warnings,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Lint response text for ranked recommendations and improvement guidance.")
    parser.add_argument("--text", default="")
    parser.add_argument("--file", action="append")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--warning-only", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.text and not args.file and not args.self_test:
        print("Provide --text, --file, or --self-test", file=sys.stderr)
        return 2
    payload = build_payload(args)
    out = workspace_path(args.out, DEFAULT_OUT)
    if args.write:
        atomic_write_json(out, payload)
    print(json.dumps({
        "status": payload["status"],
        "summary": payload["summary"],
        "validation": payload["validation"],
        "write_result": {"out": rel(out)} if args.write else None,
    }, indent=2, sort_keys=True))
    if args.validate and payload["validation"]["status"] == "error":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
