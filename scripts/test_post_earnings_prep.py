from __future__ import annotations

import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import post_earnings_note_targets as targets
import post_earnings_prep as prep


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def main() -> int:
    with TemporaryDirectory() as raw:
        root = Path(raw)
        tmp = root / "tmp"
        now = datetime.now(timezone.utc).isoformat()
        reported = (date.today() - timedelta(days=1)).isoformat()
        write_json(tmp / "technical-refresh.json", {"records": [{"ticker": "TEST", "close": 10.0, "data_date": reported}]})
        write_json(tmp / "trigger-sheet.json", {"status": "ok", "generated_at_utc": now, "records": [{"ticker": "TEST", "action_state": "WATCH", "why": "fixture"}]})
        write_json(tmp / "earnings-calendar.json", {"status": "ok", "generated_at_utc": now, "records": [{"ticker": "TEST", "next_earnings_date": reported, "primary_confirmed": False, "date_source_class": "provider_estimate"}]})
        write_json(tmp / "official-earnings-bridge.json", {"bridges": [{"ticker": "TEST", "status": "manual_required", "period_end": "2026-06-30", "official_earnings_bridge": {"official_evidence_status": "manual_required"}}]})
        write_json(tmp / "alert-level-freshness-controller.json", {"rows": [{"ticker": "TEST", "alert_state": "monitor_only", "signal_state": "monitor_only", "freshness_status": "current"}]})

        old_prep = (prep.WORKSPACE, prep.TMP, prep.TECH_PATH, prep.DEPLOY_PATH, prep.TRIGGER_PATH, prep.EARNINGS_PATH, prep.STATE_PATH, prep.OFFICIAL_BRIDGE_PATH, prep.ALERT_CONTROLLER_PATH, prep.OUT_PATH)
        try:
            prep.WORKSPACE = root
            prep.TMP = tmp
            prep.TECH_PATH = tmp / "technical-refresh.json"
            prep.DEPLOY_PATH = tmp / "deployment-check.json"
            prep.TRIGGER_PATH = tmp / "trigger-sheet.json"
            prep.EARNINGS_PATH = tmp / "earnings-calendar.json"
            prep.STATE_PATH = tmp / "market-state.json"
            prep.OFFICIAL_BRIDGE_PATH = tmp / "official-earnings-bridge.json"
            prep.ALERT_CONTROLLER_PATH = tmp / "alert-level-freshness-controller.json"
            prep.OUT_PATH = tmp / "post-earnings-prep.json"
            prep.main()
        finally:
            (prep.WORKSPACE, prep.TMP, prep.TECH_PATH, prep.DEPLOY_PATH, prep.TRIGGER_PATH, prep.EARNINGS_PATH, prep.STATE_PATH, prep.OFFICIAL_BRIDGE_PATH, prep.ALERT_CONTROLLER_PATH, prep.OUT_PATH) = old_prep

        packet = json.loads((tmp / "post-earnings-prep.json").read_text(encoding="utf-8"))
        assert packet["input_status"]["deployment_check"] == "unavailable_uses_trigger_context"
        assert packet["packets"][0]["reconciliation"]["alert_context"]["alert_state"] == "monitor_only"
        assert packet["post_earnings_reconciliation_queue"][0]["required_reviews"] == ["scorecard", "thesis", "catalyst", "alert"]

        old_targets = (targets.WORKSPACE, targets.TMP, targets.PREP_PATH, targets.OUT_PATH)
        try:
            targets.WORKSPACE = root
            targets.TMP = tmp
            targets.PREP_PATH = tmp / "post-earnings-prep.json"
            targets.OUT_PATH = tmp / "post-earnings-note-targets.json"
            targets.main()
        finally:
            (targets.WORKSPACE, targets.TMP, targets.PREP_PATH, targets.OUT_PATH) = old_targets

        result = json.loads((tmp / "post-earnings-note-targets.json").read_text(encoding="utf-8"))
        assert {task["task"] for task in result["reconciliation_queue"]} == {"scorecard", "thesis", "catalyst", "alert"}
        assert all(task["automatic_mutation_allowed"] is False for task in result["reconciliation_queue"])
        assert not any(path.startswith("03. Portfolio/") for path in result["impacted_notes"])
    print("post_earnings_prep_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
