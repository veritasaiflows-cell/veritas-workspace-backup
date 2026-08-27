#!/usr/bin/env python3
"""Regression tests for BLS CPI release-detail parsing."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import macro_metrics_ingest as ingest  # noqa: E402


SAMPLE_HTML = """
<html><body>
<p>Transmission is embargoed until 8:30 a.m. (ET) Wednesday, June 10, 2026</p>
<h1>CONSUMER PRICE INDEX - MAY 2026</h1>
<p>The index for owners' equivalent rent rose 0.3 percent in May and the index for rent increased 0.4 percent.
The lodging away from home index also rose 0.4 percent over the month.</p>
<table>
<tr><th>Expenditure category</th><th>Unadjusted 12-mo</th><th>Dec.</th><th>Jan.</th><th>Feb.</th><th>Mar.</th><th>Apr.</th><th>May</th><th>12-mo.</th></tr>
<tr><th>All items</th><td>-</td><td>0.3</td><td>0.2</td><td>0.3</td><td>0.9</td><td>0.6</td><td>0.5</td><td>4.2</td></tr>
<tr><th>Food</th><td>-</td><td>0.7</td><td>0.2</td><td>0.4</td><td>0.0</td><td>0.5</td><td>0.2</td><td>3.1</td></tr>
<tr><th>Energy</th><td>-</td><td>0.3</td><td>-1.5</td><td>0.6</td><td>10.9</td><td>3.8</td><td>3.9</td><td>23.5</td></tr>
<tr><th>Gasoline (all types)</th><td>2.7</td><td>-0.3</td><td>-3.2</td><td>0.8</td><td>21.2</td><td>5.4</td><td>7.0</td><td>40.5</td></tr>
<tr><th>All items less food and energy</th><td>-</td><td>0.2</td><td>0.3</td><td>0.2</td><td>0.2</td><td>0.4</td><td>0.2</td><td>2.9</td></tr>
<tr><th>Commodities less food and energy commodities</th><td>-</td><td>0.0</td><td>0.0</td><td>0.1</td><td>0.1</td><td>0.0</td><td>-0.1</td><td>1.1</td></tr>
<tr><th>Services less energy services</th><td>-</td><td>0.3</td><td>0.4</td><td>0.3</td><td>0.2</td><td>0.5</td><td>0.3</td><td>3.4</td></tr>
<tr><th>Shelter</th><td>-</td><td>0.4</td><td>0.2</td><td>0.2</td><td>0.3</td><td>0.6</td><td>0.3</td><td>3.4</td></tr>
</table>
</body></html>
"""

FALLING_JUNE_HTML = (
    SAMPLE_HTML
    .replace("CONSUMER PRICE INDEX - MAY 2026", "CONSUMER PRICE INDEX - JUNE 2026")
    .replace(
        "owners' equivalent rent rose 0.3 percent in May",
        "owners' equivalent rent fell 0.2 percent in June",
    )
    .replace("index for rent increased 0.4 percent", "index for rent declined 0.1 percent")
    .replace(
        "lodging away from home index also rose 0.4 percent",
        "lodging away from home index fell 2.3 percent",
    )
)


def main() -> int:
    parsed = ingest.parse_bls_cpi_release_html(SAMPLE_HTML, source_url="https://example.test/cpi")
    assert parsed["status"] == "ok", parsed
    assert parsed["release_period"] == "May 2026"
    by_key = {row["key"]: row for row in parsed["components"] + parsed["narrative_components"]}
    assert by_key["all_items"]["latest_mom_pct"] == 0.5
    assert by_key["all_items"]["yoy_pct"] == 4.2
    assert by_key["energy"]["latest_mom_pct"] == 3.9
    assert by_key["gasoline_all_types"]["yoy_pct"] == 40.5
    assert by_key["shelter"]["latest_mom_pct"] == 0.3
    assert by_key["rent_of_primary_residence"]["latest_mom_pct"] == 0.4
    assert by_key["owners_equivalent_rent"]["latest_mom_pct"] == 0.3
    summary = ingest.summarize_cpi_release_detail(parsed)
    assert summary["gasoline"]["latest_mom_pct"] == 7.0
    assert summary["rent"]["latest_mom_pct"] == 0.4

    falling = ingest.parse_bls_cpi_release_html(FALLING_JUNE_HTML, source_url="https://example.test/cpi")
    assert falling["status"] == "ok", falling
    assert falling["release_period"] == "June 2026"
    falling_by_key = {
        row["key"]: row
        for row in falling["components"] + falling["narrative_components"]
    }
    assert falling_by_key["owners_equivalent_rent"]["latest_mom_pct"] == -0.2
    assert falling_by_key["rent_of_primary_residence"]["latest_mom_pct"] == -0.1
    assert falling_by_key["lodging_away_from_home"]["latest_mom_pct"] == -2.3
    falling_summary = ingest.summarize_cpi_release_detail(falling)
    assert falling_summary["owners_equivalent_rent"]["latest_mom_pct"] == -0.2
    assert falling_summary["rent"]["latest_mom_pct"] == -0.1

    payload = {
        "schema": ingest.SCHEMA,
        "generated_at_utc": "2026-06-10T14:18:53Z",
        "status": "ok",
        "authority_boundary": ingest.AUTHORITY_BOUNDARY,
        "metrics": [
            {
                "key": "cpi_headline",
                "name": "CPI headline",
                "agency": "BLS",
                "category": "inflation",
                "status": "ok",
                "source": "FRED",
                "source_url": "https://fred.example/cpi",
                "source_mode": "live_fetch",
                "latest_date": "2026-05-01",
                "latest_value": 333.979,
                "previous_date": "2026-04-01",
                "previous_value": 332.407,
                "delta": 1.572,
                "mom_pct": 0.473,
                "yoy_pct": 4.167,
                "cache_fallback_used": False,
            }
        ],
        "cpi_release_detail": parsed,
    }
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "macro.sqlite"
        ingest.write_sqlite(payload, db_path)
        import sqlite3

        con = sqlite3.connect(db_path)
        try:
            rows = con.execute(
                "SELECT key, latest_mom_pct, yoy_pct FROM cpi_release_components WHERE key IN ('gasoline_all_types', 'shelter', 'owners_equivalent_rent') ORDER BY key"
            ).fetchall()
        finally:
            con.close()
        assert rows == [
            ("gasoline_all_types", 7.0, 40.5),
            ("owners_equivalent_rent", 0.3, None),
            ("shelter", 0.3, 3.4),
        ]
    print("ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
