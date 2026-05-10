# Stale Source Fail-Soft Hardening Plan - 2026-05-09

## Scope

This plan defines the next finance-chain hardening phase after the XOM repair-mode/dashboard-validator cleanup. The job is not to widen autonomy. The job is to make stale, partial, missing, manual, and contradictory upstream evidence visible enough that downstream review surfaces degrade honestly instead of presenting fake-green states.

Workflow under review:
- `scripts/run_finance_refresh_chain.py` windows and `scripts/chain_manifest.py` manifests.
- Dashboard trust/freshness production through `scripts/dashboard_core.py`, `scripts/dashboard_payload.py`, `scripts/dashboard_validation.py`, and `scripts/validate_dashboard_state.py`.
- Final run-state surfaces through `scripts/run_summary_refresh.py`, `scripts/dashboard_run_summary_consumer.py`, and `tmp/run-summary-*.json`.
- Deployment/review surfaces through `scripts/deployment_readiness_surface.py`, `scripts/market_intelligence_event_router.py`, and `scripts/daily_review_objects.py`.
- Derived retrieval/index layer through `scripts/artifact_index.py`, `scripts/test_artifact_index.py`, and Workflow 36.
- Regime ranking mutation through `scripts/regime_scoring_refresh.py` and `02. Markets/Regime Scoring Matrix.md`.

Current safe automation phase: scheduled artifact generation plus scheduled review-surface generation. Canonical note mutation, capital deployment, portfolio state mutation, and owner decisions remain gated/manual.

Recommended next phase: add a machine-readable stale-source classifier and fail-soft downgrade contract before any further scheduler autonomy. The classifier may support read-only gating decisions only.

## Current Trust/Freshness Logic

### Existing source freshness and warning logic

`dashboard_core.py` already has the strongest source-level freshness logic:
- `SOURCE_SPECS` defines critical sources and required paths for market, policy, credit, breadth, technical, deployment, earnings, and portfolio config.
- `assess_source()` emits per-source fields: `status`, `fresh`, `tags`, `issues`, `manual_fields`, `raw_status`, `generated_at`, `age_h`, and `stale_after_hours`.
- Current source statuses include `fresh`, `usable_with_caution`, `partial`, `stale`, and `missing`.
- Session-aware freshness tightens market/technical/deployment thresholds during pre-open/open/post-close windows.
- Known caution cases are already captured for manual dependencies, mixed dates, fallback credit sources, warning notes, timing-sensitive earnings alerts, and missing required fields.

Current live evidence:
- `tmp/dashboard-data.json` has `exec_freshness: usable_with_caution` because manual/mixed-date macro dependencies are visible.
- `tmp/dashboard-validation.json` is clean: `overall: clean`, `critical: 0`, `warning: 0`, `info: 0`, `warnings: []`.
- `tmp/dashboard-validation.json` has `stale_after_hours: 8` and is consumed by deployment readiness.

Gap: dashboard validation can be clean while execution freshness is only usable-with-caution. That is safe if visible, but downstream language must not translate clean validation into clean source trust.

### Current run-summary logic

`run_summary_refresh.py` currently:
- Checks required window outputs for `missing`, `failed`, and `stale` relative to the chain attempt start time.
- Reads `tmp/dashboard-validation.json`, `tmp/dashboard-acceptance-report.json`, `tmp/workbook-export-manifest.json`, and `tmp/run-chain-<window>.json`.
- Emits `status`, `stop_line`, `validation.exec_freshness`, `fallback_state`, `operator_action_required`, `next_action`, and `downstream` trust flags.
- Keeps `downstream.presentation_allowed: false` and `downstream.canonical_note_mutation_allowed: false` for scheduled windows.

Current live residue:
- `tmp/run-summary-post-close.json` says `status: ok`, `stop_line: false`, `validation.acceptance_passed: true`, and `validation.dashboard_validation_status: clean`.
- The same file still says `execution.chain_status: running`, `chain_status_raw: running`, `chain_status_normalized: false`, `chain_exit_code: null`, and `chain_status_reason: runtime state not safe to normalize`.
- `tmp/run-chain-post-close.json` now shows the actual chain is terminal: `status: ok`, `exit_code: 0`, `completed_at_utc: 2026-05-09T23:04:05Z`, and all 31 steps completed ok.

Interpretation: the run summary captured a finalizer self-observation gap. The chain later completed cleanly, but the persisted run summary did not re-finalize its `execution` block. This is not a data-source freshness failure; it is a run-finalization semantics failure that can make Command Center/run-summary consumers show a fake or confusing state.

### Current deployment/readiness degradation

`deployment_readiness_surface.py` currently:
- Reads `tmp/trigger-sheet.json`, `tmp/dashboard-validation.json`, `tmp/band-proposals.json`, and a selected `tmp/run-summary-*.json`.
- Converts stop lines to `SYSTEM HOLD`.
- Suspends `DEPLOYABLE NOW` when fallback is active or band-review debt exists.
- Degrades macro gate when validation is stale.
- Emits `system.canonical_note_mutation_allowed`, `system.presentation_allowed`, `system.macro_gate`, warning counts/codes, validation staleness, timestamp gaps, and grouped readiness buckets.

Current live evidence:
- `tmp/deployment-readiness-surface.json` has `system.macro_gate: DEGRADED`, `presentation_allowed: false`, and `canonical_note_mutation_allowed: false`.
- Summary counts: `DEPLOYABLE NOW: 0`, `PROMOTION REVIEW: 1`, `ALMOST DEPLOYABLE: 5`, `DO NOT TOUCH: 3`, `WATCH / RESEARCH NEEDED: 1`.

Gap: `map_macro_gate()` currently returns `CLEAN` only when `run_summary.validation.exec_freshness == "clean"`. Existing freshness vocabulary from `dashboard_core.py` / `run_summary_refresh.py` uses `ok`, `usable_with_caution`, `partial`, `stale`, and `missing`. The live `DEGRADED` macro gate is conservative and safe, but the vocabulary mismatch should be made explicit rather than accidental.

### Current review-only / owner-gated surfaces

`market_intelligence_event_router.py` currently emits:
- `consumer_posture: review_only`
- `canonical_mutation_allowed: false`
- `deployment_state_mutation_allowed: false`
- `trade_execution_allowed: false`
- `owner_review_required: true`

`daily_review_objects.py` currently emits:
- `consumer_posture: review_only`
- `canonical_mutation_allowed: false`
- `owner_approval_required_for_capital: true`
- per-capital recommendation `owner_approval_required: true`
- `known_gaps` explicitly stating fresh-intelligence routing is artifact-derived v1 only and canonical note mutation stays blocked.

Current live evidence:
- `tmp/market-intelligence-events-post-close.json` is review-only with owner review required.
- `tmp/daily-review-objects-post-close.json` is review-only, has `system.trust_level: review_required`, `macro_gate: DEGRADED`, and `owner_approval_required_for_capital: true`.

### Current derived index boundary

Workflow 36 and `artifact_index.py` establish `tmp/veritas-artifact-index.sqlite` as a derived retrieval/cache layer only. It indexes market-intelligence events, daily review objects, and capital recommendations, including review-only/owner-gated fields, but it must not become canonical truth for workflow, deployment, dashboard, portfolio, or capital decisions.

`test_artifact_index.py` already checks that indexed artifacts preserve:
- no canonical mutation permission,
- owner review required,
- no trade execution permission,
- owner approval required for capital recommendations.

### Current regime-scoring mutation boundary

`regime_scoring_refresh.py` writes both:
- derived JSON: `tmp/regime-scores.json`
- canonical/live note: `02. Markets/Regime Scoring Matrix.md`

That direct Markdown mutation is real canonical-note mutation inside a scheduled finance chain. The note itself says it is the canonical ranking source. This needs an explicit ownership decision before stale-source classification is considered complete.

## Proposed Classifier Contract

Create a small shared classifier module, likely `scripts/source_freshness_classifier.py`, and use it from existing producers instead of duplicating status interpretation. The classifier should produce a stable block that can be embedded in artifacts without granting apply permission.

### Classifier input

For each source/artifact:
- `source_key`: stable key, e.g. `market_state`, `policy_expectations`, `credit_spreads`, `breadth_state`, `technical_refresh`, `deployment_check`, `trigger_sheet`, `dashboard_validation`, `run_summary`, `market_intelligence_events`, `daily_review_objects`, `regime_scores`.
- `path`: workspace-relative source path.
- `required`: boolean.
- `criticality`: `critical`, `important`, or `context`.
- `owner_layer`: canonical owner or artifact owner.
- `generated_at_utc`: artifact timestamp if present.
- `file_mtime_utc`: filesystem fallback timestamp.
- `last_trading_day` / `as_of_date`: source data date when present.
- `status_raw`: raw upstream status, e.g. `ok`, `manual`, `needs_review`, `error`.
- `stale_after_hours`: explicit threshold.
- `required_fields`: dotted paths and labels.
- `manual_dependencies`: explicit field list.
- `freshness_notes`: source notes.
- `warnings`: warning notes/codes.
- `contradiction_refs`: optional cross-surface checks, e.g. pipeline-state consistency.

### Classifier output

Emit one normalized block per source:

```json
{
  "source_key": "market_state",
  "path": "tmp/market-state.json",
  "classification": "manual_dependency",
  "freshness_rank": 5,
  "usable_for_review": true,
  "usable_for_presentation": false,
  "usable_for_canonical_mutation": false,
  "stop_line": false,
  "generated_at_utc": "...",
  "age_hours": 0.4,
  "stale_after_hours": 24,
  "required": true,
  "criticality": "critical",
  "owner_layer": "artifact:scripts/market_state_refresh.py",
  "issues": ["Fed target range is manually maintained"],
  "tags": ["manual", "macro_manual_dependency"],
  "missing_fields": [],
  "contradictions": [],
  "confidence_ceiling": "review_required"
}
```

### Required classification vocabulary

Use one canonical vocabulary across `dashboard_core.py`, `run_summary_refresh.py`, `deployment_readiness_surface.py`, `market_intelligence_event_router.py`, `daily_review_objects.py`, `artifact_index.py`, and tests:

1. `fresh`
   - Artifact exists, timestamp is inside its freshness window, required fields are present, raw status is clean, and no manual/fallback/contradiction flags are present.
   - Allowed: review surfaces and presentation candidate language, subject to window policy.
   - Not allowed by itself: canonical mutation or capital action.

2. `current`
   - Artifact exists and is timely, but is an inherently current snapshot whose raw status may not equal `ok` vocabulary, or whose source is current but not independently verified enough to call `fresh`.
   - Example: live run-chain status says terminal `ok`, but run-summary execution block needs re-finalization.
   - Allowed: review surfaces with visible caveat.

3. `stale`
   - Artifact exists but its `generated_at_utc`, `last_trading_day`, or source data date exceeds `stale_after_hours` / source-specific calendar window.
   - Required critical source: block or degrade to `SYSTEM HOLD` / `review_required` depending on consequence.
   - Non-critical source: keep review surface but mark `presentation_allowed: false` and add operator action.

4. `partial`
   - Artifact exists but required fields are missing, upstream raw status is warning/partial/needs_review, source mode is fallback/mixed, or only part of the expected source set loaded.
   - Allowed: review-only route with explicit issues.
   - Not allowed: clean badge, deployable-now promotion, canonical mutation, presentation-ready PDF/deck.

5. `missing`
   - Required artifact missing or unreadable.
   - Critical required source: stop line / blocked run summary.
   - Optional source: degrade event count and include source gap in `known_gaps`.

6. `contradictory`
   - Two or more trusted sources disagree on a material state family, timestamp order, ticker state, owner boundary, or run terminal state.
   - Examples: trigger sheet says positive while deployment check says negative; run summary says `execution.chain_status=running` after run-chain is terminal; Command Center says ok while run-summary says blocked.
   - Required critical contradiction: stop line until reconciled.
   - Non-critical contradiction: review-only, warning-grade, owner action required.

7. `manual_dependency`
   - Source is current enough but depends on manual or non-persisted inputs.
   - Examples: Fed target range manual field, FedWatch/FOMC distribution missing, FRED key not inherited by runtime, manual note-owned portfolio config.
   - Allowed: review-only with caveat.
   - Not allowed: fake-green validation, autonomous canonical mutation, or capital recommendation without owner approval.

### Severity mapping

Recommended normalized ordering:

```python
CLASSIFICATION_ORDER = {
    "fresh": 0,
    "current": 1,
    "manual_dependency": 2,
    "partial": 3,
    "stale": 4,
    "contradictory": 5,
    "missing": 6,
}
```

Trust ceilings:
- Worst source <= `current`: `trust_level` may be `clean` only if no owner/manual caveat exists.
- Worst source == `manual_dependency`: `trust_level=review_required`, no presentation/canonical mutation.
- Worst source == `partial` or `stale`: `trust_level=review_required` or `blocked` depending on criticality.
- Worst source == `contradictory` or critical `missing`: `stop_line=true`.

### Required downstream degradation fields

Every generated review artifact should carry a compact block:

```json
"source_freshness": {
  "overall_classification": "manual_dependency",
  "trust_level": "review_required",
  "stop_line": false,
  "presentation_allowed": false,
  "canonical_note_mutation_allowed": false,
  "capital_action_allowed": false,
  "owner_review_required": true,
  "sources": [...],
  "operator_actions": [...]
}
```

Do not allow any consumer to infer permission from absence of warnings. Permission fields must be explicit and fail-closed.

## Integration Boundaries

### Canonical note ownership

Preserve these ownership boundaries:
- Markdown notes remain the canonical owner layer where the workspace says they are canonical.
- `tmp/*.json`, `tmp/veritas-artifact-index.sqlite`, dashboards, run summaries, daily review objects, market-intelligence event packets, and workbook exports are generated review artifacts unless a specific owner-gated apply procedure says otherwise.
- `tmp/veritas-artifact-index.sqlite` remains derived/cache-only under Workflow 36. It may make retrieval faster; it may not become the source of workflow, deployment, dashboard, portfolio, or capital truth.
- `02. Markets/Regime Scoring Matrix.md` is currently canonical for priority ranking. Because `regime_scoring_refresh.py` directly mutates it, either this mutation must be explicitly blessed as an owned scheduled canonical update, or the chain should be changed in a later implementation pass to write a proposal artifact first and require owner/apply review before note mutation.

### Capital deployment boundary

Preserve Workflow 42:
- Capital deployment recommendation objects may gather evidence and assemble owner-review packets.
- They must never execute trades, submit orders, move funds, automatically size positions, mutate portfolio posture, or treat a clean packet as approval.
- `daily_review_objects.py` and `artifact_index.py` should continue asserting owner approval required for every capital recommendation.
- Any `fresh/current` classification only improves evidence confidence; it is not approval.

### Finance-chain integration sequence

Recommended integration order:
1. Build classifier as read-only helper and unit-test it independently.
2. Use classifier inside dashboard trust output first; keep current behavior as baseline.
3. Feed classifier summary into `run_summary_refresh.py` and `deployment_readiness_surface.py`.
4. Feed source-freshness block into `market_intelligence_event_router.py` and `daily_review_objects.py`.
5. Extend `artifact_index.py` to index source-freshness/trust fields only after upstream schema stabilizes.
6. Only then decide whether any canonical-note mutation flow can move from manual to gated apply helper.

## Workflow Items to Add

Recommended workflow/control-surface actions:

1. Open a dedicated workflow for stale-source classifier implementation.
   - Recommended: open as the next hardening workflow.
   - Acceptance: shared classifier module, vocabulary tests, dashboard/run-summary/deployment integration, and no widening of canonical mutation or capital permissions.

2. Open/update workflow for run-summary finalization semantics.
   - Recommended: open as separate quick implementation item or include as Slice 1 of the classifier workflow.
   - Reason: live `tmp/run-summary-post-close.json` retains `execution.chain_status=running` while `tmp/run-chain-post-close.json` is terminal ok.
   - Acceptance: a post-tail or re-finalization step must make persisted run-summary execution state match the terminal chain, or explicitly classify the mismatch as `contradictory/current_pending_finalization` with visible warning.

3. Open/update workflow for regime scoring mutation ownership.
   - Recommended: open explicitly; do not bury it inside stale-source work.
   - Reason: `regime_scoring_refresh.py` mutates `02. Markets/Regime Scoring Matrix.md`, which the note declares canonical ranking source.
   - Decision needed: keep scheduled auto-mutation as approved canonical owner behavior, or change to proposal artifact + gated note apply.

4. Open/update workflow for FRED runtime environment persistence.
   - Recommended: open operator/runtime follow-up, not a finance-script secret workaround.
   - Reason: FRED key is not persistently inherited by OpenClaw runtime, but secrets must not be stored in workspace files or committed artifacts.
   - Acceptance: runtime environment inheritance is verified live without exposing or writing the key; finance artifacts show manual/fallback state honestly until fixed.

5. Update Command Center truth-alignment follow-up after the separate audit completes.
   - Recommended: do not duplicate the separate Command Center audit; add an explicit dependency from stale-source classifier to its findings.
   - Acceptance: Command Center badges must distinguish `clean validation`, `usable-with-caution sources`, `manual dependency`, `stale`, `partial`, `contradictory`, and `blocked` instead of collapsing them into a single green state.

6. Update existing tests and validators in the same implementation workflow.
   - Extend `scripts/test_run_summary_tail_order.py` or replace it with a current manifest-aware test because the chain tail now includes `market_intelligence_event_router.py` and `daily_review_objects.py` after `deployment_readiness_surface.py`.
   - Extend `scripts/test_market_intelligence_event_router.py` and `scripts/test_daily_review_objects.py` to assert `source_freshness` propagation and fail-closed permissions.
   - Extend `scripts/test_artifact_index.py` after schema stabilization to confirm indexed trust fields preserve owner-gated boundaries.

## Risks/Stop Lines

Stop lines for implementation:
- Any classifier or downstream consumer that sets `canonical_note_mutation_allowed: true` from freshness alone.
- Any capital recommendation that removes `owner_approval_required: true` or implies `autonomous_apply`.
- Any SQLite index consumer treating `tmp/veritas-artifact-index.sqlite` as canonical authority.
- Any Command Center badge that displays green/ok while critical required sources are stale, missing, contradictory, or manual-dependent without a visible caveat.
- Any attempt to persist the FRED key or other secrets in workspace files, artifacts, logs, tests, or notes.
- Any broad scheduled note mutation before the owner boundary for `regime_scoring_refresh.py` is resolved.
- Any run summary with `status: ok` and terminal presentation language while `execution.chain_status` is still `running` and not explicitly normalized or classified as pending-finalization.

Key risks:
- Vocabulary drift: `clean`, `ok`, `fresh`, `usable_with_caution`, and `DEGRADED` currently mean different things across scripts.
- False precision: a clean dashboard validator can mask usable-with-caution sources if consumers only read validation warnings.
- Authority drift: derived artifacts and SQLite retrieval can become de facto canonical if not labeled and tested.
- Hidden runtime dependency: FRED data may appear manually degraded even when scripts work in an interactive shell because the OpenClaw runtime does not inherit the key.
- Canonical mutation ambiguity: regime scoring is already mutating a canonical note from a scheduled chain.

## Acceptance Proof

Implementation is not complete until these checks pass:

1. Classifier unit tests
   - Fresh/current/stale/partial/missing/contradictory/manual_dependency fixtures.
   - Required-vs-optional source behavior.
   - Critical-vs-context degradation behavior.
   - Timestamp/date staleness windows, including market-session-sensitive windows.
   - Manual dependency and fallback-source fixtures.

2. Dashboard trust validation
   - `validate_dashboard_state.py --write` emits the same or stricter trust result for current live artifacts.
   - Dashboard validation can be `clean` while source freshness remains `manual_dependency`/`review_required`, and the distinction is visible.

3. Run-summary validation
   - `run_summary_refresh.py` cannot persist `status: ok` with an unexplained `execution.chain_status: running` after the chain state is terminal.
   - If self-observation is unavoidable during the finalizer step, the persisted artifact must either normalize after the tail or emit a visible `current`/`contradictory` classification and operator action.

4. Deployment/readiness validation
   - `deployment_readiness_surface.py` consumes normalized source freshness and keeps `DEPLOYABLE NOW` suspended when critical source trust is below clean.
   - `presentation_allowed` and `canonical_note_mutation_allowed` remain false unless explicitly owner-approved in a separate workflow.

5. Review-object/router validation
   - `market_intelligence_event_router.py` and `daily_review_objects.py` include source-freshness context and preserve review-only posture.
   - Existing owner-gated tests continue to pass.

6. Derived index validation
   - `scripts/test_artifact_index.py` passes.
   - If source-freshness fields are indexed, tests assert the index is retrieval/cache-only and does not authorize mutation, trading, or approval.

7. Cross-surface contradiction validation
   - `pipeline_state_consistency_check.py` remains in the chain before run summary.
   - Contradictions in action-state families become classifier `contradictory` signals, not buried warnings.

8. Command Center truth alignment
   - Command Center / dashboard badges visibly separate: validation clean, source freshness, run finalization, manual dependency, fallback use, and stop-line state.

Existing validators/tests to extend:
- `scripts/test_run_summary_tail_order.py`
- `scripts/test_market_intelligence_event_router.py`
- `scripts/test_daily_review_objects.py`
- `scripts/test_artifact_index.py`
- `scripts/test_dashboard_acceptance.py`
- `scripts/validate_dashboard_state.py`
- `scripts/pipeline_state_consistency_check.py`
- potentially add `scripts/test_source_freshness_classifier.py`

## Recommended Implementation Slices

### Slice 1 - Run-summary finalization repair

Goal: remove the current fake/confusing state where persisted run summary says `status: ok` while `execution.chain_status` says `running` after the chain is terminal.

Actions:
- Adjust `run_summary_refresh.py` / chain tail semantics so `tmp/run-summary-<window>.json` is re-finalized after downstream tail steps, or teach consumers to classify self-observed running states as `current_pending_finalization` and not as clean terminal execution.
- Update `test_run_summary_tail_order.py` so it matches current `chain_manifest.py`, including `market_intelligence_event_router.py` and `daily_review_objects.py` after `deployment_readiness_surface.py`.

Acceptance:
- Current window rerun produces a run summary whose `execution.chain_status` matches terminal `tmp/run-chain-<window>.json`, or visibly explains pending finalization.

### Slice 2 - Shared classifier module and tests

Goal: one vocabulary, one status-ordering model, no script-local reinterpretation.

Actions:
- Add `scripts/source_freshness_classifier.py`.
- Add `scripts/test_source_freshness_classifier.py`.
- Port `dashboard_core.py` logic into/onto the classifier without behavior loosening.

Acceptance:
- Fixture tests cover `fresh`, `current`, `stale`, `partial`, `missing`, `contradictory`, and `manual_dependency`.

### Slice 3 - Dashboard/run-summary/deployment propagation

Goal: downstream surfaces degrade using classifier output, not ad hoc warnings.

Actions:
- Embed `source_freshness` in `tmp/dashboard-data.json`, `tmp/dashboard-validation.json`, and `tmp/run-summary-*.json`.
- Fix vocabulary mismatch in `deployment_readiness_surface.py` so `macro_gate` is derived intentionally from classifier trust, not accidental `clean` vs `ok` mismatch.

Acceptance:
- Clean validation + manual dependency produces `review_required`, not fake green.
- Critical stale/missing/contradictory source produces stop line or system hold.

### Slice 4 - Review object and event router propagation

Goal: daily review packets carry trust context into owner decisions.

Actions:
- Add source freshness/trust fields to `market_intelligence_event_router.py` and `daily_review_objects.py` artifacts.
- Keep `consumer_posture=review_only`, `owner_review_required=true`, and capital owner approval required.

Acceptance:
- Tests verify source-freshness propagation and fail-closed permissions.

### Slice 5 - Derived index schema extension

Goal: make retrieval better without changing authority.

Actions:
- Extend `artifact_index.py` only after upstream source-freshness schema stabilizes.
- Index overall classification/trust level and source issues for query support.

Acceptance:
- `test_artifact_index.py` proves no indexed row can authorize mutation, trade execution, or owner approval bypass.

### Slice 6 - Regime-scoring ownership decision

Goal: resolve scheduled canonical-note mutation before treating regime scoring as hardened.

Options:
1. Keep `regime_scoring_refresh.py` as approved canonical owner for `02. Markets/Regime Scoring Matrix.md`, but document that ownership explicitly and add stale-source gates before note write.
2. Safer recommendation: change later implementation so the scheduled chain writes `tmp/regime-scores.json` plus a proposed Markdown patch/review artifact, and a separate owner-gated apply helper updates `02. Markets/Regime Scoring Matrix.md`.

Recommended: option 2 unless Randall explicitly blesses scheduled canonical mutation for this note.

### Slice 7 - FRED runtime environment follow-up

Goal: fix runtime data quality without leaking secrets.

Actions:
- Diagnose OpenClaw runtime environment inheritance separately.
- Do not store the FRED key in workspace files.
- Until fixed, classifier should emit `manual_dependency` or `partial` for affected FRED-dependent fields.

Acceptance:
- Live OpenClaw runtime can run the relevant FRED-dependent refresh with the key inherited, or artifacts clearly show fallback/manual state.

### Slice 8 - Command Center truth alignment

Goal: make the human-facing surface match the machine trust state.

Actions:
- Wait for the separate Command Center audit output.
- Then align badges and summaries so green means terminal chain + clean validation + acceptable source freshness, not merely zero dashboard warnings.

Acceptance:
- Command Center shows separate trust lines for validation, source freshness, run finalization, and owner-gated status.
