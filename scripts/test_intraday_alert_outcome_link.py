from __future__ import annotations

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from intraday_alert_outcome_link import (  # noqa: E402
    AUTHORITY_FALSE_FIELDS,
    build_link,
    render_markdown,
    validate_link,
)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def sample_packet(path: Path) -> None:
    write_json(
        path,
        {
            "schema_version": "wf68.advisor_alert_packet.v1",
            "workflow": "WF68",
            "phase": "phase_4_advisor_integration",
            "status": "ADVISOR_READY",
            "generated_at_utc": "2026-05-19T22:23:11Z",
            "alerts": [
                {
                    "packet_id": "wf68-forced-etn-test",
                    "ticker": "ETN",
                    "severity": "HIGH",
                    "event_type": "forced_fixture",
                    "source_alert_packet_path": "tmp\\intraday-alerts\\forced-alert-fixture.etn.json",
                    "source_handoff_path": "tmp\\intraday-alerts\\forced-main-session-handoff.json",
                    "advisor_decision_packet": {
                        "entry_context": {
                            "observed_price": 404.0,
                            "entry_band_low": 360.99,
                            "entry_band_high": 404.94,
                            "no_chase_above": 404.94,
                        },
                        "stop_context": {"stop": 341.01},
                        "source_freshness": {"alert_source_timestamp_utc": "2026-05-19T21:39:30Z"},
                        "recommendation_context": {
                            "recommendation_posture": "wait_for_band",
                            "recommended_action": "wait_for_band",
                        },
                        "outcome_linkage": {
                            "call_log_required": True,
                            "probability_claims_allowed": False,
                            "wf55_status": "not_yet_recorded",
                        },
                    },
                }
            ],
            "authority": {"posture": "review_only_no_authority"},
        },
    )


def test_builds_required_phase5_record() -> None:
    with TemporaryDirectory() as td:
        packet = Path(td) / "advisor-alert-packet.json"
        sample_packet(packet)
        link = build_link(packet, generated_at_utc="2026-05-19T22:30:00Z")
        validation = validate_link(link)
        assert validation["status"] == "ok", validation
        assert link["status"] == "OUTCOME_LINK_READY"
        assert link["record_count"] == 1
        record = link["records"][0]
        for field in [
            "packet_id",
            "ticker",
            "alert_trigger",
            "advisor_recommendation_posture",
            "owner_decision",
            "action_or_no_action",
            "timestamp",
            "follow_up_window",
            "realized_outcome_placeholder",
            "wf55_status",
            "authority",
            "provenance",
        ]:
            assert record.get(field) not in (None, "", [], {}), field
        assert record["packet_id"] == "wf68-forced-etn-test"
        assert record["ticker"] == "ETN"
        assert record["advisor_recommendation_posture"] == "wait_for_band"
        assert record["owner_decision"] == "pending_owner_review"
        assert record["action_or_no_action"] == "pending_owner_action_or_no_action"
        assert record["wf55_status"]["probability_claims_allowed"] is False
        assert record["call_log_proposal"]["canonical_call_log_mutation_applied"] is False
        assert record["state_history_sidecar_proposal"]["append_applied"] is False
        for key in AUTHORITY_FALSE_FIELDS:
            assert record["authority"][key] is False, key
            assert link["authority"][key] is False, key
        md = render_markdown(link, validation)
        assert "wf68-forced-etn-test" in md
        assert "proposal-only" in md


def test_validation_blocks_authority_widening_and_forbidden_language() -> None:
    with TemporaryDirectory() as td:
        packet = Path(td) / "advisor-alert-packet.json"
        sample_packet(packet)
        link = build_link(packet, generated_at_utc="2026-05-19T22:30:00Z")
        link["records"][0]["authority"]["paper_trade_allowed"] = True
        link["records"][0]["notes"] = "win rate should never appear"
        validation = validate_link(link)
        assert validation["status"] == "critical"
        issues = {finding["issue"] for finding in validation["findings"]}
        assert "record_authority_not_false" in issues
        assert "forbidden_modeling_language" in issues


if __name__ == "__main__":
    test_builds_required_phase5_record()
    test_validation_blocks_authority_widening_and_forbidden_language()
    print("intraday_alert_outcome_link targeted tests passed")
