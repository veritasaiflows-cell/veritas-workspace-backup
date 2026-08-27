#!/usr/bin/env python3
"""Validate live cron jobs against intended local contract files."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_CONTRACT_DIR = ROOT / "state" / "cron-contracts"
DEFAULT_OUT = TMP / "cron-contract-validator.json"
SCHEMA = "veritas.cron_contract_validator.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "drift_detection_only": True,
    "cron_state_mutation_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "owner_approval_inferred": False,
}

DEFAULT_COMPARE_FIELDS = [
    "enabled",
    "description",
    "schedule",
    "failureAlert",
    "payload.message",
    "payload.model",
    "payload.thinking",
    "payload.timeoutSeconds",
    "payload.lightContext",
]
DEFAULT_MAX_PROMPT_CHARS = 1800
DEFAULT_MAX_MESSAGE_LINES = 30
QUIET_RULE_MARKER = "QUIET CRON OUTPUT RULE"
TASK_BODY_MARKERS = (
    "Objective:",
    "Execute exactly",
    "Execute:",
    "Run the ",
    "Run ",
    "python scripts\\",
    "python scripts/",
)

UNSUPPORTED_MODEL_ROUTES = {
    "claude-cli/claude-fable-5": {
        "status": "unsupported_legacy",
        "reason": "Fable is no longer a supported model route.",
        "replacement_guidance": "Use openai/gpt-5.6-sol for main/final synthesis or openai/gpt-5.6-terra for an approved bounded helper route.",
    },
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


def openclaw_cmd() -> str:
    found = shutil.which("openclaw.cmd") or shutil.which("openclaw") or shutil.which("openclaw.ps1")
    if found:
        return found
    known = Path.home() / "AppData" / "Roaming" / "npm" / "openclaw.cmd"
    return str(known) if known.exists() else "openclaw.cmd"


def get_nested(obj: dict[str, Any], dotted: str) -> Any:
    current: Any = obj
    for part in dotted.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def message_shape(value: Any, *, max_prompt_chars: int, max_message_lines: int) -> dict[str, Any]:
    text = value if isinstance(value, str) else ""
    return {
        "char_count": len(text),
        "line_count": text.count("\n") + 1 if text else 0,
        "max_prompt_chars": max_prompt_chars,
        "max_message_lines": max_message_lines,
        "over_char_budget": len(text) > max_prompt_chars,
        "over_line_budget": (text.count("\n") + 1 if text else 0) > max_message_lines,
        "has_multiline": "\n" in text,
    }


def prompt_integrity_findings(job: dict[str, Any] | None, *, source: str) -> list[dict[str, Any]]:
    if not isinstance(job, dict):
        return []
    payload = as_dict(job.get("payload"))
    if payload.get("kind") != "agentTurn":
        return []
    message = payload.get("message")
    text = message if isinstance(message, str) else ""
    normalized = " ".join(text.split())
    quiet_rule_present = QUIET_RULE_MARKER in text
    task_body_present = any(marker in text for marker in TASK_BODY_MARKERS)
    findings: list[dict[str, Any]] = []
    if not normalized:
        findings.append({
            "source": source,
            "issue": "missing_agentturn_prompt",
            "severity": "error",
            "message_char_count": 0,
        })
    if quiet_rule_present and not task_body_present:
        findings.append({
            "source": source,
            "issue": "quiet_only_agentturn_prompt",
            "severity": "error",
            "message_char_count": len(text),
            "message_line_count": text.count("\n") + 1 if text else 0,
            "reason": "agentTurn prompt contains the quiet output rule but no task body or command marker",
        })
    return findings


def unsupported_model_findings(contract: dict[str, Any], live_job: dict[str, Any] | None) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for source, model in (
        ("contract", expected_value(contract, "payload.model")),
        ("live", get_nested(live_job, "payload.model") if live_job else None),
    ):
        if model in UNSUPPORTED_MODEL_ROUTES:
            findings.append({
                "source": source,
                "model": model,
                **UNSUPPORTED_MODEL_ROUTES[str(model)],
            })
    return findings


def detected_unsupported_model_routes(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return the distinct unsupported routes actually observed in this run."""
    grouped: dict[str, dict[str, Any]] = {}
    for result in results:
        for raw_finding in as_list(result.get("unsupported_model_routes")):
            finding = as_dict(raw_finding)
            model = str(finding.get("model") or "").strip()
            if not model:
                continue
            row = grouped.setdefault(model, {
                "model": model,
                "status": finding.get("status"),
                "reason": finding.get("reason"),
                "replacement_guidance": finding.get("replacement_guidance"),
                "detection_count": 0,
                "sources": set(),
                "contracts": [],
            })
            row["detection_count"] += 1
            source = str(finding.get("source") or "").strip()
            if source:
                row["sources"].add(source)
            context = {
                "contract_path": result.get("contract_path"),
                "job_id": result.get("job_id"),
                "name": result.get("name"),
                "source": source or None,
            }
            if context not in row["contracts"]:
                row["contracts"].append(context)
    return [
        {
            **row,
            "sources": sorted(row["sources"]),
            "contracts": sorted(
                row["contracts"],
                key=lambda item: (
                    str(item.get("contract_path") or ""),
                    str(item.get("job_id") or ""),
                    str(item.get("source") or ""),
                ),
            ),
        }
        for _, row in sorted(grouped.items())
    ]


def normalize_cron_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        jobs = payload.get("jobs")
        if isinstance(jobs, list):
            return [item for item in jobs if isinstance(item, dict)]
        if payload.get("id") or payload.get("name"):
            return [payload]
    return []


def load_live_jobs(live_file: Path | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if live_file:
        payload = load_json_artifact(live_file)
        return normalize_cron_payload(payload), {"source": rel(live_file), "ok": True}
    completed = subprocess.run(
        [openclaw_cmd(), "cron", "list", "--all", "--json", "--timeout", "30000"],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=45,
        check=False,
    )
    meta = {
        "source": "openclaw cron list --all --json",
        "returncode": completed.returncode,
        "ok": completed.returncode == 0,
        "stderr_tail": (completed.stderr or "")[-2000:],
    }
    if completed.returncode != 0:
        return [], meta
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        meta["ok"] = False
        meta["error"] = "cron_list_json_parse_failed"
        return [], meta
    return normalize_cron_payload(payload), meta


def iter_contract_paths(contract_dir: Path, explicit: list[Path] | None = None) -> list[Path]:
    if explicit:
        return [path if path.is_absolute() else ROOT / path for path in explicit]
    if not contract_dir.exists():
        return []
    return sorted(path for path in contract_dir.glob("*.json") if path.is_file())


def load_contracts(contract_dir: Path, explicit: list[Path] | None = None) -> tuple[list[dict[str, Any]], list[str]]:
    contracts: list[dict[str, Any]] = []
    warnings: list[str] = []
    for path in iter_contract_paths(contract_dir, explicit):
        payload = load_json_artifact(path)
        if not isinstance(payload, dict):
            warnings.append(f"invalid_contract_json:{rel(path)}")
            continue
        payload["_contract_path"] = rel(path)
        contracts.append(payload)
    return contracts, warnings


def contract_identity(contract: dict[str, Any]) -> tuple[str | None, str | None]:
    return (
        contract.get("job_id") or contract.get("id"),
        contract.get("name") or contract.get("job_name"),
    )


def find_live_job(contract: dict[str, Any], jobs: list[dict[str, Any]]) -> dict[str, Any] | None:
    job_id, name = contract_identity(contract)
    if job_id:
        for job in jobs:
            if str(job.get("id") or "") == str(job_id):
                return job
    if name:
        matches = [job for job in jobs if str(job.get("name") or "") == str(name)]
        if len(matches) == 1:
            return matches[0]
    return None


def expected_value(contract: dict[str, Any], field: str) -> Any:
    return get_nested(contract, field)


def compare_contract(
    contract: dict[str, Any],
    live_job: dict[str, Any] | None,
    *,
    max_prompt_chars: int = DEFAULT_MAX_PROMPT_CHARS,
    max_message_lines: int = DEFAULT_MAX_MESSAGE_LINES,
) -> dict[str, Any]:
    fields = [str(item) for item in as_list(contract.get("compare_fields"))] or DEFAULT_COMPARE_FIELDS
    if live_job is None:
        return {
            "contract_path": contract.get("_contract_path"),
            "job_id": contract_identity(contract)[0],
            "name": contract_identity(contract)[1],
            "status": "missing_live_job",
            "severity": "error" if contract.get("required", True) else "warning",
            "drift": [],
        }
    drift: list[dict[str, Any]] = []
    for field in fields:
        expected = expected_value(contract, field)
        if expected is None and not bool(contract.get("compare_nulls", False)):
            continue
        actual = get_nested(live_job, field)
        if actual != expected:
            drift.append({"field": field, "expected": expected, "actual": actual})
    expected_artifacts = []
    for item in as_list(contract.get("expected_artifacts")):
        path = ROOT / str(item)
        expected_artifacts.append({"path": str(item), "exists": path.exists()})
    missing_artifacts = [item for item in expected_artifacts if not item["exists"]]
    expected_message = expected_value(contract, "payload.message")
    actual_message = get_nested(live_job, "payload.message")
    prompt_shape = {
        "expected": message_shape(expected_message, max_prompt_chars=max_prompt_chars, max_message_lines=max_message_lines),
        "live": message_shape(actual_message, max_prompt_chars=max_prompt_chars, max_message_lines=max_message_lines),
    }
    prompt_bloat = []
    for source, shape in prompt_shape.items():
        if shape["over_char_budget"] or shape["over_line_budget"]:
            prompt_bloat.append({"source": source, **shape})
    unsupported_model_routes = unsupported_model_findings(contract, live_job)
    prompt_integrity = [
        *prompt_integrity_findings(contract, source="contract"),
        *prompt_integrity_findings(live_job, source="live"),
    ]
    multiline_expected = prompt_shape["expected"]["has_multiline"]
    multiline_live_intact = not multiline_expected or (
        isinstance(actual_message, str)
        and "\n" in actual_message
        and actual_message == expected_message
    )
    return {
        "contract_path": contract.get("_contract_path"),
        "job_id": live_job.get("id"),
        "name": live_job.get("name"),
        "status": (
            "prompt_integrity_error"
            if prompt_integrity else
            "unsupported_model" if unsupported_model_routes else
            ("drift" if drift else "ok")
        ),
        "severity": "error" if prompt_integrity or unsupported_model_routes else ("warning" if drift else "ok"),
        "drift": drift,
        "unsupported_model_routes": unsupported_model_routes,
        "prompt_integrity_findings": prompt_integrity,
        "expected_artifacts": expected_artifacts,
        "missing_expected_artifacts": missing_artifacts,
        "prompt_shape": prompt_shape,
        "prompt_bloat": prompt_bloat,
        "multiline_live_intact": multiline_live_intact,
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    contract_dir = args.contract_dir if args.contract_dir.is_absolute() else ROOT / args.contract_dir
    jobs, live_meta = load_live_jobs(args.live_file)
    contracts, warnings = load_contracts(contract_dir, args.contract)
    results = [
        compare_contract(
            contract,
            find_live_job(contract, jobs),
            max_prompt_chars=args.max_prompt_chars,
            max_message_lines=args.max_message_lines,
        )
        for contract in contracts
    ]
    drift_count = sum(1 for item in results if item.get("status") == "drift")
    missing_count = sum(1 for item in results if item.get("status") == "missing_live_job")
    unsupported_model_routes = detected_unsupported_model_routes(results)
    unsupported_model_route_count = len(unsupported_model_routes)
    contract_prompt_integrity_error_count = sum(1 for item in results if as_list(item.get("prompt_integrity_findings")))
    live_prompt_integrity_findings = [
        {
            "job_id": job.get("id"),
            "name": job.get("name"),
            "enabled": job.get("enabled"),
            **finding,
        }
        for job in jobs
        if job.get("enabled", True) is not False
        for finding in prompt_integrity_findings(job, source="live_global")
    ]
    live_prompt_integrity_error_count = len(live_prompt_integrity_findings)
    prompt_bloat_count = sum(1 for item in results if as_list(item.get("prompt_bloat")))
    multiline_truncation_risk_count = sum(1 for item in results if item.get("multiline_live_intact") is False)
    errors = []
    if not live_meta.get("ok"):
        errors.append("live_cron_list_unavailable")
    if args.require_contracts and not contracts:
        errors.append("no_contracts_found")
    if args.fail_on_drift and (drift_count or missing_count):
        errors.append("cron_contract_drift_present")
    if unsupported_model_route_count:
        errors.append("unsupported_cron_model_route_present")
    if live_prompt_integrity_error_count:
        errors.append("cron_prompt_integrity_error_present")
    if args.fail_on_prompt_bloat and prompt_bloat_count:
        errors.append("cron_prompt_bloat_present")
    if multiline_truncation_risk_count:
        errors.append("cron_multiline_live_payload_mismatch")
    if prompt_bloat_count:
        warnings.append("cron_prompt_bloat_present")
    if multiline_truncation_risk_count:
        warnings.append("cron_multiline_live_payload_mismatch")
    if not contracts:
        warnings.append(f"no_contracts_found:{rel(contract_dir)}")
    status = "error" if errors else "warning" if warnings or drift_count or missing_count else "ok"
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "summary": {
            "contract_count": len(contracts),
            "live_job_count": len(jobs),
            "drift_count": drift_count,
            "missing_live_job_count": missing_count,
            "unsupported_model_route_count": unsupported_model_route_count,
            "unsupported_model_routes": unsupported_model_routes,
            "configured_unsupported_model_routes": sorted(UNSUPPORTED_MODEL_ROUTES),
            "contract_prompt_integrity_error_count": contract_prompt_integrity_error_count,
            "live_prompt_integrity_error_count": live_prompt_integrity_error_count,
            "prompt_bloat_count": prompt_bloat_count,
            "multiline_truncation_risk_count": multiline_truncation_risk_count,
            "max_prompt_chars": args.max_prompt_chars,
            "max_message_lines": args.max_message_lines,
            "next_safe_action": (
                "Create state\\cron-contracts\\*.json for important jobs."
                if not contracts else
                "Review drift entries; use cron_patch_manager.py for approved live patches."
            ),
        },
        "sources": {
            "contract_dir": rel(contract_dir),
            "live": live_meta,
        },
        "contracts": results,
        "live_prompt_integrity_findings": live_prompt_integrity_findings,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "validation": {"status": "error" if errors else "warning" if warnings else "ok", "errors": errors, "warnings": warnings},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract-dir", type=Path, default=DEFAULT_CONTRACT_DIR)
    parser.add_argument("--contract", type=Path, action="append")
    parser.add_argument("--live-file", type=Path)
    parser.add_argument("--require-contracts", action="store_true")
    parser.add_argument("--fail-on-drift", action="store_true")
    parser.add_argument("--fail-on-prompt-bloat", action="store_true")
    parser.add_argument("--max-prompt-chars", type=int, default=DEFAULT_MAX_PROMPT_CHARS)
    parser.add_argument("--max-message-lines", type=int, default=DEFAULT_MAX_MESSAGE_LINES)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    payload = build_payload(args)
    out = args.out if args.out.is_absolute() else ROOT / args.out
    if args.write:
        atomic_write_json(out, payload)
    print(
        f"status={payload['status']} contracts={payload['summary']['contract_count']} "
        f"drift={payload['summary']['drift_count']} missing={payload['summary']['missing_live_job_count']} out={rel(out)}"
    )
    if args.validate and payload["validation"]["status"] == "error":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
