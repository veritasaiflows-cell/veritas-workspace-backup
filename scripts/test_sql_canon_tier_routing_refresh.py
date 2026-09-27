from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "sql_canon_tier_routing_refresh.py"

spec = importlib.util.spec_from_file_location("sql_canon_tier_routing_refresh", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def router_payload(expected_count: int = 300) -> dict:
    return {
        "status": "ok",
        "summary": {"active_ticker_count": expected_count},
        "validation": {"status": "ok", "checks": []},
    }


def router_rows(count: int = 300) -> list[dict]:
    return [
        {
            "ticker": f"T{i:03d}",
            "capital_deployment_approved": False,
            "trade_or_execution_approved": False,
        }
        for i in range(count)
    ]


def test_validate_source_accepts_current_dynamic_300_row_router_packet() -> None:
    assert module.validate_source(router_payload(), router_rows()) == []


def test_validate_source_blocks_partial_source_even_when_not_200_specific() -> None:
    errors = module.validate_source(router_payload(expected_count=300), router_rows(count=299))
    assert "source_row_count_mismatch" in errors
    assert "source_row_count_not_200" not in errors


def test_validate_source_blocks_authority_widening() -> None:
    rows = router_rows()
    rows[0]["trade_or_execution_approved"] = True
    errors = module.validate_source(router_payload(), rows)
    assert "source_has_capital_or_execution_flags" in errors


def test_expected_row_count_can_fall_back_to_router_validation_check() -> None:
    payload = {
        "status": "ok",
        "validation": {
            "status": "ok",
            "checks": [
                {
                    "name": "active_universe_rows_present",
                    "ok": True,
                    "detail": 300,
                }
            ],
        },
    }
    assert module.expected_source_row_count(payload) == 300


MODULE_WRITE_PATH_HELPERS = [
    "source_rows",
    "connect",
    "backup_db",
    "table_digest",
    "current_diffs",
    "load_json",
    "sha256",
    "atomic_write_json",
    "backup_sqlite_database",
]

RETIRED_MARKER = "retired_wf78_tier_routing_writer_disabled"


def _fail_if_called(name: str):
    def _fail(*args, **kwargs):
        raise AssertionError("retired writer must not call " + name)
    return _fail


def _install_fail_stubs(skip=(), extra=()):
    skip_set = set(skip)
    saved = {"module_attrs": {}}
    for name in list(MODULE_WRITE_PATH_HELPERS) + list(extra):
        if name in skip_set:
            continue
        saved["module_attrs"][name] = getattr(module, name)
        setattr(module, name, _fail_if_called("module." + name))
    saved["sqlite_connect"] = sqlite3.connect
    sqlite3.connect = _fail_if_called("sqlite3.connect")
    saved["path_mkdir"] = Path.mkdir
    saved["path_write_text"] = Path.write_text
    Path.mkdir = _fail_if_called("Path.mkdir")
    Path.write_text = _fail_if_called("Path.write_text")
    return saved


def _restore_fail_stubs(saved) -> None:
    for name, value in saved["module_attrs"].items():
        setattr(module, name, value)
    sqlite3.connect = saved["sqlite_connect"]
    Path.mkdir = saved["path_mkdir"]
    Path.write_text = saved["path_write_text"]


def test_connect_write_is_denied_before_sqlite_connect() -> None:
    saved = _install_fail_stubs(skip=("connect",))
    try:
        try:
            module.connect(write=True)
        except RuntimeError as exc:
            assert "retired" in str(exc).lower()
        else:
            raise AssertionError("connect(write=True) must raise")
    finally:
        _restore_fail_stubs(saved)


def test_backup_db_is_denied_before_mutation_helpers() -> None:
    saved = _install_fail_stubs(skip=("backup_db",))
    try:
        try:
            module.backup_db("probe-run")
        except RuntimeError as exc:
            assert "retired" in str(exc).lower()
        else:
            raise AssertionError("backup_db must raise")
    finally:
        _restore_fail_stubs(saved)


def test_apply_refresh_returns_deterministic_deny_without_side_effects() -> None:
    saved = _install_fail_stubs(skip=("apply_refresh",))
    try:
        first = module.apply_refresh()
        second = module.apply_refresh()
    finally:
        _restore_fail_stubs(saved)
    assert first == second
    assert first["applied"] is False
    assert first.get("db_apply_performed") is False
    assert first["status"] == "retired"
    assert first["status"] not in ("ok", "ready_for_db_apply")
    assert RETIRED_MARKER in first["errors"]
    assert "retired" in str(first["reason"]).lower()


def test_build_returns_retired_payload_without_source_or_db() -> None:
    saved = _install_fail_stubs(extra=("apply_refresh",))
    try:
        without_apply = module.build(False)
        with_apply = module.build(True)
    finally:
        _restore_fail_stubs(saved)
    for payload in (without_apply, with_apply):
        assert payload["status"] == "retired"
        assert payload["status"] not in ("ok", "ready_for_db_apply")
        assert "ready_for_db_apply" not in json.dumps(payload)
        assert payload.get("db_apply_performed") is False
        assert payload.get("written") == []
        assert payload["apply_result"]["applied"] is False
        assert payload["validation"]["status"] == "error"
        assert RETIRED_MARKER in payload["validation"]["errors"]
    first = dict(without_apply)
    second = dict(with_apply)
    first.pop("generated_at_utc", None)
    second.pop("generated_at_utc", None)
    assert first == second


def _snapshot_out():
    if module.OUT.exists():
        return module.OUT.read_bytes()
    return None


CLI_FLAG_COMBOS = [
    [],
    ["--write"],
    ["--apply-db"],
    ["--validate"],
    ["--write", "--apply-db"],
    ["--write", "--validate"],
    ["--apply-db", "--validate"],
    ["--write", "--apply-db", "--validate"],
]


def test_cli_every_flag_combination_returns_nonzero_tombstone_without_side_effects() -> None:
    before = _snapshot_out()
    for flags in CLI_FLAG_COMBOS:
        saved = _install_fail_stubs(extra=("apply_refresh",))
        buffer = io.StringIO()
        try:
            with contextlib.redirect_stdout(buffer):
                code = module.main(list(flags))
        finally:
            _restore_fail_stubs(saved)
        assert code != 0, flags
        tombstone = json.loads(buffer.getvalue())
        assert tombstone["status"] == "retired", flags
        assert tombstone["status"] not in ("ok", "ready_for_db_apply"), flags
        assert tombstone.get("db_apply_performed") is False, flags
        assert tombstone.get("written") == [], flags
        assert tombstone["errors"], flags
        assert _snapshot_out() == before, flags


if __name__ == "__main__":
    test_validate_source_accepts_current_dynamic_300_row_router_packet()
    test_validate_source_blocks_partial_source_even_when_not_200_specific()
    test_validate_source_blocks_authority_widening()
    test_expected_row_count_can_fall_back_to_router_validation_check()
    test_connect_write_is_denied_before_sqlite_connect()
    test_backup_db_is_denied_before_mutation_helpers()
    test_apply_refresh_returns_deterministic_deny_without_side_effects()
    test_build_returns_retired_payload_without_source_or_db()
    test_cli_every_flag_combination_returns_nonzero_tombstone_without_side_effects()
    print("sql_canon_tier_routing_refresh tests passed")
