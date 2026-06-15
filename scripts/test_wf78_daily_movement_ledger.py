from __future__ import annotations

import wf78_daily_movement_ledger as ledger


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    errors: list[str] = []
    packet = ledger.build_ledger()
    summary = packet["summary"]
    repair = packet["repair_priority_queue"]
    boundary = packet["authority_boundary"]

    expect(packet["schema"] == ledger.SCHEMA, "unexpected schema", errors)
    expect(packet["status"] == "ok", f"ledger status not ok: {packet['status']}", errors)
    expect(summary["record_count"] >= 200, "ledger should cover the active WF78 universe", errors)
    expect("repair" in summary["decision_counts"] or "invalidation_review" in summary["decision_counts"], "ledger should expose repair or invalidation work", errors)
    expect(repair["summary"]["repair_count"] == summary["repair_queue_count"], "repair queue count mismatch", errors)
    owner_review = {row["ticker"] for row in packet["categories"]["owner_review_candidates"]}
    no_chase = {row["ticker"] for row in packet["categories"]["no_chase_candidates"]}
    expect(not owner_review.intersection(no_chase), "owner-review and no-chase buckets must be disjoint", errors)
    for row in packet["categories"]["owner_review_candidates"]:
        expect(row["decision"] not in {"repair", "invalidation_review", "no_chase"}, f"{row['ticker']} has non-review decision in owner-review bucket", errors)
    expect(not boundary["capital_deployment_allowed"], "capital deployment boundary widened", errors)
    expect(not boundary["paper_or_live_execution_allowed"], "execution boundary widened", errors)
    expect(not boundary["owner_approval_inferred"], "owner approval inferred", errors)
    for row in packet["records"][:10]:
        row_boundary = row["authority_boundary"]
        expect(not row_boundary["capital_deployment_approved"], f"{row['ticker']} capital approval leaked", errors)
        expect(not row_boundary["trade_or_execution_approved"], f"{row['ticker']} execution approval leaked", errors)

    if errors:
        print("wf78_daily_movement_ledger_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print(
        "wf78_daily_movement_ledger_tests_passed "
        f"records={summary['record_count']} repairs={summary['repair_queue_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
