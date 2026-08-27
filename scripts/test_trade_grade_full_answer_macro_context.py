from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import trade_grade_full_answer_assembler as assembler  # noqa: E402

MACRO_METRICS = ROOT / "tmp" / "macro-metrics-current.json"


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def classifier_regressions(errors: list[str]) -> None:
    hot_headline = {
        "all_items": {"latest_mom_pct": 0.5},
        "core": {"latest_mom_pct": 0.2},
        "energy": {"latest_mom_pct": 3.9},
        "gasoline": {"latest_mom_pct": 7.0},
        "shelter": {"latest_mom_pct": 0.3},
    }
    expect(
        assembler.classify_inflation_posture(hot_headline) == "headline_hot_core_contained",
        "hot-headline fixture should distinguish contained core",
        errors,
    )
    expect(
        assembler.classify_cpi_driver(hot_headline) == "energy_gasoline_headline_pressure",
        "positive-gasoline fixture should identify headline pressure",
        errors,
    )

    negative_contained = {
        "all_items": {"latest_mom_pct": -0.4},
        "core": {"latest_mom_pct": 0.0},
        "energy": {"latest_mom_pct": -5.7},
        "gasoline": {"latest_mom_pct": -9.7},
        "shelter": {"latest_mom_pct": 0.1},
    }
    expect(
        assembler.classify_inflation_posture(negative_contained) == "contained",
        "negative-headline fixture should classify as contained",
        errors,
    )
    expect(
        assembler.classify_cpi_driver(negative_contained) == "mixed_or_contained",
        "negative energy/gasoline fixture must not claim headline pressure",
        errors,
    )


def main() -> int:
    errors: list[str] = []
    classifier_regressions(errors)
    packet, build_issues = assembler.build_full_answer("GOOG")
    expect(packet is not None, f"GOOG full answer could not be built: {build_issues}", errors)
    if packet is not None:
        expect(not build_issues, f"GOOG full answer build reported issues: {build_issues}", errors)
        failed_validation = [
            row
            for row in assembler.validate_full_answer(packet)
            if row.get("passed") is not True and row.get("severity") == "error"
        ]
        expect(not failed_validation, f"full answer validation checks failed: {failed_validation}", errors)
        expect(packet.get("validation", {}).get("status") == "ok", "full answer validation should be ok", errors)
        artifacts = packet.get("source_artifacts", {})
        expect(artifacts.get("macro_metrics") == "tmp/macro-metrics-current.json", "macro metrics artifact missing from source_artifacts", errors)
        expect(artifacts.get("macro_judgment") == "tmp/macro-judgment-draft.json", "macro judgment artifact missing from source_artifacts", errors)
        expect(artifacts.get("market_today_answer_packet") == "tmp/market-today-answer-packet.json", "market today answer packet missing from source_artifacts", errors)
        sections = packet.get("sections", {})
        catalyst = sections.get("catalyst_news_macro", {}).get("raw", {})
        risk = sections.get("risk_invalidation", {}).get("raw", {})
        macro = catalyst.get("macro_risk_context", {})
        risk_macro = risk.get("macro_risk_context", {})
        expect(macro.get("status") == "available", "macro risk context should be available", errors)
        expect(risk_macro.get("status") == "available", "risk section should carry macro context", errors)
        cpi = macro.get("cpi_release_detail", {})
        expect(MACRO_METRICS.exists(), "current macro metrics source artifact is missing", errors)
        source_cpi: dict = {}
        if MACRO_METRICS.exists():
            source_payload = json.loads(MACRO_METRICS.read_text(encoding="utf-8"))
            source_cpi = source_payload.get("summary", {}).get("cpi_release_detail", {})
        expect(bool(source_cpi), "current macro metrics CPI release detail is missing", errors)
        for key in ("status", "source", "source_url", "source_mode", "release_period", "release_date_text"):
            expect(cpi.get(key) == source_cpi.get(key), f"CPI metadata propagation drift: {key}", errors)
        for component in (
            "all_items",
            "core",
            "energy",
            "gasoline",
            "shelter",
            "rent",
            "owners_equivalent_rent",
        ):
            actual_row = cpi.get(component, {})
            expected_row = source_cpi.get(component, {})
            expect(isinstance(actual_row, dict), f"CPI component missing from full answer: {component}", errors)
            for field in ("latest_mom_pct", "previous_mom_pct", "yoy_pct"):
                expected_value = assembler.pct_value(expected_row.get(field))
                expect(
                    actual_row.get(field) == expected_value,
                    f"CPI component propagation drift: {component}.{field}",
                    errors,
                )
        expect(
            macro.get("inflation_posture") == assembler.classify_inflation_posture(source_cpi),
            "inflation posture must derive from the current CPI source artifact",
            errors,
        )
        expect(
            macro.get("cpi_driver") == assembler.classify_cpi_driver(source_cpi),
            "CPI driver must derive from the current CPI source artifact",
            errors,
        )
        tape = macro.get("market_tape_context", {})
        expect(tape.get("can_answer_full_market_close_recap_without_web") is True, "market tape context should carry full-recap readiness", errors)
        expect(tape.get("missing_for_web_free_full_recap") == [], "market tape context should have no missing full-recap fields", errors)
        symbols = {row.get("normalized_symbol") for row in tape.get("broad_index_daily_change_table", []) if isinstance(row, dict)}
        for symbol in ("SPX", "DOW", "NASDAQ_COMPOSITE", "RUSSELL_2000"):
            expect(symbol in symbols, f"market tape context missing {symbol}", errors)
        tape_rates = tape.get("rates", {})
        expect(tape_rates.get("treasury_2y_pct") is not None, "market tape context should carry 2Y Treasury", errors)
        expect(bool(tape.get("source_backed_market_driver_digest")), "market tape context should carry driver digest", errors)
        ticker_use = macro.get("ticker_use", {})
        for key in ("capital_deployment_approved", "trade_or_execution_approved", "owner_approval_inferred"):
            expect(ticker_use.get(key) is False, f"{key} must remain false", errors)
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("ok: WF85 full answers include review-only CPI macro risk context")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
