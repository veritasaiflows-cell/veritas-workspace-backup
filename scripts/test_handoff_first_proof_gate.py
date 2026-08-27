#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "handoff_first_proof_gate.py"


def load_module():
    spec = importlib.util.spec_from_file_location("handoff_first_proof_gate", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def configure_paths(module, root: Path) -> None:
    module.ROOT = root
    module.TMP = root / "tmp"
    module.OUT = module.TMP / "main-session-handoff-first-proof.json"
    by_key = {spec["key"]: dict(spec) for spec in module.LANES}
    by_key["weekday_research"]["path"] = module.TMP / "research-freshness-opportunity-review.json"
    by_key["morning"]["path"] = module.TMP / "run-summary-morning.json"
    by_key["post_close"]["path"] = module.TMP / "run-summary-post-close.json"
    by_key["sunday_weekly"]["path"] = module.TMP / "weekly-intelligence-brief.json"
    by_key["sunday_research"]["path"] = module.TMP / "sunday-research-opportunity-reset-cron-runner.json"
    module.LANES = [by_key[key] for key in ("weekday_research", "morning", "post_close", "sunday_weekly", "sunday_research")]


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class FixedSundayDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        base = cls(2026, 6, 28, 7, 30, tzinfo=timezone.utc)
        return base if tz is None else base.astimezone(tz)


class FixedMondayPreCloseDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        base = cls(2026, 6, 29, 17, 30, tzinfo=timezone.utc)
        return base if tz is None else base.astimezone(tz)


class FixedMondayPostCloseDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        base = cls(2026, 6, 29, 21, 30, tzinfo=timezone.utc)
        return base if tz is None else base.astimezone(tz)


def test_blocked_and_missing_lanes_are_actionable() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        configure_paths(module, root)
        write_json(module.TMP / "research-freshness-opportunity-review.json", {"generated_at_utc": now(), "status": "degraded"})
        write_json(
            module.TMP / "run-summary-morning.json",
            {
                "generated_at_utc": now(),
                "status": "blocked",
                "stop_line": True,
                "execution": {"chain_status": "completed_with_recovery", "failed_step": {"script": "test_dashboard_acceptance.py"}},
                "validation": {"acceptance_passed": True},
                "blockers": ["Finance refresh chain failed at test_dashboard_acceptance.py"],
            },
        )
        write_json(
            module.TMP / "run-summary-post-close.json",
            {
                "generated_at_utc": now(),
                "status": "blocked",
                "stop_line": True,
                "execution": {"chain_status": "completed_with_recovery"},
                "validation": {"acceptance_passed": True},
            },
        )
        write_json(
            module.TMP / "weekly-intelligence-brief.json",
            {"generated_at_utc": now(), "trust_gate_blocked": True, "status": "warning"},
        )
        payload = module.build_payload()
        by_key = {lane["key"]: lane for lane in payload["lanes"]}
        assert by_key["weekday_research"]["state"] == "PROVED"
        assert by_key["morning"]["state"] == "BLOCKED"
        assert by_key["post_close"]["state"] == "BLOCKED"
        assert by_key["sunday_weekly"]["state"] == "BLOCKED"
        assert by_key["sunday_research"]["state"] == "MISSING"
        assert payload["validation"]["status"] == "ok"
        assert payload["repair_lane_packet"]["status"] == "ready"
        assert set(payload["repair_lane_packet"]["target_lanes"]) == {"morning", "post_close", "sunday_weekly", "sunday_research"}


def test_clean_run_summary_can_be_proved() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        configure_paths(module, root)
        write_json(module.TMP / "research-freshness-opportunity-review.json", {"generated_at_utc": now(), "status": "ok"})
        for name in ("run-summary-morning.json", "run-summary-post-close.json"):
            write_json(
                module.TMP / name,
                {
                    "generated_at_utc": now(),
                    "status": "warning",
                    "stop_line": False,
                    "execution": {"chain_status": "ok", "chain_exit_code": 0},
                    "validation": {"acceptance_passed": True},
                },
            )
        write_json(module.TMP / "weekly-intelligence-brief.json", {"generated_at_utc": now(), "status": "ok"})
        write_json(module.TMP / "sunday-research-opportunity-reset-cron-runner.json", {"generated_at_utc": now(), "status": "ok"})
        payload = module.build_payload()
        by_key = {lane["key"]: lane for lane in payload["lanes"]}
        assert all(row["state"] == "PROVED" for row in by_key.values())
        assert payload["status"] == "ok"
        assert payload["repair_lane_packet"]["status"] == "not_needed"


def test_sunday_weekly_machine_sidecar_is_proved_without_canon_authority() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        configure_paths(module, root)
        write_json(module.TMP / "research-freshness-opportunity-review.json", {"generated_at_utc": now(), "status": "ok"})
        for name in ("run-summary-morning.json", "run-summary-post-close.json"):
            write_json(
                module.TMP / name,
                {
                    "generated_at_utc": now(),
                    "status": "warning",
                    "stop_line": False,
                    "validation": {"acceptance_passed": True},
                },
            )
        write_json(
            module.TMP / "weekly-intelligence-brief.json",
            {
                "generated_at_utc": now(),
                "action": "delta_only",
                "canonical_mutation_allowed": False,
                "trust_gate_blocked": True,
                "wrote_to": "05. Intelligence/Weekly Intelligence Brief - machine.md",
            },
        )
        write_json(module.TMP / "sunday-research-opportunity-reset-cron-runner.json", {"generated_at_utc": now(), "status": "ok"})
        payload = module.build_payload()
        by_key = {lane["key"]: lane for lane in payload["lanes"]}
        assert by_key["sunday_weekly"]["state"] == "PROVED"
        assert by_key["sunday_weekly"]["trust_gate_blocked"] is True
        assert payload["status"] == "ok"


def test_weekday_lane_uses_weekend_freshness_window() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        configure_paths(module, root)
        module.datetime = FixedSundayDateTime
        old_proved = "2026-06-26T15:23:13Z"
        write_json(module.TMP / "research-freshness-opportunity-review.json", {"generated_at_utc": old_proved, "status": "ok"})
        write_json(module.TMP / "run-summary-morning.json", {"generated_at_utc": old_proved, "status": "ok", "validation": {"acceptance_passed": True}})
        write_json(module.TMP / "run-summary-post-close.json", {"generated_at_utc": old_proved, "status": "ok", "validation": {"acceptance_passed": True}})
        write_json(module.TMP / "weekly-intelligence-brief.json", {"generated_at_utc": now(), "status": "ok"})
        write_json(module.TMP / "sunday-research-opportunity-reset-cron-runner.json", {"generated_at_utc": now(), "status": "ok"})
        payload = module.build_payload()
        by_key = {lane["key"]: lane for lane in payload["lanes"]}
        assert by_key["morning"]["state"] == "PROVED"
        assert by_key["morning"]["freshness_window_hours"] == 84.0
        assert by_key["post_close"]["state"] == "PROVED"


def test_post_close_uses_monday_pre_close_freshness_window() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        configure_paths(module, root)
        module.datetime = FixedMondayPreCloseDateTime
        old_post_close = "2026-06-26T20:32:40Z"
        write_json(module.TMP / "research-freshness-opportunity-review.json", {"generated_at_utc": now(), "status": "ok"})
        write_json(module.TMP / "run-summary-morning.json", {"generated_at_utc": now(), "status": "ok", "validation": {"acceptance_passed": True}})
        write_json(module.TMP / "run-summary-post-close.json", {"generated_at_utc": old_post_close, "status": "ok", "validation": {"acceptance_passed": True}})
        write_json(module.TMP / "weekly-intelligence-brief.json", {"generated_at_utc": now(), "status": "ok"})
        write_json(module.TMP / "sunday-research-opportunity-reset-cron-runner.json", {"generated_at_utc": now(), "status": "ok"})
        payload = module.build_payload()
        by_key = {lane["key"]: lane for lane in payload["lanes"]}
        assert by_key["post_close"]["state"] == "PROVED"
        assert by_key["post_close"]["freshness_window_hours"] == 84.0


def test_post_close_uses_base_window_after_monday_post_close_window() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        configure_paths(module, root)
        module.datetime = FixedMondayPostCloseDateTime
        old_post_close = "2026-06-26T20:32:40Z"
        write_json(module.TMP / "research-freshness-opportunity-review.json", {"generated_at_utc": now(), "status": "ok"})
        write_json(module.TMP / "run-summary-morning.json", {"generated_at_utc": now(), "status": "ok", "validation": {"acceptance_passed": True}})
        write_json(module.TMP / "run-summary-post-close.json", {"generated_at_utc": old_post_close, "status": "ok", "validation": {"acceptance_passed": True}})
        write_json(module.TMP / "weekly-intelligence-brief.json", {"generated_at_utc": now(), "status": "ok"})
        write_json(module.TMP / "sunday-research-opportunity-reset-cron-runner.json", {"generated_at_utc": now(), "status": "ok"})
        payload = module.build_payload()
        by_key = {lane["key"]: lane for lane in payload["lanes"]}
        assert by_key["post_close"]["state"] == "STALE"
        assert by_key["post_close"]["freshness_window_hours"] == 36.0


def test_authority_widening_blocks_validation() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        configure_paths(module, root)
        write_json(module.TMP / "research-freshness-opportunity-review.json", {"generated_at_utc": now(), "status": "ok"})
        write_json(module.TMP / "run-summary-morning.json", {"generated_at_utc": now(), "status": "ok", "paper_submit_allowed": True})
        payload = module.build_payload()
        by_key = {lane["key"]: lane for lane in payload["lanes"]}
        assert by_key["morning"]["state"] == "BLOCKED"
        assert payload["validation"]["status"] == "error"
        assert "lane_authority_widened:morning" in payload["validation"]["errors"]


def main() -> int:
    test_blocked_and_missing_lanes_are_actionable()
    test_clean_run_summary_can_be_proved()
    test_sunday_weekly_machine_sidecar_is_proved_without_canon_authority()
    test_weekday_lane_uses_weekend_freshness_window()
    test_post_close_uses_monday_pre_close_freshness_window()
    test_post_close_uses_base_window_after_monday_post_close_window()
    test_authority_widening_blocks_validation()
    print("handoff_first_proof_gate tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
