# Active Workflows

## Purpose

This is the compact live workflow control surface for Veritas.

Use this note for what is active, paused, blocked, cron-owned, or archive-ready. Keep detailed history in the linked continuity notes, the IC registry/history surfaces, and `09. Archive/`.

## Operating rules

- This note is the first place to check before opening or continuing workflow work.
- Cron-owned work belongs here only as a monitor/link; operational proof stays in `06. Playbooks/Cron Run Ledger.md`.
- This note is the authoritative live status surface for active, paused, blocked, cron-owned, and archive-ready work.
- `06. Playbooks/OpenClaw Parallel Pilot Queue.md` remains the detailed sequencing/handoff surface until fully retired; if it conflicts with this note, reconcile this note first.
- `06. Playbooks/IC Project Registry.md` should become a thin owner/lane index, not a duplicate workflow history dump.
- Archive and cleanup recommendations are review-only until owner-approved; do not delete, move, or archive referenced notes blindly.
- Portfolio mutation, owner approval, sizing, sleeve, cash, execution entitlement, risk-rule changes, config/auth/channel/network changes, destructive cleanup, and trades remain explicit Randall-approval gated.
- Every active workflow should preserve a truth/continuity spine: scripts produce proof artifacts and validators, skills define the repeatable operating behavior, canonical notes remain the owner truth layer, and continuity notes/memory preserve only material decisions and pickup state.

## Current active workflow

| Workflow | Status | Owner | Next action | Acceptance gate | Stop lines | Continuity / proof |
|---|---|---|---|---|---|---|
| WF58 - Dashboard freshness, entry-band automation, capital recommendations, and discrepancy resolver | Active priority | Veritas main + bounded helper lanes | Finish capital-rec Markdown/validator, current-window role test, cron posture verification, and auto-band/reference-band proof monitoring; staged tranche recommendation engine is captured as a future enhancement only | Dashboard gates are explicit; presentation/canonical-sync-review/capital-recommendation readiness are true when sources support them; recommendation packets and discrepancy queues validate review-only; eligible daily entry-band maintenance may auto-apply through `auto_apply_entry_band_maintenance.py --apply` with audit proof; Sunday chain now runs weekly minimum note-layer reference-band refresh through `reference_band_note_sync.py --apply`; Command Center payload now separates fresh reference bands from gated execution bands without implying execution entitlement; workflow preserves the truth/continuity spine: script proof -> validator -> canonical owner note -> continuity checkpoint | No trade/account action, no owner-approval inference, no sizing/sleeve/cash/risk-rule/execution-entitlement changes, no non-eligible execution-band apply, no reference-only band presented as deployable, no silent portfolio mutation beyond scoped eligible entry-band maintenance/reference visibility; no staged-tranche automation build until explicitly resumed | [[06. Playbooks/Project Continuity/Workflow 58 - Dashboard Freshness Entry Bands Capital Recommendations and Discrepancy Automation]]; `tmp/dashboard-validation.json`; `tmp/dashboard-data.json`; `tmp/auto-band-apply.*`; `tmp/reference-band-note-sync.*`; `tmp/band-proposals.json`; `tmp/finance-discrepancy-resolver.*`; `tmp/portfolio-mutation-proposals/current-capital-deployment-recommendations.json`; `tmp/current-window-artifacts.*` |
| WF56 - Portfolio Mutation Proposal Object and Gated Apply Helper / Phase 2 | Implemented / validator follow-through | Veritas main | Keep validators green while WF58 capital-rec packets use the generator; defer Phase 3 dry-run patch helper unless separately approved | Current generated bundle validates cleanly; WF56 validators pass; post-apply chain remains dry-run/planned by default | No write-capable apply helper, no scheduled mutation, no owner-approval mutation, no trade/account action | [[06. Playbooks/Project Continuity/Workflow 56 - Portfolio Mutation Proposal Object and Gated Apply Helper]]; `tmp/*validation*.json`; `tmp/portfolio-mutation-proposals/current-capital-deployment-recommendations.json` |
| WF59 - Continuity and Compaction Hardening | Implemented / monitoring | Veritas main | Monitor compaction behavior over normal use; keep archive candidates review-only; next optional pass is queue-history compaction and reference checks | Telegram removed/disabled; compaction tuning applied and config validates; Startup Truth Index and AGENTS post-compaction recovery path are live; duplicate/sprawl audit findings staged without moves/deletes | No auth/channel/network/plugin/service widening; no delete/move/archive without approval; no second memory system; future channel re-enable requires explicit owner approval | [[06. Playbooks/Project Continuity/Workflow 59 - Continuity and Compaction Hardening]]; [[06. Playbooks/Startup Truth Index]]; `tmp/wf59-disable-telegram-and-compaction.patch.json5`; `tmp/wf59-continuity-sprawl-audit.md` |

## Newly active operating-system cleanup lane

| Lane | Status | Owner | Next action | Acceptance gate | Stop lines | Notes |
|---|---|---|---|---|---|---|
| Workspace simplification / portfolio communication layer | Active sidecar | Veritas main + parallel research lanes | Make `tmp/full-portfolio-view.json/.md/.html` the default portfolio communication surface; add artifact taxonomy; stage archive candidates without moving them | `full_portfolio_view_validate` remains clean; artifact classes are documented; archive candidates are review-only | No canonical finance mutation beyond bounded freshness/status sync; no destructive cleanup or archive moves without approval | Current safe product surface: `tmp/full-portfolio-view.*` |
| Active Workflows migration | Active sidecar | Veritas main | Truth-sync queue/registry, then demote registry/history clutter into archive candidates; add the truth/continuity spine to active workflow contracts as they are touched | Registry no longer contradicts queue/memory; duplicate continuity notes are reference-checked before any move; each active workflow names proof artifacts, canonical owner surface, relevant skill behavior, and continuity home | No delete/move/archive without approval | This note is v1 of the compact control surface |

## Paused / resume-later

| Workflow | Status | Resume trigger | Stop lines | Continuity |
|---|---|---|---|---|
| WF55 - Probability Readiness and Outcome Retention Gate | Paused / reprioritized | Resume only for methodology, validator rules, outcome-label hygiene, and known-at-time/realized-outcome separation | No predictive scores, win probabilities, expected-return claims, or deployment authority | [[06. Playbooks/Project Continuity/Workflow 55 - Probability Readiness and Outcome Retention Gate]] |
| WF37 - Daily Summary Commercial Brief Hardening | Paused follow-up | Resume after higher-priority finance/canon/reporting cleanup | No authority widening | [[06. Playbooks/Project Continuity/Workflow 37 - Daily Summary Commercial Brief Hardening]] |
| WF44 / WF45 follow-ups | Paused follow-up | Resume for residual dashboard truth alignment or artifact-index/source freshness provenance | No dashboard/cached payload may outrank canonical owner notes | [[06. Playbooks/Project Continuity/Workflow 44 - Command Center Decision Object Visibility and Truth Alignment]]; [[06. Playbooks/Project Continuity/Workflow 45 - Shared Stale Source Fail-Soft Classifier]] |

## Blocked / operator-gated

| Workflow | Status | Blocker | Required approval / next step |
|---|---|---|---|
| WF49 - FRED Runtime Environment Persistence | Blocked / operator-gated | Credential/runtime environment handling | Rotate/replace credential outside chat, configure runtime inheritance, restart/verify, and scan for leaks. No secret handling in workspace notes. |
| WF50 - Tmp Helper Archive Cleanup | Blocked / owner-gated | Cleanup/archive can move/delete workspace files | Generate archive suggestions and reference checks first; ask Randall before any move/delete/archive. |
| Root backup cleanup | Blocked / owner-gated | `backups/` and `.backups/` are root drift but may be safety backups | Inspect/reference-check first; ask before moving or deleting. |

## Autonomous generation posture

Current approved autonomy is generation-first and review-gated:
- Cron and scripts may generate refreshed artifacts, review packets, proposal objects, snapshots, summaries, dashboards, printable/visual reports, guardrails, and patch proposals.
- Generated surfaces may rank, route, summarize, warn, and stage exact review objects, but they do not become portfolio truth by themselves.
- Veritas main remains responsible for note-layer/canon upkeep and final integration.
- Canonical note changes stay bounded to explicitly approved helpers or main-session review/apply. As of 2026-05-12, Randall approved scoped automatic daily entry-band maintenance: machine-eligible `canonical_apply_eligible=true` proposals may update `tmp/portfolio-config.json` and `03. Portfolio/Technical Entry and Invalidation Sheet.md` through `auto_apply_entry_band_maintenance.py --apply` with audit proof. The Sunday chain now also runs `reference_band_note_sync.py --apply` as the weekly minimum note-layer reference-band refresh; it writes reference visibility and restrictive authority labels only, not execution-band mutations. Command Center payloads now expose fresh `referenceBand` / `reference_bands.by_ticker` from `tmp/band-proposals.json` alongside gated `executionBand` from `tmp/portfolio-config.json`, with authority flags preventing reference-only bands from implying deployment. Portfolio mutation beyond entry-band maintenance, owner approval, sizing, sleeve, cash, risk-rule, execution entitlement, account actions, and trades remain blocked without separate scoped Randall approval.

## Cron-owned operational monitors

These are operationalized generation/proof surfaces, not active project workflows. Keep proof in `06. Playbooks/Cron Run Ledger.md`.

| Monitor | Owner | Status | Proof surface | Notes |
|---|---|---|---|---|
| Finance morning refresh | Cron + Veritas verification | Operational + scoped auto-band maintenance | `tmp/run-chain-morning.json`, `tmp/run-summary-morning.json`, `tmp/auto-band-apply.*` | Review/report generation plus eligible entry-band maintenance only; no trade/sizing/approval authority |
| Finance post-close refresh | Cron + Veritas verification | Operational + scoped auto-band maintenance | `tmp/run-chain-post-close.json`, `tmp/run-summary-post-close.json`, `tmp/auto-band-apply.*` | One post-close writer per day; avoid duplicate state-history appends; eligible entry-band maintenance only |
| Finance Sunday refresh / visual PDF | Cron + Veritas verification | Operational with Sunday PDF live-proof pending + weekly reference-band sync | `tmp/run-summary-sunday.json`, `tmp/reference-band-note-sync.*`, Weekly PDF outputs | PDF render is review-only; reference-band note sync is visibility-only and grants no execution authority |
| Board/canon guardrails | Cron-generated / Veritas-reviewed | Operational | `tmp/board-canon-guardrail.*`, `tmp/stale-intelligence-guardrail.*` | Detects contradictions; does not apply note edits |
| Canonical note patch proposals | Cron-generated / main-session reviewed | Operational | `tmp/canonical-note-patch-proposal.*`, `tmp/portfolio-snapshot-patch-proposal.*` | Cron may propose; main session may apply bounded freshness/status sync only |
| Full Portfolio View | Cron-generated / primary communication surface | Operational | `tmp/full-portfolio-view.*`, `tmp/full-portfolio-view-validation.json` | Default source for portfolio viewing/communication |
| Security daily bounded audit | Cron + Veritas review | Closed blocker / scheduled confirmation watch | `tmp/cyber-security-daily-audit-cron-proof.json` | No config/auth/channel/network mutation without approval |
| WF56 proposal validators | Cron/report-capable / review-only | Operational | `tmp/proposal-patch-scope-validation.json`, `tmp/canonical-status-invariant-validation.json`, `tmp/portfolio-pro-forma-risk-validation.json`, `tmp/authority-vocabulary-consistency.json`, `tmp/post-apply-validation-chain.json` | Validation/proof only; clean validation is not approval |
| WF58 capital recommendation packets | Cron-chain generated / review-only | Operational in morning/post-close/Sunday manifests | `tmp/portfolio-mutation-proposals/current-capital-deployment-recommendations.json` | Owner-gated recommendation packets only; no apply path, sizing, approval, execution, or account authority |
| WF58 discrepancy resolver | Cron-chain generated / review-only | Operational in morning/post-close/Sunday manifests | `tmp/finance-discrepancy-resolver.json`, `tmp/finance-discrepancy-resolver.md` | Queues discrepancies such as earnings dates/canon/artifact conflicts; `cron_apply_allowed=false` |
| Current-window artifact index | Cron-generated / review-only | Operational | `tmp/current-window-artifacts.json`, `tmp/current-window-artifacts.md` | Navigation/index only; no artifact promotion or canonical mutation |
| Workspace governor / cleanup suggestions | Cron/report-only | Operational monitor | archive suggestions / governance reports | Suggestions only; no destructive cleanup |

## Archive candidates / duplicate cleanup queue

Do not move these yet. First run reference checks and confirm whether the active or archive copy is the keeper.

Current generated suggestion report:
- `tmp/archive-suggestions.md`
- `tmp/archive-suggestions.json`
- status: review required; no files moved/deleted; owner approval required

- `06. Playbooks/Project Continuity/Capital Deployment Readiness - Phase 0 Contract.md`
- `06. Playbooks/Project Continuity/Capital Deployment Readiness - Phase 1 Audit.md`
- `06. Playbooks/Project Continuity/Capital Deployment Readiness - Phase 2 Surface Design.md`
- `06. Playbooks/Project Continuity/Coverage Tier Framework.md`
- `06. Playbooks/Project Continuity/E17 Universe Synchronization - Earnings Block Architecture.md`
- `06. Playbooks/Project Continuity/E17 Universe Synchronization - Phase 0 Decision.md`
- `06. Playbooks/Project Continuity/Research Department Operating Model.md`
- `06. Playbooks/Project Continuity/Sector Coverage Expansion Plan.md`
- `06. Playbooks/Project Continuity/Veritas OS Automation Spine.md` — **high-confidence duplicate** of archived copy; verify references before removing active copy

## Current simplification decisions

- `tmp/full-portfolio-view.json/.md/.html` is the preferred portfolio communication layer.
- `tmp/dashboard-data.json` is UI payload only, not portfolio truth.
- `tmp/` remains generated/staged output, not durable human-facing canon.
- Research passes accepted as durable should move to `04. Research/`; final audits to `08. Audits/`; durable workflow pickup truth to `06. Playbooks/Project Continuity/`.
- Large folder moves in `01`-`05` are deferred until script references and validators are updated.
- `06. Playbooks/Startup Truth Index.md` is the thin post-compaction pickup map; use it to reduce broad startup rereads, but canonical owner notes still win.
