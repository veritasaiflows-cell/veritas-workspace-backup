#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "wf88_daily_actionability_refresh.py"


def load_module():
    spec = importlib.util.spec_from_file_location("wf88_daily_actionability_refresh", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_runner_completes_successful_sequence() -> None:
    module = load_module()
    commands = [
        {"id": "one", "command": [sys.executable, "-c", "print('one')"]},
        {"id": "two", "command": [sys.executable, "-c", "print('two')"]},
    ]
    results, ok = module.run_sequence(commands, execute=True, timeout_seconds=30)
    assert ok is True
    assert len(results) == 2
    assert results[0]["returncode"] == 0
    assert "one" in results[0]["stdout_tail"]


def test_runner_stops_on_first_failure() -> None:
    module = load_module()
    commands = [
        {"id": "ok", "command": [sys.executable, "-c", "print('ok')"]},
        {"id": "fail", "command": [sys.executable, "-c", "raise SystemExit(3)"]},
        {"id": "skip", "command": [sys.executable, "-c", "print('skip')"]},
    ]
    results, ok = module.run_sequence(commands, execute=True, timeout_seconds=30)
    assert ok is False
    assert len(results) == 2
    assert results[-1]["id"] == "fail"
    assert results[-1]["returncode"] == 3


def test_dry_run_does_not_execute_commands() -> None:
    module = load_module()
    commands = [{"id": "dry", "command": [sys.executable, "-c", "raise SystemExit(9)"]}]
    results, ok = module.run_sequence(commands, execute=False, timeout_seconds=30)
    assert ok is True
    assert results[0]["executed"] is False
    assert results[0]["returncode"] is None


def test_fresh_wf74_artifact_reuse_skips_command() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as td:
        artifact = Path(td) / "fresh.json"
        artifact.write_text(json.dumps({
            "status": "ok",
            "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "validation": {"status": "ok"},
        }), encoding="utf-8")
        commands = [{
            "id": "reuse",
            "command": [sys.executable, "-c", "raise SystemExit(9)"],
            "reuse_fresh_artifacts": [str(artifact)],
        }]
        results, ok = module.run_sequence(commands, execute=True, timeout_seconds=30, reuse_fresh_wf74=True)
        assert ok is True
        assert results[0]["executed"] is False
        assert results[0]["skipped"] is True
        assert results[0]["returncode"] == 0
        assert results[0]["skip_reason"] == "fresh_validated_wf74_artifact_reused"


def test_stale_wf74_artifact_does_not_skip_command() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as td:
        artifact = Path(td) / "stale.json"
        stale_at = datetime.now(timezone.utc) - timedelta(hours=5)
        artifact.write_text(json.dumps({
            "status": "ok",
            "generated_at_utc": stale_at.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "validation": {"status": "ok"},
        }), encoding="utf-8")
        commands = [{
            "id": "stale",
            "command": [sys.executable, "-c", "raise SystemExit(7)"],
            "reuse_fresh_artifacts": [str(artifact)],
        }]
        results, ok = module.run_sequence(
            commands,
            execute=True,
            timeout_seconds=30,
            reuse_fresh_wf74=True,
            fresh_max_age_minutes=60,
        )
        assert ok is False
        assert results[0]["executed"] is True
        assert results[0]["skipped"] is False
        assert results[0]["returncode"] == 7


def test_no_reuse_mode_runs_even_with_fresh_artifact() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as td:
        artifact = Path(td) / "fresh.json"
        artifact.write_text(json.dumps({
            "status": "ok",
            "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "validation": {"status": "ok"},
        }), encoding="utf-8")
        commands = [{
            "id": "no-reuse",
            "command": [sys.executable, "-c", "raise SystemExit(6)"],
            "reuse_fresh_artifacts": [str(artifact)],
        }]
        results, ok = module.run_sequence(commands, execute=True, timeout_seconds=30, reuse_fresh_wf74=False)
        assert ok is False
        assert results[0]["executed"] is True
        assert results[0]["skipped"] is False
        assert results[0]["returncode"] == 6


def test_wiki_bootstrap_validator_runs_after_wiki_synthesis() -> None:
    module = load_module()
    ids = [row["id"] for row in module.COMMANDS]
    assert "wf88_wiki_synthesis" in ids
    assert "wiki_bootstrap_validator" in ids
    synthesis_index = ids.index("wf88_wiki_synthesis")
    bootstrap_index = ids.index("wiki_bootstrap_validator")
    assert bootstrap_index == synthesis_index + 1
    synthesis_command = module.COMMANDS[synthesis_index]["command"]
    bootstrap_command = module.COMMANDS[bootstrap_index]["command"]
    assert "--write-wiki" in synthesis_command
    assert "scripts\\wiki_bootstrap_validator.py" in bootstrap_command
    assert "--write" in bootstrap_command
    assert "--validate" in bootstrap_command


def main() -> int:
    test_runner_completes_successful_sequence()
    test_runner_stops_on_first_failure()
    test_dry_run_does_not_execute_commands()
    test_fresh_wf74_artifact_reuse_skips_command()
    test_stale_wf74_artifact_does_not_skip_command()
    test_no_reuse_mode_runs_even_with_fresh_artifact()
    test_wiki_bootstrap_validator_runs_after_wiki_synthesis()
    print("wf88 daily actionability refresh tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
