# Workflow 58 - Dashboard Freshness, Entry Bands, Capital Recommendations, and Discrepancy Automation

## Objective

Make the finance dashboard and generated review layer fresh enough for presentation, bounded main-session canonical-sync review, scoped automatic entry-band maintenance, fresh reference-band visibility, guarded portfolio note/model mutation support, and capital-deployment recommendation packets without granting trade/account execution, brokerage/money movement, inferred per-packet approval, or unscoped execution entitlement.


## Status - 2026-05-20 bounded volatile canon freshness sync

Status: **Implemented / proof-clean; post-close chain unblocked with warning-grade residue only**.

Randall approved keeping all tickers fresh in canon. Implemented a bounded generic freshness-maintenance path that updates volatile ticker canon state from fresh generated artifacts without changing trade/account authority, cash, sizing, sleeve, risk-rule, owner approval, or execution entitlement.

Implemented:
- New `scripts/canon_volatile_execution_board_sync.py` syncs volatile Execution Board table fields, parser-compatible ticker technical sections, Portfolio Snapshot date headers, and bounded numeric band/stop prose in `tmp/portfolio-config.json` from `tmp/technical-refresh.json`, `tmp/deployment-check.json`, `tmp/trigger-sheet.json`, and current `entry_bands`.
- `scripts/chain_manifest.py` now runs `canon_volatile_execution_board_sync.py --apply --strict-exit` and then `canon_drift_freshness_gate.py --write --strict-exit` before dashboard acceptance in morning, post-close, post-earnings, and Sunday windows.
- `scripts/run_finance_refresh_chain.py` now writes a best-effort recovery canon-drift report after any failed step so early chain failures still leave drift proof.
- `scripts/test_dashboard_acceptance.py` no longer hard-codes JPM as below-stop; JPM/other ticker state must follow fresh artifact math (`below_stop` / `close < stop`) and may be almost-deployable/trigger-not-live when above stop but below band.

Proof:
- `python -m py_compile scripts\canon_volatile_execution_board_sync.py scripts\chain_manifest.py scripts\run_finance_refresh_chain.py scripts\test_dashboard_acceptance.py`
- `python scripts\canon_volatile_execution_board_sync.py --apply --strict-exit` -> ok
- `python scripts\canon_drift_freshness_gate.py --write --strict-exit` -> ok, 0 findings
- `python scripts\board_canon_guardrail.py --write` -> ok, 0 findings
- `python scripts\test_dashboard_acceptance.py` -> 26/26 passed
- `python scripts\run_finance_refresh_chain.py post-close` -> process exit 0; `tmp/run-chain-post-close.json` status ok / exit_code 0; refreshed `tmp/run-summary-post-close.json` has stop_line=false, chain_status ok, acceptance_passed=true.

Remaining residue:
- Post-close summary remains `warning`, not blocked: dashboard validation has warning-grade items including NVDA event-risk band freeze, VRT in-band/watch-state caution, and active-weight/cash note. These require review, not execution authority.
- Scheduled windows remain fail-closed for canonical note mutation from cron; main-session bounded canon maintenance remains the owner-approved path.

## Status - 2026-05-15 priority Command Center hardening pass

Status: **Priority active / hardening pass integrated; scheduled proof monitoring remains**.

Randall promoted WF58 back to the top workflow after Command Center screenshots exposed residual UI/truth-surface defects. Veritas ran parallel lanes: a read-only QC challenger returned **SAFE WITH GAPS**, and an implementation lane generalized the hardening. Main-session integration then corrected two residues the lane left behind: handoff proof state now treats worker artifacts as insufficient proof for main-session handoffs, and the legacy `today_action.actionable` alias is constrained to clean deployable cards only.

Implemented in this pass:
- Ticker-agnostic machine/prose conflict guard: green/deployable machine states fail closed when research/prose/owner evidence says trigger-not-live, approval-on-hold, below formal band, below stop, repair, frozen, or review-only.
- JPM canonical sync in `03. Portfolio/Execution Board.md`: JPM is now **Approval recorded / trigger not live**, not deployable-now, with the parser-vs-research band conflict explicit.
- Dashboard trust panel now shows handoff proof state: weekday research **PROVED**; morning, post-close, Sunday weekly, and Sunday research **PENDING_FIRST_PROOF** until main-session handoff proof exists.
- Ticker/action cards and tables carry traceability: source artifact path, generated timestamp, band staleness, override rule, and earnings confirmation context where available.
- Legacy `today_action.actionable` is clean-deployable-only so older consumers cannot treat authority-conflict or almost-review cards as actionable.
- Acceptance tests now cover generic non-JPM authority conflicts, duplicate conflict-card prevention, handoff proof state, conflict-card traceability, capital recommendation visibility, and the upstream deployment-readiness conflict guard.

Final proof:
- `python -m py_compile scripts\dashboard_payload.py scripts\deployment_readiness_surface.py scripts\test_dashboard_acceptance.py`
- `python scripts\deployment_readiness_surface.py --window post-close`
- `python scripts\generate_dashboard.py`
- `python scripts\validate_dashboard_state.py --write`
- `python scripts\test_dashboard_acceptance.py`
- final artifact refresh repeated after tests: deployment surface + dashboard generation + dashboard validation.

Verified final state:
- `tmp/deployment-readiness-surface.json`: `DEPLOYABLE NOW: 1`, `AUTHORITY CONFLICT: 1`.
- `tmp/dashboard-data.json`: deployable summary `['ETN']`; promotion-review summary `['JPM']`; JPM renders once as `AUTHORITY CONFLICT`; legacy `today_action.actionable` contains only ETN; capital recommendations list ETN / GOOG / GS / MSFT.
- `tmp/dashboard-validation.json`: 0 critical / 1 warning, the expected NVDA event-risk band-freeze warning.

## Status - 2026-06-18 handoff proof-state simplification

Status: **Implemented / proof-clean; source lanes still repair-needed**.

Randall challenged the Command Center handoff pills because morning, post-close, Sunday weekly, and Sunday research were all stuck as `PENDING_FIRST_PROOF` with no proof artifact. The issue was not just a dashboard display problem: cron/main-session needed an actionable source-of-truth packet instead of pushing the mismatch into a generic queue.

Implemented:
- Added `scripts/handoff_first_proof_gate.py` and output `tmp/main-session-handoff-first-proof.json`.
- Replaced hard-coded handoff proof states in `scripts/dashboard_payload.py` with the gate output.
- Dashboard handoff rows now carry lane state, tone, proof artifact, generated timestamp, source status/blockers, and repair action.
- Acceptance tests now allow the full lane vocabulary: `PROVED`, `BLOCKED`, `MISSING`, `STALE`, and `PENDING_FIRST_PROOF`.

Current verified lane state:
- Weekday research: `PROVED`.
- Morning: `BLOCKED` from the existing blocked run summary / chain recovery state.
- Post-close: `BLOCKED` from the existing blocked run summary / chain recovery state.
- Sunday weekly: `BLOCKED` from the current weekly brief trust gate.
- Sunday research: `MISSING` because no real `tmp/sunday-research-review.json` producer is wired yet.

Proof:
- `python scripts\handoff_first_proof_gate.py --write --validate` -> `status=warning proved=1 repair=4`
- `python scripts\test_handoff_first_proof_gate.py`
- `python scripts\test_dashboard_handoff_sql.py`
- `python scripts\test_dashboard_acceptance.py`
- `python scripts\generate_dashboard.py`

Boundary: this did not promote blocked handoff artifacts, run finance producers, mutate portfolio/canon, or imply any capital/execution approval. It made the dashboard honest and gave cron/main-session a repair packet to act from.

Follow-on on 2026-05-15/16: after the sector-expansion pass, all 41 tracked names have reference entry bands/stops in `tmp/portfolio-config.json`, and the dashboard regenerated with fresh earnings dates for newly tracked equities. Current proof from the follow-on pass: `validate_portfolio_config.py` ok with 41 checked tickers / 0 warnings; `generate_dashboard.py` wrote 37 technical records and detected 9 earnings-date shifts; `validate_dashboard_state.py --write` remained 0 critical / 1 expected NVDA event-risk warning. The added earnings/calendar evidence is freshness/catalyst context only; it does not grant promotion, sizing, sleeve, deployment, trade/account, or owner-approval authority.

## Status - 2026-05-14 WF58/WF56 guarded mutation posture pass

Status: **Implemented / scheduled proof monitoring**.

Implemented:
- Dashboard source freshness now emits explicit readiness gates:
  - `review_only`
  - `presentation_ready`
  - `canonical_sync_review_ready`
  - `capital_recommendation_ready`
  - `capital_action_allowed=false`
- Portfolio manual dependency is allowed as an owner-maintained source for presentation/recommendation readiness when it is the only manual dependency.
- Review-only discrepancy resolver is live:
  - `scripts/finance_discrepancy_resolver.py`
  - `scripts/test_finance_discrepancy_resolver.py`
  - outputs `tmp/finance-discrepancy-resolver.json/.md`
- Capital-deployment proposal packet generator is live:
  - `scripts/portfolio_mutation_proposal_generator.py`
  - `scripts/test_portfolio_mutation_proposal_generator.py`
  - output `tmp/portfolio-mutation-proposals/current-capital-deployment-recommendations.json`
- Capital-deployment packet Markdown renderer and authority validator are live:
  - `scripts/capital_deployment_recommendation_report.py`
  - `scripts/capital_deployment_recommendation_validator.py`
  - `scripts/test_capital_deployment_recommendation_validator.py`
  - outputs `optional Markdown digest beside `tmp/portfolio-mutation-proposals/current-capital-deployment-recommendations.json`` and `tmp/capital-deployment-recommendation-validation.json`
- Current-window artifact index includes discrepancy resolver, capital-deployment recommendation JSON, Markdown, and validator artifacts.
- Morning, post-close, and Sunday manifests now run the generator, Markdown renderer, authority validator, resolver, and current-window index.
- GS eligible entry-band update was applied through `apply_band_update.py --tickers GS --all`; non-applyable MSFT/AMD remain manual-review/wait-state blocked.
- Historical GS note-layer technical levels were synchronized before finance-canon consolidation; current execution-band owner surface is `03. Portfolio/Execution Board.md`.
- Scoped eligible daily band maintenance is live through `auto_apply_entry_band_maintenance.py --apply` after `band_refresh.py`.
- Weekly minimum note-layer reference-band refresh is live in the Sunday chain through `reference_band_note_sync.py --apply`, after eligible auto-apply and before entry-band/status consumers. The current canonical execution/reference-band owner surface is `03. Portfolio/Execution Board.md`; sync artifacts write restrictive authority labels and keep execution/capital/trade/approval/sizing authority false.
- Command Center payload split is implemented in `scripts/dashboard_payload.py`: `technical[]` and `deployment_records[]` now carry both gated `executionBand` values from `tmp/portfolio-config.json` and fresh `referenceBand` values from `tmp/band-proposals.json`; top-level `reference_bands.by_ticker` carries the daily reference map with visibility-only authority fields.
- 2026-05-15 false-green hardening: `scripts/deployment_readiness_surface.py` and `scripts/dashboard_payload.py` now fail closed on machine/prose conflicts. The first patch covered the known JPM conflict from Weekly Positioning Review + research-freshness handoff evidence; the priority pass generalized the guard so any green/deployable machine state contradicted by trigger-not-live, approval-on-hold, below-band/stop, repair/frozen, or review-only evidence renders as `AUTHORITY CONFLICT`, not clean deployable. JPM is removed from deployable-now groups and represented as `AUTHORITY CONFLICT` / `APPROVAL RECORDED / TRIGGER NOT LIVE` at both the upstream deployment-readiness surface and Command Center rendering layer. The JPM card suppresses clean machine execution-band `In band` / stop-distance wording and points the reader to the conflict note; almost substates only attach while the row is actually in an ALMOST state.

## Current proof state

Latest verified state:
- `tmp/dashboard-validation.json`: source freshness remains `manual_dependency / review_required`, but:
  - `presentation_allowed=true`
  - `canonical_sync_review_ready=true`
  - `capital_recommendation_ready=true`
  - `capital_action_allowed=false`
  - `canonical_note_mutation_allowed=false`
- Dashboard warning reduced from 3 stale/blocked bands to 2:
  - remaining manual-review blockers: `MSFT`, `AMD`
- `tmp/current-window-artifacts.json`: includes capital recommendation JSON/Markdown/validator roles after the 2026-05-14 wiring pass
- `tmp/finance-discrepancy-resolver.json`: review-only discrepancy queue; no cron apply authority
- `tmp/portfolio-mutation-proposals/current-capital-deployment-recommendations.json`: current guarded capital recommendation bundle; top-level posture allows WF58/WF56 portfolio note/model mutation workflow, while per-packet apply/approval/trade flags stay false
- `optional Markdown digest beside `tmp/portfolio-mutation-proposals/current-capital-deployment-recommendations.json``: operator-readable capital recommendation report
- `tmp/capital-deployment-recommendation-validation.json`: authority validator for the bundle and packets
- `tmp/reference-band-note-sync.json`: `status=ok`, `mode=apply`, `synced=19`, `scope=weekly minimum reference-band note refresh`, `reference_band_visibility_only=true`, and `execution_band_mutation_allowed=false`
- `tmp/dashboard-data.json`: includes top-level `reference_bands` plus per-row `referenceBand` / `executionBand` fields; latest regeneration is 0 critical / 1 warning for the expected NVDA event-risk freeze.
- `tmp/deployment-readiness-surface.json`: JPM now appears under `AUTHORITY CONFLICT`, not `DEPLOYABLE NOW`; summary shows `DEPLOYABLE NOW: 1` and `AUTHORITY CONFLICT: 1`.

Proof commands passed:
- `python -m py_compile ...`
- `python scripts\test_source_freshness_classifier.py`
- `python scripts\test_finance_discrepancy_resolver.py`
- `python scripts\test_portfolio_mutation_proposal_generator.py`
- `python scripts\test_capital_deployment_recommendation_validator.py`
- `python scripts\portfolio_mutation_proposal_schema_validator.py tmp\portfolio-mutation-proposals\current-capital-deployment-recommendations.json`
- `python scripts\capital_deployment_recommendation_validator.py tmp\portfolio-mutation-proposals\current-capital-deployment-recommendations.json`
- `python scripts\proposal_patch_scope_validator.py --write`
- `python scripts\canonical_status_invariant_validator.py --write`
- `python scripts\portfolio_pro_forma_risk_validator.py --write`
- `python scripts\authority_vocabulary_consistency_check.py --write`
- `python scripts\post_apply_validation_chain.py --write`
- `python scripts\test_run_summary_tail_order.py`
- `python scripts\test_auto_apply_entry_band_maintenance.py`
- `python scripts\test_reference_band_note_sync.py`
- `python scripts\test_dashboard_acceptance.py`
- `python scripts\generate_dashboard.py`
- `python scripts\validate_dashboard_state.py --write`
- `python scripts\run_finance_refresh_chain.py morning --dry-run`
- `python scripts\run_finance_refresh_chain.py post-close --dry-run`
- `python scripts\run_finance_refresh_chain.py sunday --dry-run`

## Truth and continuity spine

This workflow should explicitly use scripts and skills as separate control layers:
- **Scripts / artifacts:** generate fresh evidence, review packets, dashboard payloads, recommendation objects, and proof artifacts under `tmp/`.
- **Validators / guardrails:** prove freshness, authority boundaries, cross-surface coherence, and artifact presence before any completion claim.
- **Skills / procedures:** govern repeatable behavior: portfolio sync, automation hardening, workspace governance, response shape, and memory routing.
- **Canonical owner notes:** Portfolio Snapshot, Execution Board, Coverage and Watchlist, Risk Rules, and the relevant intelligence notes remain the human-readable truth layer.
- **Continuity:** this note owns resumable WF58 state; daily memory records only material deltas; durable memory gets only lasting operating decisions.

Acceptance addition:
- Any future WF58 sub-pass should identify its script/proof artifact, validator, canonical owner surface, and continuity destination before being called complete.

## Authority boundary

Allowed:
- cron/script generation of review packets, patch proposals, discrepancy queues, current-window indexes, archive suggestions, and proof artifacts
- main-session bounded canonical freshness/status sync after artifact confirmation and validation
- **2026-05-14 Randall-approved guarded mutation posture:** WF58/WF56 may now acknowledge portfolio note/model mutation authority at the workflow level. Veritas may apply exact validator-backed portfolio note/model adjustments for entry bands, ticker state, sleeves, sizing, and sector posture only inside approved gates. Cron may generate the bundle, Markdown report, authority validator, current-window index, and future exact apply artifacts for scoped portfolio note/model mutation, but cron must not self-apply high-consequence portfolio mutations.
- Current capital recommendation packets remain non-self-applying: per-packet `owner_approval_granted=false`, `apply_allowed=false`, `canonical_mutation_allowed=false`, `portfolio_mutation_allowed=false`, and `trade_or_account_action_allowed=false` remain required unless a separate exact apply artifact exists and passes validators.
- **2026-05-12 Randall-approved scoped automation:** daily finance chains may run `auto_apply_entry_band_maintenance.py --apply` after `band_refresh.py` to apply only machine-eligible `canonical_apply_eligible=true` entry-band maintenance proposals to `tmp/portfolio-config.json` and `03. Portfolio/Execution Board.md`, with audit proof in `tmp/auto-band-apply.json/.md`
- **2026-05-12 weekly reference-band automation:** Sunday finance chain may run `reference_band_note_sync.py --apply` to keep note-layer reference bands fresh for every complete tracked proposal. This writes reference visibility and restrictive authority labels only; it does not update `tmp/portfolio-config.json` execution bands or create deployability.
- **Command Center reference/execution split:** dashboard payloads distinguish (1) fresh **reference bands** for every tracked name, updated from `band_refresh.py` so Command Center is not showing stale chart levels, and (2) gated **execution bands** used for deployability/capital-deployment logic, auto-updated only when `canonical_apply_eligible=true` or explicitly approved by Randall. Reference-band payloads carry restrictive labels and authority flags so watch/repair/below-stop/above-band/timing-window names cannot look deployable from reference data alone.
- non-applyable proposals remain visible review-only/monitor-only debt, not execution apply candidates

Blocked:
- trade/account action
- brokerage orders or money movement
- per-packet owner approval inference
- self-applying capital recommendation packets
- sizing, sleeve, or sector-posture changes from cron packet generation without a separate exact approved apply artifact and validator proof
- cash, risk-rule, or execution-entitlement changes without separate explicit scope
- any band proposal where `canonical_apply_eligible` is false, earnings is not clear, suggested values are incomplete, or the method/status is outside the auto-apply allowlist
- cron applying any canonical portfolio/intelligence note edits outside scoped eligible entry-band maintenance
- treating clean validation as approval

## 2026-05-19 audit-directed dashboard/advisor update

The canonical audit at `08. Audits/Financial Advisor and Real-Time Alerting Readiness Audit - 2026-05-19.md` identified dashboard fragmentation and one concrete false-green risk: the 2026-05-18 machine summary reportedly described MSFT as both deployable-now/inside-band and `+2.66% above band`. Randall then made FA/advisor-grade monitoring and real-time/intraday alerting the primary goal. WF58 is therefore a required WF68 support lane: no alert system may consume a dashboard/advisory surface that can still produce false-green or contradictory action language.
- fix stale/contradictory generated summaries before they feed alerts or advisory packets
- pick one authoritative `what do I do now` surface instead of letting Executive Brief / Daily Summary / Pre-Market / Post-Market / Command Center drift apart
- feed WF68 only validator-clean advisory context with explicit source freshness and authority flags
- preserve the review-only / owner-gated boundary for all capital recommendation packets

## Residual queue

1. Fix or invalidate the MSFT false-green/above-band contradiction in the daily machine summary generator/artifact path before it can feed WF68 alerts.
2. Choose the single authoritative `what do I do now` surface and mark retired stubs/secondary dashboard surfaces as subordinate or redirect-only.
3. Monitor ordinary morning/post-close/Sunday cron proofs after the 2026-05-15 Command Center conflict/traceability hardening. Regression checks should confirm ETN remains the only clean deployable-now card unless artifacts change, JPM stays authority-conflict until the conflict clears, and pending handoff proofs do not auto-promote from worker artifacts alone.
4. If screenshots or user review show visual residue, add a render-level DOM/pixel test for Today Action card classes, duplicate ticker placement, repair-override wrapping, and the handoff proof panel.
5. Keep the discrepancy-resolver Markdown summary visible in Active Workflows / dashboard review surfaces when material warnings remain.
6. Design a Phase 3 exact apply-helper path only if a specific portfolio note/model mutation packet needs to move from recommendation to write; it must preserve the blocked trade/account boundary and run post-apply validation.
7. As WF58 sub-passes are completed, keep the truth-continuity mapping current: script proof, validator, canonical owner note, relevant skill/procedure, and continuity home.

## Future enhancement - staged tranche recommendation engine

Captured 2026-05-12; **defer, do not build yet**.

Idea:
- Add a review-only staged deployment recommendation object for promoted names such as MSFT.
- Example output: starter tranche while inside band but below 200-day; additional staged tranches after support/reclaim/20-day/200-day confirmation.
- Use planned allocation as the denominator, not total portfolio, and always keep `owner_execution_required=true`.

Safe boundary:
- May recommend staged percentages and trigger conditions.
- May flag concentration, chase risk, stop breach, stale sources, earnings proximity, or missing owner approval.
- Must not place trades, infer owner approval, alter live allocations, mutate sizing/cash/sleeves/risk rules, or auto-promote unapproved names.

Resume condition:
- Revisit only after current WF58 capital-rec Markdown/validator/index wiring is complete and several ordinary morning/post-close/Sunday cycles prove the newer auto-band/reference-band/dashboard paths are stable.
## 2026-05-15 late - promotion band-propagation hardening
- Randall caught a real dashboard truth failure: newly promoted review tickers could have numeric low/high/stop in config while dashboard/deployment consumers still showed sentinel labels like `WATCH_DEFINED_INITIAL` and false-green deployable states.
- Hardened the contract: promotion/review upgrades are incomplete until numeric bands/stops propagate through `tmp/portfolio-config.json`, `deployment_check.py`, `dashboard_payload.py`, `generate_dashboard.py`, and `validate_dashboard_state.py`.
- Current proof: `validate_portfolio_config.py --strict` ok 41/0; `deployment_check.py` shows ETN as only deployable-now and PH/LIN/CME as review-only; dashboard labels render numeric bands/stops for LIN/CME/PH/JPM and watch ETFs; dashboard validation 0 critical / 1 expected NVDA warning; dashboard acceptance 25/25.
- Boundary: this did not grant deployment/sizing/sleeve/trade authority. Reference bands/stops remain technical context unless a separate approved model/deployment gate exists.

## 2026-05-19 WF68 Phase 6 advisory action-language cleanup

WF68 Phase 6 closed the advisory contradiction class: `DEPLOYABLE NOW` + `IN_BAND` capital/advisor packets must not say `wait_for_band`, and proposed-band/reclaim statuses must not override the current written-band/no-chase posture. `scripts/daily_review_objects.py` now derives live entry status from deployment/current-band context and maps in-band `conditional_pullback_review` packets to `owner_decision_required`, preserving owner-gated review without implying a wait for a band that already exists. `scripts/portfolio_mutation_proposal_generator.py` carries both live and proposed-band status; `scripts/capital_deployment_recommendation_validator.py` now fails `IN_BAND` + `wait_for_band` and above-band false-green combinations. `scripts/intraday_alert_advisor_enricher.py` now records observed alert entry status and rejects in-band alerts labeled `wait_for_band`.

Regenerated artifacts show ETN as `DEPLOYABLE NOW` / `IN_BAND` with `owner_decision_required`; GOOG and MSFT remain `ABOVE_BAND_WAIT` / no-chase, with MSFT preserving `proposal_band_status=BELOW_RECLAIM_STOP` only as proposed/reclaim context. Proof passed: py_compile for touched scripts; `test_daily_review_objects.py`; `test_portfolio_mutation_proposal_generator.py`; `test_intraday_alert_advisor_enricher.py`; `test_intraday_alert_outcome_link.py`; `validate_dashboard_state.py --write`; `daily_review_objects.py --window post-close`; `portfolio_mutation_proposal_generator.py --window post-close --write`; `capital_deployment_recommendation_validator.py` ok 0/0; `intraday_alert_advisor_enricher.py` ok 0/0; `intraday_alert_outcome_link.py` ok 0/0.

Boundary: no portfolio/canon mutation, no execution authority, no owner approval inference, and no runtime/channel/cron wiring was added.

## 2026-06-05 deployment-state contract migration queue

Randall identified schema sprawl where `workflow_state = REPAIR`, `machine_state = BENCH`, and `action_state = DO NOT TOUCH` all surfaced in a single XOM status answer. WF58 should treat this as dashboard/deployment-state simplification debt, not as a reason to delete fields immediately.

Plan owner: `06. Playbooks/Project Continuity/Deployment State Contract Migration.md`.

WF58 role:
- Own the deployment/dashboard false-green risk while a shared state contract is introduced.
- Keep generated artifacts compatible until readers migrate.
- Ensure user-facing dashboard/capital surfaces display one canonical state plus reason, with legacy fields available only as trace context.

Acceptance addition:
- No WF58 dashboard, capital recommendation, or deployment-readiness surface may remove top-level legacy state aliases until the shared contract helper exists, representative consumers are migrated, and validation proves no downstream reader regression.
