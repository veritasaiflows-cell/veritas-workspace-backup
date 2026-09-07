---
name: "disciplined-implementation"
description: "Absorb recurring-friction diagnosis and full-body Skill Workshop safeguards into the canonical implementation owner."
---

# Disciplined Implementation

## Goal

Turn an authorized change request into verified workspace behavior with the smallest reliable execution route, explicit authority, bounded writes, deterministic proof, and truthful closeout.

Use this skill for scripts, validators, manifests, workflow code, boot/control surfaces, generated packet producers, material documentation contracts, and recurring implementation friction such as stale artifacts, validator-order defects, lane/write drift, or thin existing-skill proposals.

## Authority

This skill permits only the scoped workspace implementation the user authorized. It does not grant config/auth/channel/runtime/service mutation, cron schedule change, finance/canon/portfolio/cash/sizing/risk mutation, capital deployment, paper/live/brokerage/account action, external delivery, destructive cleanup, skill mutation outside Skill Workshop, or approval inference.

## Step 1: Classify And Route

Record objective, acceptance criteria, authority class, task shape, write scope, validation budget, owner surfaces, stop lines, and rollback path.

Use `scripts/project_implementation_router.py` and the `veritas.execution_efficiency_policy.v1` route order:

1. model-free deterministic command and proof;
2. explicitly opted-in Codex-native Terra for bounded non-QA read-only work, never implementation code;
3. Main/Astra for integration, acceptance, and authority-sensitive judgment, not implementation code or independent QA;
4. exact role-bound specialists through `veritas-model-routing-helper-lanes`, with fresh agent-matched transport proof and scoped-writeback proof for writes.

Record explicit owner-directed task-role overrides and actual model/backend/effort without changing persistent defaults. Missing transport never authorizes silent Main fallback; Main alone accepts. Preserve any default-router nonconformance until its verified scoped route exists.

## Canonical Implementation Commands

Use the exact owner commands when their surface is in scope:

- collision/lease status: `python scripts\concurrent_lane_manager.py --status --write --validate`
- changed-file validation route: `python scripts\changed_file_validator_router.py --write --validate`
- proportional validator plan: `python scripts\validator_bundle_router.py --write --validate`
- blocking release gate: `python scripts\implementation_release_contract.py --phase blocking --write --validate`

These commands do not widen authority. Run only the smallest set required by the task and current validation budget.

## Step 2: Collision And Lease Gate

Run the concurrent-lane status check before material work. Lease exact writable surfaces, not broad folders when exact files are known. Record parent job, lane, phase, attempt, retry, expected backend/model/thinking, started timestamp, and privacy-safe session attribution.

Existing dirty changes are user-owned unless proven otherwise. Preserve them and avoid overlapping writers.

## Step 3: Bounded Handoff

When delegating, provide an explicit workspace-relative base path, no more than 6 files / 120,000 bytes / 30,000 estimated context tokens, sorted inventory, byte sizes, SHA-256 hashes, contract hash, frozen snapshot ID, deterministic preflight, exact deliverable, validators, stop lines, next recipient, and timeout.

A persistent attachment lane must preflight the actual receiver/payload shape, not merely a nonce. For a shell-free receiver use a small manifest plus one raw UTF-8 source attachment at a time; verify readback names, bytes, hashes, and line limits before dispatch. Do not use compression or aggregate envelopes without a fresh proof for that exact decoder and reader.

State whether the lane is a `patch_draft` or verified `scoped_worktree_implementation`. A draft is not a shared-workspace change. Re-use an unchanged frozen snapshot for repair/QA. Send a changed-only delta when possible. Do not fork or replay the full conversation unless the worker genuinely needs it.

## Step 4: Implement Narrowly

Inspect exact producer and consumer contracts before editing. Patch only leased surfaces. Keep generated artifacts separate from source owners. Add regression coverage for the changed behavior and adversarial coverage for fail-closed boundaries.

Do not mix unrelated refactoring, cleanup, migration, or authority expansion into the feature lane. Adjacent deterministic metadata/proof residue needs a separately named lane.

## Recurring Friction And Existing-Skill Proposal Guard

Treat repeated friction as evidence, not annoyance. Name the recurring pattern before changing it, then classify it as one of:

- `code_patch`: a bounded deterministic script, test, or harness correction;
- `artifact_refresh`: a stale derived proof or index rebuild only;
- `skill_proposal`: reusable procedure debt that belongs in a pending Skill Workshop proposal;
- `owner_gate`: a config, collector depth, schedule, authority, or policy decision;
- `skill_workshop_full_body_repair`: an existing-skill proposal that is thin, stale, or risks replacing the live body.

When artifacts or validators disagree, inspect producer-consumer order first. Refresh source artifacts before downstream scorecards, harnesses, ledgers, and session packets. Lease exact code, proof/sidecar, SQLite WAL/SHM, and append-only ledger surfaces when relevant.

For an existing live-skill update, assume `proposal_content` becomes the full live `skills/<skill>/SKILL.md` unless the tool contract proves otherwise. Do not apply when the proposal is an addendum, summary, patch note, heading-hygiene note, `# Proposed Update` wrapper, materially unexplained shrink, or otherwise omits live doctrine.

Required existing-skill sequence:

1. Inspect the live `SKILL.md` and the pending proposal.
2. Build or revise one full-body merged document; insert the new rule in the narrowest relevant section.
3. Run the pre-apply pair/body guard and confirm the proposed body can stand alone.
4. Apply only with explicit user authorization.
5. Immediately read back the live `SKILL.md`, scan for thin-proposal residue, and rerun the body guard.
6. In a multi-skill lane, apply and verify one existing skill at a time; do not batch speculative body changes.

If a body replacement occurs, repair it through a full-body Skill Workshop proposal before closeout. Record unresolved friction honestly as fixed, expected-pending, backlog, or blocked owner decision; never make a loop look green by hiding debt.

## Step 5: Validate Proportionally

- `micro`: deterministic proof plus Main verification.
- `narrow`: focused tests/compile/lint plus Main verification.
- `shared` or `major`: deterministic preflight, focused tests, then one fresh independent QA pass.

Independent QA is required for shared contracts, broad surfaces, finance/runtime/authority sensitivity, or judgment-heavy semantics - not automatically for every implementation. A narrow low-risk patch can close with deterministic proof and Main verification.

Cap normal rework at one bounded repair and one fresh QA rerun. If a second substantive rejection remains, stop and rescope the contract instead of replaying the same broad bundle.

Tests prove only what they cover. Validate producer-consumer compatibility, authority flags, privacy boundaries, stale/fresh semantics, expected/actual route conformance, and real output artifacts.

For a Main-applied helper draft, QA must target the actual applied source diff: record the frozen snapshot ID, the applied diff hash, allowed paths, Main application result, commands run, and a `qa_target=actual_applied_diff` assertion. Never close on a proposed diff alone.

For v3 handoffs, acceptance must bind the manifest schema to the handoff contract version; a v2 wrapper around a v3 handoff, or the reverse, blocks rather than downgrading proof requirements. Treat frozen input integrity and post-apply verification as separate phases: re-hash frozen sources before dispatch; after Main applies a patch, preserve immutable frozen metadata and verify the actual workspace state using each changed file's frozen before-hash plus its post-apply hash and size. A no-op or changed path outside the frozen scope blocks.

The applied diff must be a bounded, hash-matched workspace artifact with normalized workspace-relative paths. QA must use a hash-matched result artifact tied to that exact applied-diff hash, frozen snapshot, changed-path list, and post-apply file hashes. Each QA command needs a recorded zero exit result, hash-matched output artifact, and the exact changed paths/post-apply hashes it validated. A self-attested command list, arbitrary hash, or unrelated test command is not completion proof.

## Step 6: Main Acceptance

Helper output is untrusted until Main checks live files, diffs, tests, generated artifacts, hashes, route conformance, and authority. QA is advisory evidence; it cannot accept work. Documentation may call work complete only after Main accepted and verified proof exists.

Any route mismatch, mutated frozen input, failed receiver preflight, invalid telemetry, tampered integrity proof, or unresolved material QA finding blocks acceptance.

## Step 7: Usage And Efficiency Closeout

For every material job record, when exposed:

- parent job, phase, attempt, retry, task shape, write scope;
- expected and actual backend/model/thinking;
- files, bytes, estimated context tokens, duration;
- input, cached input, uncached input, output, reasoning metadata, and total with explicit semantics;
- QA verdict, Main acceptance, incident state, rework, and proof;
- `provider_usage_unavailable` when the provider exposes no trustworthy counters.

Never invent token counts, use ingestion time as usage time, call API-equivalent cost an invoice, or store raw prompts/responses/tool payloads/headers/secrets/credentials/account identifiers.

Measure uncached and gross tokens per Main-accepted job, first-pass acceptance, time to accepted proof, retry tax, and escaped defects when the evidence is available. Prefer like-for-like comparisons. Incidents and invalid telemetry receive no success credit.

Automatic route ranking and promotion remain disabled. Randall may request descriptive efficiency review on demand; no fixed cohort pilot or minimum job count is required. Main must explicitly change policy.

## Incident Update

When a lane fails, stalls, overflows, or produces unusable proof, preserve the durable transition and issue a provisional status within 90 seconds. Include failure class, affected phase/attempt, whether state was preserved, immediate containment, and next proof step. Do not wait for the final forensic report before acknowledging the incident.

## Release And Continuity

Run the changed-file validator route and the appropriate closeout bundle. Update exact durable owners - startup truth, wiki generator, procedure, skill through Workshop, continuity note, or daily memory - when behavior changes. Keep constitutional boot files limited to identity, hard boundaries, stable preferences, environment invariants, and thin routing pointers; place repeatable procedure in owner skills or playbooks. Memory alone is insufficient for operating doctrine.

After this absorbed guard proves current through the governed apply and validation path, handle `implementation-friction-closeout` only through a separate explicit compatibility-deprecation proposal. Do not delete it merely because the target proposal exists.

## Closeout

Return outcome first, exact files/behavior changed, route used, validation proof, QA/Main acceptance, usage availability, remaining limitations, and next recommendation. Mark partial or blocked honestly; never imply finance, deployment, runtime, or execution readiness beyond proof.
