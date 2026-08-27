# Workflow 79 - Veritas Command Center V2 UI Infrastructure

## Objective
- Make Veritas Command Center the single polished local review surface for finance intelligence, PM state, automation health, deployment readiness, entry-band analysis, technical posture, and tool launchers.
- Keep proof/source detail available behind drill-downs, not cluttering the main UI.
- Preserve canonical owner notes and approved validators as truth authority; Command Center is presentation, routing, warning, and review infrastructure only.

## Product Standard
- First screen answers: what matters now, what is stale, what is blocked, what needs Randall approval, and what is safe to ignore.
- UI is dense, calm, and decision-oriented: status strips, tables, filters, tabs, badges, and action drawers over long narrative blocks.
- Warnings and stops must be visible immediately. Proof paths, source files, hashes, and validator detail stay in expandable panels or developer/tool drawers.
- Every panel shows freshness and authority posture in plain language: Fresh, Stale, Warning, Stop, Review Only, Needs Randall Approval.

## Phase Plan

### Phase 1 - V2 Foundation
- Reuse `apps/pm-control-cockpit` as the base local app or rename it after the first stable cut.
- Add a V2 source registry that groups finance, PM, deployment, entry-band, technical, automation, and tool-launch surfaces.
- Keep the existing local-only Node/TypeScript server pattern and read-only allowlisted data access.
- Acceptance: one local shell displays Command, Finance, PM, Automation, Deployment, Entry Bands, Technical, and Tools tabs with source freshness summarized but not visually noisy.

### Phase 2 - Entry-Band Contract And Drift Fix
- Build one normalized entry-band contract consumed by Deployment Board and Technical tabs.
- Contract fields: ticker, close, entry low/high, stop, band position, stale flag, canonical deployment status, deployment status reason, raw legacy state context, technical state, mismatch reason, owner/canon fallback state, and authority boundary.
- Fix deployment-board and technical-tab drift by forcing both views to consume the same contract instead of independently interpreting band state.
- Acceptance: in-band / above-band / below-stop status matches across Command Center, deployment readiness, and technical views; mismatches show as warnings, not silent contradictions.

### Phase 3 - Finance And PM Review UX
- Finance tab: production ticker cards, Tier C monitor names, stale-card queue, missing data families, answer-contract launcher, and approval-needed queue.
- PM tab: lane readiness, current handoff, dispatch cooldown, blockers, helper-lane status, and next safe PM action.
- Command tab: condensed "Act Now / Review / Ignore" triage with no proof clutter.
- Acceptance: Randall can review the day's finance and PM posture without reading `tmp/` files or asking which script to run.

### Phase 4 - Tool Dock
- Add tool launchers as UI commands for safe local refresh/review tools.
- Initial tools: Entry Band Analysis, Finance State Refresh, Artifact Cockpit, Ticker Review, Chief Intelligence Gate, WF67 Paper Manager, PM Refresh, Automation Health.
- Tool outputs remain review-only and cannot directly mutate canon, portfolio, cash, risk rules, paper/live orders, accounts, config, channels, credentials, or archives.
- Acceptance: tools are one-click/manual-run inside the local UI or clearly copyable commands, with stop lines shown before any higher-consequence path.

### Phase 5 - PM Auto-Refresh
- Add a PM-managed refresh route that regenerates the Command Center source packet on a low-noise cadence.
- Preferred cadence: post-close and morning proof windows, plus manual "Refresh Command Center Now."
- Refresh writes proof/review artifacts only; main-session wake happens only on concrete stop/warning/approval-needed signals.
- Acceptance: Command Center stays fresh without restoring high-frequency prompt/handoff noise.

### Phase 6 - Polish And Acceptance
- Tighten layout, filter controls, row density, color semantics, and responsive behavior.
- Keep cards for repeated items only; use full-width operational sections and tables for scan-heavy work.
- Add UI acceptance checks for no overlap, visible warning/stop state, and local-only route health.
- Acceptance: local UI is fast, readable, polished, and clearly separates review intelligence from authority/approval.

## Warnings And Stops
- Always show: stale source, validator warning/critical, authority conflict, source mismatch, paper/live boundary, owner approval required, and canonical-note conflict.
- Never imply: buy/sell approval, paper execution approval, live trading/account authority, portfolio/canon mutation, customer/public delivery, SQL canon promotion, or source freshness certainty when stale.
- Keep proof paths hidden by default but available for audit.

## Ownership And Dependencies
- WF79 owns Command Center V2 UI/UX plan, source registry, visual hierarchy, tool dock, and PM refresh model.
- WF72 owns SQL/entry-stop cache safety and fallback-backed read posture.
- WF77 owns finance question routing and ticker-card intelligence.
- WF58/WF64/WF56 own dashboard/deployment/portfolio-canon boundaries.
- WF73/WF76 own low-noise automation, cron/handoff selectivity, and escalation behavior.
- WF67 owns paper-only guardrail visibility and paper manager routing.

## Current Status
- Planning lane opened from Randall's 2026-06-03 22:25 MST pivot request.
- Existing PM cockpit is the reuse base.
- Older WF44 dashboard truth-alignment residue should fold into this V2 plan instead of remaining a separate dashboard-only follow-up.

## Next Action
- Implement Phase 1 and Phase 2 together as the first bounded pass: V2 source registry + normalized entry-band/deployment-state contract + deployment/technical drift warning model.
- Do not add cron auto-refresh until the manual V2 refresh path validates cleanly.

## 2026-06-05 deployment-state contract migration dependency

Randall asked to slim duplicated deployment-state fields after XOM exposed `workflow_state`, `machine_state`, and `action_state` together. WF79 should use the dedicated migration note as the contract owner and reflect only the canonical state in primary UI.

Plan owner: `06. Playbooks/Project Continuity/Deployment State Contract Migration.md`.

WF79 role:
- Treat deployment state as a shared contract, not a per-panel interpretation.
- Main UI should show one compact state and reason; raw legacy fields belong in drill-down/proof drawers.
- Do not remove legacy generated fields until downstream readers and validators migrate.

## 2026-06-05 presentation artifact flattening route

Randall asked to lock in the next simplification lane after deployment-state contract migration. WF79 is the primary owner because the biggest presentation bloat is the Command Center/dashboard payload family.

Plan owner: `06. Playbooks/Project Continuity/Presentation Artifact Flattening and Retrieval Routing.md`.

WF79 role:
- Treat dashboard presentation DTOs as compact views over proof/source artifacts, not the proof artifacts themselves.
- Keep proof paths, source files, validators, and authority detail available by reference/drill-down.
- Avoid repeating status/source/warning/authority blocks across every panel when a shared proof/ref layer can own them.
- Preserve warnings/stops prominently; flattening must not hide stale data, owner-approval requirements, or authority boundaries.

First slice:
- Phase 0 inventory plus Phase 1 dashboard DTO design/parallel DTO/compatibility proof are complete.
- Current proof artifact: `tmp/dashboard-presentation-compatibility-proof.json`.
- Result: compact DTO is safe as a retrieval/presentation route, but not a direct replacement for `tmp/dashboard-data.json` in the current standalone Command Center HTML. Existing `scripts/dashboard-js/*.js` modules still read the full `DATA` object directly.
- Adapter-first route map now exists at `tmp/dashboard-presentation-adapter.json`.
- Current adapter mode: `compact_primary_legacy_passthrough`; 33 current `DATA` routes mapped, with 29 compact-primary routes, 0 legacy-only route names, and 4 adapter metadata routes.
- Compact route stack now exists:
  - `tmp/dashboard-presentation-view-model.json`
  - `tmp/dashboard-presentation-view-model.html`
  - `tmp/dashboard-presentation-renderer-validation.json`
  - `tmp/dashboard-presentation-acceptance.json`
- `generate_dashboard.py` refreshes the compact route beside `tmp/veritas-command-center.html`.
- Current proof: compact view model ok, renderer ok, compact acceptance ok, legacy Command Center acceptance 29/29.
- Thin future-payload preview now exists:
  - `tmp/dashboard-data-thin-preview.json`
  - `tmp/dashboard-data-thin-preview-validation.json`
  - It references the compact route and legacy payload/HTML without embedding or replacing `tmp/dashboard-data.json`.
- First V2 compact-reader migration proof now exists:
  - `tmp/dashboard-v2-reader-migration.json`
  - `tmp/dashboard-v2-reader-migration.html`
  - Current migrated panel batch: all 8 compact panels.
- Compact dashboard shell now exists:
  - `tmp/veritas-command-center-compact.html`
  - `tmp/dashboard-compact-shell-validation.json`
  - `tmp/dashboard-compact-shell-acceptance.json`
- Dashboard compatibility payload proof now exists:
  - `tmp/dashboard-compatibility-payload.json`
  - `tmp/dashboard-compatibility-payload-validation.json`
  - `tmp/dashboard-shrink-readiness-score.json`
  - Covers all current `DATA` sections by compact/metadata route ownership but remains not drop-in replacement-ready.
- Render-default compatibility proof now exists at `tmp/presentation-render-default-compatibility.json`.
  - Current result: default render thinning is not broadly safe yet; active full-portfolio/WF75 sidecar references remain.
- Next safe action: use the compact shell as the new review/proof route while leaving legacy `tmp/dashboard-data.json` and `tmp/veritas-command-center.html` as stable row-detail/rollback surfaces. Keep full-portfolio/WF75 HTML default renders until active script consumers are retargeted or proven clean.

## 2026-06-13 Path B compact active-route promotion

Randall approved Path B: promote the compact shell/reader as Veritas' active first-read route while retaining the legacy full-detail dashboard for Randall.

Implemented route split:
- Veritas first-read JSON: `tmp/veritas-command-center-compact-reader.json`.
- Veritas compact HTML: `tmp/veritas-command-center-compact.html`.
- Randall full-detail dashboard retained: `tmp/veritas-command-center.html`.
- Legacy payload retained by design: `tmp/dashboard-data.json`.

Behavior:
- `generate_dashboard.py` still regenerates the legacy full-detail dashboard and payload.
- `generate_dashboard.py` also regenerates the compact view model, compact shell, compact reader JSON, compact acceptance, and shrink-readiness score.
- The compact shell links to `veritas-command-center.html` as "Open Randall Full Detail Dashboard."
- The legacy full-detail dashboard links back to `veritas-command-center-compact.html` as "Open Veritas Compact Command View."
- `presentation_retrieval_route_map.py` now routes WF79 first through `tmp/veritas-command-center-compact-reader.json`; the full-detail dashboard is an explicit Randall drilldown/rollback route.
- `dashboard_shrink_readiness_score.py` now distinguishes active-route readiness from optional legacy retirement: current status is `ready_compact_reader_legacy_retained`, with `replacement_ready=false`, `legacy_retained_by_design=true`, and `randall_full_detail_view_retained=true`.

Proof:
- `python -m py_compile scripts\generate_dashboard.py scripts\dashboard_compact_shell.py scripts\dashboard_compact_shell_acceptance.py scripts\dashboard_shrink_readiness_score.py scripts\presentation_retrieval_route_map.py scripts\workflow_routing_index.py` passed.
- `python scripts\generate_dashboard.py` passed; generated legacy full view, compact shell, compact reader, and compact view model.
- `python scripts\dashboard_compact_shell_acceptance.py --write --validate` passed.
- `python scripts\dashboard_shrink_readiness_score.py --write --validate` passed with `ready_compact_reader_legacy_retained` and `0` active blockers.
- `python scripts\presentation_retrieval_route_map.py --write --validate` passed.
- `python scripts\presentation_render_default_compatibility.py --write --validate` passed.
- `python scripts\workflow_routing_index.py --write --validate` passed.
- `python scripts\artifact_index.py incremental` and `python scripts\artifact_index.py validate` passed.

Validation limit:
- `python scripts\deployment_contract_migration_validation_bundle.py --write` still fails one pre-existing audit: `deployment_contract_legacy_read_audit` has 19 unclassified legacy-read warnings across finance reader scripts. The dashboard acceptance, contract agreement, artifact-index, and canonical-status checks inside the same bundle passed. This is deployment-contract reader debt outside the compact active-route promotion and remains a separate cleanup item.

Current WF79 posture:
- No active Path B blocker.
- Optional future work: legacy payload retirement or section-by-section legacy JS reader migration if Randall later wants the full legacy dashboard thinned.
- Stop lines unchanged: local/review-only UI only; no proof deletion, sidecar archive/delete, canon/portfolio mutation, SQL promotion, paper/live/account action, approval inference, or config/channel/runtime expansion.

## 2026-06-18 human canon and deliverables split

Randall approved the full execution pass to separate human notes from machine proof, move human deliverables out of `tmp/`, and align the local UI around two roles:
- Veritas Command Center: Randall-facing human finance intelligence view.
- Veritas PM: operator/proof/queue/source-health view.

Implemented scope:
- Added `10. Deliverables/` as the human-facing shelf for PDFs, Excel workbooks, HTML views, and CSV exports.
- Added `state/deliverables/` as the manifest/index owner for that shelf.
- Added `scripts/deliverables_publisher.py` to copy known current deliverables without deleting or moving `tmp/` proof.
- Added `05. Intelligence/Thesis Ranking and Leadership Board.md` as the human thesis/ranking/leadership surface.
- Updated `Home.md`, `01. Dashboards/Executive Brief.md`, `Workspace Structure Protocol`, and `Notes Layer Governance Protocol` to make the human/machine split explicit.
- Updated the local PM cockpit/Command Center route so Randall and deliverables views sit beside the Veritas PM/proof tabs.

Stop lines:
- No `09. Archive/` restore, archive, or delete.
- No `tmp/` proof deletion or move.
- No portfolio/canon mutation.
- No SQL promotion.
- No paper/live/account action.
- No customer/public delivery.
- No approval inference.

## Acceptance Gates
- Command Center is local-only and review-only.
- No visual clutter from proof/source paths on primary screens.
- Warnings/stops are prominent and cannot be hidden by default.
- Entry-band posture is consistent across Deployment Board and Technical tabs.
- PM auto-refresh is low-noise and does not wake main session unless a concrete stop/approval-needed signal exists.
- Canonical owner notes remain source of portfolio truth.

## 2026-06-18 finance actionability compact slice

Randall asked to continue from the Command Center UI/navigation audit and implement an available slice.

Implemented Slice 1:
- Added `scripts/finance_daily_actionability_snapshot.py` and `tmp/finance-daily-actionability-snapshot.json` as the first-screen finance actionability contract.
- Added `scripts/test_finance_daily_actionability_snapshot.py`.
- Updated the compact view-model route so the finance Command Center has seven human-labeled panels: Today, Trust, Capital, Macro, Portfolio, Technicals, and Fundamentals.
- Removed `workflow_pm` from the finance compact reader and marked it migrated to `http://127.0.0.1:8765/` / Veritas PM Cockpit.
- Updated compact shell, renderer, migration proof, and acceptance gates to validate the seven-panel finance route and PM cockpit handoff.
- Published the refreshed compact Command Center into `10. Deliverables/Command Center/veritas-command-center-compact.html` through `deliverables_publisher.py`.

Current truth after implementation:
- `tmp/finance-daily-actionability-snapshot.json` reports `actionability_status=refresh_required_before_actionability`, `actionability_allowed=false`, `source_freshness_status=stale`, `source_trust_level=review_required`.
- Capital buckets are visible but review-only: deployable now `0`, owner review `9`, pullback-only `4`, below-stop `10`.
- Fundamentals, macro, and energy remain warning-class caveated evidence, not failed proof.
- Daily review and market-intelligence packets are stale, so the Command Center correctly refuses to imply "actionable after last refresh."

Validation:
- `python scripts\test_finance_daily_actionability_snapshot.py` passed.
- `python scripts\finance_daily_actionability_snapshot.py --write --validate` passed.
- `python -m py_compile` passed for changed WF79/snapshot scripts.
- `python scripts\dashboard_presentation_view_model.py --write --validate` passed with 7 panels.
- `python scripts\dashboard_presentation_renderer.py --write --validate` passed.
- `python scripts\dashboard_v2_reader_migration.py --write --validate` passed.
- `python scripts\dashboard_compact_shell.py --write --validate` passed.
- `python scripts\dashboard_compact_shell_acceptance.py --write --validate` passed.
- `python scripts\dashboard_presentation_acceptance.py --write --validate` passed.
- `python scripts\validate_dashboard_state.py` exited 0 while reporting stale/review_required source freshness.
- `python scripts\deliverables_publisher.py --write --validate` passed with 29 published / 0 errors.

Stop lines:
- Local/review-only presentation and retrieval only.
- No customer/public output, proof deletion, archive/delete, SQL promotion, config/channel/runtime expansion, portfolio/canon/cash/sizing/risk mutation, capital deployment, paper/live/account action, brokerage/account action, money movement, or owner approval inference.

## 2026-06-18 Command Center audit remediation hardening

Randall approved continuing from `08. Audits/command-center-ui-navigation-audit-2026-06-18.md` with the recommended parallel plan.

Implemented hardening:
- `scripts/finance_daily_actionability_snapshot.py` now selects daily-review and market-intelligence packet pairs by operating window instead of hardcoding post-close packets for every window.
- The daily finance snapshot now exposes `actionability_mode`, `actionability_permission`, exact `refresh_blockers`, `market_data_as_of`, `next_refresh_due`, latest required input timestamp, and proof routes.
- `scripts/dashboard_presentation_view_model.py` carries the expanded actionability contract into `tmp/dashboard-presentation-view-model.json`.
- `scripts/dashboard_compact_shell.py` now renders a first-screen actionability gate, Capital Decision Funnel, fundamentals/macro/energy caveats, and proof routes.
- `scripts/dashboard_compact_shell_acceptance.py` validates the new funnel/caveat/proof requirements and the expanded reader actionability contract.
- `scripts/deliverables_publisher.py` now publishes compact JSON proof files alongside the Command Center HTML shelf deliverables.
- PM cockpit copy is now `Veritas PM Cockpit`, with a local `Finance Snapshot` link.
- `apps/pm-control-cockpit/src/server.ts` serves the published Command Center shelf read-only at `/command-center/`.

Current truth after hardening:
- `tmp/finance-daily-actionability-snapshot.json` validates `ok` but reports `actionability_status=refresh_required_before_actionability`.
- Current refresh blockers are `dashboard_exec_freshness_stale`, `dashboard_presentation_not_allowed`, and `stale_required_source:portfolio`.
- `python scripts\validate_dashboard_state.py` exits 0 but still reports `overall_exec_status: stale` and `source_freshness: stale / review_required`; the stale portfolio config remains the current trust limit.
- Published Command Center shelf now includes:
  - `10. Deliverables/Command Center/veritas-command-center-compact.html`
  - `10. Deliverables/Command Center/veritas-command-center-compact-reader.json`
  - `10. Deliverables/Command Center/dashboard-presentation-view-model.json`
  - `10. Deliverables/Command Center/finance-daily-actionability-snapshot.json`
  - compact shell validation and acceptance JSON.
- The live local PM cockpit at `http://127.0.0.1:8765` was restarted and now serves `http://127.0.0.1:8765/command-center/` with the finance-first compact snapshot.

Validation:
- `python scripts\finance_daily_actionability_snapshot.py --write --validate` passed.
- `python scripts\dashboard_presentation_view_model.py --write --validate` passed with 7 panels.
- `python scripts\dashboard_compact_shell.py --write --validate` passed with 0 critical.
- `python scripts\dashboard_compact_shell_acceptance.py --write --validate` passed with 0 critical.
- `npm run validate` in `apps/pm-control-cockpit` passed: source count 130, missing required 0, stale required 0, SQL adapter ok.
- `python scripts\deliverables_publisher.py --write --validate` passed: 34 published, 0 errors.
- `http://127.0.0.1:8765/health` returned ok with missing required 0 and stale required 0.
- `http://127.0.0.1:8765/command-center/` returned 200 and contains `Veritas Finance Command Center`, `Capital Decision Funnel`, and `Proof Routes`.

Stop lines:
- Local/review-only UI, routing, and deliverable publication only.
- No public/customer delivery, proof deletion, archive/delete, SQL promotion, portfolio/canon/cash/sizing/risk mutation, capital deployment, paper/live/account action, brokerage/account action, money movement, or owner approval inference.

## 2026-06-18 refresh ordering and portfolio freshness unblock

Randall approved proceeding with the next recommended Command Center audit slice after Slice 1 left one stale actionability blocker.

Implemented Slice 2:
- Patched `scripts/dashboard_core.py` so `tmp/portfolio-config.json` is treated as an explicit manual-review dependency when its own `manual_review_policy` / `manual_review_fields` contract is present, instead of turning its old `generated_at_utc` provenance timestamp into a false stale blocker.
- Patched `scripts/source_freshness_classifier.py` so allowlisted dashboard manual dependencies, currently only `portfolio`, do not get age-escalated back to `stale` after `dashboard_core` has classified them as manual dependencies.
- Regenerated the dashboard payload, daily actionability snapshot, compact view model, compact shell, acceptance proof, and published Command Center shelf deliverables in order.

Current truth after Slice 2:
- `tmp/finance-daily-actionability-snapshot.json` now reports `actionability_status=review_only_actionability`, `actionability_mode=review_only`, `actionability_permission=review_only`, and `refresh_blockers=[]`.
- `tmp/dashboard-data.json` now reports `exec_freshness=usable_with_caution`, `source_freshness.overall_classification=manual_dependency`, `source_freshness.trust_level=review_required`, and `source_freshness.presentation_allowed=true`.
- Portfolio config remains visible as a review-required manual dependency, not a clean/fresh automated source.
- Capital/action boundaries remain false: no capital action, execution, brokerage/account action, money movement, owner approval inference, or portfolio/canon mutation authority.
- Remaining dashboard warnings are real review caveats, not refresh blockers: deteriorating/narrow breadth and the suspended 10% legacy model-weight gap.

Validation:
- Direct portfolio source probe: `status=usable_with_caution`, `classification=manual_dependency`, `stop_line=false`, `stale_after_hours=None`.
- `python -m py_compile scripts\dashboard_core.py scripts\source_freshness_classifier.py` passed.
- `python scripts\generate_dashboard.py` passed: 0 critical, 2 warning, `Exec freshness: usable_with_caution`.
- `python scripts\validate_dashboard_state.py` passed: 0 critical, 2 warning; `source_freshness: manual_dependency / review_required`.
- `python scripts\finance_daily_actionability_snapshot.py --write --validate` passed with `review_only_actionability`.
- `python scripts\dashboard_presentation_view_model.py --write --validate` passed with 7 panels.
- `python scripts\dashboard_compact_shell.py --write --validate` passed with 0 critical.
- `python scripts\dashboard_compact_shell_acceptance.py --write --validate` passed with 0 critical.
- `python scripts\deliverables_publisher.py --write --validate` passed: 34 published, 0 errors.
- `http://127.0.0.1:8765/command-center/` returned 200 and contains the finance title, Capital Decision Funnel, and review-only actionability; it no longer shows the refresh-required gate.

Stop lines:
- Local/review-only UI, routing, freshness classification, and deliverable publication only.
- No public/customer delivery, proof deletion, archive/delete, SQL promotion, portfolio/canon/cash/sizing/risk mutation, capital deployment, paper/live/account action, brokerage/account action, money movement, or owner approval inference.
