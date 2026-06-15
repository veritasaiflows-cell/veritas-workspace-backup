#!/usr/bin/env python3
"""Run the repeatable WF78 scaleout batch pipeline.

Default path is report-only:
select -> provider/source validation -> owner packet -> planned import gate ->
reputation refresh. `--apply` requires an exact approval reference.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import wf78_500_ticker_reputation_gate as reputation_gate  # noqa: E402
from market_data_utils import atomic_write_json  # noqa: E402
from wf78_batch_manifest import AUTHORITY_BOUNDARY, TMP, batch_artifacts, batch_spec, load_dict, rel, utc_now  # noqa: E402
from wf78_batch_owner_decision_packet import build_report as build_owner_report  # noqa: E402
from wf78_batch_provider_validation import build_report as build_provider_report  # noqa: E402
from wf78_batch_source_selector import build_report as build_source_report  # noqa: E402
from wf78_batch_tier_c_import_gate import build_report as build_import_gate_report  # noqa: E402

SCHEMA = "veritas.wf78_batch_pipeline.v1"
DEFAULT_OUT = TMP / "wf78-batch-pipeline.json"


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def step_record(name: str, path: Path, report: dict[str, Any]) -> dict[str, Any]:
    validation = as_dict(report.get("validation"))
    return {
        "name": name,
        "path": rel(path),
        "status": report.get("status"),
        "validation_status": validation.get("status"),
        "summary": report.get("summary"),
    }


def write_if_enabled(path: Path, payload: dict[str, Any], write: bool) -> None:
    if write:
        atomic_write_json(path, payload, ensure_ascii=False)


def provider_args(args: argparse.Namespace) -> argparse.Namespace:
    return argparse.Namespace(
        batch=args.batch,
        timeout_seconds=args.timeout_seconds,
        sec_timeout_seconds=args.sec_timeout_seconds,
        retries=args.retries,
        backoff_seconds=args.backoff_seconds,
        min_provider_success_rate=args.min_provider_success_rate,
        user_agent=args.user_agent,
        skip_provider_probe=args.skip_provider_probe,
        skip_sec_fetch=args.skip_sec_fetch,
    )


def owner_args(args: argparse.Namespace) -> argparse.Namespace:
    ns = provider_args(args)
    return ns


def import_gate_args(args: argparse.Namespace) -> argparse.Namespace:
    return argparse.Namespace(
        batch=args.batch,
        apply=args.apply,
        owner_approval_reference=args.owner_approval_reference,
        approval_ref=args.approval_ref,
    )


def reputation_args() -> argparse.Namespace:
    return argparse.Namespace(write=True, write_db=True, validate=True, out_json=reputation_gate.DEFAULT_OUT_JSON, out_db=reputation_gate.DEFAULT_OUT_DB)


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    spec = batch_spec(args.batch)
    if args.apply and not (args.owner_approval_reference or args.approval_ref):
        raise SystemExit("--apply requires --owner-approval-reference or --approval-ref")

    source = build_source_report(args.batch)
    write_if_enabled(spec.source_artifact, source, args.write)

    provider = build_provider_report(provider_args(args))
    write_if_enabled(spec.provider_validation, provider, args.write)

    owner = build_owner_report(owner_args(args))
    write_if_enabled(spec.owner_decision_packet, owner, args.write)

    import_gate = build_import_gate_report(import_gate_args(args))
    write_if_enabled(spec.import_gate, import_gate, args.write)

    reputation = reputation_gate.build_report(reputation_args())
    if args.write:
        atomic_write_json(reputation_gate.DEFAULT_OUT_JSON, reputation, ensure_ascii=False)
        reputation_gate.write_sqlite(reputation, reputation_gate.DEFAULT_OUT_DB)

    steps = [
        step_record("source_selector", spec.source_artifact, source),
        step_record("provider_validation", spec.provider_validation, provider),
        step_record("owner_decision_packet", spec.owner_decision_packet, owner),
        step_record("tier_c_import_gate", spec.import_gate, import_gate),
        step_record("reputation_gate", reputation_gate.DEFAULT_OUT_JSON, reputation),
    ]
    critical_step_errors = [
        step for step in steps
        if step.get("validation_status") in {"error", "blocked"} or step.get("status") == "blocked"
    ]
    write_performed = bool(import_gate.get("write_performed"))
    status = "ok"
    if critical_step_errors:
        status = "blocked"
    elif as_dict(provider.get("summary")).get("blocked_or_repair_count"):
        status = "ok_with_repair_required"
    elif owner.get("status") == "decision_required":
        status = "ok_decision_ready"
    if args.apply and not write_performed:
        status = "blocked"

    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "workflow": "WF78 - 500 Ticker Finance Intelligence Scaleout",
        "artifact_type": "wf78_batch_pipeline",
        "status": status,
        "batch": {
            "batch_label": spec.batch_label,
            "rank_start": spec.rank_start,
            "rank_end": spec.rank_end,
            "candidate_rank_start": spec.candidate_rank_start,
            "candidate_rank_end": spec.candidate_rank_end,
            "artifacts": batch_artifacts(spec),
        },
        "authority_boundary": {
            **AUTHORITY_BOUNDARY,
            "pipeline_apply_mode_used": bool(args.apply),
            "pipeline_write_performed": write_performed,
        },
        "summary": {
            "batch_label": spec.batch_label,
            "source_candidate_count": as_dict(source.get("summary")).get("candidate_count"),
            "provider_ready_count": as_dict(provider.get("summary")).get("pre_import_source_ready_count"),
            "provider_blocked_or_repair_count": as_dict(provider.get("summary")).get("blocked_or_repair_count"),
            "owner_packet_status": owner.get("status"),
            "import_gate_status": import_gate.get("status"),
            "apply_mode_used": bool(args.apply),
            "write_performed": write_performed,
            "reputation_gate_status": reputation.get("status"),
            "next_safe_action": "Use this same pipeline for 201-300, 301-400, and 401-500. Apply remains owner-gated and off by default.",
        },
        "steps": steps,
        "validation": {
            "status": "ok" if not critical_step_errors else "error",
            "errors": critical_step_errors,
            "warnings": [] if status != "ok_with_repair_required" else ["one_or_more_batch_candidates_need_provider_or_source_repair_before_apply"],
        },
        "stop_lines": [
            "No import/apply unless --apply is used and write_performed is true.",
            "No apply without exact owner approval reference.",
            "No production answer-path promotion.",
            "No SQL-first or SQL-canon/cache expansion.",
            "No canon/portfolio/sizing/cash/risk-rule mutation.",
            "No customer/external delivery.",
            "No paper/live/brokerage/account action or money movement.",
            "No owner approval inference.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", required=True)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--owner-approval-reference", default="")
    parser.add_argument("--approval-ref", default="")
    parser.add_argument("--timeout-seconds", type=float, default=8.0)
    parser.add_argument("--sec-timeout-seconds", type=float, default=20.0)
    parser.add_argument("--retries", type=int, default=0)
    parser.add_argument("--backoff-seconds", type=float, default=0.5)
    parser.add_argument("--min-provider-success-rate", type=float, default=0.9)
    parser.add_argument("--user-agent", default="Veritas OpenClaw Research veritasaiflows@gmail.com")
    parser.add_argument("--skip-provider-probe", action="store_true")
    parser.add_argument("--skip-sec-fetch", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_report(args)
    out = args.out if args.out.is_absolute() else TMP.parents[0] / args.out
    if args.write:
        atomic_write_json(out, report, ensure_ascii=False)
    output_errors: list[str] = []
    if args.validate:
        if as_dict(report.get("validation")).get("errors"):
            output_errors.append("critical step errors present")
        if args.write:
            loaded = load_dict(out)
            if loaded.get("schema") != SCHEMA:
                output_errors.append("written output schema mismatch")
    status = "blocked" if output_errors or report["status"] == "blocked" else report["status"]
    print(json.dumps({
        "status": status,
        "json_out": rel(out) if args.write else None,
        "summary": report.get("summary"),
        "output_validation_errors": output_errors,
    }, indent=2, sort_keys=True))
    return 0 if status in {"ok", "ok_decision_ready", "ok_with_repair_required"} and not output_errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
