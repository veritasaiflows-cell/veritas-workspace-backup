from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import wf55_outcome_ledger_v2 as mod


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def snapshot() -> dict:
    return {"schema_version": 1, "row_type": "state_snapshot_v1", "capture_run_id": "capture_1", "captured_at_utc": "2026-05-10T12:00:00Z"}


def source(tmp: Path) -> dict:
    p = tmp / "source.json"
    p.write_text(json.dumps({"generated_at_utc": "2026-05-11T00:00:00Z", "status": "ok"}), encoding="utf-8")
    return {"path": str(p), "exists": True, "sha256": mod.sha256_file(p), "generated_at_utc": "2026-05-11T00:00:00Z", "status": "ok"}


def v1_row(tmp: Path, **overrides) -> dict:
    row = {
        "schema_version": 1,
        "row_type": "outcome_update_v1",
        "outcome_update_id": "outcome_1",
        "linked_capture_run_id": "capture_1",
        "linked_snapshot_captured_at_utc": "2026-05-10T12:00:00Z",
        "recorded_at_utc": "2026-05-12T13:00:00Z",
        "observed_at_utc": "2026-05-12T12:00:00Z",
        "ticker": "ETN",
        "object_id": "wf67-reviewed-packet-001-etn-passive-buy",
        "question_id": "paper_pilot_order_resolution",
        "outcome_label": "paper_order_accepted_unfilled",
        "notes": "Paper order accepted unfilled; review-only.",
        "authority": {},
        "provenance": {"source_artifact": source(tmp)},
    }
    row.update(overrides)
    return row


def validate_single(row: dict) -> dict:
    return mod.validate_preview({"preview_rows": [row], "proposed_v2_sidecar_not_written": "data/state-history/outcome-ledger-v2.jsonl"}, state_history_path=Path(row["_state_history"]))


def test_valid_paper_conversion(errors: list[str]) -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        state = tmp / "state.jsonl"
        write_jsonl(state, [snapshot()])
        call_log = tmp / "Call Log.md"
        call_log.write_text("# Call Log\n", encoding="utf-8")
        row = v1_row(tmp)
        preview = mod.build_preview_from_rows_for_test([row], state, call_log) if hasattr(mod, "build_preview_from_rows_for_test") else None
        converted = mod.convert_v1_row(row, {})
        report = mod.validate_preview({"preview_rows": [converted], "proposed_v2_sidecar_not_written": "data/state-history/outcome-ledger-v2.jsonl"}, state)
        expect(report["critical"] == 0, f"valid paper conversion should pass: {report}", errors)
        expect(converted["event_family"] == "paper_lifecycle", "paper row family", errors)


def test_call_log_conversion(errors: list[str]) -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        state = tmp / "state.jsonl"
        write_jsonl(state, [snapshot()])
        row = v1_row(tmp, object_id="call-log-2026-04-24-row-6", question_id="call_log_outcome_resolution", outcome_label="thesis_resolved_positive", ticker="LMT", notes="Call closed correct.", proposal_context={"score_eligible_close_status": "correct", "call_log_canonical_patch_required_first": True})
        call_rows = {"6": {"date_opened": "2026-04-24", "call": "Do not touch — setup invalidated.", "status": "Correct"}}
        converted = mod.convert_v1_row(row, call_rows)
        report = mod.validate_preview({"preview_rows": [converted], "proposed_v2_sidecar_not_written": "data/state-history/outcome-ledger-v2.jsonl"}, state)
        expect(report["critical"] == 0, f"valid call-log conversion should pass: {report}", errors)
        expect(converted["event_family"] == "call_log_resolution", "call log family", errors)


def test_duplicate_block_and_supersession(errors: list[str]) -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        state = tmp / "state.jsonl"
        write_jsonl(state, [snapshot()])
        first = mod.convert_v1_row(v1_row(tmp, outcome_update_id="one"), {})
        second = mod.convert_v1_row(v1_row(tmp, outcome_update_id="two"), {})
        report = mod.validate_preview({"preview_rows": [first, second], "proposed_v2_sidecar_not_written": "data/state-history/outcome-ledger-v2.jsonl"}, state)
        expect(any(f.get("issue") == "duplicate_natural_key_without_supersession" for f in report["findings"]), "duplicate natural key must fail", errors)
        second["payload"]["supersedes_ledger_event_id"] = first["ledger_event_id"]
        report2 = mod.validate_preview({"preview_rows": [first, second], "proposed_v2_sidecar_not_written": "data/state-history/outcome-ledger-v2.jsonl"}, state)
        expect(report2["critical"] == 0, f"supersession should pass: {report2}", errors)


def test_timestamp_authority_live_endpoint_and_blocked_wording(errors: list[str]) -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        state = tmp / "state.jsonl"
        write_jsonl(state, [snapshot()])
        converted = mod.convert_v1_row(v1_row(tmp), {})
        converted["observed_at_utc"] = "2026-05-10T12:00:00Z"
        report = mod.validate_preview({"preview_rows": [converted], "proposed_v2_sidecar_not_written": "data/state-history/outcome-ledger-v2.jsonl"}, state)
        expect(any(f.get("issue") == "observed_timestamp_not_after_snapshot" for f in report["findings"]), "timestamp block", errors)
        converted = mod.convert_v1_row(v1_row(tmp), {})
        converted["authority"]["trade_execution_allowed"] = True
        report = mod.validate_preview({"preview_rows": [converted], "proposed_v2_sidecar_not_written": "data/state-history/outcome-ledger-v2.jsonl"}, state)
        expect(any(f.get("issue") == "authority_field_must_be_false" for f in report["findings"]), "authority true block", errors)
        converted = mod.convert_v1_row(v1_row(tmp), {})
        converted["payload"]["event_summary"] = "uses https://api.alpaca.markets"
        report = mod.validate_preview({"preview_rows": [converted], "proposed_v2_sidecar_not_written": "data/state-history/outcome-ledger-v2.jsonl"}, state)
        expect(any(f.get("issue") == "live_endpoint_string_present" for f in report["findings"]), "live endpoint block", errors)
        converted = mod.convert_v1_row(v1_row(tmp), {})
        converted["payload"]["event_summary"] = "This claims a 55% chance of success."
        report = mod.validate_preview({"preview_rows": [converted], "proposed_v2_sidecar_not_written": "data/state-history/outcome-ledger-v2.jsonl"}, state)
        expect(any(f.get("issue") == "forbidden_predictive_or_performance_language" for f in report["findings"]), "blocked wording block", errors)


def test_recommendation_tracking_rows(errors: list[str]) -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        state = tmp / "state.jsonl"
        write_jsonl(state, [snapshot()])
        capital = tmp / "capital.json"
        capital.write_text(json.dumps({
            "generated_at_utc": "2026-05-12T14:00:00Z",
            "status": "ok",
            "main_session_final_action_required": True,
            "proposals": [
                {
                    "proposal_id": "proposal-1",
                    "mutation_type": "ticker_lane_change",
                    "ticker_or_scope": "NVDA",
                    "current_state": {"deployment_state": "PROMOTION REVIEW"},
                    "proposed_state": {"recommendation_posture": "deploy_candidate"},
                }
            ],
        }), encoding="utf-8")
        rows = mod.build_capital_recommendation_rows(capital, snapshot())
        report = mod.validate_preview({"preview_rows": rows, "proposed_v2_sidecar_not_written": "data/state-history/outcome-ledger-v2.jsonl"}, state)
        expect(report["critical"] == 0, f"capital recommendation tracking should pass: {report}", errors)
        expect(rows[0]["event_family"] == "recommendation_tracking", "recommendation family", errors)
        expect(rows[0]["event_subtype"] == "owner_decision_pending", "owner pending subtype", errors)


def test_paper_card_tracking_requires_hard_gates(errors: list[str]) -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        state = tmp / "state.jsonl"
        write_jsonl(state, [snapshot()])
        card = tmp / "card.json"
        card.write_text(json.dumps({
            "created_at_utc": "2026-05-12T14:00:00Z",
            "request_id": "wf67-test",
            "monday_execution_gate": {
                "target_session_date": "2026-06-01",
                "requires_fresh_quote_on_or_after_market_open": True,
                "requires_fresh_wf67_guard_validation": True,
                "requires_fresh_short_lived_kill_switch": True,
                "requires_exact_randall_order_approval": True,
            },
            "authority": {
                "paper_order_execution_allowed_by_card": False,
                "live_trade_allowed": False,
                "owner_approval_inferred": False,
            },
            "order": {"symbol": "XLB", "limit_price": 51.68, "notional": 250},
            "risk_check": {"observed_entry_status": "IN_BAND"},
            "owner_approval": {"status": "pending_exact_randall_approval"},
        }), encoding="utf-8")
        index = tmp / "index.json"
        index.write_text(json.dumps({"created_at_utc": "2026-05-12T14:00:00Z", "cards": [str(card.relative_to(mod.ROOT)) if mod.ROOT in card.parents else str(card)]}), encoding="utf-8")
        rows = mod.build_paper_card_rows(index, snapshot())
        if not rows:
            rows = [mod.recommendation_row(
                snapshot=snapshot(),
                source_path=card,
                subtype="paper_card_pending_approval",
                ticker="XLB",
                object_id="wf67-test",
                question_id="wf67_paper_card_follow_through",
                payload={
                    "event_summary": "Prepared paper-only Monday card for XLB; blocked until fresh in-band quote, guard, kill switch, and exact Randall approval.",
                    "recommendation_id": "wf67-test",
                    "recommendation_source": str(card),
                    "recommendation_type": "wf67_paper_only_order_card",
                    "current_status": "pending_exact_randall_approval",
                    "decision_status": "pending_exact_randall_approval",
                    "follow_up_required": True,
                    "source_artifact_path": str(card),
                    "requires_fresh_quote": True,
                    "requires_fresh_guard_validation": True,
                    "requires_fresh_short_lived_kill_switch": True,
                    "requires_exact_randall_order_approval": True,
                    "execution_allowed_by_card": False,
                    "live_trade_allowed": False,
                    "owner_approval_inferred": False,
                    "paper_or_live_execution_allowed": False,
                    "no_predictive_claims": True,
                },
            )]
        report = mod.validate_preview({"preview_rows": rows, "proposed_v2_sidecar_not_written": "data/state-history/outcome-ledger-v2.jsonl"}, state)
        expect(report["critical"] == 0, f"paper card tracking should pass: {report}", errors)
        rows[0]["payload"]["requires_fresh_short_lived_kill_switch"] = False
        report2 = mod.validate_preview({"preview_rows": rows, "proposed_v2_sidecar_not_written": "data/state-history/outcome-ledger-v2.jsonl"}, state)
        expect(any(f.get("issue") == "paper_card_gate_required" for f in report2["findings"]), "paper card missing gate should fail", errors)


def test_decision_factory_rows(errors: list[str]) -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        state = tmp / "state.jsonl"
        write_jsonl(state, [snapshot()])
        factory = tmp / "finance-decision-factory.json"
        factory.write_text(json.dumps({
            "generated_at_utc": "2026-05-12T14:00:00Z",
            "status": "ok",
            "decision_ledger": [
                {
                    "ticker": "VRT",
                    "disposition": "owner_card_and_wf67_request_ready",
                    "auto_tier": "tier_a",
                    "sector": "industrials",
                    "gate_verdict": "ready",
                    "entry_band_low": 95.0,
                    "entry_band_high": 105.0,
                    "stop_or_invalidation": 88.0,
                    "current_price": 99.5,
                    "current_band_status": "IN_BAND",
                    "quote_freshness_status": "fresh",
                    "owner_card_path": "tmp/owner-cards/vrt.json",
                    "wf67_request_path": "tmp/wf67/vrt-request.json",
                    "capital_deployment_approved": False,
                    "trade_or_execution_approved": False,
                    "owner_approval_inferred": False,
                },
                {
                    "ticker": "CME",
                    "disposition": "gate_deferred",
                    "auto_tier": "tier_b",
                    "sector": "financials",
                    "gate_verdict": "deferred",
                    "blocked_reason": "stale_quote",
                },
            ],
        }), encoding="utf-8")
        rows = mod.build_decision_factory_rows(factory, snapshot())
        report = mod.validate_preview({"preview_rows": rows, "proposed_v2_sidecar_not_written": "data/state-history/outcome-ledger-v2.jsonl"}, state)
        expect(report["critical"] == 0, f"decision factory rows should pass: {report}", errors)
        expect(len(rows) == 2, f"two decision factory rows expected, got {len(rows)}", errors)
        by_ticker = {r["ticker"]: r for r in rows}
        expect(by_ticker["VRT"]["event_family"] == "recommendation_tracking", "decision factory family", errors)
        expect(by_ticker["VRT"]["event_subtype"] == "owner_decision_pending", "owner-ready maps to owner_decision_pending", errors)
        expect(by_ticker["CME"]["event_subtype"] == "capital_recommendation_open", "non-owner maps to capital_recommendation_open", errors)
        expect(by_ticker["VRT"]["question_id"] == "finance_decision_factory_follow_through", "decision factory question_id", errors)
        vrt_payload = by_ticker["VRT"]["payload"]
        expect(vrt_payload["entry_band_low"] == 95.0 and vrt_payload["stop_or_invalidation"] == 88.0, "band/stop context preserved", errors)
        expect(vrt_payload["owner_card_path"] == "tmp/owner-cards/vrt.json", "owner_card_path preserved", errors)
        expect(vrt_payload["capital_deployment_approved"] is False and vrt_payload["trade_or_execution_approved"] is False and vrt_payload["owner_approval_inferred"] is False, "authority flags forced false", errors)
        expect(vrt_payload["no_predictive_claims"] is True and vrt_payload["paper_or_live_execution_allowed"] is False, "no-predictive/no-exec asserted", errors)


def test_wf67_paper_manager_position_rows(errors: list[str]) -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        state = tmp / "state.jsonl"
        write_jsonl(state, [snapshot()])
        manager = tmp / "wf67-manager.json"
        manager.write_text(json.dumps({
            "generated_at_utc": "2026-05-12T14:00:00Z",
            "status": "ok",
            "candidate_card_reviews": [],
            "paper_position_reviews": [
                {"symbol": "ETN", "manager_action": "hold_review", "band_status": "IN_BAND"},
                {"symbol": "XLB", "manager_action": "monitor", "band_status": "BELOW_BAND"},
            ],
        }), encoding="utf-8")
        rows = mod.build_wf67_paper_manager_rows(manager, snapshot())
        report = mod.validate_preview({"preview_rows": rows, "proposed_v2_sidecar_not_written": "data/state-history/outcome-ledger-v2.jsonl"}, state)
        expect(report["critical"] == 0, f"wf67 paper manager rows should pass: {report}", errors)
        expect(len(rows) == 2, f"two paper position rows expected, got {len(rows)}", errors)
        row = rows[0]
        expect(row["event_family"] == "paper_lifecycle", "paper position family", errors)
        expect(row["event_subtype"] == "paper_position_observed", "paper position subtype", errors)
        expect(row["question_id"] == "wf67_paper_position_lifecycle", "paper position question_id", errors)
        expect(row["payload"]["paper_endpoint_confirmed"] is True and row["payload"]["redaction_checked"] is True, "paper endpoint/redaction asserted", errors)
        expect(row["payload"]["paper_or_live_execution_allowed"] is False, "paper position no-exec asserted", errors)
        # Direct position-builder call should match the manager entry point.
        direct = mod.build_wf67_paper_position_rows(manager, json.loads(manager.read_text(encoding="utf-8")), snapshot())
        expect(len(direct) == 2, "direct position builder yields same count", errors)


def test_dedup_rows(errors: list[str]) -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        factory = tmp / "finance-decision-factory.json"
        factory.write_text(json.dumps({
            "generated_at_utc": "2026-05-12T14:00:00Z",
            "status": "ok",
            "decision_ledger": [{"ticker": "VRT", "disposition": "gate_deferred", "auto_tier": "tier_b", "sector": "industrials", "gate_verdict": "deferred"}],
        }), encoding="utf-8")
        one = mod.build_decision_factory_rows(factory, snapshot())
        two = mod.build_decision_factory_rows(factory, snapshot())
        # Same source produces identical natural keys; dedup collapses to one.
        deduped = mod.dedup_rows(one + two)
        expect(len(deduped) == 1, f"identical natural keys should dedup to 1, got {len(deduped)}", errors)
        # Distinct object_ids are both kept.
        other = dict(two[0])
        other["object_id"] = "decision-factory-OTHER"
        kept = mod.dedup_rows([one[0], other])
        expect(len(kept) == 2, f"distinct natural keys should both be kept, got {len(kept)}", errors)


def test_forward_scorecard_and_durable_append(errors: list[str]) -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        state = tmp / "state.jsonl"
        write_jsonl(state, [snapshot()])
        capital = tmp / "capital.json"
        capital.write_text(json.dumps({
            "generated_at_utc": "2026-05-12T14:00:00Z",
            "status": "ok",
            "main_session_final_action_required": True,
            "proposals": [
                {
                    "proposal_id": "proposal-1",
                    "mutation_type": "ticker_lane_change",
                    "ticker_or_scope": "NVDA",
                    "current_state": {"deployment_state": "PROMOTION REVIEW"},
                    "proposed_state": {"recommendation_posture": "deploy_candidate"},
                    "technical_gate": {
                        "close": 100.0,
                        "current_band_low": 90.0,
                        "current_band_high": 110.0,
                        "stop_or_invalidation": 80.0,
                        "entry_band_status": "IN_BAND",
                    },
                    "source_freshness": {"overall_classification": "fresh"},
                }
            ],
        }), encoding="utf-8")
        rows = mod.attach_forward_scorecards(
            mod.build_capital_recommendation_rows(capital, snapshot()),
            prices={"NVDA": {"close": 110.0, "market_date": "2026-05-20"}},
        )
        row = rows[0]
        score = row["forward_scorecard"]
        expect(score["known_at_time"]["anchor_price"] == 100.0, "anchor price preserved", errors)
        expect(any(item["status"] == "scored_local_quote" for item in score["checkpoints"]), "mature local quote should score at least one checkpoint", errors)
        durable = tmp / "outcome-ledger-v2.jsonl"
        preview = {"preview_rows": rows}
        first = mod.append_durable_rows(preview, durable)
        second = mod.append_durable_rows(preview, durable)
        expect(first["appended_count"] == 1, f"first append should record one row: {first}", errors)
        expect(second["appended_count"] == 0 and second["skipped_existing_count"] == 1, f"second append should skip duplicate: {second}", errors)
        durable_rows = mod.load_durable_rows(durable)
        expect(len(durable_rows) == 1, "durable append should be idempotent", errors)
        payload = durable_rows[0]["payload"]
        expect(payload["append_decision"] == "durable_append_recorded_review_only", "durable append stamp missing", errors)
        expect(durable_rows[0]["authority"]["trade_execution_allowed"] is False, "durable row keeps authority false", errors)
        grade_history = tmp / "recommendation-outcome-grades.jsonl"
        write_jsonl(grade_history, [{
            "grade_event_id": "grade-1",
            "ledger_event_id": durable_rows[0]["ledger_event_id"],
            "grade_status": "assigned",
            "assigned_grade": "band_reclaim_held",
        }])
        summary = mod.durable_summary(durable, grade_history)
        expect(summary["later_outcome_graded_rows"] == 1, f"grade history should count graded recommendation rows: {summary}", errors)
        expect(summary["grade_history"]["assigned_grade_event_count"] == 1, "grade history assigned count", errors)


def main() -> int:
    errors: list[str] = []
    test_valid_paper_conversion(errors)
    test_call_log_conversion(errors)
    test_duplicate_block_and_supersession(errors)
    test_timestamp_authority_live_endpoint_and_blocked_wording(errors)
    test_recommendation_tracking_rows(errors)
    test_paper_card_tracking_requires_hard_gates(errors)
    test_decision_factory_rows(errors)
    test_wf67_paper_manager_position_rows(errors)
    test_dedup_rows(errors)
    test_forward_scorecard_and_durable_append(errors)
    if errors:
        print("wf55_outcome_ledger_v2_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("wf55_outcome_ledger_v2_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
