from __future__ import annotations

"""Tests for the WF75 service-state SQLite proof cache.

The SQLite cache is a local read-only/control-plane proof surface for tests and
cockpit visibility. It is not canon, customer-data authority, owner approval,
portfolio authority, paper/live trading authority, or external delivery.
"""

import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
import json

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from wf75_service_state_sqlite import (  # noqa: E402
    SERVICE_STATE,
    build_summary,
    validate_db,
    write_db,
)


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def current_request_id() -> str:
    state = json.loads(SERVICE_STATE.read_text(encoding="utf-8"))
    run = as_dict(state.get("current_service_run"))
    request = as_dict(run.get("request"))
    return str(request.get("request_id") or "anon-watchlist-ai-infrastructure-v1")


def test_temp_db_builds_with_wal_and_single_claim(errors: list[str]) -> None:
    with TemporaryDirectory() as td:
        db_path = Path(td) / "wf75-service-state.sqlite"
        write_result, claim_results = write_db(db_path)
        validation = validate_db(db_path, claim_results)
        expect(validation["status"] == "ok", f"validation failed: {validation}", errors)
        expect(validation["pragmas"]["journal_mode"] == "wal", "journal mode must be WAL", errors)
        expect(validation["pragmas"]["busy_timeout_ms"] >= 5000, "busy timeout must be at least 5000ms", errors)
        expect(validation["pragmas"]["foreign_keys"] == 1, "foreign keys must be enabled", errors)
        expect(validation["table_counts"]["service_requests"] == 1, "expected one service request", errors)
        expect(validation["table_counts"]["queue_items"] == 1, "expected one queue item", errors)
        expect(validation["table_counts"]["artifact_refs"] >= 8, "expected artifact refs", errors)
        statuses = [row["claim_status"] for row in validation["claim_rows"]]
        expect(statuses.count("claimed") == 1, f"expected exactly one claimed row: {statuses}", errors)
        expect("already_claimed" in statuses, f"expected second worker exclusion: {statuses}", errors)
        expect(write_result["request_id"] == current_request_id(), "unexpected request id", errors)


def test_summary_fails_closed_for_missing_db(errors: list[str]) -> None:
    with TemporaryDirectory() as td:
        summary = build_summary(Path(td) / "missing.sqlite", None, None)
        expect(summary["status"] == "blocked", "missing DB should block summary", errors)
        expect(summary["validation"]["status"] == "error", "missing DB validation should error", errors)


def main() -> int:
    errors: list[str] = []
    test_temp_db_builds_with_wal_and_single_claim(errors)
    test_summary_fails_closed_for_missing_db(errors)
    if errors:
        print("wf75_service_state_sqlite_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("wf75_service_state_sqlite_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
