from __future__ import annotations

import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]
SCRIPTS = WORKSPACE / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from dashboard_payload import SQL_AUTHORITY_BOUNDARY, _build_handoff_proof_state


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    errors: list[str] = []
    rows = _build_handoff_proof_state()
    by_key = {row.get("key"): row for row in rows}
    expect(by_key.get("weekday_research", {}).get("state") == "PROVED", "weekday research handoff proof state must remain PROVED", errors)
    for key in ("morning", "post_close", "sunday_weekly", "sunday_research"):
        expect(by_key.get(key, {}).get("state") == "PENDING_FIRST_PROOF", f"{key} handoff proof state must remain PENDING_FIRST_PROOF", errors)
    for key, row in by_key.items():
        sql_source = row.get("sql_source") or {}
        sql_index = row.get("sql_artifact_index") or {}
        expect(sql_source.get("authority_boundary") == SQL_AUTHORITY_BOUNDARY, f"{key}: SQL source boundary missing/polluted", errors)
        expect(sql_index.get("authority_boundary") == SQL_AUTHORITY_BOUNDARY, f"{key}: SQL health boundary missing/polluted", errors)
        expect(sql_index.get("proof_authority") == "provenance_and_health_only_not_handoff_proof", f"{key}: SQL health must not become handoff proof authority", errors)
        expect("proof_authority_note" in row, f"{key}: row must state SQL metadata does not upgrade proof state", errors)
    post_close = by_key.get("post_close", {})
    expect((post_close.get("sql_source") or {}).get("path") == "tmp/run-summary-post-close.json", "post-close handoff should route SQL metadata to run-summary-post-close when indexed", errors)
    if errors:
        print("dashboard_handoff_sql_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("dashboard_handoff_sql_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
