# Workflow 76 - Cron Automation Authority and Canon Auto-Update Expansion

## Objective
- Convert Randall's 2026-05-23 broader cron automation approval into a governed production lane for recurring workflow advancement, cleanup, validator refresh, official evidence refresh, and financial notes/canon auto-update support.
- Push mechanical repeatable work out of the main session while preserving Veritas main as final truth integrator for judgment, ambiguous canon conflicts, and owner-facing financial decisions.

## Current State
- Opened 2026-05-23 23:57 MST after Randall approved broader cron automation authority for cleanups, small implementations, recurring workflows, and financial notes/canon auto-update.
- Phase 0/1 proposal lanes completed in parallel and wrote:
  - `tmp/cron-automation-authority-matrix-proposal.json/.md`
  - `tmp/cron-broadening-job-designs.json/.md`
  - `tmp/financial-canon-cron-authority-scan.json/.md`
- Main-session integration promoted the compact authority contract to:
  - `tmp/cron-automation-authority-contract.json/.md`
  - `scripts/cron_authority_matrix_validator.py`
  - `scripts/bounded_auto_archive.py`
- WF70/WF66 evidence-spine generation/validation is now wired into `scripts/chain_manifest.py` after official capture/reconciliation and before downstream official bridge validation.
- The Sunday WF72/WF74 maintenance loop was manually proof-run successfully. CLI scheduling via `openclaw cron add` was blocked by Gateway pairing/scope-upgrade approval, so the job was scheduled through the first-class cron tool instead: `bd1c1f4d-b2e1-4307-9130-36f635f2a56c`.

## Authority Tiers

| Tier | Name | Cron can do | Cron cannot do |
|---|---|---|---|
| T0 | Observe/report | status, warnings, run summaries, ledger rows | mutate notes/canon/archive |
| T1 | Review-only artifact/dashboard refresh | write `tmp/` packets, dashboards, reports, SQL proof/index/staging | canonical/portfolio mutation or approval language |
| T2 | Patch proposal / semantic preview | generate canonical-note patch proposals, portfolio proposals, exact previews, verifier reports | apply patches or imply eligibility |
| T3 | Main-session bounded freshness/status sync | wake/handoff main session to inspect artifacts and apply bounded freshness/status sync | unattended direct cron note write |
| T4 | Exact gated workspace portfolio/canon maintenance | generate proposal/verifier; use existing narrow applies only where already approved | broaden direct apply; trade/account/cash/risk/execution changes |
| T4A | Future narrow cron-direct maintenance candidate | inactive placeholder only | any current direct apply |
| T5 | Bounded auto-archive movement | archive-only moves under approved policy | deletes or moving protected/canonical/current-window/script/skill/config files |
| TX | Blocked | nothing | live/paper-outside-WF67, credentials, config/service, deletes, approval inference |

## Financial Notes / Canon Posture
- Cron default is T1/T2: generate, validate, preview, and report.
- Main-session Veritas owns T3: inspect proved artifacts and apply bounded freshness/status sync when evidence supports it.
- Existing narrow direct-apply cron helpers remain category-specific, not a broad precedent:
  - `event_calendar_apply.py --apply`
  - `auto_apply_entry_band_maintenance.py --apply`
  - `canon_volatile_execution_board_sync.py --apply --strict-exit`
- WF64/WF56 broader portfolio/canon applies remain main-session-only unless a future exact category-specific T4A gate is explicitly promoted with repeated proof, lock, rollback, audit, and QA.

## Phases

### Phase 0 - Authority matrix and contract
- Complete: proposed and promoted T0-T5/TX tiers into machine-readable contract and validator.
- Proof: `python scripts\cron_authority_matrix_validator.py --write`.

### Phase 1 - WF70/WF66 official evidence auto-refresh integration
- Complete in manifest: `wf70_wf66_official_evidence_spine.py` and `--validate-only` are inserted into finance chain manifests after official capture/reconciliation.
- Acceptance: finance dry-run shows steps; evidence spine validation stays `status=ok`; downstream reconciliation/bridge validators stay clean.

### Phase 2 - Weekly WF72/WF74 maintenance loop
- Implement as review-only cron lane at Sunday 18:05 America/Phoenix, before continuity hygiene.
- Manual proof run passed on 2026-05-24 UTC: workspace index refreshed, SQL cockpit validated `27/0`, note-drift regenerated as review-only, cron authority validator passed `16/0`, bounded auto-archive dry-run performed no moves/deletes, and WF74 validate-only passed `24/0`.
- Scheduling status: scheduled through first-class cron tool as `bd1c1f4d-b2e1-4307-9130-36f635f2a56c` after CLI scheduling hit Gateway pairing/scope-upgrade approval.
- Stop lines: SQL authority widening, note-drift apply implication, WF74 boundary failure, or any note/config/archive mutation request.

### Phase 3 - Bounded auto-archive helper hardening
- `scripts/bounded_auto_archive.py` exists and is intentionally stricter than current suggestions.
- It moves nothing until an upstream suggestion is explicitly `apply_allowed=true`, owner approval is not still required, references are zero, destination is under approved archive roots, and kind is allowlisted.
- Current Sunday cleanup dry-run remains dry-run until policy-compliant suggestions exist and a controlled proof passes.

### Phase 4 - Financial note/canon proposal expansion
- Move more proposal/preview/verifier/reporting to cron, not broad direct apply.
- Main-session handoffs inspect current-window proof, canon drift gate, patch proposals, discrepancy resolver, post-apply validation, and full-portfolio validation before any bounded sync.

### Phase 5 - Future T4A candidate evaluation
- Only after repeated scheduled proof, exact category selection, lock/rollback/audit, no-drift proof, and independent QA.
- Candidate categories should start with low-risk freshness/status fields, not sizing/sleeve/cash/risk/execution entitlement.

## Stop Lines
- No live brokerage, live credentials, live endpoints, account changes, money movement, or live orders.
- No paper execution outside WF67 exact guardrails.
- No config/auth/channel/service/runtime mutation.
- No deletes.
- No inferred owner approval from clean validation, rank, score, dashboard state, or cron output.
- No cron-direct broad canon or portfolio apply.

## Next Action
1. Observe the first Sunday 18:05 WF72/WF74 review-only maintenance loop run and inspect proof artifacts.
2. Keep archive apply unscheduled until `archive_suggester.py` or a successor emits policy-compliant apply-eligible suggestions and controlled proof passes.
3. Use main-session handoffs for financial notes/canon sync until a future exact T4A gate is separately promoted.
4. If the CLI cron path is needed later, resolve Gateway pairing/scope approval separately; first-class cron scheduling is already active.

## Key Files
- `tmp/cron-automation-authority-contract.json/.md`
- `scripts/cron_authority_matrix_validator.py`
- `scripts/bounded_auto_archive.py`
- `tmp/cron-automation-authority-matrix-proposal.json/.md`
- `tmp/cron-broadening-job-designs.json/.md`
- `tmp/financial-canon-cron-authority-scan.json/.md`
- `scripts/chain_manifest.py`
- `06. Playbooks/Cron Job Protocol.md`
- `06. Playbooks/Cron Run Ledger.md`


## Proposed Sunday Maintenance Job Card

- Name: `WF76 - Weekly Cron Authority and OS Maintenance`
- Schedule: `5 18 * * 0`, timezone `America/Phoenix`
- Session: isolated / light context
- Tools: `read,exec`
- Delivery: none
- Timeout: 1800 seconds
- Command intent: run workspace index, SQL cockpit incremental + validate, DB lifecycle manifest validation, note-drift review report, cron authority validator, bounded auto-archive dry-run + report validation, and WF74 validate-only.
- Boundary: review/proof only; no canonical note/canon/portfolio mutation; no archive apply; no deletes; no config/auth/channel/service/runtime mutation; no owner approval inference; no live/paper order or brokerage/account action.
- Current status: scheduled through first-class cron tool as job `bd1c1f4d-b2e1-4307-9130-36f635f2a56c`; CLI `openclaw cron add` still requires Gateway pairing/scope approval if that route is needed later.
- DB lifecycle cadence: `python scripts\db_lifecycle_manifest.py --write --validate` is part of the weekly hygiene route so unlabeled SQLite residue reappears as a validator warning/critical instead of silently accumulating. Scan scope now includes `tmp/**/*.sqlite`, `state/**/*.sqlite`, and archived DB lifecycle files; `state/finance/finance-canon.sqlite` is protected live state. Archive apply remains outside cron and requires explicit owner approval plus `db_lifecycle_archive_apply.py` proof.


## Lean-OS archive cadence hardening - 2026-05-24 15:18 MST

- Randall asked that broad archive/flattening become ongoing OS hygiene, not a one-off cleanup. WF76 now owns the cron/governor side of this: recurring report/proposal cadence only, with no deletes and no broad cleanup apply from suggestions alone.
- Required posture for any archive cadence: run `archive_suggester`, `workspace_boundary_check`, and relevant validators; write review/report artifacts; apply only bounded auto-archive candidates that satisfy `06. Playbooks/Operating Procedures/Bounded Auto-Archive Policy.md`; preserve protected-surface denylist; write manifest/hash/rollback proof; notify main session.
- Cron must not move canonical finance notes, active workflow notes, memory, scripts, skills, config/auth/channel/service/runtime/credential surfaces, current-window validator inputs, SQL/cache authority surfaces, or proof-critical artifacts from suggestion alone.
- Scheduler/runtime mutation remains exact-approved; current first step is design/validation of the cadence packet, not silently adding a broad destructive job.


## Next-level workspace intelligence audit synthesis - 2026-05-24 16:10 MST

- Completed four no-mutation audit lanes: workspace organization, RSI/model optimization web scout, finance intelligence pipeline, and automation/runtime efficiency. Synthesis written to `tmp/next-level-workspace-intelligence-roadmap.*`.
- Main verdict: next-level upgrade should prioritize eval/outcome/trust coherence and narrow cleanup, not more candidate generation, broad archive sweeps, generic reflection, or new KG/vector memory. Top priorities: WF74 outcome eval suite v2 + finance-boundary fixtures; WF55 owner-decision/outcome retention ledger; advisor packet trust-coherence gate; narrow WF72 cleanup packets; prove WF76 before adding lean-OS cron; official-source reconciliation readiness queue; retrieval-quality scorecard before KG/vector expansion.
- Current blockers/trust limits: all current capital packets remain partial/action-blocked; WF55 remains NOT_READY; deployment presentation is degraded; cron has one red morning finance lane; archive suggestions remain apply_allowed=false; workspace boundary warning-only residue is `.claude/` and proof-critical `tmp/sql-canon-cache-rollback-phase3c.py`.
- Boundary preserved: no moves/deletes, no cron/config/auth/channel/service/runtime mutation, no canon/portfolio/trade/account/paper/live action, no money movement, no owner approval inference.
