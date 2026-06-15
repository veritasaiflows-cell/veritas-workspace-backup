from __future__ import annotations

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import wf74_operating_control_loop as mod


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def component() -> dict:
    return {
        "schema": "test.component.v1",
        "generated_at_utc": "2026-06-13T00:00:00Z",
        "status": "ok",
        "summary": {"row_count": 1},
        "validation": {"status": "ok", "errors": [], "warnings": []},
        "authority_boundary": {
            "review_only": True,
            "collector_config_mutation_allowed": False,
            "runtime_config_mutation_allowed": False,
            "finance_canon_or_portfolio_mutation_allowed": False,
            "paper_or_live_execution_allowed": False,
            "owner_approval_inferred": False,
        },
    }


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    errors: list[str] = []
    with TemporaryDirectory() as raw:
        root = Path(raw)
        paths = {
            "otel_drift_loop": root / "drift.json",
            "otel_decision_packet": root / "decision.json",
            "finance_repair_loop": root / "finance.json",
            "telegram_digest": root / "digest.json",
            "opportunity_queue": root / "queue.json",
        }
        for path in paths.values():
            write_json(path, component())

        payload = mod.build_payload(paths)
        validation = mod.validate_payload(payload)
        expect(payload["status"] == "ready_review_only", "required components should be ready", errors)
        expect(validation["status"] == "ok", "ready payload should validate", errors)

        drifted = component()
        drifted["authority_boundary"]["collector_config_mutation_allowed"] = True
        write_json(paths["otel_decision_packet"], drifted)
        blocked = mod.build_payload(paths)
        blocked_validation = mod.validate_payload(blocked)
        expect(blocked["status"] == "pending_components", "authority drift should block readiness", errors)
        expect(blocked_validation["status"] == "error", "authority drift should error", errors)

    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("wf74_operating_control_loop_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
