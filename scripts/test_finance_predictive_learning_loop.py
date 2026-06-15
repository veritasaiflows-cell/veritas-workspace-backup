from __future__ import annotations

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import finance_predictive_learning_loop as mod


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def component(schema: str = "test.schema") -> dict:
    return {
        "schema": schema,
        "generated_at_utc": "2026-06-13T00:00:00Z",
        "status": "ok",
        "summary": {"row_count": 1},
        "validation": {"status": "ok"},
        "authority_boundary": {
            "review_only": True,
            "capital_deployment_approved": False,
            "trade_or_execution_approved": False,
            "paper_or_live_execution_allowed": False,
            "brokerage_or_account_action_allowed": False,
            "owner_approval_inferred": False,
        },
    }


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    errors: list[str] = []
    with TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        paths = {
            "history_ledger": root / "history.json",
            "lookback_engine": root / "lookback.json",
            "calibration_report": root / "calibration.json",
            "performance_digest": root / "performance.json",
        }
        for name, path in paths.items():
            write_json(path, component(f"schema.{name}"))
        payload = mod.build_payload(paths)
        validation = mod.validate_payload(payload)
        expect(payload["status"] == "ready_review_only", "all required components should be ready", errors)
        expect(validation["status"] == "ok", "ready payload should validate cleanly", errors)

        drift = component("schema.drift")
        drift["authority_boundary"]["capital_deployment_approved"] = True
        write_json(paths["calibration_report"], drift)
        drift_payload = mod.build_payload(paths)
        drift_validation = mod.validate_payload(drift_payload)
        expect(drift_payload["status"] == "pending_components", "authority drift should block readiness", errors)
        expect(drift_validation["status"] == "error", "authority drift should be validation error", errors)

    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("finance_predictive_learning_loop_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
