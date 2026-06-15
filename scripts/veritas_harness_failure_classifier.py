#!/usr/bin/env python3
"""Classify Veritas/OpenClaw harness failures into operator actions.

This is a local triage helper. It does not execute workflows, mutate canon,
grant approval, deliver externally, or authorize paper/live actions.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_OUT = TMP / "veritas-harness-failure-classification.json"

SCHEMA = "veritas.harness.failure_classifier.v1"

AUTHORITY_REGRESSION_KEYS = {
    "public_launch_allowed",
    "public_launch_ready",
    "real_customer_data_allowed",
    "customer_data_retention_allowed",
    "external_delivery_allowed",
    "legal_or_compliance_ready",
    "source_licensing_assumed",
    "personalized_regulated_advice_allowed",
    "brokerage_or_account_connection_allowed",
    "paper_or_live_execution_allowed",
    "trading_account_or_paper_execution_allowed",
    "portfolio_or_canon_mutation_allowed",
    "sql_or_ticker_import_allowed",
    "owner_approval_inferred",
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


def text_has(pattern: str, text: str) -> bool:
    return re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE) is not None


def find_truthy_authority_flags(value: Any, prefix: str = "") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if key in AUTHORITY_REGRESSION_KEYS and item not in (False, 0):
                findings.append(f"{path}={item!r}")
            findings.extend(find_truthy_authority_flags(item, path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            findings.extend(find_truthy_authority_flags(item, f"{prefix}[{index}]"))
    return findings


def classify_text(text: str) -> dict[str, Any]:
    evidence: list[str] = []
    lowered = text.lower()

    harmless_patterns = [
        r"rg\b.*failed",
        r"wildcard",
        r"glob",
        r"cannot find path",
        r"illegal characters in path",
        r"filename.*directory name.*volume label syntax is incorrect",
        r"error 123",
        r"get-childitem.*cannot find path",
    ]
    if any(text_has(pattern, text) for pattern in harmless_patterns):
        evidence.append("Windows shell/path/glob command failure signature")
        return {
            "classification": "harmless_shell_issue",
            "severity": "low",
            "action": "Rewrite the command using explicit paths, rg -g filters, or Get-ChildItem; do not treat as workflow breakage unless validator artifacts also fail.",
            "evidence": evidence,
        }

    if text_has(r"critical[^0-9]*[1-9]", text) or any(token in lowered for token in ["traceback", "syntaxerror", "modulenotfounderror", "validation not ok", "status=error", "status=blocked"]):
        evidence.append("Critical/error/blocked execution signature")
        return {
            "classification": "real_breakage",
            "severity": "high",
            "action": "Inspect the failing script/artifact, fix the underlying validation or runtime error, then rerun the exact validator.",
            "evidence": evidence,
        }

    if text_has(r"warning", text) and text_has(r"0\s*critical|critical[^0-9]*0", text):
        evidence.append("Warning-only validator signature")
        return {
            "classification": "validator_warning",
            "severity": "medium",
            "action": "Keep reporting it, but triage as a readiness/freshness gap unless it blocks a required decision surface.",
            "evidence": evidence,
        }

    if any(token in lowered for token in ["not_ready", "stale", "freshness", "history span", "timestamp gap"]):
        evidence.append("Freshness/readiness gap signature")
        return {
            "classification": "stale_or_readiness_gap",
            "severity": "medium",
            "action": "Refresh or extend the underlying evidence/history, then rerun the readiness validator.",
            "evidence": evidence,
        }

    return {
        "classification": "unknown_needs_review",
        "severity": "medium",
        "action": "Report the full command and output; classify again after inspecting the referenced artifact or validator.",
        "evidence": ["No known signature matched"],
    }


def classify_artifact(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    if not isinstance(payload, dict):
        return {
            "classification": "real_breakage",
            "severity": "high",
            "action": "Artifact is missing or not valid JSON; rebuild the producer and rerun validation.",
            "evidence": [f"unparseable_artifact={rel(path)}"],
        }

    authority = find_truthy_authority_flags(payload)
    if authority:
        return {
            "classification": "authority_regression",
            "severity": "critical",
            "action": "Stop the workflow and restore false authority flags before using this surface.",
            "evidence": authority[:20],
        }

    validation = as_dict(payload.get("validation"))
    errors = as_list(validation.get("errors")) or as_list(payload.get("validation_errors"))
    warnings = as_list(validation.get("warnings"))
    status = str(payload.get("status") or validation.get("status") or "").lower()
    critical_count = payload.get("critical_count", validation.get("critical_count"))
    warning_count = payload.get("warning_count", validation.get("warning_count"))

    if errors or status in {"error", "blocked", "failed"} or (isinstance(critical_count, int) and critical_count > 0):
        return {
            "classification": "real_breakage",
            "severity": "high",
            "action": "Fix the producer or source artifact and rerun its validator.",
            "evidence": [f"status={status or 'unknown'}", f"errors={errors[:10]}", f"critical_count={critical_count}"],
        }

    if status in {"not_ready", "warning"} or warnings or (isinstance(warning_count, int) and warning_count > 0):
        return {
            "classification": "validator_warning",
            "severity": "medium",
            "action": "Track as readiness debt; use it only if the consuming workflow allows warnings.",
            "evidence": [f"status={status or 'unknown'}", f"warnings={warnings[:10]}", f"warning_count={warning_count}"],
        }

    return {
        "classification": "ok",
        "severity": "none",
        "action": "No failure signature found.",
        "evidence": [f"status={status or 'unknown'}"],
    }


def build_report(text: str | None, artifact: Path | None) -> dict[str, Any]:
    if artifact is not None:
        classification = classify_artifact(artifact)
        input_ref = {"type": "artifact", "path": rel(artifact)}
    else:
        classification = classify_text(text or "")
        input_ref = {"type": "text", "chars": len(text or "")}
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok",
        "input": input_ref,
        **classification,
        "authority_boundary": {
            "workflow_mutation_allowed": False,
            "external_delivery_allowed": False,
            "paper_or_live_execution_allowed": False,
            "owner_approval_inferred": False,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Classify harness/tool/validator failures.")
    parser.add_argument("--text", help="Raw error text to classify.")
    parser.add_argument("--artifact", type=Path, help="JSON artifact to classify.")
    parser.add_argument("--write", action="store_true", help="Write classification JSON.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if bool(args.text) == bool(args.artifact):
        raise SystemExit("provide exactly one of --text or --artifact")
    artifact = args.artifact
    if artifact is not None and not artifact.is_absolute():
        artifact = ROOT / artifact
    report = build_report(args.text, artifact)
    if args.write:
        out = args.out if args.out.is_absolute() else ROOT / args.out
        atomic_write_json(out, report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["classification"] not in {"real_breakage", "authority_regression"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
