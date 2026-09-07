from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import finance_cache_cleanup_readiness as cleanup_readiness
import tier_entitlement_surface_inventory as tier_inventory


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "cache_dependency_manifest.py"
RETIRED_ARTIFACT = ROOT / "tmp" / "cache-dependency-manifest.json"
WRITE_PROBE = ROOT / "tmp" / "cache-dependency-manifest-retirement-write-probe.json"
PRIMARY_SQL = ROOT / "state" / "finance" / "finance-canon.sqlite"
LEGACY_PATHS = (
    ROOT / "03. Portfolio" / "Execution Board.md",
    ROOT / "tmp" / "portfolio-config.json",
    ROOT / "tmp" / "veritas-canon-cache.sqlite",
    ROOT / "tmp" / "canonical-finance-data-plane.sqlite",
)

EXPECTED_PAYLOAD: dict[str, object] = {
    "schema": "veritas.cache_dependency_manifest.retired_compatibility.v1",
    "status": "blocked",
    "reason": "retired_surface",
    "surface": "cache_dependency_manifest",
    "retired": True,
    "tombstone": True,
    "compatibility_mode": "deny_only",
    "current_truth_allowed": False,
    "legacy_manifest_read_allowed": False,
    "legacy_manifest_write_allowed": False,
    "cache_chain_build_allowed": False,
    "cache_or_sql_read_allowed": False,
    "filesystem_read_allowed": False,
    "filesystem_write_allowed": False,
    "subprocess_allowed": False,
    "network_allowed": False,
    "schedule_mutation_allowed": False,
    "sql_mutation_allowed": False,
    "canon_mutation_allowed": False,
    "tier_mutation_allowed": False,
    "portfolio_state_or_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "trade_order_or_execution_allowed": False,
    "paper_or_live_execution_allowed": False,
    "owner_approval_inferred": False,
    "exit_code": 2,
}
EXPECTED_STDOUT = json.dumps(EXPECTED_PAYLOAD, sort_keys=True, separators=(",", ":")) + "\n"


def file_state(path: Path) -> tuple[bool, str | None, int | None, int | None]:
    if not path.exists():
        return False, None, None, None
    stat = path.stat()
    digest = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
    return True, digest, stat.st_size if path.is_file() else None, stat.st_mtime_ns


def protected_states() -> dict[str, tuple[bool, str | None, int | None, int | None]]:
    paths = (RETIRED_ARTIFACT, WRITE_PROBE, PRIMARY_SQL, *LEGACY_PATHS)
    return {str(path): file_state(path) for path in paths}


def test_every_legacy_cli_shape_is_the_same_zero_read_zero_write_denial() -> None:
    assert not WRITE_PROBE.exists()
    before = protected_states()
    cli_shapes = [
        [],
        ["--tickers", "NVDA,ETN"],
        ["--write"],
        ["--validate", "--pretty"],
        ["--out", str(WRITE_PROBE)],
        ["--tickers", "NOT-A-TICKER", "--write", "--validate", "--unknown", "value"],
    ]
    outputs: list[str] = []
    for args in cli_shapes:
        proc = subprocess.run(
            [sys.executable, "-B", str(SCRIPT), *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        assert proc.returncode == 2
        assert proc.stderr == ""
        assert proc.stdout == EXPECTED_STDOUT
        assert json.loads(proc.stdout) == EXPECTED_PAYLOAD
        outputs.append(proc.stdout)
    assert len(set(outputs)) == 1
    assert protected_states() == before


def test_tombstone_has_no_operational_read_or_write_capability() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported_modules.append(node.module or "")
    assert sorted(imported_modules) == ["__future__", "json"]

    forbidden_calls = {
        "open",
        "read_text",
        "read_bytes",
        "write_text",
        "write_bytes",
        "mkdir",
        "unlink",
        "rename",
        "replace",
        "run",
        "Popen",
        "connect",
        "urlopen",
    }
    invoked: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            invoked.add(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            invoked.add(node.func.attr)
    assert invoked.isdisjoint(forbidden_calls)

    retired_helper = "wf72_entry_stop_" + "reference_helper"
    forbidden_operational_tokens = {
        retired_helper,
        "finance_intelligence_state",
        "finance_production_scope",
        "sqlite3",
        "atomic_write_json",
        "load_json_artifact",
        "cache-dependency-manifest.json",
        "veritas-canon-cache.sqlite",
        "canonical-finance-data-plane.sqlite",
        "trade-grade-full-answer",
    }
    assert all(token not in source for token in forbidden_operational_tokens)


def test_retired_artifact_cannot_report_current_or_green_cache_truth() -> None:
    payload = json.loads(RETIRED_ARTIFACT.read_text(encoding="utf-8"))
    assert payload == {
        "schema": "veritas.cache_dependency_manifest.retired_artifact.v1",
        "generated_at_utc": "2026-09-01T05:00:00Z",
        "status": "retired",
        "reason": "retired_surface",
        "surface": "cache_dependency_manifest",
        "retired": True,
        "tombstone": True,
        "compatibility_mode": "deny_only",
        "current_truth_allowed": False,
        "historical_green_state_superseded": True,
        "authority": {
            "review_only": True,
            "filesystem_mutation_allowed": False,
            "sql_or_cache_access_allowed": False,
            "schedule_mutation_allowed": False,
            "canon_or_tier_mutation_allowed": False,
            "portfolio_capital_account_order_or_execution_allowed": False,
            "paper_or_live_execution_allowed": False,
            "owner_approval_inferred": False,
        },
    }
    assert "cache_chain" not in payload
    assert "tickers" not in payload
    assert "summary" not in payload
    assert payload["status"] != "ok"
    assert payload["current_truth_allowed"] is False


def test_cleanup_readiness_observes_retired_status_without_promoting_truth() -> None:
    record = cleanup_readiness.json_artifact_record(
        "cache_dependency_manifest",
        RETIRED_ARTIFACT,
        "cache_dependency_guard",
    )
    assert record["status"] == "retired"
    assert record["generated_at_utc"] == "2026-09-01T05:00:00Z"
    assert record["delete_allowed_now"] is False
    assert record["requires_owner_packet_for_delete_or_archive"] is True


def test_inventory_structurally_classifies_only_capability_free_tombstone() -> None:
    source_lines = SCRIPT.read_text(encoding="utf-8").splitlines()
    evidence = tier_inventory.detect_explicit_deny_only_tombstone(source_lines)
    assert {item["detail"] for item in evidence} == {
        "retired_true",
        "tombstone_true",
        "deny_only",
        "current_truth_false",
        "retired_exit_two",
    }

    operational_variant = [*source_lines, "import sqlite3", "sqlite3.connect('legacy.sqlite')"]
    assert tier_inventory.detect_explicit_deny_only_tombstone(operational_variant) == []
    hidden_runtime_variant = [*source_lines, "eval('1 + 1')"]
    assert tier_inventory.detect_explicit_deny_only_tombstone(hidden_runtime_variant) == []
    rebound_main_variant = [
        *source_lines,
        "main = eval",
        "main(\"__import__('os').system('echo classifier-bypass')\")",
    ]
    assert tier_inventory.detect_explicit_deny_only_tombstone(rebound_main_variant) == []
    marker_spoof = "\n".join(source_lines).replace(
        "\nEXIT_RETIRED = 2\n",
        "\nEXIT_RETIRED = 0\n",
        1,
    ).replace(
        "Every legacy CLI shape receives the same deterministic denial.",
        "Every legacy CLI shape receives the same deterministic denial. EXIT_RETIRED = 2",
    )
    assert tier_inventory.detect_explicit_deny_only_tombstone(marker_spoof.splitlines()) == []

    row = tier_inventory.build_row(
        SCRIPT,
        ROOT,
        source_lines,
        SCRIPT.read_bytes(),
        {},
        {},
        None,
        None,
        False,
    )
    assert row is not None
    assert row["lifecycle"] == "retired"
    assert row["operational_status"] == "retired_not_operational"
    assert row["proposed_disposition"] == "retirement_review"
    assert "explicit_deny_only_tombstone" in row["detection_classes"]


def main() -> int:
    test_every_legacy_cli_shape_is_the_same_zero_read_zero_write_denial()
    test_tombstone_has_no_operational_read_or_write_capability()
    test_retired_artifact_cannot_report_current_or_green_cache_truth()
    test_cleanup_readiness_observes_retired_status_without_promoting_truth()
    test_inventory_structurally_classifies_only_capability_free_tombstone()
    print("cache_dependency_manifest_retirement_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
