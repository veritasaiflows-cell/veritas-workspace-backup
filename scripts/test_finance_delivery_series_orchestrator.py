#!/usr/bin/env python3
"""Direct checks for the recurring finance delivery series builder."""
from __future__ import annotations

from pathlib import Path

import finance_delivery_series_orchestrator as series


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    errors: list[str] = []
    payload = series.build_payload("all")
    validation = series.validate_payload(payload)

    expect(payload.get("schema") == series.SCHEMA, "schema mismatch", errors)
    expect(payload.get("mode") == "all", "mode should be all", errors)
    expect(validation.get("status") in {"ok", "warning"}, f"validation blocked: {validation}", errors)

    boundary = series.as_dict(payload.get("authority_boundary"))
    expect(boundary.get("review_only") is True, "review_only must be true", errors)
    expect(boundary.get("internal_delivery_only") is True, "internal_delivery_only must be true", errors)
    for key in series.REQUIRED_FALSE_AUTHORITY:
        expect(boundary.get(key) is False, f"authority flag must be false: {key}", errors)

    cadence = [row.get("id") for row in series.as_list(payload.get("cadence")) if isinstance(row, dict)]
    for deliverable_id in series.DELIVERABLES:
        expect(deliverable_id in cadence, f"missing cadence row: {deliverable_id}", errors)

    rows = [row for row in series.as_list(payload.get("fundamentals_bo_yoy_finance")) if isinstance(row, dict)]
    expect(bool(rows), "missing fundamentals/BO/YoY rows", errors)
    required_columns = {"ticker", "fundamentals", "business_outlook", "eps_yoy_pct", "revenue_yoy_pct"}
    expect(required_columns.issubset(rows[0]), f"fundamentals row missing columns: {rows[0].keys()}", errors)

    scenarios = [row for row in series.as_list(payload.get("scenario_outlook")) if isinstance(row, dict)]
    expect({row.get("scenario") for row in scenarios} == {"Base case", "Bull case", "Bear case"}, "scenario outlook must have base/bull/bear", errors)

    render_payload = dict(payload)
    out_dir = series.OUT_DIR
    results = series.write_outputs(render_payload, ["daily_market_read"], html_only=True)
    html_path = Path(series.ROOT / results["daily_market_read"]["html"])
    expect(html_path.exists() and html_path.stat().st_size > 0, "daily html render missing", errors)
    expect(results["daily_market_read"]["pdf_result"]["status"] == "skipped_html_only", "html-only render should skip pdf", errors)

    if errors:
        print("status=error")
        for error in errors:
            print(f"ERROR {error}")
        return 1
    print(f"status=ok fundamentals_rows={len(rows)} scenarios={len(scenarios)} out_dir={out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
