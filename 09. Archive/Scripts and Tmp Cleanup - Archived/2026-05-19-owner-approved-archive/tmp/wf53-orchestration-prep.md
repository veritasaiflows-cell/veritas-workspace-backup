# WF53 Orchestration Prep - Sector Expansion Coverage and Correlation Proof Layer

Generated: 2026-05-10 11:09 MST helper pass  
Scope: planning only; no canonical note mutation, no portfolio/deployment/watchlist mutation, no owner approval inference.

## 1. Recommended v1 schema for `tmp/sector-correlation-check.json`

```json
{
  "schema_version": 1,
  "generated_at_utc": "...",
  "status": "ok | degraded | blocked",
  "consumer_posture": "review_only",
  "market_data_as_of": "2026-05-08",
  "source_generated_at_utc": {
    "portfolio_config": "...",
    "regime_scores": "...",
    "deployment_surface": "...",
    "trigger_sheet": "...",
    "band_proposals": "...",
    "daily_review_objects": "..."
  },
  "authority": {
    "canonical_mutation_allowed": false,
    "portfolio_mutation_allowed": false,
    "deployment_state_mutation_allowed": false,
    "watchlist_promotion_allowed": false,
    "sizing_allocation_recommendation_allowed": false,
    "trade_execution_allowed": false,
    "owner_approval_granted": false,
    "probability_or_modeling_authority": false
  },
  "risk_policy": {
    "max_single_sector_pct": 25,
    "sector_warning_within_pct_of_cap": 5,
    "normal_single_position_max_pct": 15,
    "speculative_sleeve_max_pct_without_exception": 10
  },
  "source_quality": {
    "overall_classification": "fresh | current | partial | stale | missing | contradictory",
    "trust_level": "clean | review_required | blocked",
    "stop_line": false,
    "issues": []
  },
  "portfolio_exposure": {
    "model_weight_total_pct": 90,
    "cash_pct": 10,
    "sectors": [
      {
        "sector": "Technology",
        "tickers": ["MSFT", "GOOG", "NVDA"],
        "draft_weight_pct": 25,
        "risk_cap_pct": 25,
        "distance_to_cap_pct": 0,
        "status": "at_cap | near_cap | within_limit | over_cap | unknown",
        "source": "Portfolio Snapshot / portfolio-config"
      }
    ],
    "correlated_sleeves": [
      {
        "sleeve": "Tech + AI-power",
        "tickers": ["MSFT", "GOOG", "NVDA", "ETN"],
        "draft_weight_pct": 32,
        "included_non_sector_tickers": ["ETN"],
        "status": "warning",
        "reason": "Direct Tech is at 25% cap; AI-power correlated sleeve rises to 32% including ETN."
      }
    ]
  },
  "tracked_universe_context": [
    {
      "ticker": "LLY",
      "sector": "Healthcare",
      "coverage_lane": "watch",
      "portfolio_role": "watch_only",
      "workflow_state": "WATCH",
      "candidate_role": "diversification_watch",
      "promotion_impact": "would_add_new_sector_without_reducing_tech_cap_pressure",
      "eligible_for_promotion": false,
      "blockers": ["watch-lane only", "explicit promotion and sizing review required"]
    }
  ],
  "promotion_impact_checks": [
    {
      "ticker": "GS",
      "candidate_sector": "Financials",
      "current_sector_weight_pct": 21,
      "candidate_model_weight_pct": 7,
      "pro_forma_sector_weight_pct": 21,
      "cap_status_after": "within_limit",
      "correlated_sleeve_warnings": ["secondary to JPM inside Financials"],
      "review_only_verdict": "sector_ok_but_not_deployable_authority"
    }
  ],
  "diversification_candidates": [
    {
      "ticker": "LLY",
      "sector": "Healthcare",
      "reason": "Healthcare absent from model portfolio and useful defensive-growth diversifier.",
      "status": "watch_review_only"
    },
    {
      "ticker": "CAT",
      "sector": "Industrials",
      "reason": "Industrial capex/infrastructure read-through; still watch-only and would add cyclical exposure.",
      "status": "watch_review_only"
    }
  ],
  "current_limits": [
    "This artifact is concentration proof only; it is not a promotion, sizing, probability, or trade system."
  ],
  "errors": []
}
```

## 2. Exact source files/artifacts and fields to parse

Primary ownership / caps:
- `07. Risk/Risk Rules.md`
  - Parse: `Max single sector: 25%`; `Normal max single position: 15%`; speculative sleeve cap text; escalation trigger about sector cap / correlated sleeve over-stack.
- `03. Portfolio/Portfolio Snapshot.md`
  - Parse: core/tactical/speculative tables: ticker, weight, status; `Sector allocation vs. Risk Rules caps` table: sector, names, draft weight total, cap, status; concentration action rule (`Tech + AI-power` = 32% including ETN); cash target.
- `tmp/portfolio-config.json`
  - Parse: `portfolio.core/tactical/speculative[*].ticker, weight, sector`; `tracked_universe.*.sector, portfolio_role, workflow_state, coverage_lane, sizing_tier`; `risk_thresholds.max_sector_pct`, `risk_thresholds.max_single_position_normal`, `risk_thresholds.max_single_position_stretch`; `workflow_semantics` for state/lane normalization.

Universe / candidate context:
- `02. Markets/Watchlist.md`
  - Parse active tracking table: ticker, sector, coverage tier, current deployment state, canonical source. Treat as navigation/mirror only, not thesis/deployment authority.
- `tmp/regime-scores.json`
  - Parse `records[*].ticker, sector, role, total, stance, close, band_note, repair_mode, thesis_status`; authority block must keep final authority false for deployment/portfolio/trade/owner approval.
- `tmp/deployment-readiness-surface.json`
  - Parse `summary`, `groups.*[*].ticker, surface_state, workflow_state, machine_state, close, band_position, band_stale, action_state, trigger, why, next_earnings_date`; `system.stop_line`, `system.canonical_note_mutation_allowed`, `system.presentation_allowed`.
- `tmp/trigger-sheet.json`
  - Parse `summary.*`, `records[*].ticker, portfolio_role, workflow_state, action_state, close, in_entry_band, below_stop, entry_band, invalidation, size_tier, technical_trigger, deployment_state`.
- `tmp/band-proposals.json`
  - Parse `status`, `summary`, `proposals[*].ticker, coverage_lane, workflow_state, entry_policy, band_status, needs_review, canonical_apply_eligible, reasons`; use only as entry/band debt context, not sector authority.
- `tmp/daily-review-objects-post-close.json`
  - Parse authority top-level flags; `source_freshness`; `capital_deployment_recommendations[*].ticker, sector_correlation_check, state_history_status, missing_evidence, owner_approval_required/granted, mutation flags`; `known_gaps` currently names sector/correlation artifact missing.

Optional proof-context source:
- `data/state-history/state-history-v1.jsonl`
  - WF43 now proves durable append path exists and one validated row exists. Use only for `state_history_presence=available_provenanced` if needed; do **not** use it for outcome analytics, probability, or calibrated sector performance.

## 3. Fail-closed / degraded conditions

Block (`status=blocked`, no sector verdict beyond unavailable):
- Cannot parse Risk Rules sector cap.
- Cannot parse any model weights from both Portfolio Snapshot and `tmp/portfolio-config.json`.
- Authority flags are missing or any forbidden authority flag is true.
- Sector totals from Portfolio Snapshot and `tmp/portfolio-config.json` materially contradict each other and no deterministic owner can be selected.

Degrade (`status=degraded`, review-only output allowed):
- Watchlist table missing or stale/mirror mismatch; keep candidate lane fields `unknown`.
- `tmp/regime-scores.json`, `tmp/deployment-readiness-surface.json`, `tmp/trigger-sheet.json`, `tmp/band-proposals.json`, or `tmp/daily-review-objects-post-close.json` missing/stale/partial; emit sector exposure from canonical/config layer but cap candidate-readiness and promotion-impact detail.
- `band-proposals.status=needs_review`; keep band-related context as review debt only.
- Daily review `source_freshness.overall_classification=partial` or `trust_level=review_required`; no capital-action readiness language.
- Market data unavailable for a ticker; keep exposure math if model weight exists, but mark technical/deployment context unknown.

## 4. Authority flags that must be false

Required false at top level and any per-candidate/per-promotion-impact item:
- `canonical_mutation_allowed`
- `portfolio_mutation_allowed`
- `deployment_state_mutation_allowed`
- `watchlist_promotion_allowed`
- `sizing_allocation_recommendation_allowed`
- `trade_execution_allowed`
- `owner_approval_granted`
- `probability_or_modeling_authority`
- If included: `model_driven_deployment_allowed`, `model_training_enabled`, `capital_action_allowed`

Required true / string posture:
- `consumer_posture="review_only"`
- `owner_approval_required_for_capital=true` if the artifact ever appears beside recommendation/candidate objects.

## 5. Acceptance tests / commands for implementation

Target commands:
```powershell
python -m py_compile scripts\sector_correlation_check.py scripts\test_sector_correlation_check.py
python scripts\test_sector_correlation_check.py
python scripts\sector_correlation_check.py --window post-close --output tmp\sector-correlation-check.json
python -c "import json; p='tmp/sector-correlation-check.json'; d=json.load(open(p, encoding='utf-8')); assert d['schema_version']==1; assert d['consumer_posture']=='review_only'; assert d['authority']['portfolio_mutation_allowed'] is False; assert any(s['sector'] in ('Technology','Tech') and s['status'] in ('at_cap','over_cap','near_cap') for s in d['portfolio_exposure']['sectors']); print(d['status'], d['portfolio_exposure']['correlated_sleeves'][0]['sleeve'])"
python scripts\daily_review_objects.py --window post-close
python scripts\test_daily_review_objects.py
```

Test cases to include in `scripts/test_sector_correlation_check.py`:
- Computes direct Technology exposure as 25% and flags at-cap using the 25% Risk Rules cap.
- Computes `Tech + AI-power` correlated sleeve as 32% from MSFT/GOOG/NVDA + ETN and emits warning.
- Keeps LLY/CAT/VRT/CAT-style names watch/review-only; no promotion eligibility without explicit owner review.
- GS/JPM Financials pro-forma stays inside 25% but still subordinate/owner-gated.
- Missing Risk Rules cap or weight source fails closed.
- Partial generated artifacts degrade trust but do not suppress canonical/config exposure calculation.
- Authority flags are enforced false; any true forbidden flag fails the test.
- No probability language or calibrated outcome language appears.

## 6. Smallest-diff implementation plan

Producer:
- Add `scripts/sector_correlation_check.py`.
- Output only `tmp/sector-correlation-check.json` in v1; optional Markdown should wait until JSON consumers are stable.
- Use `tmp/portfolio-config.json` as machine-readable weight/universe base, with Portfolio Snapshot and Risk Rules parsed as canonical cross-checks. If Markdown parsing is brittle, prefer config for computed totals but emit `source_quality.issues` when note-layer cap/sector table cannot be verified.

Tests:
- Add `scripts/test_sector_correlation_check.py` with fixture-style temp files for fail-closed/degraded cases plus a live-artifact smoke check if current files exist.

Chain wiring decision:
- Do **not** wire into all finance chains in the first implementation diff unless producer + test + direct JSON inspection pass.
- After standalone proof, wire conservatively before `daily_review_objects.py` in `scripts/chain_manifest.py` for windows that emit capital recommendations (`morning`, `post-close`, `post-earnings`, `sunday`) only if daily review consumption is updated in the same pass or deliberately left as "artifact available but not consumed".

Adjacent consumer to update, but only after producer proof:
- `scripts/daily_review_objects.py`: replace `sector_correlation_check: missing_artifact_manual_fallback_required` with summarized artifact status for candidate packets, while keeping owner approval and mutation flags false.
- `scripts/test_daily_review_objects.py`: update the missing-evidence expectation so it accepts `available_review_only` only when the artifact exists, is non-blocked, and authority flags are safe.

Consumers not to touch yet:
- Portfolio Snapshot, Deployment Trigger Sheet, Watchlist, Technical Entry Sheet, Risk Rules.
- Dashboard payload/HTML, `artifact_index.py`, candidate generator production paths, WF54/WF55 analytics, state-history capture schema.
- No Markdown note mutation or promotion queue mutation in WF53 v1.

## 7. Explicit blockers / residue

Current real concentration facts to preserve:
- Direct Tech is already at the 25% single-sector cap from MSFT 10% + GOOG 10% + NVDA 5%.
- AI-power correlated sleeve is broader than sector classification: MSFT + GOOG + NVDA + ETN = 32%; ETN being Industrials does not diversify away AI-power crowding.
- Financials are 21% with JPM + GS; GS may be sector-cap-compatible but remains tactical/secondary and owner-gated.
- LLY is the cleanest Healthcare diversification watch candidate, but still watch-lane only.
- CAT is useful Industrial read-through, but still watch-lane only and not an active-board promotion.

WF43 helps now:
- Durable state-history path exists (`data/state-history/state-history-v1.jsonl`) and has first append/validate proof, so consumers no longer need to call state history completely absent when only presence/provenance is required.

WF43 does **not** unlock:
- probability scoring, calibrated sector performance, win/deploy probabilities, expected return, model-ranked promotion candidates, or outcome analytics.
- deployment authority, sizing recommendations, canonical note mutation, or owner approval inference.

Remaining implementation blocker:
- Daily review currently emits `sector_correlation_check=missing_artifact_manual_fallback_required`; WF53 v1 producer should land before WF51/WF54/WF55 rely on sector/correlation proof for candidate readiness or analytics.
