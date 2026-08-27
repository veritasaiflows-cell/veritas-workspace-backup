from __future__ import annotations

from pathlib import Path

from md_finance_structured_drift_lint import build_report, scan_text


def test_scan_flags_unmarked_structured_finance_fact() -> None:
    rows = scan_text(Path("03. Portfolio/Execution Board.md"), "NVDA Tier A entry band 190-210 stop 180 fresh source-open ok")
    assert rows
    assert rows[0]["requires_thinning_or_marker"] is True
    assert "reference_band" in rows[0]["field_families"]
    assert "stop_or_invalidation" in rows[0]["field_families"]
    assert "tier_routing" in rows[0]["field_families"]


def test_scan_accepts_generated_or_historical_marker() -> None:
    generated = scan_text(Path("03. Portfolio/Execution Board.md"), "SQL-generated entry band export for NVDA")
    historical = scan_text(Path("03. Portfolio/Execution Board.md"), "Historical snapshot: NVDA stop was reviewed")
    assert generated[0]["requires_thinning_or_marker"] is False
    assert historical[0]["requires_thinning_or_marker"] is False


def test_build_report_handles_missing_target_as_warning(tmp_path: Path) -> None:
    reconciliation = tmp_path / "sql-markdown-reconciliation.json"
    reconciliation.write_text('{"rows": []}', encoding="utf-8")
    report = build_report([tmp_path / "missing.md"], reconciliation)
    assert report["validation"]["status"] == "ok"
    assert report["validation"]["warnings"]
    assert report["summary"]["finding_count"] == 0


def main() -> int:
    import tempfile

    test_scan_flags_unmarked_structured_finance_fact()
    test_scan_accepts_generated_or_historical_marker()
    with tempfile.TemporaryDirectory() as tmp:
        test_build_report_handles_missing_target_as_warning(Path(tmp))
    print("ok: md finance structured drift lint")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
