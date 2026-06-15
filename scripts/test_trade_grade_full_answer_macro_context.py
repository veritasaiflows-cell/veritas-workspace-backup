from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "trade_grade_full_answer_assembler.py"
ANSWER = ROOT / "tmp" / "trade-grade-full-answer" / "GOOG.json"
ROLLUP = ROOT / "tmp" / "trade-grade-full-answer-macro-context-test.json"


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    errors: list[str] = []
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--ticker", "GOOG", "--write", "--validate", "--out", str(ROLLUP)],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    expect(result.returncode == 0, f"full-answer assembler failed: {result.stdout} {result.stderr}", errors)
    expect(ANSWER.exists(), "GOOG full answer was not written", errors)
    if ANSWER.exists():
        packet = json.loads(ANSWER.read_text(encoding="utf-8"))
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
        expect(cpi.get("gasoline", {}).get("latest_mom_pct") == 7.0, "gasoline CPI detail missing", errors)
        expect(cpi.get("shelter", {}).get("latest_mom_pct") == 0.3, "shelter CPI detail missing", errors)
        expect(cpi.get("rent", {}).get("latest_mom_pct") == 0.4, "rent CPI detail missing", errors)
        expect(cpi.get("owners_equivalent_rent", {}).get("latest_mom_pct") == 0.3, "OER CPI detail missing", errors)
        expect(macro.get("inflation_posture") == "headline_hot_core_contained", "inflation posture should distinguish hot headline from contained core", errors)
        expect(macro.get("cpi_driver") == "energy_gasoline_headline_pressure", "CPI driver should identify energy/gasoline pressure", errors)
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
