from pathlib import Path

from execution_board_governance_review import build_report


BOARD_TEXT = """<!-- THIN HUMAN SURFACE
Structured owner: state/finance/finance-canon.sqlite plus generated/read-only proof packets.
-->

# Execution Board - Human Policy and SQL Routes

Generated/read-only route note: monthly lightweight governance review plus event-driven updates only. This page is not the source for daily or market-window ticker freshness; current structured state lives in SQL/JSON proof routes.

This page preserves the canonical human path for execution discipline. It no longer hand-maintains ticker levels, routing states, price context, evidence currentness, or queue status. Those structured facts are SQL-generated/read-only outputs from the finance canon and proof packets.

Do not use this page as:
- a live ticker table

- `python scripts\\finance_sql_canon_access.py --write --validate`
- `python scripts\\finance_intelligence_state.py ticker <TICKER> --pretty`
- `python scripts\\trade_grade_os_freshness_cron_runner.py --write --validate`
- `python scripts\\full_intelligence_answer_parity.py --all --write --validate`
- `python scripts\\canonical_finance_data_plane_phase6_10.py --write --validate`
"""


def test_thin_execution_board_passes(tmp_path: Path) -> None:
    board = tmp_path / "Execution Board.md"
    board.write_text(BOARD_TEXT, encoding="utf-8")

    report = build_report(board)

    assert report["status"] == "ok"
    assert report["summary"]["monthly_governance_only"] is True
    assert report["authority_boundary"]["ticker_freshness_refresh_allowed"] is False


def test_equivalent_ticker_freshness_policy_wording_passes(tmp_path: Path) -> None:
    board = tmp_path / "Execution Board.md"
    board.write_text(
        BOARD_TEXT.replace(
            "This page is not the source for daily or market-window ticker freshness; "
            "current structured state lives in SQL/JSON proof routes.",
            "This page does not take daily or market-window ticker freshness updates; "
            "SQL/proof routes own structured current state.",
        ),
        encoding="utf-8",
    )

    report = build_report(board)

    assert report["status"] == "ok"


def test_missing_ticker_freshness_policy_blocks(tmp_path: Path) -> None:
    board = tmp_path / "Execution Board.md"
    board.write_text(
        BOARD_TEXT.replace(
            "This page is not the source for daily or market-window ticker freshness; "
            "current structured state lives in SQL/JSON proof routes.",
            "Current operational details are available elsewhere.",
        ),
        encoding="utf-8",
    )

    report = build_report(board)

    assert report["status"] == "blocked"
    assert any(
        item["name"] == "no_market_window_ticker_refresh"
        for item in report["critical_failures"]
    )


def test_missing_thin_marker_blocks(tmp_path: Path) -> None:
    board = tmp_path / "Execution Board.md"
    board.write_text(BOARD_TEXT.replace("THIN HUMAN SURFACE", ""), encoding="utf-8")

    report = build_report(board)

    assert report["status"] == "blocked"
    assert any(item["name"] == "thin_human_surface_marker" for item in report["critical_failures"])
