# Tier B and Tier C Opportunity Discovery Code Review

Generated: 2026-06-23 17:04 MST / 2026-06-24 00:04 UTC  
Scope: WF78 automatic tier routing, opportunity discovery from Tier C and Tier B, and prevention of false A-READY/readiness claims.  
Authority: review-only. This audit does not approve capital deployment, paper/live execution, portfolio/canon mutation, customer output, or owner approval inference.

## Executive Summary

The current WF78 routing stack is good at **non-capital opportunity discovery**: it can elevate Tier C and Tier B tickers into Tier A quickly when thesis, price/band, or momentum evidence changes. The safety outcome today is correct — the six latest fast-track promotions landed in `A-CHALLENGED`, not `A-READY` — and the depth/coverage gate reports `decision_grade_allowed_count=0`.

The code still has three classes of risk that can mislead users or downstream consumers:

1. **A-READY can be preserved by stale promotion packets.** `wf78_auto_tier_router.py` reads `tmp/wf78-tier-a-final-promotion-packet.json` (generated 2026-06-05) and sets `GOOG`, `NVDA`, and `VRT` to `A-READY` based on quote timestamps from the same date. There is no TTL check on the packet or its embedded quote before the router trusts it.
2. **Production-answer routing uses state labels as a proxy for readiness.** `finance_sql_canon_access.py` treats `auto_tier='Tier A' AND auto_state='A-READY'` as the production answer set. It does not require the current coverage/depth gate to allow decision-grade claims.
3. **Router cohort and SQL/data-plane cohort are not reconciled.** The live router has 25 Tier A tickers; the coverage gate only sees 19 in the SQL/data-plane Tier A cohort. The six newest fast-track names (`PAVE`, `VAW`, `VXUS`, `WMB`, `XLF`, `XLI`) are not yet validated by the same surface that claims to certify Tier A depth.

This audit gives specific, file-level recommendations to fix these issues while keeping the useful fast-track behavior intact.

## What the System Does Well Today

- **Fast-track from Tier C/B to Tier A is real and bounded.** `wf78_auto_tier_router.py` can promote on production adjudication, competitive gate, or confidence convergence, but it lands new names in `A-CHALLENGED` when data is incomplete.
- **Tier-weighted freshness resolver correctly calibrates required depth.** `wf78_tier_weighted_freshness_resolver.py` assigns `thin_monitor` to Tier C, `promotion_repair` to Tier B, and `decision_repair` to Tier A. This prevents over-repairing monitor names.
- **Tier A coverage/depth gate blocks decision-grade claims.** `tier_a_trade_grade_coverage_gate.py` reports `decision_grade_allowed_count=0` when blockers exist. That is the right posture.
- **Append-only event ledger gives durable history.** `wf78_tier_routing_event_ledger.py` writes deduplicated JSONL events with source hashes, which is stronger than a single rolling `tmp` file.
- **Authority flags are consistently false.** Every relevant script sets `capital_deployment_approved`, `trade_or_execution_approved`, `paper_or_live_execution_allowed`, and `owner_approval_inferred` to `False`.

## Code-Level Findings and Recommendations

### F1 - Stale Tier A Final Promotion Packet Can Preserve A-READY

**File:** `scripts/wf78_auto_tier_router.py`  
**Function:** `route_entry`, `band_status_to_tier_a_state`, `build_report`  
**Issue:** The router trusts `tmp/wf78-tier-a-final-promotion-packet.json` without checking the packet age or the embedded quote timestamp. The current packet is from 2026-06-05, but `GOOG`, `NVDA`, and `VRT` are still `A-READY`.

Evidence:

```json
{
  "generated_at_utc": "2026-06-05T19:52:03Z",
  "rows": [
    {
      "ticker": "GOOG",
      "quote": {
        "quote_time_utc": "2026-06-05T16:50:46Z"
      },
      "current_band_status": "IN_BAND"
    }
  ]
}
```

**Recommendation:** Add a freshness TTL gate inside the router before any Tier A packet row can produce `A-READY`.

- Define `TIER_A_PACKET_MAX_AGE_HOURS = 24` and `TIER_A_QUOTE_MAX_AGE_HOURS = 8` (market open) or 24 (post-close).
- In `route_entry`, when `ticker in tier_a_rows`, first call a new helper `is_tier_a_packet_row_fresh(packet_row)`.
- If the packet row or its quote is stale:
  - Route the ticker to `A-WATCH` if it is still in the universe and has a current card.
  - Route to `A-CHALLENGED` if the card/quote is missing or stale.
  - Add a `route_reason` suffix such as `tier_a_packet_stale_rerouted_to_watch`.
- Do not delete or mutate the stale packet; just demote its effect in the router output.

**Acceptance test:**

- Run the router with the current 2026-06-05 packet. `GOOG`, `NVDA`, `VRT` must not be `A-READY`.
- Replace the packet with a synthetic fresh packet (quote within TTL). The same tickers can be `A-READY` only if all other gates pass.

### F2 - Production Answer Eligibility Does Not Require Current Proof

**File:** `scripts/finance_sql_canon_access.py`  
**Issue:** The SQL/JSON canon access layer uses `auto_tier='Tier A' AND auto_state='A-READY'` as the production answer definition. The coverage gate currently says `decision_grade_allowed_count=0`, so the production answer set should be empty or explicitly labeled as review-only.

**Recommendation:** Create a validated production-eligibility view that joins routing state with current proof surfaces.

- Add a helper `load_current_proof_state()` that reads:
  - `tmp/wf78-tier-weighted-freshness-resolution.json`
  - `tmp/tier-a-trade-grade-coverage-gate.json`
  - `tmp/wf78-tier-a-confidence-gate.json`
- Define `production_answer_eligible(ticker, row, proof)` requiring:
  - `auto_state == 'A-READY'`
  - No critical data conflicts in confidence gate
  - `decision_grade_allowed_count > 0` from coverage gate for the current run
  - Quote/source freshness within TTL
  - All authority false flags preserved
- Keep the legacy `auto_tier='Tier A' AND auto_state='A-READY'` lookup but rename it `legacy_production_answer_compatibility_view` and add a warning field.
- Expose a new `validated_production_answer_tickers()` function that consumers should prefer.

**Acceptance test:**

- When `tier_a_trade_grade_coverage_gate.py` reports `decision_grade_allowed_count=0`, the validated production answer count must also be 0.
- When the coverage gate is green and freshness is current, the validated count can match the number of truly fresh A-READY rows.

### F3 - Router Tier A Cohort and Coverage Gate Cohort Diverge

**File:** `scripts/tier_a_trade_grade_coverage_gate.py`  
**Function:** `load_tier_rows`, `build_report`, `validate_report`  
**Issue:** The coverage gate reads Tier A rows from `finance-canon.sqlite` and `canonical-finance-data-plane.sqlite`. It does not compare against the live `wf78-auto-tier-routing.json` cohort. Current mismatch: router has 25 Tier A tickers; SQL/data-plane gate sees 19.

**Recommendation:** Add a live-router cohort reconciliation check.

- Load `tmp/wf78-auto-tier-routing.json` in the coverage gate.
- Compute `router_only = router_tier_a - sql_tier_a` and `sql_only = sql_tier_a - router_tier_a`.
- Emit a new summary field:

```json
{
  "tier_definition_aligned": false,
  "router_tier_a_count": 25,
  "finance_tier_a_count": 19,
  "data_plane_tier_a_count": 25,
  "router_only_tickers": ["PAVE", "VAW", "VXUS", "WMB", "XLF", "XLI"],
  "sql_only_tickers": []
}
```

- If `router_only_tickers` is non-empty, set `tier_definition_aligned=false` and add a warning or blocker depending on consumer type.
- For the coverage gate specifically, treat a non-empty `router_only` as a depth blocker for decision-grade claims until the new names pass the same 17-section coverage floor.

**Acceptance test:**

- Current run must show `tier_definition_aligned=false` with the six missing names listed.
- After the missing names are added to the SQL/data-plane Tier A cohort and pass coverage, the flag flips to `true`.

### F4 - Fast-Track Target States Are Implicit

**File:** `scripts/wf78_auto_tier_router.py`  
**Function:** `route_entry`, `converge_missing_tier_a_confidence`, `enforce_tier_a_row_cap`  
**Issue:** The router can fast-track a ticker from Tier C or Tier B into Tier A, but the intermediate state is just `A-CHALLENGED`. There is no explicit `A-NOMINEE` or `A-CHALLENGED-FAST-TRACK` state that tells consumers "this came in quickly and still needs the full pass."

**Recommendation:** Make fast-track target states explicit.

- Add `A-NOMINEE` and `A-CHALLENGED-FAST-TRACK` to the allowed `auto_state` values.
- When a ticker is promoted from Tier C/B into Tier A and the confidence gate is `force_a_challenged` or the coverage/depth gate has not yet evaluated it, set `auto_state = 'A-NOMINEE'` or `A-CHALLENGED-FAST-TRACK`.
- Only set `A-READY` after:
  - Quote/source TTL passes (F1)
  - Coverage/depth gate is green for this ticker
  - Confidence gate is `ready` with no critical conflicts
  - `decision_grade_allowed_count > 0`
- Add a `fast_track_origin` field to the row metadata: `origin_tier`, `origin_state`, `promotion_trigger` (production_adjudication / competitive_gate / confidence_convergence / tier_c_attention).

**Acceptance test:**

- Promote a synthetic Tier C ticker via production adjudication. It must land in `A-NOMINEE` or `A-CHALLENGED-FAST-TRACK`, not `A-READY`.
- After the full pass runs green, it can transition to `A-READY`.

### F5 - ETF/Sector Fund Evidence Model Is Under-Specified

**Files:** `scripts/wf78_tier_a_confidence_gate.py`, `scripts/tier_a_trade_grade_coverage_gate.py`  
**Issue:** `PAVE`, `VAW`, `VXUS`, `XLF`, and `XLI` are ETFs/sector funds. The confidence gate forces them to `manual_review`, which is safe, but the coverage gate and depth repair executor still evaluate them with single-equity evidence families (thesis, moat, earnings guidance, etc.).

**Recommendation:** Add an instrument-type-aware evidence family selector.

- In `wf78_tier_a_confidence_gate.py`, expand `is_etf_or_proxy()` to detect ETFs, sector funds, and broad equity proxies by `instrument_type`, sector keyword, or a new `universe.is_fund` flag.
- For fund names, replace the 17-section coverage check with a fund-specific family set:
  - `macro_regime_fit`
  - `sector_performance_proxy`
  - `holdings_concentration`
  - `expense_liquidity_profile`
  - `flow_momentum_proxy`
  - `overlap_with_existing_portfolio_exposure`
  - `entry_stop_sizing`
  - `risk_invalidation`
- In `tier_a_depth_repair_phase_executor.py`, route ETF/sector-fund names through a dedicated `Phase G: ETF/Fund Context` lane instead of the single-company thesis/moat lanes.

**Acceptance test:**

- ETF/sector-fund Tier A names pass coverage through the fund-specific families, not through single-company fundamentals.
- The coverage gate does not report `thesis_not_synthesized` or `competitive_moat_not_structured` for a fund if the fund-specific families are present.

### F6 - Daily Movement Ledger Hides Local-Day Event History

**File:** `scripts/wf78_daily_movement_ledger.py`  
**Issue:** The ledger reports `moved_today_count=1` because it reflects the current rolling delta. The append-only event ledger shows 12 local Phoenix-day events, including 6 promotions. A consumer reading only the daily movement ledger undercounts movement.

**Recommendation:** Expose two distinct counts.

- Rename `moved_today_count` to `current_delta_moved_count`.
- Add `local_day_event_count` and `local_day_promotion_count` from `state/workflows/wf78-tier-routing-events.jsonl` filtered by the current Phoenix local day.
- Add `local_day_event_tickers` as a compact list.
- Update `render_markdown()` to show both counts.

**Acceptance test:**

- On a day with 6 promotions and some back-and-forth state changes, `local_day_event_count` is 12, `local_day_promotion_count` is 6, and `current_delta_moved_count` reflects the net current delta.

### F7 - Event Ledger Rows Do Not Carry Gate Verdicts

**File:** `scripts/wf78_tier_routing_event_ledger.py`  
**Function:** `normalize_delta_event`, `events_from_daily_movement_backfill`  
**Issue:** Events include source artifacts and hashes, but not the freshness/depth/coverage/confidence verdicts that were current when the event was emitted.

**Recommendation:** Enrich every promotion event with a `gate_verdicts` block.

For promotion events, include:

```json
{
  "gate_verdicts": {
    "freshness": "stale_quote_required",
    "coverage_floor": "ok",
    "depth": "blocked",
    "confidence": "force_a_challenged",
    "decision_grade_allowed": false,
    "quote_time_utc": "2026-06-05T16:50:46Z",
    "quote_age_hours": 432,
    "packet_age_hours": 432
  }
}
```

- Read the current `tmp/wf78-tier-weighted-freshness-resolution.json`, `tmp/tier-a-trade-grade-coverage-gate.json`, and `tmp/wf78-tier-a-confidence-gate.json` at event generation time.
- Look up the ticker in each surface and attach the relevant verdict.
- Include the authority boundary flags used at event time.

**Acceptance test:**

- A promotion event for a fast-tracked name explains why it landed in `A-CHALLENGED` without requiring a reviewer to reconstruct state from separate files.

### F8 - Weighted Freshness Resolver Needs TTL Windows

**File:** `scripts/wf78_tier_weighted_freshness_resolver.py`  
**Function:** `classify_tier_ab`, `classify_tier_c`, `current_technical_review_available`  
**Issue:** The resolver uses field presence and state labels to decide "current." It does not compute explicit age thresholds for quotes, cards, or post-close overlays.

**Recommendation:** Add TTL windows by required depth class.

- `decision_repair` (Tier A): quote/covering quote ≤ 8 hours during market hours, or ≤ 24 hours post-close; card ≤ 24 hours.
- `promotion_repair` (Tier B): quote ≤ 48 hours; card ≤ 72 hours.
- `thin_monitor` (Tier C): quote ≤ 7 days; card ≤ 14 days.
- Add a helper `quote_age_hours(symbol, source)` and `card_age_hours(symbol, source)`.
- If a Tier A row only has `fresh_price_quote` stale and no fresh post-close quote, classify it as `blocked_fresh_quote_required_before_final_use` with explicit `quote_age_hours` and `ttl_hours`.

**Acceptance test:**

- A Tier A ticker with a 36-hour-old quote and no post-close overlay is classified as blocked, not resolved to current technical review.
- A Tier C ticker with a 5-day-old quote remains resolved thin monitor.

## Implementation Lanes

| Lane | Goal | Primary Files | Risk Level | Estimated Effort |
|---|---|---|---|---|
| L1 | Stop stale packets preserving A-READY | `wf78_auto_tier_router.py` | Low | Small |
| L2 | Make production eligibility require current proof | `finance_sql_canon_access.py`, `tier_a_trade_grade_coverage_gate.py` | Low | Small |
| L3 | Reconcile router/SQL Tier A cohorts | `tier_a_trade_grade_coverage_gate.py` | Low | Small |
| L4 | Formalize fast-track target states | `wf78_auto_tier_router.py` | Medium | Small |
| L5 | Add ETF/fund evidence families | `wf78_tier_a_confidence_gate.py`, `tier_a_trade_grade_coverage_gate.py`, `tier_a_depth_repair_phase_executor.py` | Medium | Medium |
| L6 | Split movement ledger counts | `wf78_daily_movement_ledger.py` | Low | Small |
| L7 | Enrich event ledger with gate verdicts | `wf78_tier_routing_event_ledger.py` | Low | Small |
| L8 | Add TTL windows to freshness resolver | `wf78_tier_weighted_freshness_resolver.py` | Medium | Small |

## Suggested Order

1. **L1 + L2 first.** These remove the most dangerous readiness overclaim.
2. **L3 + L6 + L7 next.** These make the review surfaces trustworthy.
3. **L4 + L5 then.** These harden fast-track and fund-specific behavior.
4. **L8 in parallel with L4/L5.** TTL windows make the whole freshness stack deterministic.

## Regression Test / Eval Checklist

Add these cases to the existing validator bundle or a new `tests/test_wf78_opportunity_discovery.py`:

- [ ] Stale Tier A final promotion packet (quote > TTL) cannot produce `A-READY`.
- [ ] Fresh Tier A packet with green gates can produce `A-READY`.
- [ ] `finance_sql_canon_access.py` validated production answer count is 0 when coverage gate `decision_grade_allowed_count=0`.
- [ ] Coverage gate reports `router_only_tickers` when live router Tier A cohort exceeds SQL/data-plane cohort.
- [ ] Fast-track from Tier C/B lands in `A-NOMINEE` or `A-CHALLENGED-FAST-TRACK`, never `A-READY`.
- [ ] ETF/sector-fund coverage passes through fund-specific evidence families.
- [ ] Daily movement ledger exposes both `current_delta_moved_count` and `local_day_event_count`.
- [ ] Promotion event includes `gate_verdicts` with freshness/depth/coverage/confidence/authority fields.
- [ ] Tier A quote older than 8 hours during market hours blocks `resolved_to_current_technical_review`.
- [ ] All authority flags remain false across every modified script.

## Recommended Next Action

Open narrow implementation lanes for **L1 (stale packet TTL)** and **L2 (production eligibility proof)** first. They are small, low-risk, and remove the biggest readiness-overclaim gap. Run the full validator bundle after each lane. Then proceed to L3/L6/L7 so status and review surfaces report the same truth.

Do not change ticker tiers, universe membership, or capital posture manually. Keep all changes inside the existing non-capital routing boundary.

## Boundary

This audit is non-capital and review-only. It does not approve or recommend any trade, order, position change, capital deployment, paper/live execution, brokerage/account action, money movement, portfolio/canon-note mutation, cash/sizing/risk-rule mutation, customer output, or owner approval inference. All recommendations preserve the existing hard authority boundary: automated non-capital routing only; capital and execution decisions remain owner-gated.
