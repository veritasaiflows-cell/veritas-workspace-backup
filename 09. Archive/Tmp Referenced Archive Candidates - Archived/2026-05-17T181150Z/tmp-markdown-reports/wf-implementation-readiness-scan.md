# WF44-WF47 Implementation Readiness Scan

Generated: 2026-05-09 MST  
Scope: inspection-only scan of scripts/tests/artifacts likely touched by WF44-WF47. No canonical finance notes, portfolio/deployment state, config/auth/channel/network settings, or trade/action surfaces were edited.

## Quick live-state observations

- `tmp/dashboard-data.json` already carries `deployment_summary.promotion_review=['ETN']` and `today_action.promotionReview`, but the JS renderer does not render that section in the Overview action card, deployment strip, deployment overview, or trigger header.
- `tmp/dashboard-data.json` does **not** carry `daily_review` or `market_intelligence` blocks, while `tmp/daily-review-objects-post-close.json` and `tmp/market-intelligence-events-post-close.json` exist and are decision-relevant.
- `tmp/run-summary-post-close.json` still has `status=ok` with `execution.chain_status=running`, `chain_status_normalized=false`, `chain_exit_code=null`; `tmp/run-chain-post-close.json` is terminal `status=ok`, `exit_code=0`, tail completed through `daily_review_objects.py`.
- `tmp/postmarket-snapshot.json` and `tmp/daily-executive-brief.json` currently say `canonical_mutation_allowed=true`; `tmp/run-summary-post-close.json` and `tmp/postclose-brief-input.json` say scheduled post-close canonical mutation is disabled/review-only.
- Current test check: `python scripts\test_run_summary_tail_order.py` fails because expected tail is stale; `python scripts\test_market_intelligence_event_router.py`, `python scripts\test_daily_review_objects.py`, and `python scripts\test_artifact_index.py` pass.

---

## WF44 - Command Center Decision Object Visibility and Truth Alignment

### Files likely touched

Primary implementation:
- `scripts/dashboard_payload.py`
- `scripts/dashboard-template.html`
- `scripts/dashboard-js/04-overview.js`
- `scripts/dashboard-js/11-triggers.js`
- likely a new/extended dashboard JS panel file if the decision queue deserves its own tab/section
- `scripts/generate_dashboard.py` only if template injection or JS bundle list needs wiring

Tests/validators:
- `scripts/test_dashboard_acceptance.py`
- `scripts/validate_dashboard_state.py`
- possibly `scripts/dashboard_truth_lint.py`

Artifacts to inspect after run:
- `tmp/dashboard-data.json`
- `tmp/veritas-command-center.html`
- `tmp/dashboard-validation.json`
- `tmp/dashboard-acceptance-report.json`
- `tmp/daily-review-objects-post-close.json`
- `tmp/market-intelligence-events-post-close.json`
- `tmp/deployment-readiness-surface.json`
- `tmp/trigger-sheet.json`
- `tmp/deployment-check.json`

### Smallest safe implementation slice

1. **Promotion-review visibility only**
   - Render `today_action.promotionReview` between Deployable and Almost in `renderTodayAction()`.
   - Add `promotion_review` cells/rows to `renderDeploymentStrip()` and `renderDeploymentOverview()`.
   - Add `summary.promotion_review` to `renderTriggerSheet()` header chips.
   - Extend `test_dashboard_acceptance.py` to assert rendered/payload visibility, not just `deployment_summary` data presence.

2. **Decision Queue payload/rendering**
   - Add a compact `daily_review` block in `dashboard_payload.py` by reading current-window `tmp/daily-review-objects-*.json`.
   - Add a compact `market_intelligence` block by reading current-window `tmp/market-intelligence-events-*.json`.
   - Render counts, escalations, capital recommendations, owner questions, and authority boundaries. Keep it explicitly review-only.
   - Acceptance should fail if current-window artifacts exist but are neither ingested nor visibly warned as missing.

3. **Dual-layer owner/risk rendering**
   - Preserve owner repair/do-not-touch from `deployment-readiness-surface.json`/trigger layer while showing below-stop as a secondary risk flag from `deployment-check.json`.
   - Minimum target: LMT renders do-not-touch/repair plus below-stop; CVX/LNG/RTX remain below-stop watch-lane monitor unless owner data says otherwise.

### Tests/validators to run

- `python scripts\test_dashboard_acceptance.py`
- `python scripts\validate_dashboard_state.py --write`
- `python scripts\dashboard_truth_lint.py`
- `python scripts\generate_dashboard.py`
- Direct artifact inspection for `tmp/dashboard-data.json` and `tmp/veritas-command-center.html` strings: `Promotion review`, `Daily review`, `Market intelligence`, `ETN`, `owner approval`, `review-only`.

### Dependencies/collision risks

- Collides with WF46 through `dashboard_run_summary_consumer.py`/run-summary warning visibility if both add trust alerts.
- Collides with WF45 if source-freshness vocabulary is added to dashboard payload at the same time; keep WF44 display fields narrow unless classifier schema has landed.
- Decision queue panel depends on `market_intelligence_event_router.py` and `daily_review_objects.py` tail artifacts, so run-summary finalization/tail-order ambiguity will affect freshness claims.

### Exact no-go / stop lines

- Do not call the Command Center decision-complete if a non-empty `promotion_review` bucket is absent from Overview and Trigger Sheet summary.
- If current-window review/event artifacts exist but are not ingested, the dashboard must show a missing-decision-objects warning or fail validation.
- Owner repair/do-not-touch state must not be hidden by below-stop technical state.
- Do not let rendered UI imply canonical note mutation, trade execution, portfolio mutation, deployment mutation, or owner approval.

### Recommended helper role/thinking

- Helper: dashboard implementation helper + independent code-review auditor.
- Thinking: medium for promotion visibility; medium-high for decision queue + dual-layer owner/risk precedence.

---

## WF45 - Shared Stale Source Fail-Soft Classifier

### Files likely touched

Primary implementation:
- new `scripts/source_freshness_classifier.py`
- new `scripts/test_source_freshness_classifier.py`
- `scripts/dashboard_core.py`
- `scripts/dashboard_payload.py`
- `scripts/dashboard_validation.py`
- `scripts/validate_dashboard_state.py`
- `scripts/run_summary_refresh.py`
- `scripts/deployment_readiness_surface.py`
- later: `scripts/market_intelligence_event_router.py`, `scripts/daily_review_objects.py`, `scripts/artifact_index.py`

Adjacent consumers:
- `scripts/workbook_export.py` already has `source_freshness`-like summary vocabulary; avoid divergent meanings.
- `scripts/pipeline_state_consistency_check.py`
- `scripts/test_artifact_index.py`
- `scripts/test_market_intelligence_event_router.py`
- `scripts/test_daily_review_objects.py`

### Smallest safe implementation slice

1. **Pure helper + fixtures only**
   - Add classifier vocabulary and ordering: `fresh`, `current`, `manual_dependency`, `partial`, `stale`, `contradictory`, `missing`.
   - Unit-test timestamp staleness, required/optional behavior, manual dependency, contradiction, and fail-closed authority defaults.
   - No producer behavior changes yet.

2. **Dashboard trust read-only projection**
   - Map existing `dashboard_core.assess_source()` output into classifier blocks while preserving current dashboard behavior.
   - Add `source_freshness` block to `tmp/dashboard-data.json` and/or `tmp/dashboard-validation.json` without loosening `exec_freshness`.

3. **Run summary/deployment propagation**
   - Embed `source_freshness` in run summaries.
   - Replace `deployment_readiness_surface.map_macro_gate()` accidental `freshness == 'clean'` check with intentional classifier/trust mapping. Current live `exec_freshness=usable_with_caution` and `macro_gate=DEGRADED` is conservative; preserve or tighten, never loosen.

4. **Review objects/router/index after schema stabilizes**
   - Add compact source-freshness context to market-intelligence and daily-review artifacts.
   - Extend SQLite index only after upstream schema is stable.

### Tests/validators to run

- `python scripts\test_source_freshness_classifier.py`
- `python scripts\test_dashboard_acceptance.py`
- `python scripts\validate_dashboard_state.py --write`
- `python scripts\test_run_summary_tail_order.py`
- `python scripts\test_market_intelligence_event_router.py`
- `python scripts\test_daily_review_objects.py`
- `python scripts\test_artifact_index.py`
- `python scripts\pipeline_state_consistency_check.py`

### Dependencies/collision risks

- Should not be mixed with WF44 panel work unless only adding read-only payload fields; otherwise dashboard payload/render churn compounds.
- Should follow or explicitly account for WF46, because run-summary terminal-vs-running contradiction is one of the classifier's canonical `contradictory/current` examples.
- `artifact_index.py` schema changes are lower priority and should wait until source-freshness schema is stable.
- `regime_scoring_refresh.py` canonical note mutation is an ownership decision, not a classifier implementation detail; do not bury it here.

### Exact no-go / stop lines

- Any classifier or downstream consumer that sets `canonical_note_mutation_allowed: true` from freshness alone.
- Any capital recommendation that removes `owner_approval_required: true` or implies `autonomous_apply`.
- Any SQLite index consumer treating `tmp/veritas-artifact-index.sqlite` as canonical authority.
- Any Command Center badge that displays green/ok while critical required sources are stale, missing, contradictory, or manual-dependent without a visible caveat.
- Any attempt to persist the FRED key or other secrets in workspace files, artifacts, logs, tests, or notes.
- Any broad scheduled note mutation before the owner boundary for `regime_scoring_refresh.py` is resolved.
- Any run summary with `status: ok` and terminal presentation language while `execution.chain_status` is still `running` and not explicitly normalized or classified as pending-finalization.

### Recommended helper role/thinking

- Helper: contract-design implementation helper, then code-review auditor.
- Thinking: high for classifier contract and consumer propagation; medium for isolated fixture tests.

---

## WF46 - Run Summary Finalization Semantics Gate

### Files likely touched

Primary implementation:
- `scripts/run_summary_refresh.py`
- `scripts/run_finance_refresh_chain.py`
- `scripts/chain_manifest.py`
- `scripts/dashboard_run_summary_consumer.py`
- `scripts/test_run_summary_tail_order.py`

Adjacent artifacts/tests:
- `tmp/run-summary-*.json`
- `tmp/run-chain-*.json`
- `tmp/dashboard-data.json`
- `tmp/veritas-command-center.html`
- `scripts/deployment_readiness_surface.py`
- `scripts/test_dashboard_acceptance.py`

### Smallest safe implementation slice

1. **Fix stale tail-order test first**
   - Current manifest tail includes `deployment_readiness_surface.py`, `market_intelligence_event_router.py`, `daily_review_objects.py` after `run_summary_refresh.py` and `dashboard_run_summary_consumer.py`.
   - Update `test_run_summary_tail_order.py` to match the current manifest and allowed pending tail in `normalized_chain_status()`.

2. **Normalize self-observation safely**
   - Teach `normalized_chain_status()` that pending/running post-summary tail may include `dashboard_run_summary_consumer.py`, `deployment_readiness_surface.py`, `market_intelligence_event_router.py`, and `daily_review_objects.py` when `run_summary_refresh.py` is the only running step.
   - Rebuild `tmp/run-summary-post-close.json` and verify `execution.chain_status` becomes terminal/normalized if chain state is otherwise safe.

3. **Visible ambiguity fallback**
   - If true terminal normalization is not possible, update `dashboard_run_summary_consumer.py` to warn when `chain_status_normalized=false` or `chain_status` is non-terminal.

### Tests/validators to run

- `python scripts\test_run_summary_tail_order.py`
- `python scripts\run_summary_refresh.py --window post-close`
- `python scripts\dashboard_run_summary_consumer.py --window post-close`
- `python scripts\deployment_readiness_surface.py --window post-close`
- `python scripts\test_dashboard_acceptance.py`
- `python scripts\validate_dashboard_state.py --write`
- Inspect `tmp/run-summary-post-close.json` execution block and dashboard alert text.

### Dependencies/collision risks

- Best done before WF44 decision queue and WF45 classifier propagation because both rely on honest run-window trust state.
- Touches `dashboard_run_summary_consumer.py`, which WF44 may also touch for trust alerts.
- If `run_finance_refresh_chain.py` writes terminal state only after run-summary step, then run summary can only self-normalize or require a second finalization pass. Avoid redesigning the chain in this first slice unless necessary.

### Exact no-go / stop lines

- Top-level `status=ok` is not enough if execution status remains `running` or unnormalized.
- Do not call scheduled chains fully clean if the run-summary artifact carries unresolved execution ambiguity.
- Do not widen cron/scheduled autonomy until finalization semantics are boring and terminal.

### Recommended helper role/thinking

- Helper: focused debugging/implementation helper with chain-manifest awareness.
- Thinking: medium-high because the bug is semantic/tail-order, not syntax.

---

## WF47 - Post-Close Authority Vocabulary Reconciliation

### Files likely touched

Primary implementation:
- `scripts/market_data_utils.py` (`canonical_note_mutation_gate` currently returns true on clean dashboard validation)
- `scripts/postmarket_snapshot.py`
- `scripts/daily_executive_brief.py`
- `scripts/summary_brief_packet.py`
- `scripts/run_summary_refresh.py`
- `scripts/pipeline_state_consistency_check.py` or a new cross-artifact authority validator

Adjacent scripts using the same gate and requiring care:
- `scripts/premarket_snapshot.py`
- `scripts/weekly_intelligence_brief.py`
- `scripts/weekly_macro_snapshot.py`

Artifacts to compare:
- `tmp/run-summary-post-close.json`
- `tmp/postclose-brief-input.json`
- `tmp/postmarket-snapshot.json`
- `tmp/daily-executive-brief.json`

### Smallest safe implementation slice

1. **Vocabulary-only reconciliation for post-close summaries**
   - Decide and encode that dated dashboard summary writes are generated review/archive notes, not canonical finance-note mutation.
   - Set post-close `postmarket_snapshot.py` and `daily_executive_brief.py` outputs to `consumer_posture='review_only'` or `generated_dashboard_archive`, with `canonical_mutation_allowed=false` when run summary says scheduled windows are fail-closed.
   - Keep writing generated Markdown only if explicitly considered non-canonical/dashboard archive; otherwise write machine sidecar/review-only path.

2. **Cross-artifact validator**
   - Add a check that downstream artifacts cannot claim wider authority than `run-summary-<window>.json`.
   - Candidate home: `pipeline_state_consistency_check.py` if it already owns cross-surface consistency, or a small dedicated validator called from the chain after relevant artifacts exist.

3. **Shared gate refactor later**
   - If modifying `canonical_note_mutation_gate`, avoid accidentally changing premarket/weekly behavior without tests. Prefer adding a window/context-specific wrapper first.

### Tests/validators to run

- New/updated authority test, e.g. `python scripts\test_postclose_authority.py` or updated `python scripts\pipeline_state_consistency_check.py`
- `python scripts\postmarket_snapshot.py`
- `python scripts\daily_executive_brief.py`
- `python scripts\summary_brief_packet.py --window post-close`
- `python scripts\run_summary_refresh.py --window post-close`
- `python scripts\test_market_intelligence_event_router.py`
- `python scripts\test_daily_review_objects.py`
- `python scripts\test_artifact_index.py`

### Dependencies/collision risks

- Collides with WF46 because `run_summary_refresh.py` is the authority ceiling and also has execution ambiguity.
- Collides with WF45 if authority fields are embedded in a new `source_freshness` block; keep authority vocabulary separate from freshness classification.
- Changing `canonical_note_mutation_gate()` globally would affect premarket, weekly intelligence, and weekly macro outputs. This is high blast radius; use targeted post-close reconciliation first.

### Exact no-go / stop lines

- No artifact may claim canonical note mutation is allowed when the run summary says scheduled windows are fail-closed.
- Generated note paths must not be confused with owner approval or canonical portfolio/deployment mutation.
- No generated output implies trade execution, portfolio mutation, deployment mutation, or owner approval.

### Recommended helper role/thinking

- Helper: authority-contract auditor + bounded implementation helper.
- Thinking: high, because vocabulary drift can silently widen permissions.

---

## Cross-WF dependency order recommendation

1. **WF46 first**: fix run-summary tail/finalization semantics and stale test expectations. This removes a known trust contradiction that WF44/WF45 would otherwise need to special-case.
2. **WF47 second or parallel with review**: reconcile post-close authority vocabulary before downstream dashboards ingest and display those artifacts more prominently.
3. **WF44 third**: render promotion review and decision queue once run finalization and authority fields are trustworthy enough to display.
4. **WF45 in staged slices**: start with pure classifier/tests at any time, but defer broad consumer propagation until WF46/WF47 are stable.

## Global no-go lines for all slices

- No canonical finance note mutation.
- No portfolio/deployment mutation.
- No config/auth/channel/network edits.
- No trade/action execution.
- No owner approval inference from clean validation, fresh data, generated packets, or indexed artifacts.
- No secret persistence in workspace files, generated artifacts, logs, or tests.
