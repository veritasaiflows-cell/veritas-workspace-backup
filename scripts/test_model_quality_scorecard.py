from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "model_quality_scorecard.py"
REPORT = ROOT / "tmp" / "model-quality-scorecard.json"
sys.path.insert(0, str(ROOT / "scripts"))

def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main(argv: list[str] | None = None) -> int:
    errors: list[str] = []
    if argv is not None and "--unit-only" in argv:
        if errors:
            for error in errors:
                print(f"FAIL: {error}")
            return 1
        print("ok: model quality scorecard blocker semantics regressions passed")
        return 0

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
        validation = report.get("validation", {})
        expect(validation.get("status") in {"ok", "warning"}, "scorecard validation must not be critical", errors)
        if validation.get("status") == "warning":
            components = report.get("tracks", {}).get("decision_quality", {}).get("metrics", {}).get("active_alert_chain_components", {})
            expect(not all(components.values()), "a warning is allowed only while an active alerts-OS proof is truthfully non-green", errors)

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
        expect("alerts OS / WF74" in owners, "alerts-OS/WF74 owner gate missing from enhancement queue", errors)

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
        perf_metrics = perf.get("metrics", {}) if isinstance(perf, dict) else {}
        expect(len(perf_metrics) > 0, "performance track should expose normalized metrics", errors)
        for field in (
            "runtime_checks_total",
            "otel_window_count",
            "model_run_row_count",
            "cost_metric_available",
            "token_metric_available",
        ):
            expect(field in perf_metrics, f"performance metrics missing {field}", errors)
        # Cost/token economics now source from the authoritative token_usage_ledger
        # (Gateway usage-cost path) per the 2026-08-13 telemetry role split, not from
        # the thin OTEL debug log. Availability is allowed, but the honesty constraints
        # below must stay locked: API-equivalent only (never an invoice), partial
        # coverage, and cross-model economic claims remain gated.
        expect(
            isinstance(perf_metrics.get("cost_metric_available"), bool),
            "cost_metric_available must be a bool sourced from token_usage_ledger presence",
            errors,
        )
        expect(
            isinstance(perf_metrics.get("token_metric_available"), bool),
            "token_metric_available must be a bool sourced from token_usage_ledger presence",
            errors,
        )
        economics = perf.get("token_cost_economics", {}) if isinstance(perf, dict) else {}
        expect(
            economics.get("actual_billed_cost_known") is False,
            "token/cost must stay API-equivalent benchmark, never a claimed invoice",
            errors,
        )
        if perf_metrics.get("cost_metric_available") is True:
            expect(
                float(economics.get("api_equivalent_cost_event_coverage_percent") or 0) > 0,
                "when cost metric is available, coverage percent must be positive and provenance-backed",
                errors,
            )
            expect(
                bool(economics.get("authority_note")),
                "cost economics must carry an authority_note keeping cross-model claims gated",
                errors,
            )
        otel_local = perf.get("otel_local_ops", {}) if isinstance(perf, dict) else {}
        expect(otel_local.get("window_summary_status") == "ok", "OTEL window summary should be ok", errors)
        expect(otel_local.get("window_count") == 5, "OTEL window summary should expose five windows", errors)
        for window_id in {"intraday_1h", "intraday_6h", "daily_24h", "weekly_7d", "monthly_30d"}:
            expect(window_id in set(otel_local.get("window_ids") or []), f"missing OTEL window in scorecard: {window_id}", errors)

        decision = report.get("tracks", {}).get("decision_quality", {})
        decision_metrics = decision.get("metrics", {}) if isinstance(decision, dict) else {}
        expect(
            decision.get("readiness") in {
                "active_measurement_only_semantic_claims_gated",
                "partial_recommendation_outcome_evidence",
                "blocked_on_recommendation_outcomes",
            },
            "decision quality readiness should remain bounded",
            errors,
        )
        expect(decision_metrics.get("scorecard_active_now") is True, "decision quality scorecard should be active now", errors)
        expect((decision_metrics.get("tracking_row_count") or 0) > 0, "decision quality should include review-only recommendation rows", errors)
        expect((decision_metrics.get("graded_rows") or 0) > 0, "decision quality should include deterministic recommendation grades", errors)
        expect(decision_metrics.get("durable_append_allowed") is True, "recommendation outcomes should retain the review-only append contract", errors)
        expect(decision_metrics.get("semantic_outcome_claim_allowed") is False, "semantic outcome claims should remain gated", errors)
        expect(decision_metrics.get("predictive_or_model_ranking_allowed") is False, "predictive/model-ranking claims should remain blocked", errors)
        expect("active_alert_chain_components" in decision_metrics, "decision quality should expose active alerts-OS proof state", errors)
        claim_blockers = decision.get("claim_blockers", [])
        expect(any("predictive scoring" in str(item) for item in claim_blockers), "predictive claim blocker should be explicit", errors)
        gates = {gate.get("gate"): gate for gate in report.get("readiness_gates", []) if isinstance(gate, dict)}
        outcome_gate = gates.get("recommendation_outcome_history", {})
        expect(outcome_gate.get("status") == "review_measurement_active", "recommendation outcome gate should be active for review measurement", errors)
        expect(outcome_gate.get("blocks_track") == "none", "recommendation outcome gate should not block active decision_quality track", errors)
        expect(
            outcome_gate.get("blocks_claim") == "semantic_predictive_decision_quality",
            "recommendation outcome gate should block semantic/predictive decision-quality claims",
            errors,
        )

        learning = report.get("tracks", {}).get("learning_capture", {})
        expect(learning.get("readiness") == "active_metadata_only", "learning capture should be active metadata-only", errors)
        learning_metrics = learning.get("metrics", {})
        expect(learning_metrics.get("privacy_scan_status") == "ok", "learning capture privacy scan should be ok", errors)
        expect((learning_metrics.get("tool_rows") or 0) > 0, "learning capture should include tool rows", errors)
        expect((learning_metrics.get("coding_rows") or 0) > 0, "learning capture should include coding rows", errors)
        expect("improvement_open_count" in learning_metrics, "learning capture should include improvement open count", errors)
        expect("improvement_closed_count" in learning_metrics, "learning capture should include improvement closed count", errors)
        expect("improvement_closure_rate" in learning_metrics, "learning capture should include improvement closure rate", errors)
        expect(learning_metrics.get("improvement_anti_theater_status") in {
            "blocked_by_overdue_backlog",
            "proposal_loop_active_no_closure_proof",
            "proposal_loop_with_closure_proof",
        }, "learning capture anti-theater status missing", errors)

    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("ok: model quality scorecard efficiency loops are present and bounded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
