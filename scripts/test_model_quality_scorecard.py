from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "model_quality_scorecard.py"
REPORT = ROOT / "tmp" / "model-quality-scorecard.json"


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    errors: list[str] = []
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--write", "--validate"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    expect(result.returncode == 0, f"scorecard command failed: {result.stdout} {result.stderr}", errors)
    expect(REPORT.exists(), "model quality scorecard report missing", errors)

    if REPORT.exists():
        report = json.loads(REPORT.read_text(encoding="utf-8"))
        expect(report.get("schema") == "wf74.model_quality_scorecard.v1", "unexpected scorecard schema", errors)
        expect(report.get("validation", {}).get("status") == "ok", "scorecard validation should be ok", errors)

        loops = report.get("efficiency_loops", {})
        expect(loops.get("schema") == "wf74.efficiency_loops.v1", "efficiency loop schema missing", errors)
        expect(loops.get("status") == "active_partial", "efficiency loop status should be active_partial", errors)
        loop_rows = [row for row in loops.get("loops", []) if isinstance(row, dict)]
        domains = {row.get("domain") for row in loop_rows}
        for domain in {"coding", "models", "implementation", "routing", "operations"}:
            expect(domain in domains, f"missing efficiency loop domain: {domain}", errors)
        for row in loop_rows:
            loop_id = row.get("loop_id") or "<unknown>"
            for field in ("owner_surface", "status", "meaning", "next_safe_action", "feedback_sink", "proof_sources"):
                expect(bool(row.get(field)), f"{loop_id} missing {field}", errors)

        queue = loops.get("enhancement_queue", [])
        expect(len(queue) >= 3, "enhancement queue should name at least three next actions", errors)
        owners = {row.get("owner") for row in queue if isinstance(row, dict)}
        expect("WF74 / model-quality-scorecard" in owners, "WF74 owner missing from enhancement queue", errors)
        expect("WF55 / WF74" in owners, "WF55/WF74 owner gate missing from enhancement queue", errors)

        rules = loops.get("standing_rules", [])
        rule_ids = {row.get("rule_id") for row in rules if isinstance(row, dict)}
        for rule_id in {
            "input_changed_not_broken",
            "producer_before_consumer",
            "operational_telemetry_only",
            "freshness_precision",
            "self_contained_when_possible",
        }:
            expect(rule_id in rule_ids, f"missing efficiency loop standing rule: {rule_id}", errors)
        for row in rules:
            if not isinstance(row, dict):
                continue
            rule_id = row.get("rule_id") or "<unknown>"
            for field in ("principle", "meaning", "owner_surface", "next_safe_action"):
                expect(bool(row.get(field)), f"{rule_id} missing {field}", errors)

        boundary = report.get("authority_boundary", {})
        for flag in (
            "model_ranking_claim",
            "investment_correctness_from_runtime_metrics",
            "base_model_self_modification",
            "owner_approval_inference",
            "portfolio_or_canon_mutation",
            "paper_or_live_or_account_action",
            "otel_backend_enablement_in_this_lane",
        ):
            expect(boundary.get(flag) is False, f"authority flag must remain false: {flag}", errors)

        perf = report.get("tracks", {}).get("performance", {})
        otel_local = perf.get("otel_local_ops", {}) if isinstance(perf, dict) else {}
        expect(otel_local.get("window_summary_status") == "ok", "OTEL window summary should be ok", errors)
        expect(otel_local.get("window_count") == 5, "OTEL window summary should expose five windows", errors)
        for window_id in {"intraday_1h", "intraday_6h", "daily_24h", "weekly_7d", "monthly_30d"}:
            expect(window_id in set(otel_local.get("window_ids") or []), f"missing OTEL window in scorecard: {window_id}", errors)

        learning = report.get("tracks", {}).get("learning_capture", {})
        expect(learning.get("readiness") == "active_metadata_only", "learning capture should be active metadata-only", errors)
        learning_metrics = learning.get("metrics", {})
        expect(learning_metrics.get("privacy_scan_status") == "ok", "learning capture privacy scan should be ok", errors)
        expect((learning_metrics.get("tool_rows") or 0) > 0, "learning capture should include tool rows", errors)
        expect((learning_metrics.get("coding_rows") or 0) > 0, "learning capture should include coding rows", errors)

    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("ok: model quality scorecard efficiency loops are present and bounded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
