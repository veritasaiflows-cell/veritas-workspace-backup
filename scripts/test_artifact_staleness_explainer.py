from __future__ import annotations

from pathlib import Path

import artifact_staleness_explainer as explainer


def test_producer_for_known_cron_control() -> None:
    producer = explainer.producer_for(Path("tmp/cron-control-packet.json"))
    assert producer["owner"] == "cron_control_packet.py"
    assert "cron_control_packet.py" in producer["refresh_command"]


def test_artifact_generated_at_reads_standard_key() -> None:
    assert explainer.artifact_generated_at({"generated_at_utc": "2026-01-01T00:00:00Z"}) == "2026-01-01T00:00:00Z"


def test_missing_artifact_explains_missing() -> None:
    row = explainer.explain_artifact(Path("tmp/definitely-missing-artifact-for-test.json"), 24)
    assert row["exists"] is False
    assert row["reason"] == "missing"


if __name__ == "__main__":
    test_producer_for_known_cron_control()
    test_artifact_generated_at_reads_standard_key()
    test_missing_artifact_explains_missing()
    print("ok")
