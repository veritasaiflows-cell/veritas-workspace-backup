#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "handoff_first_proof_gate.py"
LANE_KEYS = ("morning", "midday", "post_close", "weekly")


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
    for key in LANE_KEYS:
        by_key[key]["path"] = module.TMP / f"alerts-recommendations-chain-{key.replace('_', '-')}.json"
    module.LANES = [by_key[key] for key in LANE_KEYS]


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def chain_payload(*, status: str = "ok", stop_line: bool = False, validation_status: str = "ok") -> dict:
    return {
        "schema": "veritas.alerts_recommendations_chain.v1",
        "generated_at_utc": now(),
        "status": status,
        "stop_line": stop_line,
        "authority": {
            "review_only": True,
            "alerts_and_non_executing_recommendations_only": True,
            "writes_finance_canon": False,
            "maintains_portfolio_state": False,
            "paper_or_live_execution_allowed": False,
        },
        "validation": {"status": validation_status, "errors": []},
    }


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


def write_clean_lanes(module) -> None:
    for spec in module.LANES:
        write_json(spec["path"], chain_payload())


def test_blocked_and_missing_active_lanes_are_actionable() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        configure_paths(module, Path(tmpdir))
        write_json(module.LANES[0]["path"], chain_payload(status="blocked", stop_line=True))
        write_json(module.LANES[1]["path"], chain_payload())
        write_json(module.LANES[2]["path"], chain_payload(validation_status="error"))
        payload = module.build_payload()
        by_key = {lane["key"]: lane for lane in payload["lanes"]}
        assert by_key["morning"]["state"] == "BLOCKED"
        assert by_key["midday"]["state"] == "PROVED"
        assert by_key["post_close"]["state"] == "BLOCKED"
        assert by_key["weekly"]["state"] == "MISSING"
        assert payload["repair_lane_packet"]["target_lanes"] == ["morning", "post_close", "weekly"]
        assert payload["repair_lane_packet"]["owner_route"] == "alerts_and_recommendations_os"
        assert "lease_command" not in payload["repair_lane_packet"]


def test_clean_active_chain_proofs_are_proved() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        configure_paths(module, Path(tmpdir))
        write_clean_lanes(module)
        payload = module.build_payload()
        assert all(row["state"] == "PROVED" for row in payload["lanes"])
        assert payload["status"] == "ok"
        assert payload["validation"]["status"] == "ok"
        assert payload["repair_lane_packet"]["status"] == "not_needed"
        rendered = json.dumps(payload).lower()
        assert not any(token in rendered for token in module.RETIRED_ROUTE_TOKENS)


def test_weekday_lanes_use_weekend_freshness_window() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        configure_paths(module, Path(tmpdir))
        module.datetime = FixedSundayDateTime
        old_proved = "2026-06-26T15:23:13Z"
        for spec in module.LANES:
            payload = chain_payload()
            payload["generated_at_utc"] = old_proved if spec.get("weekday_only") else now()
            write_json(spec["path"], payload)
        result = module.build_payload()
        by_key = {lane["key"]: lane for lane in result["lanes"]}
        assert by_key["morning"]["state"] == "PROVED"
        assert by_key["midday"]["freshness_window_hours"] == 84.0
        assert by_key["post_close"]["state"] == "PROVED"


def test_post_close_monday_grace_then_base_window() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        configure_paths(module, Path(tmpdir))
        write_clean_lanes(module)
        old_post_close = "2026-06-26T20:32:40Z"
        payload = chain_payload()
        payload["generated_at_utc"] = old_post_close
        post_close = next(spec for spec in module.LANES if spec["key"] == "post_close")
        write_json(post_close["path"], payload)
        module.datetime = FixedMondayPreCloseDateTime
        before = module.build_payload()
        before_row = next(row for row in before["lanes"] if row["key"] == "post_close")
        assert before_row["state"] == "PROVED"
        assert before_row["freshness_window_hours"] == 84.0
        module.datetime = FixedMondayPostCloseDateTime
        after = module.build_payload()
        after_row = next(row for row in after["lanes"] if row["key"] == "post_close")
        assert after_row["state"] == "STALE"
        assert after_row["freshness_window_hours"] == 36.0


def test_authority_widening_and_retired_route_fail_closed() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        configure_paths(module, Path(tmpdir))
        write_clean_lanes(module)
        morning = next(spec for spec in module.LANES if spec["key"] == "morning")
        bad = chain_payload()
        bad["paper_submit_allowed"] = True
        write_json(morning["path"], bad)
        payload = module.build_payload()
        assert payload["validation"]["status"] == "error"
        assert "lane_authority_widened:morning" in payload["validation"]["errors"]

        write_json(morning["path"], chain_payload())
        morning["producer"] = "python scripts\\weekday_morning_review_cron_runner.py --write --validate"
        payload = module.build_payload()
        assert "inactive_producer_route:morning" in payload["validation"]["errors"]
        assert "retired_producer_route:morning" in payload["validation"]["errors"]


def main() -> int:
    test_blocked_and_missing_active_lanes_are_actionable()
    test_clean_active_chain_proofs_are_proved()
    test_weekday_lanes_use_weekend_freshness_window()
    test_post_close_monday_grace_then_base_window()
    test_authority_widening_and_retired_route_fail_closed()
    print("handoff_first_proof_gate tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
