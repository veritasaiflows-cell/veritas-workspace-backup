# Workflow 77 - Finance Intelligence Coverage and Question Router

## Purpose

Make finance intelligence answers faster and more consistent by routing recurring questions through compact coverage registries and indexes before broad workspace scans.

This workflow exists because Randall identified a real operating gap on 2026-05-25: Veritas can retrieve artifacts, but does not yet have a clean data-family coverage map that answers "what do we collect, what is missing, what is stale, what is indexed, and what guidance is supportable?"

## Scope

Build review-only support surfaces for:
- finance data coverage
- ticker intelligence cards
- missing-evidence detection
- analyst consensus / ratings / target coverage
- recommendation-support context
- question routing
- index/cockpit integration

## Stop lines

- No live trading, brokerage/account action, or money movement.
- No paper execution or paper submit/cancel/sell.
- No owner approval inference.
- No portfolio/canon/sizing/cash/risk-rule/execution-entitlement mutation.
- SQL, coverage registries, ticker cards, and router outputs are derived routing/review surfaces only; they are not canon, approval, or apply authority.
- Source-open rule remains required before final finance, readiness, recommendation, or action claims.

## Phase plan

### Phase 0 - Contract and schema

Deliver `tmp/finance-intelligence-router-contract-2026-05-26.json` defining question classes, source-open rules, authority boundaries, artifact ownership, and acceptance gates.

Question classes:
- coverage
- missing evidence
- freshness
- proof/provenance
- ticker intelligence
- recommendation support
- authority/guardrail
- workflow/runtime status

### Phase 1 - Finance data coverage registry

Build `scripts/finance_data_coverage.py` and `tmp/finance-data-coverage-current.json`.

Initial source artifacts:
- `tmp/fundamental-metrics-current.json`
- `tmp/deployment-readiness-surface.json`
- `tmp/current-window-artifacts.json`
- `tmp/market-state.json`
- `tmp/portfolio-mutation-proposals/current-capital-deployment-recommendations.json`
- `tmp/capital-deployment-recommendation-validation.json`
- future `tmp/analyst-consensus-current.json`

Initial data families:
- valuation multiples
- official fundamentals
- revenue/growth/margins/FCF/debt
- price/band/stop
- technical posture
- catalyst/earnings state
- deployment readiness
- portfolio fit/concentration
- source freshness
- analyst consensus
- analyst ratings
- analyst price targets
- authority/guardrails

Acceptance: answer "do we collect X," "which tickers lack X," and "is X indexed/fresh" without broad workspace search.

### Phase 2 - Ticker intelligence cards

Build `scripts/ticker_intelligence_card.py` and write cards under `tmp/ticker-intelligence-cards/<TICKER>.current.json`.

Each card should include:
- ticker
- latest known price
- entry band and stop/invalidation
- valuation
- official fundamentals
- analyst consensus/ratings/targets status
- catalyst/earnings state
- technical posture
- portfolio fit/concentration
- recommendation-support posture
- missing/stale evidence
- source artifacts
- authority boundary

Prototype tickers: CME and PH first, then ETN/VRT/NVDA.

### Phase 3 - Analyst consensus layer

Build or stage `tmp/analyst-consensus-current.json` with source, timestamp, buy/hold/sell counts, consensus rating, average/median/high/low targets, implied upside/downside, rating-change notes, stale flag, and confidence.

If provider automation is not ready, explicitly mark missing/manual-required instead of fabricating values.

### Phase 4 - Artifact index / cockpit integration

Extend `scripts/artifact_index.py` only after Phase 1/2 shapes are stable.

Target commands:
- `python scripts\artifact_index.py data-coverage`
- `python scripts\artifact_index.py data-coverage --ticker CME`
- `python scripts\artifact_index.py missing-data`
- `python scripts\artifact_index.py missing-data --family analyst_consensus`
- `python scripts\artifact_index.py ticker-card CME`

### Phase 5 - Question router

Build `scripts/veritas_question_router.py` to classify user questions and return the correct registry/index/source route.

Examples it must route:
- "Do we collect analyst ratings?"
- "What is missing for PH?"
- "Is CME ready?"
- "Where is valuation for VRT?"
- "Can we paper buy CME tomorrow?"

### Phase 6 - Recommendation support layer

Add structured recommendation support to ticker cards without creating a black-box buy/sell engine.

Recommended posture labels:
- deployable now
- approval-ready paper starter if fresh in band
- promotion review
- watch only
- no chase
- blocked stale
- blocked authority
- reject/defer

Acceptance: recommendations become faster and clearer while preserving source-open, risk, concentration, freshness, and approval boundaries.

### Phase 7 - QA / validator

Add a validator or QA artifact such as `tmp/finance-intelligence-router-qa-2026-05-26.json`.

QA must verify:
- schemas parse
- coverage gaps are explicit
- stale/missing flags work
- source-open requirements remain visible
- no authority flags widened
- no generated registry/card becomes canon/approval/execution authority

## Current status

2026-05-25 20:55 MST: workflow opened from Randall request. Core startup/routing files updated so future sessions prefer registry/index routing before broad scans. Implementation prototype still pending.

2026-05-25 21:07 MST: Phase 3/5/7 partial implementation landed in review-only form: `tmp/analyst-consensus-current.json` placeholder marks analyst consensus/ratings/targets as missing/manual-required with null values; `scripts/veritas_question_router.py` routes recurring finance questions to registry/card/SQL/source surfaces without authority widening; `scripts/finance_intelligence_router_qa.py` writes `tmp/finance-intelligence-router-qa-2026-05-26.json` and passed 33 checks. Residue: Phase 1 coverage registry and Phase 2 ticker cards were absent in this lane, so router/QA explicitly report them as missing rather than fabricating coverage.

2026-05-25 21:08 MST: Phase 2/6 CME+PH prototype landed in review-only form: `scripts/ticker_intelligence_card.py` writes `tmp/ticker-intelligence-cards/<TICKER>.current.json`; CME and PH cards include latest reference price, entry band, stop, valuation, official fundamentals, placeholder analyst-consensus status, catalyst/technical/portfolio context, recommendation-support posture, missing/stale evidence, source artifacts, and authority boundary. Both cards show `approval-ready paper starter if fresh in band` as review-only recommendation support because prepared WF67 order cards exist, but still require fresh Tuesday quote, owner selection/approval, source-open review, and WF67 guards; no paper/live execution or portfolio/canon authority is granted. `python scripts\finance_intelligence_router_qa.py --pretty` passed 37 checks with 2 ticker cards found.

2026-05-25 21:32 MST: WF77 V1 closed. Phase 4/7 integration now routes the stable coverage/card shapes through `scripts/artifact_index.py` commands (`data-coverage`, `missing-data`, `ticker-card`) and the QA harness. `scripts/finance_data_coverage.py` now incorporates `tmp/ticker-intelligence-cards/*.current.json` and `tmp/tuesday-position-sizing-readiness-2026-05-26.json` as review-only coverage sources for price/band/stop, technical posture, catalyst/earnings state, deployment readiness, portfolio fit/concentration, recommendation support, analyst manual-required status, and authority guardrails. Ticker cards now exist for CME, PH, ETN, VRT, and NVDA; coverage registry summary is `source_artifact_count=9`, `source_artifacts_present=9`, `source_artifacts_stale=0`, `source_artifacts_unusable_placeholder=1`, `ticker_count_indexed=42`, `data_family_count=16`, and `analyst_layer_status=future_expected_missing`. QA passed 43 checks with 0 errors and 0 warnings; artifact-index validation passed 28/28; workspace boundary check had 0 warnings. V1 remains routing/review only: no canon/portfolio mutation, sizing/cash/risk-rule mutation, approval inference, paper/live execution, brokerage/account action, or money movement.

2026-05-25 21:57 MST: WF77 V1.1 analyst consensus automation completed. Added `scripts/analyst_consensus_refresh.py` as the default yfinance/Yahoo-derived breadth refresh for analyst recommendation counts and price targets, with `BRK.B` -> `BRK-B` Yahoo-symbol normalization and null/manual-required handling when provider data is unavailable. `tmp/analyst-consensus-current.json` is now `sourced_current` with 42 tickers, 31 yfinance-sourced/partial rows, 11 missing rows left null/stale, and an 18-name Tier A/B manual-review queue. `scripts/finance_intelligence_router_qa.py` now accepts sourced analyst artifacts while preserving source-open/manual-review requirements. Coverage now reports `source_artifacts_unusable_placeholder=0` and `analyst_layer_status=collected`; QA passed 43 checks with 0 errors/warnings. Scheduled cron job `95da55c1-5288-4aab-972e-b730ad140c55` runs weekly Monday 15:30 America/Phoenix to refresh yfinance data, rebuild WF77 coverage/card artifacts, validate router/index state, and announce the Tier A/B manual-review queue or blockers. V1.1 remains review/routing only: no canon/portfolio mutation, no approval inference, no sizing/cash/risk-rule mutation, no paper/live execution, no brokerage/account action, and no money movement.

2026-05-26 22:22 MST: WF77 SQL/JSON-first answer-contract slice completed. Integrated the gap audit and implementation plan by adding an additive `answer_contract_v2` layer to `scripts/veritas_question_router.py`, family-id normalization for questions like valuation -> `valuation_multiples`, family-specific coverage/source-open requirements, exact ticker-card path propagation in `scripts/finance_data_coverage.py`, and `scripts/artifact_index.py answer-contract` / `validate-answer-contract` read-only commands. QA now verifies 62 checks including contract-v2 review-only guardrails and family-specific valuation routing. Proof: `tmp/finance-intelligence-router-qa-wf77-phase1-20260526.json` passed 62/0, `tmp/wf77-answer-contract-vrt-valuation-20260526.json` validates ok, coverage registry now emits exact family source artifacts such as `tmp/fundamental-metrics-current.json`, and `artifact_index.py validate` remains ok 28/0 after incremental refresh. Boundary unchanged: answer contracts route/validate proof only; they do not grant canon/portfolio mutation, approval inference, sizing/cash/risk-rule changes, paper/live execution, brokerage/account action, or money movement.

2026-05-26 23:19 MST: WF77 ticker-card registry completion pass closed. `scripts/ticker_intelligence_card.py` now supports `--all-from-coverage` and `--summary-output`; it generated one review-only card for every ticker in `tmp/finance-data-coverage-current.json` (`42/42`) under `tmp/ticker-intelligence-cards/<TICKER>.current.json`, including MSFT. `scripts/finance_intelligence_router_qa.py` now asserts ticker-card registry completeness against coverage tickers, representative class presence, source-open flags, and no authority widening. `scripts/veritas_question_router.py` now propagates per-card `missing_or_stale_evidence` into `answer_contract_v2`, so material finance answers stop/downgrade when the card reports stale quote or missing evidence. Proof: `tmp/ticker-card-registry-build-summary-20260526.json` status ok / 42 cards / 0 errors; `tmp/finance-intelligence-router-qa-ticker-card-registry-20260526.json` passed 180/0 with 42 cards found; `tmp/wf77-answer-contract-msft-full-stack-post-card-20260526.json` validates ok and correctly marks final answer not allowed until fresh quote residue is handled; `artifact_index.py validate` remains ok 28/0 after incremental refresh. Boundary unchanged: ticker cards, coverage registry, answer contracts, and SQL index remain routing/review/proof only and grant no canon/portfolio mutation, owner approval, sizing/cash/risk-rule change, paper/live execution, brokerage/account action, or money movement.

2026-05-27 18:35 MST: WF77 V1.4 enriched ticker-card full-picture pass closed from Randall request. `scripts/ticker_intelligence_card.py` now emits schema v2 cards for 42/42 coverage tickers with additive fields for thesis/bull/bear/entry routing, latest earnings performance, key financial metrics, analyst consensus, risk register, competitive-moat evidence gate, recent developments, orders/backlog/book-to-bill, current sector performance, ETF/macro-proxy profile, technical moving averages, source artifacts, and unchanged authority boundaries. `scripts/finance_data_coverage.py` now indexes the new families (`latest_earnings_performance`, `key_financial_metrics`, `risk_register`, `competitive_moat`, `recent_developments`, `orders_backlog_book_to_bill`, `current_sector_performance`, and `thesis_bull_bear_entry_context`) and adds official earnings bridge, sector board, and technical refresh as source-freshness/proof inputs. `scripts/finance_intelligence_router_qa.py` now asserts enriched fields, non-empty risk registers, source-open moat safety, source-open flags, card completeness, and no authority widening. Proof: `python -m py_compile scripts\\ticker_intelligence_card.py scripts\\finance_data_coverage.py scripts\\finance_intelligence_router_qa.py` passed; validate-only ticker build wrote `tmp/ticker-card-enrichment-validate-summary.json` with 42 cards / 0 errors; live build wrote `tmp/ticker-card-registry-build-summary-20260527-enriched.json` with 42 cards / 0 errors; `python scripts\\finance_data_coverage.py --validate --write-contract` passed with 24 families and 12/12 sources present; `tmp/finance-intelligence-router-qa-2026-05-27-enriched.json` passed 306 checks / 0 errors / 0 warnings; `python scripts\\artifact_index.py validate` passed 28/28. Boundary unchanged: ticker cards are review/routing surfaces only and grant no canon/portfolio mutation, owner approval, sizing/cash/risk-rule change, paper/live execution, brokerage/account action, or money movement.

2026-05-27 19:44 MST: WF77 V1.4a ticker-card resolver hardening closed after PLTR exposed a top-level `latest_known_price: null` despite technical refresh containing a valid close. Preserved separate source artifacts; patched `scripts/ticker_intelligence_card.py` aggregation so latest price resolves Tuesday readiness -> deployment readiness -> technical refresh, and band/stop resolve Tuesday readiness -> order-card risk check -> `tmp/portfolio-config.json`. Missing Tuesday position-sizing or deployment-readiness rows remain explicit blocking/context residue and do not imply actionability. Added card validation and `scripts/finance_intelligence_router_qa.py` checks so a technical close cannot silently coexist with null top-level latest price, and price/band/stop must resolve when technical close exists. Proof: py_compile passed; `tmp/ticker-card-resolver-validate-summary-20260527.json` 42 cards / 0 errors; live build `tmp/ticker-card-registry-build-summary-20260527-resolver.json` 42 cards / 0 errors; coverage validate/write-contract passed; `tmp/finance-intelligence-router-qa-2026-05-27-resolver.json` passed 390 checks / 0 errors / 0 warnings; PLTR card now reports latest price 132.51 from `tmp/technical-refresh.json`, band 137.37-149.53 and stop 131.29 from `tmp/portfolio-config.json`; artifact index incremental + validate passed 28/28. Boundary unchanged: cards remain review/routing only and grant no canon/portfolio mutation, owner approval, sizing/cash/risk-rule change, paper/live execution, brokerage/account action, or money movement.


## Next action

Use WF77 V1.4a as the default first route for recurring finance inventory, missing-evidence, proof, ticker-intelligence, recommendation-support, and authority questions: classify the question, use coverage/ticker-card/SQL routes first, generate/read an answer contract when the answer could influence finance judgment, then open exact source artifacts or canonical owner notes before final finance claims. Treat card-level `missing_or_stale_evidence` as a required confidence downgrade/stop condition until refreshed or explicitly classified. For analyst consensus/ratings/targets, use `tmp/analyst-consensus-current.json` as the default breadth artifact, but treat yfinance as unofficial routing/review data; Tier A/B tickers require weekly manual/source-open review and fresh source-open review before consequential recommendation, portfolio-change proposal, or paper-order-card use. For competitive moat, do not infer; the card field is now structurally present but must stay `not_yet_structured_source_open_required` until sourced thesis/research evidence populates it.

## 2026-06-06 ticker-card v3 / decision-context handoff

Randall approved the next upgrade direction now that WF78, WF55, WF74, post-close quote overlay, cron freshness, and the automation trust spine have materially advanced. WF77 should evolve ticker cards from static intelligence snapshots into layered decision-context objects.

Next-lane target:
- Add an additive `decision_context_v1` or schema v3 section to `scripts/ticker_intelligence_card.py`.
- Include `effective_price_context`: selected price, selected source, market date, retrieval timestamp, source priority, prior/reference price, and whether the price is intraday, post-close final, technical close, or stale reference.
- Include `recommendation_readiness`: research-ready, owner-card-ready, execution-freshness-required, blocked-stale, blocked-source-lineage, blocked-authority.
- Include `source_lineage_status`: owner-approved, generated review-only proposal, missing, source-open required.
- Include `portfolio_fit_context`: current exposure if available, sector/sleeve fit, concentration/correlation warning, and risk-budget posture as review-only context.
- Include `outcome_tracking_id` / WF55 tracking hook when a recommendation/card/decision row exists.
- Keep `missing_or_stale_evidence` and source-open stop lines explicit; do not make ticker cards canon or execution authority.

Primary new input:
- `tmp/post-close-final-quote-ledger.json` from `scripts/post_close_final_quote_ledger.py`; use it as the preferred closed-market/weekend quote overlay for recommendation prep.
- Post-close chain rule as of 2026-06-08: after the final quote ledger is written, run `scripts/ticker_card_freshness_owner_runner.py --skip-provider-refresh --write --validate` so ticker cards and answer packets consume the same closed-market price overlay before WF78 capital-review/factory surfaces run.

Acceptance proof:
- `python -m py_compile scripts\ticker_intelligence_card.py scripts\finance_data_coverage.py scripts\finance_intelligence_router_qa.py`
- `python scripts\ticker_intelligence_card.py --all-from-coverage --validate-only --summary-output tmp\ticker-card-decision-context-validate-summary.json`
- `python scripts\ticker_intelligence_card.py --all-from-coverage --summary-output tmp\ticker-card-decision-context-build-summary.json`
- `python scripts\finance_data_coverage.py --validate --write-contract`
- `python scripts\finance_intelligence_router_qa.py --out tmp\finance-intelligence-router-qa-decision-context.json --pretty`
- `python scripts\artifact_index.py incremental`
- `python scripts\artifact_index.py validate`

Boundary:
- Additive review/routing fields only.
- No ticker-card mutation into canon, no portfolio/canon/SQL-canon apply, no approval inference, no capital deployment, no paper/live/brokerage/account action, and no money movement.

## 2026-06-05 deployment-state contract migration dependency

Randall asked to slim duplicated deployment-state fields after XOM showed `workflow_state = REPAIR`, `machine_state = BENCH`, and `action_state = DO NOT TOUCH` in one status answer.

Plan owner: `06. Playbooks/Project Continuity/Deployment State Contract Migration.md`.

WF77 role:
- Migrate `scripts/ticker_intelligence_card.py` and `scripts/finance_intelligence_state.py` early so ticker/status answers use one canonical state plus reason.
- Preserve raw legacy fields as trace context until compatibility proof is complete.
- Keep source-open and authority boundaries unchanged; a cleaner state label does not make a ticker deployable or approval-ready.

Acceptance addition:
- Ticker cards rebuild cleanly and finance-intelligence status answers can render compact states such as `XOM: DO_NOT_TOUCH / repair_mode_active / in band but not deployment-ready` without losing raw-context proof.
