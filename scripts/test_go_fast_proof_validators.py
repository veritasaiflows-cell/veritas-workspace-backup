#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "go_fast_proof_validators.py"


def load_module():
    spec = importlib.util.spec_from_file_location("go_fast_proof_validators", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_build_commands_binary_first_and_no_shell_tokens():
    module = load_module()
    commands = module.build_commands(ROOT, True, "inprocess", 96, "implementation")
    assert [command.name for command in commands] == [
        "go-json-proof-contract-lint",
        "go-sql-canon-proof-bundle-lint",
        "go-sql-consumer-registry-drift-lint",
        "go-validator-route-budget-lint",
        "go-canon-json-field-family-parity",
        "go-cron-contract-json-proof-lint",
        "go-finance-canon-authority-event-lint",
        "go-sql-source-artifact-freshness-lint",
        "go-sql-source-lineage-producer-contract-lint",
        "go-json-proof-warning-residue-lint",
        "go-implementation-closeout-ledger-lint",
    ]
    flattened = " ".join(" ".join(command.argv) for command in commands)
    for token in ("&&", "||", ";", "|", ">", "<", "`", "--apply", "--submit", "--promote", "--import"):
        assert token not in flattened
    assert any("go-json-proof-contract-lint" in command.argv[0] for command in commands)
    assert any("go-sql-canon-proof-bundle-lint" in command.argv[0] for command in commands)
    assert any("go-sql-consumer-registry-drift-lint" in command.argv[0] for command in commands)
    assert any("go-validator-route-budget-lint" in command.argv[0] for command in commands)
    assert any("go-canon-json-field-family-parity" in command.argv[0] for command in commands)
    assert any("go-cron-contract-json-proof-lint" in command.argv[0] for command in commands)
    assert any("go-finance-canon-authority-event-lint" in command.argv[0] for command in commands)
    assert any("go-json-proof-warning-residue-lint" in command.argv[0] for command in commands)
    assert any("go-sql-source-artifact-freshness-lint" in command.argv[0] for command in commands)
    assert any("go-sql-source-lineage-producer-contract-lint" in command.argv[0] for command in commands)
    assert any("go-implementation-closeout-ledger-lint" in command.argv[0] for command in commands)
    assert any("--driver" in command.argv and "inprocess" in command.argv for command in commands)
    assert all("tmp/sql-canon-wf78-routing-parity.json" not in command.argv for command in commands)
    assert all("--packet" in command.argv for command in commands[:2])
    assert all("--packet" not in command.argv for command in commands[2:])
    assert "--freshness-report" in commands[8].argv
    assert "--report" in commands[9].argv
    assert "--warning-residue" in commands[10].argv


def test_full_profile_uses_go_default_packet_bundle():
    module = load_module()
    commands = module.build_commands(ROOT, False, "inprocess", 96, "full")
    assert len(commands) == 20
    assert "go-json-proof-structural-validator" in [command.name for command in commands]
    assert "go-entry-stop-band-freshness-validator" in [command.name for command in commands]
    assert "go-pm-queue-authority-lint" in [command.name for command in commands]
    assert "go-finance-answer-completeness-validator" in [command.name for command in commands]
    assert "go-cross-db-referential-integrity-probe" in [command.name for command in commands]
    assert "go-workflow-artifact-freshness-gate" in [command.name for command in commands]
    assert "go-validator-timing-benchmark" in [command.name for command in commands]
    assert "go-execution-board-structural-lint" in [command.name for command in commands]
    assert "go-paper-trading-guard-preflight" in [command.name for command in commands]
    assert all("--packet" not in command.argv for command in commands)
    warning_command = commands[-2]
    assert warning_command.name == "go-json-proof-warning-residue-lint"
    assert "tmp/go-paper-trading-guard-preflight.json" in warning_command.argv


def test_bundle_profile_excludes_only_bundle_dependent_closeout_checks():
    module = load_module()
    commands = module.build_commands(ROOT, False, "inprocess", 96, "bundle")
    names = [command.name for command in commands]

    assert names == [
        "go-json-proof-contract-lint",
        "go-sql-canon-proof-bundle-lint",
        "go-sql-consumer-registry-drift-lint",
        "go-canon-json-field-family-parity",
        "go-cron-contract-json-proof-lint",
        "go-finance-canon-authority-event-lint",
        "go-sql-source-artifact-freshness-lint",
        "go-sql-source-lineage-producer-contract-lint",
    ]
    assert module.proof_packets_for_profile("bundle") == module.IMPLEMENTATION_PROOF_PACKETS
    assert "go-validator-route-budget-lint" not in names
    assert "go-json-proof-warning-residue-lint" not in names
    assert "go-implementation-closeout-ledger-lint" not in names


def test_missing_binary_is_fail_closed(tmp_path):
    module = load_module()
    command = module.ValidatorCommand("missing", [str(tmp_path / "missing.exe")], None)
    result = module.run_command(command, 5)
    assert not result["ok"]
    assert result["returncode"] == 98
    assert result["error"].startswith("missing_binary:")


def test_aggregate_payload_surfaces_inner_warning(tmp_path):
    module = load_module()
    original_root = module.ROOT
    module.ROOT = tmp_path
    try:
        out = tmp_path / "inner.json"
        out.write_text(
            """{
  "status": "warning",
  "summary": {"checks": 2, "critical": 0, "warnings": 1},
  "findings": [
    {"path": "tmp/example.json", "check": "warning_visible", "severity": "warning", "ok": false, "detail": "known residue"}
  ]
}
""",
            encoding="utf-8",
        )
        result = {
            "name": "inner-validator",
            "ok": True,
            "returncode": 0,
            "out": "inner.json",
        }
        payload = module.aggregate_payload("implementation", [], [result])
        assert payload["status"] == "warning"
        assert payload["summary"] == {
            "validator_count": 1,
            "failed_count": 0,
            "warning_count": 1,
            "residue_classifiable_warning_count": 1,
            "post_residue_warning_count": 0,
            "critical_count": 0,
        }
        assert payload["warning_count"] == 1
        assert payload["residue_classifiable_warning_count"] == 1
        assert payload["post_residue_warning_count"] == 0
        assert payload["inner_status_counts"] == {"warning": 1}
        assert payload["warning_details"][0]["validator"] == "inner-validator"
    finally:
        module.ROOT = original_root


def test_aggregate_payload_partitions_post_residue_closeout_warnings(tmp_path):
    module = load_module()
    original_root = module.ROOT
    module.ROOT = tmp_path
    try:
        for name in ("ordinary.json", "closeout.json"):
            (tmp_path / name).write_text(
                '{"status":"warning","summary":{"checks":1,"critical":0,"warnings":1},"findings":[]}\n',
                encoding="utf-8",
            )
        results = [
            {"name": "ordinary-validator", "ok": True, "returncode": 0, "out": "ordinary.json"},
            {
                "name": "go-implementation-closeout-ledger-lint",
                "ok": True,
                "returncode": 0,
                "out": "closeout.json",
            },
        ]
        payload = module.aggregate_payload("implementation", [], results)
        assert payload["summary"]["warning_count"] == 2
        assert payload["summary"]["residue_classifiable_warning_count"] == 1
        assert payload["summary"]["post_residue_warning_count"] == 1
    finally:
        module.ROOT = original_root


def test_write_json_creates_aggregate_payload(tmp_path):
    module = load_module()
    out = tmp_path / "aggregate.json"
    module.write_json(out, {"status": "ok"})
    assert out.exists()
    assert '"status": "ok"' in out.read_text(encoding="utf-8")


if __name__ == "__main__":
    test_build_commands_binary_first_and_no_shell_tokens()
    test_full_profile_uses_go_default_packet_bundle()
    test_bundle_profile_excludes_only_bundle_dependent_closeout_checks()
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        test_missing_binary_is_fail_closed(Path(tmp))
    with tempfile.TemporaryDirectory() as tmp:
        test_aggregate_payload_surfaces_inner_warning(Path(tmp))
    with tempfile.TemporaryDirectory() as tmp:
        test_aggregate_payload_partitions_post_residue_closeout_warnings(Path(tmp))
    with tempfile.TemporaryDirectory() as tmp:
        test_write_json_creates_aggregate_payload(Path(tmp))
    print("status=ok tests=7")
