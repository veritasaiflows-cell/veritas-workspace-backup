---
name: "veritas-workspace-audit-orchestrator"
description: "Run workspace audits, classify findings, route proof-backed follow-ups, and preserve authority stop lines."
---

# Veritas Workspace Audit Orchestrator

Run evidence-backed audits of the Veritas workspace without turning generated proof into authority.

## Purpose

Produce a trustworthy audit packet for broad workspace health or targeted findings:
- current trust state
- concrete risks
- source-backed recommendations
- next repairs with acceptance proof
- explicit authority boundaries

Default posture is review-only. Do not clean up, archive, delete, mutate config/auth/runtime, change portfolio/canon state, or imply finance/trade/account approval unless Randall explicitly approves the separate action and the proper gate exists.

## Read First

For full workspace audits, read or route through:
- `SOUL.md`
- `AGENTS.md`
- `USER.md`
- `TOOLS.md`
- `06. Playbooks/Startup Truth Index.md`
- today's and yesterday's `memory/YYYY-MM-DD.md`
- `MEMORY.md` only when durable continuity matters
- the latest relevant audit under `08. Audits/`
- `python scripts\concurrent_lane_manager.py --status --write --validate`

For targeted reviews, start with the owning artifact, then read the smallest adjacent set of producers, consumers, validators, and governing notes needed to verify the claim.

## Audit Modes

Use the narrowest mode that answers Randall's request:
- **full workspace audit**: broad control-plane, continuity, skill, cron, PM, DB lifecycle, runtime, finance-boundary, memory, and workspace-governance review
- **targeted finding review**: one finding or cluster, with root cause, current status, fix options, and acceptance proof
- **control-plane health review**: PM, cron, runtime scorecards, lane register, artifact indexes, route registries, and boot surfaces
- **skill/procedure hardening review**: map audit residue into skills, operating procedures, validators, or queue items
- **finance authority review**: verify generated artifacts, routing state, paper/live boundaries, portfolio/canon mutation gates, and owner approval lines

## Full Workspace Procedure

1. Check lane state before any write or generated proof.
   - Run `python scripts\concurrent_lane_manager.py --status --write --validate`.
   - If writing an audit note or proposal, lease exact writable surfaces first.

2. Reconstruct the audit contract.
   - What is being audited?
   - What is out of scope?
   - Which generated artifacts are proof only?
   - Which surfaces carry authority?

3. Refresh thin truth surfaces before broad scans.
   - PM: `python scripts\pm_control_packet.py --write --write-db --validate`
   - Cron: `python scripts\cron_control_packet.py --write --validate`
   - Cron freshness when cron claims matter: `python scripts\cron_freshness_scorecard.py --write --validate`
   - Runtime: `python scripts\runtime_performance_scorecard.py --timed-quick --write --validate`
   - Artifact index: `python scripts\artifact_index.py --write --validate`
   - Go routes when Go validators are in scope: `python scripts\go_sql_helper_route_registry.py --validate`
   - DB lifecycle when SQLite ownership is in scope: `python scripts\db_lifecycle_manifest.py --write --validate`
   - Skills: `openclaw skills check`
   - Config: `openclaw config validate` when config claims matter; do not mutate config during the audit.

4. Inspect exact owner surfaces for any material finding.
   - Do not rely only on summaries.
   - If a generated artifact claims green, inspect the live source or validator that backs it.
   - If live scheduler/runtime state conflicts with generated artifacts, report the conflict instead of averaging them.

5. Audit across these lenses:
   - **authority**: no generated packet implies approval, account action, capital deployment, paper/live execution, or portfolio mutation outside a gate
   - **freshness**: timestamps, market data, cron last-run status, boot surfaces, and scorecards are current enough for the claim
   - **control-plane consistency**: PM, cron, lane register, route registry, and artifact indexes agree or conflicts are named
   - **DB lifecycle**: every SQLite DB has an owner, purpose, lifecycle, and retention posture
   - **skills/procedures**: repeated work routes to skills/procedures; skills have scope, boundaries, validation posture, and deprecation triggers
   - **workspace structure**: root exceptions, numbered domains, tmp-vs-durable placement, generated proof, final audits, and archive candidates are correctly owned
   - **memory continuity**: daily notes are append-only, not duplicated, and durable lessons are promoted to the right owner
   - **dirty worktree**: classify volume and risk; do not treat unrelated dirt as audit failure unless it blocks trust or execution

6. Rank findings.
   - P1: blocks trust, correctness, finance authority, config/runtime safety, or reliable startup/control state
   - P2: material operational debt that can mislead future work but has a safe workaround
   - P3: cleanup, ergonomics, or future hardening

7. Recommend concrete repairs.
   - Each recommendation needs owner surface, next action, stop line, and acceptance proof.
   - Prefer fixing the smallest real gap over broad restructuring.
   - If the right fix is durable behavior, route it into a skill, operating procedure, validator, or queue item.

8. Close honestly.
   - State what was validated.
   - State what was not checked.
   - State what remains blocked.
   - Close the lane with proof if a lane was opened.

## Targeted Finding Review Procedure

1. State the finding in one line.
2. Verify whether it is still live using current artifacts.
3. Inspect the exact owner file, producer, consumer, validator, and latest proof.
4. Classify the finding as live, stale, resolved, partially resolved, or superseded.
5. Identify root cause, blast radius, and recurrence risk.
6. Recommend one repair path and one acceptance proof path.
7. If the finding maps to a repeated pattern, recommend the exact skill/procedure/validator update.

## Skill And Procedure Routing

When an audit finds repeatable residue:
- repeated operator steps -> operating procedure
- agent behavior or decision routing -> skill
- deterministic safety check -> validator/script
- one-off result -> audit note or daily memory
- workflow-specific state -> workflow continuity note

Do not create a new skill when an existing skill can be tightened cleanly.

## Audit-To-Implementation Handoff

When Randall approves implementation of audit recommendations, start with a lane lease and implement in this order:

1. Repair live P1 trust/governance blockers.
2. Add or adjust routing and decision dockets so the system classifies the issue correctly next time.
3. Add local eval cases for each real failure mode.
4. Wire the new summary into startup/status/future pickup surfaces.
5. Use Skill Workshop for durable skill/procedure updates.
6. Rerun changed-file routing, validators, release contract, and closeout.
7. Update project continuity and daily memory.

For each material finding include severity, live proof, owner surface, root cause, blast radius, recommended lane type, stop line, acceptance proof, and whether a local eval case or Skill Workshop update is needed.

Recommended lane types:
- `Lane 0 governance repair`: deterministic local blocker that prevents control/release trust.
- `V2 decision docket/routing`: classification logic that prevents noisy residue from becoming fake work.
- `local eval harness`: regression cases from real failures.
- `startup/status wiring`: boot surfaces show the new truth state without waking on monitor-only rows.
- `Skill Workshop durability`: repeated operating behavior becomes a skill update proposal and is applied only with explicit approval.
- `monitor-only`: keep visible and refreshed; no code or schedule mutation.
- `owner decision`: stop until Randall approves a specific authority boundary.

## Web Calibration Rule

When the audit asks for external/web calibration, use current primary or high-quality sources for patterns, but translate them into local, validator-backed OpenClaw controls. External patterns do not override local finance authority, owner approval, or release-contract gates.

Recommended calibration themes:
- evals and regression suites for agents
- tracing and guardrails
- durable execution/stateful workflows
- human-in-the-loop approval boundaries
- routing/classification dockets
- control-plane observability

## V2 Acceptance Proof

A V2 audit implementation is complete only when:
- the original audit file exists under `08. Audits/`
- live P1 governance blockers are repaired or explicitly owner-routed
- local evals pass
- startup/status/future surfaces consume the new summary
- relevant skills/procedures are proposed/applied through Skill Workshop when approved
- `changed_file_validator_router.py --write --validate` passes
- `validator_bundle_router.py --write --validate` passes
- `implementation_release_contract.py --phase blocking --write --validate` is ready to close
- `control_closeout_bundle.py --validation-budget shared --write --validate` passes or any blocker is honestly lane-routed

## Output Format

Return findings in this order:
- conclusion
- scope audited
- proof refreshed
- top findings by severity
- recommendations
- stop lines / authority limits
- next concrete action
- intentionally deferred checks

For each finding include:
- evidence
- impact
- recommendation
- acceptance proof

## Stop Lines

Stop and ask before:
- archive/delete/move/destructive cleanup
- config/auth/network/channel/credential/startup/service/plugin/runtime mutation outside the workspace
- portfolio/canon mutation outside approved gates
- paper/live order action or account/brokerage action
- external/public action
- installing third-party ClawHub skills directly

## Good Audit Standard

A good audit makes it harder for the workspace to lie about its own state. It names the gap, the proof, the owner, the next repair, and the boundary.
