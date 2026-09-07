# Workflow 73 - Queue, Index, and Boot Surface Optimization

## Objective
- Own the navigation/control-plane layer for Veritas so startup, queue selection, workflow routing, and helper-lane handoffs are flatter, faster, and less error-prone.
- Reduce main-session boot/load overhead without weakening SOUL/AGENTS/TOOLS boundaries or finance authority gates.

## Current State
- Opened 2026-05-21 23:20 MST after Randall approved making WF73 the dedicated owner for navigation/control-plane optimization under the broader WF72 Financial OS restructure.
- WF72 owns the full OS restructure; WF71 owns department/skill ownership; WF73 owns queue/index/boot-load control surfaces.
- Phase 1 contract inputs are complete and integrated as of 2026-05-21 23:25 MST: financial truth map, Today-card contract, WF71 department/skill ownership proposal, script ownership inventory, and the Phase 1 integration packet.
- Phase 2 proposal artifacts are complete as of 2026-05-21 23:50 MST: `tmp/wf73-boot-surface-load-map.json/.md`, `tmp/wf73-active-workflows-compression-proposal.json/.md`, and `tmp/wf73-startup-truth-index-proposal.json/.md`. Main session applied only low-risk boot tightening to `AGENTS.md`, `Startup Truth Index.md`, and `disciplined-implementation`; no duplicate durable control surface was created.
- Phase 3A thinning pass applied as of 2026-05-21 23:58 MST: `Startup Truth Index.md` was rewritten into a route-by-task boot map that points to Active Workflows, owner notes, current-window proof, WF71 skill routing, and WF72 script routing instead of carrying long proof lists/history. `Subagent Load Budget and Staff Handoff Standard.md` now includes the WF71 Department Routing Gate and positive/negative skill trigger checks. Backups: `backups/20260521-2358-phase3a`. Proof: structure check ok; `openclaw skills check` still shows `disciplined-implementation` visible, with the known browser plugin symlink EPERM warning.

## Scope
WF73 owns proposals and implementation plans for:
- `06. Playbooks/Active Workflows.md` compression and tiering.
- `06. Playbooks/Startup Truth Index.md` rewrite / routing map.
- workflow queue/index model and pickup routing.
- boot-file load budget across `SOUL.md`, `AGENTS.md`, `USER.md`, `TOOLS.md`, `MEMORY.md`, `HEARTBEAT.md`, and control notes.
- department/skill routing index handoff from WF71.
- script ownership index handoff from WF72/WF70.
- current-window artifact index simplification where it affects navigation and queue selection.
- helper-lane handoff/load-budget integration.

## Out of Scope / Stop Lines
- No identity/doctrine rewrite unless a specific stale/conflicting rule is proven and reviewed.
- No file moves/deletes/archive/renames without reference checks and explicit owner approval.
- No config/auth/channel/service/runtime mutation without explicit approval.
- No portfolio/canon/sizing/cash/risk/execution entitlement mutation from WF73 alone.
- No live/paper order, account action, money movement, or owner approval inference.
- No generated dashboard/report becomes canon or approval surface.

## Phased Approach

### Phase 0 - Contract inputs
- Consume Phase 1 WF72/WF71 artifacts:
  - `tmp/wf72-financial-truth-map.*`
  - `tmp/wf72-today-card-contract.*`
  - `tmp/wf71-department-skill-ownership-proposal.*`
  - `tmp/wf72-script-ownership-inventory.*`
- Acceptance: all inputs parse/read cleanly and preserve review-only/no-authority posture.

### Phase 1 - Boot and queue map proposal
- Produce review-only artifacts:
  - `tmp/wf73-boot-surface-load-map.json/.md`
  - `tmp/wf73-active-workflows-compression-proposal.json/.md`
  - `tmp/wf73-startup-truth-index-proposal.json/.md`
- Acceptance: proposes what main session always reads vs routes by task; preserves core boundaries; no apply.

### Phase 2 - Routing contracts
- Define control-plane routing for:
  - current priority selection
  - workflow pickup
  - cron/heartbeat escalation
  - helper-lane spawning
  - department/skill ownership lookup
  - artifact proof lookup
- Acceptance: routing table reduces ambiguity and names owner surfaces without duplicating truth.

### Phase 3 - Low-risk apply candidates
- After review, apply only low-risk text/structure changes that preserve proof links:
  - compressed Active Workflows layout
  - Startup Truth Index routing rewrite
  - staff-lane load-budget/handoff pointer
- Acceptance: main-session startup can find current goal, next action, blockers, proof, and stop lines quickly.

### Phase 4 - QA and drift guard
- Add validators/checks only if useful:
  - boot surface link check
  - queue/control-plane duplication check
  - stale active-workflow row check
  - skill routing trigger/negative-trigger check
- Acceptance: catches stale routing before it misleads the main session.

## Current Inputs / Evidence
- `legacy tmp artifact tombstoned in state/tmp-lifecycle-deletion-tombstone.json (wf72-full-restructure-synthesis.md)` - full workspace/script/skill restructure synthesis.
- `tmp/wf72-financial-canon-os-synthesis.md` - financial truth/cadence synthesis.
- `tmp/wf72-workspace-optimization-roadmap.md` - review-only WF72 roadmap.
- `tmp/wf72-script-ownership-inventory.*` - script ownership inventory when available.
- `tmp/wf72-today-card-contract.*` - Today-card contract when available.
- `tmp/wf72-financial-truth-map.*` - finance truth map when available.
- `tmp/wf71-department-skill-ownership-proposal.*` - skill ownership artifact when available.


## Phase 3E Active Workflows Compression - 2026-05-22 00:31 MST
- Applied WF73 Active Workflows compression in place. Backup: `backups/20260522-002919-phase3e-active-workflows/Active Workflows.md`. Apply proof: `tmp/wf73-active-workflows-compression-apply.json/.md` status ok. Independent read-only QA passed with no blockers: top snapshot has exactly one primary goal and next queue item; P0/P1 rows have required owner/next/action/gate/stop/proof fields; P2/P3/P4 monitor/paused/blocked routes are preserved; no finance/trade/account/paper/config/destructive authority widened; proof routes preserved for WF68, WF67, WF70/WF66, WF72/WF73/WF71, and WF64/WF56. QA proof: `tmp/wf73-active-workflows-compression-qa.json/.md`.
- Remaining Phase 3 residue after 3E: WF70 helper consolidation. Phase 4 SQL schema-v3 implementation can continue as a separate read/index/staging-only lane.

## Phase 4 schema-v3 control-plane update - 2026-05-22 00:46 MST
- Phase 4 schema-v3 is implemented in the existing artifact index rather than a new control plane. Proof/index surfaces: `tmp/veritas-artifact-index.sqlite`, `tmp/wf72-phase4-sql-schema-v3-implementation.json/.md`, and query commands `official-ir`, `lineage`, `canon-stage`.
- Control-plane rule remains: SQL helps find proof and staged review rows; canonical notes and exact approved apply artifacts remain truth/apply surfaces. No SQL row grants canon, portfolio, execution, paper/live order, or approval authority.

## Phase 4D SQL-first boot/proof routing update - 2026-05-22 17:22 MST
- Promoted SQL cockpit to the primary generated-artifact/proof/provenance/staging lookup route in boot and helper-lane protocols after WF72 schema v4 validation. Updated `AGENTS.md`, `06. Playbooks/Startup Truth Index.md`, `06. Playbooks/Active Workflows.md`, `TOOLS.md`, `skills/sqlite/SKILL.md`, `06. Playbooks/Automation Orchestration Protocol.md`, and `06. Playbooks/Operating Procedures/Subagent Load Budget and Staff Handoff Standard.md` to route artifact awareness through `scripts/artifact_index.py` commands first, then inspect target artifacts or canonical owner notes before claims. Proof: `tmp/wf72-sql-cockpit-boot-protocol-promotion.json/.md` status ok.
- Boundary preserved: SQL cockpit is derived proof/index/staging only. It is not canon, not owner approval, not an apply engine, not portfolio mutation authority, and not trade/account/paper execution authority. `tmp/current-window-artifacts.*` remains compatibility/fallback and cross-check, not the primary generated-artifact lookup path.

## Next Action
- The 2026-08-28 pass cleared all boot-size warnings. Keep WF73 in monitor/guard mode: run `scripts/boot_surface_size_guard.py` after boot/control edits, keep route surfaces thin, and use workflow-hygiene validation for stale queue rows.

## 2026-05-29 boot-surface reduction rollup
- Baseline proof: `tmp/wf73-boot-core-bloat-baseline-2026-05-29.json`. The approved pass converted startup/control files back to thin routing surfaces while preserving identity, finance/trading boundaries, live queue state, proof routes, and stop lines.
- Apply proof: `tmp/wf73-boot-bloat-reduction-apply-2026-05-29.json` and `tmp/wf73-soul-agents-bloat-reduction-apply-2026-05-29.json`. Reversible snapshots are preserved under `09. Archive/backups-archived-20260823/20260529-1222-wf73-*` and `09. Archive/backups-archived-20260823/20260529-1232-wf73-soul-agents-bloat-reduction/`.
- Added report-only guards: `scripts/boot_surface_size_guard.py` with `tmp/boot-surface-size-guard.json`, and `scripts/workflow_hygiene_check.py` with `tmp/workflow-hygiene-check.json`.
- WF72's historical continuity tail was compacted with its full snapshot under `09. Archive/backups-archived-20260823/20260529-1248-wf72-continuity-rollup/`; active state, boundaries, next actions, and proof routes stayed in the owner note.
- Detailed chronology remains in daily memory, proof artifacts, backups, and Git history. This note retains only the routing decision and durable outcome.
- No archive/delete, config/auth/channel/service/runtime, SQL-canon, finance/canon/portfolio, paper/live/account, or approval authority was added.

## SaaS/service UI and operator-routing dependency - 2026-05-28 21:08 MST
- WF75 now carries the service-led SaaS/product readiness plan at `tmp/wf75-saas-service-readiness-plan.*`.
- WF73 owns the navigation/control-plane side: the customer/operator status model, operator queue, proof/QA link routing, and preventing internal workspace mechanics from leaking into customer-facing UI.
- Required UI/UX posture: customer surfaces show intake, status, and deliverables; operator surfaces show intake completeness, analysis run state, QA state, proof links, and approval-to-send gates.
- Initial status model: `draft`, `needs_info`, `analysis_ready`, `qa_ready`, `approved_to_send`, `sent`.
- Boundary: do not expose workflow IDs, `tmp` paths, raw JSON, SQL tables, finance canon/cache details, or internal proof traces to customers. Keep full self-serve SaaS deferred until service delivery repeatability is proven.

## Key Files
- `SOUL.md` - identity/boundary constitution.
- `AGENTS.md` - startup/orchestration rules.
- `USER.md` - Randall preferences and finance boundaries.
- `TOOLS.md` - local runtime/tool posture.
- `MEMORY.md` - curated durable continuity.
- `HEARTBEAT.md` - heartbeat-only behavior.
- `06. Playbooks/Startup Truth Index.md` - startup routing target.
- `06. Playbooks/Active Workflows.md` - live workflow control surface.
- `06. Playbooks/Automation Orchestration Protocol.md` - helper lane orchestration.
- `06. Playbooks/Spawn and Closeout Governance Matrix.md` - spawn/closeout governance.

## Automation / Refresh Path
- WF73 starts as review/proposal only.
- Any validators should be lightweight and advisory until proven valuable.
- Any structural apply must preserve references and be separately reviewed.

## 2026-06-04 quick-routing posture sync
- WF73 now treats quick routing as the next control-plane implementation lane after operating-leverage load reduction and WF72 A2 completion. The route should be a thin wrapper/procedure over existing proof scripts, not another truth source.
- Current proof to inspect before routing: `tmp/automation-stack-hardening-pass.json`, `tmp/cron-freshness-spine.json`, `tmp/cron-signal-scorecard.json`, `tmp/escalation-trigger.json`, `tmp/pm-control-packet.json`, `tmp/veritas-artifact-index.sqlite` via `artifact_index.py validate`, and WF-specific owner artifacts.
- Quick route behavior may rank, route, and recommend the next safe proof/action. It must source-open exact artifacts before material claims and must not mutate cron, canon, portfolio, SQL/cache rows, customer surfaces, paper/live/account state, runtime config, or approval state.
- Keep boot/core files route-only. Procedure detail belongs in skills, scripts, and workflow continuity notes; generated proof remains JSON/SQLite-first.

## 2026-06-04 Cron freshness spine wiring

- Added `scripts/cron_freshness_spine.py`, a read-only main-session cron awareness surface. It reads `tmp/cron-operator-ledger.json` plus `tmp/operating-leverage-spine.json`, requires every enabled cron job to have an expected-artifact contract, and writes `tmp/cron-freshness-spine.json`.
- Wired consumers: `cron_signal_scorecard.py` now prefers the freshness spine; `escalation_trigger.py` records the scorecard source mode; `automation_stack_hardening_pass.py` fails if the spine is missing, invalid, has unregistered enabled jobs, lacks artifact contracts, or reports blocked jobs.
- Updated cron payloads without changing schedules or enabled count: `Operating Leverage - Escalation Trigger Check`, `Finance - Post-Close Control Digest Consolidated Handoff`, and `Cron - Main Session Failure and Action Watchdog` now route through the freshness spine.
- Current proof: `cron_freshness_spine.py --write --validate` reports 25 enabled / 16 disabled, 23 fresh, 2 needs-review, 0 stale, 0 blocked, 0 unregistered, validation ok. `cron_signal_scorecard.py --write --validate` consumes `source_mode=cron_freshness_spine`, reports 0 blocked and escalation remains false. Hardening pass is ok with 132 checks / 0 warnings / 0 critical.
- Boundary: review-only awareness and routing. No cron schedule expansion, no canon/portfolio mutation, no SQL write/import, no customer/external delivery, no paper/live/account action, no config/runtime mutation, and no owner approval inference.

## 2026-06-07 startup surface compression audit

- Randall requested a full audit of startup files including `TOOLS.md` and `MEMORY.md`, with migration to skills/WF notes/other owner surfaces where useful.
- Durable audit: `08. Audits/Startup Surface Compression Audit - 2026-06-07.md`.
- Applied route-only compression:
  - `TOOLS.md`: 9,079 -> 7,909 bytes.
  - `MEMORY.md`: 9,975 -> 7,792 bytes.
  - `06. Playbooks/Startup Truth Index.md`: 9,944 -> 8,760 bytes.
- Total boot/control size after pass: 96,043 bytes; `boot_surface_size_guard.py --write --validate` reports 0 warnings and 0 hard failures.
- Migration rule reaffirmed: startup files route; command catalogs live in `scripts/README.md`; workflow-specific state lives in workflow capsules/continuity; chronological detail lives in `memory/YYYY-MM-DD.md`; durable procedure lives in skills/operating procedures.
- Created pending Skill Workshop proposal `workspace-governor-20260608-a4535613aa` to add startup-surface compression rules to `workspace-governor`.
- Boundary preserved: no identity/doctrine weakening, no finance/canon/portfolio/paper/live/account/customer authority widening, no config/runtime/channel mutation, and no archive/delete.

## 2026-06-12 local Postgres coordination-spine plan

- Randall approved making the local Postgres coordination-spine idea durable and inserting it into an existing workflow. Owner: WF73, because this is queue/index/boot/control-plane coordination, not WF72 finance SQL promotion, not WF75 SaaS resumption, and not portfolio/canon authority.
- Main-session exception recorded: this pass stayed in main because the work was a bounded plan/control-surface insertion with no helper spawn, no code implementation, and no runtime/config mutation.
- Proof context: `tmp/local-postgres-readiness-benchmark.json` / `.md` shows the laptop is suitable for a light local-only Postgres operational spine if kept on `127.0.0.1` with health checks, reconnect/fallback behavior, and backups. Docker, `psql`, and local Postgres were not present/running at benchmark time.
- Durable plan artifact: `tmp/wf73-postgres-coordination-spine-plan.json` / `.md`.
- Goal: make cross-session coordination transactional so active lanes, workflow-scope claims, exact file leases, write intents, file-hash observations, validation runs, proof artifacts, and closeout events can be claimed and audited with database transactions while files/Git remain the actual code and note layer.
- Non-goal: do not replace SQLite proof DBs, generated artifacts, Markdown owner notes, portfolio/canon truth, Git diffs, or WF67/WF85 approval boundaries. Do not use Postgres as an authority source for finance approval, capital deployment, paper/live execution, or portfolio mutation.
- Phase 0 design only: define schema, adapter contract, backup/restore, health checks, local-only security, fallback behavior, and validators. Acceptance is plan/proof only; no service install.
- Phase 1 owner-gated local service pilot: only after explicit approval for service/runtime mutation, run local-only Postgres on `127.0.0.1`, create one database/user, store secrets outside repo, add health check and nightly `pg_dump` backup. Acceptance includes no LAN exposure and restore proof.
- Phase 2 shadow mirror: keep `concurrent_lane_manager.py` JSON register as primary while mirroring lane/register events into Postgres. Acceptance requires JSON/Postgres parity, fallback proof, and no behavior change.
- Phase 3 transactional lease backend: move claim/lease/write-intent checks behind Postgres transactions while continuing to emit the JSON register as a review/fallback artifact. Acceptance requires duplicate active write collisions, workflow-scope conflicts, stale TTL cleanup, and file-hash-change checks to fail closed.
- Phase 4 workflow/PM/cron integration: expose transactional coordination state to PM/cron/control packets and dashboards without granting scheduler, merge, canon, or execution authority.
- Phase 5 evaluate broader operational tables separately: job runs, alert dedupe, paper-order audit state, owner approvals, guard validations, and reconciliation events can be considered only as separate workflow work with their own gates.
- Candidate schema: `sessions`, `workflow_lanes`, `file_leases`, `write_intents`, `file_hash_observations`, `validation_runs`, `proof_artifacts`, `closeout_events`, `lease_heartbeats`, and `postgres_health_checks`.
- Stop lines: no Postgres/Docker/native-service install, config/auth/channel/runtime mutation, credential write, network exposure, SaaS production hosting, SQL-first control-plane authority, Git replacement, canon/portfolio mutation, paper/live execution, or owner approval inference without separate exact approval and validation.
- Next WF73 action: create a design-only schema/adapter proposal and validator contract before any install/runtime work. Implementation should start with a shadow mirror and fallback path, not a wholesale migration.

## 2026-06-12 WF73 phases B-C-D implementation

- B/C/D complete with proof in `tmp/wf73-phase-bcd-closeout.json`: boot-size guard ok, lane register 0 warnings, cron review queue 0, urgent/blocked/stale 0, and 12 unchanged standing review items quieted until their underlying signal changes.
- Phase D artifacts: `tmp/wf73-postgres-schema-adapter-proposal.json` / `.md`.
- Boundary preserved: no Postgres/Docker/native-service install, config/startup/credential/channel/network mutation, SQL-first authority, finance/canon/portfolio mutation, paper/live/account action, or owner-approval inference.

## 2026-06-12 WF73 Phase E review-only decision packet

- Randall chose review-only after Phase D. Created `tmp/wf73-postgres-phase-e-review-packet.json` / `.md`.
- Conclusion: concept valid, WF73 owner correct, service pilot deferred. Next review-only work: DDL contract, JSON/Postgres parity dry-spec, failure drills, backup/restore/rollback detail, and Docker-vs-native-Windows matrix.
- Blocked without exact approval: install/service/port/DB user/password/secrets/startup changes, live SQL writes from lane manager, Postgres-primary claims, or JSON fallback retirement.

## 2026-06-12 WF73 Postgres review and shadow status

- Review artifacts complete under `tmp/wf73-postgres-*-review.json`: DDL, parity, drills, Windows matrix, and go/no-go.
- Result: no service pilot now. JSON lane register remains primary. Passive shadow pilot approved for parallel-lane visibility.
- Shadow pilot active: `scripts/wf73_postgres_shadow_pilot.py` projects the lane register into shadow JSON/metrics after lane-manager writes.
- Boundary: no Postgres/Docker/native-service install, no config/startup/credential/channel/network mutation, no SQL execution, no lane-claim authority, no finance/canon/portfolio/paper/live/account action, and no owner-approval inference.

## 2026-08-22 Harness V2 Wave 1 - routing and lane-metadata truth

- Randall approved Wave 1 only. The durable cross-workflow plan is `06. Playbooks/Project Continuity/Veritas Harness V2 - Governance and Efficiency Upgrade Plan - 2026-08-22.md`; Waves 2-5 remain unapproved proposals.
- Refreshed `tmp/workflow-routing-index.json`, `tmp/workflow-routing-index.sqlite`, and `tmp/workflow-routing-index-validation.json`: 43 routes, zero critical findings, zero warnings, SQLite integrity clean. WF71, WF74, and WF88 router summaries resolve again.
- Updated `scripts/concurrent_lane_manager.py` and focused tests so terminal pre-Wave-1 identity gaps are classified as historical-unavailable rather than fabricated. Fourteen historical rows remain visible in one warning inventory; no missing `parent_job_id`, `attempt_number`, or `retry_count` was backfilled.
- New and active model-driven rows remain fail-closed under `new_model_lanes_have_parent_phase_attempt_identity`.
- The one historical cancelled lane lacking `ended_at_utc` has a valid `completed_at_utc`; the validator accepts that as historical terminal proof and records it in the informational fallback inventory. History was not rewritten.
- First independent QA rejected two real fail-open boundaries: active model rows with missing/invalid creation timestamps could bypass identity validation, and the new `completed_at_utc` fallback was not limited to historical non-complete rows. One bounded repair plus negative tests closed both defects.
- Focused lane-manager tests, compile proof, the adjacent runtime-metadata suite, SQL-canon exception tests, workflow-routing tests, and semantic-memory maintenance tests pass. Fresh independent read-only QA returned PASS against `scripts/concurrent_lane_manager.py` SHA-256 `fefaf100ece7cc4c8785150a75529566b81ff83997cf8751b29b33ddc48b6411`.
- Refreshed routing proof remains 43 routes / zero critical / zero warning. Refreshed harness readiness is 3 pass / 4 warning / zero fail; refreshed PM validation is `ok` but PM remains yellow with 3 blocked lanes and 1 stale lane.
- Boundary held: no schedule/service/runtime/config/auth/finance/canon/portfolio/delete/archive/skill-apply change and no route-efficiency credit without job-scoped usage proof.
