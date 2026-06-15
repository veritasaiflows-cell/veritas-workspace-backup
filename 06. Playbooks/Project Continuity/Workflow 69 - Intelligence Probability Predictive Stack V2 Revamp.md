# Workflow 69 - Intelligence Probability Predictive Stack V2 Revamp

## Objective

Upgrade the data-gathering, intelligence, probability-readiness, and predictive-analysis workflow stack into a V2 architecture that is explicit, validator-backed, and authority-safe.

This workflow does **not** authorize probability claims, model-driven decisions, portfolio mutation, paper execution, live execution, brokerage/account action, or owner-approval inference.

## Opened

2026-05-19 22:54 MST after Randall requested all WFs related to data gathering/intelligence/probability/predictive analysis and a V2 phased upgrade in orchestration mode.

## Related workflows

Primary V2 stack:

- WF16 - Research Automation and Canonical Freshness Hardening
- WF21 - Recurring Source Bundle and Review Window Pilot
- WF26 - Fresh External Intelligence and Geopolitical Verification Pilot
- WF27 - Predictive Analytics and Forecasting Readiness
- WF36 - Workspace Retrieval Index and SQLite Knowledge Layer
- WF41 - Market Intelligence Event Intake and Materiality Router
- WF42 - Capital Deployment Recommendation Object
- WF43 - State History and Review Outcome Retention
- WF45 - Shared Stale Source Fail-Soft Classifier
- WF51 - Daily Fresh Intelligence and Price Trend Promotion Branch
- WF52 - Earnings Date Source Confidence and Event Calendar Roll-Forward Automation
- WF53 - Sector Expansion Coverage and Correlation Proof Layer
- WF54 - Ticker Monitoring Performance Analytics v1
- WF55 - Probability Readiness and Outcome Retention Gate
- WF58 - Dashboard Freshness, Entry Bands, Capital Recommendations, and Discrepancy Automation
- WF60 - Research Freshness and Opportunity Cron Automation
- WF61 - Small Mid Cap Regime Feed and Candidate Sleeve
- WF65 - Fundamental Metrics Tracker V1
- WF66 - Why-Aware Recommendation Packet Evidence Bridge
- WF68 - Intraday Alert Engine and Advisor Surface
- WF63/WF67 - paper endpoint/readiness and paper-only feedback telemetry dependencies

## Current state

Status: **Phase 0 complete / Phase 1 control-plane validation started**.

Helper-lane note: broad helper lanes timed out and produced no trusted artifacts. Main session completed bounded Phase 0 artifacts directly and created a validator. Failed helper output is not treated as proof.

Implemented artifacts:

- `tmp/wf-v2-intelligence-stack-inventory.json`
- `legacy tmp artifact tombstoned in state/tmp-lifecycle-deletion-tombstone.json (wf-v2-intelligence-stack-upgrade-plan.md)`
- `scripts/wf_v2_intelligence_stack_validator.py`
- `tmp/wf-v2-intelligence-stack-validation.json`

Validation proof:

- `python -m py_compile scripts\wf_v2_intelligence_stack_validator.py`
- `python scripts\wf_v2_intelligence_stack_validator.py --write`
- latest result: `status=ok`, `critical_count=0`, `warning_count=0`, `authority_clean=true`, 22/22 required WFs present.

## V2 phase plan

### Phase 0 - Stack inventory and authority lock

Status: **complete**.

Acceptance:

- all related workflow owners named
- authority flags hard-false for trade/account action, portfolio mutation, probability claims, predictive-model authority, and canonical mutation from this artifact
- WF55 `NOT_READY` remains explicit
- WF27 blocked-from-live-influence remains explicit

### Phase 1 - Data contract and freshness normalization

Status: **started / next implementation pass**.

Goal:

Every intelligence object should carry a normalized minimum contract:

- as-of timestamp
- source tier / official-source posture
- freshness class
- provenance path
- missing/partial/contradictory/manual-required status
- authority block
- degradation reason

Targets:

- WF41 event packets
- WF45 freshness classifier
- WF52 catalyst/date confidence objects
- WF60/WF61 research freshness feeds
- WF65/WF66 evidence packets and why-stack
- WF68 advisor packets

Acceptance:

- missing/contradictory/stale evidence fails soft, not green
- generated packets cannot imply approval, execution, or mutation
- V2 validator can scan a representative artifact bundle

### Phase 2 - Evidence ingestion and provenance spine

Status: pending.

Goal:

Make official/company/SEC/source evidence machine-visible without hiding manual-required fields.

Acceptance:

- bridge-present is not bridge-reconciled
- official-source gaps downgrade confidence
- manual-required fields remain visible in downstream packets

### Phase 3 - Outcome/state-history V2

Status: pending.

Goal:

Connect recommendations, alerts, paper telemetry, owner decisions, and realized outcomes in append-only form.

Acceptance:

- no hindsight rewriting
- incomplete/superseded/voided outcomes are non-scoreable
- WF68 alert outcome links can append only after owner/action evidence exists

### Phase 4 - Analytics readiness without probability claims

Status: pending.

Goal:

Produce descriptive readiness analytics only.

Acceptance:

- no win-rate, expected return, model-readiness, deployment-performance, or predictive-performance claims while WF55 is `NOT_READY`
- WF55 validator remains the gate

### Phase 5 - Predictive sandbox V2

Status: blocked pending Phase 4/WF55 readiness.

Goal:

Test baselines on observable-state questions only.

Acceptance:

- research-only outputs under `tmp/`
- no hidden buy/sell/rank target
- no portfolio/paper/live action from model output

### Phase 6 - Advisor/intraday integration

Status: pending.

Goal:

Feed V2 intelligence contracts into WF68 advisor packets and WF67 paper request artifacts where explicitly scoped.

Acceptance:

- quiet `NO_REPLY` preserved
- stale/current-but-not-intraday-fresh no-fires preserved
- paper route still requires exact scoped request, fresh kill switch, guard validation, and audit log

### Phase 7 - Reporting, cron hardening, and closeout

Status: pending.

Goal:

Schedule, validate, report, and close V2 with repeated-window proof.

Acceptance:

- no critical validators
- degraded/warning states visible
- Active Workflows reflects current V2 status

## Stop lines

- No live trading, live endpoints, live credentials, money movement, account mutation, or brokerage action.
- No paper execution outside WF67 exact scoped request + fresh kill switch + guard validation + audit log.
- No probability, win-rate, expected-return, predictive-performance, or model-readiness claims while WF55 is `NOT_READY`.
- No model-driven portfolio actions.
- No generated artifact becomes canon without exact gated apply authority and validation.

## Next action

Implement Phase 1 artifact-bundle contract validation across representative WF41/WF45/WF52/WF60/WF61/WF65/WF66/WF68 outputs, then run an independent QA pass with a smaller, file-bounded scope.

## 2026-05-20 Expansion Note

Randall opened two adjacent lanes while keeping WF69 moving:

- WF70 - Official Company Source Capture and Reconciliation: makes official company release / SEC exhibit / presentation / transcript evidence machine-visible for all tracked operating-company equities, starting with ETN/VRT and then broadening in parallel batches.
- WF71 - Veritas OS Department Staff and Skill Ownership Model: defines staff-lane ownership so WF69/WF70 and other major work can run in parallel without ownership collisions.

WF69 should continue immediately with data analytics readiness work while WF70 improves source freshness and WF68 expands Alpaca market-data inputs:

1. Phase 1: validate the minimum data contract across current representative artifacts.
2. Phase 2: consume WF70 official-source capture status as a provenance/freshness input, not as approval.
3. Phase 2/6 crossfeed: consume WF68 Alpaca market-data spine status (quote/trade/bar/spread/freshness/calendar) as intraday evidence metadata, not as predictive model authority.
4. Phase 3: keep state-history/outcome work append-only and no-hindsight.
5. Phase 4: produce descriptive analytics readiness only: alert frequency, stale-data rate, band-touch/reclaim counts, paper fill/slippage tracking, and source-gap counts. No probability, win-rate, expected-return, model-readiness, deployment-performance, or predictive-performance claims while WF55 remains `NOT_READY`.
## WF72 Phase 4 SQL Truth-Spine Link - 2026-05-22 00:12 MST
- WF72 Phase 4 extended `scripts/artifact_index.py` into a derived SQLite truth-spine prototype at `tmp/veritas-artifact-index.sqlite`. It indexes source-artifact lineage, validator runs, authority flags, Today decision rows, canon proposal/apply staging rows, market events, daily review objects, and capital recommendations. This supports WF69 Phase 1/2 data-contract and evidence-provenance goals but does not authorize probability claims, canon ownership, canon mutation, portfolio mutation, paper/live execution, or owner-approval inference. Proof artifact: `tmp/wf72-phase4-sql-truth-spine-prototype.json/.md`.

## 2026-06-12/13 Historical Regime Analog Slice

WF69 now has a concrete Phase 4-adjacent analytics-readiness slice through WF55:

- `scripts/historical_regime_event_library.py`
- `tmp/historical-regime-event-library.json/.md`
- validator integration through `scripts/probability_readiness_validator.py`
- readiness-report integration through `scripts/probability_readiness_report.py`

The slice turns past regimes/events into review-only analog/base-rate context: 1970s oil/stagflation, Volcker tightening, 1987 crash, Gulf War/recession shock, 1994 rate shock, 1998 liquidity stress, dot-com bust, GFC, 2011 sovereign/fiscal stress, COVID crash/rebound, 2022 inflation/rate shock, and 2023-2024 soft-landing/broadening.

Current proof: 12 events, 10 small-vs-large comparison rows, 0 critical probability-readiness validator findings. Two existing warning-class readiness gaps remain: state-history timestamp gap above 48 hours and degraded sector-expansion-board context.

Use: base-rate/stress-context support for current questions such as rate stabilization and small/mid-cap broadening.

Blocked: calibrated probability, predictive-performance claims, deployment ranking, return-projection claims, capital deployment, paper/live/account action, canon/portfolio mutation, and owner approval inference.
