from __future__ import annotations

from board_canon_guardrail import build_risk_alerts, contains_contradiction, contains_stop_truth, markdown_section, markdown_table_row


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    note = """# Note

### JPM
- Stance: **Do not touch / stop breached**.
- Close is below the hard stop.

---

### LNG
- Stance: **Active watch**.
"""
    require("stop breached" in markdown_section(note, "JPM"), "section extraction should capture JPM stop language")
    require("Active watch" in markdown_section(note, "LNG"), "section extraction should capture next ticker section")

    table = """| Ticker | State | Source |
|---|---|---|
| JPM | Do not touch / stop-breached | Execution Board |
| LNG | Active watch | Coverage and Watchlist |
"""
    require("stop-breached" in markdown_table_row(table, "JPM"), "row extraction should capture JPM row")
    require("Active watch" in markdown_table_row(table, "LNG"), "row extraction should capture LNG row")
    require(contains_stop_truth("Do not touch / stop-breached", hard=True), "hard stop truth should detect stop-breached")
    require(contains_stop_truth("close is below the hard stop", hard=True), "hard stop truth should detect below hard stop")
    require(contains_contradiction("Almost deployable / owner-approved but action state not live"), "contradictory softer state should be detected")
    require(not contains_contradiction("Do not touch / stop-breached"), "safe state should not be contradictory")
    alerts = build_risk_alerts([
        {"ticker": "JPM", "risk_state": "below_stop", "coverage_lane": "execution", "workflow_state": "DEPLOYED"},
        {"ticker": "RTX", "risk_state": "near_stop", "coverage_lane": "watch", "workflow_state": "WATCH"},
    ])
    require(len(alerts) == 2, "below-stop and near-stop risks should create visible alerts")
    require(alerts[0]["deployment_blocking"] is True, "execution-lane below-stop risk should be deployment-blocking")
    require(alerts[1]["severity"] == "warning", "near-stop risk should be warning-grade")
    print("board_canon_guardrail_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
