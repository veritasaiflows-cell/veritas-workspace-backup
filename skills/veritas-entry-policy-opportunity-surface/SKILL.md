---
name: "veritas-entry-policy-opportunity-surface"
description: "Reuse existing technical posture surfaces; add only entry-policy visibility routing."
---

# Veritas Entry Policy Opportunity Surface

## Purpose

Prevent secondary or watch-lane tickers from being hidden when they develop a real entry setup, without creating another duplicate technical-analysis layer.

The missing piece is not another 20D/50D/200D engine. The workspace already computes and consumes technical posture in several places:

- `tmp/technical-refresh.json`: 20D/50D/200D, in-band, below-stop, moving-average posture.
- `tmp/band-proposals.json`: band status, trend stack, Keltner/MA proposal, auto-apply eligibility.
- `tmp/deployment-check.json`: deployable/watch/bench classification using entry band, below-stop, workflow state, coverage lane, and weak chart structure.
- `tmp/chief-intelligence-promotion-gate.json`: promotion scoring/vetoes including band status and MA posture.
- `tmp/finance-decision-sync-spine.json`: final review-only state aggregation and blockers.

This proposal adds a visibility and entry-policy review route that consumes those existing surfaces. It must not recalculate a competing technical verdict unless an upstream artifact is missing or stale.

## Core Rule

Secondary tickers must not be hidden behind primary tickers.

Primary-vs-secondary affects ranking, concentration warnings, and portfolio-fit notes. It must not keep a ticker in `entry_policy=underdefined` when existing technical and band surfaces show a reviewable setup.

Example: `XOM` can remain the primary Energy expression while `CVX` still surfaces for review if it reclaims a valid setup.

## What Changes

Do not add a new technical posture layer.

Add or extend a review queue that answers one question:

> Does this ticker need main-session entry-policy review because existing surfaces show a real setup but policy metadata is still suppressing visibility?

Preferred implementation: extend the existing `band_hygiene_freshness_controller` or `finance_decision_sync_spine` to emit an `entry_policy_review_candidates` section, instead of creating an entirely separate unrelated artifact. If a standalone artifact is simpler for implementation, it must be a thin index over existing surfaces, not a new source of technical truth.

## Replacement For Bare `underdefined`

Avoid silent `underdefined` for Tier A/B names with numeric band/stop context.

Recommended fields under `tracked_universe[ticker]`:

```json
{
  "entry_policy": "band_defined | reference_band | reclaim_only | repair_mode | event_freeze | missing_band | policy_review_required",
  "entry_policy_blockers": ["watch_lane", "below_stop", "source_lineage_missing", "earnings_freeze", "portfolio_role_secondary"],
  "opportunity_role": "primary | secondary | challenger | diversifier | hedge | tactical | monitor",
  "capital_review_visibility": "surface_if_setup_valid | suppress_until_reclaim | monitor_only",
  "last_entry_policy_review_date": "YYYY-MM-DD",
  "last_entry_policy_review_source": "artifact/path or main-session decision reference"
}
```

Rules:

- `entry_policy=band_defined` means existing band/stop/invalidation surfaces are decision-grade enough for capital-review ranking.
- `entry_policy=reference_band` means numeric levels exist but are review-only; still surface if existing surfaces show price entered/reclaimed the setup.
- `entry_policy=reclaim_only` means no recommendation until existing surfaces show reclaim.
- `entry_policy=repair_mode` means do not recommend; surface only as repair/reclaim watch.
- `entry_policy=policy_review_required` means existing surfaces show a possible setup, but main session has not ruled on promotion.
- `opportunity_role=secondary` is never a blocker by itself. It becomes a concentration/ranking caution.

## Existing Technical Surface Contract

The review route must read, not duplicate, these fields:

- from `technical-refresh`: `ma20`, `ma50`, `ma200`, `ma_posture`, `above_ma20`, `above_ma50`, `above_ma200`, `in_entry_band`, `below_stop`
- from `band-proposals`: `band_status`, `trend_stack`, `entry_band_method`, `canonical_apply_eligible`, `needs_review`, `reasons`
- from `deployment-check`: action state and explanation, especially watch-lane suppression language
- from `chief-intelligence-promotion-gate`: verdict/vetoes
- from `finance-decision-sync-spine`: final blockers and clean-for-review flags

No new queue may override these fields. If they conflict, the row must surface a `technical_surface_conflict` warning for main-session review.

## Cron Responsibilities

Cron may refresh evidence and produce review queues. Cron must not infer owner approval or mutate capital/execution authority.

Cron should surface a review candidate when existing artifacts show any of these:

- Tier A/B ticker has numeric band/stop, price is in/near band, but `entry_policy` is `underdefined` or `reference_band`
- price enters band while `coverage_lane != execution`
- secondary/challenger ticker becomes technically valid even if a primary ticker exists in the same sector
- reclaim occurs after repair according to existing band/deployment surfaces
- band is stale or auto-apply blocked only because policy metadata remains unresolved

The queue row should carry source pointers rather than recomputed technical analysis:

```json
{
  "ticker": "RTX",
  "auto_tier": "Tier A",
  "current_route_state": "A-CHALLENGED",
  "entry_policy": "underdefined",
  "recommended_entry_policy_action": "main_review_required | keep_reference | promote_candidate | repair_only",
  "opportunity_role": "secondary | challenger | primary | monitor",
  "secondary_not_suppressing": true,
  "source_band_status": "from band-proposals or decision spine",
  "source_ma_posture": "from technical-refresh",
  "source_deployment_check_state": "from deployment-check",
  "source_promotion_gate_verdict": "from chief-intelligence-promotion-gate",
  "blockers": [],
  "warnings": [],
  "source_artifacts": []
}
```

## Recommendation Gate

A ticker may surface for review without becoming a recommendation.

Capital-recommendation builders should continue to block recommendations when existing surfaces show:

- below stop or invalidation
- repair mode or reclaim-only state
- broken MA posture from `technical-refresh` / `band-proposals`
- above-band/no-chase
- earnings/event freeze
- stale quote or conflicting source surfaces

The new rule is only: do not hide the row when the blocker is policy metadata or secondary role.

## Main Session Responsibilities

Veritas main session reviews the surfaced candidates and may apply bounded non-capital state sync only when evidence supports it and validators pass:

- `entry_policy=band_defined`
- `coverage_lane=execution`
- `workflow_state=PROMOTION REVIEW` or `ALMOST`
- updated blockers are empty or warning-only
- preserve `capital_deployment_approved=false`
- preserve `trade_or_execution_approved=false`

Main session must not promote a ticker solely because it is secondary, popular, or in band. It must verify the existing technical, band, source, catalyst, and portfolio-risk surfaces.

## Secondary Opportunity Policy

Use ranking, not suppression.

- Primary ticker: best current expression of the theme or sector.
- Secondary ticker: valid alternative or second expression if portfolio capacity exists.
- Challenger ticker: can displace or compete with primary if evidence improves.
- Diversifier/hedge: can be recommended despite lower raw rank if it solves a portfolio construction problem.
- Monitor: visible but not recommendation-ready.

Sector overlap should produce warnings such as `energy_overlap_with_XOM_review_required`, not hidden status.

## Alerting Change

Split blocked buy alerts from review alerts.

- Keep hard blocks for buy/order alerts and WF67 request generation.
- Allow review alerts for `entered_band_but_policy_underdefined`.
- A ticker may be `order_alert_blocked` while still allowed to wake main session for entry-policy review.

## Current Ticker Recommendations From 2026-06-15 Review

- `RTX`: should surface as `main_review_required` because existing surfaces show it in band but suppressed by watch/underdefined policy. Do not promote unless existing MA/band/source/promotion surfaces support it.
- `CVX`: should not be hidden behind `XOM`; current below-stop state still blocks recommendation, but reclaim should surface it for review.
- `XOM`: primary Energy role but repair/requalify state; should not suppress CVX.
- `LMT`: repair/reclaim blocked; do not promote without reclaim and source/technical review.
- `BRK.B`: repair/do-not-touch state requires main-session review before promotion; in-band alone is insufficient.
- `LLY`: band-defined but above-band/no-chase; keep visible as high-quality wait candidate.
- `MSFT` and `RTX`: in-band names with policy/hygiene exceptions should be visible in review, not buried.
- `SMCI`: missing band context remains repair until numeric source-backed band/stop exists.

## Required Implementation Changes

1. Prefer extending `band_hygiene_freshness_controller` or `finance_decision_sync_spine` with `entry_policy_review_candidates`; use a standalone `entry-policy-review-queue.json` only as a thin derived index if needed.
2. Update `trigger_sheet_refresh.py` and `deployment_check.py` so `watch-lane + in-band + numeric band/stop` emits a review-attention state instead of only suppressing as `WATCH / RESEARCH NEEDED`.
3. Split `MUST_BLOCK` into order-alert blocking and review-attention eligibility.
4. Update recommendation builders so secondary/challenger candidates surface with overlap warnings instead of suppression.
5. Add validator: Tier A/B ticker with numeric band/stop and `entry_policy=underdefined` must be visible in the review candidates unless existing surfaces show below-stop, repair-mode, event-freeze, or broken technical posture.
6. Add validator: review candidate rows must source technical posture from existing artifacts and must not introduce a second calculation.
7. Add main-session bounded sync path for entry-policy promotion with preview/diff, validator proof, backup/rollback, and audit log.

## Acceptance Criteria

- `RTX` appears in review attention when it is in band but still watch/underdefined.
- `CVX` is not hidden because `XOM` is primary; it is visible as a secondary candidate when existing technical gates support review.
- Below-stop names remain blocked from recommendation but visible as repair/reclaim candidates.
- Above-band names remain visible as no-chase candidates.
- No duplicate MA/technical layer is created.
- No review queue row implies capital deployment approval.
- No cron job mutates portfolio/capital/execution authority.
- Validators preserve `capital_deployment_approved=false` and `trade_or_execution_approved=false` on all generated artifacts.
