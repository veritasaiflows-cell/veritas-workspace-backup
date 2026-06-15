# Workflow 64 - Bounded Portfolio Agent Cron Architecture

## Objective

Design and harden bounded cron/helper-agent paths that verify portfolio truth, generate exact portfolio note/model proposals, and autonomously apply standing-approved workspace portfolio/canon maintenance for entry bands, earnings/catalyst state, ticker state, sleeves, sizing/draft weights, sector posture, and related artifacts without widening brokerage, trade, account, money-movement, credential, or external execution authority.

## Current state - 2026-05-15 Phase 1 foundations verified

Status: **Standing-approved autonomous workspace portfolio/canon maintenance posture active; exact gated apply foundation exists; cron direct apply remains blocked until category-specific repeated proof is promoted.**

Parallel pre-review lanes completed:
- **Cron architecture review:** `SAFE_WITH_GAPS`. Safe to design as bounded review/proof architecture; not safe for cron to directly apply sizing/sleeve/sector/canonical mutations.
- **Freshness/write coverage review:** `SAFE_WITH_GAPS`. Entry-band maintenance has strongest coverage; sleeve, sector posture, and sizing writes remain proposal/preview scaffolding until stale/conflict cleanup and approval-gated apply hardening improve.
- **WF63 no-order paper-readiness review:** `BLOCKED`. Paper-readiness guardrails are safe, but read-only connection proof remains blocked by missing paper credentials and no paper trades/orders may be placed.

Main-session verification after the WF64 implementation lane:
- `portfolio_mutation_exact_patch_generator.py` now generates review-only exact patch material for `entry_band`, `sleeve`, `sizing`, and `sector_posture` categories, currently anchored to the ETN capital-review packet only.
- `proposal_patch_scope_validator.py` now enforces category/file ownership for generated patch material.
- `portfolio_mutation_patch_preview_validator.py` and `portfolio_mutation_proposal_verifier.py` verify exact patch semantics, authority flags, freshness blockers, and non-write posture.
- `portfolio_mutation_apply_helper.py` now has a WF64 approval-gated atomic apply foundation: `--plan-apply` builds a no-write rollback/backup plan, `--apply` is blocked unless the scoped approval artifact validator passes, writes are exact old/new text replacements, backups are created under `tmp/portfolio-mutation-proposals/apply-backups/`, and failed applies auto-restore from backup. Tests exercise only temp fixtures under `tmp/portfolio-mutation-proposals/`.
- `tmp/portfolio-mutation-proposals/verifier-report.json/.md` now exist and verify the proposal/proof set with `0 critical / 9 warning`; warnings are partial/stale review-required freshness with explicit blockers.
- `post_apply_validation_chain.py` now validates the approval artifact before executing post-apply validators; draft/invalid approval artifacts block before the chain runs.
- Approval artifacts must name approved adjustment categories that cover the exact patch categories.
- Targeted tests pass after updating stale authority/test expectations so they no longer imply owner approval.

## Architecture decision

Use a four-lane model:

1. **Research truth lane**
   - Mechanism: existing morning/post-close/Sunday finance and research cron chains.
   - Authority: generate evidence/freshness/sector/technical/opportunity artifacts only.

2. **Proposal generation lane**
   - Mechanism: cron-safe script/subagent output under `tmp/`.
   - Authority: generate capital recommendation packets, mutation proposals, exact patch previews, and validation reports.
   - Default authority: `apply_allowed=false`, `owner_approval_granted=false`, `trade_or_account_action_allowed=false`.

3. **Verifier/challenger lane**
   - Mechanism: read-only bounded verifier after proposal generation.
   - Authority: challenge freshness, owner-note conflicts, category ownership, stale/manual dependencies, and authority flags.
   - Output target: future `tmp/portfolio-mutation-proposals/verifier-report.json`.

4. **Autonomous workspace apply lane**
   - Mechanism: main-session Veritas applies exact scoped workspace portfolio/canon mutations under Randall's 2026-05-16 standing approval, with cron limited to proposal/verifier/artifact preparation unless a future narrow category is explicitly promoted.
   - Authority: exact scoped canonical note/model write only when a standing-approval artifact is explicit, unexpired, hash-matched, target-file-matched, category-matched, and validators pass. Trading/account/brokerage/money movement remains blocked.

## Required trust artifacts before any write

- Proposal packet with explicit false authority fields.
- Exact patch preview with target files, old/new text, diff hash, category, source evidence, and rollback context.
- Standing-approval or scoped-approval artifact with approved proposal id, approved target files, approved categories, expiration, exact diff hash, and all trade/account/brokerage/money/external-execution flags false.
- Pre-apply validator bundle.
- Post-apply result and validation bundle.
- Main-session handoff that names whether write is blocked or eligible.

## Human-gated fields

Must remain exact-gated and main-session/standing-approval scoped:
- sizing/draft weights
- sleeves
- sector posture
- ticker state
- earnings/catalyst state
- promotion/demotion state inside workspace canon
- cash targets and risk rules only when separately scoped
- execution entitlement remains externally owner-gated
- any trade/account/brokerage action

Potential auto-eligible only after repeated proof and narrow rules:
- machine-eligible entry-band maintenance where canonical apply eligibility is already validated
- reference-band visibility refresh
- bounded freshness/status sync that does not change capital authority

## Current blocking gaps

- Generalized semantic patch generation remains incomplete: exact material is still mostly ETN-anchored/visibility-oriented, so autonomous workspace applies must remain exact-artifact scoped until broader semantic generators and coherence validators exist.
- Source freshness is explicitly resolved but not clean: proposal verification reports partial/stale review-required warnings with explicit blockers, mainly warning-grade upstream artifacts and event-risk/freshness limits.
- JPM Portfolio Snapshot deployable-now residue has been reconciled to **approval recorded / trigger not live**; broader JPM config ticker-state/formal-band semantics remain higher-consequence and require the exact gated apply path before mutation.
- `tmp/portfolio-config.json` top-level freshness was refreshed and validates structurally clean, but some semantic/model-spine changes remain gated rather than hand-edited.
- Atomic apply/rollback foundation exists; broader category writes still require post-apply board/snapshot/config coherence proof and an exact approved artifact.

## Required validators / proof gates

Pre-apply:
1. proposal schema validator
2. capital deployment recommendation validator
3. category/file ownership validator
4. proposal patch scope validator
5. exact preview validator
6. approval artifact validator
7. authority vocabulary consistency check
8. stale/source/manual-dependency gate

Post-apply:
1. scoped apply result check
2. canonical ownership validation
3. portfolio config validation
4. dashboard validation
5. pipeline state consistency check
6. full portfolio view regeneration/validation
7. board/canon guardrail
8. stale-intelligence guardrail
9. direct owner-note inspection

## Stop lines

Block and no-op if:
- owner notes conflict with generated artifacts
- freshness is stale/partial/contradictory/manual-dependent for decision-critical fields
- required artifact or validator is missing/blocked/error
- proposal implies owner approval, sizing, execution, trade, or account authority outside the approved gate
- approval artifact is missing, expired, draft, hash-mismatched, or target-file-mismatched
- exact old text is not unique
- target file does not own the field category
- any brokerage/order/money/account path appears
- cron attempts owner-file apply outside already-approved narrow automation

## Next implementation pass

1. Strengthen post-apply validation-chain result inspection for board/snapshot/config coherence before broad category writes.
2. Create exact approval-artifact templates per category only when Randall approves a specific proposal id, target files, categories, and diff hash.
3. Expand exact patch generation beyond the current ETN-anchored preview path only after category owner surfaces and source freshness are clean enough for the specific write.
4. Keep all generalized writes disabled until repeated proof and an exact approval artifact exist.

## 2026-06-07 - Approved entry-band doctrine and table-format updater hardening

Randall approved the operating doctrine that the system owns fresh reference bands and routine technical entry-band/stop maintenance when proposals are posture-preserving, source-fresh, validator-clean, and inside the bounded `entry_band` gate. Randall remains responsible for exceptions, policy changes, invalidation/reclaim judgment, capital deployment, and execution decisions.

Implementation completed:
- Hardened `scripts/auto_apply_entry_band_maintenance.py` for the current table-format `03. Portfolio/Execution Board.md`.
- Dry-run now preflights the same board update path as apply.
- The updater requires current table columns, reports missing table rows separately from missing parser-compatible sections, blocks only when a ticker is missing from both, and prepares all board text before writing owner files.
- Added regression coverage in `scripts/test_auto_apply_entry_band_maintenance.py` for current table updates, table-only safe updates, missing-everywhere fail-closed behavior, and cron manifest ordering.
- Applied the scoped eligible no-risk-level-change maintenance rows for `VRT` and `GS`; both already matched the current numeric low/high/stop, so the apply refreshed maintenance proof/metadata without changing risk levels.

Proof:
- `python -m py_compile scripts\auto_apply_entry_band_maintenance.py scripts\test_auto_apply_entry_band_maintenance.py`
- `python scripts\test_auto_apply_entry_band_maintenance.py`
- `python scripts\auto_apply_entry_band_maintenance.py --dry-run`
- `python scripts\auto_apply_entry_band_maintenance.py --apply`
- `python scripts\validate_portfolio_config.py` -> ok / 0 warnings
- `python scripts\validate_canonical_ownership.py` -> ok / 0 critical / 0 warnings
- `python scripts\deployment_check.py`
- `python scripts\trigger_sheet_refresh.py`
- `python scripts\canon_volatile_execution_board_sync.py --apply --strict-exit`
- `python scripts\canon_drift_freshness_gate.py --write --strict-exit`
- `python scripts\test_dashboard_acceptance.py` -> 29/29 passed
- `python scripts\generate_dashboard.py`
- `python scripts\validate_dashboard_state.py --write` -> 0 critical / 1 known warning for suspended legacy model weight gap

Authority boundary:
- `entry_band` maintenance may run through the approved scoped cron/refresh path.
- No capital deployment, trade execution, paper/live order authority, brokerage/account action, money movement, cash/sizing/sleeve/risk-rule mutation, owner-approval inference, or broader canon apply authority was created.

## 2026-05-24 09:23 MST - entry-band / ticker-state advancement plan

- Parallel planning and independent challenge lanes completed for WF64/WF56 entry-band + technical/ticker-state applies. Decision: reuse the existing gated spine (`semantic_preview_bundle` -> patch preview -> standing approval artifact -> apply helper -> post-apply validation chain); do not create a new script yet.
- Safe material advancement completed: regenerated `tmp/portfolio-mutation-proposals/semantic-preview-bundle.json/.md` for `GOOG`, `GS`, and `MSFT` across `entry_band` and `ticker_state` using `python scripts\portfolio_mutation_semantic_preview_bundle.py --tickers GOOG GS MSFT --categories entry_band ticker_state --write`.
- Result: 6/6 rows ok, 0 critical, `writes_performed=false`; live assertions showed each generated preview has `old_text_match_count=1` and false authority flags.
- Blocker: all six regenerated material rows still carry `source_freshness.overall_classification=partial` and `explicit_blocker=true`; owner-file apply remains blocked until main-session freshness adjudication clears one exact candidate.
- First candidate if cleared: GOOG `entry_band` semantic sync only, adding config low/high/stop visibility `355.35 to 378.98 / stop 334.58` from `tmp/portfolio-config.json`; no sizing/sleeve/sector/cash/risk-rule/execution entitlement or external action authority.
- Cron-direct apply remains unsafe/blocked. Cron may generate proposal/verifier artifacts only until a separate category-promotion artifact proves repeated regenerated previews, stale/manual-review hard blocks in approval generation, approval/diff/target hash replay proof, rollback, and post-apply coherence.
## 2026-05-15 late - promotion requires band/stop closure before apply/readiness
- Added an invariant for future bounded portfolio-agent proposal/write readiness: any ticker promotion or portfolio-review upgrade must include numeric entry-band low/high/stop proof and downstream propagation proof before a proposal can be treated as complete.
- Guardrail now required in promotion/apply packets: missing numeric band/stop, sentinel labels, dashboard-only prose bands, or false-green deployable state are blocking conditions.
- Main-session apply remains owner-gated; cron/helper lanes may generate the proof/proposal, but cannot infer approval from clean validation.

### Post-apply coherence and approval-template hardening - 2026-05-16

WF64 now has blocked-by-default exact approval templates for `entry_band`, `sleeve`, `sizing`, and `sector_posture`: `scripts/write_wf64_approval_templates.py` writes templates under `tmp/portfolio-mutation-proposals/approvals/templates/`, and `scripts/test_wf64_approval_templates.py` verifies they default to `owner_approval_granted=false`, no scoped/canonical write authority, no inferred approval, no trade/account/brokerage/money movement/execution entitlement, exact proposal/category/target/diff hash, expiry, and validator proof requirements. Draft templates intentionally validate as blocked until explicit owner approval flips the required gates.

WF64 also now has `scripts/post_apply_board_snapshot_config_coherence.py`, a post-apply validator that can run generic authority-language checks or approval-scoped checks against an approval artifact. It verifies approved target files contain the approved replacement text and performs category-aware board/snapshot/config coherence checks for entry bands, sleeve, sizing, and sector posture. `scripts/post_apply_validation_chain.py` now passes `--approval-artifact` through to this coherence validator when supplied, so scoped post-apply checks are not silently downgraded to generic-only mode. Latest proof: approval-template tests passed; direct coherence check against the blocked entry-band template returned `status=ok`, 0 critical / 0 warning, with `03. Portfolio/Execution Board.md` checked; dry-run post-apply chain returned `status=ok`, 13 planned steps, and re-QC passed.


## 2026-05-16 authority expansion - autonomous workspace portfolio management

Randall explicitly approved portfolio/canon mutation for entry bands, earnings state, sleeves, sizing, and related artifacts to keep the portfolio updated, while keeping all trading owner-gated. WF64 now treats autonomous portfolio management as **workspace portfolio/canon maintenance**, not brokerage execution.

Implementation posture:
- Proposal packets should generally keep non-authorizing flags false; they are evidence/proposal surfaces.
- Write authority belongs in a scoped standing-approval artifact produced from exact validated proposal + preview material.
- `portfolio_mutation_standing_approval_artifact.py` creates exact scoped approval artifacts under the 2026-05-16 standing policy, only for supported categories and only with trade/account/brokerage/money/external-execution flags false.
- `portfolio_mutation_approval_artifact_validator.py` now recognizes `earnings_state` as an approved adjustment category.
- `proposal_patch_scope_validator.py` maps `earnings_state` to `Execution Board`, `Coverage and Watchlist`, and `tmp/portfolio-config.json`.
- `post_apply_board_snapshot_config_coherence.py` now includes initial earnings-state coherence checks.

Next build phases:
1. Generalize exact patch generation beyond ETN visibility notes into semantic category generators for entry_band, ticker_state, earnings_state, sleeve, sizing, and sector_posture.
2. Promote post-apply coherence from visibility warnings to stronger semantic checks for board/snapshot/config/risk-rule consistency.
3. Only after repeated clean proof, consider narrow cron-direct apply for low-risk maintenance categories; sizing/sleeves/sector posture should stay main-session applied until enough evidence proves otherwise.

### First standing-approved live apply proof - 2026-05-16

WF64/WF56 completed the first standing-approved workspace maintenance apply under Randall's 2026-05-16 autonomous portfolio-management posture. Veritas generated a standing approval artifact for the ETN `entry_band` exact patch, confirmed the scoped apply helper was ready, executed the exact owner-file replacement in `03. Portfolio/Execution Board.md`, and then repaired post-apply validation residue that was caused by validators rechecking already-applied `old_text` plus unrelated stale guardrail state.

Implementation deltas:
- `scripts/portfolio_mutation_standing_approval_artifact.py` creates exact standing-approved artifacts from validated proposal + preview material.
- `earnings_state` is now an approved category in approval, patch-scope, and coherence validators.
- `scripts/post_apply_validation_chain.py` can proceed post-apply when the only approval-validator failure is that the approved `old_text` was already applied and a successful apply result exists.
- `scripts/portfolio_pro_forma_risk_validator.py` ignores approval artifacts and only validates actual proposal packets, preventing false failures from approval metadata.
- `scripts/regime_scoring_refresh.py` now derives below-stop state directly from close versus stop and forces stop-breached / do-not-touch language into regime scoring.
- JPM below-stop residue was reconciled across `03. Portfolio/Execution Board.md`, `03. Portfolio/Portfolio Snapshot.md`, `05. Intelligence/Weekly Positioning Review.md`, and `02. Markets/Regime Scoring Matrix.md`.

Latest proof:
- `python -m py_compile` passed for the changed WF64/WF56 scripts/tests.
- `python scripts\test_portfolio_mutation_standing_approval_artifact.py` passed.
- `python scripts\test_wf64_approval_templates.py` passed after regenerating templates against the live preview hash.
- `python scripts\test_portfolio_mutation_phase4_scoped_apply.py` passed with dynamic exact-text fixtures.
- `python scripts\validate_canonical_ownership.py` returned needs_review with 0 critical / 8 warning after adding parser-compatible ETF coverage sections for XLI/XLB/XLC/PAVE/XLF/XLE/ITA/VAW.
- `python scripts\board_canon_guardrail.py --write` returned warning-only: 0 critical / 13 warning.
- `python scripts\stale_intelligence_guardrail.py --write` returned ok: 0 critical / 0 warning.
- `python scripts\portfolio_pro_forma_risk_validator.py --write` returned ok: 0 critical / 0 warning.
- `python scripts\post_apply_validation_chain.py --execute --approval-artifact tmp\portfolio-mutation-proposals\approvals\standing-approved\standing-post-close-ETN-capital-deployment-review-2026-05-16-20260517T041102Z.json --window post-close --write` returned ok: 0 failed.
- `python scripts\current_window_artifact_index.py --write` returned ok: 41/41.

Remaining residue: generalized semantic patch generation is still the next real build phase; the first live apply proves the standing-approved exact-gate path, not broad cron direct-apply. Cron remains proposal/verifier-first. Trading/account/brokerage/money movement/external execution entitlement remain blocked.


### Semantic category generator scaffold - 2026-05-16

WF64 now has a separate semantic exact-patch generator scaffold for the six requested autonomous workspace-maintenance categories: `entry_band`, `earnings_state`, `ticker_state`, `sleeve`, `sizing`, and `sector_posture`.

Implemented:
- `scripts/portfolio_mutation_semantic_patch_generator.py` reads current proposal packets plus `tmp/portfolio-config.json` and, for earnings, `tmp/earnings-calendar.json`.
- The generator emits exact old/new text patch material under `tmp/portfolio-mutation-proposals/semantic-patch-material/` and keeps proposal packets non-self-applying.
- Board-owned categories target `03. Portfolio/Execution Board.md`: `entry_band`, `earnings_state`, `ticker_state`.
- Snapshot-owned categories target `03. Portfolio/Portfolio Snapshot.md`: `sleeve`, `sizing`, `sector_posture`.
- Generated text is scrubbed for forbidden authority vocabulary so validator-safe semantic context does not imply approval or external action authority.
- `scripts/test_portfolio_mutation_semantic_patch_generator.py` verifies all six categories generate one exact replacement, target the correct owner surface, preserve false authority flags, and avoid forbidden action/approval words in patch text.

Current proof:
- `python -m py_compile scripts\portfolio_mutation_semantic_patch_generator.py scripts\test_portfolio_mutation_semantic_patch_generator.py`
- `python scripts\test_portfolio_mutation_semantic_patch_generator.py`
- For each category (`entry_band`, `earnings_state`, `ticker_state`, `sleeve`, `sizing`, `sector_posture`):
  - `python scripts\portfolio_mutation_semantic_patch_generator.py --ticker ETN --category <category> --write`
  - `python scripts\proposal_patch_scope_validator.py tmp\portfolio-mutation-proposals\semantic-patch-material\post-close-ETN-capital-deployment-review-2026-05-17-<category>.json --write`
  - `python scripts\portfolio_mutation_patch_preview_validator.py --proposal-bundle tmp\portfolio-mutation-proposals\semantic-patch-material\post-close-ETN-capital-deployment-review-2026-05-17-<category>.json --write`
- All six categories passed with 0 critical / 0 warning.

Boundary: these are exact semantic patch materials only. They do not write owner files, do not self-apply, do not grant owner approval, and do not authorize any external financial action. Standing/scoped approval artifacts and post-apply validation remain required before any actual workspace mutation.

Next pass: expand semantic generation beyond the current ETN proof path toward broader ticker/category coverage; keep cron direct-apply blocked until a narrow category has repeated clean proof.

### Semantic preview bundle and second standing-approved apply proof - 2026-05-16

WF64/WF56 now has a semantic preview bundle/report for all six bounded workspace-maintenance categories: `entry_band`, `earnings_state`, `ticker_state`, `sleeve`, `sizing`, and `sector_posture`.

Implemented:
- Added `scripts/portfolio_mutation_semantic_preview_bundle.py` and `scripts/test_portfolio_mutation_semantic_preview_bundle.py`.
- The bundle report writes `tmp/portfolio-mutation-proposals/semantic-preview-bundle.json` and `.md`, one row per category, with material artifact path, preview artifact path, target file, validator status, critical count, and explicit no-write/no-external-action authority.
- `SOUL.md`, `skills/veritas-bounded-portfolio-agent/SKILL.md`, `skills/veritas-portfolio-update/SKILL.md`, and Active Workflows now name the exact standing-approved categories and the main-session gated apply boundary.
- `scripts/portfolio_mutation_semantic_patch_generator.py` now omits null source-artifact placeholders.

Low-risk apply trial:
- Veritas inspected the generated ETN `entry_band` and `earnings_state` diffs.
- `entry_band` was selected because it was useful and non-duplicative: it added explicit config low/high/stop semantic context under the existing ETN preferred-band line without changing the band itself.
- Generated standing approval artifact: `tmp/portfolio-mutation-proposals/approvals/standing-approved/standing-post-close-ETN-capital-deployment-review-2026-05-17-20260517T044530Z.json`.
- Applied exact diff through `portfolio_mutation_apply_helper.py --apply`; one line was written to `03. Portfolio/Execution Board.md` and rollback was not needed.

Latest proof:
- `python -m py_compile scripts\portfolio_mutation_semantic_patch_generator.py scripts\portfolio_mutation_semantic_preview_bundle.py scripts\test_portfolio_mutation_semantic_preview_bundle.py scripts\portfolio_mutation_standing_approval_artifact.py`
- `python scripts\test_portfolio_mutation_semantic_patch_generator.py`
- `python scripts\test_portfolio_mutation_semantic_preview_bundle.py`
- `python scripts\portfolio_mutation_semantic_preview_bundle.py --ticker ETN --write` returned ok, 6/6 categories, 0 critical, writes_performed=false.
- Standing approval artifact validation returned ok with 0 critical / 0 warning.
- Apply helper plan returned ready; apply returned `applied_pending_post_apply_validation`, 1 file written, rollback_performed=false.
- `python scripts\post_apply_validation_chain.py --execute --approval-artifact tmp\portfolio-mutation-proposals\approvals\standing-approved\standing-post-close-ETN-capital-deployment-review-2026-05-17-20260517T044530Z.json --window post-close --write` returned ok, 0 failed.
- `python scripts\validate_canonical_ownership.py` returned needs_review with 0 critical / 8 warning.
- `python scripts\board_canon_guardrail.py --write` returned warning-only: 0 critical / 13 warning.
- `python scripts\stale_intelligence_guardrail.py --write` returned ok: 0 critical / 0 warning.
- `python scripts\portfolio_pro_forma_risk_validator.py --write` returned ok: 0 critical / 0 warning.
- `python scripts\current_window_artifact_index.py --write` returned ok, 41/41.
- `openclaw skills check` showed all visible skills eligible/visible and no missing requirements, but still emitted the known Windows symlink EPERM warning for plugin skill publication.

Boundary: this proves another exact main-session gated workspace-maintenance apply, not cron direct-apply. Generated semantic bundles remain non-self-applying; all future writes still require exact material, preview hash, standing/scoped approval artifact, validators, backup/rollback, post-apply proof, and no trade/account/brokerage/money movement authority.

### Broader semantic pilot and why-aware packet hardening - 2026-05-17

WF64 broadened semantic preview generation beyond the ETN-only proof path while preserving the main-session gated apply boundary. Two bounded helper lanes were used first: a worker lane identified GOOG/GS as clean all-category pilots and MSFT as a partial pilot; an audit lane challenged freshness, category risk, and cron-direct-apply readiness. Main-session implementation kept cron proposal/verifier-first and did not apply owner-file changes.

Implemented:
- `scripts/portfolio_mutation_semantic_preview_bundle.py` now supports a multi-ticker pilot set via `--tickers`, while retaining single-ticker compatibility. Bundle summaries now separate freshly generated rows from `already_current` rows so readiness stats are not inflated by idempotence.
- `scripts/portfolio_mutation_semantic_patch_generator.py` now attaches a category/source gate to generated exact patch material. `entry_band` and narrow `ticker_state` remain the only low-risk apply-trial candidates from the generator; `sleeve`, `sizing`, and `sector_posture` are explicitly preview-only due to portfolio-construction semantics. Source freshness/manual-review state is surfaced as an apply-trial blocker, not hidden behind syntactic success.
- `scripts/post_apply_board_snapshot_config_coherence.py` now resolves ticker/category from the approval plus preview, performs approval-scoped category checks, treats missing applied entry-band low/high/stop visibility as critical for an approved `entry_band` apply, and detects duplicate ticker semantic sync lines for snapshot categories.
- Capital recommendation packets now carry a structured `why_stack` / `decision_rationale`, and the report renders ?why this is here / why not action yet.? Validators require the why block and preserve official-earnings manual-required/review-only posture.

Latest proof:
- `python -m py_compile scripts\portfolio_mutation_semantic_patch_generator.py scripts\portfolio_mutation_semantic_preview_bundle.py scripts\post_apply_board_snapshot_config_coherence.py scripts\daily_review_objects.py scripts\portfolio_mutation_proposal_generator.py scripts\capital_deployment_recommendation_report.py scripts\capital_deployment_recommendation_validator.py` passed.
- `python scripts\test_portfolio_mutation_semantic_patch_generator.py` passed.
- `python scripts\test_portfolio_mutation_semantic_preview_bundle.py` passed.
- `python scripts\daily_review_objects.py --window post-close` produced 4 capital recommendations.
- `python scripts\portfolio_mutation_proposal_generator.py --window post-close --write`, `python scripts\capital_deployment_recommendation_report.py --write`, and `python scripts\capital_deployment_recommendation_validator.py --write` passed with 4 packets, 0 critical / 0 warning.
- `python scripts\portfolio_mutation_semantic_preview_bundle.py --tickers GOOG GS --write` returned 12/12 rows ok, 0 critical, writes_performed=false.
- `python scripts\portfolio_mutation_semantic_preview_bundle.py --ticker MSFT --categories earnings_state ticker_state sleeve sizing sector_posture --write` returned 5/5 rows ok, 0 critical, writes_performed=false. MSFT `entry_band` remains deferred because the existing board anchor contains forbidden owner-approval wording.
- Final staged bundle `python scripts\portfolio_mutation_semantic_preview_bundle.py --tickers GOOG GS MSFT --categories earnings_state ticker_state sleeve sizing sector_posture --write` returned 15/15 rows ok, 0 critical, writes_performed=false.
- `python scripts\post_apply_board_snapshot_config_coherence.py --approval-artifact tmp\portfolio-mutation-proposals\approvals\standing-approved\standing-post-close-ETN-capital-deployment-review-2026-05-17-20260517T044530Z.json --write` returned ok, 0 critical / 0 warning.
- Canonical ownership remains warning-only: 0 critical / 8 warning; board-canon guardrail remains warning-only: 0 critical / 13 warning; stale-intelligence 0/0; pro-forma risk 0/0; current-window artifact index ok 41/41.

Boundary: broader semantic generation is now proven as preview material for GOOG/GS/MSFT, but no generalized owner-file apply occurred in this pass. Cron direct apply remains blocked; sizing/sleeve/sector posture stay preview-only; all future writes still require exact material, preview, standing/scoped approval artifact, validators, backup/rollback, and post-apply proof. Trading/account/brokerage/money movement/external execution remain blocked.

### Next semantic apply candidate review - 2026-05-17

A bounded read-only WF64/WF56 candidate lane reviewed the next possible beyond-ETN semantic apply. The ranked result was:

1. GOOG `ticker_state` is the best next semantic maintenance candidate. Exact text is unique, useful, and non-duplicative; it would add explicit WF64 state sync for `workflow_state=ALMOST`, `coverage_lane=execution`, and `thesis_status=intact` without external-action authority.
2. GS `ticker_state` is second-best but has higher Financials/JPM relationship and bank-review context.
3. MSFT `ticker_state` should not be applied until a state conflict is reconciled: proposal/current-state language is not aligned with the board's deployed/manual posture.

Main-session proof refreshed GOOG `ticker_state` as preview-only:
- `python scripts\portfolio_mutation_semantic_preview_bundle.py --ticker GOOG --categories ticker_state --write` returned ok, 1/1 rows, 0 critical, writes_performed=false.
- `python scripts\proposal_patch_scope_validator.py tmp\portfolio-mutation-proposals\semantic-patch-material\post-close-GOOG-capital-deployment-review-2026-05-17-ticker_state.json` returned ok, 0 critical / 0 warning.
- `python scripts\portfolio_mutation_patch_preview_validator.py --proposal-bundle tmp\portfolio-mutation-proposals\semantic-patch-material\post-close-GOOG-capital-deployment-review-2026-05-17-ticker_state.json` returned ok, 0 critical / 0 warning.

Decision: no owner-file apply in this pass. GOOG remains the best next apply-trial candidate, but the generated source gate is stale/review-required, so it stays preview-only until freshness/blocker review is resolved or explicitly accepted in a main-session gated apply. Sizing, sleeve, and sector posture remain preview-only.

