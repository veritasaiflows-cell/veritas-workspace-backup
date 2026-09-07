from __future__ import annotations

import json
import tempfile
from datetime import date
from pathlib import Path

import macro_event_calendar as calendar


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_macro_followup_routes_only_alert_and_recommendation_refresh() -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        calendar.MACRO_REGIME = root / "macro-regime.json"
        calendar.ALERT_CONTROLLER = root / "alert-controller.json"
        calendar.ALERT_DIGEST = root / "alert-digest.json"
        write_json(calendar.MACRO_REGIME, {"status": "ok", "macro_regime": "neutral"})
        write_json(calendar.ALERT_CONTROLLER, {"status": "ok"})
        write_json(calendar.ALERT_DIGEST, {"status": "ok"})

        payload = calendar.build_calendar(as_of=date(2026, 6, 1))
        source_paths = {row["path"] for row in payload["source_artifacts"]}
        assert calendar.rel(calendar.ALERT_CONTROLLER) in source_paths
        assert calendar.rel(calendar.ALERT_DIGEST) in source_paths
        contract = json.dumps(payload["operator_followup_contract"]).lower()
        for retired_marker in ("deployment", "paper order", "portfolio posture", "market-state", "sizing"):
            assert retired_marker not in contract
        assert "alert states" in contract
        assert "non-executing recommendation context" in contract


if __name__ == "__main__":
    test_macro_followup_routes_only_alert_and_recommendation_refresh()
    print("macro_event_calendar_tests_passed")
