# Cron Patch Manager Efficiency Audit - 2026-06-14

Generated: 2026-06-14 18:43 America/Phoenix
Reference UTC: 2026-06-15 01:43 UTC

## Conclusion

Rating: A- opportunity / B current state

Cron patch and edit work is a high-leverage automation target. The current cron system is strong enough to operate safely, but patches still take too long because live scheduler edits, authority-boundary checks, backup discipline, artifact refresh, and stale-control cleanup are mostly operator-driven.

Expected gain from a dedicated cron patch manager:

| Work Type | Current Estimate | With Patch Manager | Expected Gain |
|---|---:|---:|---:|
| Simple payload/model/timeout edit | 20-45 minutes | 5-12 minutes | 60-75% |
| Risky finance cron patch | 60-120 minutes | 20-40 minutes | 50-70% |
| Stale control-plane cleanup | 10-30 minutes | 2-5 minutes | 70-85% |
| Long cron scheduler exposure | 2-15+ minutes foreground | 10-45 seconds launcher | 70-95% less exposure |
| Multi-cron audit after edits | 30-90 minutes | 10-25 minutes | 60-75% |

Best practical estimate: cron maintenance effort can fall by 2x to 4x, and false blocker cleanup can fall by 4x to 8x. Total daily cron runtime may improve 15-35% when paired with launcher jobs, component modes, and changed-only digests.

## Scope

Rating: A

This audit covers cron patch/edit workflow efficiency only:

- live cron payload/model/timeout/failure-alert edits
- deterministic runner and launcher patterns
- backup, diff, verification, and rollback ergonomics
- ordered control-plane refresh after cron edits
- finance authority boundary preservation

Out of scope:

- live trading, paper execution, brokerage/account action, money movement
- capital deployment approval
- portfolio/canon/cash/sizing mutation
- cron schedule expansion unless separately approved
- config/auth/channel/runtime mutation outside the workspace

## Current Bottleneck

Rating: C+

Cron changes take longest when the work combines live scheduler mutation with finance safety proof. The actual script patch is usually not the expensive part. The expensive part is proving the cron system is not lying after the patch.

Observed friction points:

- live Gateway cron edits require careful manual field handling
- prior job state must be preserved for rollback
- expected artifacts need validation after the edit
- scheduler status and artifact freshness can temporarily disagree
- control artifacts must refresh in dependency order
- long foreground jobs expose the cron agent to tool-call timeouts and misleading failures
- finance jobs require repeated no-authority-widening checks

Recent WF78 evidence: the old foreground cron command failed at the scheduler/tool-call layer, while the repaired launcher pattern returned quickly and let the background child write proof. The failure was not a capital, trade, paper/live, account, or alert-delivery failure. It was an orchestration-path fragility.

## Root Cause

Rating: B

The workspace has good cron validators, but it lacks a first-class cron patch workflow. Cron is treated as live infrastructure, yet the edit path is closer to a manual operating procedure than a structured deploy pipeline.

Root causes:

- no single tool owns plan -> diff -> backup -> apply -> verify -> rollback
- cron definitions are not fully normalized as code contracts
- control refresh ordering is not enforced by one command
- long finance crons sometimes ask the agent runtime to own too much foreground work
- scheduler-state reconciliation and artifact-state reconciliation are separate enough to create false blockers

## Proposed Fix: Cron Patch Manager

Rating: A

Build `scripts/cron_patch_manager.py` as the standard route for cron patches.

Minimum viable capabilities:

1. Plan
   - Load live cron job by id or name.
   - Show exact proposed diff for payload, model, thinking, timeout, failure alert, description, and schedule.
   - Classify authority impact.
   - Refuse unclear job matches.

2. Apply
   - Write timestamped backup before mutation.
   - Apply only explicitly allowed fields.
   - Preserve finance authority boundaries.
   - Refuse delivery, schedule, runtime, or authority widening unless a separate explicit flag is used.

3. Verify
   - Run the job-specific deterministic runner or launcher.
   - Refresh controls in this exact order:
     `cron_operator_ledger -> cron_freshness_spine -> cron_signal_scorecard -> escalation_trigger -> cron_control_packet`
   - Fail if live scheduler state and generated control state remain inconsistent.

4. Rollback
   - Restore from backup.
   - Run the same ordered verification path.
   - Write proof artifact.

Primary output:

- `tmp/cron-patch-manager.json`
- optional backup under a scoped backup directory
- no Markdown sidecar unless explicitly needed for human review

## Cron-As-Code Opportunity

Rating: A-

Add canonical cron contracts under a controlled path such as:

- `state/cron-contracts/*.json`

Each contract should include:

- job id and name
- owner workflow
- intended schedule
- exact command or launcher
- model, thinking, timeout, and light-context posture
- expected artifacts
- allowed authority
- failure-alert policy
- delivery posture
- validation commands

Live Gateway state should become the deployed copy. Contract drift should be visible as a validator finding before cron changes become confusing.

## Runner Architecture Opportunity

Rating: A

Standardize enabled crons into three runner classes:

| Class | Use | Target Runtime |
|---|---|---:|
| Launcher job | Long finance chains, broad refreshes, fragile shell-call paths | 10-45 seconds foreground |
| Deterministic runner job | Short/medium proof jobs with a single command | under 5 minutes |
| Main-session handoff job | Human-facing review or owner decision prompt | no shell work |

WF78 has already proven the launcher pattern. Any cron that routinely exceeds 60-90 seconds should be reviewed for launcher conversion or component-mode splitting.

## Finance Authority Guardrails

Rating: A

The patch manager must preserve these hard stops:

- no capital deployment approval
- no paper/live trade or order
- no brokerage/account action
- no money movement
- no inferred owner approval
- no portfolio/canon/cash/sizing/sleeve/risk-rule mutation
- no external/customer delivery
- no config/auth/channel/runtime widening

Cron patching may improve orchestration, proof, and alert readiness. It must not turn review-only finance automation into execution authority.

## Implementation Plan

Rating: A-

Phase 1: MVP patch manager

- inspect live job
- generate JSON diff
- backup job state
- apply payload/model/thinking/timeout/failure-alert changes only
- run ordered verification
- write `tmp/cron-patch-manager.json`

Phase 2: Contract support

- add cron contract JSON files for high-value jobs first
- compare live state to contract
- flag drift in cron control packet or a dedicated cron contract validator

Phase 3: Broader runner standardization

- convert long foreground jobs to launchers
- split broad runners into component modes
- use changed-only digests where practical
- reduce duplicate control-plane proof inside PM and finance cron batches

## Acceptance Proof

Rating: A

MVP is acceptable when:

- patch manager can plan a one-job payload/timeout/failure-alert change without applying it
- patch manager writes a backup before any apply
- apply can update exactly one low-risk cron field set
- rollback restores the prior job state
- ordered verification ends with:
  - `cron_control_packet.status=ok`
  - `blocked_count=0`
  - `escalation_signal_count=0` unless an intentional test failure is active
  - no authority boundary widening

Hardened version is acceptable when:

- live-vs-contract drift is visible
- stale scheduler/artifact mismatch is detected and explained
- long-runner launcher conversion has a standard template
- patch manager refuses schedule, delivery, config, or authority changes by default

## Estimated Build Cost

Rating: B+

Estimated implementation effort:

- MVP: half day
- Hardened version: 1-2 days
- Contract migration for all high-value crons: incremental, likely several passes

ROI is strong because cron is now core operating infrastructure. The first version should be used on one low-risk cron edit before applying it broadly.

## Recommendation

Rating: A

Build `cron_patch_manager.py` next as a narrow tool, not a broad cron rewrite.

First target:

- one low-risk non-finance or proof-only cron
- payload/timeout/failure-alert field only
- no schedule change
- no delivery change
- no model expansion unless explicitly approved

Then promote the pattern to WF78/Post-Close/Tier-A style finance jobs after the manager proves backup, apply, rollback, and ordered verification cleanly.

## Deferred Checks

Rating: B

Deferred until implementation:

- exact Gateway mutation API behavior for patch manager apply/rollback
- preferred backup directory and retention policy
- whether contract files should be generated from live state first or hand-authored for critical jobs
- whether cron control packet should directly call or depend on the patch manager's ordered refresh proof

## Authority Boundary

Rating: A

This audit is review-only. It does not mutate cron state, scheduler state, config, runtime, channels, portfolio/canon files, cash/sizing/sleeve/risk rules, paper/live trading, brokerage/account state, or external delivery. It does not infer owner approval.
