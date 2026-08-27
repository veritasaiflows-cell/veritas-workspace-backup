from __future__ import annotations

import sys
from pathlib import Path
from tempfile import TemporaryDirectory

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import dashboard_core
import dashboard_validation
import board_canon_guardrail


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def test_dashboard_vault_note_aliases_are_canonical() -> None:
    require(
        dashboard_core.VAULT_NOTES["technical_entry"] == "03. Portfolio/Execution Board.md",
        "technical_entry alias must resolve to Execution Board",
    )
    require(
        dashboard_core.VAULT_NOTES["trigger_sheet"] == "03. Portfolio/Execution Board.md",
        "trigger_sheet alias must resolve to Execution Board",
    )
    require(
        dashboard_core.VAULT_NOTES["watchlist"] == "04. Research/Coverage and Watchlist.md",
        "watchlist alias must resolve to Coverage and Watchlist",
    )
    require(
        dashboard_core.VAULT_NOTES["coverage_universe"] == "04. Research/Coverage and Watchlist.md",
        "coverage_universe alias must resolve to Coverage and Watchlist",
    )


def test_guardrail_note_surfaces_are_canonical() -> None:
    require(board_canon_guardrail.TECHNICAL_NOTE == board_canon_guardrail.EXECUTION_NOTE, "technical note must be Execution Board")
    require(board_canon_guardrail.TRIGGER_NOTE == board_canon_guardrail.EXECUTION_NOTE, "trigger note must be Execution Board")
    require(
        board_canon_guardrail.WATCHLIST_NOTE.name == "Coverage and Watchlist.md",
        "watchlist note must be Coverage and Watchlist",
    )


def test_coverage_watchlist_current_header_parses() -> None:
    note = """# Coverage and Watchlist

## Active machine-tracked universe

| Ticker | Sector | Coverage Tier | Thesis pointer | Deployment/action pointer | Source lineage |
|---|---|---|---|---|---|
| JPM | Financials | Core candidate | thesis | [[03. Portfolio/Execution Board#JPM|Execution/action state]] | Execution lineage |
"""
    with TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "Coverage and Watchlist.md"
        path.write_text(note, encoding="utf-8")
        original = dashboard_validation.COVERAGE_WATCHLIST_PATH
        try:
            dashboard_validation.COVERAGE_WATCHLIST_PATH = path
            rows = dashboard_validation._parse_watchlist_rows()
        finally:
            dashboard_validation.COVERAGE_WATCHLIST_PATH = original

    require("JPM" in rows, "current Coverage and Watchlist table header should parse JPM row")
    require(rows["JPM"]["source_lineage"] == "Execution lineage", "source lineage column should be retained")


def test_coverage_watchlist_missing_row_accepted_when_sql_first_thin_contract_allowed() -> None:
    thin_contract = {
        "sql_first_thin_board_detected": True,
        "sql_first_thin_board_allowed": True,
    }
    require(
        not dashboard_validation._coverage_watchlist_row_warning_required("execution", None, thin_contract),
        "execution-lane row warnings must be suppressed when SQL-first Coverage and Watchlist contract is accepted",
    )


def test_coverage_watchlist_missing_row_warns_when_sql_first_thin_contract_blocked() -> None:
    thin_contract = {
        "sql_first_thin_board_detected": True,
        "sql_first_thin_board_allowed": False,
    }
    require(
        dashboard_validation._coverage_watchlist_row_warning_required("execution", None, thin_contract),
        "execution-lane row warnings must remain when SQL-first Coverage and Watchlist contract is blocked",
    )


def test_coverage_watchlist_missing_row_warns_when_legacy_contract_absent() -> None:
    thin_contract = {
        "sql_first_thin_board_detected": False,
        "sql_first_thin_board_allowed": False,
    }
    require(
        dashboard_validation._coverage_watchlist_row_warning_required("execution", None, thin_contract),
        "execution-lane row warnings must remain when Coverage and Watchlist is not an accepted thin board",
    )


def test_suspended_legacy_weight_is_info_when_accounting_balances() -> None:
    sources = {
        "policy": {},
        "market": {},
        "credit": {},
        "breadth": {},
        "technical": {},
        "deployment": {"records": [], "summary": {}},
        "earnings": {},
        "portfolio": {
            "portfolio": {
                "cash": 10,
                "core": [
                    {"ticker": "AAA", "weight": 80},
                    {
                        "ticker": "LEGACY",
                        "weight": 0,
                        "weight_status": "suspended legacy model weight",
                        "suspended_legacy_weight": 10,
                    },
                ],
                "tactical": [],
                "speculative": [],
            },
        },
    }
    validation = dashboard_validation.build_validation(
        sources=sources,
        source_status={},
        technical_rows=[],
        sector_weights={},
        last_trade_dt=dashboard_validation.datetime.now(),
    )
    suspended = [
        item
        for item in validation["warnings"]
        if item.get("code") == "portfolio_suspended_weight_gap"
    ]
    require(len(suspended) == 1, "suspended legacy accounting should remain visible")
    require(suspended[0]["severity"] == "info", "balanced suspended legacy weight must be info, not warning")
    require(validation["summary"]["warning"] == 0, "balanced suspended legacy weight must not create warning count")


def main() -> int:
    test_dashboard_vault_note_aliases_are_canonical()
    test_guardrail_note_surfaces_are_canonical()
    test_coverage_watchlist_current_header_parses()
    test_coverage_watchlist_missing_row_accepted_when_sql_first_thin_contract_allowed()
    test_coverage_watchlist_missing_row_warns_when_sql_first_thin_contract_blocked()
    test_coverage_watchlist_missing_row_warns_when_legacy_contract_absent()
    test_suspended_legacy_weight_is_info_when_accounting_balances()
    print("dashboard_canon_surfaces_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
