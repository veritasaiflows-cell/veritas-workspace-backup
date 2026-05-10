# WF High-Grade Recommendations Program Plan - 2026-05-09

## Objective

Move the Veritas finance OS toward high-grade, owner-gated capital-deployment recommendations without crossing into autonomous trading, portfolio mutation, canonical note mutation, or inferred owner approval.

## Main-session role

Veritas main session owns:
- orchestration and phase selection;
- helper-lane contracts;
- audit/QC/test ownership;
- final synthesis and queue movement;
- small bounded patches where spawning would add friction.

Helper lanes support; they do not own final queue state.

## Authority boundary

Allowed during this program:
- generated review artifacts;
- dashboard/reporting display improvements;
- validators and tests;
- fail-soft trust classification;
- read-only event/recommendation packets;
- append-only historical state infrastructure.

Blocked unless Randall explicitly approves:
- trade execution or account action;
- automatic position sizing or portfolio mutation;
- canonical finance-note mutation;
- deployment-state or promotion/demotion mutation;
- config/auth/channel/network changes;
- credential storage or secret echoing;
- treating clean data or a clean recommendation packet as owner approval.

## Adjudicated phase sequence

The planning helper recommended `WF40 -> WF44 -> WF45 -> WF46 -> WF47 -> WF41 -> WF42 -> WF43`.

The implementation-readiness helper challenged that sequence because WF46 and WF47 are upstream truth contracts: if run summaries can say `ok` while execution is `running`, or if downstream artifacts claim wider authority than run summaries allow, then rendering those artifacts more prominently in WF44 can amplify bad trust signals.

Final main-session judgment: **WF46 and WF47 should precede the broad WF44 decision-queue rendering pass**, while a very small WF44 promotion-review visibility patch may remain safe if it does not ingest disputed authority fields.

## Phase 0 - WF40 security/runtime proof gate

Status: active monitoring / scheduled repeat pending.

Current state:
- The 2026-05-09 scheduled security job originally failed closed.
- Randall approved Telegram as setup-pending exception.
- `TOOLS.md` and `scripts/workspace_governance_truth_check.py` were updated so Telegram setup-pending is warning-grade, not critical.
- Queue wording was reconciled.
- Manual controlled wrapper proof passed at `2026-05-10T01:47:00Z` with `proof_status=ok`, `audit_status=warning`, `audit_stop_line=false`, and `errors=[]`.
- WF40 still needs the next ordinary scheduled cron run to repeat cleanly before full closure.

Acceptance gate:
- fresh scheduled proof;
- `proof_status=ok`;
- `artifact_fresh_for_runner=true`;
- `audit_stop_line=false`;
- `errors=[]`;
- remaining warnings triaged as operator-gated or accepted local-only posture.

## Phase 1 - WF46 Run Summary Finalization Semantics Gate

Goal: make run summaries terminal and boring.

Why first:
- `tmp/run-summary-post-close.json` can say top-level `status=ok` while `execution.chain_status=running` and `chain_status_normalized=false`.
- Downstream trust and dashboard rendering should not build on ambiguous terminal-state semantics.

Likely files:
- `scripts/run_summary_refresh.py`
- `scripts/run_finance_refresh_chain.py`
- `scripts/chain_manifest.py`
- `scripts/dashboard_run_summary_consumer.py`
- `scripts/test_run_summary_tail_order.py`

Smallest slice:
1. Fix stale tail-order expectations in `test_run_summary_tail_order.py`.
2. Normalize safe self-observation behavior in run-summary execution state.
3. If terminal normalization cannot be guaranteed, surface explicit ambiguity downstream.

Acceptance proof:
- `python scripts\test_run_summary_tail_order.py`
- `python scripts\run_summary_refresh.py --window post-close`
- `python scripts\dashboard_run_summary_consumer.py --window post-close`
- inspect `tmp/run-summary-post-close.json` for terminal/normalized execution or explicit warning;
- relevant dashboard validation/tests remain clean.

## Phase 2 - WF47 Post-Close Authority Vocabulary Reconciliation

Goal: make post-close authority fields coherent across artifacts.

Why second:
- Some downstream generated outputs can imply `canonical_mutation_allowed=true` while the run summary and postclose brief input are fail-closed/review-only.
- WF42 recommendation objects must inherit clear authority vocabulary.

Likely files:
- `scripts/postmarket_snapshot.py`
- `scripts/daily_executive_brief.py`
- `scripts/summary_brief_packet.py`
- `scripts/market_data_utils.py`
- `scripts/run_summary_refresh.py`
- `scripts/pipeline_state_consistency_check.py` or new targeted validator

Smallest slice:
1. Define generated review/archive write vs canonical finance-note mutation.
2. Prevent post-close downstream artifacts from claiming wider authority than run summary permits.
3. Add cross-artifact authority validator.

Acceptance proof:
- post-close artifacts agree on review-only/canonical-write boundaries;
- validator passes;
- no artifact implies trade execution, portfolio mutation, deployment mutation, or owner approval.

## Phase 3 - WF44 Command Center Decision Object Visibility

Goal: make the Command Center decision-complete after upstream trust contracts are stable.

Likely files:
- `scripts/dashboard_payload.py`
- `scripts/dashboard-js/04-overview.js`
- `scripts/dashboard-js/11-triggers.js`
- `scripts/dashboard-template.html` / dashboard JS panel files
- `scripts/test_dashboard_acceptance.py`

Smallest safe slices:
1. Promotion-review visibility: render ETN and future names as `Promotion review`, not deployable or almost.
2. Decision Queue panel: ingest/render daily review objects and market-intelligence escalations.
3. Dual-layer owner/risk display: preserve repair/do-not-touch owner state while showing below-stop technical facts.

Acceptance proof:
- dashboard data and rendered HTML include promotion review, daily review, market intelligence, owner approval/review-only language;
- acceptance tests fail if generated decision objects exist but are hidden;
- `validate_dashboard_state.py --write`, `test_dashboard_acceptance.py`, and `dashboard_truth_lint.py` pass.

## Phase 4 - WF45 Shared Stale Source Fail-Soft Classifier

Goal: create shared source trust vocabulary and fail-soft behavior.

Why after WF46/WF47 initial slices:
- run-summary contradiction and authority conflicts are canonical examples that classifier consumers must handle correctly.

Likely files:
- new `scripts/source_freshness_classifier.py`
- new `scripts/test_source_freshness_classifier.py`
- `scripts/dashboard_core.py`
- `scripts/dashboard_payload.py`
- `scripts/dashboard_validation.py`
- `scripts/run_summary_refresh.py`
- `scripts/deployment_readiness_surface.py`
- later: event router, daily review objects, artifact index

Smallest safe slices:
1. Pure helper + tests only.
2. Dashboard trust projection.
3. Run summary/deployment propagation.
4. Review-object/router/index propagation only after schema stabilizes.

Acceptance proof:
- classifier tests pass;
- downstream surfaces degrade honestly for fresh/current/manual_dependency/partial/stale/contradictory/missing;
- no consumer infers canonical mutation or owner approval from freshness.

## Phase 5 - WF41 Market Intelligence Event Intake and Materiality Router

Goal: make daily fresh-intelligence packets reliable and review-only.

First action:
- audit existing `scripts/market_intelligence_event_router.py` against WF41 rather than building a duplicate router.

Acceptance proof:
- packets include materiality, route, urgency, source tier/trust, blocked reason, and owner review requirement;
- no canonical mutation, thesis mutation, deployment mutation, or trade execution.

## Phase 6 - WF42 Capital Deployment Recommendation Object

Goal: produce decision-grade but owner-gated `deploy / wait / reject / review` packets.

First action:
- compare current `daily_review_objects.py` capital recommendation output against WF42 contract and fill only real gaps.

Acceptance proof:
- every recommendation has evidence provenance, risk/invalidation, source freshness, confidence, recommended action, and `owner_approval_required=true`;
- all mutation/execution permissions false.

## Phase 7 - WF43 State History and Review Outcome Retention

Goal: build append-only point-in-time state and outcome retention for later predictive analytics.

Acceptance proof:
- append-only schema and no-rewrite validator;
- known-at-time facts separated from later realized outcomes;
- modeling remains disabled.

## Operator-gated sidecars

### WF48 - Regime Scoring Mutation Ownership Decision

Decision required later:
- bless direct scheduled mutation of `02. Markets/Regime Scoring Matrix.md`, or
- change scheduled runs to write proposal artifacts only.

Recommended safer default: proposal artifact + owner-gated/manual apply.

### WF49 - FRED Runtime Environment Persistence

Decision/action required later:
- rotate exposed FRED key outside chat;
- configure runtime environment safely without writing secrets to workspace;
- verify child scripts inherit key without leaking it.

Until then, FRED-dependent outputs should stay manual_dependency/partial as appropriate.

## Phase reporting template

After each phase, report in webchat:
- phase name and status;
- files changed;
- artifacts generated;
- tests/validators run and result;
- findings and blockers;
- authority/QC result;
- next phase and helper-lane plan.
