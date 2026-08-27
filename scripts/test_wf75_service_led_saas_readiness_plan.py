from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from wf75_service_led_saas_readiness_plan import (  # noqa: E402
    SERVICE_STATE_EVIDENCE,
    build_plan,
    validate_plan,
)

NOW = datetime(2026, 8, 8, 6, 30, tzinfo=timezone.utc)


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def write_current_evidence(root: Path, *, generated_at: datetime = NOW) -> None:
    written: set[str] = set()
    for contract in SERVICE_STATE_EVIDENCE.values():
        rel = str(contract["artifact"])
        if rel in written:
            continue
        written.add(rel)
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema": contract["schema"],
            "status": sorted(contract["statuses"])[0],
            "generated_at_utc": generated_at.isoformat().replace("+00:00", "Z"),
            "validation": {"status": "ok", "errors": []},
        }
        path.write_text(json.dumps(payload), encoding="utf-8")


def replace_json_field(root: Path, capability: str, field: str, value: object) -> None:
    path = root / str(SERVICE_STATE_EVIDENCE[capability]["artifact"])
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload[field] = value
    path.write_text(json.dumps(payload), encoding="utf-8")


def assert_gap(plan: dict[str, object], capability: str, errors: list[str]) -> None:
    ok, validation_errors = validate_plan(plan)
    expect(not ok, f"{capability}: gap plan must fail validation", errors)
    expect(
        plan.get("status") == "internal_service_led_evidence_gaps",
        f"{capability}: status must expose evidence gaps",
        errors,
    )
    summary = plan.get("evidence_summary") or {}
    expect(
        capability in summary.get("gap_capabilities", []),
        f"{capability}: missing from gap summary: {validation_errors}",
        errors,
    )


def test_current_good_evidence(errors: list[str]) -> None:
    with TemporaryDirectory() as td:
        root = Path(td)
        write_current_evidence(root)
        plan = build_plan(root=root, now=NOW)
        ok, validation_errors = validate_plan(plan)
        expect(ok, f"current evidence should validate: {validation_errors}", errors)
        expect(
            plan["status"] == "internal_service_led_readiness_plan_ready",
            "current evidence should derive the compatible internal-plan status",
            errors,
        )
        summary = plan["evidence_summary"]
        expect(summary["capability_count"] == 9, "capability count must be 9", errors)
        expect(summary["unique_artifact_count"] == 8, "unique artifact count must be 8", errors)
        expect(summary["all_evidence_current"] is True, "all evidence should be current", errors)
        target = plan["readiness_target"]
        expect(target["classification"] == "future_target_only", "readiness band must be future-only", errors)
        expect(target["current_readiness_percentage"] is None, "current readiness percentage must not be inferred", errors)


def test_missing_evidence(errors: list[str]) -> None:
    with TemporaryDirectory() as td:
        root = Path(td)
        write_current_evidence(root)
        capability = "service_state_store"
        (root / str(SERVICE_STATE_EVIDENCE[capability]["artifact"])).unlink()
        assert_gap(build_plan(root=root, now=NOW), capability, errors)


def test_invalid_json_evidence(errors: list[str]) -> None:
    with TemporaryDirectory() as td:
        root = Path(td)
        write_current_evidence(root)
        capability = "operator_console_work_queue"
        (root / str(SERVICE_STATE_EVIDENCE[capability]["artifact"])).write_text("{", encoding="utf-8")
        assert_gap(build_plan(root=root, now=NOW), capability, errors)


def test_stale_evidence(errors: list[str]) -> None:
    with TemporaryDirectory() as td:
        root = Path(td)
        write_current_evidence(root)
        capability = "scenario_template_library"
        replace_json_field(
            root,
            capability,
            "generated_at_utc",
            (NOW - timedelta(hours=25)).isoformat().replace("+00:00", "Z"),
        )
        assert_gap(build_plan(root=root, now=NOW), capability, errors)


def test_bad_status_evidence(errors: list[str]) -> None:
    with TemporaryDirectory() as td:
        root = Path(td)
        write_current_evidence(root)
        capability = "artifact_only_pm_handoff"
        replace_json_field(root, capability, "status", "blocked")
        assert_gap(build_plan(root=root, now=NOW), capability, errors)


def test_bad_schema_evidence(errors: list[str]) -> None:
    with TemporaryDirectory() as td:
        root = Path(td)
        write_current_evidence(root)
        capability = "cron_main_handoff_expansion"
        replace_json_field(root, capability, "schema", "wrong.schema.v1")
        assert_gap(build_plan(root=root, now=NOW), capability, errors)


def main() -> int:
    errors: list[str] = []
    test_current_good_evidence(errors)
    test_missing_evidence(errors)
    test_invalid_json_evidence(errors)
    test_stale_evidence(errors)
    test_bad_status_evidence(errors)
    test_bad_schema_evidence(errors)
    if errors:
        print("wf75_service_led_saas_readiness_plan_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("wf75_service_led_saas_readiness_plan_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
