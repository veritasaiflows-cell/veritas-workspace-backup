from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "dashboard_run_summary_consumer.py"


def load_module():
    spec = importlib.util.spec_from_file_location("dashboard_run_summary_consumer", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_summary(*, status: str, chain_status: str, classification: str) -> dict:
    return {
        "window": "morning",
        "status": status,
        "execution": {
            "chain_status": chain_status,
            "chain_status_normalized": True,
            "data_quality_repair": {"classification": classification},
        },
        "artifact_index": {
            "enabled": True,
            "status": "ok",
            "operator_action_required": False,
        },
        "downstream": {
            "presentation_allowed": status != "blocked",
            "canonical_note_mutation_allowed": False,
        },
    }


def workflow_alert(module, summary: dict) -> dict:
    payload = {"ui": {"alerts": []}, "trust": {}}
    result = module.propagate_run_summary(payload, summary)
    return next(alert for alert in result["ui"]["alerts"] if alert["title"] == "Workflow window status")


def test_ticker_scoped_terminal_status_is_not_ambiguous() -> None:
    module = load_module()
    alert = workflow_alert(
        module,
        run_summary(
            status="warning",
            chain_status="completed_with_ticker_repairs",
            classification="ticker_scoped_repair",
        ),
    )
    assert alert["tone"] == "warn", alert
    assert "Execution finalization is ambiguous" not in alert["detail"], alert


def test_systemic_terminal_status_is_not_ambiguous_and_remains_blocked() -> None:
    module = load_module()
    alert = workflow_alert(
        module,
        run_summary(
            status="blocked",
            chain_status="completed_with_systemic_data_quality",
            classification="systemic_data_quality",
        ),
    )
    assert alert["tone"] == "bad", alert
    assert "Execution finalization is ambiguous" not in alert["detail"], alert
