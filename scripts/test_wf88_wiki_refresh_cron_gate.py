from __future__ import annotations

import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import wf88_wiki_refresh_cron_gate as gate


REMOVE = object()


def write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def paths(base: Path) -> dict[str, Path]:
    return {
        "grade_history": base / "grades.jsonl",
        "recommendation_ledger": base / "recommendation.json",
        "finance_digest": base / "digest.json",
        "wf88_os2": base / "os2.json",
        "wf88_wiki": base / "wiki.json",
    }


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def fresh_evidence(*, status: str = "ok", validation: str = "ok") -> dict:
    return {
        "path": "tmp/producer.json",
        "present": True,
        "required": True,
        "generated_at_utc": now_utc(),
        "age_hours": 0.0,
        "max_age_hours": 24,
        "freshness_status": "fresh",
        "status": status,
        "validation_status": validation,
    }


def stale_evidence() -> dict:
    old = (datetime.now(timezone.utc) - timedelta(days=30)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return {
        "path": "tmp/producer.json",
        "present": True,
        "required": True,
        "generated_at_utc": old,
        "age_hours": 720.0,
        "max_age_hours": 24,
        "freshness_status": "stale",
        "status": "ok",
        "validation_status": "ok",
    }


def seed(
    base: Path,
    *,
    leak_guard_pass: bool = True,
    auto_apply_count: int = 0,
    graded_rows: int = 3,
    mature: bool = True,
    compiler_status: str = "ok",
    stale_producers: tuple[str, ...] = (),
) -> dict[str, Path]:
    p = paths(base)
    p["grade_history"].parent.mkdir(parents=True, exist_ok=True)
    rows = [json.dumps({"grade_event_id": f"g{i}"}) for i in range(graded_rows)]
    p["grade_history"].write_text("".join(row + "\n" for row in rows), encoding="utf-8")
    write_json(p["recommendation_ledger"], {"durable_v2_ledger": {"later_outcome_graded_rows": graded_rows}})
    write_json(p["finance_digest"], {"wf55_recommendation_outcomes": {"outcome_grade_assigned_count": graded_rows}})
    write_json(p["wf88_os2"], {
        "summary": {"recommendation_later_outcome_graded_rows": graded_rows},
        "validation": {"status": "blocked", "errors": ["wiki_synthesis_validation_blocked"]},
    })
    inputs = {
        "retrieval_quality_scorecard": fresh_evidence(),
        "wf88_decision_compiler": fresh_evidence(status=compiler_status, validation="warning" if compiler_status != "ok" else "ok"),
        "rsi_outcome_scorecard": fresh_evidence(status="warning", validation="warning"),
    }
    for key in stale_producers:
        inputs[key] = stale_evidence()
    write_json(p["wf88_wiki"], {
        "summary": {
            "recommendation_later_outcome_graded_rows": graded_rows,
            "decision_compiler_leak_guard_pass": True,
            "decision_compiler_status": compiler_status,
            "rsi_outcome_mature": mature,
        },
        "inputs": inputs,
        "recommendation_leak_guard": {
            "pass": leak_guard_pass,
            "open_unrouted_recommendation_count": 0,
            "auto_apply_count": auto_apply_count,
        },
        "validation": {"status": "blocked", "errors": ["decision_docket_hard_stop_count_must_be_zero"]},
    })
    return p


def descriptor_case(**over) -> dict:
    base = fresh_evidence()
    base.update(over)
    return {key: value for key, value in base.items() if value is not REMOVE}


def seed_with_retrieval(base: Path, descriptor: dict) -> dict[str, Path]:
    seeded = seed(base)
    wiki = json.loads(seeded["wf88_wiki"].read_text(encoding="utf-8"))
    wiki["inputs"]["retrieval_quality_scorecard"] = descriptor
    seeded["wf88_wiki"].write_text(json.dumps(wiki), encoding="utf-8")
    return seeded


def test_gate_allows_unrelated_packet_warnings_when_hard_checks_pass() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        payload = gate.build_payload(seed(Path(tmp)))
        assert payload["validation"]["status"] == "ok"
        assert payload["summary"]["recommendation_later_outcome_graded_rows"] == 3
        assert "wiki_validation_status:blocked" in payload["validation"]["warnings"]


def test_gate_blocks_leak_guard_or_missing_grades() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        payload = gate.build_payload(seed(Path(tmp), leak_guard_pass=False, auto_apply_count=1, graded_rows=0))
        assert payload["validation"]["status"] == "blocked"
        assert "recommendation_leak_guard_pass" in payload["validation"]["errors"]
        assert "auto_apply_count_zero" in payload["validation"]["errors"]
        assert "recommendation_ledger_grade_count_positive" in payload["validation"]["errors"]
        assert "grade_history_present" in payload["validation"]["errors"]


def test_gate_blocks_stale_producer_evidence_despite_fresh_packet() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        payload = gate.build_payload(seed(Path(tmp), stale_producers=("rsi_outcome_scorecard",)))
        assert payload["validation"]["status"] == "blocked"
        assert "producer_evidence_fresh:rsi_outcome_scorecard" in payload["validation"]["errors"]
        assert payload["producer_evidence"]["rsi_outcome_scorecard"]["fresh"] is False
        assert payload["producer_evidence"]["retrieval_quality_scorecard"]["fresh"] is True


def test_gate_blocks_missing_producer_evidence_descriptor() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        seeded = seed(Path(tmp))
        wiki = json.loads(seeded["wf88_wiki"].read_text(encoding="utf-8"))
        del wiki["inputs"]["wf88_decision_compiler"]
        seeded["wf88_wiki"].write_text(json.dumps(wiki), encoding="utf-8")
        payload = gate.build_payload(seeded)
        assert payload["validation"]["status"] == "blocked"
        assert "producer_evidence_fresh:wf88_decision_compiler" in payload["validation"]["errors"]


def test_gate_keeps_operational_warnings_as_warnings_not_failures() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        payload = gate.build_payload(seed(
            Path(tmp),
            mature=False,
            compiler_status="decision_objects_warning_review_only",
        ))
        assert payload["validation"]["status"] == "ok"
        assert "rsi_outcome_maturity_not_met" in payload["validation"]["warnings"]
        assert "decision_compiler_upstream_warning_visible" in payload["validation"]["warnings"]


def test_gate_rejects_malformed_producer_evidence_despite_fresh_timestamp() -> None:
    cases = [
        descriptor_case(validation_status=REMOVE),
        descriptor_case(validation_status=None),
        descriptor_case(validation_status="critical"),
        descriptor_case(validation_status="unknown"),
        descriptor_case(validation_status="failed"),
        descriptor_case(status=REMOVE),
        descriptor_case(status=None),
        descriptor_case(status=""),
        descriptor_case(status="   "),
        descriptor_case(status=0),
        descriptor_case(status="critical"),
        descriptor_case(status="failed"),
        descriptor_case(status="fail_open"),
        descriptor_case(status="fail_closed"),
        descriptor_case(status="error"),
        descriptor_case(status="blocked"),
        descriptor_case(present=False),
        descriptor_case(present=REMOVE),
        descriptor_case(present=None),
    ]
    for index, descriptor in enumerate(cases):
        with tempfile.TemporaryDirectory() as tmp:
            payload = gate.build_payload(seed_with_retrieval(Path(tmp), descriptor))
            assert payload["validation"]["status"] == "blocked", f"case {index} {descriptor} greened the gate"
            assert "producer_evidence_healthy:retrieval_quality_scorecard" in payload["validation"]["errors"], f"case {index}"
            assert payload["validation"]["errors"], f"case {index} blocked with empty errors"


def test_gate_rejects_banana_unknown_hyphenated_and_malformed() -> None:
    cases = [
        descriptor_case(status="banana"),
        descriptor_case(status="unknown"),
        descriptor_case(status="fail-open"),
        descriptor_case(status="fail-closed"),
        descriptor_case(status="Fail_Open"),
        descriptor_case(status="WARNING"),
        descriptor_case(status="Ok"),
        descriptor_case(status="decision-objects-warning-review-only"),
        descriptor_case(status=""),
        descriptor_case(status="   "),
        descriptor_case(status=None),
        descriptor_case(status=0),
        descriptor_case(status=[]),
        descriptor_case(status={}),
    ]
    for index, descriptor in enumerate(cases):
        with tempfile.TemporaryDirectory() as tmp:
            payload = gate.build_payload(seed_with_retrieval(Path(tmp), descriptor))
            assert payload["validation"]["status"] == "blocked", "case %d %r greened the gate" % (index, descriptor)
            assert "producer_evidence_healthy:retrieval_quality_scorecard" in payload["validation"]["errors"], "case %d" % index


def test_gate_accepts_known_review_only_statuses() -> None:
    cases = [
        ("ok", "ok"),
        ("warning", "warning"),
        ("decision_objects_warning_review_only", "warning"),
        ("wiki_synthesis_warning_no_apply_authority", "warning"),
    ]
    for status, validation in cases:
        with tempfile.TemporaryDirectory() as tmp:
            payload = gate.build_payload(seed_with_retrieval(
                Path(tmp), descriptor_case(status=status, validation_status=validation)
            ))
            assert payload["validation"]["status"] == "ok", (status, validation, payload["validation"]["errors"])


if __name__ == "__main__":
    test_gate_allows_unrelated_packet_warnings_when_hard_checks_pass()
    test_gate_blocks_leak_guard_or_missing_grades()
    test_gate_blocks_stale_producer_evidence_despite_fresh_packet()
    test_gate_blocks_missing_producer_evidence_descriptor()
    test_gate_keeps_operational_warnings_as_warnings_not_failures()
    test_gate_rejects_malformed_producer_evidence_despite_fresh_timestamp()
    test_gate_accepts_known_review_only_statuses()
    print("wf88_wiki_refresh_cron_gate_tests_passed")
