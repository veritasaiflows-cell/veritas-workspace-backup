#!/usr/bin/env python3
from __future__ import annotations

import concurrent_lane_manager as lanes


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def active_sql_lane(path: str, workstream: str = "unit-test", workflow_id: str = "SQL-CANON") -> dict:
    return {
        "lane_id": f"SQL-CANON::{workstream}",
        "workflow_id": workflow_id,
        "workstream_id": workstream,
        "owner": "main-session",
        "status": "leased",
        "lease_expires_at_utc": "2999-01-01T00:00:00Z",
        "allowed_writes": [path],
        "acceptance_commands": ["python scripts\\sql_source_lineage_artifact_registry_repair.py --write --apply --validate"],
    }


def main() -> None:
    register = lanes.empty_register()
    register["lanes"] = [
        active_sql_lane("state/finance/finance-canon.sqlite", "unit-test-db"),
        active_sql_lane("backups/finance-sql-source-lineage", "unit-test-backup-root"),
        active_sql_lane("backups/finance-sql-source-lineage/20260622/finance-canon.sqlite", "unit-test-backup"),
        active_sql_lane(
            "backups/finance-sql-canon-migration/finance-canon-consumer-registry-sync-20260624T220000Z.sqlite",
            "unit-test-consumer-registry-backup",
        ),
        active_sql_lane(
            "backups/reference-levels-derived-refresh/20260705T200000Z/finance-canon.sqlite",
            "unit-test-reference-levels-backup",
        ),
    ]
    result = lanes.validate_register(register)
    expect(result["status"] == "ok", f"expected SQL-CANON exact exceptions to validate: {result['errors']}")

    namespaced = lanes.empty_register()
    namespaced["lanes"] = [
        active_sql_lane(
            "state/finance/finance-canon.sqlite",
            "unit-test-namespaced-db",
            workflow_id="SQL-CANON::SOURCE-LINEAGE-WARNING-CLEANUP-20260630",
        ),
    ]
    namespaced_result = lanes.validate_register(namespaced)
    expect(
        namespaced_result["status"] == "ok",
        f"expected namespaced SQL-CANON exact exception to validate: {namespaced_result['errors']}",
    )

    blocked = lanes.empty_register()
    blocked["lanes"] = [active_sql_lane("state/finance/other.sqlite")]
    blocked_result = lanes.validate_register(blocked)
    blocked_names = {item["name"] for item in blocked_result["errors"]}
    expect("no_active_forbidden_write_paths" in blocked_names, "generic state/finance write must remain blocked")
    print("concurrent_lane_manager_sql_canon_exception_tests_passed")


if __name__ == "__main__":
    main()
