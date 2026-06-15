# Workflow 60 - Research Freshness and Opportunity Cron Automation

## Objective

Turn the research department operating model into scheduled, review-only freshness and opportunity lookup work without creating a second portfolio truth layer.

## Current State

Opened on 2026-05-12 after Randall asked how the Research Department Operating Model is being automated and requested workflows for cron-backed ticker freshness and opportunity lookup.

Implementation proof on 2026-05-13: `scripts/research_freshness_opportunity_review.py` v1 exists and wrote `tmp/research-freshness-opportunity-review.json` plus `.md` in a manual post-close run. The artifact is composition-only / review-only; all authority flags remain false. Current artifact status is `degraded` because `tmp/sector-expansion-board.json` is itself degraded, while required source freshness is still true.

QC fix on 2026-05-13: independent review found required JSON sources without usable timestamps could be treated as fresh. The composer now fails closed for required unstamped/unparseable/stale JSON and has a regression test for that case.

Scheduling integration attempted on 2026-05-13: existing weekday and Sunday research cron jobs were identified as the right periodic helper lane, but `openclaw cron edit` failed with a Gateway scope/pairing approval block. On 2026-05-14 Randall approved cron-edit scope, and the existing jobs were patched through the cron tool rather than by hand-editing the cron store.

Cron support is now scheduled using the existing proven scripts plus the WF60/WF61 composers:

- `Finance - Research Freshness and Opportunity Review` / job id `25aef99b-7b2b-40a9-823c-2cfff7d5493d` / weekdays 14:05 America/Phoenix / refreshes `macro_judgment_draft.py --write --validate` first, then runs `sector_expansion_board.py --window post-close`, `sector_dashboard_suite.py`, `ticker_monitoring_performance.py --window post-close`, `research_freshness_opportunity_review.py --window post-close`, `small_mid_cap_regime_feed.py --window post-close`, and `json_sql_promotion_index.py --write --write-md --validate`.
- `Finance - Sunday Research Opportunity Reset` / job id `5918839c-25a0-4220-8d4a-75f8e71b8e4e` / Sundays 09:35 America/Phoenix / refreshes `macro_judgment_draft.py --write --validate` first, then runs the same research sequence with `--window sunday` where applicable, followed by `json_sql_promotion_index.py --write --write-md --validate`. The macro judgment input and JSON-to-SQL promotion index are review-only context for research opportunity routing; they grant no portfolio/canon mutation, capital action, sizing, trade/account action, customer authority, SQL import authority, or owner approval.

Controlled proof after the patch passed on 2026-05-14. The weekday proof refreshed `tmp/research-freshness-opportunity-review.json/.md` at `2026-05-14T21:39:58Z` with `status=degraded` because `sector_expansion_board` remained degraded, and refreshed `tmp/small-mid-cap-regime-feed.json/.md` at `2026-05-14T21:40:03Z` with `status=ok`. Authority blocks remained false for canonical mutation, portfolio mutation, deployment/watchlist mutation, owner approval inference, probability/model deployment authority, sizing/allocation, capital action, and trade/account action. Remaining proof item: ordinary scheduled-repeat proof, especially the Sunday reset after the weekly chain.

Enhancement on 2026-05-15/16 after the sector-leadership research pass: the composer now emits `response_recommendation_digest` so main-session Veritas and the research handoff crons can embed the useful recommendation pattern in normal responses. The digest carries improving leadership, underexposed lanes, portfolio-review candidates, conditional-watch names, blocked/deferred names, and the required no-authority boundary sentence. It also carries forward manually promoted sector-expansion names from `tmp/portfolio-config.json` so PH/LIN/META/CME stay visible as portfolio-review-only candidates and ECL/NFLX/VMC/GE/WMB/TMUS stay visible as conditional watch/research monitors until fresher WF60/WF61 artifacts replace them. Current proof: `python scripts\research_freshness_opportunity_review.py --window post-close` wrote `tmp/research-freshness-opportunity-review.json` with `status=degraded`, required sources fresh enough, 16 candidates, and all mutation/trade/approval authority false.

Important clarification: `06. Playbooks/Project Continuity/Research Department Operating Model.md` is an archive candidate / duplicate surface. The active keeper is `06. Playbooks/Project Continuity/Workflow 9 - Research Department Operating Model.md`.

## Why this workflow exists

The current finance chain already refreshes many research-department inputs:

- macro / regime: `tmp/market-state.json`, `tmp/macro-regime.json`, `tmp/regime-scores.json`
- breadth / sectors: `tmp/breadth-state.json`, `tmp/sector-correlation-check.json`, `tmp/sector-expansion-board.json`
- coverage / catalyst state: `tmp/earnings-calendar.json`, `tmp/post-earnings-prep.json`, `tmp/post-earnings-note-targets.json`
- portfolio / deployment: `tmp/deployment-check.json`, `tmp/trigger-sheet.json`, `tmp/band-proposals.json`, `tmp/full-portfolio-view.*`
- proposal/review objects: `tmp/portfolio-mutation-proposals/current-capital-deployment-recommendations.json`, `tmp/finance-discrepancy-resolver.*`

What is still missing is a dedicated research-department freshness/opportunity control pass that says, in one place:

1. which tracked tickers are fresh enough for decision support
2. which tickers have stale thesis, catalyst, technical, or source-confidence state
3. which sectors are improving or underowned
4. which candidate packets should be requested next
5. which opportunities are review-only versus owner-decision-ready

## Automation design

### Mechanism

Cron-owned review packet, preferably after the existing post-close chain and after the Sunday weekly rebuild.

### Proposed schedules

- **Weekday post-close freshness/opportunity check:** after `Finance - Weekday Post-Close Review Refresh`, no earlier than 14:05 America/Phoenix.
- **Sunday research queue reset:** after `Finance - Sunday Weekly Printable Intelligence Refresh`, no earlier than 09:30 America/Phoenix.

### Read first

- `06. Playbooks/Cron Job Protocol.md`
- `06. Playbooks/Operating Procedures/Portfolio Truth Surface Ownership Procedure.md`
- `06. Playbooks/Project Continuity/Workflow 9 - Research Department Operating Model.md`
- `06. Playbooks/Project Continuity/Workflow 53 - Sector Expansion Coverage and Correlation Proof Layer.md`
- `06. Playbooks/Project Continuity/Workflow 54 - Ticker Monitoring Performance Analytics v1.md`
- `skills/veritas-macro-pass/SKILL.md`
- `03. Portfolio/Portfolio Snapshot.md`
- `03. Portfolio/Execution Board.md`
- `04. Research/Coverage and Watchlist.md`
- `07. Risk/Risk Rules.md`

### Execute in order

Initial implementation should use existing scripts before adding new ones:

1. `python scripts\run_finance_refresh_chain.py post-close` or rely on the already completed post-close chain.
2. `python scripts\macro_judgment_draft.py --write --validate`
3. `python scripts\sector_expansion_board.py --window post-close`
4. `python scripts\sector_dashboard_suite.py`
5. `python scripts\ticker_monitoring_performance.py --window post-close`
6. `python scripts\research_freshness_opportunity_review.py --window post-close`
7. `python scripts\small_mid_cap_regime_feed.py --window post-close`
8. `python scripts\json_sql_promotion_index.py --write --write-md --validate`
9. validate/inspect:
   - `tmp/macro-judgment-draft.json`
   - `tmp/sector-expansion-board.json`
   - `tmp/sector-dashboard-suite.html`
   - `tmp/ticker-monitoring-performance.json`
   - `tmp/ticker-monitoring-performance.md`
   - `tmp/research-freshness-opportunity-review.json`
   - `tmp/small-mid-cap-regime-feed.json`
   - `tmp/json-sql-promotion-index.json`
   - `tmp/json-sql-promotion-registry.json`
   - `tmp/json-sql-promotion-index.sqlite`
   - `tmp/full-portfolio-view-validation.json`
   - `tmp/finance-discrepancy-resolver.json`

### Output packet to add

Implement a new generated review-only packet if existing outputs are not enough:

- `tmp/research-freshness-opportunity-review.json`
- `tmp/research-freshness-opportunity-review.md`

Minimum fields:

- generated_at_utc
- market_data_as_of
- source_artifacts
- overall_status: ok / degraded / blocked
- ticker_freshness_queue
- stale_or_partial_research_items
- sector_opportunity_queue
- small_mid_cap_regime_feed_status
- candidate_packet_requests
- canonical_sync_candidates_review_only
- owner_decision_required
- authority block with every mutation/trade/approval field false

## Current data sufficiency judgment

Enough fresh data exists for **tracked large-cap / current watchlist freshness** and sector-level review-only opportunity routing.

Not enough exists yet for automatic small/mid-cap portfolio addition or allocation. Small/mid cap posture needs first-class regime feed data before it can become a real portfolio proposal source.

Current proof snapshot from 2026-05-12 artifacts:

- `tmp/market-state.json` status `ok`, last trading day `2026-05-12`
- `tmp/breadth-state.json` status `ok`, broad sector participation at 8/11 sectors above 50DMA
- equal-weight vs cap-weight ratio still deteriorating over 5d and 20d, so broadening is not clean enough to call a small/mid-cap green light
- `tmp/sector-expansion-board.json` status `degraded`, review-only, with Technology improving, multiple underexposed sectors, and promotion-review candidates CAT / GS / LLY / NVDA

## Stop lines

- No portfolio addition.
- No automatic promotion/demotion.
- No owner approval inference.
- No sizing, sleeve, cash, risk-rule, execution-entitlement, trade, or account action.
- No generated packet becomes canonical truth.
- Cron may generate review packets and candidate requests only.
- Any canonical note sync remains bounded to freshness/status fields and main-session review.

## Acceptance gates

- Existing scripts run cleanly or degrade honestly.
- Macro judgment draft exists and has validation `ok`, or research output labels the macro posture as missing/partial.
- JSON-to-SQL promotion index validates `ok`, or the research handoff labels it missing/partial.
- New cron job has a symmetrical Cron Job Protocol card.
- Output packet states source freshness and owner-gated authority clearly.
- Active Workflows names the monitor and proof surfaces.
- Any small/mid-cap signal is routed to Workflow 61, not directly into portfolio truth.
- SQLite remains a rebuildable derived lookup layer over JSON proof; it does not become canon, approval authority, capital-action authority, customer authority, SQL import authority, or paper/live/account authority.

## Backlog / not priority

Market-moving news intake pilot: Randall approved adding this to the queue on 2026-05-13 as **not priority**. Concept is a narrow review-only intraday news-awareness layer, not a live-news firehose: run a source-bundled market-moving event scan during market hours, rank only material items, and write `tmp/research-automation/intake-packets-*` / research review packets with source, freshness, affected tickers/sectors, thesis impact, confidence/downgrade, and explicit authority flags. Keep it behind WF58/WF60/WF61 stabilization unless Randall explicitly promotes it.

Stop lines for the pilot: no ungated canonical mutation, no portfolio action, no owner approval inference, no promotion/demotion, no cash/risk-rule/execution entitlement, no sizing/sleeve/sector-posture write outside exact approved gates, and no trade/account authority.

## Next action

Monitor the next ordinary weekday and Sunday scheduled runs. Treat `tmp/research-freshness-opportunity-review.*` as review-required when upstream sector/source artifacts are degraded, treat `tmp/small-mid-cap-regime-feed.*` as a research-routing feed only, and use `tmp/json-sql-promotion-index.sqlite` only as a derived lookup/control-plane index back to JSON proof. Main-session responses should use `response_recommendation_digest` when fresh, but no candidate may be promoted, sized, sleeved, added, approved, imported into SQL authority, or acted on from these outputs without a separate owner-gated proposal path.
