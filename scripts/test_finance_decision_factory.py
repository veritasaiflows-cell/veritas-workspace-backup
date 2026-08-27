from __future__ import annotations

import argparse

import finance_decision_factory as factory


def args(**overrides):
    defaults = {
        "ledger_only": False,
        "full": False,
        "refresh_prep": False,
        "repair_evidence": False,
        "step": [],
        "skip_provider_refresh": False,
        "repair_tier": "A",
        "repair_limit": 10,
        "repair_cursor": 0,
        "closeout": False,
        "recommend_qa_lane": False,
        "out": factory.OUT,
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def test_promotion_gate_freshness_contract_has_stale_input_fields() -> None:
    freshness = factory.promotion_gate_input_freshness()
    assert "promotion_gate_generated_at_utc" in freshness
    assert "stale_relative_to_inputs" in freshness
    assert "newer_input_artifacts" in freshness


def test_deferred_rows_carry_plain_english_root_cause_blockers(monkeypatch) -> None:
    def fake_load_dict(path):
        if path == factory.CAPITAL_REVIEW_QUEUE:
            return {
                "rows": [
                    {
                        "ticker": "TST",
                        "name": "Test Co",
                        "capital_review_card_preparable": True,
                        "written_band": {},
                        "wf84_canonical_data_plane": {},
                    }
                ]
            }
        if path == factory.PROMOTION_GATE:
            return {
                "generated_at_utc": "2026-06-24T00:00:00Z",
                "candidates": [
                    {
                        "ticker": "TST",
                        "chief_intelligence_verdict": "monitor_only",
                        "cautions": ["fixture caution"],
                    }
                ],
            }
        return {}

    monkeypatch.setattr(factory, "load_dict", fake_load_dict)

    ledger = factory.build_ledger()
    deferred = [row for row in ledger if row.get("disposition") == "gate_deferred"]
    assert deferred, "expected at least one deferred row in current factory artifacts"
    for row in deferred:
        assert row.get("root_cause_blockers"), row
        assert row.get("plain_english_blockers"), row
        assert row.get("promotion_gate_input_freshness"), row
        assert isinstance(row.get("gate_veto_details"), list)


def test_default_report_is_ledger_only_and_skips_producers(monkeypatch) -> None:
    def fail_if_called(*_args, **_kwargs):  # pragma: no cover - assertion helper
        raise AssertionError("default factory path must not run producer steps")

    monkeypatch.setattr(factory, "run_step", fail_if_called)

    report = factory.build_report(args())

    assert report["status"] in {"ok", "blocked"}
    assert report["parameters"]["default_mode"] == "ledger_only"
    assert report["parameters"]["producer_steps_requested"] == []
    assert report["summary"]["executed_steps"] == []
    skipped = {row["name"] for row in report["summary"]["skipped_steps"]}
    assert factory.CANDIDATE_PREP_STEP in skipped
    assert factory.EVIDENCE_REPAIR_STEP in skipped


def test_full_report_runs_candidate_prep_and_evidence_repair(monkeypatch) -> None:
    calls: list[str] = []

    def fake_run_step(name, command, timeout):
        calls.append(name)
        return {
            "name": name,
            "executed": True,
            "skipped": False,
            "command": command,
            "timeout_seconds": timeout,
            "ok": True,
            "returncode": 0,
        }

    monkeypatch.setattr(factory, "run_step", fake_run_step)

    report = factory.build_report(args(full=True))

    assert calls == [factory.CANDIDATE_PREP_STEP, factory.EVIDENCE_REPAIR_STEP]
    assert report["parameters"]["producer_steps_requested"] == [
        factory.CANDIDATE_PREP_STEP,
        factory.EVIDENCE_REPAIR_STEP,
    ]
    assert report["summary"]["executed_steps"] == calls


if __name__ == "__main__":
    test_promotion_gate_freshness_contract_has_stale_input_fields()
    test_deferred_rows_carry_plain_english_root_cause_blockers()
    print("finance_decision_factory_tests_passed")
