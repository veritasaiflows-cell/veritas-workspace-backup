# Presentation Artifact Flattening and Retrieval Routing

## Objective
- Flatten bulky presentation artifacts without deleting proof.
- Improve routing and retrieval by separating source/proof artifacts, compact presentation objects, and index/route metadata.
- Keep human-facing surfaces clean: what matters, why, freshness/confidence, stop lines, and owner action required.

## Why This Matters
- Current presentation surfaces often repeat status/source/warning/authority/validation blocks.
- Repetition makes search noisier, dashboard payloads heavier, and user-facing answers more likely to expose internal workflow vocabulary.
- The deployment-state contract migration proved the pattern: keep raw trace in a contract/proof layer, show compact canonical state in presentation.

## Current Scan Findings - 2026-06-05
- Deployment-state migration wrap proof stayed green:
  - `python scripts\deployment_contract_migration_validation_bundle.py --write --full` -> ok, 16 commands, 0 failures.
  - JSON scan found 0 generated records that embed `deployment_contract` while reintroducing duplicate top-level deployment-state aliases.
- Largest/most relevant flattening candidates:
  - `tmp/dashboard-data.json` and `tmp/dashboard-last.json` are about 1.9 MB each and repeat status/source/warning/authority fields across UI payload sections.
  - `tmp/full-portfolio-view.json/.md/.html` is a triple-output communication surface.
  - `tmp/wf75-operator-console.json/.md/.html` is a triple-output operator surface.
  - `tmp/retail-saas-fixture-demo*` has 11 fixture/render/validation files; this needs retention/manifest discipline, not deletion.
  - WF78 promotion/routing packets repeat authority/stop-line/validation/summary blocks across many JSONs.

## Phased Approach

### Phase 0 - Inventory And Contract Map
- Build a small read-only inventory of active presentation artifact families:
  - JSON source/proof artifacts.
  - JSON presentation payloads.
  - Markdown/HTML sidecars.
  - Dashboard/PM/UI consumers.
- Classify each artifact as:
  - `source_proof`
  - `presentation_dto`
  - `human_render_optional`
  - `validation_proof`
  - `legacy_sidecar`
- Acceptance:
  - inventory identifies owner script, downstream consumers, current size, sidecar count, and authority boundary.
  - no deletes, moves, or schema changes.

### Phase 1 - WF79 Dashboard Payload Normalization
- Owner: WF79 / Command Center V2.
- Target: `dashboard_payload.py`, `tmp/dashboard-data.json`, `tmp/dashboard-last.json`, and PM cockpit/Command Center readers.
- Define compact panel DTOs:
  - `headline`
  - `state`
  - `freshness`
  - `severity`
  - `primary_reason`
  - `owner_action_required`
  - `source_ref`
  - `proof_ref`
  - `authority_summary`
- Keep full proof in source artifacts and expose proof paths by reference, not by repeated embedded blocks.
- Acceptance:
  - dashboard payload validates.
  - dashboard acceptance tests pass.
  - artifact index validates.
  - payload size and repeated-key count are measured before/after.
  - no authority widening and no proof deletion.

### Phase 2 - Full Portfolio View Output Discipline
- Owner: portfolio communication / WF58-WF64-WF56 boundary.
- Target: `full_portfolio_view.py` and `tmp/full-portfolio-view.json/.md/.html`.
- Keep JSON as the machine truth for the report surface.
- Make Markdown/HTML explicitly optional render outputs when possible, or document why they remain active.
- Acceptance:
  - portfolio view regenerates.
  - dashboard/answer surfaces that rely on it still work.
  - no canon/portfolio mutation.

### Phase 3 - WF75 Operator Console Output Discipline
- Owner: WF75 / PM service-led readiness.
- Target: `wf75_operator_console.py` and `tmp/wf75-operator-console.json/.md/.html`.
- Apply JSON-first/optional-render discipline.
- Keep operator console local/internal only.
- Acceptance:
  - WF75 operator console validates.
  - retail truth routing / answer harness / automation control plane stay green.
  - no customer/public/export authority.

### Phase 4 - WF78 Packet Summary Consolidation
- Owner: WF78 tier/routing spine.
- Target: tier promotion/routing/adjudication packets that repeat authority/stop-line/validation blocks.
- Add shared summary/reference blocks only after consumer inventory proves no reader depends on repeated embedded blocks.
- Acceptance:
  - `wf78_phase_runner.py --phase all-safe --write --validate` passes.
  - auto-tier routing remains the default non-capital routing truth.
  - no tier/capital/trade/portfolio authority changes.

### Phase 5 - Retrieval/Index Improvement
- Update artifact/index routing so compact presentation DTOs point to exact proof artifacts.
- Improve answer routing:
  - retrieve compact presentation object first;
  - open source proof only when material, stale, disputed, or requested.
- Acceptance:
  - artifact index validates.
  - representative finance/status questions route with fewer noisy artifact hits.
  - no proof/source hiding.

## Recommended First Slice
- Start with **Phase 0 + a narrow Phase 1 design pass**:
  - inventory dashboard payload sections and consumers;
  - identify repeated status/source/warning/authority blocks;
  - propose the compact dashboard DTO shape;
  - do not rewrite the dashboard payload yet.
- This gives the biggest retrieval/presentation payoff while keeping risk bounded.

## Stop Lines
- Do not delete proof artifacts.
- Do not archive/move/delete sidecars without a separate cleanup approval path.
- Do not remove fields from source/proof artifacts just because presentation DTOs do not need them.
- Do not weaken authority, warning, stale-source, or owner-approval stop lines.
- Do not imply canon/portfolio mutation, SQL-canon promotion, customer/public output, paper/live/account action, or owner approval.

## Proof Ladder
- Compile changed scripts.
- Regenerate target artifact.
- Run target validator/acceptance test.
- Run `artifact_index.py incremental` and `artifact_index.py validate`.
- Run adjacent workflow proof:
  - dashboard: `dashboard_payload.py --write --validate` + `test_dashboard_acceptance.py`
  - portfolio view: `full_portfolio_view.py`
  - WF75: retail truth routing / answer harness / automation control plane
  - WF78: `wf78_phase_runner.py --phase all-safe --write --validate`

## Next Action
- Resume the remaining consumer-retargeting lane before any further payload retirement.
- Phase A: retarget `tmp/full-portfolio-view.html` active consumers to JSON-first/optional-proof.
- Phase B: retarget `tmp/wf75-operator-console.html` active consumers to JSON-first/optional-proof.
- Phase C: only after A/B proof is clean, change owner-script defaults so HTML writes are explicit/optional rather than default-required.
- Phase D: rerun render-default compatibility and require 4 safe / 0 unsafe before claiming sidecar retarget closure.
- Phase E: separately address `dashboard-data.json` drop-in readiness; this is not the same blocker as HTML sidecar retargeting.

## Progress - 2026-06-05

Safe additive phases advanced:

- **Phase 0 inventory implemented:** `scripts/presentation_artifact_inventory.py`.
  - Writes `tmp/presentation-artifact-flattening-inventory.json`.
  - Latest run: 8 families, 4753.8 KB total.
  - Highest-priority families: `dashboard-data`, `dashboard-last`, `full-portfolio-view`, `wf75-operator-console`.
  - Acceptance passed: owner scripts identified, consumer inventory present, size recorded, authority boundary present, no schema changes, no deletes/moves/archives.
- **Phase 1 dashboard DTO design implemented:** `scripts/dashboard_presentation_dto_design.py`.
  - Writes `tmp/dashboard-presentation-dto-design.json`.
  - Defines 8 compact panel contracts: command/today, trust/freshness, deployment, market/macro, portfolio, technical, fundamentals/earnings, workflow/PM.
- **Phase 1 parallel DTO implemented:** `scripts/dashboard_presentation_dto.py`.
  - Writes `tmp/dashboard-presentation-dto.json`.
  - Latest run: ok, 8 panels, 0 validation criticals.
  - Existing `tmp/dashboard-data.json` remains unchanged as the full payload; compact DTO is additive.
- **Phase 2 full-portfolio-view output discipline advanced:** `scripts/full_portfolio_view.py`.
  - Added `render_policy`.
  - Added `--json-only`, `--write-md`, and `--write-html`.
  - Current `--write` behavior is JSON-first; Markdown/HTML require explicit `--write-md` / `--write-html`.
- **Phase 3 WF75 operator console output discipline advanced:** `scripts/wf75_operator_console.py`.
  - Added `render_policy`.
  - Added `--json-only` and `--write-html`.
  - Current `--write` behavior is JSON-first; HTML/Markdown require explicit `--write-html` / `--write-md`.
- **Phase 5 retrieval/index improvement started:** `scripts/artifact_index.py` now tracks:
  - `tmp/dashboard-presentation-dto.json`
  - `tmp/dashboard-presentation-dto-design.json`
  - `tmp/dashboard-presentation-compatibility-proof.json`
  - `tmp/dashboard-presentation-adapter.json`
  - `tmp/dashboard-presentation-view-model.json`
  - `tmp/dashboard-presentation-renderer-validation.json`
  - `tmp/dashboard-presentation-acceptance.json`
  - `tmp/presentation-artifact-flattening-inventory.json`

Compatibility proof advanced:
- Added `scripts/dashboard_presentation_compatibility_proof.py`.
- Writes `tmp/dashboard-presentation-compatibility-proof.json`.
- Latest proof: `status=ok`, compact DTO safe for retrieval route, compact DTO **not** safe as current standalone Command Center HTML payload replacement.
- Size proof: `tmp/dashboard-presentation-dto.json` is about 0.37% of `tmp/dashboard-data.json` (7.4 KB vs 2.0 MB), with repeated authority/status/source-style keys materially reduced.
- Consumer proof: `scripts/dashboard-js/*.js` modules still read 33 top-level `DATA` sections directly; 16 of 20 scanned Command Center files read `DATA`/`DELTA`.

Adapter-first promotion advanced:
- Added `scripts/dashboard_presentation_adapter.py`.
- Writes `tmp/dashboard-presentation-adapter.json`.
- Current adapter mode: `compact_primary_legacy_passthrough`.
- Latest validation: 33 current Command Center `DATA` routes mapped:
  - 29 `compact_panel_primary_with_legacy_passthrough`
  - 4 `adapter_metadata`
- The adapter does not embed the full dashboard payload; it records route metadata and keeps `tmp/dashboard-data.json` as the legacy UI passthrough while compact DTOs become the first retrieval/presentation route.
- The first adapter cleanup slice converted the five former legacy-only route names (`escalation_triggers`, `regime_indicators`, `sector_weights`, `ui`, `vault_freshness`) into compact-panel-owned routes by extending the DTO design source section map.

Compact view-model and renderer proof advanced:
- Added `scripts/dashboard_presentation_view_model.py`.
  - Writes `tmp/dashboard-presentation-view-model.json`.
  - Builds the compact UI-facing contract from DTO + adapter; does not embed the full legacy dashboard payload.
- Added `scripts/dashboard_presentation_renderer.py`.
  - Writes `tmp/dashboard-presentation-view-model.html`.
  - Writes `tmp/dashboard-presentation-renderer-validation.json`.
  - Provides a parallel compact renderer proof; it does not replace `tmp/veritas-command-center.html`.
- Added `scripts/dashboard_presentation_acceptance.py`.
  - Writes `tmp/dashboard-presentation-acceptance.json`.
  - Proves view-model, adapter, renderer, authority flags, and legacy Command Center preservation.
- Updated `scripts/generate_dashboard.py` so the compact route refreshes alongside the stable legacy dashboard run.
- Latest proof: view model ok (8 panels), renderer ok (0 critical), compact acceptance ok (0 critical), current dashboard acceptance still 29/29.

Thin-payload preview and render-default compatibility proof advanced:
- Added `scripts/dashboard_thin_payload_preview.py`.
  - Writes `tmp/dashboard-data-thin-preview.json`.
  - Writes `tmp/dashboard-data-thin-preview-validation.json`.
  - Latest preview: ok, 0 critical, 0 warnings.
  - Shape: compact view-model/adapter/acceptance first, `tmp/dashboard-data.json` and `tmp/veritas-command-center.html` by reference only.
  - It does not embed the full legacy dashboard payload and does not replace the live dashboard contract.
  - Latest size proof: live `dashboard-data.json` about 2.0 MB; compact route artifacts about 44.7 KB.
- Added `scripts/presentation_render_default_compatibility.py`.
  - Writes `tmp/presentation-render-default-compatibility.json`.
  - Latest validation: ok, 0 critical.
  - Scanned 2 render families and 761 script/app/playbook files.
  - Result: 1 sidecar default-disable path appears safe/optional, while 3 default-disable paths remain unsafe or unproven because active consumers/docs still reference them.
  - Therefore full-portfolio/WF75 render defaults should stay intact until specific consumers are retargeted or proven clean.
- `scripts/generate_dashboard.py` now refreshes the thin preview as part of the compact route stack.
- `scripts/artifact_index.py` now tracks:
  - `tmp/dashboard-data-thin-preview.json`
  - `tmp/dashboard-data-thin-preview-validation.json`
  - `tmp/presentation-render-default-compatibility.json`
- `scripts/presentation_artifact_inventory.py` now tracks the thin-preview and render-default proof families. Latest inventory: 15 families, 4833.2 KB.

Phase 1/2 reader migration and shrink gate advanced:
- Added `scripts/dashboard_v2_reader_migration.py`.
  - Writes `tmp/dashboard-v2-reader-migration.json`.
  - Writes `tmp/dashboard-v2-reader-migration.html`.
  - Current migrated compact-reader panel batch: all 8 compact panels (`command_today`, `trust_and_freshness`, `deployment`, `portfolio`, `technical`, `fundamentals_earnings`, `market_macro`, `workflow_pm`).
  - It renders from compact view-model/thin-preview contracts and keeps legacy dashboard only as a referenced drilldown source.
- Added `scripts/dashboard_compact_shell.py`.
  - Writes `tmp/veritas-command-center-compact.html`.
  - Writes `tmp/dashboard-compact-shell-validation.json`.
  - Provides the usable compact shell over all 8 compact panels. It remains local/review-only and does not replace the legacy Command Center.
- Added `scripts/dashboard_compact_shell_acceptance.py`.
  - Writes `tmp/dashboard-compact-shell-acceptance.json`.
  - Validates required panel anchors, review-only boundary language, compact shell validation, and no legacy payload blob embedding.
- Added `scripts/dashboard_shrink_readiness_score.py`.
  - Writes `tmp/dashboard-shrink-readiness-score.json`.
  - Latest result: 100% route coverage, compact route artifacts about 2.26% of legacy dashboard payload size, but replacement remains blocked by `compatibility_payload_not_drop_in_ready`.
- Added `scripts/dashboard_compatibility_payload.py`.
  - Writes `tmp/dashboard-compatibility-payload.json`.
  - Writes `tmp/dashboard-compatibility-payload-validation.json`.
  - Latest proof: 33 current `DATA` route sections covered, 29 compact-primary, 4 adapter metadata, 0 legacy-only.
  - Status remains `coverage_ready_not_drop_in`; it does **not** claim `dashboard-data.json` replacement readiness because current JS still expects concrete row/table values.
- `generate_dashboard.py` now refreshes the V2 reader migration and compatibility payload artifacts with the normal dashboard run.

Phase 3 sidecar retarget closed:
- `scripts/authority_vocabulary_consistency_check.py` now scans `tmp/full-portfolio-view.json` instead of `tmp/full-portfolio-view.md`.
- This removes one active script dependency on the Markdown sidecar while keeping the authority vocabulary checker green.
- `scripts/presentation_retrieval_route_map.py` no longer uses `tmp/full-portfolio-view.md` as a proof ref.
- Full-portfolio and WF75 operator HTML consumers have been retargeted to JSON-first/optional-proof routes.
- `scripts/full_portfolio_view.py` and `scripts/wf75_operator_console.py` are JSON-first by default; Markdown/HTML require explicit sidecar flags.
- Render-default proof now shows 4 safe default-disable paths and 0 unsafe/unproven paths.

Phase 4 WF78 packet consolidation proof advanced:
- Added `scripts/wf78_packet_summary_consolidation.py`.
  - Writes `tmp/wf78-packet-summary-consolidation.json`.
  - Writes `tmp/wf78-packet-shared-header.json`.
  - Previews shared header/summary/validation reference candidates across active WF78 routing/promotion packet families.
  - Added additive `shared_header_ref` support to Tier A/Tier B final-promotion packet generators.
  - Current generated Tier B packet family carries `shared_header_ref` while preserving embedded compatibility fields.
  - No routing, tier, label, capital, trade, proof, or source-field behavior changed.
  - Latest adjacent WF78 proof: `wf78_phase_runner.py --phase all-safe --validate` ok, 20 steps, 0 failures.

Phase 5 retrieval-first route map advanced:
- Added `scripts/presentation_retrieval_route_map.py`.
  - Writes `tmp/presentation-retrieval-route-map.json`.
  - Routes WF79 dashboard summaries to compact view-model/thin-preview first, portfolio/WF75 to JSON first, and WF78 routing to auto-tier routing first, with proof artifacts preserved behind those routes.
- Added `scripts/presentation_retrieval_enforcement.py`.
  - Writes `tmp/presentation-retrieval-enforcement.json`.
  - Validates first-read artifacts exist, proof refs remain, and route-map authority flags stay clamped.
- Latest inventory after these additions: 19 families, 4865.6 KB.

Decision gate:
- `tmp/dashboard-presentation-dto.json` may be used as a compact retrieval/presentation route now.
- `tmp/dashboard-presentation-adapter.json` may be used as the adapter-first route map now.
- `tmp/dashboard-presentation-view-model.json` and `tmp/dashboard-presentation-view-model.html` may be used as the compact parallel UI proof route now.
- `tmp/dashboard-data-thin-preview.json` may be used as a future payload migration preview now.
- `tmp/dashboard-v2-reader-migration.json` may be used as the first compact-reader migration proof now.
- `tmp/veritas-command-center-compact.html` may be used as the compact dashboard shell proof route now.
- `tmp/dashboard-compatibility-payload.json` may be used as route-coverage proof, not as a drop-in payload.
- `tmp/presentation-retrieval-route-map.json` may be used as the compact/JSON-first retrieval guide now.
- Do **not** replace `tmp/dashboard-data.json` for the current Command Center HTML until a later pass either:
  - proves a compatibility payload/view model that satisfies the existing HTML `DATA` contract from compact routes plus legacy passthrough; or
  - rewrites the UI to render directly from compact panel DTOs and passes acceptance tests.
- Replacing existing `tmp/dashboard-data.json` fields or consolidating WF78 repeated packet blocks still requires the relevant consumer-by-consumer compatibility proof and a separate go. Destructive/removal behavior is not authorized here.

## Historical Pickup Checkpoint - 2026-06-05 16:36 MST

Superseded by the 2026-06-05 17:00 MST checkpoint below. This section preserves the pre-retarget state and should not be used as current pickup truth.

Historical truth at that time:
- Today's additive compact-route work is complete and validated, but the consumer-retargeting lane is not fully complete.
- `tmp/dashboard-shrink-readiness-score.json` says route coverage is 100% and compact route artifacts are about 2.26% of legacy `tmp/dashboard-data.json`, but replacement is still blocked by `compatibility_payload_not_drop_in_ready`.
- `tmp/presentation-render-default-compatibility.json` still showed unresolved HTML-sidecar proof debt.
- Safe default-disable paths:
  - `tmp/full-portfolio-view.md`
  - `tmp/wf75-operator-console.md`
- Unsafe/unproven default-disable paths:
  - `tmp/full-portfolio-view.html`
  - `tmp/wf75-operator-console.html`

Remaining active HTML consumers:
- `tmp/full-portfolio-view.html` active consumers:
  - `scripts/chain_manifest.py`
  - `scripts/current_window_artifact_index.py`
  - `scripts/presentation_retrieval_route_map.py`
  - `scripts/tmp_lifecycle_delete_proposal.py`
  - `scripts/tmp_lifecycle_phase2_6_delete_apply.py`
- `tmp/wf75-operator-console.html` active consumers:
  - `scripts/operator_packet.py`
  - `scripts/presentation_retrieval_route_map.py`
  - `scripts/veritas_pm_department_validate.py`
  - `scripts/wf75_cron_automation_authority_plan.py`
  - `scripts/wf75_pm_readiness_pdf.py`

Next phased execution:
- Phase A - Full-portfolio HTML consumer retarget:
  - Make JSON the required source and HTML optional proof in chain/index/route/lifecycle consumers.
  - Acceptance: render-default proof shows `full_portfolio_view.html` safe to disable; full-portfolio JSON validation still passes; no delete/archive authority widens.
- Phase B - WF75 operator HTML consumer retarget:
  - Make JSON the required source and HTML optional proof in operator packet, route map, PM validation, cron authority plan, and PM readiness PDF.
  - Acceptance: render-default proof shows `wf75_operator_console.html` safe to disable; WF75 operator JSON validation and PM/readiness validators stay green.
- Phase C - Owner script default flags:
  - Update `scripts/full_portfolio_view.py` and `scripts/wf75_operator_console.py` so default writes are JSON-first and HTML requires an explicit flag.
  - Acceptance: default runs write required JSON; explicit HTML flag still writes valid HTML.
- Phase D - Closure proof:
  - Rerun `scripts/presentation_render_default_compatibility.py`.
  - Acceptance: `safe_default_disable_count=4`, `unsafe_or_unproven_default_disable_count=0`, no authority flags widen.
- Phase E - Dashboard compatibility blocker:
  - Separately identify old dashboard JS readers that still need concrete row/table values.
  - Acceptance: either shrink readiness flips ready, or the legacy dashboard remains explicitly retained as row-level drilldown by design.

Validation ladder for next session:
- Compile changed scripts.
- Run targeted owner validations for full-portfolio and WF75 operator console.
- Run `python scripts\presentation_render_default_compatibility.py --write --validate`.
- Run compact shell acceptance, shrink readiness score, retrieval enforcement, dashboard acceptance, presentation inventory, and artifact index validation.
- If WF78 shared-header references are touched, rerun `python scripts\wf78_phase_runner.py --phase all-safe --write --validate`.

Stop lines:
- Do not delete, archive, or move HTML sidecars in this lane.
- Do not replace `tmp/dashboard-data.json` until drop-in readiness is proven or legacy retention is explicitly chosen.
- Do not remove WF78 embedded packet fields; current shared header remains additive only.
- No canon/portfolio/SQL-canon mutation, customer/public output, paper/live/brokerage/account action, capital deployment, trade execution, or owner approval inference.

## Pickup Checkpoint - 2026-06-05 17:00 MST

Current truth:
- Phase A/B consumer retargeting is complete for the two HTML sidecar families.
- Phase C owner-script default changes are complete:
  - `scripts/full_portfolio_view.py --write` writes JSON by default.
  - `scripts/wf75_operator_console.py --write` writes JSON by default.
  - `--write-html` and `--write-md` explicitly generate optional sidecars.
- Phase D closure proof is clean:
  - `tmp/presentation-render-default-compatibility.json` reports `safe_default_disable_count=4`, `unsafe_or_unproven_default_disable_count=0`, `owner_defaults_json_first=true`, and `sidecars_explicit_only=true`.
- Phase E remains blocked:
  - `tmp/dashboard-shrink-readiness-score.json` still reports `compatibility_payload_not_drop_in_ready`.
  - This is the remaining dashboard replacement blocker, separate from the now-closed render-sidecar default lane.

Validated commands:
- `python -m py_compile scripts\full_portfolio_view.py scripts\wf75_operator_console.py scripts\presentation_render_default_compatibility.py`
- `python scripts\full_portfolio_view.py --write`
- `python scripts\full_portfolio_view.py --write --write-html --write-md`
- `python scripts\wf75_operator_console.py --write --validate`
- `python scripts\wf75_operator_console.py --write --write-html --write-md --validate`
- `python scripts\presentation_render_default_compatibility.py --write --validate`
- `python scripts\presentation_retrieval_route_map.py --write --validate`
- `python scripts\presentation_retrieval_enforcement.py --write --validate`
- `python scripts\dashboard_compact_shell_acceptance.py --write --validate`
- `python scripts\dashboard_shrink_readiness_score.py --write --validate` remains blocked only on `compatibility_payload_not_drop_in_ready`
- `python scripts\artifact_index.py incremental`
- `python scripts\artifact_index.py validate`

Next phased execution:
- Phase E1: decide whether to make the compact shell the active reader or build a drop-in compatibility payload for existing dashboard JS.
- Phase E2: if keeping current JS, prove the compatibility payload carries every concrete row/table value expected by `scripts/dashboard-js/*.js` without embedding the entire legacy payload.
- Phase E3: if moving to compact reader, migrate the active HTML shell to consume compact panel DTO/view-model contracts directly and pass dashboard acceptance.
- Phase E4: only after one of those passes, consider replacing or thinning `tmp/dashboard-data.json`.

Stop lines:
- Do not delete, archive, or move existing HTML/Markdown sidecars.
- Do not replace `tmp/dashboard-data.json` until drop-in readiness is proven or a compact-reader replacement passes acceptance.
- Do not widen authority: no canon/portfolio/SQL-canon mutation, customer/public output, paper/live/brokerage/account action, capital deployment, trade execution, or owner approval inference.

## Pickup Checkpoint - 2026-06-05 20:09 MST

Closeout proof after the parallel implementation run:
- `python scripts\presentation_render_default_compatibility.py --write --validate` remains ok: `safe_default_disable_count=4`, `unsafe_or_unproven_default_disable_count=0`, `owner_defaults_json_first=true`, `sidecars_explicit_only=true`.
- `python scripts\dashboard_shrink_readiness_score.py --write --validate` remains blocked only on `compatibility_payload_not_drop_in_ready`.
- `tmp/dashboard-shrink-readiness-score.json` still shows 100% route coverage and compact shell active-reader readiness, but the legacy dashboard JS still has 29 row/table dependency sections. Do not replace `tmp/dashboard-data.json` yet.
- Artifact index rebuilt and validated after the proof loop: 28 checks, 0 failed.

Next phased execution:
- Phase E remains the only open presentation-flattening lane.
- Either prove a drop-in compatibility payload for the current dashboard JS, or migrate the active shell to compact DTO/view-model reader contracts and pass dashboard acceptance.

Stop lines unchanged:
- No proof deletion/archive.
- No sidecar removal.
- No `tmp/dashboard-data.json` replacement until drop-in readiness or compact-reader replacement is proven.
- No canon/portfolio/SQL-canon mutation, customer/public output, paper/live/brokerage/account action, capital deployment, trade execution, or owner approval inference.
