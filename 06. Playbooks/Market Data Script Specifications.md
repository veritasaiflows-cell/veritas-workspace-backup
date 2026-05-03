# Market Data Script Specifications

## Purpose

This note defines the implementation contract for the next three market-data scripts:
- `scripts/policy_expectations_refresh.py`
- `scripts/credit_spread_refresh.py`
- `scripts/breadth_refresh.py`

The goal is to make them production-grade inputs to the finance OS rather than one-off data pulls.

## Shared artifact contract

Each script should write one dedicated JSON artifact and follow the same top-level structure already used by the current machine layer.

```json
{
  "generated_at_utc": "ISO-8601",
  "status": "ok | partial | manual | error",
  "stale_after_hours": 24,
  "expected_update_window": "human-readable refresh rule",
  "last_trading_day": "YYYY-MM-DD or null",
  "source_last_trading_day": {},
  "freshness_notes": [],
  "warnings": [],
  "data": {}
}
```

### Status meanings
- `ok` = all required fields populated from intended sources
- `partial` = usable but some fields missing or on fallback sources
- `manual` = artifact exists but at least one required field depends on manual confirmation or manual entry
- `error` = artifact could not be trusted for downstream decisions

### Shared rules
- never silently fill required fields with fake defaults
- every source failure should produce a warning
- every manual dependency should be explicit in both `status` and `warnings`
- downstream consumers must degrade confidence when status is not `ok`

---

## 1. `policy_expectations_refresh.py`

### Goal
Create a first-class policy-expectations artifact so macro commentary no longer hand-waves the Fed path.

### Output
- `tmp/policy-expectations.json`

### Suggested stale threshold
- `stale_after_hours: 24`

### Primary source posture
- primary: CME FedWatch-style implied move probabilities when reliably obtainable
- fallback: explicit manual status

### Suggested top-level shape
```json
{
  "generated_at_utc": "...",
  "status": "ok",
  "stale_after_hours": 24,
  "expected_update_window": "Refresh daily during active market sessions and before macro-sensitive weekly outputs. Refresh again on scheduled FOMC decision days after the announcement.",
  "last_trading_day": "2026-04-29",
  "source_last_trading_day": {
    "policy_expectations": "2026-04-29"
  },
  "freshness_notes": [],
  "warnings": [],
  "data": {
    "source_label": "CME FedWatch",
    "source_mode": "primary | fallback | manual",
    "current_target_range": {
      "low": 3.50,
      "high": 3.75,
      "as_of": "2026-04-29",
      "confirmed": true
    },
    "next_fomc": {
      "meeting_date": "2026-06-17",
      "days_until": 49,
      "distribution": [
        { "outcome": "hold", "probability": 0.64 },
        { "outcome": "cut_25bp", "probability": 0.31 },
        { "outcome": "hike_25bp", "probability": 0.05 }
      ],
      "most_likely_outcome": "hold"
    },
    "next_two_meetings": [
      {
        "meeting_date": "2026-06-17",
        "most_likely_outcome": "hold",
        "cut_probability": 0.31,
        "hold_probability": 0.64,
        "hike_probability": 0.05
      }
    ],
    "manual_dependencies": [],
    "notes": []
  }
}
```

### Required fields
- `data.source_label`
- `data.source_mode`
- `data.current_target_range.low`
- `data.current_target_range.high`
- `data.current_target_range.as_of`
- `data.next_fomc.meeting_date`
- `data.next_fomc.distribution`
- `data.next_fomc.most_likely_outcome`

### Failure behavior
- if probabilities fail but current target range is known, set `status="partial"` or `manual` and write a clear warning
- if both current range and meeting expectations are unavailable, set `status="error"`

### Downstream integration
- `market_state_refresh.py` should stop owning hardcoded policy logic and instead ingest this artifact
- `weekly_macro_snapshot.py` and `weekly_intelligence_brief.py` should cite policy state from this file
- `validate_dashboard_state.py` should flag missing, stale, partial, or manual policy state

### Validator warnings to add
- `policy_expectations_missing`
- `policy_expectations_stale`
- `policy_expectations_manual_dependency`
- `policy_expectations_partial`

---

## 2. `credit_spread_refresh.py`

### Goal
Add a credit-stress layer so regime and deployment calls are not overly equity-price-centric.

### Output
- `tmp/credit-spreads.json`

### Suggested stale threshold
- `stale_after_hours: 36`

### Primary source posture
- primary: FRED / ICE BofA OAS series
  - `BAMLC0A0CM` for investment-grade OAS
  - `BAMLH0A0HYM2` for high-yield OAS
- fallback proxies: HYG, JNK, LQD, and HYG/LQD relative behavior

### Suggested top-level shape
```json
{
  "generated_at_utc": "...",
  "status": "ok",
  "stale_after_hours": 36,
  "expected_update_window": "Refresh after the close for next-session regime work and before weekly macro outputs.",
  "last_trading_day": "2026-04-29",
  "source_last_trading_day": {
    "ig_oas": "2026-04-29",
    "hy_oas": "2026-04-29"
  },
  "freshness_notes": [],
  "warnings": [],
  "data": {
    "source_label": "FRED ICE BofA OAS",
    "source_mode": "primary | fallback | mixed",
    "investment_grade_oas": {
      "value": 1.34,
      "unit": "percent",
      "series": "BAMLC0A0CM",
      "as_of": "2026-04-29"
    },
    "high_yield_oas": {
      "value": 3.92,
      "unit": "percent",
      "series": "BAMLH0A0HYM2",
      "as_of": "2026-04-29"
    },
    "hy_minus_ig_spread": 2.58,
    "direction": {
      "ig_5d": "tightening | widening | flat",
      "ig_20d": "tightening | widening | flat",
      "hy_5d": "tightening | widening | flat",
      "hy_20d": "tightening | widening | flat"
    },
    "stress_regime": "benign | watch | stressed | severe",
    "fallback_proxies": [],
    "notes": []
  }
}
```

### Required fields
- IG OAS value and date
- HY OAS value and date
- HY minus IG spread
- 5-day and 20-day direction labels
- stress regime label

### Failure behavior
- if one spread is present and the other missing, set `status="partial"`
- if direct OAS fails but proxy basket works, set `source_mode="fallback"` and `status="partial"`
- if no trustworthy read is available, set `status="error"`

### Downstream integration
- `market_state_refresh.py` should ingest this artifact into macro risk context
- `regime_scoring_refresh.py` should use credit state in regime-fit adjustments
- `validate_dashboard_state.py` should downgrade trust when credit state is missing, stale, or partial

### Validator warnings to add
- `credit_spreads_missing`
- `credit_spreads_stale`
- `credit_spreads_partial`
- `credit_spreads_fallback_proxy_only`

---

## 3. `breadth_refresh.py`

### Goal
Measure participation so index-level strength is not mistaken for healthy internal market structure.

### Output
- `tmp/breadth-state.json`

### Suggested stale threshold
- `stale_after_hours: 24`

### Source posture
Two-tier model.

#### Tier 1: stable proxy breadth
- RSP vs SPY
- sector participation count using the tracked sector ETF layer
- QQQ vs equal-weight tech proxy when practical
- relative-strength checks on leadership cohorts

#### Tier 2: deeper breadth
- % above 50DMA
- % above 200DMA
- new highs / new lows
- advance / decline style breadth

Start with Tier 1. Add Tier 2 only if source stability is good enough.

### Suggested top-level shape
```json
{
  "generated_at_utc": "...",
  "status": "ok",
  "stale_after_hours": 24,
  "expected_update_window": "Refresh each weekday before deployment work and after the close for next-session readiness.",
  "last_trading_day": "2026-04-29",
  "source_last_trading_day": {
    "rsp": "2026-04-29",
    "spy": "2026-04-29",
    "sector_participation": "2026-04-29"
  },
  "freshness_notes": [],
  "warnings": [],
  "data": {
    "source_mode": "tier1 | tier2 | mixed",
    "equal_weight_vs_cap_weight": {
      "rsp_close": 210.44,
      "spy_close": 718.21,
      "rsp_spy_ratio": 0.2930,
      "ratio_20d_direction": "improving | weakening | flat",
      "ratio_50d_direction": "improving | weakening | flat"
    },
    "sector_participation": {
      "sectors_above_50dma": 8,
      "sectors_above_200dma": 10,
      "leadership_breadth_label": "broad | mixed | narrow"
    },
    "major_index_breadth": {
      "spx_participation_score": 72,
      "nasdaq_participation_score": 66,
      "breadth_regime": "healthy | mixed | narrow | deteriorating"
    },
    "tier2_metrics": {
      "spx_pct_above_50dma": null,
      "spx_pct_above_200dma": null,
      "new_highs": null,
      "new_lows": null
    },
    "notes": []
  }
}
```

### Required fields
- equal-weight vs cap-weight ratio block
- sector participation block
- breadth regime label
- participation score

### Failure behavior
- if only Tier 1 is available, `status` may still be `ok` if all Tier 1 requirements are met
- if some Tier 1 fields fail, set `status="partial"`
- if no coherent participation read is available, set `status="error"`

### Downstream integration
- `market_state_refresh.py` should ingest breadth state
- `regime_scoring_refresh.py` should use breadth regime in regime-fit or caution logic
- `validate_dashboard_state.py` should flag missing or stale breadth because deployment trust should not ignore participation quality

### Validator warnings to add
- `breadth_state_missing`
- `breadth_state_stale`
- `breadth_state_partial`
- `breadth_state_narrow_participation`

---

## Chain placement rules

These scripts should become part of `run_finance_refresh_chain.py`, but only after:
1. each script runs cleanly on its own
2. each artifact has freshness and warning logic
3. `market_state_refresh.py` can consume the artifact
4. `validate_dashboard_state.py` knows how to downgrade trust when it is missing or weak

### Recommended placement

#### Morning chain
- include: `breadth_refresh.py`
- consume fresh prior outputs from:
  - `policy-expectations.json`
  - `credit-spreads.json`
- conditional add: `policy_expectations_refresh.py` on FOMC decision days or when the policy artifact is stale or missing
- do **not** run credit by default in the morning

#### Post-close chain
- include:
  - `policy_expectations_refresh.py`
  - `credit_spread_refresh.py`
  - `breadth_refresh.py`
- reason: this is the main next-session rebuild and should own full regime readiness

#### Sunday chain
- include:
  - `policy_expectations_refresh.py`
  - `credit_spread_refresh.py`
  - `breadth_refresh.py`
- reason: weekly priming should refresh the full regime stack

#### Post-earnings chain
- default: do **not** include these scripts
- exception: only add them conditionally if the post-earnings run is explicitly serving as a wider regime refresh, not just an earnings-closure pass

---

## Exact runner insertion order

### Morning
1. `market_state_refresh.py`
2. `technical_refresh.py`
3. `regime_scoring_refresh.py`
4. `breadth_refresh.py`
5. `band_refresh.py`
6. `entry_band_fetch.py --all-tracked --html`
7. `generate_entry_band_status.py`
8. `deployment_check.py`
9. `trigger_sheet_refresh.py`
10. `test_dashboard_acceptance.py`
11. `generate_dashboard.py`
12. `validate_dashboard_state.py --write`
13. `premarket_snapshot.py`

### Post-close
1. `earnings_calendar_enrichment.py`
2. `policy_expectations_refresh.py`
3. `credit_spread_refresh.py`
4. `market_state_refresh.py`
5. `technical_refresh.py`
6. `breadth_refresh.py`
7. `regime_scoring_refresh.py`
8. `band_refresh.py`
9. `entry_band_fetch.py --all-tracked --html`
10. `generate_entry_band_status.py`
11. `deployment_check.py`
12. `trigger_sheet_refresh.py`
13. `post_earnings_prep.py`
14. `post_earnings_note_targets.py`
15. `test_dashboard_acceptance.py`
16. `generate_dashboard.py`
17. `validate_dashboard_state.py --write`
18. `postmarket_snapshot.py`
19. `daily_executive_brief.py`

### Sunday
1. `earnings_calendar_enrichment.py`
2. `policy_expectations_refresh.py`
3. `credit_spread_refresh.py`
4. `market_state_refresh.py`
5. `technical_refresh.py`
6. `breadth_refresh.py`
7. `regime_scoring_refresh.py`
8. `weekly_review_skeleton.py`
9. `band_refresh.py`
10. `entry_band_fetch.py --all-tracked --html`
11. `generate_entry_band_status.py`
12. `deployment_check.py`
13. `trigger_sheet_refresh.py`
14. `post_earnings_prep.py`
15. `post_earnings_note_targets.py`
16. `call_log_sync.py`
17. `test_dashboard_acceptance.py`
18. `generate_dashboard.py`
19. `validate_dashboard_state.py --write`
20. `weekly_macro_snapshot.py`
21. `weekly_intelligence_brief.py`
22. `postmarket_snapshot.py`
23. `daily_executive_brief.py`

---

## Validator integration rule

`validate_dashboard_state.py` should treat these new artifacts the same way it already treats weak market and earnings states:
- missing = warning at minimum
- stale = warning
- partial/manual = warning with confidence downgrade
- contradictory = warning or critical depending on impact

Suggested summary rule:
- if policy or breadth is missing/stale/partial, overall trust cannot be better than `warning`
- if both policy and credit are missing during macro-sensitive sessions, macro confidence should be explicitly degraded
- if breadth is narrow and index strength remains strong, the dashboard should surface that contradiction rather than smoothing it away

## Recommendation

Build the scripts in this order:
1. `policy_expectations_refresh.py`
2. `credit_spread_refresh.py`
3. `breadth_refresh.py`

Then wire them into:
- `market_state_refresh.py`
- `regime_scoring_refresh.py`
- `validate_dashboard_state.py`
- `run_finance_refresh_chain.py`

Only after those integrations exist should cron automation be built around them.
