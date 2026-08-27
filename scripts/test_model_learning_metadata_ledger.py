from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import model_learning_metadata_ledger as ledger

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "model_learning_metadata_ledger.py"
REPORT = ROOT / "tmp" / "model-learning-metadata-ledger.json"
FINANCE_RESPONSE = ROOT / "tmp" / "finance-response-quality-slice.json"


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def test_uncredited_model_lane_is_audit_only() -> None:
    rows = ledger.model_rows({
        "rows": [
            {
                "run_id": "unverified-lane",
                "producer": "concurrent_lane_manager",
                "run_kind": "workspace_lane",
                "model_path": "openai/gpt-5.6-terra",
                "status": "complete",
                "duration_ms": 900,
                "tokens": 1234,
                "cost": 0.12,
                "attribution": {
                    "model_present": True,
                    "model_applicable": False,
                    "telemetry_eligible": False,
                    "telemetry_credit_status": "blocked_unverified_usage_source",
                    "telemetry_block_reasons": ["source_reverification_not_verified"],
                },
            },
            {
                "run_id": "direct-cron",
                "producer": "openclaw_cron_runs",
                "run_kind": "cron_agent_turn",
                "model_path": "openai/gpt-5.6-terra",
                "status": "ok",
                "duration_ms": 800,
                "tokens": 42,
                "cost": 0.01,
                "attribution": {
                    "model_present": True,
                    "model_applicable": True,
                    "telemetry_eligible": True,
                    "telemetry_credit_status": "direct_gateway_cron_usage",
                },
            },
        ]
    })
    assert len(rows) == 2
    row = next(row for row in rows if row["source_id"] == "unverified-lane")
    assert row["domain"] == "model_audit_uncredited"
    assert row["metadata"]["telemetry_eligible"] is False
    assert row["metadata"]["duration_ms"] is None
    assert row["metadata"]["tokens_present"] is False
    assert row["metadata"]["cost_present"] is False
    assert "audit only" in str(row["scoring_use"])
    cron_row = next(row for row in rows if row["source_id"] == "direct-cron")
    assert cron_row["domain"] == "model"
    assert cron_row["metadata"]["duration_ms"] == 800
    assert cron_row["metadata"]["tokens_present"] is True
    assert cron_row["metadata"]["cost_present"] is True


def main() -> int:
    errors: list[str] = []
    try:
        test_uncredited_model_lane_is_audit_only()
    except AssertionError as exc:
        errors.append(f"uncredited model lane regression failed: {exc}")
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--write", "--write-md", "--validate"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    expect(result.returncode == 0, f"ledger command failed: {result.stdout} {result.stderr}", errors)
    expect(REPORT.exists(), "metadata ledger report missing", errors)
    if REPORT.exists():
        report = json.loads(REPORT.read_text(encoding="utf-8"))
        expect(report.get("schema") == "veritas.model_learning_metadata_ledger.v1", "schema mismatch", errors)
        expect(report.get("validation", {}).get("status") == "ok", "validation should be ok", errors)
        expect(report.get("privacy_scan", {}).get("status") == "ok", "privacy scan should be ok", errors)
        boundary = report.get("authority_boundary", {})
        for flag in (
            "external_export_allowed",
            "raw_prompt_capture_allowed",
            "raw_response_capture_allowed",
            "tool_payload_capture_allowed",
            "system_prompt_capture_allowed",
            "secret_or_header_capture_allowed",
            "base_model_self_modification_allowed",
            "model_ranking_claim_allowed",
            "investment_correctness_from_runtime_metrics_allowed",
            "canon_or_portfolio_mutation_allowed",
            "paper_or_live_or_account_action_allowed",
            "owner_approval_inferred",
        ):
            expect(boundary.get(flag) is False, f"authority flag must be false: {flag}", errors)
        domains = set(report.get("summary", {}).get("by_domain", {}))
        for domain in {"tools", "coding", "coding_outcome", "finance_response_quality"}:
            expect(domain in domains, f"missing domain: {domain}", errors)
        expect(
            bool({"model", "model_audit_uncredited"} & domains),
            "missing both scoreable and audit-only model domains",
            errors,
        )
        expect(
            report.get("summary", {}).get("coding_outcome_rows", 0) > 0,
            "coding_outcome rows should be present",
            errors,
        )
        if "runtime_otel" in domains:
            expect(
                report.get("summary", {}).get("runtime_otel_rows", 0) > 0,
                "runtime_otel domain present but row count missing",
                errors,
            )
        if "tool_workflow_metadata" in domains:
            expect(
                report.get("summary", {}).get("tool_workflow_metadata_rows", 0) > 0,
                "tool_workflow_metadata domain present but row count missing",
                errors,
            )
        if "coding_runtime" in domains:
            expect(
                report.get("summary", {}).get("coding_runtime_rows", 0) > 0,
                "coding_runtime domain present but row count missing",
                errors,
            )
        for row in report.get("rows", []):
            expect(row.get("payload_capture") is False, f"payload capture must be false: {row.get('row_id')}", errors)
        if FINANCE_RESPONSE.exists():
            finance_response = json.loads(FINANCE_RESPONSE.read_text(encoding="utf-8"))
            finance_summary = finance_response.get("summary", {})
            summary_rows = [
                row for row in report.get("rows", [])
                if row.get("domain") == "finance_response_quality"
                and row.get("source_id") == "finance_response_quality_summary"
            ]
            expect(summary_rows, "finance response quality summary row missing", errors)
            if summary_rows:
                metadata = summary_rows[0].get("metadata", {})
                for field in ("source_freshness_blocked_count", "remediation_tracks_needing_repair"):
                    expect(
                        metadata.get(field) == finance_summary.get(field),
                        f"finance response ledger mismatch for {field}: {metadata.get(field)} != {finance_summary.get(field)}",
                        errors,
                    )
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("ok: model learning metadata ledger is bounded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
