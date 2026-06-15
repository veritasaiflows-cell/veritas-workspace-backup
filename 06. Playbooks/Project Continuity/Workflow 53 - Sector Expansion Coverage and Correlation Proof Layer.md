# Workflow 53 - Sector Expansion Coverage and Correlation Proof Layer

## Objective

Build a review-only sector exposure and correlation proof layer so sector expansion, diversification candidates, and promotion-review packets can see concentration risk before any candidate is treated as deployable.

## User request trigger

Opened on 2026-05-10 after Randall asked to plan sector expansion into the Veritas OS and start automating more with Veritas approval while preserving owner gates.

## Scope

Create a machine-readable sector/correlation diagnostic from existing canonical and generated surfaces:
- `03. Portfolio/Portfolio Snapshot.md`
- `07. Risk/Risk Rules.md`
- `02. Markets/Watchlist.md`
- `tmp/portfolio-config.json`
- `tmp/regime-scores.json`
- existing deployment / trigger / technical artifacts where needed

Expected v1 output:
- `tmp/sector-correlation-check.json`
- `tmp/sector-expansion-board.json`
- optional `tmp/sector-correlation-check.md`

## Required checks

- direct sector exposure versus the Risk Rules cap
- correlated sleeves, especially Tech / AI-power exposure
- diversification candidates by sector
- whether a promotion candidate would worsen concentration
- candidate role: execution / watch / macro / speculative
- fail-closed behavior when source tables or generated artifacts cannot be parsed

## Authority boundary

Review-only.

This workflow does not authorize:
- watchlist promotion
- Portfolio Snapshot mutation
- Deployment Trigger Sheet mutation
- sizing or allocation recommendations without Randall approval
- trade execution or account action
- inferred owner approval

## Dependencies

- WF43 durable state history is not required for the first current-state sector check, but is required before outcome analytics or calibrated sector-performance claims.
- WF51 production candidate generation remains deferred until this sector/correlation proof exists and passes.

## Acceptance gates

- sector and sleeve exposure are computed from files/artifacts, not asserted
- Risk Rules caps are visible in output
- missing/partial source inputs produce a degraded/fail-closed status
- LLY/CAT-style diversification names remain watch/review-only unless explicit promotion review exists
- output includes authority flags matching the review-only finance spine
- proof includes py_compile, targeted test, artifact generation, and direct JSON inspection

## Current implementation state

Status: **v1 implemented and QA-accepted on 2026-05-10**.

2026-05-10 implementation lane completed the review-only v1 chain:
- `scripts/sector_correlation_check.py` writes `tmp/sector-correlation-check.json` and now uses the window-specific daily-review artifact if it exists without requiring it before daily review generation.
- `scripts/sector_expansion_board.py` writes `tmp/sector-expansion-board.json`, reviews all 11 SPDR sectors against SPY, includes 1d/5d/20d relative strength, 50DMA participation, portfolio exposure, tracked candidates, promotion-review rows, correlation warnings, and the exact status question.
- `scripts/chain_manifest.py` wires `sector_correlation_check.py` then `sector_expansion_board.py` before `daily_review_objects.py` for morning, post-close, and Sunday. Post-earnings was intentionally not widened.
- `scripts/daily_review_objects.py` consumes fresh sector board / correlation artifacts for capital packets while keeping owner approval and all mutation authority false.

Proof completed:
- `python -m py_compile scripts\\sector_expansion_board.py scripts\\test_sector_expansion_board.py scripts\\sector_correlation_check.py scripts\\daily_review_objects.py scripts\\chain_manifest.py`
- `python scripts\\test_sector_expansion_board.py`
- `python scripts\\test_sector_correlation_check.py`
- `python scripts\\sector_correlation_check.py --window post-close --output tmp\\sector-correlation-check.json`
- `python scripts\\sector_expansion_board.py --window post-close --output tmp\\sector-expansion-board.json`
- `python scripts\\daily_review_objects.py --window post-close`
- `python scripts\\run_finance_refresh_chain.py post-close --dry-run`
- Additional dry-runs verified morning and Sunday manifest placement.

Independent QA found one blocker before closeout: stale sector-board/correlation documents could leak fields into fresh daily-review sector context when only one artifact was fresh. Fixed in `scripts/daily_review_objects.py`; added regression coverage in `scripts/test_daily_review_objects.py` for stale-board/fresh-correlation, fresh-board/stale-correlation, and both-stale fallback behavior.

Final main-session proof after the QA fix:
- `python -m py_compile scripts\\daily_review_objects.py scripts\\test_daily_review_objects.py`
- `python scripts\\test_daily_review_objects.py`
- `python -m py_compile scripts\\sector_expansion_board.py scripts\\test_sector_expansion_board.py scripts\\sector_correlation_check.py scripts\\chain_manifest.py`
- `python scripts\\test_sector_expansion_board.py`
- `python scripts\\test_sector_correlation_check.py`
- `python scripts\\daily_review_objects.py --window post-close`
- `python scripts\\run_finance_refresh_chain.py post-close --dry-run`
- `python scripts\\run_finance_refresh_chain.py morning --dry-run`
- `python scripts\\run_finance_refresh_chain.py sunday --dry-run`

Current board verdict from the generated post-close artifact:
- Status is `degraded`, not clean, because upstream source warnings / partial trust remain visible.
- Improving leadership: Technology.
- Underexposed sectors: Communication Services, Consumer Discretionary, Consumer Staples, Health Care, Materials, Real Estate, Utilities.
- Promotion-review candidates parsed: CAT, ETN, GS, JPM, LLY, NVDA.
- Technology/AI-power cap warning is visible; all authority flags are false.

## Residue / next action

WF53 v1 is usable as a review-only daily sector-expansion board. Remaining residue is non-blocking:
- `post-earnings` daily review may consume a still-fresh WF53 board/correlation artifact, but the post-earnings manifest intentionally does not regenerate WF53; keep this documented rather than treating it as fresh post-earnings sector work.
- Optional future refinement: tighten taxonomy mapping for non-SPDR model sectors such as Defense, Commodities, and Diversified Quality if Randall wants those reconciled into SPDR-style sector exposure views.

Do not use WF53 output as watchlist promotion, sizing, deployment, trade, probability, or owner-approval authority.

## WF56 handoff boundary

WF53 may feed concentration and diversification context into portfolio-mutation proposals.
It does not authorize the mutation.

Allowed handoff to WF56:
- current sector exposure and underexposure context
- correlated-sleeve warnings, especially Technology / AI-power crowding
- promotion-review candidate list and concentration-impact diagnostics
- source freshness / degraded-state warnings

Blocked:
- automatic sleeve rebalancing
- automatic ticker promotion/demotion
- automatic Portfolio Snapshot or Deployment Trigger Sheet mutation
- sizing/allocation recommendation treated as approval
