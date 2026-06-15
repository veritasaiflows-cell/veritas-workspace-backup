# Workflow 51 - Daily Fresh Intelligence and Price Trend Promotion Branch

## Objective

Add the missing daily freshness branch Randall asked for: combine price-trend evidence, watchlist promotion candidates, and fresh macro/company news into review-only promotion intelligence without widening execution authority.

This workflow should answer each day:
- which watchlist names are improving enough to deserve a promotion packet?
- which strong candidates are weakening or losing thesis quality?
- which macro, sector, company, or catalyst news changed the probability setup?
- which price-trend changes are real enough to raise or lower promotion odds?
- what should move to owner review, and what should stay watch-only?

## User request trigger

Opened after Randall's 2026-05-09 request:
- GS was omitted from the weekly summary despite being an almost-deployable tactical financial candidate.
- The watchlist needs a stronger path for promoting high-quality candidates.
- Daily price trends should be tracked and used as evidence for market-direction probability and promotion readiness.
- Daily news and fresh content should keep macro and thesis truth current.

## Current state

The workspace already has several useful pieces:
- `scripts/technical_refresh.py` and `scripts/band_refresh.py` track daily price/MA/band posture.
- `tmp/deployment-readiness-surface.json` ranks deployable / promotion-review / almost-deployable / repair states.
- `scripts/market_intelligence_event_router.py` and `scripts/daily_review_objects.py` produce review-only daily intelligence packets.
- `06. Playbooks/Watchlist Promotion Candidate Packet Contract.md` defines the safe watchlist -> candidate packet -> human review -> owner decision path.
- WF38 established sector-expansion and promotion-review governance.
- WF43 defines the durable append-only history path needed before trend/probability claims become trustworthy over time.

But the system is not yet complete enough:
- daily price trend is not yet converted into a durable promotion-probability evidence history
- broad external news intake is not yet live; WF41 v1 is artifact-derived and explicitly does not crawl broad web/news sources
- candidate-packet generation is not yet part of a daily watchlist promotion branch
- probability language is not yet evidence-calibrated against append-only outcomes

## Scope

Build a review-only branch that can eventually run daily after the finance refresh chain:
1. collect daily price-trend deltas for active and watchlist names
2. combine trend deltas with band state, moving-average posture, catalyst windows, and regime fit
3. ingest approved fresh intelligence sources from the WF26 source-tier map
4. emit watchlist promotion candidate packets for names that improved materially
5. emit downgrade / thesis-review alerts for names where news or price action worsened the setup
6. route outputs to daily review objects and the Promotion Review Queue without canonical mutation

## Out of scope

- no trade execution
- no automatic buy/sell/trim/add decisions
- no automatic Trigger Sheet, Portfolio Snapshot, or Watchlist mutation
- no autonomous watchlist-to-deployable promotion
- no social-rumor ingestion or unattributed news chains
- no probability claims that imply statistical forecasting before history/outcome calibration exists

## Required inputs

Canonical / owner surfaces:
- `02. Markets/Watchlist.md`
- `03. Portfolio/Deployment Trigger Sheet.md`
- `03. Portfolio/Technical Entry and Invalidation Sheet.md`
- `03. Portfolio/Portfolio Snapshot.md`
- `07. Risk/Risk Rules.md`
- `04. Research/Coverage Universe.md`

Machine / artifact surfaces:
- `tmp/technical-refresh.json`
- `tmp/band-proposals.json`
- `tmp/deployment-readiness-surface.json`
- `tmp/market-intelligence-events-post-close.json`
- `tmp/daily-review-objects-post-close.json`
- `tmp/positioning-ranking.json`
- `tmp/regime-scores.json`
- `data/state-history/state-history-v1.jsonl` after WF43 durable proof succeeds

Source policy:
- `06. Playbooks/Fresh External Intelligence Source and Sleeve Map - WF26 Phase 1.md`
- `06. Playbooks/Watchlist Promotion Candidate Packet Contract.md`

## Proposed outputs

Initial review-only outputs:
- `tmp/daily-price-trend-signals.json`
- `tmp/watchlist-promotion-candidates.json`
- `tmp/fresh-intelligence-thesis-alerts.json`
- optional human review note under `01. Dashboards/Review-Only Briefs/`

Future durable output after WF43 proof:
- append selected daily state snapshots and later outcomes to `data/state-history/state-history-v1.jsonl`

## Promotion signal framework

A name may be raised for promotion review when several of these improve together:
- thesis remains intact or improves from fresh primary/credible secondary evidence
- regime score improves or stays high
- price moves into or near a written entry band
- trend stack improves without becoming overextended
- stop/invalidation is defined and not violated
- catalyst window is clean or explicitly manageable
- sector/correlated-sleeve checks do not breach risk rules
- it beats opportunity cost versus current deployable names

A name must stay watch-only or downgrade when:
- it is above band and becoming a chase
- it is below stop or in repair mode
- fresh news creates thesis uncertainty
- catalyst timing is unresolved or too close
- it worsens concentration in an already crowded sleeve
- source trust is partial/stale/manual enough to cap confidence

## Probability language boundary

Use probability language only as directional review support until enough state/outcome history exists.

Allowed now:
- “higher promotion readiness”
- “improving setup probability”
- “trend and catalyst evidence improved”
- “review priority increased”

Not allowed yet:
- precise win probabilities
- price targets presented as forecast certainty
- model-driven deployment authority
- automated portfolio action from predicted direction

## Initial implementation phases

### Phase 1 - Design and residue audit
- Audit existing scripts for reusable price-trend, band, ranking, and event-routing fields.
- Define the exact JSON schema for daily price-trend and promotion-candidate outputs.
- Confirm where GS-style almost-deployable names should appear in daily/weekly summaries.

### Phase 2 - Daily price-trend signal artifact
- Add a read-only script that compares current technical state to prior state/history.
- Emit trend deltas: in-band, above-band, below-stop, MA stack change, volatility/extension flags, and near-catalyst flags.
- Do not mutate canonical notes.

### Phase 3 - Watchlist promotion candidate generator
- Build on the existing candidate packet contract.
- Generate review-only packets for names that meet evidence thresholds.
- Fail closed when owner notes conflict or required gates are missing.

### Phase 4 - Fresh intelligence intake expansion
- Extend WF41 from artifact-derived events toward approved external source-tier intake.
- Prioritize primary company releases, SEC/IR, official macro data, and credible wire/major financial sources.
- Preserve source freshness, attribution, and confidence ceiling.

### Phase 5 - State-history and outcome calibration
- After WF43 durable append/validate proof, append daily signal state and later owner outcomes.
- Use history to evaluate whether trend/fresh-intel signals improve promotion review quality.
- Keep this as review analytics, not an execution model.

## Acceptance gates

- GS and other almost-deployable candidates are explicitly represented in the daily/weekly summary logic when they are material.
- Watchlist promotion candidate packets can be generated without canonical mutation.
- Daily price trend signals are source-linked and review-only.
- Fresh intelligence events carry source freshness/provenance and confidence ceilings.
- Outputs route to daily review objects / Promotion Review Queue with owner approval required.
- No language implies automatic promotion, sizing, execution, or account action.

## Current priority

This is a newly opened branch. It should start as design + schema + reuse audit, not immediate autonomy.

Best first implementation move:
- spawn a bounded implementation-readiness scan to map existing fields in `technical-refresh`, `band_refresh`, `deployment-readiness-surface`, `daily_review_objects`, `market_intelligence_event_router`, `candidate_packet_validator`, and `state_history_capture` into the Phase 1 schema.

## WF56 handoff boundary

WF51 can produce trend/fresh-intelligence evidence and diagnostic candidate readiness.
It does not own applying ticker promotion/demotion or canonical-status moves.

When a candidate needs a real lane/status change, hand off to WF56 for a typed review-only proposal artifact with:
- current and proposed canonical status tuple
- source freshness and missing-evidence checks
- sector/correlation context from WF53
- owner-conflict check across canonical notes and `tmp/portfolio-config.json`
- `owner_decision_required=true`, `owner_approval_granted=false`, and `apply_allowed=false`

Production candidate generation remains deferred until trust-context, sector/correlation, owner-conflict, and outcome-history gates are stronger.

## Phase 1 synthesis - 2026-05-09

Helper lanes completed:
- `legacy tmp artifact tombstoned in state/tmp-lifecycle-deletion-tombstone.json (wf51-phase1-schema-reuse-scan.md)`
- `legacy tmp artifact tombstoned in state/tmp-lifecycle-deletion-tombstone.json (wf51-phase1-verifier-risk-scan.md)`

Main conclusion:
- WF51 should start with a read-only daily price-trend signal artifact, not a promotion engine.
- Existing artifacts already carry most current-state inputs: technical posture, entry-band state, deployment readiness, regime score, event routing, and daily review-object posture.
- True day-over-day / outcome-aware trend deltas remain limited until WF43 durable state-history append/validate proof succeeds.
- GS-style almost-deployable visibility is currently adequate, but it should become a durable shortlist visibility contract so material almost-deployable names do not disappear only because a stronger peer ranks higher.

Phase 2 approved implementation target:
- Add `scripts/daily_price_trend_signals.py` as a read-only producer.
- Add `scripts/test_daily_price_trend_signals.py` as the authority/vocabulary/schema guard.
- Emit `tmp/daily-price-trend-signals.json` only.

Phase 2 must include:
- review-only authority header
- no canonical / portfolio / deployment mutation
- no trade execution
- owner approval required and not granted
- source-artifact provenance and timestamps
- directional trend/readiness labels only
- `history_status=missing|partial|available|stale` with honest `unknown` deltas when WF43 history is unavailable
- material shortlist visibility for `PROMOTION REVIEW` and `ALMOST DEPLOYABLE` names, including GS-style secondary candidates

Phase 2 must not include:
- watchlist-promotion candidate generation
- broad web/news ingestion
- calibrated probability, expected return, win-rate, or deploy-probability claims
- daily-review integration or chain wiring before standalone validation

## Phase 2 closeout - 2026-05-09

Implemented:
- `scripts/daily_price_trend_signals.py`
- `scripts/test_daily_price_trend_signals.py`
- `tmp/daily-price-trend-signals.json`

Current artifact behavior:
- emits current-state directional price-trend / readiness signals only
- preserves review-only authority fields at top level and per signal
- carries source-artifact provenance and source-freshness context
- keeps `history_status=missing` while `data/state-history/state-history-v1.jsonl` is absent
- leaves all prior-state deltas `unknown` until WF43 history is usable
- surfaces material `PROMOTION REVIEW` and `ALMOST DEPLOYABLE` names in `material_shortlist`, including GS-style secondary candidates
- caps macro-degraded names so technical improvement does not become increased promotion readiness under degraded macro conditions
- fails closed for `BELOW_STOP` / below-stop cases

Verifier issue found and fixed:
- the first Phase 2 output leaked raw source wording with sizing/action language (`tactical add`, `disciplined size`); this was sanitized and added to forbidden-vocabulary tests before closeout

Proof:
- `python -m py_compile scripts\daily_price_trend_signals.py scripts\test_daily_price_trend_signals.py`
- `python scripts\test_daily_price_trend_signals.py`
- `python scripts\daily_price_trend_signals.py --window post-close`
- direct JSON inspection confirmed no forbidden probability/sizing/execution vocabulary, GS shortlist visibility, macro-degraded readiness capped, below-stop blocked, and missing-history deltas unknown
- independent verifier wrote `legacy tmp artifact tombstoned in state/tmp-lifecycle-deletion-tombstone.json (wf51-phase2-final-verifier.md)` with verdict `close`

## Phase 3 synthesis - 2026-05-10

Helper lanes completed:
- `legacy tmp artifact tombstoned in state/tmp-lifecycle-deletion-tombstone.json (wf51-phase3-candidate-generator-readiness.md)`
- `legacy tmp artifact tombstoned in state/tmp-lifecycle-deletion-tombstone.json (wf51-phase3-authority-risk-audit.md)`

Main decision:
- Defer production daily watchlist-promotion candidate generation.
- Current evidence can support guard hardening and dry-run blocked/needs-research diagnostics, but not `candidate_review_ready` production packets.

Original blocker:
- canonical owner notes said JPM and ETN were already owner-approved deployable-now, while machine artifacts still classified them as promotion/almost-deployable states

Phase 3A root-cause finding:
- ETN machine config still carried stale `workflow_state=ALMOST` after owner promotion.
- JPM had two drifts: stale machine config still carried `workflow_state=PROMOTION REVIEW`, and canonical notes still described the 2026-05-06 in-band close even though the refreshed 2026-05-08 technical artifact showed JPM below the formal band and close to invalidation.

Remaining reasons production candidates stay deferred:
- macro/source trust is degraded / review-required
- sector and correlated-sleeve checks are not independently machine-proven
- state history is missing, so trend evidence is current-state only
- candidate validator is now stronger, but production generation still lacks computed owner-conflict, sector/correlation, and trust-context wiring

Current shortlist expected behavior after Phase 3A fix:
- ETN: no `candidate_review_ready`; owner-promoted and in band at the trigger-sheet layer, but downstream readiness remains capped by trust/fallback state and review-only authority
- JPM: no `candidate_review_ready`; owner approval remains recorded, but current price is below the formal band, so trigger readiness fails closed until reclaim or explicit band review
- GS: `needs_research`; visible, but not ready because macro-degraded, JPM-secondary/peer context, and sector/correlation proof gaps remain
- GOOG: `blocked`; direct Tech cap / above-band / macro degraded
- MSFT: `blocked`; below-stop / repair and artifact conflict
- NVDA: `blocked`; above-band, near catalyst, crowded sleeve / Tech cap, macro degraded

Next safe Phase 3A implementation:
- harden candidate-packet guard/validation first
- add forbidden authority-vocabulary checks
- add system trust-gate awareness
- add owner/machine conflict check requirements
- require sector/correlation evidence to be computed or explicitly fail closed
- do not implement production generator, daily chain integration, or canonical note mutation yet

## Status

- status: WF51 repair/hardening phase closure-ready after false-green authority repairs and chain proof / production candidate generation still deferred
- opened: 2026-05-09
- owner: Veritas main session
- authority: review-only
- phase 1 proof: schema/reuse and verifier/risk helper lanes wrote `legacy tmp artifact tombstoned in state/tmp-lifecycle-deletion-tombstone.json (wf51-phase1-schema-reuse-scan.md)` and `legacy tmp artifact tombstoned in state/tmp-lifecycle-deletion-tombstone.json (wf51-phase1-verifier-risk-scan.md)`; main synthesis wrote `legacy tmp artifact tombstoned in state/tmp-lifecycle-deletion-tombstone.json (wf51-phase1-synthesis.md)`
- phase 2 proof: producer/test/artifact landed and final verifier wrote `legacy tmp artifact tombstoned in state/tmp-lifecycle-deletion-tombstone.json (wf51-phase2-final-verifier.md)` with close verdict
- phase 3 proof: readiness and authority-risk helpers wrote `legacy tmp artifact tombstoned in state/tmp-lifecycle-deletion-tombstone.json (wf51-phase3-candidate-generator-readiness.md)` and `legacy tmp artifact tombstoned in state/tmp-lifecycle-deletion-tombstone.json (wf51-phase3-authority-risk-audit.md)`; main synthesis wrote `legacy tmp artifact tombstoned in state/tmp-lifecycle-deletion-tombstone.json (wf51-phase3-synthesis.md)`
- phase 3A proof: guard helper changed `scripts/candidate_packet_validator.py` and `scripts/test_candidate_packet_validator.py`; main-session root-cause fix changed `scripts/deployment_check.py`, added `scripts/test_deployment_check_owner_state.py`, reconciled ETN/JPM in `tmp/portfolio-config.json`, and wrote `legacy tmp artifact tombstoned in state/tmp-lifecycle-deletion-tombstone.json (wf51-phase3a-root-cause-fix.md)`
- latest proof: `08. Audits/WF51 Closure Hardening Implementation Audit - 2026-05-10.md`; `python scripts\run_finance_refresh_chain.py post-close` completed successfully after `daily_price_trend_signals.py` manifest wiring; direct inspection confirmed ETN `stable/unchanged`, JPM `weakening/decreased`, `top_improving_tickers=[]`, and no stale `candidate_review_ready` / `auto_approved` / `deployable_now_authorized=true` residue
- next pass: do not implement production generator yet; if WF51 continues, start with a dry-run blocked/needs-research diagnostic design that wires trust context and sector/correlation proof explicitly
- blocked by: WF43 durable append/validate proof for calibrated probability/history layer; WF49/FRED runtime for cleaner macro source freshness; source-tier expansion policy before broad web/news ingestion; sector/correlation artifact for stronger candidate-packet readiness

## Closure hardening - 2026-05-10

Independent QA correctly challenged WF51 as not close-ready while daily trend signals could falsely imply increased promotion readiness for ETN/JPM and while stale promotion-review residue still contained auto-approval semantics.

Repairs landed:
- `DEPLOYABLE NOW` / owner-promoted names can no longer emit promotion-readiness `increased` or top-improving promotion signals.
- Reclaim-only / below-band names are treated as weakening, not improving promotion candidates.
- Degraded system trust caps readiness direction and adds explicit `system_trust_review_required` blockers.
- The live `PROMOTION REVIEW` shortlist assertion is now conditional on the source group being non-empty.
- `promotion_review_check.py` is now review-only / non-authorizing; stale JPM residue was regenerated without `auto_approved`, `authorization_required=false`, or `deployable_now_authorized=true`.
- `daily_price_trend_signals.py` is wired into all finance windows after deployment readiness and before market-intelligence routing / daily review objects.

Closeout boundary:
- WF51 may close for this review-only signal/guard phase.
- Production candidate generation remains deferred.
- No probability, deployment, portfolio mutation, owner-approval, or trade/account authority was added.
