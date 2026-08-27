#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "heartbeat_priority_handoff.py"


def load_module():
    spec = importlib.util.spec_from_file_location("heartbeat_priority_handoff", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def configure(module, root: Path) -> None:
    module.ROOT = root
    module.TMP = root / "tmp"
    module.OUT = module.TMP / "heartbeat-priority-receipt.json"
    module.CONSUMER_OUT = module.TMP / "heartbeat-main-session-escalation-consumer.json"
    module.PRIORITY_OUT = module.TMP / "heartbeat-main-session-priority-handoff.json"


def priority_boundary() -> dict:
    return {
        "review_only": True,
        "main_session_review_required": True,
        "heartbeat_may_execute": False,
        "heartbeat_may_spawn_helper": False,
        "heartbeat_may_lease_lane": False,
        "cron_schedule_mutation_allowed": False,
        "config_auth_runtime_mutation_allowed": False,
        "sql_or_ticker_import_allowed": False,
        "canon_or_portfolio_mutation_allowed": False,
        "capital_deployment_allowed": False,
        "paper_or_live_execution_allowed": False,
        "brokerage_or_account_action_allowed": False,
        "owner_approval_inferred": False,
    }


def test_fixed_bridge_is_heartbeat_dry_run_only() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        configure(module, root)
        write_json(module.CONSUMER_OUT, {
            "status": "warning", "mode": "dry_run", "context": "heartbeat", "execution_results": [], "summary": {},
        })
        write_json(module.PRIORITY_OUT, {
            "status": "needs_main_review", "receipt": "NEW_PRIORITY", "validation": {"status": "ok"},
            "authority_boundary": priority_boundary(),
        })
        module.run_step = lambda name, command, timeout=300: {"name": name, "command": command, "ok": True}
        receipt = module.build_receipt()
        assert receipt["validation"]["status"] == "ok"
        assert receipt["status"] == "needs_main_review"
        assert receipt["receipt"] == "NEW_PRIORITY"
        commands = [" ".join(step["command"]) for step in receipt["steps"]]
        assert len(commands) == 1
        assert all("--context heartbeat" in command for command in commands)
        assert all("--execute-safe" not in command and "--execute-one" not in command for command in commands)
        assert all("--out tmp/heartbeat-main-session-escalation-consumer.json" in command for command in commands)
        assert all("--priority-out tmp/heartbeat-main-session-priority-handoff.json" in command for command in commands)


def test_receipt_rejects_execution_and_nonfixed_cli_flags() -> None:
    module = load_module()
    bad = {
        "authority_boundary": module.AUTHORITY_BOUNDARY,
        "steps": [{"name": "bad", "command": ["python", "x.py", "--execute-safe"], "ok": True}],
        "consumer": {"context": "heartbeat", "mode": "dry_run", "execution_results": []},
        "priority_handoff": {"validation": {"status": "ok"}, "receipt": "NO_DELTA"},
        "source_artifacts": {"consumer": "tmp/main-session-escalation-consumer.json", "priority_handoff": "tmp/main-session-priority-handoff.json"},
    }
    validation = module.validate_receipt(bad)
    assert validation["status"] == "blocked"
    assert "fixed_heartbeat_commands_changed" in validation["errors"]
    assert "heartbeat_source_artifacts_changed" in validation["errors"]

    old_argv = sys.argv
    try:
        for forbidden_flag, forbidden_value in (("--execute-safe", None), ("--out", "tmp/cron-control-packet.json")):
            sys.argv = [str(SCRIPT), "--write", forbidden_flag] + ([] if forbidden_value is None else [forbidden_value])
            try:
                module.parse_args()
                raise AssertionError(f"{forbidden_flag} was accepted")
            except SystemExit as exc:
                assert exc.code == 2
    finally:
        sys.argv = old_argv


def main() -> int:
    test_fixed_bridge_is_heartbeat_dry_run_only()
    test_receipt_rejects_execution_and_nonfixed_cli_flags()
    print("heartbeat_priority_handoff tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
